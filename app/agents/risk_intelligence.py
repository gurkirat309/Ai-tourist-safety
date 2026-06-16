"""Risk Intelligence agent (M4).

Pipeline per run:
  fetch raw items from pluggable sources
    -> extract structured, geo-tagged risk events (LLM, or heuristic in dry-run)
    -> map location to a Bengaluru zone
    -> dedupe (seen-store + existing source_url)
    -> persist `risk_events` with grounding (source / event_time / confidence)
       and a pgvector embedding.

No LLM call ever touches the real-time alert path — this agent runs on a
schedule and only writes grounded risk signals for later retrieval.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.seen_store import SeenStore, default_seen_store, item_hash
from app.agents.sources import RawItem, RiskSource
from app.core.logging import get_logger
from app.db.enums import RiskEventType
from app.db.models import RiskEvent, Zone
from app.db.spatial import geom_to_shape, point_to_geom
from app.services.embeddings import embed
from app.services.llm import LLMClient

log = get_logger(__name__)

_EXTRACT_SYSTEM = (
    "You extract structured public-safety risk events for tourists in "
    "Bengaluru, India from news snippets. Return STRICT JSON: "
    '{"events": [{"event_type": one of '
    "[crime, natural_hazard, civil_unrest, accident, health, advisory, other], "
    '"title": str, "description": str, "location_name": str|null, '
    '"lat": float|null, "lon": float|null, "event_time": ISO8601|null, '
    '"confidence": 0..1}]}. Only include events relevant to safety. If none, '
    'return {"events": []}.'
)

# Heuristic keyword -> event type, used in dry-run (no LLM).
_KEYWORDS: list[tuple[RiskEventType, tuple[str, ...]]] = [
    (RiskEventType.CRIME, ("snatch", "theft", "robbery", "crime", "chain", "assault", "scam")),
    (RiskEventType.NATURAL_HAZARD, ("flood", "waterlog", "landslide", "storm", "rain", "cyclone")),
    (RiskEventType.CIVIL_UNREST, ("protest", "bandh", "riot", "unrest", "strike", "clash")),
    (RiskEventType.ACCIDENT, ("accident", "crash", "collision", "derail", "fire")),
    (RiskEventType.HEALTH, ("outbreak", "dengue", "flu", "virus", "contamination")),
]


@dataclass
class ExtractedEvent:
    event_type: RiskEventType
    title: str
    description: str | None
    location_name: str | None = None
    lat: float | None = None
    lon: float | None = None
    event_time: datetime | None = None
    confidence: float = 0.5


@dataclass
class RunResult:
    fetched: int = 0
    created: int = 0
    skipped: int = 0
    created_titles: list[str] = field(default_factory=list)


class RiskIntelligenceAgent:
    def __init__(
        self,
        db: Session,
        sources: list[RiskSource],
        *,
        llm: LLMClient | None = None,
        seen_store: SeenStore | None = None,
    ) -> None:
        self.db = db
        self.sources = sources
        self.llm = llm or LLMClient()
        self.seen = seen_store or default_seen_store()
        self._zones = self._load_zones()

    # --- zone lookup ------------------------------------------------------
    def _load_zones(self) -> list[tuple[Zone, float, float]]:
        zones = []
        for z in self.db.execute(select(Zone)).scalars():
            c = geom_to_shape(z.geom).centroid
            zones.append((z, c.y, c.x))  # (zone, lat, lon)
        return zones

    def _match_zone(self, text: str) -> tuple[Zone | None, float | None, float | None]:
        low = text.lower()
        for z, lat, lon in self._zones:
            # Match on the first word of the zone name (e.g. "Koramangala").
            key = re.split(r"[ (]", z.name.strip())[0].lower()
            if key and key in low:
                return z, lat, lon
        return None, None, None

    # --- extraction -------------------------------------------------------
    def _extract(self, item: RawItem) -> list[ExtractedEvent]:
        if self.llm.dry_run:
            return self._heuristic_extract(item)
        return self._llm_extract(item)

    def _heuristic_extract(self, item: RawItem) -> list[ExtractedEvent]:
        text = f"{item.title} {item.summary}".lower()
        event_type = RiskEventType.ADVISORY
        for etype, words in _KEYWORDS:
            if any(w in text for w in words):
                event_type = etype
                break
        _, lat, lon = self._match_zone(f"{item.title} {item.summary}")
        return [
            ExtractedEvent(
                event_type=event_type,
                title=item.title[:256],
                description=item.summary or None,
                lat=lat,
                lon=lon,
                event_time=item.published,
                confidence=0.6,
            )
        ]

    def _llm_extract(self, item: RawItem) -> list[ExtractedEvent]:
        result = self.llm.extract_json(_EXTRACT_SYSTEM, item.content_for_llm())
        events: list[ExtractedEvent] = []
        for raw in result.get("events", []):
            try:
                etype = RiskEventType(str(raw.get("event_type", "other")).lower())
            except ValueError:
                etype = RiskEventType.OTHER
            events.append(
                ExtractedEvent(
                    event_type=etype,
                    title=str(raw.get("title") or item.title)[:256],
                    description=raw.get("description") or item.summary,
                    location_name=raw.get("location_name"),
                    lat=raw.get("lat"),
                    lon=raw.get("lon"),
                    event_time=_parse_time(raw.get("event_time")) or item.published,
                    confidence=_clamp(raw.get("confidence", 0.5)),
                )
            )
        return events

    # --- persistence ------------------------------------------------------
    def _already_in_db(self, source_url: str) -> bool:
        if not source_url:
            return False
        return self.db.execute(
            select(RiskEvent.id).where(RiskEvent.source_url == source_url).limit(1)
        ).first() is not None

    def _persist(self, ev: ExtractedEvent, item: RawItem) -> RiskEvent:
        # Resolve geo: explicit lat/lon, else zone match on text.
        zone = None
        lat, lon = ev.lat, ev.lon
        text = f"{ev.location_name or ''} {ev.title} {ev.description or ''}"
        z, zlat, zlon = self._match_zone(text)
        if z is not None:
            zone = z
            if lat is None or lon is None:
                lat, lon = zlat, zlon

        geom = point_to_geom(lat, lon) if (lat is not None and lon is not None) else None
        embedding = embed(f"{ev.title}. {ev.description or ''}")

        risk_event = RiskEvent(
            event_type=ev.event_type,
            title=ev.title,
            description=ev.description,
            geom=geom,
            zone_id=zone.id if zone else None,
            source=item.source_name[:256],
            source_url=item.url[:512] if item.url else None,
            event_time=ev.event_time or datetime.now(UTC),
            confidence=ev.confidence,
            embedding=embedding,
        )
        self.db.add(risk_event)
        return risk_event

    # --- orchestration ----------------------------------------------------
    def run_once(self) -> RunResult:
        result = RunResult()
        for source in self.sources:
            items = source.fetch()
            result.fetched += len(items)
            for item in items:
                key = item_hash(item.url, item.title)
                if self.seen.is_seen(key) or self._already_in_db(item.url):
                    result.skipped += 1
                    continue
                for ev in self._extract(item):
                    self._persist(ev, item)
                    result.created += 1
                    result.created_titles.append(ev.title)
                self.seen.mark_seen(key)
        self.db.commit()
        log.info(
            "RiskIntel run: fetched=%d created=%d skipped=%d",
            result.fetched, result.created, result.skipped,
        )
        return result


def _clamp(v, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return 0.5


def _parse_time(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None
