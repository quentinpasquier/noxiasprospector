"""Google Maps scraping via Bright Data datasets API.

Workflow per ``(keyword, location)`` couple:

1. **Trigger**: ``POST /datasets/v3/trigger`` with the dataset ID. Body is a
   list of ``{keyword, country}`` (we always pin ``country="FR"``). The
   response contains ``snapshot_id``.
2. **Poll**: ``GET /datasets/v3/progress/{snapshot_id}`` every 30 s. Done
   when ``status="ready"``. We give up after a configurable timeout.
3. **Download**: ``GET /datasets/v3/snapshot/{snapshot_id}?format=json``.

Each result is normalized into a :class:`GMapsResult` dataclass before being
handed off to the orchestrator.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

BRIGHTDATA_BASE_URL = "https://api.brightdata.com"


@dataclass(frozen=True, slots=True)
class GMapsResult:
    """Normalized Google Maps place returned by Bright Data."""

    place_id: str
    name: str
    address: str | None
    city: str | None
    postal_code: str | None
    country: str
    lat: float | None
    lon: float | None
    phone_raw: str | None
    website: str | None
    gmaps_url: str | None
    category: str | None
    rating: float | None
    reviews_count: int | None
    raw: dict[str, Any]


class BrightDataError(RuntimeError):
    """Raised when Bright Data returns an error or times out."""


def _client(token: str) -> httpx.AsyncClient:
    from app.core.http import make_async_client

    return make_async_client(
        base_url=BRIGHTDATA_BASE_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )


async def trigger_search(client: httpx.AsyncClient, keyword: str, dataset_id: str) -> str:
    """Trigger a discover_new dataset run, returning the ``snapshot_id``."""
    response = await client.post(
        "/datasets/v3/trigger",
        params={
            "dataset_id": dataset_id,
            "type": "discover_new",
            "discover_by": "location",
            "limit_per_input": 20,
        },
        json=[{"keyword": keyword, "country": "FR"}],
    )
    response.raise_for_status()
    payload = response.json()
    snapshot_id = payload.get("snapshot_id")
    if not snapshot_id:
        raise BrightDataError(f"Trigger returned no snapshot_id: {payload!r}")
    logger.info("brightdata.trigger", keyword=keyword, snapshot_id=snapshot_id)
    return str(snapshot_id)


async def poll_until_ready(
    client: httpx.AsyncClient,
    snapshot_id: str,
    *,
    interval_seconds: int,
    timeout_seconds: int,
) -> None:
    """Poll the snapshot progress until ``status='ready'`` or timeout.

    Raises:
        BrightDataError: On terminal ``failed`` status or timeout.
    """
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    backoff: float = float(interval_seconds)
    while True:
        response = await client.get(f"/datasets/v3/progress/{snapshot_id}")
        response.raise_for_status()
        status = response.json().get("status")
        logger.info("brightdata.progress", snapshot_id=snapshot_id, status=status)
        if status == "ready":
            return
        if status == "failed":
            raise BrightDataError(f"Snapshot {snapshot_id} failed.")
        if asyncio.get_running_loop().time() >= deadline:
            raise BrightDataError(f"Snapshot {snapshot_id} timed out after {timeout_seconds}s.")
        await asyncio.sleep(backoff)
        # Mild back-off if the dataset is taking longer than expected (cap at 2x).
        backoff = min(backoff * 1.2, interval_seconds * 2)


async def download_snapshot(client: httpx.AsyncClient, snapshot_id: str) -> list[dict[str, Any]]:
    """Download the snapshot payload as a list of raw place dicts."""
    response = await client.get(f"/datasets/v3/snapshot/{snapshot_id}", params={"format": "json"})
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise BrightDataError(f"Expected JSON array, got {type(data).__name__}.")
    return data


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _split_address(addr: str | None) -> tuple[str | None, str | None]:
    """Best-effort extraction of ``(postal_code, city)`` from a French address."""
    if not addr:
        return None, None
    import re

    match = re.search(r"\b(\d{5})\b\s+([A-Za-zÀ-ÿ' \-]+)", addr)
    if match:
        return match.group(1), match.group(2).strip().rstrip(",").strip()
    return None, None


def normalize_place(raw: dict[str, Any]) -> GMapsResult | None:
    """Convert a raw Bright Data place dict into a :class:`GMapsResult`.

    Returns ``None`` if the place is missing the minimum required fields
    (``place_id`` and ``name``).
    """
    place_id = raw.get("place_id") or raw.get("placeId")
    name = raw.get("name") or raw.get("title")
    if not place_id or not name:
        return None

    address = raw.get("address")
    postal_code, city = _split_address(address)

    return GMapsResult(
        place_id=str(place_id),
        name=str(name),
        address=address,
        city=city,
        postal_code=postal_code,
        country="FR",
        lat=_to_float(raw.get("lat") or raw.get("latitude")),
        lon=_to_float(raw.get("lon") or raw.get("longitude")),
        phone_raw=raw.get("phone_number") or raw.get("phone"),
        website=raw.get("open_website") or raw.get("website"),
        gmaps_url=raw.get("url") or raw.get("link"),
        category=raw.get("category") or raw.get("type"),
        rating=_to_float(raw.get("rating")),
        reviews_count=_to_int(raw.get("reviews_count") or raw.get("reviews")),
        raw=raw,
    )


async def fetch_places(keyword: str) -> list[GMapsResult]:
    """High-level helper: trigger → poll → download → normalize."""
    settings = get_settings()
    if not settings.BRIGHTDATA_API_TOKEN:
        raise BrightDataError("BRIGHTDATA_API_TOKEN is not configured.")

    async with _client(settings.BRIGHTDATA_API_TOKEN) as client:
        snapshot_id = await trigger_search(client, keyword, settings.BRIGHTDATA_GMAPS_DATASET_ID)
        await poll_until_ready(
            client,
            snapshot_id,
            interval_seconds=settings.BRIGHTDATA_POLL_INTERVAL_SECONDS,
            timeout_seconds=settings.BRIGHTDATA_POLL_TIMEOUT_SECONDS,
        )
        raw_places = await download_snapshot(client, snapshot_id)

    results: list[GMapsResult] = []
    seen: set[str] = set()
    for raw in raw_places:
        normalized = normalize_place(raw)
        if normalized and normalized.place_id not in seen:
            seen.add(normalized.place_id)
            results.append(normalized)
    return results
