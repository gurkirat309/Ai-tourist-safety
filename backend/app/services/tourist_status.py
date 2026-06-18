"""Shared helper to compute a tourist's live operational status.

Used by the police dashboard (per-tourist summary). Status is derived from
open incidents + ping freshness:
  panic    — an open PANIC incident
  alert    — any other open incident
  inactive — last ping older than the inactivity window
  safe     — recent ping, no open incidents
  no_data  — no pings at all
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.enums import IncidentStatus, IncidentType
from app.db.models import Incident, LocationPing, Tourist
from app.db.spatial import geom_to_latlon
from app.detection.adapters import containing_zone

INACTIVE_AFTER_MIN = 20


@dataclass
class TouristLive:
    last_lat: float | None
    last_lon: float | None
    last_seen: datetime | None
    zone_name: str | None
    area_risk_score: float | None
    status: str
    open_incidents: int


def _area_risk(lat: float, lon: float, when: datetime) -> float | None:
    try:
        from app.ml.risk_model import predict_risk

        return predict_risk(lat, lon, when)
    except Exception:  # noqa: BLE001
        return None


def tourist_live(db: Session, tourist: Tourist, *, now: datetime | None = None) -> TouristLive:
    now = now or datetime.now(UTC)
    last = db.execute(
        select(LocationPing)
        .where(LocationPing.tourist_id == tourist.id)
        .order_by(LocationPing.recorded_at.desc())
        .limit(1)
    ).scalars().first()

    open_incidents = db.execute(
        select(func.count(Incident.id)).where(
            Incident.tourist_id == tourist.id,
            Incident.status == IncidentStatus.OPEN,
        )
    ).scalar_one()
    has_panic = db.execute(
        select(Incident.id).where(
            Incident.tourist_id == tourist.id,
            Incident.status == IncidentStatus.OPEN,
            Incident.incident_type == IncidentType.PANIC,
        ).limit(1)
    ).first() is not None

    if last is None:
        return TouristLive(None, None, None, None, None, "no_data", int(open_incidents))

    lat, lon = geom_to_latlon(last.geom)
    zone = containing_zone(db, lat, lon)
    gap_min = (now - last.recorded_at).total_seconds() / 60.0

    if has_panic:
        status = "panic"
    elif open_incidents > 0:
        status = "alert"
    elif gap_min > INACTIVE_AFTER_MIN:
        status = "inactive"
    else:
        status = "safe"

    return TouristLive(
        last_lat=lat,
        last_lon=lon,
        last_seen=last.recorded_at,
        zone_name=zone.name if zone else None,
        area_risk_score=_area_risk(lat, lon, now),
        status=status,
        open_incidents=int(open_incidents),
    )
