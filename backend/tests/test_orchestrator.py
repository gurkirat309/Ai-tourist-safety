"""M6 tests for the safety orchestrator."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.db.enums import IncidentStatus, IncidentType, RiskCategory
from app.db.models import Alert, Incident, Tourist, Zone
from app.db.spatial import polygon_to_geom
from app.orchestrator.orchestrator import SafetyOrchestrator
from app.services.llm import LLMClient

NOW = datetime(2026, 6, 16, 22, tzinfo=UTC)

# A restricted zone far from the seeded Bengaluru zones, so tests are isolated.
ZLON, ZLAT = 78.40, 13.40
RING = [
    (ZLON - 0.01, ZLAT - 0.01),
    (ZLON + 0.01, ZLAT - 0.01),
    (ZLON + 0.01, ZLAT + 0.01),
    (ZLON - 0.01, ZLAT + 0.01),
    (ZLON - 0.01, ZLAT - 0.01),
]
# A point with no zone coverage at all.
EMPTY_LAT, EMPTY_LON = 13.90, 78.90


def _restricted_zone(db) -> Zone:
    z = Zone(name="Test Restricted", risk_category=RiskCategory.HIGH,
             restricted=True, geom=polygon_to_geom(RING))
    db.add(z)
    db.flush()
    return z


def _tourist(db) -> Tourist:
    t = Tourist(display_name="Orch Subject", consent_given=True)
    db.add(t)
    db.flush()
    return t


def _orch(db) -> SafetyOrchestrator:
    return SafetyOrchestrator(db, llm=LLMClient(dry_run=True))


def test_normal_update_creates_no_incident(db_session):
    t = _tourist(db_session)
    res = _orch(db_session).process_location_update(
        t.id, EMPTY_LAT, EMPTY_LON, NOW
    )
    assert res.ping_id is not None
    assert res.signals == []
    assert res.incident_id is None
    assert res.incident_created is False


def test_restricted_entry_creates_incident_and_alert(db_session):
    _restricted_zone(db_session)
    t = _tourist(db_session)

    res = _orch(db_session).process_location_update(t.id, ZLAT, ZLON, NOW)

    assert res.incident_created is True
    assert res.incident_id is not None
    assert res.escalation in ("high", "critical")

    incident = db_session.get(Incident, res.incident_id)
    assert incident.incident_type is IncidentType.GEOFENCE_BREACH
    assert incident.status is IncidentStatus.OPEN
    # An advisory alert was attached.
    alert = db_session.execute(
        select(Alert).where(Alert.incident_id == incident.id)
    ).scalars().one()
    assert alert.severity.value == res.escalation
    assert alert.summary


def test_dedupe_reuses_open_incident(db_session):
    _restricted_zone(db_session)
    t = _tourist(db_session)
    orch = _orch(db_session)

    first = orch.process_location_update(t.id, ZLAT, ZLON, NOW)
    second = orch.process_location_update(
        t.id, ZLAT + 0.001, ZLON, NOW + timedelta(minutes=2)
    )

    assert first.incident_created is True
    assert second.incident_created is False
    assert second.incident_id == first.incident_id

    # Exactly one geofence incident, and one alert (no spam on reuse).
    n_inc = db_session.execute(
        select(func.count(Incident.id)).where(Incident.tourist_id == t.id)
    ).scalar_one()
    n_alerts = db_session.execute(
        select(func.count(Alert.id)).where(Alert.incident_id == first.incident_id)
    ).scalar_one()
    assert n_inc == 1
    assert n_alerts == 1


def test_panic_bypasses_threshold_and_is_critical(db_session):
    t = _tourist(db_session)
    # Panic at an empty location with zero detection signals.
    res = _orch(db_session).trigger_panic(t.id, EMPTY_LAT, EMPTY_LON, NOW)

    assert res.incident_created is True
    incident = db_session.get(Incident, res.incident_id)
    assert incident.incident_type is IncidentType.PANIC
    assert res.escalation == "critical"

    alert = db_session.execute(
        select(Alert).where(Alert.incident_id == incident.id)
    ).scalars().one()
    assert alert.severity.value == "critical"


def test_decision_trace_recorded(db_session):
    _restricted_zone(db_session)
    t = _tourist(db_session)
    res = _orch(db_session).process_location_update(t.id, ZLAT, ZLON, NOW)
    assert res.trace
    assert any("incident" in line.lower() for line in res.trace)
