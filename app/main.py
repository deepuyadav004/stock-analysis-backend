from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from sqlalchemy import text

from app.core.database import engine
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
    ],
)
