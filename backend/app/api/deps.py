"""Shared FastAPI dependencies.

`get_db` yields a request-scoped session; `get_llm` yields the provider-agnostic
LLM client (respecting env / dry-run). Both are overridable in tests.
"""

from __future__ import annotations

from app.db.session import get_db  # re-exported for routers
from app.services.llm import LLMClient

__all__ = ["get_db", "get_llm", "get_realtime_llm"]


def get_llm() -> LLMClient:
    """LLM client honoring env settings (dry-run when no key / flag set).

    For non-real-time / scheduled use (e.g. offline enrichment).
    """
    return LLMClient()


def get_realtime_llm() -> LLMClient:
    """LLM client for the synchronous request path — always heuristic/dry-run.

    Keeps ingest/panic fast and deterministic (no blocking network call). The
    triage escalation is a deterministic safety floor regardless; the LLM only
    adds prose, which we defer off the hot path. Live LLM is reserved for the
    scheduled Risk Intelligence agent (M4).
    """
    return LLMClient(dry_run=True)
