"""Risk query endpoints (M7): area-risk score and zone risk."""

from __future__ import annotations

from datetime import UTC, datetime
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
