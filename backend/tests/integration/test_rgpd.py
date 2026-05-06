"""End-to-end RGPD tests: blacklist API, prospect deletion, auto opt-out.

These tests validate the demo path stated in the spec:
*"add to blacklist + auto-filter on next search"* and
*"DELETE /api/prospects/{id} retire de la DB ET de Pipedrive
(note de suppression conservée 3 ans)"*.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from app.api.blacklist import router as blacklist_router
from app.api.prospects import router as prospects_router
from app.core import deps
from app.core.deps import get_db
from app.crm import pipedrive as pipedrive_module
from app.db.models import (
    Blacklist,
    BlacklistReason,
    DeletionLog,
    PipedriveMapping,
    Prospect,
    Search,
    User,
)
from app.enrichment.blacklist import is_blacklisted
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import make_user


# --- Fixtures ----------------------------------------------------------------
@pytest_asyncio.fixture
async def authed_client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[tuple[AsyncClient, User]]:
    """FastAPI test client whose auth is short-circuited to a fresh user."""
    user = User(**make_user())
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    async def _get_db_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    fake_claims: dict[str, Any] = {
        "sub": user.auth0_sub,
        "email": user.email,
        "name": user.name,
    }
    monkeypatch.setattr(deps, "verify_access_token", AsyncMock(return_value=fake_claims))

    app = FastAPI()
    app.include_router(blacklist_router, prefix="/api/v1")
    app.include_router(prospects_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _get_db_override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, user


# --- Blacklist API tests -----------------------------------------------------
@pytest.mark.asyncio
async def test_post_blacklist_requires_siren_or_phone(
    authed_client: tuple[AsyncClient, User],
) -> None:
    client, _user = authed_client
    response = await client.post(
        "/api/v1/blacklist",
        json={"reason": "opt_out"},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_post_blacklist_creates_entry(
    authed_client: tuple[AsyncClient, User], db_session: AsyncSession
) -> None:
    client, _user = authed_client
    response = await client.post(
        "/api/v1/blacklist",
        json={"siren": "123456789", "reason": "opt_out", "note": "ticket #42"},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["siren"] == "123456789"
    assert body["reason"] == "opt_out"

    rows = (await db_session.execute(select(Blacklist))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_blacklisted_siren_is_filtered_by_orchestrator(
    db_session: AsyncSession,
) -> None:
    db_session.add(Blacklist(siren="999999999", reason=BlacklistReason.OPT_OUT))
    await db_session.commit()
    assert await is_blacklisted(db_session, siren="999999999", phone_e164=None) is True


# --- Deletion endpoint -------------------------------------------------------
@pytest.mark.asyncio
async def test_delete_prospect_creates_deletion_log_and_blacklists(
    authed_client: tuple[AsyncClient, User],
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, user = authed_client

    search = Search(owner_id=user.id, query="kw", locations=[{"city": "Lyon"}])
    db_session.add(search)
    await db_session.flush()
    prospect = Prospect(
        search_id=search.id,
        place_id="ChIJ-del-1",
        name="Acme",
        siren="123456789",
        phone_e164="+33472001122",
    )
    db_session.add(prospect)
    await db_session.commit()
    await db_session.refresh(prospect)

    # No Pipedrive token configured → no Pipedrive call should happen.
    response = await client.delete(
        f"/api/v1/prospects/{prospect.id}",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Prospect gone, deletion log + blacklist row added.
    assert (
        await db_session.execute(select(Prospect).where(Prospect.id == prospect.id))
    ).scalar_one_or_none() is None

    log = (await db_session.execute(select(DeletionLog))).scalar_one()
    assert log.siren == "123456789"
    assert log.phone_last4 == "1122"  # only last 4 digits stored
    assert log.deleted_by_email == user.email

    bl = (await db_session.execute(select(Blacklist))).scalar_one()
    assert bl.siren == "123456789"
    assert bl.phone_e164 == "+33472001122"
    assert bl.reason == BlacklistReason.OPT_OUT


@pytest.mark.asyncio
async def test_delete_prospect_calls_pipedrive_when_mapping_exists(
    authed_client: tuple[AsyncClient, User],
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, user = authed_client

    # Pretend Pipedrive is configured so the deletion goes through.
    monkeypatch.setenv("PIPEDRIVE_API_TOKEN", "tok")
    monkeypatch.setenv("PIPEDRIVE_COMPANY_DOMAIN", "noxias")
    from app.core.config import get_settings

    get_settings.cache_clear()

    search = Search(owner_id=user.id, query="kw", locations=[{"city": "Lyon"}])
    db_session.add(search)
    await db_session.flush()
    prospect = Prospect(search_id=search.id, place_id="p-x", name="Acme", siren="111222333")
    db_session.add(prospect)
    await db_session.flush()
    db_session.add(
        PipedriveMapping(
            prospect_id=prospect.id,
            pipedrive_organization_id=10,
            pipedrive_person_id=20,
            pipedrive_deal_id=30,
        )
    )
    await db_session.commit()

    deleted: list[tuple[str, int]] = []

    class FakeClient:
        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return

        async def delete_organization(self, org_id: int) -> None:
            deleted.append(("org", org_id))

        async def delete_person(self, person_id: int) -> None:
            deleted.append(("person", person_id))

        async def delete_deal(self, deal_id: int) -> None:
            deleted.append(("deal", deal_id))

    monkeypatch.setattr(pipedrive_module, "build_client", lambda: FakeClient())
    # Also patch the import that the prospects router resolves.
    from app.api import prospects as prospects_module

    monkeypatch.setattr(prospects_module, "build_client", lambda: FakeClient())

    response = await client.delete(
        f"/api/v1/prospects/{prospect.id}",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
    # Deal is deleted before person before org.
    kinds = [k for k, _ in deleted]
    assert kinds == ["deal", "person", "org"]


@pytest.mark.asyncio
async def test_delete_prospect_404_for_other_user(
    authed_client: tuple[AsyncClient, User],
    db_session: AsyncSession,
) -> None:
    client, _user = authed_client

    other = User(**make_user())
    db_session.add(other)
    await db_session.flush()
    search = Search(owner_id=other.id, query="kw", locations=[{"city": "Lyon"}])
    db_session.add(search)
    await db_session.flush()
    prospect = Prospect(search_id=search.id, place_id="p-other", name="Other")
    db_session.add(prospect)
    await db_session.commit()
    await db_session.refresh(prospect)

    response = await client.delete(
        f"/api/v1/prospects/{prospect.id}",
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
