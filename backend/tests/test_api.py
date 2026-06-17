"""M7 API tests (TestClient) — DB + LLM dependencies overridden onto the
transactional test session / dry-run LLM, so no network and full isolation."""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db, get_llm
from app.db.enums import RiskCategory
from app.db.models import Zone
from app.db.spatial import polygon_to_geom
from app.main import app
from app.services.llm import LLMClient

# Restricted zone far from seeded zones (isolation).
ZLON, ZLAT = 78.40, 13.40
RING = [
    (ZLON - 0.01, ZLAT - 0.01),
    (ZLON + 0.01, ZLAT - 0.01),
    (ZLON + 0.01, ZLAT + 0.01),
    (ZLON - 0.01, ZLAT + 0.01),
    (ZLON - 0.01, ZLAT - 0.01),
]


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_llm] = lambda: LLMClient(dry_run=True)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _register(client, consent=True) -> str:
    resp = client.post("/tourists", json={
        "display_name": "API Tester",
        "nationality": "IN",
        "consent": {"consent_given": consent},
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _add_restricted_zone(db):
    db.add(Zone(name="API Restricted", risk_category=RiskCategory.HIGH,
               restricted=True, geom=polygon_to_geom(RING)))
    db.flush()


def test_register_and_get_tourist(client):
    tid = _register(client)
    resp = client.get(f"/tourists/{tid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["consent_given"] is True
    assert body["retention_until"] is not None


def test_get_unknown_tourist_404(client):
    resp = client.get("/tourists/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_ingest_without_consent_is_forbidden(client):
    tid = _register(client, consent=False)
    resp = client.post(f"/tourists/{tid}/pings",
                       json={"location": {"lat": 12.97, "lon": 77.59}})
    assert resp.status_code == 403


def test_ingest_in_restricted_zone_creates_incident(client, db_session):
    _add_restricted_zone(db_session)
    tid = _register(client)
    resp = client.post(f"/tourists/{tid}/pings",
                       json={"location": {"lat": ZLAT, "lon": ZLON}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["incident_created"] is True
    assert body["escalation"] in ("high", "critical")
    assert any(s["severity"] == "critical" for s in body["signals"])

    # Now visible in the authorities' incident list + detail (with alert).
    inc_id = body["incident_id"]
    detail = client.get(f"/incidents/{inc_id}").json()
    assert detail["incident_type"] == "geofence_breach"
    assert len(detail["alerts"]) == 1


def test_panic_endpoint_is_critical(client):
    tid = _register(client)
    resp = client.post(f"/tourists/{tid}/panic",
                       json={"location": {"lat": 12.80, "lon": 77.58}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["incident_created"] is True
    assert body["escalation"] == "critical"


def test_area_risk_endpoint(client):
    resp = client.get("/risk/area", params={"lat": 12.977, "lon": 77.572})
    assert resp.status_code == 200
    body = resp.json()
    assert body["model_available"] is True
    assert 0.0 <= body["risk_score"] <= 1.0


def test_list_zones_includes_added(client, db_session):
    _add_restricted_zone(db_session)
    resp = client.get("/risk/zones")
    assert resp.status_code == 200
    names = {z["name"] for z in resp.json()}
    assert "API Restricted" in names


def test_zone_at_point(client, db_session):
    _add_restricted_zone(db_session)
    resp = client.get("/risk/zone", params={"lat": ZLAT, "lon": ZLON})
    assert resp.status_code == 200
    body = resp.json()
    assert body["zone"] is not None
    assert body["zone"]["restricted"] is True


def test_list_incidents_and_alerts(client, db_session):
    _add_restricted_zone(db_session)
    tid = _register(client)
    client.post(f"/tourists/{tid}/pings", json={"location": {"lat": ZLAT, "lon": ZLON}})

    incidents = client.get("/incidents", params={"tourist_id": tid}).json()
    assert len(incidents) >= 1
    alerts = client.get("/alerts").json()
    assert len(alerts) >= 1
