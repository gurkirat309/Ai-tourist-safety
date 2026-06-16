"""M4 tests for the Risk Intelligence agent (dry-run; no network / no key)."""

from datetime import UTC, datetime

from app.agents.risk_intelligence import RiskIntelligenceAgent
from app.agents.seen_store import InMemorySeenStore, item_hash
from app.agents.sources import MockSource, RawItem
from app.db.enums import RiskEventType
from app.db.models import RiskEvent
from app.services.embeddings import embed
from app.services.llm import LLMClient

# --- embeddings (no DB) ---
def test_embedding_dim_and_determinism():
    a = embed("chain snatching near Majestic")
    b = embed("chain snatching near Majestic")
    assert len(a) == 384
    assert a == b  # deterministic


def test_seen_store_dedup():
    s = InMemorySeenStore()
    k = item_hash("http://x", "title")
    assert not s.is_seen(k)
    s.mark_seen(k)
    assert s.is_seen(k)


# --- LLM wrapper dry-run (no DB) ---
def test_llm_dry_run_returns_canned():
    llm = LLMClient(dry_run=True, dry_run_response={"events": [{"title": "x"}]})
    out = llm.extract_json("sys", "user")
    assert out == {"events": [{"title": "x"}]}


# --- agent end-to-end against DB (dry-run heuristic extraction) ---
def _clear_source(db, source="mock-news"):
    """Remove any pre-existing rows for this source within the test txn so the
    test is independent of dev-DB state (rolled back at teardown)."""
    db.query(RiskEvent).filter(RiskEvent.source == source).delete()
    db.flush()


def _agent(db):
    return RiskIntelligenceAgent(
        db,
        [MockSource()],
        llm=LLMClient(dry_run=True),
        seen_store=InMemorySeenStore(),
    )


def test_agent_creates_grounded_geotagged_events(db_session):
    _clear_source(db_session)
    result = _agent(db_session).run_once()
    assert result.created == 2

    events = db_session.query(RiskEvent).filter(RiskEvent.source == "mock-news").all()
    assert len(events) == 2
    for ev in events:
        # Grounding present.
        assert ev.source and ev.event_time and 0.0 <= ev.confidence <= 1.0
        assert ev.embedding is not None and len(ev.embedding) == 384

    by_type = {e.event_type for e in events}
    assert RiskEventType.CRIME in by_type  # "chain snatching"
    assert RiskEventType.NATURAL_HAZARD in by_type  # "waterlogging"

    # Geo-tagged to the matching zones.
    titles_to_zone = {e.title: e.zone_id for e in events}
    assert all(z is not None for z in titles_to_zone.values())


def test_agent_dedup_skips_second_run(db_session):
    _clear_source(db_session)
    agent1 = _agent(db_session)
    first = agent1.run_once()
    assert first.created == 2

    # New agent (fresh in-memory seen-store) — dedup must come from the DB
    # source_url check.
    second = _agent(db_session).run_once()
    assert second.created == 0
    assert second.skipped == 2


def test_agent_custom_item_event_type(db_session):
    item = RawItem(
        title="Protest blocks road in MG Road area",
        summary="A large protest disrupts traffic near MG Road.",
        url="https://example.test/protest-mg",
        published=datetime(2026, 6, 16, 12, tzinfo=UTC),
        source_name="mock-news",
    )
    agent = RiskIntelligenceAgent(
        db_session, [MockSource([item])],
        llm=LLMClient(dry_run=True), seen_store=InMemorySeenStore(),
    )
    _clear_source(db_session)
    agent.run_once()
    ev = db_session.query(RiskEvent).filter(
        RiskEvent.source_url == "https://example.test/protest-mg"
    ).one()
    assert ev.event_type == RiskEventType.CIVIL_UNREST
    assert ev.zone_id is not None  # matched "MG Road"
