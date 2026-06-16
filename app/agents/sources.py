"""Pluggable risk-signal sources for the Risk Intelligence agent.

A source yields `RawItem`s (title/summary/url/published). Sources are pluggable
and mockable: tests use `MockSource`; live runs use `RSSSource` (Google News
queries by default). Keep network access here and nowhere else in the agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class RawItem:
    title: str
    summary: str
    url: str
    published: datetime | None = None
    source_name: str = "unknown"

    def content_for_llm(self) -> str:
        when = self.published.isoformat() if self.published else "unknown"
        return f"Title: {self.title}\nPublished: {when}\nSummary: {self.summary}"


@runtime_checkable
class RiskSource(Protocol):
    name: str

    def fetch(self) -> list[RawItem]:
        ...


class MockSource:
    """Canned items for tests / dry-run — no network."""

    name = "mock"

    def __init__(self, items: list[RawItem] | None = None) -> None:
        self._items = items if items is not None else _DEFAULT_MOCK_ITEMS

    def fetch(self) -> list[RawItem]:
        return list(self._items)


_DEFAULT_MOCK_ITEMS = [
    RawItem(
        title="Chain snatching reported near Majestic bus stand",
        summary=(
            "Police report a rise in chain-snatching incidents around the "
            "Kempegowda (Majestic) bus terminus late at night."
        ),
        url="https://example.test/news/majestic-snatching",
        published=datetime(2026, 6, 16, 21, 0, tzinfo=UTC),
        source_name="mock-news",
    ),
    RawItem(
        title="Heavy waterlogging in Koramangala after rain",
        summary=(
            "Severe waterlogging reported in Koramangala; commuters advised to "
            "avoid underpasses."
        ),
        url="https://example.test/news/koramangala-flood",
        published=datetime(2026, 6, 16, 18, 30, tzinfo=UTC),
        source_name="mock-news",
    ),
]


class RSSSource:
    """Fetch + parse an RSS/Atom feed. Used for live runs."""

    def __init__(self, url: str, name: str = "rss", timeout_s: float = 10.0) -> None:
        self.url = url
        self.name = name
        self.timeout_s = timeout_s

    def fetch(self) -> list[RawItem]:
        import feedparser
        import httpx

        try:
            # Fetch bytes with httpx (honours system certs better than urllib).
            resp = httpx.get(self.url, timeout=self.timeout_s, follow_redirects=True)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
        except Exception as exc:  # noqa: BLE001
            log.warning("RSS fetch failed for %s: %s", self.url, exc)
            return []

        items: list[RawItem] = []
        for entry in parsed.entries:
            published = None
            if getattr(entry, "published_parsed", None):
                import time as _time

                published = datetime.fromtimestamp(
                    _time.mktime(entry.published_parsed), tz=UTC
                )
            items.append(
                RawItem(
                    title=getattr(entry, "title", ""),
                    summary=getattr(entry, "summary", ""),
                    url=getattr(entry, "link", ""),
                    published=published,
                    source_name=self.name,
                )
            )
        return items


def default_bengaluru_sources() -> list[RiskSource]:
    """Google News RSS queries for Bengaluru safety-relevant signals."""
    base = "https://news.google.com/rss/search?q="
    queries = {
        "bengaluru-crime": "Bengaluru+crime+when:2d",
        "bengaluru-protest": "Bengaluru+protest+OR+bandh+when:2d",
        "bengaluru-weather": "Bengaluru+flooding+OR+waterlogging+when:2d",
    }
    return [RSSSource(f"{base}{q}&hl=en-IN&gl=IN&ceid=IN:en", name=name)
            for name, q in queries.items()]
