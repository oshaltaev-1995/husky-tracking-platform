"""Bounded, immutable provider contracts. No transport is configured by default."""

from __future__ import annotations

import json
from typing import Any, Literal, NoReturn

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["groq", "openrouter"]
ErrorCode = Literal[
    "agent_disabled",
    "app_rate_limited",
    "provider_configuration",
    "provider_authentication",
    "provider_access_denied",
    "provider_payment_required",
    "provider_bad_request",
    "provider_quota",
    "provider_transport",
    "provider_timeout",
    "provider_unavailable",
    "free_route_unavailable",
    "ai_quota_exhausted",
    "ai_temporarily_unavailable",
    "invalid_provider_response",
    "forbidden_tool",
    "invalid_evidence",
    "policy_refusal",
    "run_budget_exhausted",
    "timeout",
    "session_expired",
    "date_out_of_range",
    "snapshot_too_large",
    "context_changed",
    "cancelled",
    "stale_attempt",
    "run_finished",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


def json_object(value: str | bytes) -> dict[str, Any]:
    """RFC JSON object: reject ambiguous duplicate keys and non-finite numbers."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = item
        return result

    def invalid_constant(_: str) -> NoReturn:
        raise ValueError("Non-finite JSON number")

    try:
        parsed = json.loads(
            value, object_pairs_hook=pairs, parse_constant=invalid_constant
        )
    except RecursionError:
        raise ValueError("Nested JSON exceeds supported depth") from None
    if not isinstance(parsed, dict):
        raise ValueError("Expected JSON object")
    return parsed


class ProviderSettings(BaseSettings):
    """Separate server-only config; enabling does NOT enable a network transport.

    Groq's Free-account attestation is an operator prerequisite, not a claim that
    the model identifier itself proves a free account. P14B must verify the plan.
    """

    model_config = SettingsConfigDict(env_prefix="AGENT_", extra="forbid", frozen=True)

    enabled: bool = False
    groq_free_account_confirmed: bool = False
    groq_api_key: SecretStr | None = Field(default=None, repr=False)
    openrouter_api_key: SecretStr | None = Field(default=None, repr=False)
    groq_model: Literal["openai/gpt-oss-20b"] = "openai/gpt-oss-20b"
    openrouter_model: Literal["openai/gpt-oss-20b:free"] = "openai/gpt-oss-20b:free"
    max_http_calls: int = Field(default=6, ge=1, le=6)
    max_tool_calls: int = Field(default=8, ge=1, le=8)
    deadline_seconds: float = Field(default=45.0, ge=1, le=45)
    http_timeout_seconds: float = Field(default=12.0, ge=0.1, le=15)
    max_output_tokens: int = Field(default=1024, ge=64, le=1024)
    max_input_bytes: int = Field(default=65536, ge=1024, le=65536)
    max_response_bytes: int = Field(default=32768, ge=1024, le=32768)
    max_tool_result_bytes: int = Field(default=16384, ge=256, le=16384)


class AgentFailure(Exception):
    """Safe typed error; never includes provider bodies, keys or raw exceptions."""

    def __init__(
        self,
        code: ErrorCode,
        *,
        http_status: int = 503,
        retry_after_seconds: int | None = None,
    ) -> None:
        self.code = code
        self.http_status = http_status
        self.retry_after_seconds = retry_after_seconds
        super().__init__(code)


class ToolContract(FrozenModel):
    name: str = Field(pattern=r"^[a-z][a-z_]{1,39}$")
    description: str = Field(min_length=1, max_length=240)
    parameters_json: str = Field(min_length=2, max_length=8192, repr=False)

    @field_validator("parameters_json")
    @classmethod
    def schema_object(cls, value: str) -> str:
        parsed = json_object(value)
        if parsed.get("type") != "object":
            raise ValueError("Tool schema must describe an object")
        return value


class ToolCall(FrozenModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=40)
    arguments_json: str = Field(min_length=2, max_length=4096, repr=False)


class Message(FrozenModel):
    role: Literal["assistant", "tool"]
    content: str = Field(default="", max_length=16384, repr=False)
    tool_call: ToolCall | None = Field(default=None, repr=False)
    tool_call_id: str | None = None


class Usage(FrozenModel):
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)


class ProviderResult(FrozenModel):
    provider: ProviderName
    attempt: int = Field(ge=0)
    content_json: str | None = Field(default=None, repr=False)
    tool_call: ToolCall | None = Field(default=None, repr=False)
    usage: Usage = Field(default_factory=Usage)


class HttpRequest(FrozenModel):
    """Only an injected transport may consume this; secrets are excluded from repr."""

    url: Literal[
        "https://api.groq.com/openai/v1/chat/completions",
        "https://openrouter.ai/api/v1/chat/completions",
    ]
    authorization: SecretStr = Field(repr=False)
    body_json: str = Field(repr=False)
    timeout_seconds: float = Field(gt=0, le=15)
    follow_redirects: Literal[False] = False
    retries: Literal[0] = 0
    response_limit_bytes: int = Field(ge=1024, le=32768)


class HttpReply(FrozenModel):
    status: int = Field(ge=100, le=599)
    body: bytes = Field(default=b"", repr=False)
    retry_after: str | None = Field(default=None, max_length=100)


class RunMetadata(FrozenModel):
    """This allowlist is the entire logging projection; no transcript or task."""

    run_id: str
    provider: ProviderName
    model: str
    switches: int
    http_calls: int
    tool_calls: int
    elapsed_seconds: float
    error_code: ErrorCode | None = None
    usage: Usage = Field(default_factory=Usage)
