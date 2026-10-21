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
    # Avoid network in tests: stub the router with two deterministic routes —
    # a direct one and a longer detour — so alternative-scoring is exercised.
    monkeypatch.setattr(
        "app.api.me.compute_routes",
        lambda slat, slon, dlat, dlon, **kw: [
            Route(
                coords=[(slon, slat), (dlon, dlat)],
                distance_m=1000.0, duration_s=700.0, source="straightline",
            ),
            Route(
                coords=[(slon, slat), (slon + 0.01, slat + 0.01), (dlon, dlat)],
                distance_m=1600.0, duration_s=1100.0, source="straightline",
            ),
        ],
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


def test_ping_source_allowlist():
    """A client may label a ping, but only with a known source.

    Demo pings must stay distinguishable from real ones — an officer reading
    simulated movement as a tourist in distress is a safety failure — while
    an arbitrary client-supplied string must never reach the database.
    """
    from app.api.me import _ping_source

    assert _ping_source("demo") == "demo"
    assert _ping_source("mobile_gps") == "mobile_gps"
    assert _ping_source("tourist-app") == "tourist-app"
    # Unknown / missing values collapse to the generic app source.
    assert _ping_source("anything-else") == "tourist-app"
    assert _ping_source("") == "tourist-app"
    assert _ping_source(None) == "tourist-app"


def test_demo_ping_is_recorded_as_demo(client, db_session):
    """A ping sent in demo mode is persisted with the `demo` source."""
    from app.db.models import LocationPing

    h = _auth(client, email="demomode@example.com")
    r = client.post(
        "/me/pings",
        headers=h,
        json={"location": {"lat": 12.97, "lon": 77.59}, "source": "demo"},
    )
    assert r.status_code == 200

    ping = (
        db_session.query(LocationPing)
        .filter_by(id=r.json()["ping_id"])
        .one()
    )
    assert ping.source == "demo"


# --- Tier 1: route alternatives --------------------------------------------


def test_trip_returns_scored_alternatives(client):
    """Every candidate route comes back scored, with one marked fastest."""
    h = _auth(client, email="alts@example.com")
    r = client.post("/me/trip", headers=h, json={
        "start": {"lat": 12.97, "lon": 77.59},
        "destination": {"lat": 12.95, "lon": 77.60},
    })
    assert r.status_code == 200
    d = r.json()

    assert len(d["alternatives"]) == 2
    assert [a["index"] for a in d["alternatives"]] == [0, 1]
    # Exactly one fastest, one safest, one selected.
    assert sum(a["is_fastest"] for a in d["alternatives"]) == 1
    assert sum(a["is_safest"] for a in d["alternatives"]) == 1
    assert sum(a["is_selected"] for a in d["alternatives"]) == 1
    # The shorter route is the fastest one.
    fastest = next(a for a in d["alternatives"] if a["is_fastest"])
    assert fastest["duration_s"] == 700.0


def test_trip_prefer_fastest_selects_fastest(client):
    """`prefer=fastest` adopts the quickest route even if it scores worse."""
    h = _auth(client, email="fastest@example.com")
    r = client.post("/me/trip", headers=h, json={
        "start": {"lat": 12.97, "lon": 77.59},
        "destination": {"lat": 12.95, "lon": 77.60},
        "prefer": "fastest",
    })
    assert r.status_code == 200
    d = r.json()
    assert d["chosen"] == "fastest"
    assert d["duration_s"] == 700.0
    selected = next(a for a in d["alternatives"] if a["is_selected"])
    assert selected["is_fastest"] is True
    # No trade-off note when the fastest route is the one taken.
    assert d["trade_off"] is None


def test_trip_defaults_to_safest(client):
    """Safety is the default preference, not speed."""
    h = _auth(client, email="safest@example.com")
    r = client.post("/me/trip", headers=h, json={
        "start": {"lat": 12.97, "lon": 77.59},
        "destination": {"lat": 12.95, "lon": 77.60},
    })
    d = r.json()
    assert d["chosen"] == "safest"
    selected = next(a for a in d["alternatives"] if a["is_selected"])
    assert selected["is_safest"] is True


def test_trip_top_level_matches_selected(client):
    """The legacy top-level fields mirror the selected route (back-compat)."""
    h = _auth(client, email="backcompat@example.com")
    r = client.post("/me/trip", headers=h, json={
        "start": {"lat": 12.97, "lon": 77.59},
        "destination": {"lat": 12.95, "lon": 77.60},
    })
    d = r.json()
    selected = next(a for a in d["alternatives"] if a["is_selected"])
    assert d["route"] == selected["route"]
    assert d["distance_m"] == selected["distance_m"]
    assert d["duration_s"] == selected["duration_s"]
    assert d["safety"] == selected["safety"]


# --- Tier 1: advisories -----------------------------------------------------


def test_advisories_empty_without_position(client):
    """A tourist with no pings has nothing to be 'near'."""
    h = _auth(client, email="noadv@example.com")
    r = client.get("/me/advisories", headers=h)
    assert r.status_code == 200
    assert r.json()["advisories"] == []


def test_advisories_are_sanitized(client, db_session):
    """Advisories carry no title, description or source URL."""
    from datetime import UTC, datetime

    from app.db.enums import RiskEventType
    from app.db.models import RiskEvent
    from app.db.spatial import point_to_geom

    h = _auth(client, email="adv@example.com")
    # Give the tourist a position.
    client.post("/me/pings", headers=h, json={"location": {"lat": 12.97, "lon": 77.59}})

    db_session.add(RiskEvent(
        event_type=RiskEventType.CIVIL_UNREST,
        title="Protest turns violent, three injured",
        description="Graphic details that a tourist must never be shown.",
        source="news.example", source_url="https://news.example/story",
        event_time=datetime.now(UTC), confidence=0.8,
        geom=point_to_geom(12.9705, 77.5905),
    ))
    db_session.flush()

    body = client.get("/me/advisories", headers=h).json()
    assert len(body["advisories"]) >= 1
    adv = body["advisories"][0]

    assert adv["event_type"] == "civil_unrest"
    assert "avoiding the area" in adv["advice"]
    # The sensitive fields must not appear anywhere in the payload.
    blob = str(body)
    assert "violent" not in blob
    assert "Graphic details" not in blob
    assert "news.example" not in blob
    # Location is blurred to ~100 m.
    assert adv["location"]["lat"] == round(12.9705, 3)
