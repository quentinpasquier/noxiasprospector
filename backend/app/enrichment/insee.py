"""French legal data enrichment via ``recherche-entreprises.api.gouv.fr``.

The API is free, keyless, rate-limited to 7 req/s. We try a cascade of queries
to maximize hit rate while keeping false positives low:

1. ``q={cleaned_name}&code_postal={zip}``
2. ``q={first_two_words(name)}&code_postal={zip}`` (handles brand suffixes)
3. ``q={cleaned_name}&departement={dept}`` (broader if zip is wrong)

Hits are then filtered by NAF section to keep only relevant industries — the
spec lists divisions ``41/43/46/70/71/74/81`` (construction, retail trade,
real estate, scientific/admin services, building support).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

INSEE_API_URL = "https://recherche-entreprises.api.gouv.fr/search"

# NAF divisions kept relevant for Noxias prospecting (cf. spec).
RELEVANT_NAF_PREFIXES: tuple[str, ...] = ("41", "43", "46", "70", "71", "74", "81")


@dataclass(frozen=True, slots=True)
class InseeMatch:
    """Normalized INSEE hit."""

    siren: str
    legal_name: str
    legal_form: str | None
    naf_code: str | None
    director_name: str | None
    employees_range: str | None
    creation_date: date | None
    raw: dict[str, Any]


def _clean_query(name: str) -> str:
    """Remove French legal suffixes and stop-noise tokens."""
    cleaned = re.sub(
        r"\b(SARL|SAS|SASU|SA|SCI|EURL|SCP|SC|EI|EURL)\b",
        "",
        name,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"[^\w\s\-']", " ", cleaned, flags=re.UNICODE)
    return " ".join(cleaned.split()).strip()


def _first_words(name: str, n: int = 2) -> str:
    return " ".join(_clean_query(name).split()[:n])


def _dept_from_zip(postal_code: str | None) -> str | None:
    """Return a 2-digit French département from a 5-digit postal code."""
    if not postal_code or len(postal_code) < 2:
        return None
    if postal_code.startswith("20"):  # Corsica → 2A/2B; we coarsely return "20".
        return "20"
    return postal_code[:2]


def _parse_director(unite: dict[str, Any]) -> str | None:
    """Extract the first natural-person director name from an INSEE record."""
    dirigeants = unite.get("dirigeants") or []
    for d in dirigeants:
        if d.get("type_dirigeant") == "personne physique" or d.get("nom"):
            first = d.get("prenoms") or d.get("prenom_usuel") or ""
            last = d.get("nom") or ""
            full = f"{first} {last}".strip()
            if full:
                return full
    return None


def _parse_creation_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _is_relevant(unite: dict[str, Any]) -> bool:
    naf = unite.get("activite_principale") or ""
    return naf[:2] in RELEVANT_NAF_PREFIXES if naf else True


def _to_match(unite: dict[str, Any]) -> InseeMatch | None:
    siren = unite.get("siren")
    name = unite.get("nom_complet") or unite.get("nom_raison_sociale")
    if not siren or not name:
        return None
    return InseeMatch(
        siren=str(siren),
        legal_name=str(name),
        legal_form=unite.get("nature_juridique"),
        naf_code=unite.get("activite_principale"),
        director_name=_parse_director(unite),
        employees_range=unite.get("tranche_effectif_salarie"),
        creation_date=_parse_creation_date(unite.get("date_creation")),
        raw=unite,
    )


async def _query(client: httpx.AsyncClient, params: dict[str, str | int]) -> list[dict[str, Any]]:
    response = await client.get(INSEE_API_URL, params=params)
    if response.status_code == 404:
        return []
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results")
    return list(results) if isinstance(results, list) else []


async def find_company(
    *,
    name: str,
    postal_code: str | None,
    client: httpx.AsyncClient | None = None,
) -> InseeMatch | None:
    """Run the cascade of strategies until we find a relevant match.

    Args:
        name: Business name (any case, may contain legal suffix).
        postal_code: Optional 5-digit postal code.
        client: Optional pre-built ``httpx.AsyncClient``; one is created if
            absent.

    Returns:
        The first relevant :class:`InseeMatch`, or ``None`` if none match.
    """
    cleaned = _clean_query(name)
    if not cleaned:
        return None

    owned_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=10.0)

    try:
        strategies: list[dict[str, str | int]] = []
        if postal_code:
            strategies.append({"q": cleaned, "code_postal": postal_code, "per_page": 3})
        strategies.append({"q": _first_words(cleaned, 2), "per_page": 3})
        dept = _dept_from_zip(postal_code)
        if dept:
            strategies.append({"q": cleaned, "departement": dept, "per_page": 3})

        for params in strategies:
            results = await _query(client, params)
            for unite in results:
                if not _is_relevant(unite):
                    continue
                match = _to_match(unite)
                if match:
                    logger.info(
                        "insee.match",
                        siren=match.siren,
                        naf=match.naf_code,
                        strategy=list(params.keys()),
                    )
                    return match
        return None
    finally:
        if owned_client:
            await client.aclose()
