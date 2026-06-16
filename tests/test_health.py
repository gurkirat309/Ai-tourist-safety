"""M0 smoke tests for the health endpoints.

The liveness probe must work with no infra. The readiness probe is tested with
Postgres/Redis mocked so the test suite needs no running services.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_liveness():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "app" in body


@patch("app.api.health.get_redis")
@patch("app.api.health.engine")
def test_readiness_all_ok(mock_engine, mock_get_redis):
    # Postgres mock: context-managed connection that executes SELECT 1
    conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = conn
    # Redis mock: ping returns True
    mock_get_redis.return_value.ping.return_value = True

    resp = client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"postgres": "ok", "redis": "ok"}


@patch("app.api.health.get_redis")
@patch("app.api.health.engine")
def test_readiness_degraded_when_redis_down(mock_engine, mock_get_redis):
    conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = conn
    mock_get_redis.return_value.ping.side_effect = ConnectionError("nope")

    resp = client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["postgres"] == "ok"
    assert body["checks"]["redis"] == "error"
