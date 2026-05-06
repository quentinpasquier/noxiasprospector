"""Blacklist lookup helpers.

The opt-out registry is consulted *before* any prospect is persisted. We
match against ``siren`` (most reliable) and ``phone_e164`` (covers cases
where the company changes name/legal form).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Blacklist


async def is_blacklisted(
    session: AsyncSession,
    *,
    siren: str | None,
    phone_e164: str | None,
) -> bool:
    """Return ``True`` if either ``siren`` or ``phone_e164`` is opted-out."""
    if not siren and not phone_e164:
        return False

    conditions = []
    if siren:
        conditions.append(Blacklist.siren == siren)
    if phone_e164:
        conditions.append(Blacklist.phone_e164 == phone_e164)

    from sqlalchemy import or_

    stmt = select(Blacklist.id).where(or_(*conditions)).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None
