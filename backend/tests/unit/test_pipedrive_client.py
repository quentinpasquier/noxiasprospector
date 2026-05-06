"""Tests for the typed Pipedrive client (HTTP layer)."""

from __future__ import annotations

import httpx
import pytest
import respx
from app.crm.pipedrive import PipedriveClient, PipedriveError

BASE = "https://noxias.pipedrive.com/v1"


@pytest.mark.asyncio
async def test_search_persons_returns_hits() -> None:
    payload = {
        "data": {
            "items": [
                {"item": {"id": 42, "name": "Jean Dupont"}},
                {"item": {"id": 43, "name": "Marc Martin"}},
            ]
        }
    }
    async with respx.mock(base_url=BASE) as router:
        router.get("/persons/search").mock(return_value=httpx.Response(200, json=payload))
        async with PipedriveClient(api_token="x", company_domain="noxias") as client:
            hits = await client.search_persons(term="+33472001122")
    assert [h.pipedrive_id for h in hits] == [42, 43]
    assert hits[0].name == "Jean Dupont"


@pytest.mark.asyncio
async def test_search_organizations_returns_empty_when_no_match() -> None:
    async with respx.mock(base_url=BASE) as router:
        router.get("/organizations/search").mock(
            return_value=httpx.Response(200, json={"data": {"items": []}})
        )
        async with PipedriveClient(api_token="x", company_domain="noxias") as client:
            hits = await client.search_organizations(term="000000000")
    assert hits == []


@pytest.mark.asyncio
async def test_create_organization_returns_id() -> None:
    async with respx.mock(base_url=BASE) as router:
        router.post("/organizations").mock(
            return_value=httpx.Response(201, json={"data": {"id": 9001, "name": "Acme"}})
        )
        async with PipedriveClient(api_token="x", company_domain="noxias") as client:
            org_id = await client.create_organization(name="Acme")
    assert org_id == 9001


@pytest.mark.asyncio
async def test_create_organization_with_siren_uses_custom_field() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"data": {"id": 1, "name": "Acme"}})

    async with respx.mock(base_url=BASE) as router:
        router.post("/organizations").mock(side_effect=handler)
        async with PipedriveClient(api_token="x", company_domain="noxias") as client:
            await client.create_organization(
                name="Acme",
                siren="123456789",
                siren_field_key="abc12345",
            )
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["abc12345"] == "123456789"
    assert body["name"] == "Acme"


@pytest.mark.asyncio
async def test_create_person_attaches_phone() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"data": {"id": 7}})

    async with respx.mock(base_url=BASE) as router:
        router.post("/persons").mock(side_effect=handler)
        async with PipedriveClient(api_token="x", company_domain="noxias") as client:
            await client.create_person(name="Jean Dupont", org_id=1, phone_e164="+33472001122")
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["phone"] == [{"value": "+33472001122", "primary": True, "label": "work"}]


@pytest.mark.asyncio
async def test_raises_on_http_error() -> None:
    async with respx.mock(base_url=BASE) as router:
        router.get("/persons/search").mock(
            return_value=httpx.Response(500, text="Server is on fire.")
        )
        async with PipedriveClient(api_token="x", company_domain="noxias") as client:
            with pytest.raises(PipedriveError, match="500"):
                await client.search_persons(term="anything")


@pytest.mark.asyncio
async def test_constructor_validates_credentials() -> None:
    with pytest.raises(PipedriveError):
        PipedriveClient(api_token="", company_domain="x")
    with pytest.raises(PipedriveError):
        PipedriveClient(api_token="x", company_domain="")
