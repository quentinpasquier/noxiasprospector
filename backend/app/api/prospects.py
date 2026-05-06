"""Prospect detail endpoint — used by the frontend to render `/prospects/{id}`."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.core.deps import CurrentUser, DbSession
from app.db.models import Prospect, Search
from app.schemas.prospect import ProspectPublic

router = APIRouter(prefix="/prospects", tags=["prospects"])


@router.get("/{prospect_id}", response_model=ProspectPublic)
async def get_prospect(
    prospect_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> ProspectPublic:
    """Return the prospect if it belongs to a search owned by the caller."""
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status_code=404, detail="Prospect not found.")

    parent = await db.get(Search, prospect.search_id)
    if parent is None or parent.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Prospect not found.")

    return ProspectPublic.model_validate(prospect)
