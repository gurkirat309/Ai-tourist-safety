"""Pydantic schemas for location pings."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.geo import GeoPoint


class LocationPingCreate(BaseModel):
    tourist_id: uuid.UUID
    location: GeoPoint
    recorded_at: datetime
    speed_mps: float | None = Field(default=None, ge=0)
    accuracy_m: float | None = Field(default=None, ge=0)
    source: str | None = Field(default=None, max_length=32)


class LocationPingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tourist_id: uuid.UUID
    location: GeoPoint
    recorded_at: datetime
    speed_mps: float | None
    accuracy_m: float | None
    source: str | None
