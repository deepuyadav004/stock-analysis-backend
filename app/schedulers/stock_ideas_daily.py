from __future__ import annotations

from datetime import date
from time import perf_counter
from typing import Any

from app.scrapers.stock_ideas.kotak_scraper import KotakStockIdeasScraper
from app.scrapers.stock_ideas.lemonn_scraper import LemonnStockIdeasScraper
from app.scrapers.stock_ideas.moneycontrol_scraper import MoneycontrolStockIdeasScraper


def run_daily_stock_ideas_ingestion() -> dict[str, Any]:
    """Run all stock-ideas scrapers once and return a compact execution summary."""
    started_at = perf_counter()
    print(f"\n--- Starting Daily Stock Ideas Ingestion for {date.today()} ---", flush=True)

    sources: list[tuple[str, Any]] = [
        ("moneycontrol", MoneycontrolStockIdeasScraper),
        ("kotakneo", KotakStockIdeasScraper),
        ("lemonn", LemonnStockIdeasScraper),
    ]

    source_results: dict[str, Any] = {}
    totals = {"parsed": 0, "deduplicated": 0, "saved": 0, "failed_sources": 0}

    for source_name, scraper_cls in sources:
        source_started = perf_counter()
        print(f"\n[StockIdeas] Running {source_name} scraper...", flush=True)
        try:
            scraper = scraper_cls()
            summary = scraper.run()
            duration_seconds = round(perf_counter() - source_started, 2)

            parsed = int(summary.get("parsed", 0))
            dedup = int(summary.get("deduplicated", 0))
            saved = int(summary.get("saved", 0))

            totals["parsed"] += parsed
            totals["deduplicated"] += dedup
            totals["saved"] += saved

            source_results[source_name] = {
                "status": "ok",
                "duration_seconds": duration_seconds,
                "parsed": parsed,
                "deduplicated": dedup,
                "saved": saved,
            }
            print(
                f"[StockIdeas] {source_name}: parsed={parsed}, deduplicated={dedup}, "
                f"saved={saved}, duration={duration_seconds}s",
                flush=True,
            )
        except Exception as exc:
            totals["failed_sources"] += 1
            duration_seconds = round(perf_counter() - source_started, 2)
            source_results[source_name] = {
                "status": "error",
                "duration_seconds": duration_seconds,
                "detail": str(exc),
            }
            print(
                f"[StockIdeas] {source_name}: ERROR after {duration_seconds}s -> {exc}",
                flush=True,
            )

    overall_duration = round(perf_counter() - started_at, 2)
    result = {
        "status": "ok" if totals["failed_sources"] == 0 else "partial",
        "duration_seconds": overall_duration,
        "totals": totals,
        "sources": source_results,
    }

    print(
        "\n--- Stock Ideas Ingestion Complete: "
        f"status={result['status']}, parsed={totals['parsed']}, "
        f"deduplicated={totals['deduplicated']}, saved={totals['saved']}, "
        f"failed_sources={totals['failed_sources']} ---",
        flush=True,
    )
    return result


if __name__ == "__main__":
    run_daily_stock_ideas_ingestion()
