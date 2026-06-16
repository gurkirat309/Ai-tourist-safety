"""Pydantic schemas for tourists (incl. DPDP consent)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import ConsentPurpose
from app.schemas.geo import Coordinate


class ConsentIn(BaseModel):
    """Consent declaration captured at registration."""

    consent_given: bool = False
    consent_purpose: ConsentPurpose = ConsentPurpose.SAFETY_MONITORING


class TouristCreate(BaseModel):
    display_name: str | None = Field(default=None, max_length=128)
    nationality: str | None = Field(default=None, max_length=64)
    emergency_contact: str | None = Field(default=None, max_length=64)
    external_ref: str | None = Field(default=None, max_length=128)
    # Planned route as [lon, lat] pairs (optional).
    planned_route: list[Coordinate] | None = None
    consent: ConsentIn = ConsentIn()


class TouristRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str | None
    nationality: str | None
    consent_given: bool
    consent_purpose: ConsentPurpose
    consent_timestamp: datetime | None
    retention_until: datetime | None
    is_active: bool
    created_at: datetime
