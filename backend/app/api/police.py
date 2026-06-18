"""Police / authority endpoints (`/police/*`) — role-restricted.

Police see operational detail tourists never do: every tourist's live position
and status, per-tourist activity, and the full crime/risk-event feed.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.api.serializers import incident_out
from app.db.enums import UserRole
from app.db.models import Incident, LocationPing, RiskEvent, Tourist
from app.db.spatial import geom_to_latlon
from app.schemas.api import (
    ActiveTouristOut,
    RiskEventOut,
    TimelinePing,
    TouristDetailOut,
)
from app.schemas.geo import GeoPoint
from app.services.tourist_status import tourist_live

router = APIRouter(
    prefix="/police",
    tags=["police"],
    dependencies=[Depends(require_role(UserRole.POLICE))],
)


@router.get("/tourists", response_model=list[ActiveTouristOut])
def list_tourists(db: Session = Depends(get_db)) -> list[ActiveTouristOut]:
    """All tourists with their live position + status."""
    out: list[ActiveTouristOut] = []
    for t in db.execute(select(Tourist).where(Tourist.is_active)).scalars():
        live = tourist_live(db, t)
        out.append(ActiveTouristOut(
            id=t.id,
            display_name=t.display_name,
            nationality=t.nationality,
            last_position=GeoPoint(lat=live.last_lat, lon=live.last_lon)
            if live.last_lat is not None else None,
            last_seen=live.last_seen,
            zone_name=live.zone_name,
            area_risk_score=live.area_risk_score,
            status=live.status,
            open_incidents=live.open_incidents,
        ))
    # Most urgent first.
    order = {"panic": 0, "alert": 1, "inactive": 2, "safe": 3, "no_data": 4}
    out.sort(key=lambda a: order.get(a.status, 9))
    return out


@router.get("/tourists/{tourist_id}", response_model=TouristDetailOut)
def tourist_detail(tourist_id: uuid.UUID, db: Session = Depends(get_db)) -> TouristDetailOut:
    t = db.get(Tourist, tourist_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Tourist not found")
    live = tourist_live(db, t)

    pings = db.execute(
        select(LocationPing)
        .where(LocationPing.tourist_id == tourist_id)
        .order_by(LocationPing.recorded_at.desc())
        .limit(30)
    ).scalars().all()
    timeline = []
    for p in pings:
        lat, lon = geom_to_latlon(p.geom)
        timeline.append(TimelinePing(lat=lat, lon=lon, recorded_at=p.recorded_at, source=p.source))

    incidents = db.execute(
        select(Incident)
        .where(Incident.tourist_id == tourist_id)
        .order_by(Incident.detected_at.desc())
        .limit(20)
    ).scalars().all()

    return TouristDetailOut(
        id=t.id,
        display_name=t.display_name,
        nationality=t.nationality,
        emergency_contact=t.emergency_contact,
        consent_given=t.consent_given,
        status=live.status,
        last_position=GeoPoint(lat=live.last_lat, lon=live.last_lon)
        if live.last_lat is not None else None,
        zone_name=live.zone_name,
        area_risk_score=live.area_risk_score,
        recent_pings=timeline,
        incidents=[incident_out(i) for i in incidents],
    )


@router.get("/risk-events", response_model=list[RiskEventOut])
def risk_events(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[RiskEventOut]:
    """Full crime / risk-event feed (police-only)."""
    rows = db.execute(
        select(RiskEvent).order_by(RiskEvent.event_time.desc()).limit(limit)
    ).scalars().all()
    out = []
    for r in rows:
        loc = None
        if r.geom is not None:
            lat, lon = geom_to_latlon(r.geom)
            loc = GeoPoint(lat=lat, lon=lon)
        out.append(RiskEventOut(
            id=r.id,
            event_type=r.event_type.value,
            title=r.title,
            description=r.description,
            location=loc,
            zone_id=r.zone_id,
            source=r.source,
            source_url=r.source_url,
            event_time=r.event_time,
            confidence=r.confidence,
        ))
    return out
