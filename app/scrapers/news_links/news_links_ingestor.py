from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from sqlalchemy import text

from app.core.database import engine
from app.scrapers.news_links.economic_times_expert_views_scraper import (
    scrape_economic_times_expert_views,
)
from app.scrapers.news_links.icicidirect_blog_scraper import scrape_icicidirect_blog
from app.scrapers.news_links.moneycontrol_recommendations_scraper import (
    scrape_moneycontrol_recommendations,
)
from app.scrapers.news_links.types import NewsArticleRecord


def run_news_links_ingestion(target_count_per_source: int = 50) -> dict[str, Any]:
    started_at = perf_counter()
    source_functions: list[tuple[str, Any]] = [
        ("icicidirect", scrape_icicidirect_blog),
        ("economictimes", scrape_economic_times_expert_views),
        ("moneycontrol", scrape_moneycontrol_recommendations),
    ]

    source_results: dict[str, Any] = {}
    all_records: list[NewsArticleRecord] = []
    failed_sources = 0

    for source, scraper_fn in source_functions:
        source_started = perf_counter()
        try:
            rows = scraper_fn(target_count=target_count_per_source)
            duration_seconds = round(perf_counter() - source_started, 2)
            source_results[source] = {
                "status": "ok",
                "duration_seconds": duration_seconds,
                "fetched": len(rows),
            }
            all_records.extend(rows)
        except Exception as exc:
            failed_sources += 1
            duration_seconds = round(perf_counter() - source_started, 2)
            source_results[source] = {
                "status": "error",
                "duration_seconds": duration_seconds,
                "detail": str(exc),
            }

    deduplicated = _deduplicate_records(all_records)
    saved = _upsert_records(deduplicated)

    return {
        "status": "ok" if failed_sources == 0 else "partial",
        "duration_seconds": round(perf_counter() - started_at, 2),
        "totals": {
            "fetched": len(all_records),
            "deduplicated": len(deduplicated),
            "saved": saved,
            "failed_sources": failed_sources,
        },
        "sources": source_results,
    }


def _deduplicate_records(rows: list[NewsArticleRecord]) -> list[NewsArticleRecord]:
    deduped: dict[tuple[str, str], NewsArticleRecord] = {}
    now_utc = datetime.now(timezone.utc)
    for row in rows:
        source = (row.get("source") or "").strip().lower()
        source_url = (row.get("source_url") or "").strip()
        headline = (row.get("headline") or "").strip()
        published_at = row.get("published_at") or now_utc
        if not source or not source_url or not headline:
            continue

        deduped[(source, source_url)] = {
            "source": source,
            "source_url": source_url,
            "headline": headline,
            "published_at": published_at,
        }
    return list(deduped.values())


def _upsert_records(rows: list[NewsArticleRecord]) -> int:
    if not rows:
        return 0

    upsert_sql = text(
        """
        INSERT INTO news_articles (
            source,
            source_url,
            headline,
            published_at
        ) VALUES (
            :source,
            :source_url,
            :headline,
            :published_at
        )
        ON CONFLICT (source, source_url)
        DO UPDATE SET
            headline = EXCLUDED.headline,
            published_at = COALESCE(EXCLUDED.published_at, news_articles.published_at)
        """
    )

    with engine.begin() as conn:
        for row in rows:
            conn.execute(upsert_sql, row)

    return len(rows)


if __name__ == "__main__":
    summary = run_news_links_ingestion(target_count_per_source=50)
    print(summary)
