"""
base_scraper.py
---------------
Abstract base class for all news source scrapers.
Each concrete scraper must implement `fetch_headlines()` which returns
a list of raw article dicts:
    {
        "title": str,       # headline
        "summary": str,     # short description / first paragraph (may be empty)
        "source": str,      # human-readable source name e.g. "Economic Times"
        "url": str,         # canonical article URL
    }
Articles are never stored to disk or DB — they are ephemeral, held in
memory only long enough to be scored by the sentiment service.
"""

import random
import time
from abc import ABC, abstractmethod

import httpx


# Rotate user agents to reduce scraper detection.
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


def _random_user_agent() -> str:
    return random.choice(_USER_AGENTS)


class Article:
    """Lightweight container for a single scraped article."""

    __slots__ = ("title", "summary", "source", "url")

    def __init__(self, title: str, summary: str, source: str, url: str) -> None:
        self.title = title.strip()
        self.summary = summary.strip()
        self.source = source
        self.url = url.strip()

    @property
    def text(self) -> str:
        """Combined text used for sentiment scoring (title + summary)."""
        parts = [self.title]
        if self.summary:
            parts.append(self.summary)
        return " ".join(parts)

    def __repr__(self) -> str:
        preview = self.title[:60] + "..." if len(self.title) > 60 else self.title
        return f"Article(source={self.source!r}, title={preview!r})"


class BaseScraper(ABC):
    """
    Abstract base for a single news source scraper.

    Subclasses override:
        SOURCE_NAME : str  — display name of the source
        fetch_headlines()  — returns list[Article]
    """

    SOURCE_NAME: str = "Unknown"
    # Minimum seconds to sleep between HTTP requests within one scraper.
    REQUEST_DELAY: float = 2.0

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout
        self._client = httpx.Client(
            headers={
                "User-Agent": _random_user_agent(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=self._timeout,
            follow_redirects=True,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape(self) -> list[Article]:
        """
        Entry point. Returns a (possibly empty) list of Article objects.
        Logs progress and swallows top-level errors so one broken source
        does not crash the whole pipeline.
        """
        print(f"[{self.SOURCE_NAME}] Starting scrape...", flush=True)
        try:
            articles = self.fetch_headlines()
            print(
                f"[{self.SOURCE_NAME}] Fetched {len(articles)} articles.",
                flush=True,
            )
            return articles
        except Exception as exc:
            print(
                f"[{self.SOURCE_NAME}] FAILED — {type(exc).__name__}: {exc}",
                flush=True,
            )
            return []

    # ------------------------------------------------------------------
    # Helpers for subclasses
    # ------------------------------------------------------------------

    def _get(self, url: str, **kwargs) -> httpx.Response:
        """
        GET a URL with a fresh random user agent and polite delay.
        Raises httpx.HTTPStatusError on 4xx/5xx.
        """
        # Refresh user agent on each request.
        self._client.headers["User-Agent"] = _random_user_agent()
        time.sleep(self.REQUEST_DELAY)
        response = self._client.get(url, **kwargs)
        response.raise_for_status()
        return response

    def close(self) -> None:
        """Release the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> "BaseScraper":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Must implement
    # ------------------------------------------------------------------

    @abstractmethod
    def fetch_headlines(self) -> list[Article]:
        """
        Scrape the source and return a list of Article objects.
        Should NOT raise — handle errors internally or let `scrape()` catch them.
        """
