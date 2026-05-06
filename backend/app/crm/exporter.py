"""Pipedrive exporter with built-in dedup.

For every prospect we:

1. Search Pipedrive persons by ``phone_e164`` — if a hit exists, we mark
   the prospect as a phone-duplicate and skip it.
2. Otherwise search organizations by ``siren`` — duplicate if found.
3. Otherwise create Organization + Person + Deal + Note in one go and
   persist a :class:`PipedriveMapping` row so we never re-export the
   same prospect twice.

The exporter is tested end-to-end with mocked clients via dependency
injection (:class:`ExportDeps`).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.crm.pipedrive import PipedriveClient, SearchHit, build_client
from app.db.models import PipedriveMapping, Prospect, User

logger = structlog.get_logger(__name__)


DuplicateReason = Literal["none", "phone", "siren", "already_exported"]


@dataclass(frozen=True, slots=True)
class DedupResult:
    """Outcome of the dedup check for a single prospect."""

    prospect_id: uuid.UUID
    reason: DuplicateReason
    pipedrive_id: int | None  # which Pipedrive row collided (org or person)


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Per-prospect outcome of an actual export call."""

    prospect_id: uuid.UUID
    status: Literal["created", "skipped", "failed"]
    organization_id: int | None
    person_id: int | None
    deal_id: int | None
    error: str | None = None


# ----- Dependency-injection types --------------------------------------------
ClientFactory = Callable[[], PipedriveClient]
ExistingMappingsLookup = Callable[[list[uuid.UUID]], Awaitable[set[uuid.UUID]]]


@dataclass(frozen=True, slots=True)
class ExportDeps:
    """Pluggable dependencies — used by tests to swap the real client out."""

    client_factory: ClientFactory


def _default_deps() -> ExportDeps:
    return ExportDeps(client_factory=build_client)


# ----- Helpers ---------------------------------------------------------------
async def _existing_mappings(
    session: AsyncSession, prospect_ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    if not prospect_ids:
        return set()
    result = await session.execute(
        select(PipedriveMapping.prospect_id).where(PipedriveMapping.prospect_id.in_(prospect_ids))
    )
    return set(result.scalars())


def _hit_id(hits: list[SearchHit]) -> int | None:
    return hits[0].pipedrive_id if hits else None


# ----- Preview ---------------------------------------------------------------
async def preview_export(
    *,
    session: AsyncSession,
    prospects: list[Prospect],
    deps: ExportDeps | None = None,
) -> list[DedupResult]:
    """Run dedup checks against Pipedrive and return per-prospect verdicts."""
    deps = deps or _default_deps()
    settings = get_settings()
    already = await _existing_mappings(session, [p.id for p in prospects])

    results: list[DedupResult] = []
    async with deps.client_factory() as client:
        for prospect in prospects:
            if prospect.id in already:
                results.append(DedupResult(prospect.id, "already_exported", pipedrive_id=None))
                continue

            # 1. Phone dedup
            if prospect.phone_e164:
                hits = await client.search_persons(term=prospect.phone_e164)
                if hits:
                    results.append(DedupResult(prospect.id, "phone", pipedrive_id=_hit_id(hits)))
                    continue

            # 2. SIREN dedup (only if a custom field key is configured)
            if prospect.siren and settings.PIPEDRIVE_SIREN_FIELD_KEY:
                hits = await client.search_organizations(term=prospect.siren)
                if hits:
                    results.append(DedupResult(prospect.id, "siren", pipedrive_id=_hit_id(hits)))
                    continue

            results.append(DedupResult(prospect.id, "none", pipedrive_id=None))
    return results


# ----- Export ---------------------------------------------------------------
async def export_to_pipedrive(
    *,
    session: AsyncSession,
    prospects: list[Prospect],
    user: User,
    skip_ids: set[uuid.UUID] | None = None,
    deps: ExportDeps | None = None,
) -> list[ExportResult]:
    """Push selected prospects to Pipedrive (skipping duplicates)."""
    deps = deps or _default_deps()
    settings = get_settings()
    skip_ids = skip_ids or set()
    already = await _existing_mappings(session, [p.id for p in prospects])

    results: list[ExportResult] = []
    async with deps.client_factory() as client:
        for prospect in prospects:
            if prospect.id in skip_ids or prospect.id in already:
                results.append(
                    ExportResult(
                        prospect.id,
                        "skipped",
                        organization_id=None,
                        person_id=None,
                        deal_id=None,
                    )
                )
                continue

            # Snapshot the fields we'll need even after a rollback (which
            # would expire ``prospect`` and trigger a lazy reload).
            prospect_id = prospect.id
            try:
                org_id = await client.create_organization(
                    name=prospect.legal_name or prospect.name,
                    siren=prospect.siren,
                    siren_field_key=settings.PIPEDRIVE_SIREN_FIELD_KEY,
                    address=prospect.address,
                )
                person_id = (
                    await client.create_person(
                        name=prospect.director_name or prospect.name,
                        org_id=org_id,
                        phone_e164=prospect.phone_e164,
                    )
                    if prospect.phone_e164 or prospect.director_name
                    else None
                )
                deal_id = await client.create_deal(
                    title=prospect.name,
                    org_id=org_id,
                    person_id=person_id,
                    pipeline_id=settings.PIPEDRIVE_PIPELINE_ID,
                    imported_by_email=user.email,
                    imported_by_field_key=settings.PIPEDRIVE_IMPORTED_BY_FIELD_KEY,
                )
                note_lines = [
                    f"NoxiasProspect — score {prospect.score} ({prospect.label}).",
                    f"GMaps : {prospect.gmaps_url}" if prospect.gmaps_url else "",
                    f"Site : {prospect.website}" if prospect.website else "",
                    f"SIREN : {prospect.siren}" if prospect.siren else "",
                    f"NAF : {prospect.naf_code}" if prospect.naf_code else "",
                ]
                note_id = await client.create_note(
                    content="\n".join(line for line in note_lines if line),
                    deal_id=deal_id,
                )

                mapping = PipedriveMapping(
                    prospect_id=prospect_id,
                    pipedrive_organization_id=org_id,
                    pipedrive_person_id=person_id,
                    pipedrive_deal_id=deal_id,
                    pipedrive_note_id=note_id,
                    exported_by_id=user.id,
                    exported_by_email=user.email,
                )
                session.add(mapping)
                await session.commit()

                results.append(
                    ExportResult(
                        prospect_id,
                        "created",
                        organization_id=org_id,
                        person_id=person_id,
                        deal_id=deal_id,
                    )
                )
                logger.info(
                    "pipedrive.exported",
                    prospect_id=str(prospect_id),
                    org_id=org_id,
                    deal_id=deal_id,
                )
            except Exception as exc:
                await session.rollback()
                logger.warning(
                    "pipedrive.export_failed",
                    prospect_id=str(prospect_id),
                    error=str(exc),
                )
                results.append(
                    ExportResult(
                        prospect_id,
                        "failed",
                        organization_id=None,
                        person_id=None,
                        deal_id=None,
                        error=str(exc)[:300],
                    )
                )

    return results
