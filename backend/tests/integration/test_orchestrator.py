"""End-to-end orchestrator test with mocked external fetchers.

This is the integration scenario described in the spec — a search resolves to
~5 prospects, INSEE/Pappers/socials are mocked, scoring runs, opt-outs are
filtered, and the resulting state is verified directly from the DB.
"""

from __future__ import annotations

import uuid

import pytest
from app.db.models import (
    Blacklist,
    BlacklistReason,
    Prospect,
    ProspectLabel,
    Search,
    SearchStatus,
    User,
)
from app.enrichment.gmaps import GMapsResult
from app.enrichment.insee import InseeMatch
from app.enrichment.orchestrator import EnrichmentDeps, enrich_search
from app.enrichment.pappers import PappersData
from app.enrichment.socials import SocialProfiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import make_user


def _place(idx: int, *, rating: float, reviews: int, phone: str | None) -> GMapsResult:
    return GMapsResult(
        place_id=f"ChIJ{idx}",
        name=f"Acme Travaux {idx}",
        address=f"{idx} rue Garibaldi 69003 Lyon",
        city="Lyon",
        postal_code="69003",
        country="FR",
        lat=45.764,
        lon=4.836,
        phone_raw=phone,
        website=f"https://acme-{idx}.fr",
        gmaps_url=f"https://maps.google.com/?cid={idx}",
        category="Building contractor",
        rating=rating,
        reviews_count=reviews,
        raw={"place_id": f"ChIJ{idx}", "name": f"Acme {idx}"},
    )


@pytest.mark.asyncio
async def test_orchestrator_full_pipeline(db_session: AsyncSession) -> None:
    user = User(**make_user())
    db_session.add(user)
    await db_session.flush()
    search = Search(
        owner_id=user.id,
        query="courtier en travaux",
        locations=[{"city": "Lyon", "postal_code": "69003"}],
        limit=20,
    )
    db_session.add(search)
    await db_session.commit()
    search_id = search.id

    # Pre-fill blacklist: place #2 is opted out via SIREN.
    db_session.add(Blacklist(siren="200000002", reason=BlacklistReason.OPT_OUT))
    await db_session.commit()

    places = [
        _place(1, rating=4.8, reviews=200, phone="0472001122"),
        _place(2, rating=4.5, reviews=80, phone="0472003344"),  # blacklisted
        _place(3, rating=3.5, reviews=10, phone=None),
        _place(4, rating=2.0, reviews=2, phone=None),
        _place(5, rating=5.0, reviews=150, phone="0472005566"),
    ]

    async def fake_places(_keyword: str) -> list[GMapsResult]:
        return places

    async def fake_insee(_name: str, _zip: str | None) -> InseeMatch | None:
        idx = int(_name.split(" ")[-1])
        # Produces "100000001", "200000002", "300000003"...
        siren = f"{idx * 10**8 + idx:09d}"
        return InseeMatch(
            siren=siren,
            legal_name=f"Acme Travaux {idx}",
            legal_form="5710",
            naf_code="4399A",
            director_name="Jean Dupont",
            employees_range="12",
            creation_date=None,
            raw={},
        )

    async def fake_pappers(siren: str) -> PappersData | None:
        return PappersData(
            revenue_eur=1_000_000,
            profit_eur=50_000,
            financials_year=2024,
            employees_count=10,
            raw_html_preview="<html>...</html>",
        )

    async def fake_socials(_website: str) -> SocialProfiles:
        return SocialProfiles(
            facebook_url="https://facebook.com/acme",
            instagram_url=None,
            linkedin_url="https://linkedin.com/acme",
        )

    deps = EnrichmentDeps(
        fetch_places=fake_places,
        fetch_insee=fake_insee,
        fetch_pappers=fake_pappers,
        fetch_socials=fake_socials,
    )

    summary = await enrich_search(search_id, deps=deps)

    # The blacklisted prospect must be skipped, the 4 others persisted.
    assert summary["places_found"] == 5
    assert summary["persisted"] == 4
    assert summary["skipped"] == 1

    db_session.expire_all()
    refreshed = await db_session.get(Search, search_id)
    assert refreshed is not None
    assert refreshed.status == SearchStatus.COMPLETED
    assert refreshed.progress_done == 5
    assert refreshed.progress_total == 5

    result = await db_session.execute(
        select(Prospect).where(Prospect.search_id == search_id).order_by(Prospect.score.desc())
    )
    prospects = list(result.scalars())
    assert len(prospects) == 4
    assert prospects[0].score is not None
    assert prospects[0].score >= prospects[-1].score  # type: ignore[operator]
    # Top prospect (rating 5, 150 reviews, site, phone) hits the Hot bucket.
    assert prospects[0].label is ProspectLabel.HOT
    # All persisted prospects carry SIREN, NAF, financials and at least one social.
    for p in prospects:
        assert p.siren is not None
        assert p.naf_code == "4399A"
        assert p.revenue_eur == 1_000_000
        assert p.facebook_url == "https://facebook.com/acme"
    # The blacklisted SIREN was skipped.
    assert all(p.siren != "200000002" for p in prospects)


@pytest.mark.asyncio
async def test_orchestrator_marks_search_failed_on_gmaps_error(
    db_session: AsyncSession,
) -> None:
    user = User(**make_user())
    db_session.add(user)
    await db_session.flush()
    search = Search(owner_id=user.id, query="boom", locations=[{"city": "Lyon"}])
    db_session.add(search)
    await db_session.commit()
    search_id = search.id

    async def boom(_keyword: str) -> list[GMapsResult]:
        raise RuntimeError("brightdata down")

    async def _no_insee(_n: str, _z: str | None) -> InseeMatch | None:
        return None

    async def _no_pappers(_s: str) -> PappersData | None:
        return None

    async def _no_socials(_w: str) -> SocialProfiles:
        return SocialProfiles(None, None, None)

    deps = EnrichmentDeps(
        fetch_places=boom,
        fetch_insee=_no_insee,
        fetch_pappers=_no_pappers,
        fetch_socials=_no_socials,
    )

    with pytest.raises(RuntimeError, match="brightdata down"):
        await enrich_search(search_id, deps=deps)

    db_session.expire_all()
    refreshed = await db_session.get(Search, search_id)
    assert refreshed is not None
    assert refreshed.status == SearchStatus.FAILED
    assert refreshed.error_message is not None
    assert "brightdata down" in refreshed.error_message


@pytest.mark.asyncio
async def test_orchestrator_idempotent_on_re_run(db_session: AsyncSession) -> None:
    """A second pass over the same search must skip already-persisted place_ids."""
    user = User(**make_user())
    db_session.add(user)
    await db_session.flush()
    search = Search(
        owner_id=user.id, query="kw", locations=[{"city": "Lyon", "postal_code": "69003"}]
    )
    db_session.add(search)
    await db_session.commit()
    search_id = search.id

    async def fake_places(_kw: str) -> list[GMapsResult]:
        return [_place(idx, rating=4.0, reviews=20, phone=None) for idx in range(1, 4)]

    async def _no_insee(_n: str, _z: str | None) -> InseeMatch | None:
        return None

    async def _no_pappers(_s: str) -> PappersData | None:
        return None

    async def _no_socials(_w: str) -> SocialProfiles:
        return SocialProfiles(None, None, None)

    deps = EnrichmentDeps(
        fetch_places=fake_places,
        fetch_insee=_no_insee,
        fetch_pappers=_no_pappers,
        fetch_socials=_no_socials,
    )

    first = await enrich_search(search_id, deps=deps)
    second = await enrich_search(search_id, deps=deps)

    assert first["persisted"] == 3
    assert second["persisted"] == 0  # all 3 already in DB
    # Verify only 3 rows in DB.
    result = await db_session.execute(select(Prospect).where(Prospect.search_id == search_id))
    assert len(list(result.scalars())) == 3


@pytest.mark.asyncio
async def test_unused_uuid_search_id_raises() -> None:
    """A non-existent search id raises ``ValueError``."""
    with pytest.raises(ValueError, match="Unknown search"):
        await enrich_search(uuid.uuid4())
