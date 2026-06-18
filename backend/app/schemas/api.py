"""Request/response schemas specific to the HTTP API (M7)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.geo import GeoPoint


class PingIngestRequest(BaseModel):
    location: GeoPoint
    recorded_at: datetime | None = None  # defaults to server time
    speed_mps: float | None = Field(default=None, ge=0)
    accuracy_m: float | None = Field(default=None, ge=0)
    source: str = "api"


class PanicRequest(BaseModel):
    location: GeoPoint
    recorded_at: datetime | None = None


class SignalOut(BaseModel):
    type: str
    severity: str
    reason: str
    confidence: float
    details: dict[str, Any] = {}
    source: str


class OrchestrationResponse(BaseModel):
    ping_id: uuid.UUID | None = None
    zone_name: str | None = None
    area_risk_score: float | None = None
    signals: list[SignalOut] = []
    incident_id: uuid.UUID | None = None
    incident_created: bool = False
    alert_id: uuid.UUID | None = None
    escalation: str | None = None
    trace: list[str] = []


class AreaRiskResponse(BaseModel):
    location: GeoPoint
    when: datetime
    risk_score: float | None
    model_available: bool


class ZoneRiskOut(BaseModel):
    id: uuid.UUID
    name: str
    risk_category: str
    restricted: bool
    capacity: int | None = None


class ContainingZoneResponse(BaseModel):
    location: GeoPoint
    zone: ZoneRiskOut | None = None
    area_risk_score: float | None = None


class IncidentOut(BaseModel):
    id: uuid.UUID
    tourist_id: uuid.UUID | None
    zone_id: uuid.UUID | None
    incident_type: str
    status: str
    location: GeoPoint | None
    detected_at: datetime
    details: dict[str, Any] | None
    created_at: datetime


class AlertOut(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    severity: str
    status: str
    summary: str | None
    recommended_action: str | None
    created_by: str | None
    created_at: datetime


class IncidentDetailOut(IncidentOut):
    alerts: list[AlertOut] = []


# --- Tourist /me schemas ---
class TripRequest(BaseModel):
    start: GeoPoint
    destination: GeoPoint


class RoutePointSafety(BaseModel):
    lat: float
    lon: float
    score: float | None


class RouteSafety(BaseModel):
    overall_score: float | None
    max_score: float | None
    label: str
    points: list[RoutePointSafety] = []


class TripResponse(BaseModel):
    route: list[tuple[float, float]]  # (lat, lon) pairs for the map
    distance_m: float
    duration_s: float
    source: str
    safety: RouteSafety


class TouristStatusResponse(BaseModel):
    tourist_id: uuid.UUID
    display_name: str | None = None
    has_route: bool = False
    last_position: GeoPoint | None = None
    last_seen: datetime | None = None
    zone: ZoneRiskOut | None = None
    area_risk_score: float | None = None
    on_route: bool | None = None
    deviation_m: float | None = None
    status: str = "no_data"  # safe | warning | critical | no_data
    # Safety-only warnings (NO crime specifics — those are police-only).
    warnings: list[SignalOut] = []
