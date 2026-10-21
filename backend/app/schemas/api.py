"""Request/response schemas specific to the HTTP API (M7)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

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
    # Which alternative to adopt as the planned route. "safest" is the default
    # because that is the point of the product; the tourist can still ask for
    # "fastest" after seeing the trade-off.
    prefer: Literal["safest", "fastest"] = "safest"


class RoutePointSafety(BaseModel):
    lat: float
    lon: float
    score: float | None


class RouteSafety(BaseModel):
    overall_score: float | None
    max_score: float | None
    label: str
    points: list[RoutePointSafety] = []


class RouteOption(BaseModel):
    """One candidate route, scored for safety.

    `index` is stable within a single response and is what the UI labels.
    """

    index: int
    route: list[tuple[float, float]]  # (lat, lon) pairs for the map
    distance_m: float
    duration_s: float
    source: str
    safety: RouteSafety
    is_fastest: bool = False
    is_safest: bool = False
    # Set on the option actually adopted as the planned route.
    is_selected: bool = False


class TripResponse(BaseModel):
    # The selected route stays at the top level so existing callers keep
    # working unchanged; `alternatives` is additive.
    route: list[tuple[float, float]]  # (lat, lon) pairs for the map
    distance_m: float
    duration_s: float
    source: str
    safety: RouteSafety
    alternatives: list[RouteOption] = []
    # Which preference produced the selection ("safest" | "fastest").
    chosen: str = "safest"
    # Human-readable note on the trade-off, e.g. "6 min slower, 38% safer".
    trade_off: str | None = None


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


class RiskForecastPoint(BaseModel):
    when: datetime
    risk_score: float | None
    label: str


class RiskForecastResponse(BaseModel):
    """Area risk over the next N hours for one location.

    The trained model already takes time-of-day and day-of-week as features,
    so this is the same model asked about the future rather than now. It lets
    a tourist answer "is it safe to come back here tonight?".
    """

    location: GeoPoint
    points: list[RiskForecastPoint] = []
    model_available: bool = False
    safest: RiskForecastPoint | None = None
    riskiest: RiskForecastPoint | None = None


class AdvisoryOut(BaseModel):
    """A risk event, sanitized for tourist eyes.

    Deliberately omits the event title, description and source URL. Tourists
    get awareness ("civil unrest reported near Majestic in the last 6h") and
    never the underlying crime specifics, which stay police-only.
    """

    event_type: str
    advice: str
    area: str | None = None
    # Coarse location (~100 m) so it can be mapped without pinpointing anyone.
    location: GeoPoint | None = None
    event_time: datetime
    confidence: float


class AdvisoriesResponse(BaseModel):
    advisories: list[AdvisoryOut] = []
    radius_m: int
    since_hours: int


# --- Police schemas ---
class ActiveTouristOut(BaseModel):
    id: uuid.UUID
    display_name: str | None
    nationality: str | None
    last_position: GeoPoint | None
    last_seen: datetime | None
    zone_name: str | None = None
    area_risk_score: float | None = None
    status: str  # safe | inactive | alert | panic | no_data
    open_incidents: int = 0


class TimelinePing(BaseModel):
    lat: float
    lon: float
    recorded_at: datetime
    source: str | None = None


class TouristDetailOut(BaseModel):
    id: uuid.UUID
    display_name: str | None
    nationality: str | None
    emergency_contact: str | None
    consent_given: bool
    status: str
    last_position: GeoPoint | None
    zone_name: str | None = None
    area_risk_score: float | None = None
    recent_pings: list[TimelinePing] = []
    incidents: list[IncidentOut] = []


class RiskEventOut(BaseModel):
    id: uuid.UUID
    event_type: str
    title: str
    description: str | None
    location: GeoPoint | None
    zone_id: uuid.UUID | None
    source: str
    source_url: str | None
    event_time: datetime
    confidence: float
