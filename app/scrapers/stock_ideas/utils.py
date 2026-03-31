from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from app.core.database import engine
from app.scrapers.stock_ideas.types import StockIdeaRecord


def deduplicate_recommendations(rows: list[StockIdeaRecord]) -> list[StockIdeaRecord]:
    deduped: dict[tuple[str, str, date | None], StockIdeaRecord] = {}
    for row in rows:
        ticker = row.get("ticker", "").strip().upper()
        source = row.get("source", "").strip().lower()
        recommendation_date = row.get("recommendation_date")
        if not ticker or not source:
            continue

        normalized_row: StockIdeaRecord = {
            "ticker": ticker,
            "company_name": row.get("company_name", "").strip() or ticker,
            "call_type": row.get("call_type"),
            "target_price": row.get("target_price"),
            "recommendation_date": recommendation_date,
            "source": source,
            "brief_rationale": row.get("brief_rationale"),
        }
        deduped[(ticker, source, recommendation_date)] = normalized_row
    return list(deduped.values())


def save_recommendations(rows: list[StockIdeaRecord]) -> int:
    if not rows:
        return 0

    upsert_sql = text(
        """
        UPDATE stock_ideas_recommendations
        SET
            company_name = :company_name,
            call_type = :call_type,
            target_price = :target_price,
            brief_rationale = :brief_rationale,
            created_at = COALESCE(created_at, NOW())
        WHERE
            ticker = :ticker
            AND source = :source
            AND recommendation_date IS NOT DISTINCT FROM :recommendation_date
        """
    )

    insert_sql = text(
        """
        INSERT INTO stock_ideas_recommendations (
            ticker,
            company_name,
            call_type,
            target_price,
            recommendation_date,
            source,
            brief_rationale,
            created_at
        ) VALUES (
            :ticker,
            :company_name,
            :call_type,
            :target_price,
            :recommendation_date,
            :source,
            :brief_rationale,
            NOW()
        )
        """
    )

    saved = 0
    with engine.begin() as conn:
        for row in rows:
            params: dict[str, Any] = {
                "ticker": row["ticker"],
                "company_name": row["company_name"],
                "call_type": row.get("call_type"),
                "target_price": _to_decimal_or_none(row.get("target_price")),
                "recommendation_date": row.get("recommendation_date"),
                "source": row["source"],
                "brief_rationale": row.get("brief_rationale"),
            }
            updated = conn.execute(upsert_sql, params).rowcount or 0
            if updated == 0:
                conn.execute(insert_sql, params)
            saved += 1

    return saved


def _to_decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return None
