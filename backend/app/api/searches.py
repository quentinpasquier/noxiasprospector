"""Searches API — create / read / list / SSE progress."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

import structlog
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.db.models import Prospect, Search
from app.schemas.prospect import ProspectPublic
from app.schemas.search import SearchCreate, SearchPublic

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/searches", tags=["searches"])


@router.post("", response_model=SearchPublic, status_code=status.HTTP_201_CREATED)
async def create_search(payload: SearchCreate, db: DbSession, user: CurrentUser) -> SearchPublic:
    """Persist the search request and enqueue the enrichment job."""
    search = Search(
        owner_id=user.id,
        query=payload.query,
        locations=[loc.model_dump() for loc in payload.locations],
        limit=payload.limit,
        preset=payload.preset,
    )
    db.add(search)
    await db.commit()
    await db.refresh(search)

    settings = get_settings()
    try:
        pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        try:
            await pool.enqueue_job("run_search_enrichment", str(search.id))
        finally:
            await pool.close()
    except Exception as exc:  # pragma: no cover - infra failure path
        logger.warning("searches.enqueue_failed", search_id=str(search.id), error=str(exc))

    return SearchPublic.model_validate(search)


@router.get("", response_model=list[SearchPublic])
async def list_searches(db: DbSession, user: CurrentUser) -> list[SearchPublic]:
    """Return the authenticated user's searches, newest first."""
    result = await db.execute(
        select(Search).where(Search.owner_id == user.id).order_by(Search.created_at.desc())
    )
    return [SearchPublic.model_validate(s) for s in result.scalars().all()]


@router.get("/{search_id}", response_model=SearchPublic)
async def get_search(search_id: uuid.UUID, db: DbSession, user: CurrentUser) -> SearchPublic:
    search = await db.get(Search, search_id)
    if search is None or search.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Search not found.")
    return SearchPublic.model_validate(search)


@router.get("/{search_id}/prospects", response_model=list[ProspectPublic])
async def list_prospects(
    search_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> list[ProspectPublic]:
    search = await db.get(Search, search_id)
    if search is None or search.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Search not found.")
    result = await db.execute(
        select(Prospect)
        .where(Prospect.search_id == search_id)
        .order_by(Prospect.score.desc().nullslast(), Prospect.created_at.desc())
    )
    return [ProspectPublic.model_validate(p) for p in result.scalars().all()]


@router.get("/{search_id}/events")
async def stream_progress(
    search_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> StreamingResponse:
    """Server-Sent Events stream that emits progress until the search is done."""
    search = await db.get(Search, search_id)
    if search is None or search.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Search not found.")

    async def _events() -> AsyncIterator[str]:
        from app.db.session import AsyncSessionLocal

        last_payload: str | None = None
        while True:
            async with AsyncSessionLocal() as session:
                current = await session.get(Search, search_id)
                if current is None:
                    break
                payload = {
                    "status": str(current.status),
                    "progress_done": current.progress_done,
                    "progress_total": current.progress_total,
                    "error_message": current.error_message,
                }
            data = json.dumps(payload)
            if data != last_payload:
                yield f"event: progress\ndata: {data}\n\n"
                last_payload = data
            if payload["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(2)

    return StreamingResponse(_events(), media_type="text/event-stream")
