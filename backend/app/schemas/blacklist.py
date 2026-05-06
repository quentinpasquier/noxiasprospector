"""Pydantic schemas for the Blacklist resource."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models import BlacklistReason


class BlacklistCreate(BaseModel):
    """Body for ``POST /blacklist``."""

    siren: str | None = Field(default=None, min_length=9, max_length=9, pattern=r"^\d{9}$")
    phone_e164: str | None = Field(default=None, max_length=20, pattern=r"^\+\d{8,15}$")
    reason: BlacklistReason = BlacklistReason.OPT_OUT
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _at_least_one(self) -> Self:
        if not self.siren and not self.phone_e164:
            raise ValueError("siren or phone_e164 is required.")
        return self


class BlacklistPublic(BaseModel):
    """Blacklist row exposed by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    siren: str | None
    phone_e164: str | None
    reason: BlacklistReason
    note: str | None
    created_at: datetime
