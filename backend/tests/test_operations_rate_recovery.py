"""One authorized short after-tool quota recovery; fake time/HTTP only."""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from pydantic import SecretStr

from app.operations.policy import ProviderRun
from app.operations.provider_models import (
    AgentFailure,
    HttpReply,
    HttpRequest,
    ProviderSettings,
    ToolContract,
)

TOOLS = tuple(
    ToolContract(
        name=name,
        description="Read one frozen selected day",
        parameters_json='{"type":"object","properties":{}}',
    )
    for name in ("validate_day", "get_day_plan")
)


class Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.waits: list[float] = []
        self.after_wait: Callable[[], None] = lambda: None

    def __call__(self) -> float:
        return self.now

    def wait(self, seconds: float) -> None:
        assert 0 < seconds <= 0.1
        self.waits.append(seconds)
        self.now += seconds
        self.after_wait()


class Transport:
    def __init__(self, *replies: HttpReply | Exception) -> None:
        self.replies = list(replies)
        self.requests: list[HttpRequest] = []
        self.after_request: Callable[[], None] = lambda: None

    def __call__(self, request: HttpRequest) -> HttpReply:
        self.requests.append(request)
        result = self.replies.pop(0)
        self.after_request()
        if isinstance(result, Exception):
            raise result
        return result


def tool(name: str = "validate_day") -> HttpReply:
    return HttpReply(
        status=200,
        body=json.dumps(
            {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "frozen-read",
                                    "type": "function",
                                    "function": {"name": name, "arguments": "{}"},
                                }
                            ]
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 1},
            }
        ).encode(),
    )


def final(content: str = '{"explanation":"Frozen facts","references":[]}') -> HttpReply:
    return HttpReply(
        status=200,
        body=json.dumps(
            {
                "choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 4},
            }
        ).encode(),
    )


def active(
    transport: Transport,
    clock: Clock,
    *,
    check: Callable[[], None] = lambda: None,
    max_http_calls: int = 6,
    deadline: float = 45,
) -> ProviderRun:
    return ProviderRun(
        settings=ProviderSettings(
            enabled=True,
            groq_free_account_confirmed=True,
            groq_api_key=SecretStr("offline-primary-not-a-project-key"),
            openrouter_api_key=SecretStr("offline-retained-key-not-used"),
            max_http_calls=max_http_calls,
            deadline_seconds=deadline,
        ),
        transport=transport,
        snapshot_id="one-frozen-snapshot",
        snapshot_json='{"selected_date":"2026-03-29","plan_exists":true}',
        task="Review this frozen synthetic day",
        tools=TOOLS,
        check_context=check,
        admit=lambda: True,
        monotonic=clock,
        waiter=clock.wait,
        force_validate_day=True,
    )


def validate_once(run: ProviderRun) -> None:
    result = run.call()
    assert result.tool_call is not None and result.tool_call.name == "validate_day"
    run.record_tool(result, '{"snapshot_id":"one-frozen-snapshot","checks":[]}')


@pytest.mark.parametrize("delay", [1, 5])
def test_one_short_quota_recovery_reuses_exact_request_and_counts_unknown_usage(
    delay: int,
) -> None:
    clock = Clock()
    transport = Transport(
        tool(), HttpReply(status=429, retry_after=str(delay)), final()
    )
    run = active(transport, clock)
    validate_once(run)
    result = run.call()
    assert run.finalize(result, lambda _: None)
    assert len(transport.requests) == run.http_calls == 3
    assert run.tool_calls == 1 and run.switches == 0 and run.provider == "groq"
    assert run.quota_retries == 1
    rejected, repeated = transport.requests[1:]
    assert rejected.body_json == repeated.body_json
    assert rejected.url == repeated.url == transport.requests[0].url
    assert rejected.authorization == repeated.authorization
    assert repeated.retries == 0 and repeated.follow_redirects is False
    assert "tool_choice" not in json.loads(repeated.body_json)
    assert (
        json.loads(repeated.body_json)["response_format"]["json_schema"]["strict"]
        is True
    )
    assert sum(clock.waits) >= delay and clock.now < delay + 0.01
    metadata = run.metadata()
    assert metadata.known_run_usage.prompt_tokens == 30
    assert metadata.known_run_usage.completion_tokens == 5
    assert metadata.usage_complete is False
    assert metadata.known_usage_by_provider[0].http_calls == 3
    assert metadata.known_usage_by_provider[0].usage_complete is False
    assert metadata.elapsed_seconds == clock.now


@pytest.mark.parametrize("retry_after", [None, "bad", "0", "-1", "1.5", "6", "30"])
def test_no_recovery_without_valid_short_retry_after(retry_after: str | None) -> None:
    clock = Clock()
    transport = Transport(
        tool(), HttpReply(status=429, retry_after=retry_after), final()
    )
    run = active(transport, clock)
    validate_once(run)
    with pytest.raises(AgentFailure, match="^ai_quota_exhausted$"):
        run.call()
    assert len(transport.requests) == 2 and not clock.waits


def test_initial_turn_quota_is_terminal_without_wait_or_reserve() -> None:
    clock = Clock()
    transport = Transport(HttpReply(status=429, retry_after="1"), tool(), final())
    run = active(transport, clock)
    with pytest.raises(AgentFailure, match="^ai_quota_exhausted$"):
        run.call()
    assert len(transport.requests) == 1 and run.tool_calls == 0 and not clock.waits


def test_after_validation_retry_cannot_open_another_tool_turn() -> None:
    clock = Clock()
    transport = Transport(
        tool(), HttpReply(status=429, retry_after="1"), tool("get_day_plan"), final()
    )
    run = active(transport, clock)
    validate_once(run)
    with pytest.raises(AgentFailure, match="^forbidden_tool$"):
        run.call()
    assert len(transport.requests) == 3 and run.tool_calls == 1
    assert run.quota_retries == 1
    assert sum(clock.waits) >= 1 and clock.now < 1.01


def test_retry_returning_second_quota_is_terminal_and_keeps_latest_hint() -> None:
    clock = Clock()
    transport = Transport(
        tool(),
        HttpReply(status=429, retry_after="1"),
        HttpReply(status=429, retry_after="5"),
        final(),
    )
    run = active(transport, clock)
    validate_once(run)
    with pytest.raises(AgentFailure, match="^ai_quota_exhausted$") as failure:
        run.call()
    assert failure.value.retry_after_seconds == 5
    assert len(transport.requests) == run.http_calls == 3
    assert run.quota_retries == 1 and run.tool_calls == 1
    assert sum(clock.waits) >= 1 and clock.now < 1.01


@pytest.mark.parametrize(
    "case", ["http_budget", "deadline", "time_consumed_while_waiting"]
)
def test_insufficient_time_or_http_budget_prevents_extra_dispatch(case: str) -> None:
    clock = Clock()
    transport = Transport(tool(), HttpReply(status=429, retry_after="1"), final())
    run = active(transport, clock, max_http_calls=2 if case == "http_budget" else 6)
    validate_once(run)
    if case == "deadline":
        clock.now = 33  # Less than delay1 + configured HTTP timeout12 remains.
    elif case == "time_consumed_while_waiting":
        clock.now = 30
        clock.after_wait = lambda: setattr(clock, "now", clock.now + 3.5)
    with pytest.raises(AgentFailure, match="^ai_quota_exhausted$"):
        run.call()
    assert len(transport.requests) == 2 and run.http_calls == 2
    assert run.quota_retries == 0
    assert bool(clock.waits) is (case == "time_consumed_while_waiting")


@pytest.mark.parametrize("change", ["cancelled", "context_changed", "session_expired"])
def test_context_invalidation_during_wait_blocks_retry(change: str) -> None:
    clock = Clock()
    failure: list[str] = []

    def check() -> None:
        if failure:
            raise AgentFailure(failure[0], http_status=409)  # type: ignore[arg-type]

    transport = Transport(tool(), HttpReply(status=429, retry_after="1"), final())
    run = active(transport, clock, check=check)
    validate_once(run)
    clock.after_wait = (
        run.cancel if change == "cancelled" else lambda: failure.append(change)
    )
    with pytest.raises(AgentFailure, match=f"^{change}$"):
        run.call()
    assert len(transport.requests) == 2 and run.tool_calls == 1
    assert run.quota_retries == 0
    assert clock.now <= 0.1


def test_context_checked_after_retry_response_prevents_stale_final() -> None:
    clock = Clock()
    current = [True]

    def check() -> None:
        if not current[0]:
            raise AgentFailure("context_changed", http_status=409)

    transport = Transport(tool(), HttpReply(status=429, retry_after="1"), final())
    run = active(transport, clock, check=check)
    validate_once(run)

    def invalidate_after_reply() -> None:
        if len(transport.requests) == 3:
            current[0] = False

    transport.after_request = invalidate_after_reply
    with pytest.raises(AgentFailure, match="^context_changed$"):
        run.call()
    assert run.http_calls == 3 and run.tool_calls == 1 and run.switches == 0


@pytest.mark.parametrize(
    "reply,code",
    [
        (HttpReply(status=401), "provider_authentication"),
        (HttpReply(status=402), "provider_payment_required"),
        (HttpReply(status=503), "ai_temporarily_unavailable"),
        (OSError("unknown remote outcome"), "ai_temporarily_unavailable"),
        (TimeoutError(), "ai_temporarily_unavailable"),
        (final("invalid JSON"), "invalid_provider_response"),
        (
            AgentFailure("provider_quota", http_status=429, retry_after_seconds=1),
            "ai_quota_exhausted",
        ),
    ],
)
def test_other_failures_and_unconfirmed_quota_do_not_retry(
    reply: HttpReply | Exception, code: str
) -> None:
    clock = Clock()
    transport = Transport(tool(), reply, final())
    run = active(transport, clock)
    validate_once(run)
    with pytest.raises(AgentFailure, match=f"^{code}$"):
        run.call()
    assert len(transport.requests) == 2 and not clock.waits


def test_invalid_final_evidence_after_recovery_is_terminal() -> None:
    clock = Clock()
    transport = Transport(
        tool(), HttpReply(status=429, retry_after="1"), final(), final()
    )
    run = active(transport, clock)
    validate_once(run)
    result = run.call()

    def refuse(_: str) -> None:
        raise AgentFailure("invalid_evidence", http_status=422)

    with pytest.raises(AgentFailure, match="^invalid_evidence$"):
        run.finalize(result, refuse)
    with pytest.raises(AgentFailure, match="^run_finished$"):
        run.call()
    assert len(transport.requests) == 3 and run.tool_calls == 1
