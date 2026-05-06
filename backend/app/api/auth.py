"""Auth endpoints — currently exposes only ``/auth/me``.

Login itself is handled client-side by NextAuth → Auth0; the backend never
issues tokens. It only verifies them.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentUser
from app.schemas.user import UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserPublic)
async def read_me(user: CurrentUser) -> UserPublic:
    """Return the authenticated user's profile (creates it on first login)."""
    return UserPublic.model_validate(user)
