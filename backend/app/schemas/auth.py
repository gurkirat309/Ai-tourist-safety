"""Auth request/response schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.db.enums import ConsentPurpose, UserRole


class SignupRequest(BaseModel):
    """Tourist self-registration (creates a User + a Tourist profile)."""

    email: str = Field(max_length=255)
    password: str = Field(min_length=6, max_length=128)
    display_name: str | None = Field(default=None, max_length=128)
    nationality: str | None = Field(default=None, max_length=64)
    emergency_contact: str | None = Field(default=None, max_length=64)
    consent_given: bool = True
    consent_purpose: ConsentPurpose = ConsentPurpose.SAFETY_MONITORING


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    tourist_id: uuid.UUID | None = None
    email: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: UserRole
    tourist_id: uuid.UUID | None = None
