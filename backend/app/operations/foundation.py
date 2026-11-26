"""Read-only snapshot/tool boundary shared by scripted tests and the review loop."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from time import monotonic

from pydantic import ValidationError

from app.operations.diagnostics import annotate_failure, safe_diagnostic
from app.operations.observations import ObservationCatalog, RenderedSelection
from app.operations.policy import ProviderRun
from app.operations.provider_models import (
    AgentFailure,
    ErrorCode,
    ProviderResult,
    ProviderSettings,
    ToolContract,
    json_object,
)
from app.operations.providers import Transport
from app.operations.schemas import OperationError, ReferencedExplanation, ToolResult
from app.operations.snapshot import RunContext, SnapshotReader
from app.operations.tools import TOOL_DESCRIPTIONS, FrozenTools

CONTEXT_ERRORS: dict[str, ErrorCode] = {
    "session_required": "session_expired",
    "session_expired": "session_expired",
    "context_changed": "context_changed",
    "cancelled": "cancelled",
    "date_out_of_range": "date_out_of_range",
    "snapshot_too_large": "snapshot_too_large",
    "timeout": "timeout",
    "database_unavailable": "ai_temporarily_unavailable",
}


def context_failure(error: OperationError) -> AgentFailure:
    status = (
        504
        if error.code == "timeout"
        else 503
        if error.code == "database_unavailable"
        else 409
    )
    return AgentFailure(
        CONTEXT_ERRORS.get(error.code, "provider_configuration"), http_status=status
    )


class PreparedReview:
    def __init__(
        self,
        context: RunContext,
        tools: FrozenTools,
        run: ProviderRun,
        *,
        observation_selection: bool = False,
    ):
        self.context, self.tools, self.run = context, tools, run
        self._observation_selection = observation_selection
        self._catalog: ObservationCatalog | None = None

    def execute_tool(self, response: ProviderResult) -> ToolResult:
        self.run.check_tool(response)
        call = response.tool_call
        if call is None:
            self.run.reject("invalid_provider_response")
            raise AssertionError("unreachable")
        try:
            result = self.tools.execute(call.name, call.arguments_json)
        except OperationError as error:
            self.run.note_diagnostic(
                safe_diagnostic(failure_stage="tool", failure_reason="tool_arguments")
            )
            self.run.reject(
                "forbidden_tool"
                if error.code == "tool_not_allowed"
                else "invalid_provider_response"
            )
            raise AssertionError("unreachable") from None
        catalog: ObservationCatalog | None = None
        if self._observation_selection and call.name == "validate_day":
            try:
                catalog = ObservationCatalog(
                    self.context.snapshot,
                    result,
                    self.run.run_id,
                    self.tools.link,
                )
            except OperationError:
                self.run.note_diagnostic(
                    safe_diagnostic(
                        failure_stage="reference_validation",
                        failure_reason="reference_membership",
                    )
                )
                self.run.reject("invalid_evidence")
        self.run.record_tool(
            response,
            result.model_dump_json(),
            catalog_json=catalog.provider_json() if catalog is not None else None,
        )
        self._catalog = catalog
        return result

    def finish_selection(self, response: ProviderResult) -> RenderedSelection:
        """Decode issued IDs, never consume provider prose as a factual result."""
        if not self._observation_selection or self._catalog is None:
            self.run.reject("invalid_evidence")
            raise AssertionError("unreachable")
        rendered: RenderedSelection | None = None

        def validate(value: str) -> None:
            nonlocal rendered
            assert self._catalog is not None
            try:
                rendered = self._catalog.select(value)
                # Normal decoding expands previously bound references; validate
                # against the very same frozen registry, with no DB fact reads.
                self.tools.validate_references(rendered.answer.model_dump_json())
            except OperationError as error:
                schema = error.code == "invalid_selection"
                raise annotate_failure(
                    AgentFailure("invalid_evidence", http_status=422),
                    "final_schema" if schema else "reference_validation",
                    "final_schema" if schema else "reference_membership",
                ) from None

        self.run.finalize(response, validate)
        assert rendered is not None
        return rendered

    def finish(self, response: ProviderResult) -> str:
        def validate(value: str) -> None:
            # Separate schema rejection from verified evidence membership without
            # ever exposing Pydantic inputs or arbitrary exception strings.
            try:
                json_object(value)
                ReferencedExplanation.model_validate_json(value)
            except (ValidationError, ValueError, TypeError):
                raise annotate_failure(
                    AgentFailure("invalid_evidence", http_status=422),
                    "final_schema",
                    "final_schema",
                ) from None
            try:
                self.tools.validate_references(value)
            except OperationError:
                raise annotate_failure(
                    AgentFailure("invalid_evidence", http_status=422),
                    "reference_validation",
                    "reference_membership",
                ) from None

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
    force_validate_day: bool = False,
    observation_selection: bool = False,
    started_at: float | None = None,
) -> PreparedReview:
    started_at = monotonic() if started_at is None else started_at
    deadline = started_at + settings.deadline_seconds
    # No cookie resolution, snapshot work, or outbound request when disabled.
    if not settings.enabled:
        raise AgentFailure("agent_disabled")
    if observation_selection and (
        not force_validate_day or settings.openrouter_reserve_enabled
    ):
        raise AgentFailure("provider_configuration")
    # Admission is a required host boundary, not a per-process in-memory limiter.
    if not admit():
        raise AgentFailure("app_rate_limited", http_status=429)
    if cancelled():
        raise AgentFailure("cancelled", http_status=409)
    try:
        context = reader.capture(
            current_cookie(), selected_date, deadline=deadline, cancelled=cancelled
        )
    except OperationError as error:
        raise context_failure(error) from None

    def check() -> None:
        try:
            reader.check(
                context, current_cookie(), cancelled=cancelled, deadline=deadline
            )
        except OperationError as error:
            raise context_failure(error) from None

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
                description=TOOL_DESCRIPTIONS[name],
                parameters_json=schema,
            )
            for name, schema in tools.contracts()
        ),
        check_context=check,
        admit=lambda: True,  # Already admitted above; never re-admit on reserve.
        started_at=started_at,
        force_validate_day=force_validate_day,
        observation_selection=observation_selection,
    )
    return PreparedReview(
        context, tools, run, observation_selection=observation_selection
    )
