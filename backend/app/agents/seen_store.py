"""Dedupe store: tracks already-processed source items.

Avoids re-processing unchanged sources and re-calling the LLM (important for
Groq free-tier limits). Uses Redis when available, with an in-memory fallback
for tests / offline runs.
"""

from __future__ import annotations

import hashlib
from typing import Protocol

from app.core.logging import get_logger

log = get_logger(__name__)

_PREFIX = "riskintel:seen:"
_TTL_S = 7 * 24 * 3600  # a week


def item_hash(url: str, title: str) -> str:
    return hashlib.sha256(f"{url}|{title}".encode()).hexdigest()[:32]


class SeenStore(Protocol):
    def is_seen(self, key: str) -> bool: ...
    def mark_seen(self, key: str) -> None: ...


class InMemorySeenStore:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    def is_seen(self, key: str) -> bool:
        return key in self._seen

    def mark_seen(self, key: str) -> None:
        self._seen.add(key)


class RedisSeenStore:
    def __init__(self, client, ttl_s: int = _TTL_S) -> None:
        self._r = client
        self._ttl = ttl_s

    def is_seen(self, key: str) -> bool:
        return bool(self._r.exists(_PREFIX + key))

    def mark_seen(self, key: str) -> None:
        self._r.set(_PREFIX + key, "1", ex=self._ttl)


def default_seen_store() -> SeenStore:
    """Redis-backed store if reachable, else in-memory."""
    try:
        from app.services.redis_client import get_redis

        client = get_redis()
        client.ping()
        return RedisSeenStore(client)
    except Exception as exc:  # noqa: BLE001
        log.info("Redis unavailable (%s); using in-memory seen-store", exc)
        return InMemorySeenStore()
