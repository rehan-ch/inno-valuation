"""Shared pieces of the AI output models.

Every output is strict: no extra fields, so a model that adds a score or a total fails the
check instead of slipping it through. Every output item names its dimension with a
``dimension_key`` that must be a key of the question set.
"""

import re
from typing import Annotated, Any, Final

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from app.scoring.question_set import QUESTION_SET

# House style for AI text: simple English, short sentences, no em dashes.
_EM_DASH: Final = "—"


def _known_dimension(key: str) -> str:
    if key not in QUESTION_SET.dimension_keys:
        # Generic on purpose: the message lands in run.error, so it must not echo the
        # model's output.
        raise ValueError("not a dimension key")
    return key


def _plain(text: str) -> str:
    if _EM_DASH in text:
        raise ValueError("must not contain an em dash; use a comma or a full stop")
    return text


_DIGIT: Final = re.compile(r"\d")
_GUARANTEE: Final = re.compile(r"guarantee", re.IGNORECASE)


def _no_numbers(text: str) -> str:
    # The app shows every number beside the AI's words; the AI writes none of its own.
    if _DIGIT.search(text):
        raise ValueError("must not contain a number; describe it in words")
    return text


def _no_guarantee(text: str) -> str:
    # Advice is a suggestion. It never promises a return or a result.
    if _GUARANTEE.search(text):
        raise ValueError("must not promise or guarantee a result")
    return text


DimensionKey = Annotated[str, AfterValidator(_known_dimension)]

# One plain sentence, short enough to read at a glance.
Sentence = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=10, max_length=300),
    AfterValidator(_plain),
]


# One sentence of advice: plain, and never a promise.
Advice = Annotated[Sentence, AfterValidator(_no_guarantee)]

# One sentence that explains a result in words only: the numbers stay with the engine.
Words = Annotated[Advice, AfterValidator(_no_numbers)]


def item_schema(schema: dict[str, Any], prop: str) -> dict[str, Any]:
    """The object schema of the items of the list property ``prop``, following a ``$ref``."""
    items: dict[str, Any] = schema["properties"][prop]["items"]
    if "$ref" in items:  # the item model is shared through $defs
        items = schema["$defs"][items["$ref"].rsplit("/", 1)[-1]]
    return items


def constrain_dimensions(schema: dict[str, Any], prop: str, keys: list[str]) -> None:
    """Constrain generation to exactly one item per key in ``keys`` (the touchpoint's check
    still applies): the list has that many items and ``dimension_key`` is one of them."""
    schema["properties"][prop]["minItems"] = schema["properties"][prop]["maxItems"] = len(keys)
    item_schema(schema, prop)["properties"]["dimension_key"]["enum"] = list(keys)


class AiOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
