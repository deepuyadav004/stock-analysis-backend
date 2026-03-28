from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.database import engine

_ALLOWED_SORTS = {
    "confidence_desc": "sp.confidence DESC NULLS LAST, s.name ASC",
    "confidence_asc": "sp.confidence ASC NULLS LAST, s.name ASC",
    "sentiment_desc": "ssd.avg_score DESC NULLS LAST, s.name ASC",
    "sentiment_asc": "ssd.avg_score ASC NULLS LAST, s.name ASC",
    "name_asc": "s.name ASC",
    "name_desc": "s.name DESC",
}


def _freshness_label(age_days: int) -> str:
    if age_days <= 1:
        return "Fresh"
    if age_days <= 3:
        return "Recent"
    return "Stale"


def _parse_date_param(raw: str | None) -> date | None:
    if not raw:
        return None
    return datetime.strptime(raw, "%Y-%m-%d").date()


def _parse_int_list(raw: str | None) -> list[int]:
    if not raw:
        return []
    values: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        values.append(int(part))
    return values


def _age_days(snapshot_date: date) -> int:
    return max((date.today() - snapshot_date).days, 0)


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


async def snapshot_latest(_: Request) -> JSONResponse:
    snapshot_date = _resolve_snapshot_date(None)
    if snapshot_date is None:
        return JSONResponse(
            {
                "has_data": False,
                "latest_date": None,
                "age_days": None,
                "freshness_label": None,
            }
        )

    age_days = _age_days(snapshot_date)
    return JSONResponse(
        {
            "has_data": True,
            "latest_date": snapshot_date.isoformat(),
            "age_days": age_days,
            "freshness_label": _freshness_label(age_days),
        }
    )


async def home_summary(request: Request) -> JSONResponse:
    try:
        requested_date = _parse_date_param(request.query_params.get("date"))
    except ValueError:
        return JSONResponse({"error": "Invalid date format. Use YYYY-MM-DD."}, status_code=400)

    if requested_date and requested_date > date.today():
        return JSONResponse({"error": "date cannot be in the future."}, status_code=400)

    snapshot_date = _resolve_snapshot_date(requested_date)
    if snapshot_date is None:
        return JSONResponse(
            {
                "has_data": False,
                "snapshot_date": None,
                "age_days": None,
                "freshness_label": None,
                "market_mood": {
                    "up_count": 0,
                    "down_count": 0,
                    "neutral_count": 0,
                    "total_sectors": 0,
                    "avg_confidence": 0.0,
                    "avg_sentiment_score": 0.0,
                },
            }
        )

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (WHERE sp.signal = 'UP') AS up_count,
                    COUNT(*) FILTER (WHERE sp.signal = 'DOWN') AS down_count,
                    COUNT(*) FILTER (WHERE sp.signal = 'NEUTRAL') AS neutral_count,
                    COUNT(*) AS total_sectors,
                    AVG(sp.confidence) AS avg_confidence,
                    AVG(ssd.avg_score) AS avg_sentiment_score
                FROM sector_predictions sp
                LEFT JOIN sector_sentiment_daily ssd
                    ON ssd.sector_id = sp.sector_id
                    AND ssd.date = sp.date
                WHERE sp.date = :snapshot_date
                """
            ),
            {"snapshot_date": snapshot_date},
        ).mappings().first()

    total_sectors = int(row["total_sectors"] or 0)
    age_days = _age_days(snapshot_date)
    return JSONResponse(
        {
            "has_data": total_sectors > 0,
            "snapshot_date": snapshot_date.isoformat(),
            "age_days": age_days,
            "freshness_label": _freshness_label(age_days),
            "market_mood": {
                "up_count": int(row["up_count"] or 0),
                "down_count": int(row["down_count"] or 0),
                "neutral_count": int(row["neutral_count"] or 0),
                "total_sectors": total_sectors,
                "avg_confidence": round(float(row["avg_confidence"] or 0.0), 3),
                "avg_sentiment_score": round(float(row["avg_sentiment_score"] or 0.0), 3),
            },
        }
    )


async def sector_signals(request: Request) -> JSONResponse:
    query = request.query_params

    try:
        requested_date = _parse_date_param(query.get("date"))
    except ValueError:
        return JSONResponse({"error": "Invalid date format. Use YYYY-MM-DD."}, status_code=400)

    if requested_date and requested_date > date.today():
        return JSONResponse({"error": "date cannot be in the future."}, status_code=400)

    snapshot_date = _resolve_snapshot_date(requested_date)
    if snapshot_date is None:
        return JSONResponse(
            {
                "has_data": False,
                "snapshot_date": None,
                "age_days": None,
                "freshness_label": None,
                "pagination": {"limit": 0, "offset": 0, "total": 0, "count": 0},
                "items": [],
            }
        )

    try:
        limit = min(max(int(query.get("limit", 20)), 1), 50)
        offset = max(int(query.get("offset", 0)), 0)
    except ValueError:
        return JSONResponse({"error": "limit and offset must be integers."}, status_code=400)

    sort_key = query.get("sort", "confidence_desc")
    order_clause = _ALLOWED_SORTS.get(sort_key)
    if order_clause is None:
        return JSONResponse(
            {
                "error": "Invalid sort value.",
                "allowed": sorted(_ALLOWED_SORTS.keys()),
            },
            status_code=400,
        )

    sql = f"""
        SELECT
            s.id AS sector_id,
            s.name AS sector_name,
            sp.signal,
            sp.confidence,
            ssd.avg_score AS sentiment_score,
            ssd.article_count,
            sp.date AS snapshot_date
        FROM sector_predictions sp
        JOIN sectors s ON s.id = sp.sector_id
        LEFT JOIN sector_sentiment_daily ssd
            ON ssd.sector_id = sp.sector_id
            AND ssd.date = sp.date
        WHERE sp.date = :snapshot_date
        ORDER BY {order_clause}
        LIMIT :limit OFFSET :offset
    """

    with engine.connect() as conn:
        total_row = conn.execute(
            text("SELECT COUNT(*) AS total FROM sector_predictions WHERE date = :snapshot_date"),
            {"snapshot_date": snapshot_date},
        ).mappings().first()

        rows = conn.execute(
            text(sql),
            {
                "snapshot_date": snapshot_date,
                "limit": limit,
                "offset": offset,
            },
        ).mappings().all()

    age_days = _age_days(snapshot_date)
    items: list[dict[str, Any]] = []
    for row in rows:
        items.append(
            {
                "sector_id": row["sector_id"],
                "sector_name": row["sector_name"],
                "signal": row["signal"],
                "confidence": round(float(row["confidence"] or 0.0), 3),
                "sentiment_score": round(float(row["sentiment_score"] or 0.0), 3),
                "article_count": int(row["article_count"] or 0),
                "snapshot_date": row["snapshot_date"].isoformat(),
            }
        )

    total = int(total_row["total"] or 0)
    return JSONResponse(
        {
            "has_data": total > 0,
            "snapshot_date": snapshot_date.isoformat(),
            "age_days": age_days,
            "freshness_label": _freshness_label(age_days),
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total,
                "count": len(items),
            },
            "items": items,
        }
    )


async def sector_trends(request: Request) -> JSONResponse:
    query = request.query_params

    try:
        requested_date = _parse_date_param(query.get("date"))
    except ValueError:
        return JSONResponse({"error": "Invalid date format. Use YYYY-MM-DD."}, status_code=400)

    if requested_date and requested_date > date.today():
        return JSONResponse({"error": "date cannot be in the future."}, status_code=400)

    snapshot_date = _resolve_snapshot_date(requested_date)
    if snapshot_date is None:
        return JSONResponse(
            {
                "has_data": False,
                "snapshot_date": None,
                "days": 0,
                "items": [],
            }
        )

    try:
        days = int(query.get("days", 7))
    except ValueError:
        return JSONResponse({"error": "days must be an integer."}, status_code=400)

    days = min(max(days, 2), 30)

    try:
        sector_ids = _parse_int_list(query.get("sector_ids"))
    except ValueError:
        return JSONResponse({"error": "sector_ids must be comma-separated integers."}, status_code=400)

    with engine.connect() as conn:
        if not sector_ids:
            top_rows = conn.execute(
                text(
                    """
                    SELECT sector_id
                    FROM sector_predictions
                    WHERE date = :snapshot_date
                    ORDER BY confidence DESC NULLS LAST
                    LIMIT 5
                    """
                ),
                {"snapshot_date": snapshot_date},
            ).mappings().all()
            sector_ids = [int(row["sector_id"]) for row in top_rows]

        if not sector_ids:
            return JSONResponse(
                {
                    "has_data": False,
                    "snapshot_date": snapshot_date.isoformat(),
                    "days": days,
                    "items": [],
                }
            )

        start_date = snapshot_date - timedelta(days=days - 1)

        sectors = conn.execute(
            text(
                """
                SELECT id, name
                FROM sectors
                WHERE id = ANY(:sector_ids)
                """
            ),
            {"sector_ids": sector_ids},
        ).mappings().all()

        trend_rows = conn.execute(
            text(
                """
                SELECT
                    sp.sector_id,
                    sp.date,
                    sp.signal,
                    sp.confidence,
                    ssd.avg_score AS sentiment_score
                FROM sector_predictions sp
                LEFT JOIN sector_sentiment_daily ssd
                    ON ssd.sector_id = sp.sector_id
                    AND ssd.date = sp.date
                WHERE sp.sector_id = ANY(:sector_ids)
                  AND sp.date BETWEEN :start_date AND :snapshot_date
                ORDER BY sp.sector_id, sp.date
                """
            ),
            {
                "sector_ids": sector_ids,
                "start_date": start_date,
                "snapshot_date": snapshot_date,
            },
        ).mappings().all()

    name_by_id = {int(row["id"]): row["name"] for row in sectors}
    points_by_sector: dict[int, list[dict[str, Any]]] = {sid: [] for sid in sector_ids}

    for row in trend_rows:
        sid = int(row["sector_id"])
        if sid not in points_by_sector:
            points_by_sector[sid] = []
        points_by_sector[sid].append(
            {
                "date": row["date"].isoformat(),
                "signal": row["signal"],
                "confidence": round(float(row["confidence"] or 0.0), 3),
                "sentiment_score": round(float(row["sentiment_score"] or 0.0), 3),
            }
        )

    items: list[dict[str, Any]] = []
    for sid in sector_ids:
        if sid not in name_by_id:
            continue
        items.append(
            {
                "sector_id": sid,
                "sector_name": name_by_id[sid],
                "points": points_by_sector.get(sid, []),
            }
        )

    return JSONResponse(
        {
            "has_data": len(items) > 0,
            "snapshot_date": snapshot_date.isoformat(),
            "days": days,
            "items": items,
        }
    )


async def sector_detail(request: Request) -> JSONResponse:
    raw_sector_id = request.path_params.get("sector_id")
    try:
        sector_id = int(raw_sector_id)
    except (TypeError, ValueError):
        return JSONResponse({"error": "sector_id must be an integer."}, status_code=400)

    query = request.query_params
    try:
        from_date = _parse_date_param(query.get("from"))
        to_date = _parse_date_param(query.get("to"))
    except ValueError:
        return JSONResponse({"error": "Invalid date format. Use YYYY-MM-DD."}, status_code=400)

    snapshot_date = _resolve_snapshot_date(None)
    if snapshot_date is None:
        return JSONResponse(
            {
                "has_data": False,
                "sector": None,
                "timeline": [],
            }
        )

    if to_date is None:
        to_date = snapshot_date
    if from_date is None:
        from_date = to_date - timedelta(days=29)

    if from_date > to_date:
        return JSONResponse({"error": "from date must be before to date."}, status_code=400)

    with engine.connect() as conn:
        sector_row = conn.execute(
            text("SELECT id, name FROM sectors WHERE id = :sector_id"),
            {"sector_id": sector_id},
        ).mappings().first()

        if sector_row is None:
            return JSONResponse({"error": "sector not found."}, status_code=404)

        timeline_rows = conn.execute(
            text(
                """
                SELECT
                    sp.date,
                    sp.signal,
                    sp.confidence,
                    ssd.avg_score AS sentiment_score,
                    ssd.article_count
                FROM sector_predictions sp
                LEFT JOIN sector_sentiment_daily ssd
                    ON ssd.sector_id = sp.sector_id
                    AND ssd.date = sp.date
                WHERE sp.sector_id = :sector_id
                  AND sp.date BETWEEN :from_date AND :to_date
                ORDER BY sp.date DESC
                """
            ),
            {
                "sector_id": sector_id,
                "from_date": from_date,
                "to_date": to_date,
            },
        ).mappings().all()

    timeline: list[dict[str, Any]] = []
    for row in timeline_rows:
        timeline.append(
            {
                "date": row["date"].isoformat(),
                "signal": row["signal"],
                "confidence": round(float(row["confidence"] or 0.0), 3),
                "sentiment_score": round(float(row["sentiment_score"] or 0.0), 3),
                "article_count": int(row["article_count"] or 0),
            }
        )

    return JSONResponse(
        {
            "has_data": len(timeline) > 0,
            "sector": {
                "sector_id": int(sector_row["id"]),
                "sector_name": sector_row["name"],
            },
            "range": {
                "from": from_date.isoformat(),
                "to": to_date.isoformat(),
            },
            "timeline": timeline,
        }
    )
