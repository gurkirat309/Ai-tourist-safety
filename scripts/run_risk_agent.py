"""Run the Risk Intelligence agent once and print what it wrote.

Dry-run by default (offline, heuristic extraction over mock items). Use --live
to fetch real RSS sources and call the configured LLM (Groq).

Run:
  uv run python -m scripts.run_risk_agent            # dry-run, mock source
  uv run python -m scripts.run_risk_agent --live     # real RSS + LLM
"""

from __future__ import annotations

import argparse

from app.agents.risk_intelligence import RiskIntelligenceAgent
from app.agents.seen_store import InMemorySeenStore
from app.agents.sources import MockSource, default_bengaluru_sources
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.services.llm import LLMClient

log = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Risk Intelligence agent.")
    parser.add_argument("--live", action="store_true",
                        help="use real RSS sources + the configured LLM")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.live:
            sources = default_bengaluru_sources()
            llm = LLMClient(dry_run=False)
            seen = None  # use Redis-backed default
            print("Mode: LIVE (real RSS + LLM)")
        else:
            sources = [MockSource()]
            llm = LLMClient(dry_run=True)
            seen = InMemorySeenStore()
            print("Mode: DRY-RUN (mock source + heuristic extraction)")

        agent = RiskIntelligenceAgent(db, sources, llm=llm, seen_store=seen)
        result = agent.run_once()

        print(f"\nfetched={result.fetched} created={result.created} "
              f"skipped={result.skipped}")
        for title in result.created_titles:
            print(f"  + {title}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
