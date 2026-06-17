"""Tourist registration + consent endpoints (M7)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.db.models import Tourist
from app.db.spatial import linestring_to_geom
from app.schemas.tourist import TouristCreate, TouristRead

router = APIRouter(prefix="/tourists", tags=["tourists"])


@router.post("", response_model=TouristRead, status_code=201)
def register_tourist(payload: TouristCreate, db: Session = Depends(get_db)) -> Tourist:
    """Register a tourist with consent. Retention is set per DPDP config."""
    now = datetime.now(UTC)
    retention_days = get_settings().location_retention_days

    tourist = Tourist(
        display_name=payload.display_name,
        nationality=payload.nationality,
        emergency_contact=payload.emergency_contact,
        external_ref=payload.external_ref,
        planned_route=(
            linestring_to_geom(payload.planned_route) if payload.planned_route else None
        ),
        consent_given=payload.consent.consent_given,
        consent_purpose=payload.consent.consent_purpose,
        consent_timestamp=now if payload.consent.consent_given else None,
        retention_until=(
            now + timedelta(days=retention_days)
            if payload.consent.consent_given
            else None
        ),
        is_active=True,
    )
    db.add(tourist)
    db.commit()
    db.refresh(tourist)
    return tourist


@router.get("/{tourist_id}", response_model=TouristRead)
def get_tourist(tourist_id: uuid.UUID, db: Session = Depends(get_db)) -> Tourist:
    tourist = db.get(Tourist, tourist_id)
    if tourist is None:
        raise HTTPException(status_code=404, detail="Tourist not found")
    return tourist
