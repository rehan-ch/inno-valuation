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


# Any numeral: digits of every script, and signs such as a superscript two or a half.
_DIGIT: Final = re.compile(
    r"[\d\u00b2\u00b3\u00b9\u00bc-\u00be\u2070-\u2079\u2080-\u2089\u2150-\u218b]"
)
# Words that promise an outcome ("guaranteed", "promises", "assured"). Not "promising" or
# "assurance", which advice may fairly use.
_PROMISE: Final = re.compile(r"guarantee|\bpromise[sd]?\b|\bassured?\b", re.IGNORECASE)
# Signs that only come with a figure or a price, and links: advice sends nobody anywhere.
_FIGURE_SIGN: Final = re.compile(r"[%$\u20ac\u00a3\u00a5]")
_LINK: Final = re.compile(r"https?://|www\.", re.IGNORECASE)


def _no_numbers(text: str) -> str:
    # The app shows every number beside the AI's words; the AI writes none of its own.
    if _DIGIT.search(text) or _FIGURE_SIGN.search(text):
        raise ValueError("must not contain a number; describe it in words")
    return text


def _no_guarantee(text: str) -> str:
    # Advice is a suggestion. It never promises a return or a result.
    if _PROMISE.search(text):
        raise ValueError("must not promise or guarantee a result")
    if _LINK.search(text):
        raise ValueError("must not contain a link")
    return text


DimensionKey = Annotated[str, AfterValidator(_known_dimension)]

# One plain sentence, short enough to read at a glance.
Sentence = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=10, max_length=300),
    AfterValidator(_plain),
]


# One sentence of AI advice, in words only. It is never a promise and never a link, and it
# holds no numeral: the app shows every number beside the text, so a score the AI restated
# could contradict the engine's, at once or after a target changes. Every advice text of
# touchpoints 4, 5, 6 and 8 has this type. Not caught here, left to the prompt: numbers
# spelled out in words, and a band or level name (the level "Innovation" is also an
# ordinary word in this method).
Words = Annotated[Sentence, AfterValidator(_no_guarantee), AfterValidator(_no_numbers)]


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
