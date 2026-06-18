"""Authentication endpoints: signup (tourist), login, me.

Tourists self-register here (creating a User + a Tourist profile). Police
accounts are seeded (see scripts.seed) and only log in.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.db.enums import UserRole
from app.db.models import Tourist, User
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserOut
from app.services.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user: User) -> TokenResponse:
    token = create_access_token(subject=str(user.id), role=user.role.value)
    return TokenResponse(
        access_token=token,
        role=user.role,
        tourist_id=user.tourist_id,
        email=user.email,
    )


@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Register a tourist account + profile and return a token."""
    email = payload.email.strip().lower()
    exists = db.execute(
        select(User).where(func.lower(User.email) == email)
    ).scalars().first()
    if exists:
        raise HTTPException(status_code=409, detail="Email already registered")

    now = datetime.now(UTC)
    retention_days = get_settings().location_retention_days
    tourist = Tourist(
        display_name=payload.display_name,
        nationality=payload.nationality,
        emergency_contact=payload.emergency_contact,
        consent_given=payload.consent_given,
        consent_purpose=payload.consent_purpose,
        consent_timestamp=now if payload.consent_given else None,
        retention_until=now + timedelta(days=retention_days)
        if payload.consent_given
        else None,
        is_active=True,
    )
    db.add(tourist)
    db.flush()

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        role=UserRole.TOURIST,
        tourist_id=tourist.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = payload.email.strip().lower()
    user = db.execute(
        select(User).where(func.lower(User.email) == email)
    ).scalars().first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
