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

from app.db.models import LocationPing, Zone
from app.db.spatial import geom_to_shape, point_to_geom
from app.detection.geofence import ZoneInfo


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
