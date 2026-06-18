"""M7 API tests (TestClient) — DB + LLM dependencies overridden onto the
transactional test session / dry-run LLM, so no network and full isolation."""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db, get_llm
from app.db.enums import RiskCategory, UserRole
from app.db.models import User, Zone
from app.db.spatial import polygon_to_geom
from app.main import app
from app.services.llm import LLMClient
from app.services.security import hash_password

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


def _police_headers(client, db, email="apicop@example.com"):
    """Create a police user and return an auth header (incidents/alerts are
    police-only)."""
    db.add(User(email=email, hashed_password=hash_password("copsecret"),
                role=UserRole.POLICE))
    db.flush()
    tok = client.post("/auth/login", json={"email": email, "password": "copsecret"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


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
    headers = _police_headers(client, db_session)
    detail = client.get(f"/incidents/{inc_id}", headers=headers).json()
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


def test_zones_geojson(client, db_session):
    _add_restricted_zone(db_session)
    resp = client.get("/risk/zones.geojson")
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) >= 1
    feat = next(f for f in body["features"] if f["properties"]["name"] == "API Restricted")
    assert feat["geometry"]["type"] == "Polygon"
    assert feat["properties"]["restricted"] is True


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

    headers = _police_headers(client, db_session)
    incidents = client.get("/incidents", params={"tourist_id": tid}, headers=headers).json()
    assert len(incidents) >= 1
    alerts = client.get("/alerts", headers=headers).json()
    assert len(alerts) >= 1
