"""M1 model tests against a real Postgres+PostGIS (transaction-rolled-back)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.enums import RiskCategory, RiskEventType
from app.db.models import LocationPing, RiskEvent, Tourist, Zone
from app.db.spatial import (
    geom_to_latlon,
    point_to_geom,
    polygon_to_geom,
)


def test_tourist_ping_roundtrip(db_session):
    t = Tourist(display_name="Test Tourist", consent_given=True)
    db_session.add(t)
    db_session.flush()

    lat, lon = 15.5430, 73.7550
    ping = LocationPing(
        tourist_id=t.id,
        geom=point_to_geom(lat, lon),
        recorded_at=datetime.now(UTC),
        source="test",
    )
    db_session.add(ping)
    db_session.flush()

    fetched = db_session.get(LocationPing, ping.id)
    out_lat, out_lon = geom_to_latlon(fetched.geom)
    assert out_lat == pytest.approx(lat, abs=1e-6)
    assert out_lon == pytest.approx(lon, abs=1e-6)
    assert fetched.tourist.id == t.id


def test_zone_contains_point_via_postgis(db_session):
    # Square around (lon=73.75, lat=15.54), ~0.01 deg half-size.
    ring = [
        (73.74, 15.53),
        (73.76, 15.53),
        (73.76, 15.55),
        (73.74, 15.55),
        (73.74, 15.53),
    ]
    zone = Zone(
        name="Test Zone",
        risk_category=RiskCategory.MODERATE,
        geom=polygon_to_geom(ring),
    )
    db_session.add(zone)
    db_session.flush()

    inside = point_to_geom(15.54, 73.75)
    outside = point_to_geom(15.60, 73.90)

    # Scope to this zone so seeded zones don't interfere.
    hit = db_session.execute(
        select(func.ST_Contains(Zone.geom, inside)).where(Zone.id == zone.id)
    ).scalar_one()
    miss = db_session.execute(
        select(func.ST_Contains(Zone.geom, outside)).where(Zone.id == zone.id)
    ).scalar_one()

    assert hit is True
    assert miss is False


def test_risk_event_confidence_constraint(db_session):
    bad = RiskEvent(
        event_type=RiskEventType.ADVISORY,
        title="Invalid confidence",
        source="test",
        event_time=datetime.now(UTC),
        confidence=1.5,  # violates ck_confidence_unit
    )
    # Use a savepoint so the constraint violation doesn't poison the outer
    # test transaction.
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(bad)
            db_session.flush()


def test_risk_event_embedding_roundtrip(db_session):
    vec = [0.1] * 384
    ev = RiskEvent(
        event_type=RiskEventType.CRIME,
        title="With embedding",
        source="test",
        event_time=datetime.now(UTC) - timedelta(hours=1),
        confidence=0.5,
        embedding=vec,
    )
    db_session.add(ev)
    db_session.flush()

    fetched = db_session.get(RiskEvent, ev.id)
    assert len(fetched.embedding) == 384
    assert fetched.embedding[0] == pytest.approx(0.1)
