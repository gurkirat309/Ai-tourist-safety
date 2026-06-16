"""Pydantic schemas for risk events (grounded signals)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import RiskEventType
from app.schemas.geo import GeoPoint


class RiskEventCreate(BaseModel):
    event_type: RiskEventType = RiskEventType.OTHER
    title: str = Field(max_length=256)
    description: str | None = None
    location: GeoPoint | None = None
    zone_id: uuid.UUID | None = None
    # Grounding (mandatory by architectural rule).
    source: str = Field(max_length=256)
    source_url: str | None = Field(default=None, max_length=512)
    event_time: datetime
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class RiskEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: RiskEventType
    title: str
    description: str | None
    location: GeoPoint | None
    zone_id: uuid.UUID | None
    source: str
    source_url: str | None
    event_time: datetime
    confidence: float
    created_at: datetime
