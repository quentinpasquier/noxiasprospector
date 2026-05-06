"""Prospect endpoints — read + RGPD-compliant deletion.

`DELETE /prospects/{id}` cascades:

1. Delete the linked Pipedrive Organization / Person / Deal (if any).
2. Insert a :class:`Blacklist` row so future enrichments will skip the
   same SIREN / phone (auto opt-out, RGPD art. 21).
3. Insert a :class:`DeletionLog` row kept three years for audit (RGPD
   accountability — purgeable by an external job after that).
4. Delete the :class:`Prospect` row from our DB.

Pipedrive failures are tolerated (logged + 207-style note) so we never
leave orphaned rows in our DB once the user has clicked "supprimer".
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.core.logging import anonymize_phone
from app.crm.pipedrive import PipedriveError, build_client
from app.db.models import (
    Blacklist,
    BlacklistReason,
    DeletionLog,
    DeletionReason,
    PipedriveMapping,
    Prospect,
    Search,
)
from app.schemas.prospect import ProspectPublic

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/prospects", tags=["prospects"])


@router.get("/{prospect_id}", response_model=ProspectPublic)
async def get_prospect(prospect_id: uuid.UUID, db: DbSession, user: CurrentUser) -> ProspectPublic:
    """Return the prospect if it belongs to a search owned by the caller."""
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status_code=404, detail="Prospect not found.")

    parent = await db.get(Search, prospect.search_id)
    if parent is None or parent.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Prospect not found.")

    return ProspectPublic.model_validate(prospect)


@router.delete("/{prospect_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prospect(prospect_id: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    """Delete a prospect from DB + Pipedrive and add it to the blacklist."""
    prospect = await db.get(Prospect, prospect_id)
    if prospect is None:
        raise HTTPException(status_code=404, detail="Prospect not found.")

    parent = await db.get(Search, prospect.search_id)
    if parent is None or parent.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Prospect not found.")

    # Snapshot identifiers before any cascade.
    siren = prospect.siren
    phone = prospect.phone_e164
    name = prospect.name

    # 1. Best-effort Pipedrive deletion.
    pipedrive_err: str | None = None
    org_id: int | None = None
    deal_id: int | None = None
    mapping_result = await db.execute(
        select(PipedriveMapping).where(PipedriveMapping.prospect_id == prospect_id)
    )
    mapping = mapping_result.scalar_one_or_none()
    if mapping:
        org_id = mapping.pipedrive_organization_id
        deal_id = mapping.pipedrive_deal_id
        s = get_settings()
        if s.PIPEDRIVE_API_TOKEN and s.PIPEDRIVE_COMPANY_DOMAIN:
            try:
                async with build_client() as pd:
                    if mapping.pipedrive_deal_id:
                        await pd.delete_deal(mapping.pipedrive_deal_id)
                    if mapping.pipedrive_person_id:
                        await pd.delete_person(mapping.pipedrive_person_id)
                    if mapping.pipedrive_organization_id:
                        await pd.delete_organization(mapping.pipedrive_organization_id)
            except PipedriveError as exc:
                pipedrive_err = str(exc)[:300]
                logger.warning(
                    "prospect.delete.pipedrive_failed",
                    prospect_id=str(prospect_id),
                    error=pipedrive_err,
                )

    # 2. Auto-blacklist on user request — shields future scrapes.
    if siren or phone:
        db.add(
            Blacklist(
                siren=siren,
                phone_e164=phone,
                reason=BlacklistReason.OPT_OUT,
                added_by_id=user.id,
                note=f"Auto-blacklisted on prospect deletion (id={prospect_id}).",
            )
        )

    # 3. RGPD audit row — kept 3 years, identifiers minimised.
    db.add(
        DeletionLog(
            siren=siren,
            phone_last4=phone[-4:] if phone else None,
            name=name,
            reason=DeletionReason.USER_REQUEST,
            note=(f"Pipedrive cleanup error: {pipedrive_err}" if pipedrive_err else None),
            deleted_by_id=user.id,
            deleted_by_email=user.email,
            pipedrive_organization_id=org_id,
            pipedrive_deal_id=deal_id,
        )
    )

    # 4. Local delete (cascades to PipedriveMapping via FK).
    await db.delete(prospect)
    await db.commit()

    logger.info(
        "prospect.deleted",
        prospect_id=str(prospect_id),
        siren=siren,
        phone=anonymize_phone(phone),
        deleted_by=user.email,
        pipedrive_err=pipedrive_err,
    )
