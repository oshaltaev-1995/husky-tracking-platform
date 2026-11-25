"""Rejected provider replies retain only bounded shape metadata; fake HTTP only."""

from __future__ import annotations

import json
from typing import Any

import pytest
from test_operations_providers import TOOLS, answer, tool_answer
from test_operations_transport import FakeConnection, FakeResponse, request, transport

from app.operations import diagnostics
from app.operations.provider_models import AgentFailure, HttpReply
from app.operations.providers import parse_reply

SENTINEL = "NEVER_EXPOSE_PRIVATE_BODY_COOKIE_KEY"


def parsed(body: dict[str, Any]) -> None:
    parse_reply(
        HttpReply(status=200, body=json.dumps(body).encode()), "groq", 0, TOOLS, 32768
    )


def envelope(**changes: Any) -> dict[str, Any]:
    value = json.loads(answer('{"explanation":"safe"}').body)
    message = value["choices"][0]["message"]
    message.update(changes)
    return value


def test_eight_historically_indistinguishable_failures_are_specific() -> None:
    fenced = envelope(content='```json\n{"explanation":"' + SENTINEL + '"}\n```')
    plain = envelope(content=SENTINEL)
    length = envelope()
    length["choices"][0]["finish_reason"] = "length"
    multiple = json.loads(tool_answer().body)
    multiple["choices"][0]["message"]["tool_calls"] *= 2
    conflict = envelope(tool_calls=[{"private": SENTINEL}])
    usage = envelope()
    usage["usage"] = SENTINEL
    malformed = {"choices": SENTINEL}
    array = envelope(content='["' + SENTINEL + '"]')
    reasons = []
    for body in (fenced, plain, length, multiple, conflict, usage, malformed, array):
        with pytest.raises(AgentFailure) as caught:
            parsed(body)
        error = caught.value
        assert (error.code, error.http_status) == ("invalid_provider_response", 502)
        assert str(error) == "invalid_provider_response"
        assert error.diagnostic is not None
        assert error.diagnostic.upstream_http_status == 200
        assert SENTINEL not in repr(error)
        assert SENTINEL not in error.diagnostic.model_dump_json()
        reasons.append(error.diagnostic.failure_reason)
    assert reasons == [
        "content_fenced_json",
        "content_json",
        "finish_length",
        "tool_count",
        "finish_tool_conflict",
        "usage_type",
        "invalid_choices",
        "content_not_object",
    ]
    assert len(set(reasons)) == 8


@pytest.mark.parametrize(
    "body,reason",
    [
        (b"not-json", "envelope_json"),
        (b'{"choices":[],"choices":[]}', "envelope_json"),
        (b'{"choices":[],"private":NaN}', "envelope_json"),
        (b'{"choices":[],"private":Infinity}', "envelope_json"),
        (b'{"choices":"\xff"}', "envelope_json"),
        (
            b'{"choices":[{"finish_reason":"stop","message":{"content":"{\\"v\\":1,\\"v\\":2}"}}]}',
            "content_json",
        ),
    ],
)
def test_strict_json_failures_do_not_leak(body: bytes, reason: str) -> None:
    with pytest.raises(AgentFailure) as caught:
        parse_reply(HttpReply(status=200, body=body), "groq", 0, TOOLS, 32768)
    assert caught.value.diagnostic is not None
    assert caught.value.diagnostic.failure_reason == reason


def test_unknown_finish_content_type_and_partial_usage_are_normalized() -> None:
    body = envelope(content={"secret": SENTINEL})
    body["choices"][0]["finish_reason"] = SENTINEL
    body["usage"] = {"prompt_tokens": 23, "completion_tokens": SENTINEL}
    with pytest.raises(AgentFailure) as caught:
        parsed(body)
    diagnostic = caught.value.diagnostic
    assert diagnostic is not None
    assert diagnostic.finish_reason == "other"
    assert diagnostic.content_type == "object"
    assert diagnostic.prompt_tokens == 23
    assert diagnostic.completion_tokens is None
    assert diagnostic.content_bytes is None
    assert SENTINEL not in diagnostic.model_dump_json()


@pytest.mark.parametrize(
    "usage",
    [
        [],
        "bad",
        12,
        True,
        {"prompt_tokens": True},
        {"prompt_tokens": -1},
        {"completion_tokens": "12"},
    ],
)
def test_invalid_usage_is_never_coerced_or_zero(usage: object) -> None:
    body = envelope()
    body["usage"] = usage
    with pytest.raises(AgentFailure) as caught:
        parsed(body)
    diagnostic = caught.value.diagnostic
    assert diagnostic is not None and diagnostic.failure_reason == "usage_type"
    assert diagnostic.prompt_tokens is None and diagnostic.completion_tokens is None


def test_missing_metadata_stays_unknown_and_success_diagnostic_is_internal() -> None:
    body = envelope()
    del body["usage"]
    reply = HttpReply(status=200, body=json.dumps(body).encode())
    result = parse_reply(reply, "groq", 0, TOOLS, 32768)
    assert result.diagnostic is not None
    assert result.diagnostic.prompt_tokens is None
    assert result.diagnostic.completion_tokens is None
    assert result.diagnostic.failure_reason is None
    assert result.diagnostic.finish_reason == "stop"
    assert "diagnostic" not in result.model_dump()
    assert "diagnostic" not in repr(result)


def test_instrumentation_failure_cannot_replace_success_or_original_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError(SENTINEL)

    monkeypatch.setattr(diagnostics.ResponseDiagnostic, "model_validate", broken)
    parsed(envelope())
    with pytest.raises(AgentFailure, match="^invalid_provider_response$") as caught:
        parsed(envelope(content=SENTINEL))
    assert caught.value.http_status == 502 and caught.value.diagnostic is None
    assert SENTINEL not in repr(caught.value)


@pytest.mark.parametrize(
    "headers,body,reason,read_count",
    [
        ({"Content-Encoding": SENTINEL}, b"", "transport_encoding", 0),
        ({"Content-Length": SENTINEL}, b"", "response_length", 0),
        ({"Content-Length": "1025"}, b"", "response_size", 0),
        ({}, b"x" * 1025, "response_size", 1),
        ({"Content-Length": "100"}, b"{}", "transport_fragmentation", 2),
    ],
)
def test_transport_diagnostics_preserve_status_and_read_bounds(
    headers: dict[str, str], body: bytes, reason: str, read_count: int
) -> None:
    response = FakeResponse(body, headers=headers)
    connection = FakeConnection(response)
    with pytest.raises(AgentFailure) as caught:
        transport(connection)(request())
    diagnostic = caught.value.diagnostic
    assert diagnostic is not None
    assert diagnostic.failure_reason == reason
    assert diagnostic.upstream_http_status == 200
    assert len(response.read_sizes) == read_count
    assert len(connection.requests) == 1
    assert SENTINEL not in repr(caught.value)
    assert SENTINEL not in diagnostic.model_dump_json()


def test_error_http_body_not_read_for_diagnostics() -> None:
    response = FakeResponse(SENTINEL.encode(), status=429)
    connection = FakeConnection(response)
    reply = transport(connection)(request())
    assert reply.body == b"" and not response.read_sizes
    with pytest.raises(AgentFailure) as caught:
        parse_reply(reply, "groq", 0, TOOLS, 32768)
    assert caught.value.code == "provider_quota"
    diagnostic = caught.value.diagnostic
    assert diagnostic is not None and diagnostic.upstream_http_status == 429
    assert diagnostic.failure_reason == "transport_status"


def test_metadata_enums_and_numbers_reject_untrusted_values() -> None:
    assert diagnostics.safe_diagnostic(failure_reason=SENTINEL) is None
    assert diagnostics.safe_diagnostic(finish_reason=SENTINEL) is None
    assert diagnostics.safe_diagnostic(prompt_tokens=True) is None
    assert diagnostics.safe_diagnostic(response_bytes=10**100) is None


def test_rejected_choices_still_retain_valid_envelope_usage() -> None:
    body = {"choices": [], "usage": {"prompt_tokens": 31, "completion_tokens": 7}}
    with pytest.raises(AgentFailure) as caught:
        parsed(body)
    diagnostic = caught.value.diagnostic
    assert diagnostic is not None
    assert diagnostic.prompt_tokens == 31 and diagnostic.completion_tokens == 7
    assert diagnostic.failure_reason == "invalid_choices"
