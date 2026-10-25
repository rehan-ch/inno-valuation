"""The connection to the AI model. Every AI call in the app goes through ``get_ai_client``.

- ``AnthropicAiClient`` when ``ANTHROPIC_API_KEY`` is set: the official SDK, structured
  JSON output against the touchpoint's schema, the effort from config/ai.yml, a timeout
  per attempt and the SDK's own retries with backoff (timeouts, connection errors, 429,
  5xx). Refusal fallback is on: if the model declines for policy reasons, the API retries
  on its default substitute and reports which model answered.
- ``OfflineAiClient`` in development and test without a key: answers with the
  touchpoint's sample reply, says so in ``model``, and sends nothing anywhere. Tests always
  use it or a recorded client (``override_ai_client``), never the live API.
- In staging or production without a key, ``get_ai_client`` raises
  ``AiNotConfiguredError``, so the run fails loudly instead of showing sample text.

Clients see only the prompts. They never see a database row, and they log no user text.
"""

import logging
import uuid
from dataclasses import dataclass, field
from functools import cache
from typing import Any, Final, Protocol

import anthropic

from app.ai.config import Effort
from app.core.settings import get_settings

logger = logging.getLogger(__name__)

# The ``response_model`` of a run answered by the offline stand-in.
OFFLINE_MODEL: Final = "offline"

# Retries inside one attempt, with the SDK's exponential backoff.
SDK_MAX_RETRIES: Final = 2

# Server-side refusal fallback, routed by the API by refusal category.
_FALLBACK_BETA: Final = "server-side-fallback-2026-07-01"

_SERVER_ERROR_MIN: Final = 500


class AiError(Exception):
    """The call failed. The message is safe to log and store: it holds no user text."""


class AiUnavailableError(AiError):
    """The service did not answer in time or was overloaded, after the SDK's retries."""


class AiRequestError(AiError):
    """The service refused the request itself (a bad request, key or model)."""


class AiNotConfiguredError(AiError):
    """No AI key on a deployed server."""


@dataclass(frozen=True)
class AiRequest:
    run_id: uuid.UUID  # traces the call in our logs
    model: str
    effort: Effort
    max_tokens: int
    timeout_seconds: float
    system: str
    user: str
    output_schema: dict[str, Any]
    # What the offline stand-in answers. Never sent anywhere.
    offline_reply: str = field(repr=False)


@dataclass(frozen=True)
class AiReply:
    text: str
    model: str
    stop_reason: str | None
    input_tokens: int
    output_tokens: int
    request_id: str | None


class AiClient(Protocol):
    @property
    def offline(self) -> bool: ...

    def complete(self, request: AiRequest) -> AiReply: ...


@cache
def _sdk_client(api_key: str) -> anthropic.Anthropic:
    # One client per process, so connections are reused between calls.
    return anthropic.Anthropic(api_key=api_key, max_retries=SDK_MAX_RETRIES)


class AnthropicAiClient:
    offline = False

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def complete(self, request: AiRequest) -> AiReply:
        client = _sdk_client(self._api_key).with_options(timeout=request.timeout_seconds)
        try:
            message = client.beta.messages.create(
                model=request.model,
                max_tokens=request.max_tokens,
                system=request.system,
                messages=[{"role": "user", "content": request.user}],
                output_config={
                    "effort": request.effort,
                    "format": {"type": "json_schema", "schema": request.output_schema},
                },
                betas=[_FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.APITimeoutError as error:
            raise AiUnavailableError("The AI service did not answer in time.") from error
        except anthropic.APIConnectionError as error:
            raise AiUnavailableError("The AI service could not be reached.") from error
        except anthropic.RateLimitError as error:
            raise AiUnavailableError(f"The AI service is busy ({_ids(error)}).") from error
        except anthropic.APIStatusError as error:
            detail = f"HTTP {error.status_code}, {_ids(error)}"
            if error.status_code >= _SERVER_ERROR_MIN:
                raise AiUnavailableError(f"The AI service failed ({detail}).") from error
            raise AiRequestError(f"The AI service refused the request ({detail}).") from error
        text = "".join(block.text for block in message.content if block.type == "text")
        return AiReply(
            text=text,
            model=str(message.model),
            stop_reason=message.stop_reason,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            request_id=message._request_id,  # public, despite the underscore
        )


def _ids(error: anthropic.APIStatusError) -> str:
    return f"request {error.request_id or 'unknown'}"


class OfflineAiClient:
    """Development and tests without a key: the touchpoint's sample reply, no network."""

    offline = True

    def complete(self, request: AiRequest) -> AiReply:
        return AiReply(
            text=request.offline_reply,
            model=OFFLINE_MODEL,
            stop_reason="end_turn",
            input_tokens=0,
            output_tokens=0,
            request_id=None,
        )


_override: AiClient | None = None


def override_ai_client(client: AiClient | None) -> None:
    # A module-level switch is how tests swap the client for the eager Celery tasks.
    global _override  # noqa: PLW0603
    _override = client


def get_ai_client() -> AiClient:
    if _override is not None:
        return _override
    settings = get_settings()
    if settings.is_test:
        return OfflineAiClient()  # never a live call from a test, whatever .env holds
    if settings.anthropic_api_key:
        return AnthropicAiClient(settings.anthropic_api_key)
    if settings.is_deployed:
        raise AiNotConfiguredError(
            f"ANTHROPIC_API_KEY is not set in {settings.environment}; AI features cannot run."
        )
    _warn_offline()
    return OfflineAiClient()


@cache
def _warn_offline() -> None:
    logger.warning("ANTHROPIC_API_KEY is not set: AI features answer with sample text.")


def is_offline() -> bool:
    """True while AI answers come from the offline stand-in. Never raises."""
    try:
        return get_ai_client().offline
    except AiNotConfiguredError:
        return False
