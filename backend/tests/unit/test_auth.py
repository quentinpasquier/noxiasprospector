"""Unit tests for the auth dependency.

We avoid hitting Auth0's JWKS endpoint by stubbing :func:`verify_access_token`.
This isolates the FastAPI dependency logic (token presence, user upsert, last
login refresh) from the JWT validation itself.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from app.api.auth import router as auth_router
from app.core import deps
from app.core.deps import get_db
from app.db.models import User
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    """Build a tiny FastAPI app wired to the test DB session."""

    async def _get_db_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _get_db_override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_me_requires_bearer_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_me_creates_user_on_first_login(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_claims: dict[str, Any] = {
        "sub": "auth0|first-login",
        "email": "newcomer@noxias.fr",
        "name": "Newcomer",
        "picture": "https://example.com/avatar.png",
    }
    monkeypatch.setattr(deps, "verify_access_token", AsyncMock(return_value=fake_claims))

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer fake-token"},
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["email"] == "newcomer@noxias.fr"
    assert payload["name"] == "Newcomer"
    assert payload["role"] == "sales"
    assert payload["last_login_at"] is not None

    result = await db_session.execute(select(User).where(User.auth0_sub == "auth0|first-login"))
    user = result.scalar_one()
    assert user.email == "newcomer@noxias.fr"


@pytest.mark.asyncio
async def test_me_refreshes_last_login(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two consecutive calls update ``last_login_at`` without creating duplicates."""
    fake_claims: dict[str, Any] = {
        "sub": "auth0|repeat",
        "email": "repeat@noxias.fr",
        "name": "Repeat User",
    }
    monkeypatch.setattr(deps, "verify_access_token", AsyncMock(return_value=fake_claims))

    response1 = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer fake-token"})
    assert response1.status_code == status.HTTP_200_OK

    response2 = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer fake-token"})
    assert response2.status_code == status.HTTP_200_OK

    result = await db_session.execute(select(User).where(User.auth0_sub == "auth0|repeat"))
    users = result.scalars().all()
    assert len(users) == 1


@pytest.mark.asyncio
async def test_me_rejects_invalid_token(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.security import AuthError

    async def _raise(_: str) -> dict[str, Any]:
        raise AuthError("Token expired.")

    monkeypatch.setattr(deps, "verify_access_token", _raise)

    response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer expired"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Token expired."
