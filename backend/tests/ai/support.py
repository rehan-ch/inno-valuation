"""A recorded AI client and fixture loading for AI tests. No test ever calls the live API.

Fixtures live in ``tests/ai/fixtures/<touchpoint>/<case>.json``: the inputs of one case
and the replies the model gave, in order (a retry case has two). A reply holds either an
``output`` object (sent as its JSON text) or a raw ``text``.
"""

import json
from pathlib import Path
from typing import Any

from app.ai.client import AiError, AiReply, AiRequest

FIXTURES = Path(__file__).parent / "fixtures"


class RecordedAiClient:
    """Answers each call with the next recorded reply (or raises it, for an error)."""

    offline = False

    def __init__(self, *replies: AiReply | AiError) -> None:
        self._replies = list(replies)
        self.requests: list[AiRequest] = []

    def complete(self, request: AiRequest) -> AiReply:
        self.requests.append(request)
        if not self._replies:
            raise AssertionError("The AI was called more often than the test recorded.")
        reply = self._replies.pop(0)
        if isinstance(reply, AiError):
            raise reply
        return reply


def reply(
    output: dict[str, Any] | None = None,
    *,
    text: str | None = None,
    model: str = "claude-sonnet-5-5",
    stop_reason: str | None = "end_turn",
    input_tokens: int = 600,
    output_tokens: int = 150,
    request_id: str | None = "req_test",
) -> AiReply:
    return AiReply(
        text=text if text is not None else json.dumps(output),
        model=model,
        stop_reason=stop_reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        request_id=request_id,
    )


def fixture(touchpoint: str, case: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / touchpoint / f"{case}.json").read_text())
    return data


def fixture_cases(touchpoint: str) -> list[str]:
    return sorted(p.stem for p in (FIXTURES / touchpoint).glob("*.json"))


def recorded_replies(data: dict[str, Any]) -> list[AiReply | AiError]:
    return [
        reply(
            r.get("output"),
            text=r.get("text"),
            model=r.get("model", "claude-sonnet-5-5"),
            stop_reason=r.get("stop_reason", "end_turn"),
            input_tokens=r.get("input_tokens", 600),
            output_tokens=r.get("output_tokens", 150),
            request_id=r.get("request_id"),
        )
        for r in data["replies"]
    ]
