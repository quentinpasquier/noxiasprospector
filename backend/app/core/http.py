"""Shared HTTP client helpers.

We attach an httpx event hook on every request/response so every external
call lands in our structured logs with:

- ``method``, ``host``, ``path``
- ``status_code``
- ``elapsed_ms`` (millisecond precision)

Requests longer than 5 s are flagged at WARN level for SLO tracking.
The hook never reads request/response bodies — that would risk leaking
PII into Sentry / log aggregators.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

logger = structlog.get_logger("noxias.http")

_SLOW_REQUEST_MS = 5_000


async def _on_request(request: httpx.Request) -> None:
    request.extensions["start_time"] = time.perf_counter()


async def _on_response(response: httpx.Response) -> None:
    started_at = response.request.extensions.get("start_time")
    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 1) if started_at else None
    payload = {
        "method": response.request.method,
        "host": response.request.url.host,
        "path": response.request.url.path,
        "status_code": response.status_code,
        "elapsed_ms": elapsed_ms,
    }
    if elapsed_ms is not None and elapsed_ms > _SLOW_REQUEST_MS:
        logger.warning("http.slow", **payload)
    elif response.status_code >= 500:
        logger.warning("http.server_error", **payload)
    elif response.status_code >= 400:
        logger.info("http.client_error", **payload)
    else:
        logger.info("http.ok", **payload)


def make_async_client(**kwargs: object) -> httpx.AsyncClient:
    """Build an :class:`httpx.AsyncClient` wired with our logging hooks.

    Use this anywhere we call a third-party service so every request lands
    in the structured log stream (and Sentry for slow/5xx ones).
    """
    hooks: dict[str, list[Any]] = {
        "request": [_on_request],
        "response": [_on_response],
    }
    existing_hooks = kwargs.pop("event_hooks", None)
    if isinstance(existing_hooks, dict):
        for key in ("request", "response"):
            extra = existing_hooks.get(key)
            if extra:
                hooks[key] = list(extra) + hooks[key]
    return httpx.AsyncClient(event_hooks=hooks, **kwargs)  # type: ignore[arg-type]
