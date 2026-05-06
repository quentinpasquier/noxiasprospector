"""Social-network handle extraction from a prospect's website.

We fetch the homepage HTML through Bright Data's unlocker (same as Pappers)
to bypass anti-bot measures, then run a small bank of regexes against it.
The patterns avoid Facebook share/dialog widgets, Instagram post links and
LinkedIn job pages — those are not the company's own profile.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

UNLOCKER_URL = "https://api.brightdata.com/request"

# Handles to discard: widgets / non-profile paths.
BAD_HANDLES: frozenset[str] = frozenset(
    {
        "tr",
        "sharer",
        "share",
        "plugins",
        "dialog",
        "public",
        "pages",
        "pg",
        "login",
        "fr",
        "fr-fr",
        "p",
        "reel",
        "stories",
        "explore",
        "people",
    }
)

_FB = re.compile(
    r"facebook\.com/(?!sharer|share|tr/|plugins/|dialog/)"
    r"(?P<handle>[A-Za-z0-9._\-]{2,80})",
)
_IG = re.compile(
    r"instagram\.com/(?!p/|reel/|stories/|explore/)"
    r"(?P<handle>[A-Za-z0-9._\-]{2,40})",
)
_LI = re.compile(
    r"(?:[a-z]{2,3}\.)?linkedin\.com/(?:company|in|school)/"
    r"(?P<handle>[A-Za-z0-9\-]{2,80})",
)


@dataclass(frozen=True, slots=True)
class SocialProfiles:
    """First clean social URL found per network."""

    facebook_url: str | None
    instagram_url: str | None
    linkedin_url: str | None


def _first_clean(handles: list[str]) -> str | None:
    for h in handles:
        normalized = h.strip("/").lower()
        if normalized and normalized not in BAD_HANDLES:
            return h.strip("/")
    return None


def extract_socials(html: str) -> SocialProfiles:
    """Run regexes against ``html`` and return the cleaned profile URLs."""
    fb = _first_clean([m.group("handle") for m in _FB.finditer(html)])
    ig = _first_clean([m.group("handle") for m in _IG.finditer(html)])
    li = _first_clean([m.group("handle") for m in _LI.finditer(html)])

    return SocialProfiles(
        facebook_url=f"https://facebook.com/{fb}" if fb else None,
        instagram_url=f"https://instagram.com/{ig}" if ig else None,
        linkedin_url=f"https://linkedin.com/{li}" if li else None,
    )


async def fetch_socials(website: str, *, client: httpx.AsyncClient | None = None) -> SocialProfiles:
    """Fetch the website root HTML and extract social profiles from it.

    Returns an empty :class:`SocialProfiles` on any error — best-effort.
    """
    empty = SocialProfiles(None, None, None)
    settings = get_settings()
    if not settings.BRIGHTDATA_API_TOKEN:
        return empty

    owned = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=20.0)

    try:
        response = await client.post(
            UNLOCKER_URL,
            headers={"Authorization": f"Bearer {settings.BRIGHTDATA_API_TOKEN}"},
            json={
                "zone": settings.BRIGHTDATA_UNLOCKER_ZONE,
                "url": website,
                "format": "raw",
                "country": "fr",
            },
        )
        response.raise_for_status()
        return extract_socials(response.text)
    except httpx.HTTPError as exc:
        logger.warning("socials.http_error", website=website, error=str(exc))
        return empty
    finally:
        if owned:
            await client.aclose()
