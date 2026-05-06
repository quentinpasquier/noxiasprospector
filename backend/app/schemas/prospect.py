"""Pydantic schemas for the Prospect resource."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.db.models import ProspectLabel


class ProspectPublic(BaseModel):
    """Prospect row returned to the front."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    search_id: uuid.UUID
    name: str
    address: str | None
    city: str | None
    postal_code: str | None

    phone_e164: str | None
    website: str | None
    gmaps_url: str | None
    category: str | None
    rating: float | None
    reviews_count: int | None

    siren: str | None
    naf_code: str | None
    legal_name: str | None
    legal_form: str | None
    creation_date: date | None
    director_name: str | None
    employees_range: str | None

    revenue_eur: int | None
    profit_eur: int | None
    financials_year: int | None

    facebook_url: str | None
    instagram_url: str | None
    linkedin_url: str | None

    score: int | None
    label: ProspectLabel | None

    created_at: datetime
