"""Application settings, loaded from environment variables.

All secrets and runtime configuration flow through this module — never read
``os.environ`` directly elsewhere.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings loaded from ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Runtime ---
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    API_V1_PREFIX: str = "/api/v1"

    # --- Database / cache ---
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://noxias:noxias@localhost:5432/noxiasprospect",
    )
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # --- Auth0 ---
    AUTH0_DOMAIN: str = ""
    AUTH0_CLIENT_ID: str = ""
    AUTH0_CLIENT_SECRET: str = ""
    AUTH0_AUDIENCE: str = ""

    # --- Bright Data scraping ---
    BRIGHTDATA_API_TOKEN: str = ""
    BRIGHTDATA_GMAPS_DATASET_ID: str = "gd_m8ebnr0q2qlklc02fz"
    BRIGHTDATA_UNLOCKER_ZONE: str = "sdk_unlocker"

    # --- Enrichment toggles ---
    PAPPERS_USE_SCRAPING: bool = True
    DROPCONTACT_API_KEY: str = ""

    # --- Pipedrive ---
    PIPEDRIVE_API_TOKEN: str = ""
    PIPEDRIVE_COMPANY_DOMAIN: str = ""

    # --- Observability ---
    SENTRY_DSN: str = ""

    # --- Concurrency ---
    ENRICHMENT_MAX_CONCURRENCY: int = 5
    BRIGHTDATA_POLL_INTERVAL_SECONDS: int = 30
    BRIGHTDATA_POLL_TIMEOUT_SECONDS: int = 600

    @property
    def is_production(self) -> bool:
        """Return True if running in production environment."""
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance.

    Using ``lru_cache`` ensures the env file is parsed exactly once per process.
    """
    return Settings()
