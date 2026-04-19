"""
Application configuration using Pydantic Settings.

Loads environment variables from .env file and provides typed,
validated configuration across the application.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Application ──────────────────────────────────────────────
    app_name: str = "StadiumFlow AI"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, description="Enable debug mode")
    host: str = "0.0.0.0"
    port: int = 8000
    allowed_origins: str = Field(
        default="http://localhost:8000,http://127.0.0.1:8000",
        description="Comma-separated list of allowed CORS origins",
    )

    # ── Google Services ──────────────────────────────────────────
    google_api_key: Optional[str] = Field(
        default=None, description="Google Gemini AI API key"
    )
    google_maps_api_key: Optional[str] = Field(
        default=None, description="Google Maps Platform API key"
    )
    firebase_project_id: Optional[str] = Field(
        default=None, description="Firebase project ID"
    )
    bigquery_project_id: Optional[str] = Field(
        default=None, description="BigQuery project ID for analytics"
    )

    # ── Database ─────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./stadiumflow.db",
        description="Async database connection URL",
    )

    # ── Simulation ───────────────────────────────────────────────
    simulation_tick_interval: float = Field(
        default=2.0, description="Seconds between simulation ticks"
    )
    max_venue_capacity: int = Field(
        default=132000, description="Maximum venue capacity (Narendra Modi Stadium)"
    )
    initial_attendee_count: int = Field(
        default=45000, description="Starting attendee count for simulation"
    )
    congestion_threshold: float = Field(
        default=0.85, description="Zone capacity threshold for alerts (0-1)"
    )

    # ── Security ─────────────────────────────────────────────────
    api_key: Optional[str] = Field(
        default=None, description="Optional API key for endpoint auth"
    )
    rate_limit_requests: int = Field(
        default=100, description="Max requests per rate limit window"
    )
    rate_limit_window: int = Field(
        default=60, description="Rate limit window in seconds"
    )

    @property
    def cors_origins(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
