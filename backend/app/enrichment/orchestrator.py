"""End-to-end enrichment pipeline.

Given a :class:`Search` row in ``pending`` status, the orchestrator:

1. Marks the search ``running``.
2. For every keyword × location combination, calls Bright Data to fetch
   Google Maps places.
3. De-duplicates by ``place_id`` against existing prospects.
4. For each new place, runs INSEE → Pappers → socials in parallel
   (sub-tasks gated by a semaphore = ``ENRICHMENT_MAX_CONCURRENCY``).
5. Filters opt-outs via the :mod:`app.enrichment.blacklist` lookup.
6. Computes a score + label and persists the prospect.
7. Updates ``progress_done`` after each batch so the SSE endpoint can stream
   live progress to the front.
8. Marks the search ``completed`` (or ``failed`` on unrecoverable error).

Each external dependency is injected as a callable so tests can substitute
mock fetchers without monkey-patching the modules.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import structlog
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db import session as _db_session
from app.db.models import Prospect, Search, SearchStatus
from app.enrichment import gmaps as gmaps_module
from app.enrichment import insee as insee_module
from app.enrichment import pappers as pappers_module
from app.enrichment import socials as socials_module
from app.enrichment.blacklist import is_blacklisted
from app.enrichment.gmaps import GMapsResult
from app.enrichment.insee import InseeMatch
from app.enrichment.pappers import PappersData
from app.enrichment.phone import to_e164
from app.enrichment.scoring import label_for, score_prospect
from app.enrichment.socials import SocialProfiles

logger = structlog.get_logger(__name__)


# ----- Dependency-injection types --------------------------------------------
GMapsFetcher = Callable[[str], Awaitable[list[GMapsResult]]]
InseeFetcher = Callable[[str, str | None], Awaitable[InseeMatch | None]]
PappersFetcher = Callable[[str], Awaitable[PappersData | None]]
SocialsFetcher = Callable[[str], Awaitable[SocialProfiles]]


@dataclass(frozen=True, slots=True)
class EnrichmentDeps:
    """Pluggable enrichment fetchers — useful for tests."""

    fetch_places: GMapsFetcher
    fetch_insee: InseeFetcher
    fetch_pappers: PappersFetcher
    fetch_socials: SocialsFetcher


def _default_deps() -> EnrichmentDeps:
    """Wire the real Bright Data / API gouv clients."""
    return EnrichmentDeps(
        fetch_places=gmaps_module.fetch_places,
        fetch_insee=lambda name, zip_: insee_module.find_company(name=name, postal_code=zip_),
        fetch_pappers=pappers_module.fetch_pappers,
        fetch_socials=socials_module.fetch_socials,
    )


def _build_keywords(query: str, locations: list[dict[str, str]]) -> list[str]:
    """Cartesian product ``query × city`` to build Bright Data inputs."""
    if not locations:
        return [query]
    return [f"{query} {loc.get('city', '').strip()}".strip() for loc in locations]


# ----- Per-place pipeline ----------------------------------------------------
async def _enrich_one(
    place: GMapsResult,
    deps: EnrichmentDeps,
) -> dict[str, object]:
    """Run INSEE + Pappers + socials in parallel for a single GMaps place."""
    insee_task = deps.fetch_insee(place.name, place.postal_code)
    socials_task = deps.fetch_socials(place.website) if place.website else _none_socials()

    insee, socials = await asyncio.gather(insee_task, socials_task)

    pappers: PappersData | None = None
    if insee and insee.siren:
        pappers = await deps.fetch_pappers(insee.siren)

    return {
        "insee": insee,
        "pappers": pappers,
        "socials": socials,
    }


async def _none_socials() -> SocialProfiles:
    return SocialProfiles(None, None, None)


# ----- DB persistence -------------------------------------------------------
async def _persist(
    session: AsyncSession,
    *,
    search_id: uuid.UUID,
    place: GMapsResult,
    enrichments: dict[str, object],
) -> Prospect | None:
    """Persist a prospect, returning ``None`` if blacklisted or duplicate."""
    insee = enrichments.get("insee")
    pappers = enrichments.get("pappers")
    socials = enrichments.get("socials")
    assert socials is None or isinstance(socials, SocialProfiles)

    phone_e164 = to_e164(place.phone_raw)
    siren = insee.siren if isinstance(insee, InseeMatch) else None

    if await is_blacklisted(session, siren=siren, phone_e164=phone_e164):
        logger.info(
            "orchestrator.skip.blacklist",
            place_id=place.place_id,
            siren=siren,
        )
        return None

    score = score_prospect(
        rating=place.rating,
        reviews_count=place.reviews_count,
        has_website=bool(place.website),
        has_phone=bool(phone_e164),
    )

    prospect = Prospect(
        search_id=search_id,
        place_id=place.place_id,
        name=place.name,
        address=place.address,
        city=place.city,
        postal_code=place.postal_code,
        country=place.country,
        lat=place.lat,
        lon=place.lon,
        phone_raw=place.phone_raw,
        phone_e164=phone_e164,
        website=place.website,
        gmaps_url=place.gmaps_url,
        category=place.category,
        rating=place.rating,
        reviews_count=place.reviews_count,
        siren=siren,
        naf_code=insee.naf_code if isinstance(insee, InseeMatch) else None,
        legal_name=insee.legal_name if isinstance(insee, InseeMatch) else None,
        legal_form=insee.legal_form if isinstance(insee, InseeMatch) else None,
        creation_date=insee.creation_date if isinstance(insee, InseeMatch) else None,
        director_name=insee.director_name if isinstance(insee, InseeMatch) else None,
        employees_range=insee.employees_range if isinstance(insee, InseeMatch) else None,
        revenue_eur=pappers.revenue_eur if isinstance(pappers, PappersData) else None,
        profit_eur=pappers.profit_eur if isinstance(pappers, PappersData) else None,
        financials_year=pappers.financials_year if isinstance(pappers, PappersData) else None,
        facebook_url=socials.facebook_url if isinstance(socials, SocialProfiles) else None,
        instagram_url=socials.instagram_url if isinstance(socials, SocialProfiles) else None,
        linkedin_url=socials.linkedin_url if isinstance(socials, SocialProfiles) else None,
        score=score,
        label=label_for(score),
        raw_gmaps=place.raw,
        raw_insee=insee.raw if isinstance(insee, InseeMatch) else None,
        raw_pappers=(
            {"preview": pappers.raw_html_preview} if isinstance(pappers, PappersData) else None
        ),
    )
    session.add(prospect)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        logger.info("orchestrator.skip.duplicate", place_id=place.place_id, siren=siren)
        return None
    await session.refresh(prospect)
    return prospect


# ----- Public entrypoints ---------------------------------------------------
async def enrich_search(
    search_id: uuid.UUID,
    *,
    deps: EnrichmentDeps | None = None,
) -> dict[str, int]:
    """Run the full pipeline for ``search_id`` and return summary counts.

    Args:
        search_id: The :class:`Search` UUID; must already exist in DB.
        deps: Override fetchers (used by tests).

    Returns:
        Dict with ``places_found``, ``persisted``, ``skipped``.
    """
    deps = deps or _default_deps()

    async with _db_session.AsyncSessionLocal() as session:
        search = await session.get(Search, search_id)
        if search is None:
            raise ValueError(f"Unknown search {search_id}")
        keywords = _build_keywords(search.query, list(search.locations or []))
        await session.execute(
            update(Search)
            .where(Search.id == search_id)
            .values(status=SearchStatus.RUNNING, progress_total=0, progress_done=0)
        )
        await session.commit()

    settings = get_settings()
    semaphore = asyncio.Semaphore(settings.ENRICHMENT_MAX_CONCURRENCY)
    persisted = 0
    skipped = 0
    seen_place_ids: set[str] = set()

    try:
        all_places: list[GMapsResult] = []
        for keyword in keywords:
            places = await deps.fetch_places(keyword)
            all_places.extend(places)

        # Cross-keyword de-dup: keep first occurrence of each place_id.
        unique_places: list[GMapsResult] = []
        for place in all_places:
            if place.place_id in seen_place_ids:
                continue
            seen_place_ids.add(place.place_id)
            unique_places.append(place)

        # Drop place_ids already persisted in earlier runs of this search.
        async with _db_session.AsyncSessionLocal() as session:
            existing = await session.execute(
                select(Prospect.place_id).where(Prospect.search_id == search_id)
            )
            existing_ids = set(existing.scalars())
        unique_places = [p for p in unique_places if p.place_id not in existing_ids]

        async with _db_session.AsyncSessionLocal() as session:
            await session.execute(
                update(Search)
                .where(Search.id == search_id)
                .values(progress_total=len(unique_places))
            )
            await session.commit()

        async def _run_one(place: GMapsResult) -> None:
            nonlocal persisted, skipped
            async with semaphore:
                enrichments = await _enrich_one(place, deps)
            async with _db_session.AsyncSessionLocal() as session:
                prospect = await _persist(
                    session, search_id=search_id, place=place, enrichments=enrichments
                )
                if prospect is None:
                    skipped += 1
                else:
                    persisted += 1
                await session.execute(
                    update(Search)
                    .where(Search.id == search_id)
                    .values(progress_done=persisted + skipped)
                )
                await session.commit()

        await asyncio.gather(*(_run_one(p) for p in unique_places))

        async with _db_session.AsyncSessionLocal() as session:
            await session.execute(
                update(Search).where(Search.id == search_id).values(status=SearchStatus.COMPLETED)
            )
            await session.commit()

    except Exception as exc:
        logger.exception("orchestrator.failed", search_id=str(search_id))
        async with _db_session.AsyncSessionLocal() as session:
            await session.execute(
                update(Search)
                .where(Search.id == search_id)
                .values(status=SearchStatus.FAILED, error_message=str(exc)[:500])
            )
            await session.commit()
        raise

    summary = {
        "places_found": len(seen_place_ids),
        "persisted": persisted,
        "skipped": skipped,
    }
    logger.info("orchestrator.done", search_id=str(search_id), **summary)
    return summary
