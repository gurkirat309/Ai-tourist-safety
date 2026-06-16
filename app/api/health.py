"""Health endpoints.

`/health` is a liveness probe (always 200 if the app is up).
`/health/ready` is a readiness probe that checks Postgres and Redis.
"""

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import engine
from app.services.redis_client import get_redis

router = APIRouter(tags=["health"])
log = get_logger(__name__)


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {"status": "ok", "app": settings.app_name, "env": settings.env}


@router.get("/health/ready")
def readiness() -> dict:
    checks: dict[str, str] = {}

    # Postgres
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:  # noqa: BLE001
        log.warning("Postgres readiness check failed: %s", exc)
        checks["postgres"] = "error"

    # Redis
    try:
        get_redis().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        log.warning("Redis readiness check failed: %s", exc)
        checks["redis"] = "error"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}
