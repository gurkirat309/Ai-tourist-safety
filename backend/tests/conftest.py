"""Shared pytest fixtures.

DB tests use a real Postgres+PostGIS (per the project decision). Each test runs
inside a transaction that is rolled back, so tests are isolated and leave no
residue. If the database is unreachable, DB tests are skipped (not failed) so the
infra-free unit tests still run.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import engine


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


DB_AVAILABLE = _db_available()


@pytest.fixture
def db_session():
    if not DB_AVAILABLE:
        pytest.skip("Postgres not reachable; start it with `make infra-up`.")

    connection = engine.connect()
    trans = connection.begin()
    # `create_savepoint` makes session.commit() release a SAVEPOINT instead of
    # committing the outer transaction, so code under test that commits (e.g.
    # the agent) stays isolated and is fully rolled back at teardown.
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()
