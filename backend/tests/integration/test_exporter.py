"""End-to-end exporter tests with a fake Pipedrive client."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

import pytest
from app.crm.exporter import ExportDeps, export_to_pipedrive, preview_export
from app.crm.pipedrive import SearchHit
from app.db.models import PipedriveMapping, Prospect, Search, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import make_user


class FakePipedriveClient:
    """In-memory stub that records every call."""

    def __init__(
        self,
        *,
        person_hits_by_term: dict[str, list[SearchHit]] | None = None,
        org_hits_by_term: dict[str, list[SearchHit]] | None = None,
    ) -> None:
        self.person_hits = person_hits_by_term or {}
        self.org_hits = org_hits_by_term or {}
        self.created: list[dict[str, Any]] = []
        self._next_id = 1000

    async def __aenter__(self) -> FakePipedriveClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        return

    def _next(self) -> int:
        self._next_id += 1
        return self._next_id

    async def search_persons(self, *, term: str, fields: str | None = None) -> list[SearchHit]:
        return self.person_hits.get(term, [])

    async def search_organizations(
        self, *, term: str, fields: str | None = None
    ) -> list[SearchHit]:
        return self.org_hits.get(term, [])

    async def create_organization(self, **kwargs: Any) -> int:
        self.created.append({"kind": "org", **kwargs})
        return self._next()

    async def create_person(self, **kwargs: Any) -> int:
        self.created.append({"kind": "person", **kwargs})
        return self._next()

    async def create_deal(self, **kwargs: Any) -> int:
        self.created.append({"kind": "deal", **kwargs})
        return self._next()

    async def create_note(self, **kwargs: Any) -> int:
        self.created.append({"kind": "note", **kwargs})
        return self._next()


def _deps_for(client: FakePipedriveClient) -> ExportDeps:
    @asynccontextmanager
    async def _factory_cm() -> Any:  # pragma: no cover  -- used by export_to_pipedrive
        async with client as c:
            yield c

    # The exporter uses ``async with deps.client_factory()``; passing the
    # FakePipedriveClient itself works because it implements __aenter__/__aexit__.
    return ExportDeps(client_factory=lambda: client)


async def _seed_search(db: AsyncSession, *, prospects: list[dict[str, Any]]) -> tuple[Search, User]:
    user = User(**make_user())
    db.add(user)
    await db.flush()
    search = Search(owner_id=user.id, query="kw", locations=[{"city": "Lyon"}])
    db.add(search)
    await db.flush()
    for fields in prospects:
        db.add(Prospect(search_id=search.id, **fields))
    await db.commit()
    return search, user


@pytest.mark.asyncio
async def test_preview_marks_phone_duplicates(db_session: AsyncSession) -> None:
    search, _user = await _seed_search(
        db_session,
        prospects=[
            {"place_id": "p1", "name": "Acme 1", "phone_e164": "+33472001111"},
            {"place_id": "p2", "name": "Acme 2", "phone_e164": "+33472002222"},
            {"place_id": "p3", "name": "Acme 3", "phone_e164": None},
        ],
    )
    result = await db_session.execute(select(Prospect).where(Prospect.search_id == search.id))
    prospects = list(result.scalars())

    fake = FakePipedriveClient(
        person_hits_by_term={"+33472001111": [SearchHit(pipedrive_id=42, name="Old Acme", raw={})]}
    )
    verdicts = await preview_export(session=db_session, prospects=prospects, deps=_deps_for(fake))

    by_id = {v.prospect_id: v for v in verdicts}
    p1 = next(p for p in prospects if p.place_id == "p1")
    p2 = next(p for p in prospects if p.place_id == "p2")
    p3 = next(p for p in prospects if p.place_id == "p3")
    assert by_id[p1.id].reason == "phone"
    assert by_id[p1.id].pipedrive_id == 42
    assert by_id[p2.id].reason == "none"
    assert by_id[p3.id].reason == "none"


@pytest.mark.asyncio
async def test_preview_flags_already_exported(db_session: AsyncSession) -> None:
    search, _user = await _seed_search(
        db_session,
        prospects=[{"place_id": "px", "name": "Acme", "phone_e164": "+33400000000"}],
    )
    prospects = list(
        (
            await db_session.execute(select(Prospect).where(Prospect.search_id == search.id))
        ).scalars()
    )
    db_session.add(
        PipedriveMapping(
            prospect_id=prospects[0].id,
            pipedrive_organization_id=1,
            pipedrive_deal_id=2,
        )
    )
    await db_session.commit()

    fake = FakePipedriveClient()
    verdicts = await preview_export(session=db_session, prospects=prospects, deps=_deps_for(fake))
    assert verdicts[0].reason == "already_exported"


@pytest.mark.asyncio
async def test_export_creates_org_person_deal_note_and_mapping(
    db_session: AsyncSession,
) -> None:
    search, user = await _seed_search(
        db_session,
        prospects=[
            {
                "place_id": "p1",
                "name": "Acme Travaux",
                "legal_name": "Acme Travaux SAS",
                "phone_e164": "+33472001122",
                "siren": "123456789",
                "naf_code": "4399A",
                "address": "12 rue Garibaldi",
                "score": 87,
                "label": "Hot",
                "gmaps_url": "https://maps.google.com/?cid=1",
                "website": "https://acme.fr",
                "director_name": "Jean Dupont",
            },
        ],
    )
    prospects = list(
        (
            await db_session.execute(select(Prospect).where(Prospect.search_id == search.id))
        ).scalars()
    )

    fake = FakePipedriveClient()
    results = await export_to_pipedrive(
        session=db_session,
        prospects=prospects,
        user=user,
        deps=_deps_for(fake),
    )
    assert len(results) == 1
    assert results[0].status == "created"
    assert results[0].organization_id is not None
    assert results[0].deal_id is not None

    kinds = [c["kind"] for c in fake.created]
    assert kinds == ["org", "person", "deal", "note"]

    # Note content includes score + GMaps + SIREN + NAF.
    note = next(c for c in fake.created if c["kind"] == "note")
    assert "score 87" in note["content"]
    assert "SIREN : 123456789" in note["content"]
    assert "NAF : 4399A" in note["content"]
    assert "Hot" in note["content"]

    # Mapping persisted.
    mapping = (
        await db_session.execute(
            select(PipedriveMapping).where(PipedriveMapping.prospect_id == prospects[0].id)
        )
    ).scalar_one()
    assert mapping.pipedrive_organization_id is not None
    assert mapping.exported_by_email == user.email


@pytest.mark.asyncio
async def test_export_skips_listed_prospects(db_session: AsyncSession) -> None:
    search, user = await _seed_search(
        db_session,
        prospects=[
            {"place_id": "p1", "name": "Keep me", "phone_e164": "+33400000001"},
            {"place_id": "p2", "name": "Skip me", "phone_e164": "+33400000002"},
        ],
    )
    prospects = list(
        (
            await db_session.execute(select(Prospect).where(Prospect.search_id == search.id))
        ).scalars()
    )
    skip_id = next(p for p in prospects if p.place_id == "p2").id

    fake = FakePipedriveClient()
    results = await export_to_pipedrive(
        session=db_session,
        prospects=prospects,
        user=user,
        skip_ids={skip_id},
        deps=_deps_for(fake),
    )
    by_id = {r.prospect_id: r for r in results}
    assert by_id[skip_id].status == "skipped"
    assert by_id[next(p.id for p in prospects if p.place_id == "p1")].status == "created"
    # Only one org created.
    assert sum(1 for c in fake.created if c["kind"] == "org") == 1


@pytest.mark.asyncio
async def test_export_failure_records_error(db_session: AsyncSession) -> None:
    search, user = await _seed_search(
        db_session,
        prospects=[{"place_id": "p1", "name": "Bad"}],
    )
    prospects = list(
        (
            await db_session.execute(select(Prospect).where(Prospect.search_id == search.id))
        ).scalars()
    )

    class Boom(FakePipedriveClient):
        async def create_organization(self, **kwargs: Any) -> int:
            raise RuntimeError("pipedrive 500")

    fake = Boom()
    results = await export_to_pipedrive(
        session=db_session, prospects=prospects, user=user, deps=_deps_for(fake)
    )
    assert results[0].status == "failed"
    assert results[0].error is not None
    assert "pipedrive 500" in results[0].error
    # No mapping persisted.
    count = (await db_session.execute(select(PipedriveMapping))).scalars().all()
    assert count == []


@pytest.mark.asyncio
async def test_export_idempotent_after_existing_mapping(
    db_session: AsyncSession,
) -> None:
    """A prospect already mapped to Pipedrive must be reported as skipped."""
    search, user = await _seed_search(db_session, prospects=[{"place_id": "p1", "name": "Acme"}])
    prospects = list(
        (
            await db_session.execute(select(Prospect).where(Prospect.search_id == search.id))
        ).scalars()
    )
    db_session.add(
        PipedriveMapping(
            prospect_id=prospects[0].id,
            pipedrive_organization_id=999,
            pipedrive_deal_id=1000,
        )
    )
    await db_session.commit()

    # Running export again must not call Pipedrive nor create a duplicate row.
    fake = FakePipedriveClient()
    results = await export_to_pipedrive(
        session=db_session, prospects=prospects, user=user, deps=_deps_for(fake)
    )
    assert results[0].status == "skipped"
    assert fake.created == []


@pytest.mark.asyncio
async def test_unused_uuid_passes_through() -> None:
    """A truly empty list yields an empty result set."""
    fake = FakePipedriveClient()
    # No DB session used — exporter must not query when prospects is empty.
    fake_id = uuid.uuid4()  # noqa: F841 -- only for type assertion below

    # Just calling preview_export with an empty list against a no-op client.
    # We do this via a real (empty) DB session-less invocation by passing []:
    # The exporter calls _existing_mappings which short-circuits on []...
    # so we don't need the session at all for empty input.
    class _NoopSession:
        async def execute(self, *_: object, **__: object) -> Any:
            raise AssertionError("session.execute should not be called for empty list")

    result = await preview_export(
        session=_NoopSession(),  # type: ignore[arg-type]
        prospects=[],
        deps=_deps_for(fake),
    )
    assert result == []
