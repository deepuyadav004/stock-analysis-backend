from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.database import engine


def _parse_date_param(raw: str | None) -> date | None:
    if not raw:
        return None
    return datetime.strptime(raw, "%Y-%m-%d").date()


def _resolve_snapshot_date(requested: date | None) -> date | None:
    if requested:
        return requested

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT MAX(dt) AS latest_date
                FROM (
                    SELECT MAX(date) AS dt FROM sector_predictions
                    UNION ALL
                    SELECT MAX(date) AS dt FROM sector_sentiment_daily
                ) src
                """
            )
        ).mappings().first()

    return row["latest_date"] if row and row["latest_date"] else None


async def insights_sector_compare(request: Request) -> JSONResponse:
    query = request.query_params
    try:
        requested_date = _parse_date_param(query.get("date"))
    except ValueError:
        return JSONResponse({"error": "Invalid date format. Use YYYY-MM-DD."}, status_code=400)

    if requested_date and requested_date > date.today():
        return JSONResponse({"error": "date cannot be in the future."}, status_code=400)

    try:
        days = int(query.get("days", 7))
    except ValueError:
        return JSONResponse({"error": "days must be an integer."}, status_code=400)

    if days not in (7, 30):
        return JSONResponse({"error": "days must be 7 or 30."}, status_code=400)

    snapshot_date = _resolve_snapshot_date(requested_date)
    if snapshot_date is None:
        return JSONResponse(
            {
                "has_data": False,
                "snapshot_date": None,
                "days": days,
                "market": None,
                "leaders": {"strongest": None, "weakest": None},
            }
        )

    start_date = snapshot_date - timedelta(days=days - 1)
    prev_start = start_date - timedelta(days=days)
    prev_end = start_date - timedelta(days=1)

    with engine.connect() as conn:
        latest_row = conn.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (WHERE signal = 'UP') AS up_count,
                    COUNT(*) FILTER (WHERE signal = 'DOWN') AS down_count,
                    COUNT(*) FILTER (WHERE signal = 'NEUTRAL') AS neutral_count,
                    COUNT(*) AS total
                FROM sector_predictions
                WHERE date = :snapshot_date
                """
            ),
            {"snapshot_date": snapshot_date},
        ).mappings().first()

        window_row = conn.execute(
            text(
                """
                SELECT
                    AVG(sp.confidence) AS avg_confidence,
                    AVG(ssd.avg_score) AS avg_sentiment
                FROM sector_predictions sp
                LEFT JOIN sector_sentiment_daily ssd
                    ON ssd.sector_id = sp.sector_id
                    AND ssd.date = sp.date
                WHERE sp.date BETWEEN :start_date AND :snapshot_date
                """
            ),
            {"start_date": start_date, "snapshot_date": snapshot_date},
        ).mappings().first()

        previous_sentiment_row = conn.execute(
            text(
                """
                SELECT AVG(ssd.avg_score) AS avg_sentiment
                FROM sector_sentiment_daily ssd
                WHERE ssd.date BETWEEN :prev_start AND :prev_end
                """
            ),
            {"prev_start": prev_start, "prev_end": prev_end},
        ).mappings().first()

        leader_rows = conn.execute(
            text(
                """
                SELECT
                    s.id AS sector_id,
                    s.name AS sector_name,
                    AVG(COALESCE(ssd.avg_score, 0)) AS avg_sentiment,
                    AVG(COALESCE(sp.confidence, 0)) AS avg_confidence
                FROM sector_predictions sp
                JOIN sectors s ON s.id = sp.sector_id
                LEFT JOIN sector_sentiment_daily ssd
                    ON ssd.sector_id = sp.sector_id
                    AND ssd.date = sp.date
                WHERE sp.date BETWEEN :start_date AND :snapshot_date
                GROUP BY s.id, s.name
                ORDER BY avg_sentiment DESC NULLS LAST
                """
            ),
            {"start_date": start_date, "snapshot_date": snapshot_date},
        ).mappings().all()

    total = int(latest_row["total"] or 0)
    if total == 0:
        return JSONResponse(
            {
                "has_data": False,
                "snapshot_date": snapshot_date.isoformat(),
                "days": days,
                "market": None,
                "leaders": {"strongest": None, "weakest": None},
            }
        )

    strongest = None
    weakest = None
    if leader_rows:
        top = leader_rows[0]
        low = leader_rows[-1]
        strongest = {
            "sector_id": int(top["sector_id"]),
            "sector_name": top["sector_name"],
            "avg_sentiment": round(float(top["avg_sentiment"] or 0.0), 3),
            "avg_confidence": round(float(top["avg_confidence"] or 0.0), 3),
        }
        weakest = {
            "sector_id": int(low["sector_id"]),
            "sector_name": low["sector_name"],
            "avg_sentiment": round(float(low["avg_sentiment"] or 0.0), 3),
            "avg_confidence": round(float(low["avg_confidence"] or 0.0), 3),
        }

    current_avg_sentiment = float(window_row["avg_sentiment"] or 0.0)
    prev_avg_sentiment = float(previous_sentiment_row["avg_sentiment"] or 0.0)

    return JSONResponse(
        {
            "has_data": True,
            "snapshot_date": snapshot_date.isoformat(),
            "days": days,
            "market": {
                "up_count": int(latest_row["up_count"] or 0),
                "down_count": int(latest_row["down_count"] or 0),
                "neutral_count": int(latest_row["neutral_count"] or 0),
                "total_sectors": total,
                "avg_confidence": round(float(window_row["avg_confidence"] or 0.0), 3),
                "avg_sentiment": round(current_avg_sentiment, 3),
                "sentiment_change_vs_previous": round(current_avg_sentiment - prev_avg_sentiment, 3),
            },
            "leaders": {
                "strongest": strongest,
                "weakest": weakest,
            },
        }
    )


async def insights_signal_stability(request: Request) -> JSONResponse:
    query = request.query_params
    try:
        requested_date = _parse_date_param(query.get("date"))
    except ValueError:
        return JSONResponse({"error": "Invalid date format. Use YYYY-MM-DD."}, status_code=400)

    if requested_date and requested_date > date.today():
        return JSONResponse({"error": "date cannot be in the future."}, status_code=400)

    try:
        days = int(query.get("days", 30))
    except ValueError:
        return JSONResponse({"error": "days must be an integer."}, status_code=400)

    if days < 7 or days > 60:
        return JSONResponse({"error": "days must be between 7 and 60."}, status_code=400)

    snapshot_date = _resolve_snapshot_date(requested_date)
    if snapshot_date is None:
        return JSONResponse(
            {
                "has_data": False,
                "snapshot_date": None,
                "days": days,
                "summary": None,
                "items": [],
            }
        )

    start_date = snapshot_date - timedelta(days=days - 1)

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                WITH series AS (
                    SELECT
                        sp.sector_id,
                        s.name AS sector_name,
                        sp.date,
                        sp.signal,
                        sp.confidence,
                        LAG(sp.signal) OVER (PARTITION BY sp.sector_id ORDER BY sp.date) AS prev_signal
                    FROM sector_predictions sp
                    JOIN sectors s ON s.id = sp.sector_id
                    WHERE sp.date BETWEEN :start_date AND :snapshot_date
                )
                SELECT
                    sector_id,
                    sector_name,
                    COUNT(*) AS total_days,
                    SUM(CASE WHEN prev_signal IS NOT NULL AND prev_signal <> signal THEN 1 ELSE 0 END) AS flips,
                    AVG(confidence) AS avg_confidence,
                    MAX(date) AS latest_date
                FROM series
                GROUP BY sector_id, sector_name
                ORDER BY sector_name
                """
            ),
            {"start_date": start_date, "snapshot_date": snapshot_date},
        ).mappings().all()

        latest_rows = conn.execute(
            text(
                """
                SELECT sp.sector_id, sp.signal
                FROM sector_predictions sp
                WHERE sp.date = :snapshot_date
                """
            ),
            {"snapshot_date": snapshot_date},
        ).mappings().all()

    latest_signal_by_sector = {int(row["sector_id"]): row["signal"] for row in latest_rows}

    items: list[dict[str, Any]] = []
    for row in rows:
        total_days = int(row["total_days"] or 0)
        flips = int(row["flips"] or 0)
        stability_ratio = 0.0
        if total_days > 0:
            stability_ratio = (total_days - flips) / total_days

        sector_id = int(row["sector_id"])
        items.append(
            {
                "sector_id": sector_id,
                "sector_name": row["sector_name"],
                "latest_signal": latest_signal_by_sector.get(sector_id, "NEUTRAL"),
                "total_days": total_days,
                "flips": flips,
                "stability_ratio": round(stability_ratio, 3),
                "avg_confidence": round(float(row["avg_confidence"] or 0.0), 3),
            }
        )

    items.sort(key=lambda x: (x["stability_ratio"], x["avg_confidence"]), reverse=True)

    if not items:
        return JSONResponse(
            {
                "has_data": False,
                "snapshot_date": snapshot_date.isoformat(),
                "days": days,
                "summary": None,
                "items": [],
            }
        )

    avg_stability = sum(item["stability_ratio"] for item in items) / len(items)
    avg_confidence = sum(item["avg_confidence"] for item in items) / len(items)

    return JSONResponse(
        {
            "has_data": True,
            "snapshot_date": snapshot_date.isoformat(),
            "days": days,
            "summary": {
                "stable_sector_count": len([x for x in items if x["stability_ratio"] >= 0.7]),
                "total_sectors": len(items),
                "avg_stability_ratio": round(avg_stability, 3),
                "avg_confidence": round(avg_confidence, 3),
            },
            "items": items,
        }
    )
