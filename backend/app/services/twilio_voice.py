"""Twilio Voice service for managing outbound emergency calls and TwiML responses."""

from __future__ import annotations

import uuid
from typing import Any

from twilio.rest import Client
from twilio.twiml.voice_response import Gather, VoiceResponse

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


class TwilioVoiceService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.account_sid = self.settings.twilio_account_sid.strip()
        self.auth_token = self.settings.twilio_auth_token.strip()
        self.from_phone = self.settings.twilio_from_phone.strip()
        self.webhook_base_url = self.settings.twilio_webhook_base_url.strip().rstrip("/")
        self.dry_run = (
            self.settings.twilio_dry_run
            or not self.account_sid
            or not self.auth_token
            or not self.from_phone
        )
        self._client: Client | None = None

    @property
    def client(self) -> Client:
        if self._client is None:
            if self.dry_run:
                raise RuntimeError("Cannot instantiate Twilio Client in dry-run mode")
            self._client = Client(self.account_sid, self.auth_token)
        return self._client

    def initiate_call(self, to_phone: str, tourist_name: str, tourist_id: uuid.UUID) -> dict[str, Any]:
        """Trigger an outbound voice call to the tourist's phone number."""
        clean_phone = to_phone.strip().replace(" ", "").replace("-", "")
        if not clean_phone.startswith("+"):
            # Default to India country code if not provided
            clean_phone = f"+91{clean_phone}"

        greeting_url = f"{self.webhook_base_url}/voice/greeting?tourist_id={tourist_id}"
        status_url = f"{self.webhook_base_url}/voice/status?tourist_id={tourist_id}"

        if self.dry_run:
            fake_sid = f"CA_MOCK_{uuid.uuid4().hex[:16]}"
            log.info(
                "[DRY-RUN] Twilio Voice call initiated: to=%s, name=%s, url=%s, sid=%s",
                clean_phone,
                tourist_name,
                greeting_url,
                fake_sid,
            )
            return {"call_sid": fake_sid, "status": "queued", "dry_run": True}

        try:
            log.info("Dispatching real Twilio call to %s from %s (url=%s)", clean_phone, self.from_phone, greeting_url)
            call = self.client.calls.create(
                to=clean_phone,
                from_=self.from_phone,
                url=greeting_url,
                status_callback=status_url,
                status_callback_event=["completed", "busy", "no-answer", "failed"],
            )
            return {"call_sid": call.sid, "status": call.status, "dry_run": False}
        except Exception as e:
            log.exception("Failed to dispatch Twilio call to %s: %s", clean_phone, e)
            raise

    def build_greeting_twiml(self, tourist_name: str, location_context: str, tourist_id: uuid.UUID) -> str:
        """Initial TwiML greeting played when the tourist answers."""
        response = VoiceResponse()
        gather = Gather(
            input="speech",
            action=f"{self.webhook_base_url}/voice/respond?tourist_id={tourist_id}",
            method="POST",
            timeout=5,
            speech_timeout="auto",
            language="en-IN",
        )
        greeting = (
            f"Hello {tourist_name}. This is your Bengaluru Tourist Safety AI Assistant. "
            f"We have your location near {location_context}. "
            "Please tell me, what is your emergency?"
        )
        gather.say(greeting, voice="Polly.Aditi", language="en-IN")
        response.append(gather)

        # Fallback if no speech is detected on the first turn
        retry_gather = Gather(
            input="speech",
            action=f"{self.webhook_base_url}/voice/respond?tourist_id={tourist_id}",
            method="POST",
            timeout=5,
            speech_timeout="auto",
            language="en-IN",
        )
        retry_gather.say(
            "I didn't hear you. If you are in danger or need immediate police assistance, please speak now.",
            voice="Polly.Aditi",
            language="en-IN",
        )
        response.append(retry_gather)
        response.say("No response received. Emergency control room 112 is on standby. Goodbye.", voice="Polly.Aditi", language="en-IN")
        return str(response)

    def build_response_twiml(self, ai_text: str, tourist_id: uuid.UUID, is_final: bool = False) -> str:
        """TwiML for conversational turns."""
        response = VoiceResponse()
        if is_final:
            response.say(ai_text, voice="Polly.Aditi", language="en-IN")
            response.hangup()
            return str(response)

        gather = Gather(
            input="speech",
            action=f"{self.webhook_base_url}/voice/respond?tourist_id={tourist_id}",
            method="POST",
            timeout=5,
            speech_timeout="auto",
            language="en-IN",
        )
        gather.say(ai_text, voice="Polly.Aditi", language="en-IN")
        response.append(gather)

        # Fallback if tourist stays silent after AI advice
        response.say(
            "If you are safe, you may hang up now. Otherwise, stay near well-lit public areas.",
            voice="Polly.Aditi",
            language="en-IN",
        )
        return str(response)
