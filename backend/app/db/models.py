"""SQLAlchemy models for NoxiasProspect.

The schema follows the spirit of the CDC (section 7) — five core entities:

- :class:`User` — Auth0-backed sales user
- :class:`Search` — a prospecting query (keyword + locations + scoring preset)
- :class:`Prospect` — an enriched B2B lead
- :class:`Blacklist` — opt-out registry (siren or phone E.164)
- :class:`PipedriveMapping` — link from a prospect to its Pipedrive IDs

Constraint highlights (for unit tests):
- ``users.auth0_sub`` UNIQUE
- ``users.email`` UNIQUE
- ``prospects.place_id`` UNIQUE (idempotent re-scrapes)
- ``prospects.siren`` UNIQUE *partial* index ``WHERE siren IS NOT NULL``
- ``prospects.phone_e164`` UNIQUE *partial* index ``WHERE phone_e164 IS NOT NULL``
- ``blacklist`` ``CHECK (siren IS NOT NULL OR phone_e164 IS NOT NULL)``
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPkMixin


# ============================================================
#  Enums
# ============================================================
class UserRole(enum.StrEnum):
    """Application-level roles."""

    ADMIN = "admin"
    SALES = "sales"


class SearchStatus(enum.StrEnum):
    """Lifecycle of a search job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProspectLabel(enum.StrEnum):
    """Score-based label shown on the UI."""

    HOT = "Hot"
    WARM = "Warm"
    COLD = "Cold"
    UNQUALIFIED = "À qualifier"


class BlacklistReason(enum.StrEnum):
    """Why a prospect was opted-out."""

    OPT_OUT = "opt_out"  # explicit user request (RGPD art. 21)
    INVALID = "invalid"  # bad data (test, fake, ghost)
    COMPETITOR = "competitor"  # do-not-contact list


# ============================================================
#  User
# ============================================================
class User(UUIDPkMixin, TimestampMixin, Base):
    """A Noxias commercial authenticated via Auth0 SSO Google."""

    __tablename__ = "users"

    auth0_sub: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    picture_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.SALES,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    searches: Mapped[list[Search]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"


# ============================================================
#  Search
# ============================================================
class Search(UUIDPkMixin, TimestampMixin, Base):
    """A prospecting search initiated by a user.

    ``locations`` is a JSON array of ``{"city": str, "postal_code": str}``
    dicts. ``preset`` keeps a snapshot of the scoring preset name in case the
    preset definition is later edited.
    """

    __tablename__ = "searches"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query: Mapped[str] = mapped_column(String(500), nullable=False)
    locations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    limit: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    preset: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    status: Mapped[SearchStatus] = mapped_column(
        Enum(SearchStatus, name="search_status"),
        nullable=False,
        default=SearchStatus.PENDING,
        index=True,
    )
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner: Mapped[User] = relationship(back_populates="searches")
    prospects: Mapped[list[Prospect]] = relationship(
        back_populates="search",
        cascade="all, delete-orphan",
    )


# ============================================================
#  Prospect
# ============================================================
class Prospect(UUIDPkMixin, TimestampMixin, Base):
    """An enriched B2B lead.

    Raw payloads from each enrichment step are stored in JSONB columns to
    support replay/debug without re-scraping.
    """

    __tablename__ = "prospects"
    __table_args__ = (
        # Partial unique indexes — multiple NULLs allowed (Postgres default
        # already permits this, the partial form is explicit and fast).
        Index(
            "uq_prospects_siren_notnull",
            "siren",
            unique=True,
            postgresql_where="siren IS NOT NULL",
        ),
        Index(
            "uq_prospects_phone_e164_notnull",
            "phone_e164",
            unique=True,
            postgresql_where="phone_e164 IS NOT NULL",
        ),
        UniqueConstraint("place_id", name="uq_prospects_place_id"),
    )

    search_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("searches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --- Google Maps source ---
    place_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    postal_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="FR")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Contact ---
    phone_raw: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone_e164: Mapped[str | None] = mapped_column(String(20), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    gmaps_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # --- GMaps signals ---
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviews_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- INSEE / legal ---
    siren: Mapped[str | None] = mapped_column(String(9), nullable=True)
    naf_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    legal_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    legal_form: Mapped[str | None] = mapped_column(String(255), nullable=True)
    creation_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    director_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employees_range: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # --- Pappers / financials ---
    revenue_eur: Mapped[int | None] = mapped_column(Integer, nullable=True)
    profit_eur: Mapped[int | None] = mapped_column(Integer, nullable=True)
    financials_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Socials ---
    facebook_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    instagram_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # --- Scoring ---
    score: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    label: Mapped[ProspectLabel | None] = mapped_column(
        Enum(ProspectLabel, name="prospect_label"),
        nullable=True,
        index=True,
    )

    # --- Raw enrichment payloads (debug / replay) ---
    raw_gmaps: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    raw_insee: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    raw_pappers: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    search: Mapped[Search] = relationship(back_populates="prospects")
    pipedrive_mapping: Mapped[PipedriveMapping | None] = relationship(
        back_populates="prospect",
        cascade="all, delete-orphan",
        uselist=False,
    )


# ============================================================
#  Blacklist
# ============================================================
class Blacklist(UUIDPkMixin, TimestampMixin, Base):
    """Opt-out registry consulted by every enrichment run.

    A row must have at least one of ``siren`` / ``phone_e164``. We don't enforce
    uniqueness — it's allowed to add the same SIREN twice with different
    reasons / timestamps for audit purposes.
    """

    __tablename__ = "blacklist"
    __table_args__ = (
        CheckConstraint(
            "siren IS NOT NULL OR phone_e164 IS NOT NULL",
            name="siren_or_phone_required",
        ),
        Index("ix_blacklist_siren", "siren", postgresql_where="siren IS NOT NULL"),
        Index(
            "ix_blacklist_phone_e164",
            "phone_e164",
            postgresql_where="phone_e164 IS NOT NULL",
        ),
    )

    siren: Mapped[str | None] = mapped_column(String(9), nullable=True)
    phone_e164: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reason: Mapped[BlacklistReason] = mapped_column(
        Enum(BlacklistReason, name="blacklist_reason"),
        nullable=False,
        default=BlacklistReason.OPT_OUT,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


# ============================================================
#  PipedriveMapping
# ============================================================
class PipedriveMapping(UUIDPkMixin, TimestampMixin, Base):
    """Link between a NoxiasProspect prospect and its Pipedrive IDs."""

    __tablename__ = "pipedrive_mappings"
    __table_args__ = (UniqueConstraint("prospect_id", name="uq_pipedrive_mappings_prospect_id"),)

    prospect_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prospects.id", ondelete="CASCADE"),
        nullable=False,
    )
    pipedrive_organization_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pipedrive_person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pipedrive_deal_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pipedrive_note_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exported_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    exported_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sync_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    prospect: Mapped[Prospect] = relationship(back_populates="pipedrive_mapping")
