from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from sqlalchemy import text

from app.core.database import engine
from app.routers.home import home_summary, sector_detail, sector_signals, sector_trends, snapshot_latest
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


app = Starlette(
    debug=True,
    routes=[
        Route("/test", test_endpoint),
        Route("/health", health),
        Route("/health/db", health_db),
        Route("/v1/snapshot/latest", snapshot_latest),
        Route("/v1/home/summary", home_summary),
        Route("/v1/sectors/signals", sector_signals),
        Route("/v1/sectors/trends", sector_trends),
        Route("/v1/sectors/{sector_id:int}/detail", sector_detail),
    ],
)
