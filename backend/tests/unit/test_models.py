"""Unit tests for SQLAlchemy models.

Cover the constraints stated in the CDC:
- ``users.email`` and ``users.auth0_sub`` are unique
- ``prospects.place_id`` is unique
- ``prospects.siren`` is uniquely indexed only when not null
- ``prospects.phone_e164`` is uniquely indexed only when not null
- ``blacklist`` rejects rows with neither siren nor phone_e164
"""

from __future__ import annotations

import pytest
from app.db.models import (
    Blacklist,
    BlacklistReason,
    Prospect,
    Search,
    SearchStatus,
    User,
    UserRole,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import make_user


@pytest.mark.asyncio
async def test_user_can_be_created(db_session: AsyncSession) -> None:
    user = User(**make_user())
    db_session.add(user)
    await db_session.commit()
    assert user.id is not None
    assert user.role == UserRole.SALES
    assert user.created_at is not None


@pytest.mark.asyncio
async def test_user_email_is_unique(db_session: AsyncSession) -> None:
    user1 = User(**make_user(email="dup@noxias.fr"))
    db_session.add(user1)
    await db_session.commit()

    user2 = User(**make_user(email="dup@noxias.fr"))
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_user_auth0_sub_is_unique(db_session: AsyncSession) -> None:
    user1 = User(**make_user(auth0_sub="auth0|abc"))
    db_session.add(user1)
    await db_session.commit()

    user2 = User(**make_user(auth0_sub="auth0|abc"))
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_search_cascade_deletes_prospects(db_session: AsyncSession) -> None:
    user = User(**make_user())
    db_session.add(user)
    await db_session.flush()

    search = Search(
        owner_id=user.id,
        query="courtier en travaux Lyon",
        locations=[{"city": "Lyon", "postal_code": "69001"}],
        status=SearchStatus.PENDING,
    )
    db_session.add(search)
    await db_session.flush()

    prospect = Prospect(
        search_id=search.id,
        place_id="ChIJ_test_123",
        name="Acme",
        rating=4.5,
        reviews_count=120,
    )
    db_session.add(prospect)
    await db_session.commit()
    prospect_id = prospect.id

    await db_session.delete(search)
    await db_session.commit()

    result = await db_session.execute(select(Prospect).where(Prospect.id == prospect_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_prospect_place_id_is_unique(db_session: AsyncSession) -> None:
    user = User(**make_user())
    db_session.add(user)
    await db_session.flush()
    search = Search(owner_id=user.id, query="q", locations=[])
    db_session.add(search)
    await db_session.flush()

    p1 = Prospect(search_id=search.id, place_id="ChIJsame", name="A")
    p2 = Prospect(search_id=search.id, place_id="ChIJsame", name="B")
    db_session.add_all([p1, p2])
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_prospect_siren_unique_only_when_set(db_session: AsyncSession) -> None:
    user = User(**make_user())
    db_session.add(user)
    await db_session.flush()
    search = Search(owner_id=user.id, query="q", locations=[])
    db_session.add(search)
    await db_session.flush()

    # Two prospects with NULL siren are allowed.
    p1 = Prospect(search_id=search.id, place_id="ChIJ1", name="A", siren=None)
    p2 = Prospect(search_id=search.id, place_id="ChIJ2", name="B", siren=None)
    db_session.add_all([p1, p2])
    await db_session.commit()

    # But two prospects with the same siren are rejected.
    p3 = Prospect(search_id=search.id, place_id="ChIJ3", name="C", siren="123456789")
    p4 = Prospect(search_id=search.id, place_id="ChIJ4", name="D", siren="123456789")
    db_session.add_all([p3, p4])
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_prospect_phone_e164_unique_only_when_set(db_session: AsyncSession) -> None:
    user = User(**make_user())
    db_session.add(user)
    await db_session.flush()
    search = Search(owner_id=user.id, query="q", locations=[])
    db_session.add(search)
    await db_session.flush()

    p1 = Prospect(search_id=search.id, place_id="ChIJ5", name="A", phone_e164=None)
    p2 = Prospect(search_id=search.id, place_id="ChIJ6", name="B", phone_e164=None)
    db_session.add_all([p1, p2])
    await db_session.commit()

    p3 = Prospect(search_id=search.id, place_id="ChIJ7", name="C", phone_e164="+33472001122")
    p4 = Prospect(search_id=search.id, place_id="ChIJ8", name="D", phone_e164="+33472001122")
    db_session.add_all([p3, p4])
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_blacklist_requires_siren_or_phone(db_session: AsyncSession) -> None:
    bl = Blacklist(siren=None, phone_e164=None, reason=BlacklistReason.OPT_OUT)
    db_session.add(bl)
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_blacklist_accepts_siren_only(db_session: AsyncSession) -> None:
    bl = Blacklist(siren="987654321", reason=BlacklistReason.COMPETITOR)
    db_session.add(bl)
    await db_session.commit()
    assert bl.id is not None
