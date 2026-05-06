"""Pydantic schemas for the Search resource."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import SearchStatus


class Location(BaseModel):
    """A target city for the search."""

    city: str = Field(min_length=1, max_length=120)
    postal_code: str | None = Field(default=None, max_length=10)


class SearchCreate(BaseModel):
    """Payload accepted by ``POST /searches``."""

    query: str = Field(min_length=1, max_length=500)
    locations: list[Location] = Field(min_length=1, max_length=50)
    limit: int = Field(default=100, ge=1, le=500)
    preset: str = Field(default="default", max_length=64)


class SearchPublic(BaseModel):
    """Search row exposed by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    query: str
    locations: list[dict[str, str | None]]
    status: SearchStatus
    progress_total: int
    progress_done: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
