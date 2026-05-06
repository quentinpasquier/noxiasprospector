"""Pipedrive export endpoints (preview + execute)."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.crm.exporter import export_to_pipedrive, preview_export
from app.crm.pipedrive import PipedriveError
from app.db.models import Prospect, Search
from app.schemas.export import (
    ExportPreview,
    ExportPreviewItem,
    ExportRequest,
    ExportResponse,
    ExportResultItem,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/searches", tags=["exports"])


async def _load_search_prospects(
    db: DbSession, search_id: uuid.UUID, user_id: uuid.UUID
) -> list[Prospect]:
    """Fetch prospects for a search owned by ``user_id`` or raise 404."""
    search = await db.get(Search, search_id)
    if search is None or search.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Search not found.")
    result = await db.execute(
        select(Prospect)
        .where(Prospect.search_id == search_id)
        .order_by(Prospect.score.desc().nullslast())
    )
    return list(result.scalars())


def _check_pipedrive_configured() -> None:
    s = get_settings()
    if not s.PIPEDRIVE_API_TOKEN or not s.PIPEDRIVE_COMPANY_DOMAIN:
        raise HTTPException(
            status_code=503,
            detail=(
                "Pipedrive integration not configured. "
                "Set PIPEDRIVE_API_TOKEN and PIPEDRIVE_COMPANY_DOMAIN."
            ),
        )


@router.post("/{search_id}/exports/pipedrive/preview", response_model=ExportPreview)
async def preview_pipedrive_export(
    search_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> ExportPreview:
    """Return per-prospect duplicate-status flags without writing to Pipedrive."""
    _check_pipedrive_configured()
    prospects = await _load_search_prospects(db, search_id, user.id)
    try:
        verdicts = await preview_export(session=db, prospects=prospects)
    except PipedriveError as exc:
        raise HTTPException(status_code=502, detail=f"Pipedrive: {exc}") from exc

    by_id = {p.id: p for p in prospects}
    items = [
        ExportPreviewItem(
            prospect_id=v.prospect_id,
            name=by_id[v.prospect_id].name,
            siren=by_id[v.prospect_id].siren,
            phone_e164=by_id[v.prospect_id].phone_e164,
            duplicate_reason=v.reason,
            duplicate_pipedrive_id=v.pipedrive_id,
        )
        for v in verdicts
    ]
    return ExportPreview(items=items)


@router.post("/{search_id}/exports/pipedrive", response_model=ExportResponse)
async def run_pipedrive_export(
    search_id: uuid.UUID,
    payload: ExportRequest,
    db: DbSession,
    user: CurrentUser,
) -> ExportResponse:
    """Push prospects to Pipedrive (with org/person/deal/note + dedup mapping)."""
    _check_pipedrive_configured()
    prospects = await _load_search_prospects(db, search_id, user.id)
    skip_ids = set(payload.skip_prospect_ids)

    try:
        results = await export_to_pipedrive(
            session=db, prospects=prospects, user=user, skip_ids=skip_ids
        )
    except PipedriveError as exc:
        raise HTTPException(status_code=502, detail=f"Pipedrive: {exc}") from exc

    created = sum(1 for r in results if r.status == "created")
    skipped = sum(1 for r in results if r.status == "skipped")
    failed = sum(1 for r in results if r.status == "failed")
    logger.info(
        "exports.done",
        search_id=str(search_id),
        created=created,
        skipped=skipped,
        failed=failed,
    )
    return ExportResponse(
        created=created,
        skipped=skipped,
        failed=failed,
        items=[
            ExportResultItem(
                prospect_id=r.prospect_id,
                status=r.status,
                organization_id=r.organization_id,
                person_id=r.person_id,
                deal_id=r.deal_id,
                error=r.error,
            )
            for r in results
        ],
    )
