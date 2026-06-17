"""ORM -> API response converters (handles PostGIS geometry)."""

from __future__ import annotations

from app.db.models import Alert, Incident, Zone
from app.db.spatial import geom_to_latlon
from app.schemas.api import AlertOut, IncidentDetailOut, IncidentOut, ZoneRiskOut
from app.schemas.geo import GeoPoint


def _point(geom) -> GeoPoint | None:
    if geom is None:
        return None
    lat, lon = geom_to_latlon(geom)
    return GeoPoint(lat=lat, lon=lon)


def zone_out(z: Zone) -> ZoneRiskOut:
    return ZoneRiskOut(
        id=z.id,
        name=z.name,
        risk_category=z.risk_category.value,
        restricted=z.restricted,
        capacity=z.capacity,
    )


def incident_out(inc: Incident) -> IncidentOut:
    return IncidentOut(
        id=inc.id,
        tourist_id=inc.tourist_id,
        zone_id=inc.zone_id,
        incident_type=inc.incident_type.value,
        status=inc.status.value,
        location=_point(inc.geom),
        detected_at=inc.detected_at,
        details=inc.details,
        created_at=inc.created_at,
    )


def alert_out(a: Alert) -> AlertOut:
    return AlertOut(
        id=a.id,
        incident_id=a.incident_id,
        severity=a.severity.value,
        status=a.status.value,
        summary=a.summary,
        recommended_action=a.recommended_action,
        created_by=a.created_by,
        created_at=a.created_at,
    )


def incident_detail_out(inc: Incident, alerts: list[Alert]) -> IncidentDetailOut:
    base = incident_out(inc).model_dump()
    return IncidentDetailOut(**base, alerts=[alert_out(a) for a in alerts])
