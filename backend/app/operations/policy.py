"""Bounded single-provider run state shared by the read-only P14B agent loop.

This state machine never owns a DB session or executes tools. Admission and
freshness are injected checks. Groq-only permits one short confirmed after-tool
quota recovery within the original deadline; it never restarts the review. The
retained optional reserve still requires explicit operator opt-in.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from typing import NoReturn
from uuid import uuid4

from pydantic import ValidationError

from app.operations.provider_models import (
    AgentFailure,
    ErrorCode,
    HttpRequest,
    Message,
    ProviderName,
    ProviderResult,
    ProviderSettings,
    ProviderUsage,
    RunMetadata,
    ToolContract,
    Usage,
    json_object,
)
from app.operations.providers import Transport, build_request, parse_reply

RETRYABLE = frozenset(
    {"provider_quota", "provider_transport", "provider_timeout", "provider_unavailable"}
)


class ProviderRun:
    def __init__(
        self,
        *,
        settings: ProviderSettings,
        transport: Transport,
        snapshot_id: str,
        snapshot_json: str,
        task: str,
        tools: tuple[ToolContract, ...],
        check_context: Callable[[], None],
        admit: Callable[[], bool],
        monotonic: Callable[[], float] = time.monotonic,
        waiter: Callable[[float], None] = time.sleep,
        started_at: float | None = None,
        force_validate_day: bool = False,
    ) -> None:
        self.settings = settings
        self._transport = transport
        self.snapshot_id = snapshot_id
        self._snapshot_json = snapshot_json
        self._task = task
        self._tools = tools
        self._check_context = check_context
        self._clock = monotonic
        self._waiter = waiter
        now = monotonic()
        if not math.isfinite(now) or (
            started_at is not None
            and (not math.isfinite(started_at) or started_at > now)
        ):
            raise AgentFailure("provider_configuration")
        # The caller may capture this on the SAME clock before admission/snapshot.
        # Never reset the whole-run deadline when DB preparation has already elapsed.
        self._started = now if started_at is None else started_at
        self._deadline = self._started + settings.deadline_seconds
        self.run_id = str(uuid4())
        self.provider: ProviderName = "groq"
        self.attempt = 0
        self.switches = 0
        self.http_calls = 0
        self.tool_calls = 0
        self._finished = False
        self._cancelled = False
        self._pending_tool: ProviderResult | None = None
        self._last_result: ProviderResult | None = None
        self._messages: tuple[Message, ...] = ()
        self._error: ErrorCode | None = None
        self._usage = Usage()
        self._usage_history: list[tuple[ProviderName, Usage]] = []
        self._provider_http_calls: dict[ProviderName, int] = {
            "groq": 0,
            "openrouter": 0,
        }
        self._force_validate_day = force_validate_day
        self._validated_attempt: int | None = None
        self._primary_error: ErrorCode | None = None
        self._last_request: HttpRequest | None = None
        self._last_reply_status: int | None = None
        self._quota_retry_used = False
        self._quota_retries = 0
        self.retry_after_seconds: int | None = None
        if not settings.enabled:
            self._fail("agent_disabled", 503)
        self._guard()
        if not admit():
            self._fail("app_rate_limited", 429)
        self._guard()  # Admission itself also consumes the whole-run time budget.

    def _fail(self, code: ErrorCode, status: int = 503) -> NoReturn:
        self._finished = True
        self._error = code
        self.attempt += 1
        raise AgentFailure(
            code, http_status=status, retry_after_seconds=self.retry_after_seconds
        )

    def _guard(self) -> None:
        if self._cancelled:
            self._fail("cancelled", 409)
        if self._finished:
            raise AgentFailure("run_finished", http_status=409)
        try:
            self._check_context()
        except AgentFailure as failure:
            self._finished = True
            self._error = failure.code
            self.attempt += 1
            raise
        if self._clock() >= self._deadline:
            self._fail("timeout", 504)

    def _send(self, request: HttpRequest | None = None) -> ProviderResult:
        quota_retry = request is not None
        self._guard()
        if (
            self.provider == "openrouter"
            and not self.settings.openrouter_reserve_enabled
        ):
            self._fail("provider_configuration")
        if self.http_calls >= self.settings.max_http_calls:
            self._fail("run_budget_exhausted", 429)
        remaining = self._deadline - self._clock()
        if remaining <= 0:
            self._fail("timeout", 504)
        if request is None:
            try:
                request = build_request(
                    self.provider,
                    self.settings,
                    task=self._task,
                    snapshot_json=self._snapshot_json,
                    tools=self._tools,
                    messages=self._messages,
                    timeout_seconds=min(self.settings.http_timeout_seconds, remaining),
                    required_tool=(
                        "validate_day"
                        if self._force_validate_day
                        and not self.validated_current_attempt
                        else None
                    ),
                )
            except ValidationError:
                self._fail("provider_configuration")
        # Serialization and validation consume the SAME run deadline too. Never
        # dispatch a zero/expired timeout or leak HttpRequest's ValidationError.
        self._guard()  # Recheck current context immediately before dispatch.
        remaining = self._deadline - self._clock()
        if remaining <= 0:
            self._fail("timeout", 504)
        request = request.model_copy(
            update={"timeout_seconds": min(request.timeout_seconds, remaining)}
        )
        self.http_calls += 1  # Failed attempts spend the same total budget.
        self._quota_retries += int(quota_retry)
        self._provider_http_calls[self.provider] += 1
        self._usage = Usage()  # Last dispatch may have an unknown/lost response.
        self._last_request = request
        self._last_reply_status = None
        captured_attempt = self.attempt
        captured_provider = self.provider
        try:
            reply = self._transport(request)
        except TimeoutError:
            raise AgentFailure("provider_timeout") from None
        except OSError:
            raise AgentFailure("provider_transport") from None
        self._last_reply_status = reply.status
        self._guard()
        if captured_attempt != self.attempt or captured_provider != self.provider:
            self._fail("stale_attempt", 409)
        result = parse_reply(
            reply,
            self.provider,
            self.attempt,
            self._tools,
            self.settings.max_response_bytes,
        )
        self._usage = result.usage
        self._usage_history.append((self.provider, result.usage))
        if (
            self._force_validate_day
            and not self.validated_current_attempt
            and (result.tool_call is None or result.tool_call.name != "validate_day")
        ):
            raise AgentFailure("invalid_provider_response", http_status=502)
        self._last_result = result
        self._pending_tool = result if result.tool_call else None
        return result

    def call(self) -> ProviderResult:
        """One model turn, one narrow quota recovery/run; never executes tools."""
        self._guard()
        if self._pending_tool is not None:
            self._fail("provider_bad_request", 409)
        try:
            return self._send()
        except AgentFailure as failure:
            if self._finished:
                raise
            self._guard()
            if failure.code not in RETRYABLE:
                self._finished = True
                self._error = failure.code
                raise
            self.retry_after_seconds = failure.retry_after_seconds
            if self._short_quota_wait(failure):
                # Retry the rejected serialized request, not a new prompt/review.
                # _short_quota_wait has checked this exact request and context.
                assert self._last_request is not None
                try:
                    return self._send(self._last_request)
                except AgentFailure as retry_failure:
                    self._finish_failure(retry_failure)
            if (
                self.settings.openrouter_reserve_enabled
                and self.provider == "groq"
                and self.switches == 0
            ):
                self._primary_error = failure.code
                # Recheck reset/expiry/cancel immediately before restart.
                self._guard()
                if self.http_calls >= self.settings.max_http_calls:
                    self._fail("run_budget_exhausted", 429)
                self.provider = "openrouter"
                self.switches = 1
                self.attempt += 1
                # Restart original task/tools/SAME snapshot. No provider transcript/CoT.
                self._messages = ()
                self._last_result = None
                self._validated_attempt = None
                try:
                    return self._send()
                except AgentFailure as reserve_failure:
                    self._finish_failure(reserve_failure)
            self._finish_failure(failure)
        raise AssertionError("unreachable")

    def _short_quota_wait(self, failure: AgentFailure) -> bool:
        """One confirmed short Groq-only after-validation 429, never a retry loop.

        Every freshness check completes before the next wait chunk, so no injected
        database transaction/lock is held during the pause. Default chunks bound
        cancellation observation to 100 ms plus a freshness check.
        """
        delay = failure.retry_after_seconds
        if (
            self.settings.openrouter_reserve_enabled
            or self.provider != "groq"
            or not self._force_validate_day
            or not self.validated_current_attempt
            or self._quota_retry_used
            or failure.code != "provider_quota"
            or failure.http_status != 429
            or self._last_reply_status != 429
            or type(delay) is not int
            or not 1 <= delay <= 5
            or self._last_request is None
            or self.http_calls >= self.settings.max_http_calls
        ):
            return False
        self._guard()
        # Preserve a full configured call timeout after the promised wait. An
        # already nearly-expired run must not begin recovery with a token window.
        if self._deadline - self._clock() < delay + self.settings.http_timeout_seconds:
            return False
        self._quota_retry_used = True
        ready_at = self._clock() + delay
        while True:
            self._guard()
            remaining = ready_at - self._clock()
            if remaining <= 0:
                break
            self._waiter(min(0.1, remaining))
        self._guard()
        return self._deadline - self._clock() >= self.settings.http_timeout_seconds

    def _finish_failure(self, failure: AgentFailure) -> NoReturn:
        if self._finished:
            raise failure
        self._guard()
        if failure.retry_after_seconds is not None:
            self.retry_after_seconds = max(
                self.retry_after_seconds or 0, failure.retry_after_seconds
            )
        if failure.code == "provider_quota" and (
            not self.settings.openrouter_reserve_enabled
            or self._primary_error == "provider_quota"
        ):
            self._fail("ai_quota_exhausted", 429)
        if failure.code in RETRYABLE or failure.code == "free_route_unavailable":
            self._fail("ai_temporarily_unavailable", 503)
        self._finished = True
        self._error = failure.code
        raise failure

    def check_tool(self, result: ProviderResult) -> None:
        """Preflight BEFORE executing even a read tool; no stale or ninth execution."""
        self._guard()
        if result != self._pending_tool or result.tool_call is None:
            self._fail("stale_attempt", 409)
        if result.attempt != self.attempt or result.provider != self.provider:
            self._fail("stale_attempt", 409)
        if self.tool_calls >= self.settings.max_tool_calls:
            self._fail("run_budget_exhausted", 429)

    def record_tool(self, result: ProviderResult, output_json: str) -> None:
        """Called only after a server tool succeeded; arguments validated by registry.

        The caller must terminally reject a registry/evidence error, using
        reject(), instead of asking another provider to bypass the rejected request.
        """
        self.check_tool(result)
        call = result.tool_call
        assert call is not None  # Established by check_tool before any execution.
        if len(output_json.encode()) > self.settings.max_tool_result_bytes:
            self._fail("run_budget_exhausted", 422)
        try:
            json_object(output_json)
        except (TypeError, ValueError):
            self._fail("invalid_provider_response", 422)
        self.tool_calls += 1
        if call.name == "validate_day":
            self._validated_attempt = self.attempt
        self._messages += (
            Message(role="assistant", tool_call=call),
            Message(role="tool", tool_call_id=call.id, content=output_json),
        )
        self._pending_tool = None

    def finalize(
        self, result: ProviderResult, validate_evidence: Callable[[str], None]
    ) -> str:
        self._guard()
        if self._force_validate_day and not self.validated_current_attempt:
            self._fail("invalid_provider_response", 422)
        if (
            result != self._last_result
            or result.attempt != self.attempt
            or result.provider != self.provider
            or result.content_json is None
            or self._pending_tool is not None
        ):
            self._fail("stale_attempt", 409)
        try:
            validate_evidence(result.content_json)
        except (ValueError, AgentFailure):
            self._fail("invalid_evidence", 422)
        self._guard()  # Never apply a result after reset/expiry during validation.
        self._finished = True
        return result.content_json

    def reject(self, code: ErrorCode) -> None:
        """Terminal registry/schema/evidence rejection; never triggers fallback."""
        self._fail(code, 422)

    def cancel(self) -> None:
        self._cancelled = True
        self.attempt += 1

    @property
    def validated_current_attempt(self) -> bool:
        return self._validated_attempt == self.attempt

    @property
    def quota_retries(self) -> int:
        """Dispatched bounded recoveries, not merely an interrupted wait."""
        return self._quota_retries

    @staticmethod
    def _known_usage(items: list[Usage]) -> Usage:
        prompts = [
            item.prompt_tokens for item in items if item.prompt_tokens is not None
        ]
        completions = [
            item.completion_tokens
            for item in items
            if item.completion_tokens is not None
        ]
        return Usage(
            prompt_tokens=sum(prompts) if prompts else None,
            completion_tokens=sum(completions) if completions else None,
        )

    @staticmethod
    def _complete_usage(items: list[Usage], calls: int) -> bool:
        return (
            calls > 0
            and len(items) == calls
            and all(
                item.prompt_tokens is not None and item.completion_tokens is not None
                for item in items
            )
        )

    def metadata(self) -> RunMetadata:
        known = [item for _, item in self._usage_history]
        per_provider = []
        for provider in ("groq", "openrouter"):
            typed_provider: ProviderName = provider
            calls = self._provider_http_calls[typed_provider]
            if not calls:
                continue
            items = [item for owner, item in self._usage_history if owner == provider]
            per_provider.append(
                ProviderUsage(
                    provider=typed_provider,
                    http_calls=calls,
                    known_usage=self._known_usage(items),
                    usage_complete=self._complete_usage(items, calls),
                )
            )
        return RunMetadata(
            run_id=self.run_id,
            provider=self.provider,
            model=(
                self.settings.groq_model
                if self.provider == "groq"
                else self.settings.openrouter_model
            ),
            switches=self.switches,
            http_calls=self.http_calls,
            tool_calls=self.tool_calls,
            elapsed_seconds=max(0.0, self._clock() - self._started),
            error_code=self._error,
            usage=self._usage,
            last_response_usage=self._usage,
            known_run_usage=self._known_usage(known),
            usage_complete=self._complete_usage(known, self.http_calls),
            known_usage_by_provider=tuple(per_provider),
        )
