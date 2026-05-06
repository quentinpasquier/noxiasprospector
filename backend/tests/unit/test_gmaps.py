"""Tests for the Bright Data Google Maps client."""

from __future__ import annotations

import httpx
import pytest
import respx
from app.enrichment.gmaps import (
    BrightDataError,
    download_snapshot,
    normalize_place,
    poll_until_ready,
    trigger_search,
)


@pytest.mark.asyncio
async def test_trigger_search_returns_snapshot_id() -> None:
    async with respx.mock(base_url="https://api.brightdata.com") as router:
        router.post("/datasets/v3/trigger").mock(
            return_value=httpx.Response(200, json={"snapshot_id": "snap_123"})
        )
        async with httpx.AsyncClient(base_url="https://api.brightdata.com") as client:
            snapshot_id = await trigger_search(client, "courtier en travaux Lyon", "ds_xyz")
        assert snapshot_id == "snap_123"


@pytest.mark.asyncio
async def test_trigger_raises_when_no_snapshot_id() -> None:
    async with respx.mock(base_url="https://api.brightdata.com") as router:
        router.post("/datasets/v3/trigger").mock(
            return_value=httpx.Response(200, json={"error": "boom"})
        )
        async with httpx.AsyncClient(base_url="https://api.brightdata.com") as client:
            with pytest.raises(BrightDataError):
                await trigger_search(client, "kw", "ds")


@pytest.mark.asyncio
async def test_poll_returns_when_ready() -> None:
    async with respx.mock(base_url="https://api.brightdata.com") as router:
        router.get("/datasets/v3/progress/snap_1").mock(
            side_effect=[
                httpx.Response(200, json={"status": "running"}),
                httpx.Response(200, json={"status": "ready"}),
            ]
        )
        async with httpx.AsyncClient(base_url="https://api.brightdata.com") as client:
            await poll_until_ready(client, "snap_1", interval_seconds=0, timeout_seconds=5)


@pytest.mark.asyncio
async def test_poll_raises_on_failed() -> None:
    async with respx.mock(base_url="https://api.brightdata.com") as router:
        router.get("/datasets/v3/progress/snap_2").mock(
            return_value=httpx.Response(200, json={"status": "failed"})
        )
        async with httpx.AsyncClient(base_url="https://api.brightdata.com") as client:
            with pytest.raises(BrightDataError):
                await poll_until_ready(client, "snap_2", interval_seconds=0, timeout_seconds=5)


@pytest.mark.asyncio
async def test_download_snapshot_returns_list() -> None:
    payload = [{"place_id": "p1", "name": "Acme"}]
    async with respx.mock(base_url="https://api.brightdata.com") as router:
        router.get("/datasets/v3/snapshot/snap_3").mock(
            return_value=httpx.Response(200, json=payload)
        )
        async with httpx.AsyncClient(base_url="https://api.brightdata.com") as client:
            data = await download_snapshot(client, "snap_3")
        assert data == payload


def test_normalize_place_extracts_postal_code_and_city() -> None:
    raw = {
        "place_id": "ChIJfoo",
        "name": "Acme Travaux",
        "address": "12 rue Garibaldi 69003 Lyon",
        "phone_number": "0472001122",
        "open_website": "https://acme.fr",
        "rating": "4.6",
        "reviews_count": "87",
        "lat": "45.764",
        "lon": "4.836",
    }
    place = normalize_place(raw)
    assert place is not None
    assert place.place_id == "ChIJfoo"
    assert place.postal_code == "69003"
    assert place.city == "Lyon"
    assert place.rating == 4.6
    assert place.reviews_count == 87
    assert place.website == "https://acme.fr"


def test_normalize_place_returns_none_when_missing_fields() -> None:
    assert normalize_place({"name": "no place id"}) is None
    assert normalize_place({"place_id": "p"}) is None
