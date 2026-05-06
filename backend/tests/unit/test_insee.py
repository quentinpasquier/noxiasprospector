"""Tests for the INSEE recherche-entreprises client."""

from __future__ import annotations

from datetime import date

import httpx
import pytest
import respx
from app.enrichment.insee import find_company


@pytest.mark.asyncio
async def test_finds_company_on_first_strategy() -> None:
    payload = {
        "results": [
            {
                "siren": "123456789",
                "nom_complet": "Acme Travaux",
                "nature_juridique": "5710",
                "activite_principale": "4399A",
                "tranche_effectif_salarie": "12",
                "date_creation": "2015-04-12",
                "dirigeants": [
                    {
                        "type_dirigeant": "personne physique",
                        "prenoms": "Jean",
                        "nom": "Dupont",
                    }
                ],
            }
        ]
    }
    async with respx.mock(base_url="https://recherche-entreprises.api.gouv.fr") as router:
        router.get("/search").mock(return_value=httpx.Response(200, json=payload))
        async with httpx.AsyncClient() as client:
            match = await find_company(name="Acme Travaux SARL", postal_code="69003", client=client)
    assert match is not None
    assert match.siren == "123456789"
    assert match.naf_code == "4399A"
    assert match.director_name == "Jean Dupont"
    assert match.creation_date == date(2015, 4, 12)


@pytest.mark.asyncio
async def test_filters_irrelevant_naf() -> None:
    """Bakery NAF (10.71B) must be filtered out for prospecting."""
    payload = {
        "results": [
            {
                "siren": "999999999",
                "nom_complet": "Boulangerie du coin",
                "activite_principale": "1071B",  # outside whitelist
            }
        ]
    }
    async with respx.mock(base_url="https://recherche-entreprises.api.gouv.fr") as router:
        router.get("/search").mock(return_value=httpx.Response(200, json=payload))
        async with httpx.AsyncClient() as client:
            match = await find_company(
                name="Boulangerie du coin", postal_code="69003", client=client
            )
    assert match is None


@pytest.mark.asyncio
async def test_falls_back_to_first_words() -> None:
    """Strategy 1 returns nothing → fallback to ``first_words`` succeeds."""

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        if params.get("code_postal"):
            return httpx.Response(200, json={"results": []})
        # 2nd strategy: q only.
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "siren": "111111111",
                        "nom_complet": "Acme Construction",
                        "activite_principale": "4120A",
                    }
                ]
            },
        )

    async with respx.mock(base_url="https://recherche-entreprises.api.gouv.fr") as router:
        router.get("/search").mock(side_effect=handler)
        async with httpx.AsyncClient() as client:
            match = await find_company(
                name="Acme Construction Tour Eiffel", postal_code="69003", client=client
            )

    assert match is not None
    assert match.siren == "111111111"


@pytest.mark.asyncio
async def test_returns_none_when_all_strategies_empty() -> None:
    async with respx.mock(base_url="https://recherche-entreprises.api.gouv.fr") as router:
        router.get("/search").mock(return_value=httpx.Response(200, json={"results": []}))
        async with httpx.AsyncClient() as client:
            match = await find_company(name="Inconnu", postal_code="01000", client=client)
    assert match is None
