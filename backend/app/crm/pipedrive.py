"""Typed Pipedrive v1 API client.

Uses an API-token authenticated httpx client. Every method returns the parsed
``data`` field of the Pipedrive response, or ``None`` for empty searches.

Reference docs: https://developers.pipedrive.com/docs/api/v1
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class PipedriveError(RuntimeError):
    """Raised on non-2xx Pipedrive responses we can't recover from."""


@dataclass(frozen=True, slots=True)
class SearchHit:
    """A single hit returned by Pipedrive's ``/search`` endpoints."""

    pipedrive_id: int
    name: str
    raw: dict[str, Any]


def _build_base_url(company_domain: str) -> str:
    return f"https://{company_domain}.pipedrive.com/v1"


class PipedriveClient:
    """Async client wrapping the Pipedrive v1 endpoints we need.

    The token is passed as the ``api_token`` query parameter on every call —
    Pipedrive's recommended auth scheme for server-to-server integrations.
    """

    def __init__(self, *, api_token: str, company_domain: str) -> None:
        if not api_token or not company_domain:
            raise PipedriveError("Pipedrive client is missing token or company domain.")
        from app.core.http import make_async_client

        self._api_token = api_token
        self._client = make_async_client(
            base_url=_build_base_url(company_domain),
            timeout=20.0,
        )

    async def __aenter__(self) -> PipedriveClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    # --- Internal helpers -------------------------------------------------
    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        merged = {"api_token": self._api_token, **(params or {})}
        response = await self._client.get(path, params=merged)
        if response.status_code >= 400:
            raise PipedriveError(f"GET {path} -> {response.status_code}: {response.text[:200]}")
        return dict(response.json())

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post(
            path, params={"api_token": self._api_token}, json=payload
        )
        if response.status_code >= 400:
            raise PipedriveError(f"POST {path} -> {response.status_code}: {response.text[:200]}")
        return dict(response.json())

    # --- Search -----------------------------------------------------------
    async def search_persons(self, *, term: str, fields: str | None = None) -> list[SearchHit]:
        """Search persons by free-text term (matches phone, email, name…)."""
        params: dict[str, Any] = {"term": term, "exact_match": "false"}
        if fields:
            params["fields"] = fields
        body = await self._get("/persons/search", params=params)
        items = (body.get("data") or {}).get("items") or []
        return [
            SearchHit(
                pipedrive_id=int(it["item"]["id"]),
                name=str(it["item"].get("name", "")),
                raw=it,
            )
            for it in items
            if it.get("item")
        ]

    async def search_organizations(
        self, *, term: str, fields: str | None = None
    ) -> list[SearchHit]:
        """Search organizations by free-text term (matches name + custom fields)."""
        params: dict[str, Any] = {"term": term, "exact_match": "false"}
        if fields:
            params["fields"] = fields
        body = await self._get("/organizations/search", params=params)
        items = (body.get("data") or {}).get("items") or []
        return [
            SearchHit(
                pipedrive_id=int(it["item"]["id"]),
                name=str(it["item"].get("name", "")),
                raw=it,
            )
            for it in items
            if it.get("item")
        ]

    # --- Create -----------------------------------------------------------
    async def create_organization(
        self,
        *,
        name: str,
        siren: str | None = None,
        siren_field_key: str = "",
        address: str | None = None,
    ) -> int:
        """Create an organization, returning its Pipedrive id."""
        payload: dict[str, Any] = {"name": name}
        if address:
            payload["address"] = address
        if siren and siren_field_key:
            payload[siren_field_key] = siren
        data = (await self._post("/organizations", payload)).get("data") or {}
        return int(data["id"])

    async def create_person(
        self,
        *,
        name: str,
        org_id: int | None = None,
        phone_e164: str | None = None,
        email: str | None = None,
    ) -> int:
        """Create a person, returning its Pipedrive id."""
        payload: dict[str, Any] = {"name": name}
        if org_id:
            payload["org_id"] = org_id
        if phone_e164:
            payload["phone"] = [{"value": phone_e164, "primary": True, "label": "work"}]
        if email:
            payload["email"] = [{"value": email, "primary": True, "label": "work"}]
        data = (await self._post("/persons", payload)).get("data") or {}
        return int(data["id"])

    async def create_deal(
        self,
        *,
        title: str,
        org_id: int | None = None,
        person_id: int | None = None,
        pipeline_id: int | None = None,
        imported_by_email: str | None = None,
        imported_by_field_key: str = "",
    ) -> int:
        """Create a deal, returning its Pipedrive id."""
        payload: dict[str, Any] = {"title": title}
        if org_id:
            payload["org_id"] = org_id
        if person_id:
            payload["person_id"] = person_id
        if pipeline_id is not None:
            payload["pipeline_id"] = pipeline_id
        if imported_by_email and imported_by_field_key:
            payload[imported_by_field_key] = imported_by_email
        data = (await self._post("/deals", payload)).get("data") or {}
        return int(data["id"])

    async def create_note(
        self,
        *,
        content: str,
        deal_id: int | None = None,
        org_id: int | None = None,
        person_id: int | None = None,
    ) -> int:
        """Create a note attached to a deal/org/person."""
        payload: dict[str, Any] = {"content": content}
        if deal_id:
            payload["deal_id"] = deal_id
        if org_id:
            payload["org_id"] = org_id
        if person_id:
            payload["person_id"] = person_id
        data = (await self._post("/notes", payload)).get("data") or {}
        return int(data["id"])

    # --- Delete -----------------------------------------------------------
    async def _delete(self, path: str) -> None:
        response = await self._client.delete(path, params={"api_token": self._api_token})
        # 404 is tolerated — the row may have been removed manually already.
        if response.status_code not in (200, 204, 404):
            raise PipedriveError(f"DELETE {path} -> {response.status_code}: {response.text[:200]}")

    async def delete_organization(self, org_id: int) -> None:
        await self._delete(f"/organizations/{org_id}")

    async def delete_person(self, person_id: int) -> None:
        await self._delete(f"/persons/{person_id}")

    async def delete_deal(self, deal_id: int) -> None:
        await self._delete(f"/deals/{deal_id}")


def build_client() -> PipedriveClient:
    """Construct a :class:`PipedriveClient` from app settings."""
    s = get_settings()
    return PipedriveClient(
        api_token=s.PIPEDRIVE_API_TOKEN, company_domain=s.PIPEDRIVE_COMPANY_DOMAIN
    )
