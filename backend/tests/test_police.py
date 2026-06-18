"""Phase 3 tests for police endpoints (role-guarded)."""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.db.enums import UserRole
from app.db.models import User
from app.main import app
from app.services.security import hash_password


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _police(client, db, email="pcop@example.com"):
    db.add(User(email=email, hashed_password=hash_password("copsecret"),
                role=UserRole.POLICE))
    db.flush()
    tok = client.post("/auth/login", json={"email": email, "password": "copsecret"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _tourist_token(client, email="ptourist@example.com"):
    r = client.post("/auth/signup", json={"email": email, "password": "hunter2",
                                          "display_name": "P Tourist", "consent_given": True})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_police_endpoints_require_auth(client):
    assert client.get("/police/tourists").status_code in (401, 403)
    assert client.get("/police/risk-events").status_code in (401, 403)


def test_tourist_cannot_access_police(client):
    h = _tourist_token(client)
    assert client.get("/police/tourists", headers=h).status_code == 403
    assert client.get("/police/risk-events", headers=h).status_code == 403


def test_police_lists_tourists_with_status(client, db_session):
    # A signed-up tourist who shares a location should appear with a status.
    th = _tourist_token(client, email="seen@example.com")
    client.post("/me/pings", headers=th, json={"location": {"lat": 12.80, "lon": 77.577}})

    ph = _police(client, db_session)
    r = client.get("/police/tourists", headers=ph)
    assert r.status_code == 200
    tourists = r.json()
    assert any(t["display_name"] == "P Tourist" or t["last_position"] for t in tourists)
    # Every entry has a status field.
    assert all("status" in t for t in tourists)


def test_police_tourist_detail_has_timeline(client, db_session):
    th = _tourist_token(client, email="detail@example.com")
    me = client.get("/auth/me", headers=th).json()
    tid = me["tourist_id"]
    client.post("/me/pings", headers=th, json={"location": {"lat": 12.80, "lon": 77.577}})

    ph = _police(client, db_session)
    r = client.get(f"/police/tourists/{tid}", headers=ph)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == tid
    assert len(body["recent_pings"]) >= 1
    # A restricted-zone ping should have produced an incident.
    assert len(body["incidents"]) >= 1


def test_police_risk_events_returns_crime(client, db_session):
    from datetime import UTC, datetime

    from app.db.enums import RiskEventType
    from app.db.models import RiskEvent

    db_session.add(RiskEvent(
        event_type=RiskEventType.CRIME, title="Test theft report",
        source="test", event_time=datetime.now(UTC), confidence=0.7,
    ))
    db_session.flush()

    ph = _police(client, db_session)
    r = client.get("/police/risk-events", headers=ph)
    assert r.status_code == 200
    assert any(e["title"] == "Test theft report" for e in r.json())
