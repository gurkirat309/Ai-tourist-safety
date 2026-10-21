"""Tourist self-service endpoints (`/me/*`).

The authenticated tourist acts on their own profile (tourist_id from the JWT).
Tourists see **safety information only** — never the underlying crime/risk-event
specifics, which are police-only.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_realtime_llm, require_role
from app.api.serializers import zone_out
from app.db.enums import RiskEventType, UserRole
from app.db.models import LocationPing, RiskEvent, Tourist, User, Zone
from app.db.spatial import geom_to_latlon, geom_to_shape, linestring_to_geom
from app.detection.adapters import (
    containing_zone,
    load_zone_infos,
    trajectory_anomaly_signal,
    zone_crowd_signal,
)
from app.detection.geo import distance_point_to_route_m
from app.detection.geofence import check_geofence
from app.detection.inactivity import check_inactivity
from app.detection.route_deviation import check_route_deviation
from app.detection.thresholds import ROUTE_DEVIATION_WARN_M
from app.detection.types import DetectionSignal, Severity
from app.orchestrator.orchestrator import SafetyOrchestrator
from app.schemas.api import (
    AdvisoriesResponse,
    AdvisoryOut,
    OrchestrationResponse,
    PanicRequest,
    PingIngestRequest,
    RouteOption,
    RoutePointSafety,
    RouteSafety,
    SignalOut,
    TouristStatusResponse,
    TripRequest,
    TripResponse,
)
from app.schemas.geo import GeoPoint
from app.services.llm import LLMClient
from app.services.routing import compute_routes

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


def _trade_off_note(selected: RouteOption, fastest: RouteOption) -> str | None:
    """Plain-language cost of taking the safer route instead of the fastest."""
    if selected.index == fastest.index:
        return None

    extra_min = round((selected.duration_s - fastest.duration_s) / 60)
    sel, fast = selected.safety.max_score, fastest.safety.max_score
    if sel is None or fast is None or fast <= 0:
        return f"{extra_min} min slower" if extra_min > 0 else None

    safer_pct = round((1 - sel / fast) * 100)
    if safer_pct <= 0:
        return None
    if extra_min <= 0:
        return f"{safer_pct}% lower peak risk, and no slower"
    return f"{extra_min} min slower, {safer_pct}% lower peak risk"


@router.post("/trip", response_model=TripResponse)
def plan_trip(
    payload: TripRequest,
    tourist: Tourist = Depends(get_current_tourist),
    db: Session = Depends(get_db),
) -> TripResponse:
    """Score several candidate routes and adopt the preferred one.

    Routing engines optimise for time. This endpoint scores every alternative
    against the area-risk model so the tourist can trade a few minutes for a
    materially safer path — and see exactly what that trade costs.

    The adopted route is persisted as `planned_route`, which is what the
    deviation detector then measures against.
    """
    now = datetime.now(UTC)
    routes = compute_routes(
        payload.start.lat, payload.start.lon,
        payload.destination.lat, payload.destination.lon,
    )

    options: list[RouteOption] = [
        RouteOption(
            index=i,
            route=[(lat, lon) for (lon, lat) in r.coords],
            distance_m=r.distance_m,
            duration_s=r.duration_s,
            source=r.source,
            safety=_score_route(r.coords, now),
        )
        for i, r in enumerate(routes)
    ]

    # Fastest by duration. Safest by the worst point on the route: a route is
    # only as safe as its most dangerous stretch, so peak risk decides, with
    # the average as a tie-break.
    fastest = min(options, key=lambda o: o.duration_s)
    safest = min(
        options,
        key=lambda o: (
            o.safety.max_score if o.safety.max_score is not None else 1.0,
            o.safety.overall_score if o.safety.overall_score is not None else 1.0,
            o.duration_s,
        ),
    )
    fastest.is_fastest = True
    safest.is_safest = True

    selected = fastest if payload.prefer == "fastest" else safest
    selected.is_selected = True

    chosen_route = routes[selected.index]
    tourist.planned_route = linestring_to_geom(chosen_route.coords)
    db.add(tourist)
    db.commit()

    return TripResponse(
        route=selected.route,
        distance_m=selected.distance_m,
        duration_s=selected.duration_s,
        source=selected.source,
        safety=selected.safety,
        alternatives=options,
        chosen=payload.prefer,
        trade_off=_trade_off_note(selected, fastest),
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

    # Crowd density for the zone they're standing in. Congestion is a safety
    # issue in its own right (crush risk at festivals and transit hubs), and
    # until now the detector's output never reached the tourist.
    crowd = zone_crowd_signal(db, zone, now=now)
    if crowd:
        signals.append(crowd)

    # Advisory ML. No-op when torch or the model artifact is absent, so the
    # deterministic detectors above remain the safety floor.
    anomaly = trajectory_anomaly_signal(db, tourist.id)
    if anomaly:
        signals.append(anomaly)

    top = max((s.severity for s in signals), key=lambda s: _SEV_RANK[s], default=None)
    resp.status = (
        "critical" if top is Severity.CRITICAL
        else "warning" if top is Severity.WARNING
        else "safe"
    )
    resp.warnings = [SignalOut(**s.as_dict()) for s in signals]
    return resp


# Ping sources a tourist client may claim. Anything else collapses to the
# generic app source, so a client cannot invent labels — but a simulated
# ping MUST stay distinguishable from a real one, or an officer could read
# demo movement as a tourist genuinely in distress.
_ALLOWED_PING_SOURCES = {"tourist-app", "mobile_gps", "demo"}


def _ping_source(claimed: str | None) -> str:
    return claimed if claimed in _ALLOWED_PING_SOURCES else "tourist-app"


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
        speed_mps=payload.speed_mps, accuracy_m=payload.accuracy_m,
        source=_ping_source(payload.source),
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


# Tourist-facing phrasing per risk-event type. Deliberately generic: the
# tourist learns *what kind* of thing happened nearby and can act on it,
# without ever seeing the incident's title, description or source article.
_ADVICE_BY_TYPE: dict[RiskEventType, str] = {
    RiskEventType.CRIME: "Incidents reported nearby — stay on busy, well-lit streets.",
    RiskEventType.CIVIL_UNREST: (
        "Gathering or disruption reported nearby — consider avoiding the area."
    ),
    RiskEventType.NATURAL_HAZARD: (
        "Weather or hazard warning for this area — check conditions before travelling."
    ),
    RiskEventType.ACCIDENT: "Accident reported nearby — expect disruption and take care crossing.",
    RiskEventType.HEALTH: "Health advisory for this area — follow local guidance.",
    RiskEventType.ADVISORY: "An official advisory is active for this area.",
    RiskEventType.OTHER: "Something was reported near this area — stay aware.",
}

# ~100 m. Coarse enough that an advisory cannot pinpoint a person or address,
# precise enough to be worth drawing on a map.
_ADVISORY_COORD_DP = 3


@router.get("/advisories", response_model=AdvisoriesResponse)
def my_advisories(
    tourist: Tourist = Depends(get_current_tourist),
    db: Session = Depends(get_db),
    radius_m: int = Query(default=3000, ge=100, le=20000),
    since_hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=10, ge=1, le=50),
) -> AdvisoriesResponse:
    """Recent risk events near the tourist, sanitized for their eyes.

    The Risk Intelligence agent already collects these from news and official
    feeds, but they have been police-only. A tourist benefits from knowing
    *that* civil unrest was reported near their location — they do not need,
    and must not get, the underlying crime specifics.
    """
    empty = AdvisoriesResponse(advisories=[], radius_m=radius_m, since_hours=since_hours)

    last = db.execute(
        select(LocationPing)
        .where(LocationPing.tourist_id == tourist.id)
        .order_by(LocationPing.recorded_at.desc())
        .limit(1)
    ).scalars().first()
    if last is None:
        return empty  # no position yet — nothing to be near

    cutoff = datetime.now(UTC) - timedelta(hours=since_hours)
    pt = func.ST_SetSRID(func.ST_MakePoint(*reversed(geom_to_latlon(last.geom))), 4326)
    geog, pt_geog = func.geography(RiskEvent.geom), func.geography(pt)

    rows = db.execute(
        select(RiskEvent, Zone.name)
        .outerjoin(Zone, Zone.id == RiskEvent.zone_id)
        .where(RiskEvent.geom.isnot(None))
        .where(RiskEvent.event_time >= cutoff)
        .where(func.ST_DWithin(geog, pt_geog, radius_m))
        .order_by(RiskEvent.event_time.desc())
        .limit(limit)
    ).all()

    advisories = [
        AdvisoryOut(
            event_type=ev.event_type.value,
            advice=_ADVICE_BY_TYPE.get(ev.event_type, _ADVICE_BY_TYPE[RiskEventType.OTHER]),
            area=zone_name,
            location=_coarse_point(ev.geom),
            event_time=ev.event_time,
            confidence=ev.confidence,
        )
        for ev, zone_name in rows
    ]
    return AdvisoriesResponse(
        advisories=advisories, radius_m=radius_m, since_hours=since_hours
    )


def _coarse_point(geom) -> GeoPoint | None:
    """Blur a risk-event location so it indicates an area, not an address."""
    if geom is None:
        return None
    lat, lon = geom_to_latlon(geom)
    return GeoPoint(
        lat=round(lat, _ADVISORY_COORD_DP), lon=round(lon, _ADVISORY_COORD_DP)
    )
