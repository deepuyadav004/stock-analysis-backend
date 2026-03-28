from __future__ import annotations

from datetime import date, datetime, timedelta
from math import ceil
from typing import Any

from sqlalchemy import text
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.database import engine

_ALLOWED_SORTS = {
    "name_asc": "c.name ASC",
    "name_desc": "c.name DESC",
    "change_desc": "day_change_pct DESC NULLS LAST, c.name ASC",
    "change_asc": "day_change_pct ASC NULLS LAST, c.name ASC",
    "price_desc": "latest_close DESC NULLS LAST, c.name ASC",
    "price_asc": "latest_close ASC NULLS LAST, c.name ASC",
}


def _signal_from_change(change_pct: float) -> str:
    if change_pct >= 0.4:
        return "UP"
    if change_pct <= -0.4:
        return "DOWN"
    return "NEUTRAL"


def _resolve_days(range_key: str) -> int:
    key = range_key.upper()
    mapping = {
        "1W": 7,
        "1M": 30,
        "1Y": 365,
        "3Y": 365 * 3,
        "5Y": 365 * 5,
        "10Y": 365 * 10,
    }
    if key not in mapping:
        raise ValueError("range must be one of 1W, 1M, 1Y, 3Y, 5Y, 10Y")
    return mapping[key]


def _company_listing_row(conn: Any, company_id: int) -> Any:
    return conn.execute(
        text(
            """
            SELECT
                l.id AS listing_id,
                l.ticker,
                c.name AS company_name,
                e.code AS exchange_code
            FROM companies c
            JOIN listings l ON l.company_id = c.id
            JOIN exchanges e ON e.id = l.exchange_id
            WHERE c.id = :company_id
            ORDER BY CASE WHEN e.code = 'NSE' THEN 0 ELSE 1 END, l.id
            LIMIT 1
            """
        ),
        {"company_id": company_id},
    ).mappings().first()


async def companies_list(request: Request) -> JSONResponse:
    query = request.query_params
    search = (query.get("query") or "").strip()
    signal = (query.get("signal") or "").strip().upper()

    if signal and signal not in ("UP", "DOWN", "NEUTRAL"):
        return JSONResponse({"error": "signal must be one of UP, DOWN, NEUTRAL."}, status_code=400)

    try:
        limit = min(max(int(query.get("limit", 20)), 1), 50)
        offset = max(int(query.get("offset", 0)), 0)
    except ValueError:
        return JSONResponse({"error": "limit and offset must be integers."}, status_code=400)

    sort_key = query.get("sort", "name_asc")
    order_clause = _ALLOWED_SORTS.get(sort_key)
    if order_clause is None:
        return JSONResponse({"error": "Invalid sort value.", "allowed": sorted(_ALLOWED_SORTS.keys())}, status_code=400)

    where_conditions = ["1 = 1"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if search:
        where_conditions.append("(LOWER(c.name) LIKE LOWER(:search) OR LOWER(l.ticker) LIKE LOWER(:search))")
        params["search"] = f"%{search}%"

    day_change_pct_expr = """
        CASE
            WHEN pp.prev_close IS NULL OR pp.prev_close = 0 THEN 0
            ELSE ((COALESCE(lp.latest_close, 0) - pp.prev_close) / pp.prev_close) * 100
        END
    """

    if signal == "UP":
        where_conditions.append(f"{day_change_pct_expr} >= 0.4")
    elif signal == "DOWN":
        where_conditions.append(f"{day_change_pct_expr} <= -0.4")
    elif signal == "NEUTRAL":
        where_conditions.append(f"{day_change_pct_expr} > -0.4 AND {day_change_pct_expr} < 0.4")

    where_clause = " AND ".join(where_conditions)

    base_sql = f"""
        FROM companies c
        JOIN listings l ON l.company_id = c.id
        JOIN exchanges e ON e.id = l.exchange_id
        LEFT JOIN LATERAL (
            SELECT sp.date AS latest_date, sp.close AS latest_close
            FROM stock_prices sp
            WHERE sp.listing_id = l.id
            ORDER BY sp.date DESC
            LIMIT 1
        ) lp ON true
        LEFT JOIN LATERAL (
            SELECT sp.close AS prev_close
            FROM stock_prices sp
            WHERE sp.listing_id = l.id
            ORDER BY sp.date DESC
            OFFSET 1 LIMIT 1
        ) pp ON true
        WHERE {where_clause}
    """

    sql = f"""
        SELECT
            c.id AS company_id,
            c.name AS company_name,
            l.ticker,
            e.code AS exchange_code,
            lp.latest_date,
            COALESCE(lp.latest_close, 0) AS latest_close,
            {day_change_pct_expr} AS day_change_pct
        {base_sql}
        ORDER BY {order_clause}
        LIMIT :limit OFFSET :offset
    """

    count_sql = f"""
        SELECT COUNT(*) AS total
        {base_sql}
    """

    with engine.connect() as conn:
        total = int(conn.execute(text(count_sql), params).scalar() or 0)
        rows = conn.execute(text(sql), params).mappings().all()

    items: list[dict[str, Any]] = []
    for row in rows:
        day_change_pct = float(row["day_change_pct"] or 0.0)
        derived_signal = _signal_from_change(day_change_pct)
        items.append(
            {
                "company_id": int(row["company_id"]),
                "company_name": row["company_name"],
                "ticker": row["ticker"],
                "exchange_code": row["exchange_code"],
                "latest_date": row["latest_date"].isoformat() if row["latest_date"] else None,
                "latest_close": round(float(row["latest_close"] or 0.0), 2),
                "day_change_pct": round(day_change_pct, 2),
                "signal": derived_signal,
            }
        )

    return JSONResponse(
        {
            "has_data": total > 0,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total,
                "count": len(items),
            },
            "items": items,
        }
    )


async def company_summary(request: Request) -> JSONResponse:
    raw_company_id = request.path_params.get("company_id")
    try:
        company_id = int(raw_company_id)
    except (TypeError, ValueError):
        return JSONResponse({"error": "company_id must be an integer."}, status_code=400)

    with engine.connect() as conn:
        listing = _company_listing_row(conn, company_id)
        if listing is None:
            return JSONResponse({"error": "company not found."}, status_code=404)

        latest_row = conn.execute(
            text(
                """
                SELECT sp.date, sp.close
                FROM stock_prices sp
                WHERE sp.listing_id = :listing_id
                ORDER BY sp.date DESC
                LIMIT 1
                """
            ),
            {"listing_id": listing["listing_id"]},
        ).mappings().first()

        prev_row = conn.execute(
            text(
                """
                SELECT sp.close
                FROM stock_prices sp
                WHERE sp.listing_id = :listing_id
                ORDER BY sp.date DESC
                OFFSET 1 LIMIT 1
                """
            ),
            {"listing_id": listing["listing_id"]},
        ).mappings().first()

    latest_close = float((latest_row or {}).get("close") or 0.0)
    prev_close = float((prev_row or {}).get("close") or 0.0)
    day_change = latest_close - prev_close if prev_close else 0.0
    day_change_pct = ((day_change / prev_close) * 100) if prev_close else 0.0

    return JSONResponse(
        {
            "has_data": latest_row is not None,
            "company_id": company_id,
            "company_name": listing["company_name"],
            "ticker": listing["ticker"],
            "exchange_code": listing["exchange_code"],
            "latest_close": round(latest_close, 2),
            "latest_date": latest_row["date"].isoformat() if latest_row else None,
            "day_change": round(day_change, 2),
            "day_change_pct": round(day_change_pct, 2),
        }
    )


async def company_performance(request: Request) -> JSONResponse:
    raw_company_id = request.path_params.get("company_id")
    try:
        company_id = int(raw_company_id)
    except (TypeError, ValueError):
        return JSONResponse({"error": "company_id must be an integer."}, status_code=400)

    range_key = (request.query_params.get("range") or "1Y").upper()
    try:
        days = _resolve_days(range_key)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    with engine.connect() as conn:
        listing = _company_listing_row(conn, company_id)
        if listing is None:
            return JSONResponse({"error": "company not found."}, status_code=404)

        latest_date = conn.execute(
            text("SELECT MAX(date) AS latest_date FROM stock_prices WHERE listing_id = :listing_id"),
            {"listing_id": listing["listing_id"]},
        ).mappings().first()["latest_date"]

        if latest_date is None:
            return JSONResponse(
                {
                    "has_data": False,
                    "company_id": company_id,
                    "range": range_key,
                    "from_date": None,
                    "to_date": None,
                    "points": [],
                    "period_change": 0.0,
                    "period_change_pct": 0.0,
                }
            )

        from_date = latest_date - timedelta(days=days - 1)
        rows = conn.execute(
            text(
                """
                SELECT date, close, volume
                FROM stock_prices
                WHERE listing_id = :listing_id
                  AND date BETWEEN :from_date AND :to_date
                ORDER BY date ASC
                """
            ),
            {
                "listing_id": listing["listing_id"],
                "from_date": from_date,
                "to_date": latest_date,
            },
        ).mappings().all()

    points: list[dict[str, Any]] = [
        {
            "date": row["date"].isoformat(),
            "close": round(float(row["close"] or 0.0), 2),
            "volume": int(row["volume"] or 0),
        }
        for row in rows
    ]

    if len(points) > 500:
        step = ceil(len(points) / 500)
        points = points[::step]

    first_close = float(points[0]["close"]) if points else 0.0
    last_close = float(points[-1]["close"]) if points else 0.0
    period_change = last_close - first_close if points else 0.0
    period_change_pct = ((period_change / first_close) * 100) if first_close else 0.0

    return JSONResponse(
        {
            "has_data": len(points) > 0,
            "company_id": company_id,
            "company_name": listing["company_name"],
            "ticker": listing["ticker"],
            "exchange_code": listing["exchange_code"],
            "range": range_key,
            "from_date": from_date.isoformat(),
            "to_date": latest_date.isoformat(),
            "points": points,
            "period_change": round(period_change, 2),
            "period_change_pct": round(period_change_pct, 2),
        }
    )
