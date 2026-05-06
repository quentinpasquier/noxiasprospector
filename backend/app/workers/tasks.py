"""arq worker definitions.

Run with::

    uv run arq app.workers.tasks.WorkerSettings

The worker is intentionally minimal — its only public task is
:func:`run_search_enrichment`, which delegates to the orchestrator. We keep
the orchestrator in ``enrichment/orchestrator.py`` so it can also be invoked
synchronously from tests without the arq layer.
"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

import structlog
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging

logger = structlog.get_logger(__name__)


async def run_search_enrichment(ctx: dict[str, Any], search_id: str) -> dict[str, Any]:
    """arq entrypoint — kicks off the enrichment pipeline for a given search."""
    from app.enrichment.orchestrator import enrich_search  # local import — circular guard

    logger.info("worker.search.start", search_id=search_id)
    summary = await enrich_search(uuid.UUID(search_id))
    logger.info("worker.search.done", search_id=search_id, **summary)
    return summary


async def _on_startup(ctx: dict[str, Any]) -> None:
    configure_logging()
    logger.info("worker.startup")


async def _on_shutdown(ctx: dict[str, Any]) -> None:
    logger.info("worker.shutdown")


def _redis_settings() -> RedisSettings:
    settings = get_settings()
    return RedisSettings.from_dsn(settings.REDIS_URL)


class WorkerSettings:
    """arq configuration class."""

    functions: ClassVar[list[Any]] = [run_search_enrichment]
    on_startup = _on_startup
    on_shutdown = _on_shutdown
    redis_settings = _redis_settings()
    max_jobs = 4
    job_timeout = 30 * 60  # 30 min per search
    keep_result = 3600
