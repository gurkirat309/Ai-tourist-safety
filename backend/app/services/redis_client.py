"""Redis client factory.

Used for the live-location cache and pub/sub bus (from M2/M6 onward). In M0 it
backs the health check.
"""

import redis

from app.core.config import get_settings

settings = get_settings()

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return a process-wide Redis client (lazy singleton)."""
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _client
