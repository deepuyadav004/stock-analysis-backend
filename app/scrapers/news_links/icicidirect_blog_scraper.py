from __future__ import annotations

from bs4 import BeautifulSoup

from app.scrapers.news_links.types import NewsArticleRecord
from app.scrapers.news_links.utils import fetch_html, normalize_url, parse_iso_or_common_datetime

SOURCE = "icicidirect"
START_URL = "https://www.icicidirect.com/research/equity/blog"


def scrape_icicidirect_blog(target_count: int = 50, max_pages: int = 20) -> list[NewsArticleRecord]:
    records: list[NewsArticleRecord] = []
    seen_urls: set[str] = set()

    for page in range(1, max_pages + 1):
        if len(records) >= target_count:
            break

        page_url = _page_url(page)
        html = fetch_html(page_url)
        soup = BeautifulSoup(html, "html.parser")

        for anchor in soup.select("a[href]"):
            href = (anchor.get("href") or "").strip()
            if not href:
                continue

            article_url = normalize_url(href, page_url)
            if article_url.rstrip("/") == START_URL.rstrip("/"):
                continue
            if "/research/equity/blog/" not in article_url:
                continue
            if "?page=" in article_url or "?pg=" in article_url:
                continue
            if article_url in seen_urls:
                continue

            title = _extract_headline(anchor)
            if not title:
                continue

            seen_urls.add(article_url)
            records.append(
                {
                    "source": SOURCE,
                    "source_url": article_url,
                    "headline": title,
                    "published_at": parse_iso_or_common_datetime(_extract_datetime(anchor)),
                }
            )

            if len(records) >= target_count:
                break

    return records


def _page_url(page: int) -> str:
    if page <= 1:
        return START_URL
    return f"{START_URL}?page={page}"


def _extract_headline(anchor) -> str:
    candidates = [
        (anchor.get("title") or "").strip(),
        (anchor.get("aria-label") or "").strip(),
        (anchor.get("data-title") or "").strip(),
        anchor.get_text(" ", strip=True),
    ]
    for candidate in candidates:
        text = " ".join(candidate.split())
        if text and text.lower() not in {"read more", "more", "next"}:
            return text
    return ""


def _extract_datetime(anchor) -> str | None:
    parent = anchor.find_parent()
    time_node = parent.select_one("time") if parent else None
    if not time_node:
        time_node = anchor.select_one("time")
    if not time_node:
        return None
    return (time_node.get("datetime") or "").strip() or time_node.get_text(" ", strip=True)
