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

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

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
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
