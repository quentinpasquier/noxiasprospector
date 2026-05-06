"""Pydantic schemas for Pipedrive export endpoints."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ExportPreviewItem(BaseModel):
    """Per-prospect dedup verdict returned by ``/exports/pipedrive/preview``."""

    prospect_id: uuid.UUID
    name: str
    siren: str | None
    phone_e164: str | None
    duplicate_reason: Literal["none", "phone", "siren", "already_exported"]
    duplicate_pipedrive_id: int | None


class ExportPreview(BaseModel):
    """Full preview body."""

    items: list[ExportPreviewItem]


class ExportRequest(BaseModel):
    """Body of ``POST /exports/pipedrive``.

    ``skip_prospect_ids`` lets the user opt-out of importing certain prospects
    (typically those flagged as duplicates in the preview).
    """

    skip_prospect_ids: list[uuid.UUID] = Field(default_factory=list)


class ExportResultItem(BaseModel):
    """Per-prospect outcome of an actual export call."""

    prospect_id: uuid.UUID
    status: Literal["created", "skipped", "failed"]
    organization_id: int | None = None
    person_id: int | None = None
    deal_id: int | None = None
    error: str | None = None


class ExportResponse(BaseModel):
    """Aggregate result of an export operation."""

    created: int
    skipped: int
    failed: int
    items: list[ExportResultItem]
