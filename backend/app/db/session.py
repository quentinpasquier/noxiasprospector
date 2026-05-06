"""Database engine and session management.

We expose:
- ``engine``: an async SQLAlchemy engine (asyncpg driver)
- ``AsyncSessionLocal``: a session factory bound to that engine
- ``get_db``: a FastAPI dependency yielding an :class:`AsyncSession`

Alembic uses a separate sync engine (see ``app/db/migrations/env.py``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def _build_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


engine: AsyncEngine = _build_engine()

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a database session.

    The session is automatically closed at request end. Commit is the caller's
    responsibility (typically inside a service function).
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
