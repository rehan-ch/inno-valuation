"""The AI client: what is sent to the API, how failures are reported, and which client is
used where. The SDK is faked; nothing leaves the machine."""

import uuid
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

from app.ai import client as ai_client
from app.ai.client import (
    OFFLINE_MODEL,
    AiNotConfiguredError,
    AiRequest,
    AiRequestError,
    AiUnavailableError,
    AnthropicAiClient,
    OfflineAiClient,
    get_ai_client,
    is_offline,
)
from app.core.settings import Settings

_URL = "https://api.anthropic.com/v1/messages"


def _request(**changes: Any) -> AiRequest:
    values: dict[str, Any] = {
        "run_id": uuid.uuid4(),
        "model": "claude-sonnet-5-5",
        "effort": "low",
        "max_tokens": 4000,
        "timeout_seconds": 60.0,
        "system": "the system prompt",
        "user": "the user prompt",
        "output_schema": {"type": "object", "properties": {}},
        "offline_reply": '{"sample": true}',
    }
    return AiRequest(**{**values, **changes})


class _FakeMessages:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    def create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict[str, str]],
        output_config: dict[str, Any],
        betas: list[str],
        fallbacks: str,
    ) -> object:
        # The exact keyword set the real call uses, so a renamed SDK parameter fails here.
        self.calls.append(
            {
                "model": model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": messages,
                "output_config": output_config,
                "betas": betas,
                "fallbacks": fallbacks,
            }
        )
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class _FakeSdk:
    def __init__(self, outcome: object) -> None:
        self.messages = _FakeMessages(outcome)
        self.options: dict[str, Any] = {}
        self.beta = SimpleNamespace(messages=self.messages)

    def with_options(self, **options: Any) -> "_FakeSdk":
        self.options = options
        return self


def _message(**changes: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "content": [
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text='{"a": 1}'),
        ],
        "model": "claude-sonnet-5-5",
        "stop_reason": "end_turn",
        "usage": SimpleNamespace(input_tokens=612, output_tokens=148),
        "_request_id": "req_abc",
    }
    return SimpleNamespace(**{**values, **changes})


@pytest.fixture
def sdk(monkeypatch: pytest.MonkeyPatch) -> Any:
    def install(outcome: object) -> _FakeSdk:
        fake = _FakeSdk(outcome)
        monkeypatch.setattr(ai_client, "_sdk_client", lambda api_key: fake)
        return fake

    return install


def test_the_request_sent_to_the_api(sdk: Any) -> None:
    fake = sdk(_message())
    reply = AnthropicAiClient("key").complete(_request())
    [call] = fake.messages.calls
    assert call == {
        "model": "claude-sonnet-5-5",
        "max_tokens": 4000,
        "system": "the system prompt",
        "messages": [{"role": "user", "content": "the user prompt"}],
        "output_config": {
            "effort": "low",
            "format": {"type": "json_schema", "schema": {"type": "object", "properties": {}}},
        },
        "betas": ["server-side-fallback-2026-07-01"],
        "fallbacks": "default",
    }
    # Removed from the API (2026-10-21) and never sent; the offline reply never leaves.
    assert not {"temperature", "top_p", "top_k"} & set(call)
    assert '{"sample": true}' not in str(call)
    assert fake.options == {"timeout": 60.0}
    assert reply.text == '{"a": 1}'
    assert (reply.model, reply.stop_reason, reply.request_id) == (
        "claude-sonnet-5-5",
        "end_turn",
        "req_abc",
    )
    assert (reply.input_tokens, reply.output_tokens) == (612, 148)


def _status_error(cls: type[anthropic.APIStatusError], status: int) -> anthropic.APIStatusError:
    response = httpx2.Response(
        status, request=httpx2.Request("POST", _URL), headers={"request-id": "req_failed"}
    )
    return cls("failed", response=response, body=None)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (anthropic.APITimeoutError(request=httpx2.Request("POST", _URL)), AiUnavailableError),
        (anthropic.APIConnectionError(request=httpx2.Request("POST", _URL)), AiUnavailableError),
        (_status_error(anthropic.RateLimitError, 429), AiUnavailableError),
        (_status_error(anthropic.InternalServerError, 500), AiUnavailableError),
        (_status_error(anthropic.APIStatusError, 529), AiUnavailableError),
        (_status_error(anthropic.BadRequestError, 400), AiRequestError),
        (_status_error(anthropic.AuthenticationError, 401), AiRequestError),
        (_status_error(anthropic.NotFoundError, 404), AiRequestError),
    ],
)
def test_failures_are_reported_by_kind(sdk: Any, error: Exception, expected: type) -> None:
    sdk(error)
    with pytest.raises(expected) as raised:
        AnthropicAiClient("key").complete(_request())
    if isinstance(error, anthropic.APIStatusError):
        assert "req_failed" in str(raised.value)  # the API's request id, for tracing


def test_the_offline_stand_in_answers_with_the_sample_and_costs_nothing() -> None:
    reply = OfflineAiClient().complete(_request())
    assert reply.text == '{"sample": true}'
    assert reply.model == OFFLINE_MODEL
    assert (reply.input_tokens, reply.output_tokens, reply.request_id) == (0, 0, None)


def _settings(environment: str, key: str = "") -> Settings:
    return Settings(
        environment=environment,  # type: ignore[arg-type]
        anthropic_api_key=key,
        secret_key="s" * 40,
        frontend_origin="https://app.example.com",
    )


@pytest.mark.parametrize(
    ("environment", "key", "expected"),
    [
        ("test", "sk-live", OfflineAiClient),  # tests never reach the live API
        ("development", "", OfflineAiClient),
        ("development", "sk-live", AnthropicAiClient),
        ("production", "sk-live", AnthropicAiClient),
    ],
)
def test_which_client_is_used(
    monkeypatch: pytest.MonkeyPatch, environment: str, key: str, expected: type
) -> None:
    monkeypatch.setattr(ai_client, "get_settings", lambda: _settings(environment, key))
    assert isinstance(get_ai_client(), expected)


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_a_deployed_server_without_a_key_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setattr(ai_client, "get_settings", lambda: _settings(environment))
    with pytest.raises(AiNotConfiguredError):
        get_ai_client()
    assert is_offline() is False  # no sample text is ever treated as current there
