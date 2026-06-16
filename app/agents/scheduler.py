"""APScheduler wiring for periodic Risk Intelligence runs.

Throttled to respect Groq free-tier limits. The agent is also runnable one-shot
via `scripts.run_risk_agent`; this module is for long-running scheduled use
(e.g. started by a worker process, not the API request path).
"""

from __future__ import annotations

from app.agents.risk_intelligence import RiskIntelligenceAgent
from app.agents.sources import RiskSource, default_bengaluru_sources
from app.core.logging import get_logger
from app.db.session import SessionLocal

log = get_logger(__name__)

DEFAULT_INTERVAL_MIN = 30  # throttle scheduled runs


def run_agent_once(sources: list[RiskSource] | None = None) -> None:
    """Single scheduled run with its own DB session."""
    db = SessionLocal()
    try:
        agent = RiskIntelligenceAgent(db, sources or default_bengaluru_sources())
        agent.run_once()
    finally:
        db.close()


def build_scheduler(interval_min: int = DEFAULT_INTERVAL_MIN):
    """Create (but do not start) a BackgroundScheduler running the agent."""
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_agent_once,
        "interval",
        minutes=interval_min,
        id="risk_intelligence",
        max_instances=1,
        coalesce=True,
    )
    log.info("Risk Intelligence scheduler built (every %d min)", interval_min)
    return scheduler
