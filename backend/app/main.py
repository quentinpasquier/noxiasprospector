"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.auth import router as auth_router
from app.api.searches import router as searches_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger


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
        """Liveness probe."""
        return {"status": "ok", "version": __version__}

    @app.get("/health/ready", tags=["health"])
    async def readiness() -> dict[str, str]:
        """Readiness probe — DB/Redis checks added at Phase 7."""
        return {"status": "ready"}

    app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
    app.include_router(searches_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
