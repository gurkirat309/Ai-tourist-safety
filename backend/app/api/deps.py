"""Shared FastAPI dependencies.

`get_db` yields a request-scoped session; `get_llm` yields the provider-agnostic
LLM client (respecting env / dry-run). Both are overridable in tests.
"""

from __future__ import annotations

import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.enums import UserRole
from app.db.models import User
from app.db.session import get_db  # re-exported for routers
from app.services.llm import LLMClient
from app.services.security import decode_token

__all__ = [
    "get_db",
    "get_llm",
    "get_realtime_llm",
    "get_current_user",
    "require_role",
]

_bearer = HTTPBearer(auto_error=True)


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


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the Bearer token."""
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = decode_token(creds.credentials)
        user_id = uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise cred_exc from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise cred_exc
    return user


def require_role(*roles: UserRole):
    """Dependency factory: allow only the given role(s)."""

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _dep
