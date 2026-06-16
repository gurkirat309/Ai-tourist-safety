"""Geofencing: point-in-polygon checks against zones.

Flags entry into restricted areas (critical) and high-risk zones (warning).
Pure and deterministic — no DB, no LLM. The orchestrator (M6) supplies zone
info; a DB adapter is provided in `app.detection.adapters`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from shapely.geometry import Point, Polygon

from app.db.enums import IncidentType, RiskCategory
from app.detection.types import DetectionSignal, Severity

SOURCE = "detection.geofence"


@dataclass
class ZoneInfo:
    """Minimal zone description for geofencing (decoupled from ORM)."""

    name: str
    polygon: list[tuple[float, float]]  # (lon, lat) ring
    risk_category: RiskCategory = RiskCategory.LOW
    restricted: bool = False
    zone_id: uuid.UUID | None = None


def zones_containing(lat: float, lon: float, zones: list[ZoneInfo]) -> list[ZoneInfo]:
    """Return zones whose polygon contains the point."""
    pt = Point(lon, lat)
    return [z for z in zones if Polygon(z.polygon).contains(pt)]


def check_geofence(lat: float, lon: float, zones: list[ZoneInfo]) -> list[DetectionSignal]:
    """Emit signals for restricted / high-risk zone entry at a point."""
    signals: list[DetectionSignal] = []
    for z in zones_containing(lat, lon, zones):
        base = {"zone": z.name, "zone_id": str(z.zone_id) if z.zone_id else None}
        if z.restricted:
            signals.append(
                DetectionSignal(
                    type=IncidentType.GEOFENCE_BREACH,
                    severity=Severity.CRITICAL,
                    reason=f"Entered restricted zone '{z.name}'",
                    confidence=1.0,
                    details={**base, "restricted": True},
                    source=SOURCE,
                )
            )
        elif z.risk_category == RiskCategory.HIGH:
            signals.append(
                DetectionSignal(
                    type=IncidentType.GEOFENCE_BREACH,
                    severity=Severity.WARNING,
                    reason=f"Entered high-risk zone '{z.name}'",
                    confidence=0.8,
                    details={**base, "risk_category": z.risk_category.value},
                    source=SOURCE,
                )
            )
    return signals
