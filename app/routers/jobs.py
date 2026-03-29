import os
from datetime import datetime, timezone

from anyio import to_thread
from starlette.requests import Request
from starlette.responses import JSONResponse

# from app.schedulers.daily_pipeline import run_daily_pipeline


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
        # Vercel-deployment branch: ML pipeline is intentionally disabled to stay within
        # serverless package/storage limits. Uncomment lines below in full-runtime envs.
        # predictions_made = await to_thread.run_sync(run_daily_pipeline)
        # return JSONResponse(
        #     {
        #         "status": "ok",
        #         "job": "daily_pipeline",
        #         "predictions_made": predictions_made,
        #         "triggered_at_utc": datetime.now(timezone.utc).isoformat(),
        #     }
        # )
        return JSONResponse(
            {
                "status": "disabled",
                "job": "daily_pipeline",
                "detail": "ML pipeline is commented out in vercel-deployment branch.",
                "triggered_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            status_code=503,
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
