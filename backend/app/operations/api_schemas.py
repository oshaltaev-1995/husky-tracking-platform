"""Small public contracts; no workspace identity, transcript or model-owned URL."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.operations.provider_models import ProviderName
from app.operations.schemas import Check, Entity, Evidence, Frozen, ToolName


class ReviewRequest(Frozen):
    selected_date: date

    @field_validator("selected_date", mode="before")
    @classmethod
    def calendar_date(cls, value: object) -> date:
        if type(value) is date:
            return value
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Select a calendar date in YYYY-MM-DD format.")
        return date.fromisoformat(value)


class OperationsCapabilities(Frozen):
    enabled: bool
    external_processing: bool
    providers: tuple[ProviderName, ...]
    selected_scenario: Literal["review_operations"] = "review_operations"
    season_start: date
    season_end: date


class ReviewLink(Frozen):
    entity: Entity
    label: str = Field(max_length=160)
    path: str = Field(max_length=240)


class ReviewTrace(Frozen):
    tool_name: ToolName
    provider: ProviderName
    outcome: Literal["ok"] = "ok"
    elapsed_ms: int = Field(ge=0)


class ReviewUsage(Frozen):
    known_prompt_tokens: int | None
    known_completion_tokens: int | None
    incomplete: bool


class ReviewStatusCounts(Frozen):
    passed: int = Field(ge=0)
    violations: int = Field(ge=0)
    attention: int = Field(ge=0)
    unverified: int = Field(ge=0)


class OperationsReviewRead(Frozen):
    snapshot_id: UUID
    selected_date: date
    captured_at: datetime
    explanation: str = Field(max_length=4000)
    facts: tuple[Check, ...] = Field(max_length=2)
    findings: tuple[Check, ...] = Field(max_length=32)
    evidence: tuple[Evidence, ...] = Field(max_length=66)
    links: tuple[ReviewLink, ...] = Field(max_length=128)
    checked_rules: tuple[str, ...]
    status_counts: ReviewStatusCounts
    omitted_findings: int = Field(ge=0)
    provider: ProviderName
    model: str
    fallback: bool
    http_calls: int = Field(ge=1, le=6)
    tool_calls: int = Field(ge=1, le=8)
    trace: tuple[ReviewTrace, ...] = Field(min_length=1, max_length=8)
    usage: ReviewUsage
