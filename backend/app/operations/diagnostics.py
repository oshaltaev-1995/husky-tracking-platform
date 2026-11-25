"""Content-free internal response diagnostics, never a public error contract.

Only fixed enums and bounded numbers cross this boundary. Construction is best
-effort: an instrumentation failure cannot replace the original typed failure.
"""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from app.operations.provider_models import AgentFailure

FailureStage = Literal[
    "transport",
    "envelope",
    "content",
    "tool",
    "usage",
    "policy",
    "final_schema",
    "reference_validation",
    "diagnostics",
]
FailureReason = Literal[
    "transport_encoding",
    "response_size",
    "response_length",
    "transport_fragmentation",
    "transport_timeout",
    "transport_network",
    "transport_configuration",
    "transport_status",
    "cancelled",
    "envelope_json",
    "envelope_type",
    "invalid_choices",
    "message_type",
    "finish_length",
    "finish_reason",
    "content_filter",
    "content_type",
    "content_json",
    "content_fenced_json",
    "content_not_object",
    "tool_count",
    "tool_shape",
    "tool_name",
    "tool_arguments",
    "tool_in_final",
    "finish_tool_conflict",
    "usage_type",
    "mandatory_tool",
    "reference_membership",
    "final_schema",
    "context_changed",
    "budget",
    "unknown",
]
FinishReason = Literal[
    "stop", "tool_calls", "length", "content_filter", "missing", "other"
]
ContentType = Literal[
    "string", "null", "missing", "array", "object", "boolean", "number", "other"
]


class ResponseDiagnostic(BaseModel):
    """Safe even on rejected responses; no body, identifiers, arbitrary strings."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    failure_stage: FailureStage | None = None
    failure_reason: FailureReason | None = None
    upstream_http_status: int | None = Field(default=None, ge=100, le=599)
    finish_reason: FinishReason = "missing"
    response_bytes: int | None = Field(default=None, ge=0, le=65536)
    content_bytes: int | None = Field(default=None, ge=0, le=65536)
    content_type: ContentType = "missing"
    tool_call_count: int | None = Field(default=None, ge=0, le=65536)
    prompt_tokens: int | None = Field(default=None, ge=0, le=2**63 - 1)
    completion_tokens: int | None = Field(default=None, ge=0, le=2**63 - 1)


def safe_diagnostic(**metadata: object) -> ResponseDiagnostic | None:
    """Drop failed instrumentation rather than altering the application path."""
    try:
        return ResponseDiagnostic.model_validate(metadata)
    except Exception:
        return None


def annotate_failure(
    error: AgentFailure,
    failure_stage: FailureStage,
    failure_reason: FailureReason,
    **metadata: object,
) -> AgentFailure:
    with suppress(Exception):
        error.diagnostic = safe_diagnostic(
            failure_stage=failure_stage,
            failure_reason=failure_reason,
            **metadata,
        )
    return error


def bounded_size(value: int) -> int:
    """Cap diagnostics only, without increasing the actual accepted body limit."""
    return max(0, min(value, 65536))


def valid_usage(value: object) -> int | None:
    # bool is an int subclass, but is never token usage. Missing/invalid != zero.
    return value if type(value) is int and 0 <= value <= 2**63 - 1 else None


def content_kind(message: dict[str, object]) -> ContentType:
    if "content" not in message:
        return "missing"
    value = message["content"]
    if value is None:
        return "null"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "other"


def normalize_finish(value: object) -> FinishReason:
    if value is None:
        return "missing"
    if value in ("stop", "tool_calls", "length", "content_filter"):
        # Returning constants prevents arbitrary provider strings from escaping.
        if value == "stop":
            return "stop"
        if value == "tool_calls":
            return "tool_calls"
        if value == "length":
            return "length"
        return "content_filter"
    return "other"
