"""Shared pytest fixtures.

Tests run against a real Postgres database (matches production behavior for
JSONB, partial indexes, enums). The test database is created/dropped per
session and migrations are applied via Alembic.

Set ``TEST_DATABASE_URL`` to point at a dedicated test database; default is
``postgresql+asyncpg://noxias:noxias@localhost:5432/noxiasprospect_test``.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://noxias:noxias@localhost:5432/noxiasprospect_test",
)


def _admin_url(test_url: str) -> str:
    """Convert the test DB URL into an admin URL pointing at ``postgres``."""
    # postgresql+asyncpg://user:pass@host:port/dbname → postgresql+asyncpg://...:port/postgres
    head, _, _ = test_url.rpartition("/")
    return f"{head}/postgres"


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """Override pytest-asyncio's default loop with a session-scoped one."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _setup_test_database() -> AsyncIterator[None]:
    """Create the test DB, apply migrations, drop on teardown."""
    test_db_name = TEST_DATABASE_URL.rsplit("/", 1)[-1]
    admin_engine = create_async_engine(_admin_url(TEST_DATABASE_URL), isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{test_db_name}"'))
        await conn.execute(text(f'CREATE DATABASE "{test_db_name}"'))
    await admin_engine.dispose()

    cfg = Config("alembic.ini")
    cfg.set_main_option(
        "sqlalchemy.url",
        TEST_DATABASE_URL.replace("+asyncpg", ""),
    )
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    # Auth is exercised via monkey-patched verify_access_token; force the
    # flag off so the auto-detect (Auth0 envs missing) doesn't bypass it.
    os.environ["AUTH_DISABLED"] = "false"
    # Reset the cached settings so the new URL is picked up.
    from app.core.config import get_settings

    get_settings.cache_clear()
    command.upgrade(cfg, "head")

    # Rebuild the application engine to point at the test DB and use NullPool
    # so cross-event-loop usage in pytest-asyncio doesn't trip asyncpg.
    from app.db import session as db_session

    new_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    new_factory = async_sessionmaker(bind=new_engine, expire_on_commit=False, autoflush=False)
    db_session.engine = new_engine
    db_session.AsyncSessionLocal = new_factory

    yield

    admin_engine = create_async_engine(_admin_url(TEST_DATABASE_URL), isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        # Force-disconnect any lingering connections before dropping.
        await conn.execute(
            text(
                f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname='{test_db_name}' AND pid<>pg_backend_pid()"
            )
        )
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{test_db_name}"'))
    await admin_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Yield a clean :class:`AsyncSession` and roll back changes after the test."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
    # Truncate every table to keep tests isolated.
    async with engine.connect() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE pipedrive_mappings, prospects, searches, "
                "blacklist, users RESTART IDENTITY CASCADE"
            )
        )
        await conn.commit()
    await engine.dispose()


def make_user(**overrides: Any) -> dict[str, Any]:
    """Factory helper for User attributes."""
    base: dict[str, Any] = {
        "auth0_sub": f"auth0|{uuid.uuid4().hex}",
        "email": f"user-{uuid.uuid4().hex[:8]}@noxias.fr",
        "name": "Sales Rep",
    }
    base.update(overrides)
    return base
