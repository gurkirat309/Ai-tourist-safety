"""Incident Triage agent (M5).

Given a flagged incident: gather context (zone, nearby risk events, recent
pings, area-risk score), then produce a concise human-readable summary and a
recommended escalation level. **Advisory only** — output is decision support
for humans; the agent never dispatches anyone.

Escalation is computed by a deterministic heuristic that also runs as the
dry-run path, so the agent is fully testable without an LLM. In live mode the
LLM writes the prose summary/rationale; the heuristic escalation is kept as a
safety floor so an LLM cannot *downgrade* a serious incident.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.agents.triage_types import NearbyEvent, TriageContext, TriageResult
from app.core.logging import get_logger
from app.db.enums import AlertSeverity, IncidentType
from app.db.models import Alert, Incident, LocationPing, RiskEvent, Zone
from app.db.spatial import geom_to_latlon, point_to_geom
from app.services.llm import LLMClient

log = get_logger(__name__)

# Ordered severities (low -> high) for "take the max" combination.
_ORDER = [
    AlertSeverity.INFO,
    AlertSeverity.LOW,
    AlertSeverity.MEDIUM,
    AlertSeverity.HIGH,
    AlertSeverity.CRITICAL,
]
_RANK = {s: i for i, s in enumerate(_ORDER)}

NEARBY_RADIUS_M = 2000.0
NEARBY_WINDOW_H = 48
RECENT_PING_WINDOW_MIN = 60

_TRIAGE_SYSTEM = (
    "You are an incident-triage assistant for a tourist-safety control room in "
    "Bengaluru. Given structured incident context, return STRICT JSON: "
    '{"summary": str (2-3 sentences, factual, no speculation), '
    '"recommended_actions": [str, ...]}. Be concise and operational. Do NOT '
    "invent facts not present in the context. You provide decision support for "
    "human operators; you never dispatch responders."
)


def _max_sev(a: AlertSeverity, b: AlertSeverity) -> AlertSeverity:
    return a if _RANK[a] >= _RANK[b] else b


def heuristic_escalation(ctx: TriageContext) -> tuple[AlertSeverity, str]:
    """Deterministic escalation level + rationale from context."""
    level = AlertSeverity.INFO
    reasons: list[str] = []

    if ctx.incident_type is IncidentType.PANIC:
        level = _max_sev(level, AlertSeverity.CRITICAL)
        reasons.append("panic button pressed")

    if ctx.signal_severity == "critical":
        level = _max_sev(level, AlertSeverity.HIGH)
        reasons.append("a critical detection signal")
    elif ctx.signal_severity == "warning":
        level = _max_sev(level, AlertSeverity.MEDIUM)
        reasons.append("a warning detection signal")

    if ctx.zone_restricted:
        level = _max_sev(level, AlertSeverity.HIGH)
        reasons.append(f"entry into restricted zone '{ctx.zone_name}'")

    if ctx.area_risk_score is not None:
        if ctx.area_risk_score >= 0.5:
            level = _max_sev(level, AlertSeverity.HIGH)
            reasons.append(f"high area-risk score ({ctx.area_risk_score:.2f})")
        elif ctx.area_risk_score >= 0.3:
            level = _max_sev(level, AlertSeverity.MEDIUM)
            reasons.append(f"elevated area-risk score ({ctx.area_risk_score:.2f})")

    if ctx.nearby_events:
        strong = [e for e in ctx.nearby_events if e.confidence >= 0.6]
        if strong:
            level = _max_sev(level, AlertSeverity.MEDIUM)
            reasons.append(f"{len(strong)} nearby risk event(s)")

    if level is AlertSeverity.INFO:
        level = AlertSeverity.LOW
        reasons.append("baseline review")

    rationale = "Escalation driven by " + "; ".join(reasons) + "."
    return level, rationale


def _default_actions(ctx: TriageContext, level: AlertSeverity) -> list[str]:
    actions: list[str] = []
    if level in (AlertSeverity.HIGH, AlertSeverity.CRITICAL):
        actions.append("Attempt to contact the tourist immediately")
        actions.append("Notify the nearest patrol/control room for verification")
    if ctx.zone_restricted:
        actions.append("Advise/guide the tourist out of the restricted area")
    if ctx.minutes_since_last_ping and ctx.minutes_since_last_ping >= 15:
        actions.append("Investigate possible signal loss or device issue")
    if not actions:
        actions.append("Monitor; no immediate action required")
    return actions


def _heuristic_summary(ctx: TriageContext) -> str:
    who = ctx.tourist_name or "A tourist"
    where = f" in {ctx.zone_name}" if ctx.zone_name else ""
    bits = [f"{who} triggered a {ctx.incident_type.value.replace('_', ' ')} incident{where}."]
    if ctx.signal_reasons:
        bits.append("Signals: " + "; ".join(ctx.signal_reasons) + ".")
    if ctx.area_risk_score is not None:
        bits.append(f"Area-risk score {ctx.area_risk_score:.2f}.")
    if ctx.nearby_events:
        bits.append(f"{len(ctx.nearby_events)} nearby risk event(s) in the last "
                    f"{NEARBY_WINDOW_H}h.")
    return " ".join(bits)


class IncidentTriageAgent:
    def __init__(self, db: Session, *, llm: LLMClient | None = None) -> None:
        self.db = db
        self.llm = llm or LLMClient()

    # --- context gathering (deterministic) --------------------------------
    def gather_context(self, incident: Incident) -> TriageContext:
        lat = lon = None
        if incident.geom is not None:
            lat, lon = geom_to_latlon(incident.geom)

        tourist_name = incident.tourist.display_name if incident.tourist else None

        # Zone: prefer the incident's zone, else spatial containment.
        zone = self.db.get(Zone, incident.zone_id) if incident.zone_id else None
        if zone is None and lat is not None:
            pt = point_to_geom(lat, lon)
            zone = self.db.execute(
                select(Zone).where(func.ST_Contains(Zone.geom, pt)).limit(1)
            ).scalars().first()

        # Detection signals from the incident details.
        signal_severity = None
        signal_reasons: list[str] = []
        details = incident.details or {}
        signals = details.get("signals") if isinstance(details, dict) else None
        if isinstance(signals, list):
            sev_rank = {"info": 0, "warning": 1, "critical": 2}
            best = -1
            for s in signals:
                sev = s.get("severity")
                if s.get("reason"):
                    signal_reasons.append(s["reason"])
                if sev in sev_rank and sev_rank[sev] > best:
                    best = sev_rank[sev]
                    signal_severity = sev

        # Nearby recent risk events (PostGIS distance on geography).
        nearby: list[NearbyEvent] = []
        if lat is not None:
            pt = point_to_geom(lat, lon)
            cutoff = datetime.now(UTC) - timedelta(hours=NEARBY_WINDOW_H)
            geom_geog = cast(RiskEvent.geom, Geography)
            pt_geog = cast(pt, Geography)
            rows = self.db.execute(
                select(
                    RiskEvent.title,
                    RiskEvent.event_type,
                    RiskEvent.confidence,
                    func.ST_Distance(geom_geog, pt_geog).label("dist"),
                )
                .where(RiskEvent.geom.is_not(None))
                .where(func.ST_DWithin(geom_geog, pt_geog, NEARBY_RADIUS_M))
                .where(RiskEvent.event_time >= cutoff)
                .order_by("dist")
                .limit(5)
            ).all()
            for title, etype, conf, dist in rows:
                nearby.append(
                    NearbyEvent(
                        title=title,
                        event_type=etype.value if hasattr(etype, "value") else str(etype),
                        confidence=float(conf),
                        distance_m=float(dist) if dist is not None else None,
                    )
                )

        # Recent pings + minutes since last ping.
        recent_count = 0
        minutes_since = None
        if incident.tourist_id:
            window_start = datetime.fromtimestamp(
                datetime.now(UTC).timestamp() - RECENT_PING_WINDOW_MIN * 60, tz=UTC
            )
            recent_count = self.db.execute(
                select(func.count(LocationPing.id)).where(
                    LocationPing.tourist_id == incident.tourist_id,
                    LocationPing.recorded_at >= window_start,
                )
            ).scalar_one()
            last_ts = self.db.execute(
                select(func.max(LocationPing.recorded_at)).where(
                    LocationPing.tourist_id == incident.tourist_id
                )
            ).scalar_one()
            if last_ts is not None:
                minutes_since = (datetime.now(UTC) - last_ts).total_seconds() / 60.0

        # M3 area-risk score (optional).
        area_risk = None
        if lat is not None:
            try:
                from app.ml.risk_model import predict_risk

                area_risk = predict_risk(lat, lon, incident.detected_at)
            except Exception as exc:  # noqa: BLE001
                log.info("Area-risk score unavailable: %s", exc)

        return TriageContext(
            incident_type=incident.incident_type,
            detected_at=incident.detected_at,
            lat=lat,
            lon=lon,
            tourist_name=tourist_name,
            zone_name=zone.name if zone else None,
            zone_risk=zone.risk_category.value if zone else None,
            zone_restricted=zone.restricted if zone else False,
            area_risk_score=area_risk,
            signal_severity=signal_severity,
            signal_reasons=signal_reasons,
            nearby_events=nearby,
            recent_ping_count=int(recent_count),
            minutes_since_last_ping=minutes_since,
        )

    # --- summarization ----------------------------------------------------
    def summarize(self, ctx: TriageContext) -> TriageResult:
        # Heuristic escalation is the safety floor (an LLM cannot downgrade it).
        level, rationale = heuristic_escalation(ctx)

        if self.llm.dry_run:
            return TriageResult(
                summary=_heuristic_summary(ctx),
                escalation=level,
                rationale=rationale,
                recommended_actions=_default_actions(ctx, level),
                confidence=0.7,
                source="agent.triage:dry-run",
            )

        try:
            out = self.llm.extract_json(
                _TRIAGE_SYSTEM, str(ctx.to_prompt_dict()), temperature=0.2
            )
            summary = out.get("summary") or _heuristic_summary(ctx)
            actions = out.get("recommended_actions") or _default_actions(ctx, level)
        except Exception as exc:  # noqa: BLE001
            log.warning("Triage LLM failed (%s); using heuristic summary", exc)
            summary, actions = _heuristic_summary(ctx), _default_actions(ctx, level)

        return TriageResult(
            summary=summary,
            escalation=level,
            rationale=rationale,
            recommended_actions=list(actions),
            confidence=0.75,
            source="agent.triage",
        )

    def triage(self, incident: Incident) -> TriageResult:
        return self.summarize(self.gather_context(incident))


def to_alert(result: TriageResult, incident: Incident) -> Alert:
    """Build an advisory Alert row from a triage result (not committed)."""
    return Alert(
        incident_id=incident.id,
        severity=result.escalation,
        summary=result.summary,
        recommended_action="\n".join(result.recommended_actions),
        created_by=result.source,
    )
