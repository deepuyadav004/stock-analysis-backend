from __future__ import annotations

from datetime import date
from typing import Any

from app.scrapers.news_links.news_links_ingestor import run_news_links_ingestion


def run_daily_news_links_ingestion(target_count_per_source: int = 50) -> dict[str, Any]:
    print(
        f"\n--- Starting Daily News Links Ingestion for {date.today()} ---",
        flush=True,
    )
    summary = run_news_links_ingestion(target_count_per_source=target_count_per_source)
    print("--- Daily News Links Ingestion Complete ---", flush=True)
    return summary


if __name__ == "__main__":
    result = run_daily_news_links_ingestion(target_count_per_source=50)
    print(result)
