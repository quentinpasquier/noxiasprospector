"""FastAPI dependencies — DB session + current authenticated user."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AuthError, verify_access_token
from app.db.models import User, UserRole
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Validate the Bearer token and return the matching :class:`User`.

    On first login the user is created (upsert by ``auth0_sub``). The
    ``last_login_at`` timestamp is refreshed on every authenticated request.

    Raises:
        HTTPException 401: if no token is provided or token is invalid.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = await verify_access_token(credentials.credentials)
    except AuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    auth0_sub = claims.get("sub")
    if not auth0_sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim.",
        )

    # Auth0 puts email in custom namespaced claims when issued from M2M; we
    # accept either the standard ``email`` or namespaced fallbacks.
    email = (
        claims.get("email") or claims.get("https://noxias.fr/email") or f"{auth0_sub}@unknown.local"
    )
    name = claims.get("name") or claims.get("https://noxias.fr/name")
    picture = claims.get("picture")

    result = await db.execute(select(User).where(User.auth0_sub == auth0_sub))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            auth0_sub=auth0_sub,
            email=email,
            name=name,
            picture_url=picture,
            role=UserRole.SALES,
            last_login_at=datetime.now(UTC),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        user.last_login_at = datetime.now(UTC)
        if name and user.name != name:
            user.name = name
        if picture and user.picture_url != picture:
            user.picture_url = picture
        await db.commit()
        await db.refresh(user)

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
