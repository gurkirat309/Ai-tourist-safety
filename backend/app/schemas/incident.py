"""Pydantic schemas for incidents."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.db.enums import IncidentStatus, IncidentType
from app.schemas.geo import GeoPoint


class IncidentCreate(BaseModel):
    tourist_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None
    incident_type: IncidentType
    location: GeoPoint | None = None
    detected_at: datetime
    details: dict[str, Any] | None = None


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tourist_id: uuid.UUID | None
    zone_id: uuid.UUID | None
    incident_type: IncidentType
    status: IncidentStatus
    location: GeoPoint | None
    detected_at: datetime
    details: dict[str, Any] | None
    created_at: datetime
