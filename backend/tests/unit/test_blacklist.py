"""Tests for the blacklist lookup helper."""

from __future__ import annotations

import pytest
from app.db.models import Blacklist, BlacklistReason
from app.enrichment.blacklist import is_blacklisted
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_returns_false_when_no_match(db_session: AsyncSession) -> None:
    found = await is_blacklisted(db_session, siren="123456789", phone_e164="+33472001122")
    assert found is False


@pytest.mark.asyncio
async def test_match_by_siren(db_session: AsyncSession) -> None:
    db_session.add(Blacklist(siren="123456789", reason=BlacklistReason.OPT_OUT))
    await db_session.commit()
    assert await is_blacklisted(db_session, siren="123456789", phone_e164=None) is True


@pytest.mark.asyncio
async def test_match_by_phone(db_session: AsyncSession) -> None:
    db_session.add(Blacklist(phone_e164="+33472001122", reason=BlacklistReason.OPT_OUT))
    await db_session.commit()
    assert await is_blacklisted(db_session, siren=None, phone_e164="+33472001122") is True


@pytest.mark.asyncio
async def test_no_inputs_returns_false(db_session: AsyncSession) -> None:
    assert await is_blacklisted(db_session, siren=None, phone_e164=None) is False
