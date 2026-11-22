"""One bounded serial read-only agent, independent of HTTP and browser state."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable
from datetime import date
from time import monotonic
from urllib.parse import urlencode

from app.operations.api_schemas import (
    OperationsReviewRead,
    ReviewLink,
    ReviewStatusCounts,
    ReviewTrace,
    ReviewUsage,
)
from app.operations.display import FrozenDisplay
from app.operations.foundation import PreparedReview, context_failure, prepare_review
from app.operations.provider_models import AgentFailure, ProviderSettings
from app.operations.providers import Transport
from app.operations.schemas import Entity, OperationError, ReferencedExplanation
from app.operations.snapshot import SnapshotReader

logger = logging.getLogger("uvicorn.error")
TransportFactory = Callable[[Callable[[], bool]], Transport]


class OperationsReviewService:
    def __init__(
        self,
        reader: SnapshotReader,
        settings: ProviderSettings,
        transport_factory: TransportFactory,
    ) -> None:
        self.reader = reader
        self.settings = settings
        self.transport_factory = transport_factory

    def review(
        self,
        cookie: str | None,
        selected_date: date,
        cancelled: Callable[[], bool],
        started_at: float,
    ) -> OperationsReviewRead:
        prepared: PreparedReview | None = None
        error_code: str | None = None
        try:
            if not self.settings.enabled:
                raise AgentFailure("agent_disabled")
            prepared = prepare_review(
                reader=self.reader,
                selected_date=selected_date,
                current_cookie=lambda: cookie,
                cancelled=cancelled,
                settings=self.settings,
                transport=self.transport_factory(cancelled),
                admit=lambda: (
                    True
                ),  # Worker slot and authoritative ingress admit first.
                force_validate_day=True,
                started_at=started_at,
            )
            trace: list[ReviewTrace] = []
            while True:
                response = prepared.run.call()
                if response.tool_call is not None:
                    start = monotonic()
                    tool_result = prepared.execute_tool(response)
                    trace.append(
                        ReviewTrace(
                            tool_name=tool_result.tool,
                            provider=response.provider,
                            elapsed_ms=max(0, int((monotonic() - start) * 1000)),
                        )
                    )
                    continue
                # The policy also enforces this. Keep the application acceptance
                # boundary explicit; a generated report without tools is not AI QA.
                if not prepared.run.validated_current_attempt:
                    prepared.run.reject("invalid_provider_response")
                final = prepared.finish(response)
                answer = prepared.tools.validate_references(final)
                result = self._response(prepared, answer, tuple(trace))
                self.reader.check(
                    prepared.context,
                    cookie,
                    cancelled=cancelled,
                    deadline=started_at + self.settings.deadline_seconds,
                )
                return result
        except AgentFailure as error:
            error_code = error.code
            raise
        except OperationError as error:
            failure = context_failure(error)
            error_code = failure.code
            raise failure from None
        except Exception:
            error_code = "internal_failure"
            raise
        finally:
            if prepared is not None:
                metadata = prepared.run.metadata()
                # Fixed allowlisted metadata only. Never log task, data, arguments,
                # model explanation/reasoning, provider bodies or credentials.
                logger.info(
                    "operations_review run=%s provider=%s model=%s requests=%s "
                    "tools=%s switches=%s quota_retries=%s error=%s",
                    metadata.run_id,
                    metadata.provider,
                    metadata.model,
                    metadata.http_calls,
                    metadata.tool_calls,
                    metadata.switches,
                    prepared.run.quota_retries,
                    error_code or metadata.error_code or "none",
                )

    @staticmethod
    def _response(
        prepared: PreparedReview,
        answer: ReferencedExplanation,
        trace: tuple[ReviewTrace, ...],
    ) -> OperationsReviewRead:
        snapshot = prepared.context.snapshot
        facts = tuple(
            row
            for row in snapshot.checks
            if row.rule in {"PLAN_PRESENCE", "ACTUAL_LEDGER"}
        )
        display = FrozenDisplay(snapshot, prepared.tools.link)
        groups = display.finding_groups()
        important = tuple(row for row in snapshot.checks if row.status != "pass")
        findings = tuple(row for group in groups for row in group.findings)
        evidence_ids = {
            identity for row in (*facts, *findings) for identity in row.evidence_ids
        } | {row.evidence_id for row in answer.references}
        evidence = tuple(row for row in snapshot.evidence if row.id in evidence_ids)
        when = snapshot.selected_date.isoformat()
        day = Entity(kind="day", id=when)
        query = urlencode({"date": when})
        links: list[ReviewLink] = [
            ReviewLink(entity=day, label="Daily Plan", path=f"/demo/daily?{query}"),
            ReviewLink(
                entity=day, label="Daily Entry", path=f"/demo/daily-entry?{query}"
            ),
            ReviewLink(entity=day, label="Kennel Map", path=f"/demo/kennel?{query}"),
        ]
        known_paths = {row.path for row in links}
        for item in evidence:
            for entity in item.entities:
                if entity.kind == "dog":
                    # Dog links live beside their selected names or scoped findings.
                    continue
                path = prepared.tools.link(entity)
                if path in known_paths:
                    continue
                known_paths.add(path)
                label = {
                    "activity": "Saved teams"
                    if path.endswith("/teams")
                    else "Daily Plan",
                    "actual": "Daily Entry",
                    "location": "Kennel Map",
                    "day": "Daily Plan",
                }[entity.kind]
                links.append(ReviewLink(entity=entity, label=label, path=path))
        counts = Counter(row.status for row in snapshot.checks)
        metadata = prepared.run.metadata()
        return OperationsReviewRead(
            snapshot_id=snapshot.id,
            selected_date=snapshot.selected_date,
            captured_at=snapshot.captured_at,
            explanation=answer.explanation,
            presentation=display.explanation(
                answer.explanation,
                executed_tools=tuple(row.tool_name for row in trace),
                references=answer.references,
            ),
            summary=display.summary(),
            finding_groups=groups,
            facts=facts,
            findings=findings,
            evidence=evidence,
            links=tuple(links),
            checked_rules=tuple(sorted({row.rule for row in snapshot.checks})),
            status_counts=ReviewStatusCounts(
                passed=counts["pass"],
                violations=counts["violation"],
                attention=counts["attention"],
                unverified=counts["unverified"],
            ),
            omitted_findings=max(0, len(important) - len(findings)),
            provider=metadata.provider,
            model=metadata.model,
            fallback=metadata.switches > 0,
            http_calls=metadata.http_calls,
            quota_retries=prepared.run.quota_retries,
            tool_calls=metadata.tool_calls,
            trace=trace,
            usage=ReviewUsage(
                known_prompt_tokens=metadata.known_run_usage.prompt_tokens,
                known_completion_tokens=metadata.known_run_usage.completion_tokens,
                incomplete=not metadata.usage_complete,
            ),
        )
