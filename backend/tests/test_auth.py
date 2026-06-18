"""Phase 1 auth tests (signup / login / me / roles)."""

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


def _signup(client, email="tourist1@example.com", pw="hunter2"):
    return client.post("/auth/signup", json={
        "email": email, "password": pw, "display_name": "Test Tourist",
        "consent_given": True,
    })


def test_signup_returns_token_and_tourist(client):
    r = _signup(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["role"] == "tourist"
    assert body["tourist_id"] is not None
    assert body["access_token"]


def test_signup_duplicate_email_conflicts(client):
    _signup(client, email="dup@example.com")
    r = _signup(client, email="dup@example.com")
    assert r.status_code == 409


def test_login_success_and_wrong_password(client):
    _signup(client, email="login@example.com", pw="rightpass")
    ok = client.post("/auth/login", json={"email": "login@example.com", "password": "rightpass"})
    assert ok.status_code == 200
    assert ok.json()["role"] == "tourist"

    bad = client.post("/auth/login", json={"email": "login@example.com", "password": "nope"})
    assert bad.status_code == 401


def test_me_requires_and_returns_user(client):
    assert client.get("/auth/me").status_code in (401, 403)  # no token

    token = _signup(client, email="me@example.com").json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "me@example.com"
    assert r.json()["role"] == "tourist"


def test_police_login(client, db_session):
    db_session.add(User(
        email="cop@example.com",
        hashed_password=hash_password("copsecret"),
        role=UserRole.POLICE,
    ))
    db_session.flush()
    r = client.post("/auth/login", json={"email": "cop@example.com", "password": "copsecret"})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "police"
    assert body["tourist_id"] is None


def test_invalid_token_rejected(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401
