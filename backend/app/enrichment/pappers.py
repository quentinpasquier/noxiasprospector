"""Pappers financial data via Bright Data web unlocker.

We *scrape* the public Pappers page rather than calling the Pappers API,
because the latter is paid and the spec accepts the trade-off (the
``PAPPERS_USE_SCRAPING=true`` env toggle).

The HTML embeds a JSON-ish blob containing yearly figures we extract with
two complementary regexes:

- A precise one for the years/CA/résultat triplets:
  ``"annee":2023,"chiffre_affaires":1234567,"resultat":-2345``
- A loose one for the textual sentence used when figures are confidential
  (``"chiffre d'affaires était inférieur à 100 000 €"``).

We also extract the workforce (``"annee":2023,"effectif":12``) for the most
recent year available.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

UNLOCKER_URL = "https://api.brightdata.com/request"

_RE_FIN_TRIPLET = re.compile(
    r'"annee":(?P<year>\d{4})[^}]*?"chiffre_affaires":(?P<ca>\d+|null)'
    r'[^}]*?"resultat":(?P<resultat>-?\d+|null)'
)
_RE_FIN_TEXT = re.compile(
    r"chiffre d['’]affaires\s+(?:était|est)\s+"
    r"(?P<comp>inférieur|supérieur|compris).*?(?P<value>\d[\d\s]+)\s*€",
    re.IGNORECASE,
)
_RE_HEADCOUNT = re.compile(r'"annee":(?P<year>\d{4})[^}]*?"effectif":(?P<count>\d+)')


@dataclass(frozen=True, slots=True)
class PappersData:
    """Subset of Pappers data we keep — financials + headcount."""

    revenue_eur: int | None
    profit_eur: int | None
    financials_year: int | None
    employees_count: int | None
    raw_html_preview: str  # First 500 chars, for debug

    @property
    def has_financials(self) -> bool:
        return self.revenue_eur is not None or self.profit_eur is not None


def _parse_int(token: str) -> int | None:
    if token == "null":  # noqa: S105 -- comparing against the literal JSON null token
        return None
    try:
        return int(token)
    except ValueError:
        return None


def _parse_text_revenue(value: str) -> int | None:
    cleaned = value.replace(" ", "").replace(" ", "")
    return int(cleaned) if cleaned.isdigit() else None


def parse_pappers_html(html: str) -> PappersData:
    """Extract financials and headcount from a Pappers entreprise page."""
    revenue: int | None = None
    profit: int | None = None
    year: int | None = None

    triplets = _RE_FIN_TRIPLET.finditer(html)
    most_recent_year = -1
    for m in triplets:
        candidate_year = int(m.group("year"))
        ca = _parse_int(m.group("ca"))
        res = _parse_int(m.group("resultat"))
        if candidate_year > most_recent_year and (ca is not None or res is not None):
            most_recent_year = candidate_year
            year = candidate_year
            revenue = ca
            profit = res

    if revenue is None:
        text_match = _RE_FIN_TEXT.search(html)
        if text_match:
            revenue = _parse_text_revenue(text_match.group("value"))

    employees: int | None = None
    head_year = -1
    for m in _RE_HEADCOUNT.finditer(html):
        candidate_year = int(m.group("year"))
        if candidate_year > head_year:
            head_year = candidate_year
            employees = int(m.group("count"))

    return PappersData(
        revenue_eur=revenue,
        profit_eur=profit,
        financials_year=year,
        employees_count=employees,
        raw_html_preview=html[:500],
    )


async def fetch_pappers(
    siren: str, *, client: httpx.AsyncClient | None = None
) -> PappersData | None:
    """Fetch a Pappers page through Bright Data's web unlocker and parse it.

    Returns ``None`` if the unlocker call fails or returns empty content.
    """
    settings = get_settings()
    if not settings.BRIGHTDATA_API_TOKEN:
        logger.warning("pappers.skipped", reason="no_brightdata_token")
        return None

    owned = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=30.0)

    try:
        response = await client.post(
            UNLOCKER_URL,
            headers={"Authorization": f"Bearer {settings.BRIGHTDATA_API_TOKEN}"},
            json={
                "zone": settings.BRIGHTDATA_UNLOCKER_ZONE,
                "url": f"https://www.pappers.fr/entreprise/{siren}",
                "format": "raw",
                "country": "fr",
            },
        )
        response.raise_for_status()
        html = response.text or ""
        if not html.strip():
            return None
        return parse_pappers_html(html)
    except httpx.HTTPError as exc:
        logger.warning("pappers.http_error", siren=siren, error=str(exc))
        return None
    finally:
        if owned:
            await client.aclose()
