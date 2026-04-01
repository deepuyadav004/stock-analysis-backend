from __future__ import annotations

from typing import Any

from sqlalchemy import text
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.database import engine

_ALLOWED_SOURCES = {"icicidirect", "economictimes", "moneycontrol"}


def _serialize_news_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "source": row["source"],
        "headline": row["headline"],
        "article_url": row["source_url"],
        "published_at": row["published_at"].isoformat() if row["published_at"] else None,
    }


async def news_list(request: Request) -> JSONResponse:
    query = request.query_params

    source = (query.get("source") or "").strip().lower()
    if source and source not in _ALLOWED_SOURCES:
        return JSONResponse(
            {"error": "Invalid source.", "allowed_sources": sorted(_ALLOWED_SOURCES)},
            status_code=400,
        )

    try:
        limit = min(max(int(query.get("limit", 20)), 1), 100)
        offset = max(int(query.get("offset", 0)), 0)
    except ValueError:
        return JSONResponse({"error": "limit and offset must be integers."}, status_code=400)

    where_conditions = ["1 = 1"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if source:
        where_conditions.append("source = :source")
        params["source"] = source

    where_clause = " AND ".join(where_conditions)

    sql = f"""
        SELECT
            id,
            source,
            source_url,
            headline,
            published_at
        FROM news_articles
        WHERE {where_clause}
        ORDER BY published_at DESC NULLS LAST, id DESC
        LIMIT :limit OFFSET :offset
    """

    count_sql = f"""
        SELECT COUNT(*) AS total
        FROM news_articles
        WHERE {where_clause}
    """

    with engine.connect() as conn:
        total = int(conn.execute(text(count_sql), params).scalar() or 0)
        rows = conn.execute(text(sql), params).mappings().all()

    items = [_serialize_news_row(dict(row)) for row in rows]

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