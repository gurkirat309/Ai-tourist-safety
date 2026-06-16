"""M5 tests for the Incident Triage agent."""

from datetime import UTC, datetime, timedelta

from app.agents.triage import (
    IncidentTriageAgent,
    heuristic_escalation,
    to_alert,
)
from app.agents.triage_types import TriageContext
from app.db.enums import AlertSeverity, IncidentType, RiskCategory, RiskEventType
from app.db.models import Incident, LocationPing, RiskEvent, Tourist, Zone
from app.db.spatial import point_to_geom, polygon_to_geom
from app.services.llm import LLMClient

NOW = datetime(2026, 6, 16, 22, tzinfo=UTC)


def _ctx(**kw) -> TriageContext:
    base = dict(incident_type=IncidentType.ROUTE_DEVIATION, detected_at=NOW)
    base.update(kw)
    return TriageContext(**base)


# --- escalation heuristic (pure) ---
def test_panic_is_critical():
    level, _ = heuristic_escalation(_ctx(incident_type=IncidentType.PANIC))
    assert level is AlertSeverity.CRITICAL


def test_restricted_zone_is_at_least_high():
    level, _ = heuristic_escalation(_ctx(zone_restricted=True, zone_name="Forest"))
    assert level is AlertSeverity.HIGH


def test_critical_signal_is_high():
    level, _ = heuristic_escalation(_ctx(signal_severity="critical"))
    assert level is AlertSeverity.HIGH


def test_warning_signal_is_medium():
    level, _ = heuristic_escalation(_ctx(signal_severity="warning"))
    assert level is AlertSeverity.MEDIUM


def test_high_area_risk_is_high():
    level, _ = heuristic_escalation(_ctx(area_risk_score=0.6))
    assert level is AlertSeverity.HIGH


def test_quiet_incident_is_low():
    level, reason = heuristic_escalation(_ctx())
    assert level is AlertSeverity.LOW
    assert reason


def test_takes_max_severity():
    # warning signal (medium) + restricted (high) -> high.
    level, _ = heuristic_escalation(
        _ctx(signal_severity="warning", zone_restricted=True)
    )
    assert level is AlertSeverity.HIGH


# --- DB integration: gather context + full triage ---
def _build_incident(db) -> Incident:
    ring = [
        (77.567, 12.795),
        (77.587, 12.795),
        (77.587, 12.805),
        (77.567, 12.805),
        (77.567, 12.795),
    ]
    zone = Zone(
        name="Test Restricted Forest",
        risk_category=RiskCategory.HIGH,
        restricted=True,
        geom=polygon_to_geom(ring),
    )
    db.add(zone)
    db.flush()

    tourist = Tourist(display_name="Triage Subject", consent_given=True)
    db.add(tourist)
    db.flush()

    lat, lon = 12.800, 77.577
    db.add(LocationPing(tourist_id=tourist.id, geom=point_to_geom(lat, lon),
                        recorded_at=NOW))
    db.add(RiskEvent(
        event_type=RiskEventType.NATURAL_HAZARD,
        title="Wildlife sighting nearby",
        source="test", event_time=NOW - timedelta(hours=2),
        confidence=0.7, geom=point_to_geom(lat, lon),
    ))
    incident = Incident(
        tourist_id=tourist.id,
        zone_id=zone.id,
        incident_type=IncidentType.GEOFENCE_BREACH,
        geom=point_to_geom(lat, lon),
        detected_at=NOW,
        details={"signals": [{"severity": "critical",
                              "reason": "Entered restricted zone"}]},
    )
    db.add(incident)
    db.flush()
    return incident


def test_gather_context_pulls_zone_and_nearby(db_session):
    incident = _build_incident(db_session)
    agent = IncidentTriageAgent(db_session, llm=LLMClient(dry_run=True))
    ctx = agent.gather_context(incident)

    assert ctx.zone_restricted is True
    assert ctx.signal_severity == "critical"
    assert any("Wildlife" in e.title for e in ctx.nearby_events)
    assert ctx.area_risk_score is not None  # M3 model loaded


def test_full_triage_is_high_and_advisory(db_session):
    incident = _build_incident(db_session)
    agent = IncidentTriageAgent(db_session, llm=LLMClient(dry_run=True))
    result = agent.triage(incident)

    assert result.escalation is AlertSeverity.HIGH
    assert result.summary
    assert result.recommended_actions
    assert "dry-run" in result.source


def test_to_alert_matches_escalation(db_session):
    incident = _build_incident(db_session)
    agent = IncidentTriageAgent(db_session, llm=LLMClient(dry_run=True))
    result = agent.triage(incident)
    alert = to_alert(result, incident)

    assert alert.incident_id == incident.id
    assert alert.severity is result.escalation
    assert alert.summary == result.summary
