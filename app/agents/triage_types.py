"""Types for the Incident Triage agent (M5).

Triage output is **advisory only** — it summarizes and recommends an escalation
level for a human to act on. It never dispatches anyone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.db.enums import AlertSeverity, IncidentType


@dataclass
class NearbyEvent:
    title: str
    event_type: str
    confidence: float
    distance_m: float | None = None


@dataclass
class TriageContext:
    """Deterministically-gathered context for an incident (LLM input)."""

    incident_type: IncidentType
    detected_at: datetime
    lat: float | None = None
    lon: float | None = None
    tourist_name: str | None = None
    zone_name: str | None = None
    zone_risk: str | None = None
    zone_restricted: bool = False
    area_risk_score: float | None = None
    # Highest detection severity already attached to the incident, if any.
    signal_severity: str | None = None
    signal_reasons: list[str] = field(default_factory=list)
    nearby_events: list[NearbyEvent] = field(default_factory=list)
    recent_ping_count: int = 0
    minutes_since_last_ping: float | None = None

    def to_prompt_dict(self) -> dict:
        return {
            "incident_type": self.incident_type.value,
            "detected_at": self.detected_at.isoformat(),
            "location": {"lat": self.lat, "lon": self.lon},
            "tourist": self.tourist_name,
            "zone": self.zone_name,
            "zone_risk": self.zone_risk,
            "zone_restricted": self.zone_restricted,
            "area_risk_score": self.area_risk_score,
            "signal_severity": self.signal_severity,
            "signal_reasons": self.signal_reasons,
            "nearby_events": [
                {"title": e.title, "type": e.event_type, "confidence": e.confidence}
                for e in self.nearby_events
            ],
            "recent_ping_count": self.recent_ping_count,
            "minutes_since_last_ping": self.minutes_since_last_ping,
        }


@dataclass
class TriageResult:
    """Structured, advisory triage output."""

    summary: str
    escalation: AlertSeverity
    rationale: str
    recommended_actions: list[str] = field(default_factory=list)
    confidence: float = 0.7
    source: str = "agent.triage"

    def as_dict(self) -> dict:
        return {
            "summary": self.summary,
            "escalation": self.escalation.value,
            "rationale": self.rationale,
            "recommended_actions": self.recommended_actions,
            "confidence": round(self.confidence, 3),
            "source": self.source,
        }
