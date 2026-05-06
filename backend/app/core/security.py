"""Auth0 JWT verification.

Validates RS256 access tokens issued by Auth0 against:
- the JWKS published at ``https://{AUTH0_DOMAIN}/.well-known/jwks.json``
- the configured ``AUTH0_AUDIENCE`` (the API identifier in Auth0)
- the issuer ``https://{AUTH0_DOMAIN}/``

Public keys are cached in-process for 1 hour. We refresh the cache when a
token references an unknown ``kid`` (key rotation).
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError

from app.core.config import get_settings

_JWKS_CACHE_TTL_SECONDS = 3600
_jwks_cache: dict[str, Any] | None = None
_jwks_cache_expires_at: float = 0.0


class AuthError(Exception):
    """Raised when token verification fails. Carries an HTTP status code."""

    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _build_jwks_url() -> str:
    settings = get_settings()
    if not settings.AUTH0_DOMAIN:
        raise AuthError("Auth0 not configured (AUTH0_DOMAIN missing).", 500)
    return f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json"


def _build_issuer() -> str:
    return f"https://{get_settings().AUTH0_DOMAIN}/"


async def _fetch_jwks(force: bool = False) -> dict[str, Any]:
    """Fetch and cache the Auth0 JWKS document."""
    global _jwks_cache, _jwks_cache_expires_at
    now = time.monotonic()
    if not force and _jwks_cache is not None and now < _jwks_cache_expires_at:
        return _jwks_cache
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(_build_jwks_url())
    response.raise_for_status()
    _jwks_cache = response.json()
    _jwks_cache_expires_at = now + _JWKS_CACHE_TTL_SECONDS
    return _jwks_cache


def _find_signing_key(jwks: dict[str, Any], kid: str) -> dict[str, Any] | None:
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key.get("use", "sig"),
                "n": key["n"],
                "e": key["e"],
            }
    return None


async def verify_access_token(token: str) -> dict[str, Any]:
    """Verify an Auth0 RS256 access token and return its claims.

    Args:
        token: The bearer token (without the ``Bearer `` prefix).

    Returns:
        Decoded claims dictionary.

    Raises:
        AuthError: If the token is malformed, expired, has an unknown ``kid``,
            or fails audience/issuer validation.
    """
    settings = get_settings()
    if not settings.AUTH0_AUDIENCE:
        raise AuthError("Auth0 not configured (AUTH0_AUDIENCE missing).", 500)

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise AuthError("Invalid token header.") from exc

    kid = unverified_header.get("kid")
    if not kid:
        raise AuthError("Token missing 'kid' header.")

    jwks = await _fetch_jwks()
    signing_key = _find_signing_key(jwks, kid)
    if signing_key is None:
        # Key rotation — refresh once and retry.
        jwks = await _fetch_jwks(force=True)
        signing_key = _find_signing_key(jwks, kid)
        if signing_key is None:
            raise AuthError("Unable to find appropriate signing key.")

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.AUTH0_AUDIENCE,
            issuer=_build_issuer(),
        )
    except ExpiredSignatureError as exc:
        raise AuthError("Token expired.") from exc
    except JWTClaimsError as exc:
        raise AuthError(f"Invalid claims: {exc}") from exc
    except JWTError as exc:
        raise AuthError(f"Invalid token: {exc}") from exc

    return claims
