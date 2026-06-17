"""Location ingest + panic endpoints (M7).

Ingest runs the full orchestrator (detection -> risk -> escalation -> triage).
Panic is an immediate, threshold-bypassing escalation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_realtime_llm
from app.db.models import Tourist
from app.orchestrator.orchestrator import OrchestrationResult, SafetyOrchestrator
from app.schemas.api import OrchestrationResponse, PanicRequest, PingIngestRequest
from app.services.llm import LLMClient

router = APIRouter(tags=["locations"])


def _to_response(result: OrchestrationResult) -> OrchestrationResponse:
    return OrchestrationResponse(
        ping_id=result.ping_id,
        zone_name=result.zone_name,
        area_risk_score=result.area_risk_score,
        signals=[s.as_dict() for s in result.signals],
        incident_id=result.incident_id,
        incident_created=result.incident_created,
        alert_id=result.alert_id,
        escalation=result.escalation,
        trace=result.trace,
    )


def _require_consenting_tourist(db: Session, tourist_id: uuid.UUID) -> Tourist:
    tourist = db.get(Tourist, tourist_id)
    if tourist is None:
        raise HTTPException(status_code=404, detail="Tourist not found")
    if not tourist.consent_given:
        # DPDP: do not process location without consent.
        raise HTTPException(status_code=403, detail="Tourist has not given consent")
    return tourist


@router.post("/tourists/{tourist_id}/pings", response_model=OrchestrationResponse)
def ingest_ping(
    tourist_id: uuid.UUID,
    payload: PingIngestRequest,
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_realtime_llm),
) -> OrchestrationResponse:
    _require_consenting_tourist(db, tourist_id)
    orch = SafetyOrchestrator(db, llm=llm)
    result = orch.process_location_update(
        tourist_id,
        payload.location.lat,
        payload.location.lon,
        payload.recorded_at or datetime.now(UTC),
        speed_mps=payload.speed_mps,
        accuracy_m=payload.accuracy_m,
        source=payload.source,
    )
    return _to_response(result)


@router.post("/tourists/{tourist_id}/panic", response_model=OrchestrationResponse)
def trigger_panic(
    tourist_id: uuid.UUID,
    payload: PanicRequest,
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_realtime_llm),
) -> OrchestrationResponse:
    # Panic bypasses thresholds; we still require the tourist to exist. We do
    # NOT block on consent here — a panic signal is an emergency.
    if db.get(Tourist, tourist_id) is None:
        raise HTTPException(status_code=404, detail="Tourist not found")
    orch = SafetyOrchestrator(db, llm=llm)
    result = orch.trigger_panic(
        tourist_id,
        payload.location.lat,
        payload.location.lon,
        payload.recorded_at or datetime.now(UTC),
    )
    return _to_response(result)
