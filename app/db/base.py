"""SQLAlchemy declarative base and shared column helpers.

All models inherit from `Base`. Importing this module (and `app.db.models`)
registers every table on `Base.metadata`, which Alembic autogenerate uses.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def uuid_pk() -> Mapped[uuid.UUID]:
    """A UUID primary key column (server-side random default)."""
    return mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """Adds created_at / updated_at audit columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
