"""Tests for the DPDP retention/expiry helpers."""

from datetime import UTC, datetime, timedelta

from app.db.models import LocationPing, Tourist
from app.db.spatial import point_to_geom
from app.services.retention import (
    minimize_expired_tourists,
    purge_expired_pings,
)


def test_purge_expired_pings(db_session):
    now = datetime.now(UTC)
    t = Tourist(display_name="Retention Test", consent_given=True)
    db_session.add(t)
    db_session.flush()

    old = LocationPing(
        tourist_id=t.id,
        geom=point_to_geom(15.5, 73.8),
        recorded_at=now - timedelta(days=60),  # well past default 30d window
    )
    recent = LocationPing(
        tourist_id=t.id,
        geom=point_to_geom(15.5, 73.8),
        recorded_at=now - timedelta(days=1),
    )
    db_session.add_all([old, recent])
    db_session.flush()

    deleted = purge_expired_pings(db_session, now=now)
    db_session.flush()

    assert deleted == 1
    remaining = db_session.get(LocationPing, recent.id)
    assert remaining is not None
    assert db_session.get(LocationPing, old.id) is None


def test_minimize_expired_tourists(db_session):
    now = datetime.now(UTC)
    expired = Tourist(
        display_name="Expired Person",
        nationality="IN",
        emergency_contact="+91-123",
        consent_given=True,
        retention_until=now - timedelta(days=1),
        is_active=True,
    )
    active = Tourist(
        display_name="Active Person",
        nationality="GB",
        consent_given=True,
        retention_until=now + timedelta(days=10),
        is_active=True,
    )
    db_session.add_all([expired, active])
    db_session.flush()

    count = minimize_expired_tourists(db_session, now=now)
    db_session.flush()
    db_session.refresh(expired)
    db_session.refresh(active)

    assert count == 1
    assert expired.display_name is None
    assert expired.nationality is None
    assert expired.is_active is False
    # Active tourist untouched.
    assert active.display_name == "Active Person"
    assert active.is_active is True
