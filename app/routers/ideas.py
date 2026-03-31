from __future__ import annotations

from typing import Any

from sqlalchemy import text
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.database import engine

_ALLOWED_SOURCES = {"moneycontrol", "kotakneo", "lemonn"}
_ALLOWED_CALL_TYPES = {"BUY", "SELL", "HOLD"}
_ALLOWED_SORTS = {
    "date_desc": "recommendation_date DESC NULLS LAST, id DESC",
    "date_asc": "recommendation_date ASC NULLS LAST, id DESC",
    "target_desc": "target_price DESC NULLS LAST, id DESC",
    "target_asc": "target_price ASC NULLS LAST, id DESC",
    "company_asc": "company_name ASC",
    "company_desc": "company_name DESC",
}


def _serialize_idea_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "ticker": row["ticker"],
        "company_name": row["company_name"],
        "call_type": row["call_type"],
        "target_price": float(row["target_price"]) if row["target_price"] is not None else None,
        "recommendation_date": row["recommendation_date"].isoformat() if row["recommendation_date"] else None,
        "source": row["source"],
        "brief_rationale": row["brief_rationale"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


async def ideas_list(request: Request) -> JSONResponse:
    query = request.query_params

    source = (query.get("source") or "").strip().lower()
    if source and source not in _ALLOWED_SOURCES:
        return JSONResponse(
            {"error": "Invalid source.", "allowed_sources": sorted(_ALLOWED_SOURCES)},
            status_code=400,
        )

    call_type = (query.get("call_type") or "").strip().upper()
    if call_type and call_type not in _ALLOWED_CALL_TYPES:
        return JSONResponse(
            {"error": "Invalid call_type.", "allowed_call_types": sorted(_ALLOWED_CALL_TYPES)},
            status_code=400,
        )

    search = (query.get("query") or "").strip()

    try:
        limit = min(max(int(query.get("limit", 20)), 1), 100)
        offset = max(int(query.get("offset", 0)), 0)
    except ValueError:
        return JSONResponse({"error": "limit and offset must be integers."}, status_code=400)

    sort_key = (query.get("sort") or "date_desc").strip().lower()
    order_clause = _ALLOWED_SORTS.get(sort_key)
    if order_clause is None:
        return JSONResponse(
            {"error": "Invalid sort value.", "allowed_sorts": sorted(_ALLOWED_SORTS.keys())},
            status_code=400,
        )

    where_conditions = ["1 = 1"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if source:
        where_conditions.append("source = :source")
        params["source"] = source

    if call_type:
        where_conditions.append("call_type = :call_type")
        params["call_type"] = call_type

    if search:
        where_conditions.append("(LOWER(company_name) LIKE LOWER(:search) OR LOWER(ticker) LIKE LOWER(:search))")
        params["search"] = f"%{search}%"

    where_clause = " AND ".join(where_conditions)

    sql = f"""
        SELECT
            id,
            ticker,
            company_name,
            call_type,
            target_price,
            recommendation_date,
            source,
            brief_rationale,
            created_at
        FROM stock_ideas_recommendations
        WHERE {where_clause}
        ORDER BY {order_clause}
        LIMIT :limit OFFSET :offset
    """

    count_sql = f"""
        SELECT COUNT(*) AS total
        FROM stock_ideas_recommendations
        WHERE {where_clause}
    """

    with engine.connect() as conn:
        total = int(conn.execute(text(count_sql), params).scalar() or 0)
        rows = conn.execute(text(sql), params).mappings().all()

    items = [_serialize_idea_row(dict(row)) for row in rows]

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


async def idea_detail(request: Request) -> JSONResponse:
    raw_idea_id = request.path_params.get("idea_id")
    try:
        idea_id = int(raw_idea_id)
    except (TypeError, ValueError):
        return JSONResponse({"error": "idea_id must be an integer."}, status_code=400)

    sql = text(
        """
        SELECT
            id,
            ticker,
            company_name,
            call_type,
            target_price,
            recommendation_date,
            source,
            brief_rationale,
            created_at
        FROM stock_ideas_recommendations
        WHERE id = :idea_id
        LIMIT 1
        """
    )

    with engine.connect() as conn:
        row = conn.execute(sql, {"idea_id": idea_id}).mappings().first()

    if row is None:
        return JSONResponse({"error": "idea not found."}, status_code=404)

    return JSONResponse({"has_data": True, "item": _serialize_idea_row(dict(row))})
