"""Incident + alert listing endpoints for authorities (M7)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.api.serializers import alert_out, incident_detail_out, incident_out
from app.db.enums import IncidentStatus, UserRole
from app.db.models import Alert, Incident
from app.schemas.api import AlertOut, IncidentDetailOut, IncidentOut

# Incidents and alerts are authority data — police only.
router = APIRouter(tags=["incidents"], dependencies=[Depends(require_role(UserRole.POLICE))])


@router.get("/incidents", response_model=list[IncidentOut])
def list_incidents(
    status: IncidentStatus | None = None,
    tourist_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[IncidentOut]:
    stmt = select(Incident).order_by(Incident.detected_at.desc()).limit(limit)
    if status is not None:
        stmt = stmt.where(Incident.status == status)
    if tourist_id is not None:
        stmt = stmt.where(Incident.tourist_id == tourist_id)
    return [incident_out(i) for i in db.execute(stmt).scalars().all()]


@router.get("/incidents/{incident_id}", response_model=IncidentDetailOut)
def get_incident(
    incident_id: uuid.UUID, db: Session = Depends(get_db)
) -> IncidentDetailOut:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    alerts = db.execute(
        select(Alert).where(Alert.incident_id == incident_id).order_by(Alert.created_at)
    ).scalars().all()
    return incident_detail_out(incident, list(alerts))


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AlertOut]:
    alerts = db.execute(
        select(Alert).order_by(Alert.created_at.desc()).limit(limit)
    ).scalars().all()
    return [alert_out(a) for a in alerts]
