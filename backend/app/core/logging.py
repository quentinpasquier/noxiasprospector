"""Structured JSON logging configuration via structlog.

Logs are emitted as JSON in production and as a colored console renderer in
development. PII (phone numbers, emails) MUST be anonymized before logging —
see :func:`anonymize_phone` and :func:`anonymize_email` helpers.
"""

import logging
import sys
from typing import Any

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    """Configure structlog + stdlib logging integration.

    Call once at application startup.
    """
    settings = get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.ENVIRONMENT == "development":
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def anonymize_phone(phone: str | None) -> str:
    """Return an anonymized version of a phone number, e.g. ``+33***45``.

    Args:
        phone: Phone number in any format. ``None`` is allowed.

    Returns:
        Anonymized string safe to log, or ``"<empty>"`` if input is empty.
    """
    if not phone:
        return "<empty>"
    cleaned = phone.strip()
    if len(cleaned) < 6:
        return "***"
    return f"{cleaned[:3]}***{cleaned[-2:]}"


def anonymize_email(email: str | None) -> str:
    """Return an anonymized version of an email address, e.g. ``j***@noxias.fr``.

    Args:
        email: Email address. ``None`` is allowed.

    Returns:
        Anonymized string safe to log, or ``"<empty>"`` if input is empty.
    """
    if not email or "@" not in email:
        return "<empty>"
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


def get_logger(name: str | None = None) -> Any:
    """Return a configured structlog logger.

    Args:
        name: Optional logger name; defaults to caller module.
    """
    return structlog.get_logger(name)
