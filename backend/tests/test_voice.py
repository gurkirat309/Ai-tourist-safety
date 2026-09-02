"""Tests for Twilio Voice Service and Webhook Endpoints."""

import uuid
from xml.etree import ElementTree

from app.core.config import Settings
from app.services.twilio_voice import TwilioVoiceService


def test_twilio_voice_service_dry_run():
    settings = Settings(
        twilio_account_sid="ACmock1234567890",
        twilio_auth_token="mock_token",
        twilio_from_phone="+1234567890",
        twilio_webhook_base_url="https://mock.trycloudflare.com",
        twilio_dry_run=True,
    )
    svc = TwilioVoiceService(settings=settings)
    tourist_id = uuid.uuid4()
    call = svc.initiate_call(to_phone="+919876543210", tourist_name="Raja", tourist_id=tourist_id)
    assert call["status"] == "queued"
    assert "CA_MOCK_" in call["call_sid"]
    assert call["dry_run"] is True


def test_twilio_voice_twiml_generation():
    settings = Settings(
        twilio_webhook_base_url="https://mock.trycloudflare.com",
        twilio_dry_run=True,
    )
    svc = TwilioVoiceService(settings=settings)
    tourist_id = uuid.uuid4()

    # Greeting TwiML
    greeting = svc.build_greeting_twiml("Raja", "Cubbon Park", tourist_id)
    assert "<Response>" in greeting
    assert "<Gather" in greeting
    assert "Cubbon Park" in greeting
    # Valid XML check
    root = ElementTree.fromstring(greeting)
    assert root.tag == "Response"

    # Response TwiML
    resp = svc.build_response_twiml("Move toward the police booth.", tourist_id, is_final=False)
    assert "Move toward the police booth." in resp
    root_resp = ElementTree.fromstring(resp)
    assert root_resp.tag == "Response"

    # Final response TwiML
    final_resp = svc.build_response_twiml("Glad you are safe. Goodbye.", tourist_id, is_final=True)
    assert "<Hangup" in final_resp
    root_final = ElementTree.fromstring(final_resp)
    assert root_final.tag == "Response"
