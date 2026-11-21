"""Explicit programmatic steps, not an agent loop, route, UI or live transport."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from time import monotonic

from app.operations.policy import ProviderRun
from app.operations.provider_models import (
    AgentFailure,
    ErrorCode,
    ProviderResult,
    ProviderSettings,
    ToolContract,
)
from app.operations.providers import Transport
from app.operations.schemas import OperationError, ToolResult
from app.operations.snapshot import RunContext, SnapshotReader
from app.operations.tools import FrozenTools

CONTEXT_ERRORS: dict[str, ErrorCode] = {
    "session_required": "session_expired",
    "session_expired": "session_expired",
    "context_changed": "context_changed",
    "cancelled": "cancelled",
    "date_out_of_range": "date_out_of_range",
    "snapshot_too_large": "snapshot_too_large",
}


class PreparedReview:
    def __init__(self, context: RunContext, tools: FrozenTools, run: ProviderRun):
        self.context, self.tools, self.run = context, tools, run

    def execute_tool(self, response: ProviderResult) -> ToolResult:
        self.run.check_tool(response)
        call = response.tool_call
        if call is None:
            self.run.reject("invalid_provider_response")
            raise AssertionError("unreachable")
        try:
            result = self.tools.execute(call.name, call.arguments_json)
        except OperationError as error:
            self.run.reject(
                "forbidden_tool"
                if error.code == "tool_not_allowed"
                else "invalid_provider_response"
            )
            raise AssertionError("unreachable") from None
        self.run.record_tool(response, result.model_dump_json())
        return result

    def finish(self, response: ProviderResult) -> str:
        def validate(value: str) -> None:
            try:
                self.tools.validate_references(value)
            except OperationError:
                raise AgentFailure("invalid_evidence", http_status=422) from None

        return self.run.finalize(response, validate)


def prepare_review(
    *,
    reader: SnapshotReader,
    selected_date: date,
    current_cookie: Callable[[], str | None],
    cancelled: Callable[[], bool],
    settings: ProviderSettings,
    transport: Transport,
    admit: Callable[[], bool],
) -> PreparedReview:
    started_at = monotonic()
    # No cookie resolution, snapshot work, or outbound request when disabled.
    if not settings.enabled:
        raise AgentFailure("agent_disabled")
    # Admission is a required host boundary, not a per-process in-memory limiter.
    if not admit():
        raise AgentFailure("app_rate_limited", http_status=429)
    if cancelled():
        raise AgentFailure("cancelled", http_status=409)
    try:
        context = reader.capture(current_cookie(), selected_date)
    except OperationError as error:
        raise AgentFailure(
            CONTEXT_ERRORS.get(error.code, "provider_configuration"),
            http_status=409,
        ) from None

    def check() -> None:
        try:
            reader.check(context, current_cookie(), cancelled=cancelled())
        except OperationError as error:
            raise AgentFailure(
                CONTEXT_ERRORS.get(error.code, "provider_configuration"),
                http_status=409,
            ) from None

    tools = FrozenTools(context.snapshot)
    run = ProviderRun(
        settings=settings,
        transport=transport,
        snapshot_id=str(context.snapshot.id),
        snapshot_json=tools.provider_context(),
        task="Review operations for the selected demo date. Use server evidence; "
        "do not infer that planned work ran.",
        tools=tuple(
            ToolContract(
                name=name,
                description=f"Read-only {name}; same frozen snapshot, "
                "no execution of plans or solver.",
                parameters_json=schema,
            )
            for name, schema in tools.contracts()
        ),
        check_context=check,
        admit=lambda: True,  # Already admitted above; never re-admit on reserve.
        started_at=started_at,
    )
    return PreparedReview(context, tools, run)
