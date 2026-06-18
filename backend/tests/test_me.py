"""Phase 2 tests for tourist /me endpoints (auth + trip + status + pings)."""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db, get_realtime_llm
from app.main import app
from app.services.llm import LLMClient
from app.services.routing import Route


@pytest.fixture
def client(db_session, monkeypatch):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_realtime_llm] = lambda: LLMClient(dry_run=True)
    # Avoid network in tests: stub the router with a deterministic straight line.
    monkeypatch.setattr(
        "app.api.me.compute_route",
        lambda slat, slon, dlat, dlon: Route(
            coords=[(slon, slat), (dlon, dlat)],
            distance_m=1000.0, duration_s=700.0, source="straightline",
        ),
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _auth(client, email="trip@example.com"):
    r = client.post("/auth/signup", json={"email": email, "password": "hunter2",
                                          "display_name": "Trip Tester", "consent_given": True})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_me_requires_auth(client):
    assert client.get("/me/status").status_code in (401, 403)


def test_plan_trip_returns_route_and_safety(client):
    h = _auth(client)
    r = client.post("/me/trip", headers=h, json={
        "start": {"lat": 12.9716, "lon": 77.5946},
        "destination": {"lat": 12.9352, "lon": 77.6245},
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["route"]) >= 2
    assert body["source"] == "straightline"
    assert "overall_score" in body["safety"]
    assert body["safety"]["label"] in ("low", "moderate", "elevated", "high", "n/a")


def test_status_no_data_then_after_ping(client):
    h = _auth(client, email="status@example.com")
    s0 = client.get("/me/status", headers=h).json()
    assert s0["status"] == "no_data"

    # Send a ping in the restricted Bannerghatta zone (if seeded) — at minimum
    # the status should now have a position and a numeric area-risk score.
    client.post("/me/pings", headers=h, json={"location": {"lat": 12.80, "lon": 77.577}})
    s1 = client.get("/me/status", headers=h).json()
    assert s1["last_position"] is not None
    assert s1["status"] in ("safe", "warning", "critical")


def test_my_panic(client):
    h = _auth(client, email="panic@example.com")
    r = client.post("/me/panic", headers=h, json={"location": {"lat": 12.97, "lon": 77.59}})
    assert r.status_code == 200
    assert r.json()["escalation"] == "critical"


def test_police_cannot_use_me(client, db_session):
    from app.db.enums import UserRole
    from app.db.models import User
    from app.services.security import hash_password

    db_session.add(User(email="cop2@example.com", hashed_password=hash_password("x123456"),
                        role=UserRole.POLICE))
    db_session.flush()
    tok = client.post("/auth/login", json={"email": "cop2@example.com",
                                            "password": "x123456"}).json()["access_token"]
    r = client.get("/me/status", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403
