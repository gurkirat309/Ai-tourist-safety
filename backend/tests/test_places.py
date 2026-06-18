"""Tests for the place-suggestion endpoint (curated; no network needed)."""

from fastapi.testclient import TestClient

from app.main import app
from app.services.places import curated_places

client = TestClient(app)


def test_curated_places():
    resp = client.get("/places")
    assert resp.status_code == 200
    places = resp.json()["places"]
    assert len(places) == len(curated_places())
    sample = {p["name"] for p in places}
    assert "Cubbon Park" in sample
    assert all({"name", "lat", "lon", "category"} <= set(p) for p in places)


def test_search_requires_min_length():
    # q shorter than 3 chars is rejected by validation.
    assert client.get("/places/search", params={"q": "ab"}).status_code == 422
