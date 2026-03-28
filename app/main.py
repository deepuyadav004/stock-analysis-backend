from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from sqlalchemy import text

from app.core.database import engine
from app.routers.companies import companies_list, company_performance, company_summary
from app.routers.home import home_summary, sector_detail, sector_signals, sector_trends, snapshot_latest
from app.routers.insights import insights_sector_compare, insights_signal_stability
from app.routers.jobs import run_daily_pipeline_job
from app.routers.test import test_endpoint


async def health(_: object) -> JSONResponse:
    return JSONResponse({"status": "ok"})


async def health_db(_: object) -> JSONResponse:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return JSONResponse({"status": "ok", "database": "connected"})
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "database": "disconnected", "detail": str(exc)},
            status_code=500,
        )


async def api_version(_: object) -> JSONResponse:
    return JSONResponse(
        {
            "service": "grow-wealth-backend",
            "api_version": "v1",
            "release": "chunk-6",
        }
    )


async def diagnostics(_: object) -> JSONResponse:
    with engine.connect() as connection:
        total_sectors = int(
            connection.execute(text("SELECT COUNT(*) FROM sectors")).scalar() or 0
        )
        prediction_days = int(
            connection.execute(text("SELECT COUNT(DISTINCT date) FROM sector_predictions")).scalar() or 0
        )
        sentiment_days = int(
            connection.execute(text("SELECT COUNT(DISTINCT date) FROM sector_sentiment_daily")).scalar() or 0
        )

    return JSONResponse(
        {
            "status": "ok",
            "diagnostics": {
                "total_sectors": total_sectors,
                "prediction_days": prediction_days,
                "sentiment_days": sentiment_days,
            },
        }
    )


app = Starlette(
    debug=True,
    routes=[
        Route("/test", test_endpoint),
        Route("/health", health),
        Route("/health/db", health_db),
        Route("/v1/meta/version", api_version),
        Route("/v1/meta/diagnostics", diagnostics),
        Route("/v1/snapshot/latest", snapshot_latest),
        Route("/v1/home/summary", home_summary),
        Route("/v1/sectors/signals", sector_signals),
        Route("/v1/sectors/trends", sector_trends),
        Route("/v1/sectors/{sector_id:int}/detail", sector_detail),
        Route("/v1/companies/list", companies_list),
        Route("/v1/companies/{company_id:int}/summary", company_summary),
        Route("/v1/companies/{company_id:int}/performance", company_performance),
        Route("/v1/insights/sector-compare", insights_sector_compare),
        Route("/v1/insights/signal-stability", insights_signal_stability),
        Route("/v1/jobs/daily-pipeline", run_daily_pipeline_job, methods=["GET"]),
    ],
)
