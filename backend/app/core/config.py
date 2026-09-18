from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url

DEVELOPMENT_DEMO_SESSION_SECRET = "development-only-demo-session-secret"
PRODUCTION_HOSTNAME = "huskytracking.com"
PRODUCTION_PUBLIC_BASE_URL = f"https://{PRODUCTION_HOSTNAME}"


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
    public_base_url: str = "http://localhost:4300"
    api_v1_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+psycopg://husky_tracking:husky_tracking_dev@localhost:5433/"
        "husky_tracking"
    )
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:4300"]
    )
    allowed_hosts: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "testserver"]
    )
    log_level: str = "INFO"
    db_pool_size: int = Field(default=5, ge=1, le=20)
    db_max_overflow: int = Field(default=5, ge=0, le=20)
    db_pool_timeout_seconds: int = Field(default=30, ge=1, le=120)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86400)
    demo_season_start: date = date(2025, 12, 1)
    demo_season_end: date = date(2026, 3, 31)
    demo_reference_date: date = date(2026, 3, 31)
    demo_reset_enabled: bool = False
    demo_workspace_ttl_hours: int = Field(default=24, ge=1, le=168)
    demo_session_secret: str = DEVELOPMENT_DEMO_SESSION_SECRET
    demo_cookie_secure: bool = False
    demo_origin_check_enabled: bool = False
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
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: float = 10.0

    @field_validator("cors_origins", "allowed_hosts", mode="before")
    @classmethod
    def parse_csv_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be development, test, or production")
        return normalized

    @field_validator("public_base_url")
    @classmethod
    def normalize_public_base_url(cls, value: str) -> str:
        return value.strip().rstrip("/")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError("LOG_LEVEL must be a standard Python logging level")
        return normalized

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
        if self.smtp_starttls and self.smtp_use_ssl:
            raise ValueError("SMTP_STARTTLS and SMTP_USE_SSL cannot both be enabled")
        if bool(self.smtp_username) != bool(self.smtp_password):
            raise ValueError("SMTP username and password must be configured together")
        if self.app_env == "production":
            if self.public_base_url != PRODUCTION_PUBLIC_BASE_URL:
                raise ValueError(
                    "production PUBLIC_BASE_URL must be https://huskytracking.com"
                )
            if PRODUCTION_HOSTNAME not in self.allowed_hosts:
                raise ValueError(
                    "production ALLOWED_HOSTS must include huskytracking.com"
                )
            if "*" in self.allowed_hosts:
                raise ValueError("production ALLOWED_HOSTS cannot contain a wildcard")
            if set(self.cors_origins) != {self.public_base_url}:
                raise ValueError(
                    "production CORS_ORIGINS may contain only the canonical "
                    "public origin"
                )
            if (
                len(self.demo_session_secret) < 32
                or self.demo_session_secret == DEVELOPMENT_DEMO_SESSION_SECRET
                or "replace" in self.demo_session_secret.lower()
            ):
                raise ValueError("production DEMO_SESSION_SECRET must be strong")
            if not self.demo_cookie_secure:
                raise ValueError("production demo cookies must be Secure")
            if not self.demo_origin_check_enabled:
                raise ValueError("production demo mutation origin checking is required")
            if self.demo_workspace_ttl_hours > 72:
                raise ValueError(
                    "production demo workspace TTL must not exceed 72 hours"
                )
            if (
                not self.privacy_controller_name.strip()
                or not self.privacy_contact_email.strip()
                or "@" not in self.privacy_contact_email
                or self.privacy_contact_email.endswith(".invalid")
                or not self.privacy_controller_country.strip()
                or not self.privacy_hosting_region.strip()
                or "not configured" in self.privacy_controller_country.lower()
                or "not configured" in self.privacy_hosting_region.lower()
                or "project operator" in self.privacy_controller_name.lower()
                or any(
                    "replace" in value.lower()
                    for value in (
                        self.privacy_controller_name,
                        self.privacy_contact_email,
                        self.privacy_controller_country,
                        self.privacy_hosting_region,
                    )
                )
            ):
                raise ValueError("production privacy controller settings are required")
            if self.contact_delivery_mode == "sink":
                raise ValueError("production contact delivery cannot use sink mode")
            if self.contact_delivery_mode == "smtp":
                if (
                    not self.contact_recipient_email
                    or not self.smtp_host
                    or not self.smtp_from
                    or "@" not in self.contact_recipient_email
                    or "@" not in self.smtp_from
                ):
                    raise ValueError(
                        "production SMTP contact configuration is incomplete"
                    )
                if not self.smtp_starttls and not self.smtp_use_ssl:
                    raise ValueError("production SMTP transport encryption is required")
                if (
                    not self.privacy_mail_provider_name
                    or not self.privacy_mail_provider_region
                ):
                    raise ValueError(
                        "SMTP privacy provider name and region are required "
                        "in production"
                    )
            try:
                database = make_url(self.database_url)
            except Exception as error:
                raise ValueError("production DATABASE_URL is invalid") from error
            if (
                not database.drivername.startswith("postgresql")
                or database.host in {None, "localhost", "127.0.0.1"}
                or not database.database
                or "test" in database.database.lower()
                or database.password in {None, "husky_tracking_dev"}
                or "replace" in (database.password or "").lower()
                or (database.password or "").lower()
                in {"password", "postgres", "admin", "changeme"}
            ):
                raise ValueError("production DATABASE_URL is not production-safe")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
