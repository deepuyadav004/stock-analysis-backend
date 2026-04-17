import os
from datetime import datetime, timezone

from anyio import to_thread
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.schedulers.daily_pipeline import run_daily_pipeline
from app.schedulers.news_links_daily import run_daily_news_links_ingestion
from app.schedulers.nse_weekly_price_history import run_nse_weekly_price_history
from app.schedulers.stock_ideas_daily import run_daily_stock_ideas_ingestion


def _is_authorized_cron(request: Request) -> bool:
    """Validate scheduled-job auth using CRON_SECRET bearer token.

    If CRON_SECRET is not configured, allow unauthenticated access.
    """
    secret = os.getenv("CRON_SECRET", "").strip()
    print(f"[CronAuth] CRON_SECRET configured: {bool(secret)}", flush=True)
    if not secret:
        print(f"[CronAuth] No CRON_SECRET set, allowing unauthenticated request", flush=True)
        return True

    auth_header = request.headers.get("authorization", "")
    expected = f"Bearer {secret}"
    is_valid = auth_header == expected
    print(f"[CronAuth] Auth header present: {bool(auth_header)}, Valid: {is_valid}", flush=True)
    return is_valid


async def run_daily_pipeline_job(request: Request) -> JSONResponse:
    if not _is_authorized_cron(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        predictions_made = await to_thread.run_sync(run_daily_pipeline)
        return JSONResponse(
            {
                "status": "ok",
                "job": "daily_pipeline",
                "predictions_made": predictions_made,
                "triggered_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as exc:
        return JSONResponse(
            {
                "status": "error",
                "job": "daily_pipeline",
                "detail": str(exc),
                "triggered_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            status_code=500,
        )


async def run_stock_ideas_daily_job(request: Request) -> JSONResponse:
    if not _is_authorized_cron(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        summary = await to_thread.run_sync(run_daily_stock_ideas_ingestion)
        return JSONResponse(
            {
                "status": "ok",
                "job": "stock_ideas_daily",
                "summary": summary,
                "triggered_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as exc:
        return JSONResponse(
            {
                "status": "error",
                "job": "stock_ideas_daily",
                "detail": str(exc),
                "triggered_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            status_code=500,
        )


async def run_weekly_nse_price_history_job(request: Request) -> JSONResponse:
    try:
        summary = await to_thread.run_sync(run_nse_weekly_price_history)
        return JSONResponse(
            {
                "status": "ok",
                "job": "weekly_nse_price_history",
                "summary": summary,
                "triggered_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as exc:
        return JSONResponse(
            {
                "status": "error",
                "job": "weekly_nse_price_history",
                "detail": str(exc),
                "triggered_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            status_code=500,
        )


async def run_news_links_ingestion_job(request: Request) -> JSONResponse:
    try:
        summary = await to_thread.run_sync(run_daily_news_links_ingestion)
        return JSONResponse(
            {
                "status": "ok",
                "job": "news_links_ingestion",
                "summary": summary,
                "triggered_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as exc:
        return JSONResponse(
            {
                "status": "error",
                "job": "news_links_ingestion",
                "detail": str(exc),
                "triggered_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            status_code=500,
        )
