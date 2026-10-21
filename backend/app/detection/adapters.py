"""DB adapters bridging ORM rows to the pure detection functions.

The detectors themselves take plain inputs (no DB). These helpers load the
inputs (zones, planned route, previous ping, in-zone crowd counts) so the
orchestrator stays readable.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.enums import IncidentType
from app.db.models import LocationPing, Zone
from app.db.spatial import geom_to_latlon, geom_to_shape, point_to_geom
from app.detection.crowd import check_zone_crowd
from app.detection.geofence import ZoneInfo
from app.detection.thresholds import CROWD_WINDOW_S
from app.detection.types import DetectionSignal, Severity


def load_zone_infos(db: Session) -> list[ZoneInfo]:
    """All zones as geofencing inputs (decoupled from ORM)."""
    infos: list[ZoneInfo] = []
    for z in db.execute(select(Zone)).scalars():
        ring = list(geom_to_shape(z.geom).exterior.coords)  # (lon, lat)
        infos.append(ZoneInfo(z.name, ring, z.risk_category, z.restricted, z.id))
    return infos


def tourist_route(planned_route_geom) -> list[tuple[float, float]] | None:
    """Planned route WKB -> list of (lon, lat), or None."""
    if planned_route_geom is None:
        return None
    return list(geom_to_shape(planned_route_geom).coords)


def previous_ping(
    db: Session, tourist_id: uuid.UUID, before: datetime
) -> LocationPing | None:
    """Most recent ping for a tourist strictly before `before`."""
    return db.execute(
        select(LocationPing)
        .where(LocationPing.tourist_id == tourist_id, LocationPing.recorded_at < before)
        .order_by(LocationPing.recorded_at.desc())
        .limit(1)
    ).scalars().first()


def count_recent_pings_in_zone(
    db: Session, zone: Zone, window_s: int, *, now: datetime | None = None
) -> int:
    """Count pings inside a zone polygon within the trailing window."""
    now = now or datetime.now(tz=zone.created_at.tzinfo if zone.created_at else None)
    cutoff = now - timedelta(seconds=window_s)
    return db.execute(
        select(func.count(LocationPing.id))
        .where(LocationPing.recorded_at >= cutoff)
        .where(func.ST_Contains(zone.geom, LocationPing.geom))
    ).scalar_one()


def containing_zone(db: Session, lat: float, lon: float) -> Zone | None:
    """First zone whose polygon contains the point."""
    pt = point_to_geom(lat, lon)
    return db.execute(
        select(Zone).where(func.ST_Contains(Zone.geom, pt)).limit(1)
    ).scalars().first()


def zone_crowd_signal(
    db: Session, zone: Zone | None, *, now: datetime | None = None
) -> DetectionSignal | None:
    """Crowd-density signal for the zone a tourist is currently in.

    Only zones with a modelled `capacity` can be congested, so this is a
    no-op elsewhere. Shared by the orchestrator (on each ping) and the
    tourist status endpoint, so both report congestion identically.
    """
    if zone is None or not zone.capacity:
        return None
    count = count_recent_pings_in_zone(db, zone, CROWD_WINDOW_S, now=now)
    return check_zone_crowd(count, zone.capacity, zone_name=zone.name)


def trajectory_anomaly_signal(
    db: Session, tourist_id: uuid.UUID
) -> DetectionSignal | None:
    """Advisory LSTM anomaly signal over the tourist's recent path.

    Entirely optional: returns None when torch or the model artifact is
    absent, so the deterministic detectors remain the safety floor.
    """
    try:
        from app.ml.lstm.features import WINDOW
        from app.ml.lstm.infer import score_trajectory
    except Exception:  # noqa: BLE001
        return None

    pings = db.execute(
        select(LocationPing)
        .where(LocationPing.tourist_id == tourist_id)
        .order_by(LocationPing.recorded_at.desc())
        .limit(WINDOW + 1)
    ).scalars().all()
    if len(pings) < 3:
        return None

    points = [
        (*geom_to_latlon(p.geom), p.recorded_at.timestamp()) for p in reversed(pings)
    ]
    prob = score_trajectory(points)
    if prob is None:
        return None

    if prob < get_settings().lstm_anomaly_threshold:
        return None

    return DetectionSignal(
        type=IncidentType.ROUTE_DEVIATION,
        severity=Severity.WARNING,
        reason=f"Unusual movement pattern for this area (confidence {prob:.0%})",
        confidence=prob,
        details={"anomaly_prob": round(prob, 3)},
        source="ml.trajectory_lstm",
    )
