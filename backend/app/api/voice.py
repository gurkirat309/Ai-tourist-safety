"""Twilio Voice webhook endpoints and tourist call trigger."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.me import get_current_tourist
from app.core.logging import get_logger
from app.db.enums import AlertSeverity, AlertStatus, IncidentStatus, IncidentType
from app.db.models import Alert, Incident, LocationPing, Tourist, Zone
from app.db.spatial import geom_to_latlon
from app.services.llm import LLMClient
from app.services.twilio_voice import TwilioVoiceService

log = get_logger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])


class VoiceCallRequest(BaseModel):
    phone_number: str | None = None


@router.post("/call-me")
def request_voice_call(
    req: VoiceCallRequest,
    tourist: Tourist = Depends(get_current_tourist),
    db: Session = Depends(get_db),
) -> dict:
    """Initiate an outbound emergency AI voice call to the tourist's phone."""
    phone = req.phone_number or tourist.emergency_contact
    if not phone or len(phone.strip()) < 5:
        raise HTTPException(
            status_code=400,
            detail="A valid phone number is required. Please provide a verified mobile number.",
        )

    # Save phone as emergency contact if updated
    if req.phone_number and req.phone_number.strip() != tourist.emergency_contact:
        tourist.emergency_contact = req.phone_number.strip()
        db.add(tourist)

    # Fetch last known position
    stmt = (
        select(LocationPing)
        .where(LocationPing.tourist_id == tourist.id)
        .order_by(desc(LocationPing.recorded_at))
        .limit(1)
    )
    last_ping = db.scalars(stmt).first()
    geom = last_ping.geom if last_ping else None

    # Create or reuse active incident
    incident = Incident(
        tourist_id=tourist.id,
        incident_type=IncidentType.PANIC,
        status=IncidentStatus.OPEN,
        detected_at=datetime.now(UTC),
        geom=geom,
        details={
            "trigger": "ai_voice_call",
            "phone_called": phone,
            "call_started_at": datetime.now(UTC).isoformat(),
            "transcript": [],
        },
    )
    db.add(incident)
    db.flush()

    # Add an emergency alert for the police dashboard
    alert = Alert(
        incident_id=incident.id,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.PENDING,
        summary=f"Tourist {tourist.display_name or 'Unknown'} requested AI Emergency Voice Assistance",
        recommended_action="Monitor live voice call transcript; dispatch patrol if distress escalates.",
        created_by="voice_orchestrator",
    )
    db.add(alert)
    db.commit()

    # Dispatch outbound call via Twilio
    voice_service = TwilioVoiceService()
    try:
        call_info = voice_service.initiate_call(
            to_phone=phone,
            tourist_name=tourist.display_name or "Tourist",
            tourist_id=tourist.id,
        )
    except Exception as e:
        log.exception("Twilio call initiation failed: %s", e)
        clean_err = getattr(e, "msg", str(e))
        raise HTTPException(status_code=502, detail=f"Twilio Call Error: {clean_err}")

    # Store call SID in incident details
    incident.details["call_sid"] = call_info.get("call_sid")
    db.add(incident)
    db.commit()

    return {
        "status": "call_dispatched",
        "phone": phone,
        "call_sid": call_info.get("call_sid"),
        "incident_id": str(incident.id),
        "dry_run": call_info.get("dry_run", False),
    }


@router.post("/greeting")
def voice_greeting(
    tourist_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
) -> Response:
    """TwiML webhook called by Twilio when the tourist answers the call."""
    tourist = db.get(Tourist, tourist_id)
    tourist_name = tourist.display_name if tourist else "Tourist"

    # Get location context
    location_desc = "Bengaluru"
    if tourist:
        stmt = (
            select(LocationPing)
            .where(LocationPing.tourist_id == tourist.id)
            .order_by(desc(LocationPing.recorded_at))
            .limit(1)
        )
        last_ping = db.scalars(stmt).first()
        if last_ping:
            latlon = geom_to_latlon(last_ping.geom)
            # Find containing zone if available
            zone_stmt = select(Zone).where(Zone.geom.ST_Contains(last_ping.geom)).limit(1)
            zone = db.scalars(zone_stmt).first()
            if zone:
                location_desc = f"{zone.name} ({zone.risk_category} risk area)"
            elif latlon:
                location_desc = f"coordinates {latlon.lat:.3f}, {latlon.lon:.3f}"

    voice_service = TwilioVoiceService()
    twiml = voice_service.build_greeting_twiml(
        tourist_name=tourist_name,
        location_context=location_desc,
        tourist_id=tourist_id,
    )
    log.info("Serving voice greeting TwiML for tourist %s at %s", tourist_id, location_desc)
    return Response(content=twiml, media_type="application/xml")


@router.post("/respond")
def voice_respond(
    tourist_id: uuid.UUID = Query(...),
    SpeechResult: str = Form(default=""),
    db: Session = Depends(get_db),
) -> Response:
    """Twilio webhook called with transcribed speech from the tourist."""
    speech = SpeechResult.strip()
    log.info("Tourist %s spoken audio: %r", tourist_id, speech)

    tourist = db.get(Tourist, tourist_id)
    tourist_name = tourist.display_name if tourist else "Tourist"

    # Fetch active incident to log transcript
    stmt = (
        select(Incident)
        .where(Incident.tourist_id == tourist_id)
        .order_by(desc(Incident.detected_at))
        .limit(1)
    )
    incident = db.scalars(stmt).first()

    # Determine location context
    location_desc = "Bengaluru central region"
    if tourist:
        ping_stmt = (
            select(LocationPing)
            .where(LocationPing.tourist_id == tourist.id)
            .order_by(desc(LocationPing.recorded_at))
            .limit(1)
        )
        last_ping = db.scalars(ping_stmt).first()
        if last_ping:
            latlon = geom_to_latlon(last_ping.geom)
            zone_stmt = select(Zone).where(Zone.geom.ST_Contains(last_ping.geom)).limit(1)
            zone = db.scalars(zone_stmt).first()
            if zone:
                location_desc = f"{zone.name} ({zone.risk_category} risk zone)"
            elif latlon:
                location_desc = f"coordinates {latlon.lat:.3f}, {latlon.lon:.3f}"

    # Generate response via LLM
    llm = LLMClient()
    system_prompt = (
        "You are an emergency crisis response AI voice assistant for tourists in Bengaluru, India. "
        "Keep your response concise, calm, and reassuring (maximum 2-3 sentences) because it is being read aloud over a phone call. "
        "Provide direct safety guidance or tell them where to move. "
        "Return STRICT JSON with keys 'reply' (the text to speak aloud) and 'is_resolved' (boolean, true if tourist says they are safe, fine, or want to hang up)."
    )
    user_prompt = (
        f"Tourist: {tourist_name}\n"
        f"Current Location Context: {location_desc}\n"
        f"Spoken by tourist: {speech or '(Silence / unclear audio)'}"
    )

    is_final = False
    ai_reply = ""

    if llm.dry_run or not speech:
        # Smart heuristic fallback for dry-run or low connectivity
        speech_lower = speech.lower()
        if any(w in speech_lower for w in ["safe", "fine", "okay", "bye", "goodbye", "no problem"]):
            ai_reply = "I'm glad to hear you are safe. Bengaluru Police control room is still monitoring. Have a safe journey, goodbye."
            is_final = True
        elif any(w in speech_lower for w in ["lost", "help", "danger", "follow", "dark", "fear", "stuck"]):
            ai_reply = f"Stay calm. I see you are near {location_desc}. Please move toward the nearest lit street or store. Emergency assistance has your coordinates."
        else:
            ai_reply = f"I have received your location at {location_desc}. Stay near public lit areas. If you need immediate assistance, please say help."
    else:
        try:
            res = llm.extract_json(system_prompt, user_prompt)
            ai_reply = res.get("reply", "")
            is_final = bool(res.get("is_resolved", False))
        except Exception as e:
            log.warning("LLM extraction error during voice dialogue: %s", e)
            ai_reply = "I have your location. Please stay in a safe, visible area. Emergency services are aware."

    # Update transcript in incident details
    if incident and incident.details:
        current_transcript = incident.details.get("transcript", [])
        current_transcript.append({"speaker": "tourist", "text": speech, "time": datetime.now(UTC).isoformat()})
        current_transcript.append({"speaker": "ai", "text": ai_reply, "time": datetime.now(UTC).isoformat()})
        incident.details["transcript"] = current_transcript
        incident.details["last_ai_reply"] = ai_reply
        db.add(incident)
        db.commit()

    voice_service = TwilioVoiceService()
    twiml = voice_service.build_response_twiml(ai_text=ai_reply, tourist_id=tourist_id, is_final=is_final)
    return Response(content=twiml, media_type="application/xml")


@router.post("/status")
def voice_status(
    tourist_id: uuid.UUID = Query(...),
    CallSid: str = Form(default=""),
    CallStatus: str = Form(default=""),
    CallDuration: str = Form(default="0"),
    db: Session = Depends(get_db),
) -> dict:
    """Twilio status callback when the call ends."""
    log.info("Twilio Call %s for tourist %s ended with status %s (duration %ss)", CallSid, tourist_id, CallStatus, CallDuration)
    stmt = (
        select(Incident)
        .where(Incident.tourist_id == tourist_id)
        .order_by(desc(Incident.detected_at))
        .limit(1)
    )
    incident = db.scalars(stmt).first()
    if incident and incident.details:
        incident.details["call_final_status"] = CallStatus
        incident.details["call_duration_seconds"] = CallDuration
        db.add(incident)
        db.commit()
    return {"status": "ok"}
