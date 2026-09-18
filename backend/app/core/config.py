from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings, including the explicit demo clock."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Husky Tracking API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+psycopg://husky_tracking:husky_tracking_dev@localhost:5433/"
        "husky_tracking"
    )
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:4300"]
    )
    demo_season_start: date = date(2025, 12, 1)
    demo_season_end: date = date(2026, 3, 31)
    demo_reference_date: date = date(2026, 3, 31)
    demo_reset_enabled: bool = False
    demo_workspace_ttl_hours: int = Field(default=24, ge=1, le=168)
    demo_cookie_secure: bool = False
    privacy_controller_name: str = "Husky Tracking project operator"
    privacy_contact_email: str = "privacy@example.invalid"
    privacy_controller_country: str = "Not configured"
    privacy_hosting_region: str = "Not configured"
    privacy_effective_date: date = date(2026, 9, 18)
    privacy_mail_provider_name: str | None = None
    privacy_mail_provider_region: str | None = None
    contact_delivery_mode: str = "sink"
    contact_recipient_email: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = True
    smtp_timeout_seconds: float = 10.0

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("contact_delivery_mode")
    @classmethod
    def validate_contact_delivery_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"sink", "smtp", "disabled"}:
            raise ValueError("contact delivery mode must be sink, smtp, or disabled")
        return normalized

    @model_validator(mode="after")
    def validate_demo_clock(self) -> Settings:
        if self.demo_season_start > self.demo_season_end:
            raise ValueError("demo season start must not follow its end")
        if (
            not self.demo_season_start
            <= self.demo_reference_date
            <= self.demo_season_end
        ):
            raise ValueError("demo reference date must fall within the demo season")
        if self.app_env.lower() == "production":
            if not self.demo_cookie_secure:
                raise ValueError("production demo cookies must be Secure")
            if (
                not self.privacy_controller_name.strip()
                or not self.privacy_contact_email.strip()
                or self.privacy_contact_email.endswith(".invalid")
                or not self.privacy_controller_country.strip()
                or not self.privacy_hosting_region.strip()
                or "not configured" in self.privacy_controller_country.lower()
                or "not configured" in self.privacy_hosting_region.lower()
            ):
                raise ValueError("production privacy controller settings are required")
            if self.contact_delivery_mode == "smtp" and (
                not self.privacy_mail_provider_name
                or not self.privacy_mail_provider_region
            ):
                raise ValueError(
                    "SMTP privacy provider name and region are required in production"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
