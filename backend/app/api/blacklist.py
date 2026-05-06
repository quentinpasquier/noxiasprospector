"""Blacklist (opt-out) API.

Every enrichment run consults this table before persisting a prospect, so
adding a SIREN or phone here permanently shields it from future scrapes.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.core.logging import anonymize_phone
from app.db.models import Blacklist
from app.schemas.blacklist import BlacklistCreate, BlacklistPublic

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/blacklist", tags=["blacklist"])


@router.get("", response_model=list[BlacklistPublic])
async def list_entries(db: DbSession, _user: CurrentUser) -> list[BlacklistPublic]:
    """Return every blacklist entry, newest first."""
    result = await db.execute(select(Blacklist).order_by(Blacklist.created_at.desc()))
    return [BlacklistPublic.model_validate(r) for r in result.scalars().all()]


@router.post("", response_model=BlacklistPublic, status_code=status.HTTP_201_CREATED)
async def add_entry(payload: BlacklistCreate, db: DbSession, user: CurrentUser) -> BlacklistPublic:
    """Add a SIREN/phone opt-out. The combination is allowed to repeat
    (we keep history of every block decision)."""
    entry = Blacklist(
        siren=payload.siren,
        phone_e164=payload.phone_e164,
        reason=payload.reason,
        note=payload.note,
        added_by_id=user.id,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    logger.info(
        "blacklist.added",
        entry_id=str(entry.id),
        siren=payload.siren,
        phone=anonymize_phone(payload.phone_e164),
        added_by=user.email,
    )
    return BlacklistPublic.model_validate(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_entry(entry_id: uuid.UUID, db: DbSession, _user: CurrentUser) -> None:
    """Remove a previously added blacklist entry."""
    entry = await db.get(Blacklist, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found.")
    await db.delete(entry)
    await db.commit()
    logger.info("blacklist.removed", entry_id=str(entry_id))
