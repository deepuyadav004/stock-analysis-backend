from __future__ import annotations

from datetime import datetime
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
}


def fetch_html(url: str, timeout_seconds: float = 20.0) -> str:
    with httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True, timeout=timeout_seconds) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def normalize_url(url: str, base_url: str) -> str:
    absolute = urljoin(base_url, url.strip())
    parsed = urlparse(absolute)
    cleaned = parsed._replace(query=parsed.query, fragment="")
    return urlunparse(cleaned)


def parse_iso_or_common_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None

    candidates = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%d %b %Y, %I:%M %p IST",
        "%d %b %Y %I:%M %p",
        "%d %B %Y, %I:%M %p IST",
        "%d %B %Y %I:%M %p",
        "%d %b %Y",
        "%d %B %Y",
        "%Y-%m-%d",
    ]

    normalized = raw.replace("Z", "+00:00")

    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass

    for fmt in candidates:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def find_next_page_url(soup: BeautifulSoup, current_url: str) -> str | None:
    selectors = [
        "a[rel='next']",
        "a.next",
        ".pagination a.next",
        ".paging a.next",
        ".page-nav a.next",
    ]
    for selector in selectors:
        anchor = soup.select_one(selector)
        if not anchor:
            continue
        href = (anchor.get("href") or "").strip()
        if href:
            return normalize_url(href, current_url)

    for anchor in soup.select("a"):
        label = anchor.get_text(" ", strip=True).lower()
        if label in {"next", "next >", ">", "older", "more"}:
            href = (anchor.get("href") or "").strip()
            if href:
                return normalize_url(href, current_url)

    return None
