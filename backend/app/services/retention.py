"""DPDP data-retention / expiry helpers.

Location data is sensitive personal data. These helpers implement the
data-minimization path: raw location pings are purged once they exceed the
configured retention window, and tourists past their `retention_until` have
their PII minimized.

This is a deliberately small, deterministic building block; a scheduled job
(APScheduler, M6) will call `purge_expired`.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import LocationPing, Tourist

log = get_logger(__name__)


@dataclass
class RetentionResult:
    pings_deleted: int
    tourists_minimized: int


def purge_expired_pings(db: Session, *, now: datetime | None = None) -> int:
    """Delete location pings older than the configured retention window."""
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=get_settings().location_retention_days)

    result = db.execute(delete(LocationPing).where(LocationPing.recorded_at < cutoff))
    deleted = result.rowcount or 0
    if deleted:
        log.info("Retention: purged %d expired location pings", deleted)
    return deleted


def minimize_expired_tourists(db: Session, *, now: datetime | None = None) -> int:
    """Strip PII from tourists whose retention window has passed.

    We keep the row (for incident lineage) but clear identifying fields and
    deactivate the record.
    """
    now = now or datetime.now(UTC)

    expired_ids = db.execute(
        select(Tourist.id).where(
            Tourist.retention_until.is_not(None),
            Tourist.retention_until < now,
            Tourist.is_active.is_(True),
        )
    ).scalars().all()

    if not expired_ids:
        return 0

    db.execute(
        update(Tourist)
        .where(Tourist.id.in_(expired_ids))
        .values(
            display_name=None,
            nationality=None,
            emergency_contact=None,
            external_ref=None,
            planned_route=None,
            is_active=False,
        )
    )
    log.info("Retention: minimized PII for %d expired tourists", len(expired_ids))
    return len(expired_ids)


def purge_expired(db: Session, *, now: datetime | None = None) -> RetentionResult:
    """Run the full retention pass and commit."""
    now = now or datetime.now(UTC)
    pings = purge_expired_pings(db, now=now)
    tourists = minimize_expired_tourists(db, now=now)
    db.commit()
    return RetentionResult(pings_deleted=pings, tourists_minimized=tourists)
