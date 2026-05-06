"""Pydantic schemas for the User resource."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.db.models import UserRole


class UserPublic(BaseModel):
    """User information returned to authenticated clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str | None
    picture_url: str | None
    role: UserRole
    last_login_at: datetime | None
    created_at: datetime
