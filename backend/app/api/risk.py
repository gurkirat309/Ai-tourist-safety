"""Risk query endpoints (M7): area-risk score and zone risk."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from shapely.geometry import mapping
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.serializers import zone_out
from app.db.models import Zone
from app.db.spatial import geom_to_shape
from app.detection.adapters import containing_zone
from app.schemas.api import (
    AreaRiskResponse,
    ContainingZoneResponse,
    RiskForecastPoint,
    RiskForecastResponse,
    ZoneRiskOut,
)
from app.schemas.geo import GeoPoint

router = APIRouter(prefix="/risk", tags=["risk"])


def _area_risk(lat: float, lon: float, when: datetime) -> float | None:
    try:
        from app.ml.risk_model import predict_risk

        return predict_risk(lat, lon, when)
    except Exception:  # noqa: BLE001
        return None


@router.get("/area", response_model=AreaRiskResponse)
def area_risk(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    when: datetime | None = None,
) -> AreaRiskResponse:
    """M3 area-risk score for a (location, time)."""
    when = when or datetime.now(UTC)
    score = _area_risk(lat, lon, when)
    return AreaRiskResponse(
        location=GeoPoint(lat=lat, lon=lon),
        when=when,
        risk_score=score,
        model_available=score is not None,
    )


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


@router.get("/forecast", response_model=RiskForecastResponse)
def risk_forecast(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    hours: int = Query(default=24, ge=1, le=72),
    start: datetime | None = None,
) -> RiskForecastResponse:
    """Hour-by-hour area risk for a location.

    The area-risk model already uses time-of-day and day-of-week as features,
    so asking it about future hours is the same inference, not a new model.
    This answers the question a tourist actually has — "this place is fine
    now, but what about when I come back tonight?".
    """
    start = start or datetime.now(UTC)
    # Snap to the top of the hour so the series is stable across calls within
    # the same hour (and therefore cacheable client-side).
    start = start.replace(minute=0, second=0, microsecond=0)

    points: list[RiskForecastPoint] = []
    for h in range(hours):
        when = start + timedelta(hours=h)
        score = _area_risk(lat, lon, when)
        points.append(
            RiskForecastPoint(when=when, risk_score=score, label=_risk_label(score))
        )

    scored = [p for p in points if p.risk_score is not None]
    return RiskForecastResponse(
        location=GeoPoint(lat=lat, lon=lon),
        points=points,
        model_available=bool(scored),
        safest=min(scored, key=lambda p: p.risk_score) if scored else None,
        riskiest=max(scored, key=lambda p: p.risk_score) if scored else None,
    )


@router.get("/zones", response_model=list[ZoneRiskOut])
def list_zones(db: Session = Depends(get_db)) -> list[ZoneRiskOut]:
    zones = db.execute(select(Zone).order_by(Zone.name)).scalars().all()
    return [zone_out(z) for z in zones]


@router.get("/zones.geojson")
def zones_geojson(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Zones as a GeoJSON FeatureCollection (polygons + risk props) for maps."""
    features = []
    for z in db.execute(select(Zone)).scalars():
        features.append({
            "type": "Feature",
            "geometry": mapping(geom_to_shape(z.geom)),
            "properties": {
                "id": str(z.id),
                "name": z.name,
                "risk_category": z.risk_category.value,
                "restricted": z.restricted,
                "capacity": z.capacity,
            },
        })
    return {"type": "FeatureCollection", "features": features}


@router.get("/zone", response_model=ContainingZoneResponse)
def zone_at_point(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    db: Session = Depends(get_db),
) -> ContainingZoneResponse:
    """Containing zone (if any) + area-risk score at a point."""
    zone = containing_zone(db, lat, lon)
    return ContainingZoneResponse(
        location=GeoPoint(lat=lat, lon=lon),
        zone=zone_out(zone) if zone else None,
        area_risk_score=_area_risk(lat, lon, datetime.now(UTC)),
    )
