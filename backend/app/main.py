"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as redis
import sentry_sdk
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.api.auth import router as auth_router
from app.api.blacklist import router as blacklist_router
from app.api.exports import router as exports_router
from app.api.prospects import router as prospects_router
from app.api.searches import router as searches_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — runs at startup and shutdown."""
    configure_logging()
    logger = get_logger(__name__)
    settings = get_settings()

    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=0.1,
            send_default_pii=False,
        )
        logger.info("sentry.initialized", environment=settings.ENVIRONMENT)

    logger.info("app.startup", version=__version__, environment=settings.ENVIRONMENT)
    yield
    logger.info("app.shutdown")


def create_app() -> FastAPI:
    """Application factory — keeps tests fast and isolated."""
    settings = get_settings()

    app = FastAPI(
        title="NoxiasProspect API",
        version=__version__,
        description="B2B prospecting backend for Noxias.",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        """Liveness probe — process is up. Used by Render/Fly.io health checks."""
        return {"status": "ok", "version": __version__}

    @app.get("/health/ready", tags=["health"])
    async def readiness() -> JSONResponse:
        """Readiness probe — pings Postgres and Redis.

        Returns ``503`` with per-dependency status if any of the backing
        services is unreachable, so traffic isn't routed to broken instances.
        """
        results: dict[str, str] = {}

        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            results["database"] = "ok"
        except Exception as exc:  # pragma: no cover -- exercised in prod only
            results["database"] = f"error: {exc.__class__.__name__}"

        try:
            client: redis.Redis = redis.Redis.from_url(settings.REDIS_URL)
            try:
                await client.ping()
                results["redis"] = "ok"
            finally:
                await client.aclose()
        except Exception as exc:  # pragma: no cover -- exercised in prod only
            results["redis"] = f"error: {exc.__class__.__name__}"

        all_ok = all(v == "ok" for v in results.values())
        return JSONResponse(
            status_code=status.HTTP_200_OK
            if all_ok
            else status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "ready" if all_ok else "degraded", **results},
        )

    app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
    app.include_router(searches_router, prefix=settings.API_V1_PREFIX)
    app.include_router(prospects_router, prefix=settings.API_V1_PREFIX)
    app.include_router(exports_router, prefix=settings.API_V1_PREFIX)
    app.include_router(blacklist_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
