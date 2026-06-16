"""Pydantic schemas for alerts (advisory output for humans)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.enums import AlertSeverity, AlertStatus


class AlertCreate(BaseModel):
    incident_id: uuid.UUID
    severity: AlertSeverity = AlertSeverity.INFO
    summary: str | None = None
    recommended_action: str | None = None
    created_by: str | None = None


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    severity: AlertSeverity
    status: AlertStatus
    summary: str | None
    recommended_action: str | None
    created_by: str | None
    created_at: datetime
