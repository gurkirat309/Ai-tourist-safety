"""Pydantic schemas for zones."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import RiskCategory
from app.schemas.geo import Coordinate


class ZoneCreate(BaseModel):
    name: str = Field(max_length=128)
    description: str | None = None
    risk_category: RiskCategory = RiskCategory.LOW
    restricted: bool = False
    capacity: int | None = Field(default=None, ge=0)
    # Outer ring as [lon, lat] pairs (first/last may repeat).
    polygon: list[Coordinate] = Field(min_length=3)


class ZoneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    risk_category: RiskCategory
    restricted: bool
    capacity: int | None
    created_at: datetime
