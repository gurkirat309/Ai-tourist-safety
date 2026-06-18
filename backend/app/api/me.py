"""Tourist self-service endpoints (`/me/*`).

The authenticated tourist acts on their own profile (tourist_id from the JWT).
Tourists see **safety information only** — never the underlying crime/risk-event
specifics, which are police-only.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_realtime_llm, require_role
from app.api.serializers import zone_out
from app.db.enums import UserRole
from app.db.models import LocationPing, Tourist, User
from app.db.spatial import geom_to_latlon, geom_to_shape, linestring_to_geom
from app.detection.adapters import containing_zone, load_zone_infos
from app.detection.geo import distance_point_to_route_m
from app.detection.geofence import check_geofence
from app.detection.inactivity import check_inactivity
from app.detection.route_deviation import check_route_deviation
from app.detection.thresholds import ROUTE_DEVIATION_WARN_M
from app.detection.types import DetectionSignal, Severity
from app.orchestrator.orchestrator import SafetyOrchestrator
from app.schemas.api import (
    OrchestrationResponse,
    PanicRequest,
    PingIngestRequest,
    RoutePointSafety,
    RouteSafety,
    SignalOut,
    TouristStatusResponse,
    TripRequest,
    TripResponse,
)
from app.schemas.geo import GeoPoint
from app.services.llm import LLMClient
from app.services.routing import compute_route

router = APIRouter(prefix="/me", tags=["tourist"])

_SEV_RANK = {Severity.INFO: 0, Severity.WARNING: 1, Severity.CRITICAL: 2}


def get_current_tourist(
    user: User = Depends(require_role(UserRole.TOURIST)),
    db: Session = Depends(get_db),
) -> Tourist:
    if user.tourist_id is None:
        raise HTTPException(status_code=400, detail="No tourist profile linked")
    tourist = db.get(Tourist, user.tourist_id)
    if tourist is None:
        raise HTTPException(status_code=404, detail="Tourist profile not found")
    return tourist


def _area_risk(lat: float, lon: float, when: datetime) -> float | None:
    try:
        from app.ml.risk_model import predict_risk

        return predict_risk(lat, lon, when)
    except Exception:  # noqa: BLE001
        return None


def _risk_label(score: float | None) -> str:
    if score is None:
        return "n/a"
    if score >= 0.5:
        return "high"
    if score >= 0.3:
        return "elevated"
    if score >= 0.15:
        return "moderate"
    return "low"


def _score_route(coords_lonlat: list[tuple[float, float]], when: datetime) -> RouteSafety:
    """Sample the route and score area-risk along it (safety-only)."""
    if not coords_lonlat:
        return RouteSafety(overall_score=None, max_score=None, label="n/a")
    step = max(1, len(coords_lonlat) // 15)
    sampled = coords_lonlat[::step]
    if coords_lonlat[-1] not in sampled:
        sampled.append(coords_lonlat[-1])

    points: list[RoutePointSafety] = []
    scores: list[float] = []
    for lon, lat in sampled:
        s = _area_risk(lat, lon, when)
        if s is not None:
            scores.append(s)
        points.append(RoutePointSafety(lat=lat, lon=lon, score=s))

    overall = sum(scores) / len(scores) if scores else None
    mx = max(scores) if scores else None
    return RouteSafety(
        overall_score=overall, max_score=mx, label=_risk_label(mx), points=points
    )


@router.post("/trip", response_model=TripResponse)
def plan_trip(
    payload: TripRequest,
    tourist: Tourist = Depends(get_current_tourist),
    db: Session = Depends(get_db),
) -> TripResponse:
    """Compute a route to the destination, save it, and score its safety."""
    route = compute_route(
        payload.start.lat, payload.start.lon,
        payload.destination.lat, payload.destination.lon,
    )
    # Persist as the tourist's planned route (used by route-deviation detection).
    tourist.planned_route = linestring_to_geom(route.coords)
    db.add(tourist)
    db.commit()

    safety = _score_route(route.coords, datetime.now(UTC))
    return TripResponse(
        route=[(lat, lon) for (lon, lat) in route.coords],
        distance_m=route.distance_m,
        duration_s=route.duration_s,
        source=route.source,
        safety=safety,
    )


@router.get("/status", response_model=TouristStatusResponse)
def my_status(
    tourist: Tourist = Depends(get_current_tourist),
    db: Session = Depends(get_db),
) -> TouristStatusResponse:
    """Current safety status for the tourist (safety-only, no crime details)."""
    now = datetime.now(UTC)
    has_route = tourist.planned_route is not None
    resp = TouristStatusResponse(
        tourist_id=tourist.id, display_name=tourist.display_name, has_route=has_route
    )

    last = db.execute(
        select(LocationPing)
        .where(LocationPing.tourist_id == tourist.id)
        .order_by(LocationPing.recorded_at.desc())
        .limit(1)
    ).scalars().first()
    if last is None:
        resp.status = "no_data"
        return resp

    lat, lon = geom_to_latlon(last.geom)
    resp.last_position = GeoPoint(lat=lat, lon=lon)
    resp.last_seen = last.recorded_at
    resp.area_risk_score = _area_risk(lat, lon, now)

    zone = containing_zone(db, lat, lon)
    if zone is not None:
        resp.zone = zone_out(zone)

    signals: list[DetectionSignal] = list(
        check_geofence(lat, lon, load_zone_infos(db))
    )
    if has_route:
        coords = list(geom_to_shape(tourist.planned_route).coords)
        dev = distance_point_to_route_m(lat, lon, coords)
        resp.deviation_m = round(dev, 1)
        resp.on_route = dev < ROUTE_DEVIATION_WARN_M
        sig = check_route_deviation(lat, lon, coords)
        if sig:
            signals.append(sig)

    gap_s = (now - last.recorded_at).total_seconds()
    inact = check_inactivity(gap_s, zone.risk_category if zone else None)
    if inact:
        signals.append(inact)

    top = max((s.severity for s in signals), key=lambda s: _SEV_RANK[s], default=None)
    resp.status = (
        "critical" if top is Severity.CRITICAL
        else "warning" if top is Severity.WARNING
        else "safe"
    )
    resp.warnings = [SignalOut(**s.as_dict()) for s in signals]
    return resp


@router.post("/pings", response_model=OrchestrationResponse)
def ingest_my_ping(
    payload: PingIngestRequest,
    tourist: Tourist = Depends(get_current_tourist),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_realtime_llm),
) -> OrchestrationResponse:
    if not tourist.consent_given:
        raise HTTPException(status_code=403, detail="Consent required")
    orch = SafetyOrchestrator(db, llm=llm)
    result = orch.process_location_update(
        tourist.id, payload.location.lat, payload.location.lon,
        payload.recorded_at or datetime.now(UTC),
        speed_mps=payload.speed_mps, accuracy_m=payload.accuracy_m, source="tourist-app",
    )
    return _to_orch_response(result)


@router.post("/panic", response_model=OrchestrationResponse)
def my_panic(
    payload: PanicRequest,
    tourist: Tourist = Depends(get_current_tourist),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_realtime_llm),
) -> OrchestrationResponse:
    orch = SafetyOrchestrator(db, llm=llm)
    result = orch.trigger_panic(
        tourist.id, payload.location.lat, payload.location.lon,
        payload.recorded_at or datetime.now(UTC),
    )
    return _to_orch_response(result)


def _to_orch_response(result) -> OrchestrationResponse:
    return OrchestrationResponse(
        ping_id=result.ping_id,
        zone_name=result.zone_name,
        area_risk_score=result.area_risk_score,
        signals=[s.as_dict() for s in result.signals],
        incident_id=result.incident_id,
        incident_created=result.incident_created,
        alert_id=result.alert_id,
        escalation=result.escalation,
        trace=result.trace,
    )
