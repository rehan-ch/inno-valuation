"""Shared pieces of the AI output models.

Every output is strict: no extra fields, so a model that adds a score or a total fails the
check instead of slipping it through. Every output item names its dimension with a
``dimension_key`` that must be a key of the question set.
"""

from typing import Annotated, Final

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from app.scoring.question_set import QUESTION_SET

# House style for AI text: simple English, short sentences, no em dashes.
_EM_DASH: Final = "—"


def _known_dimension(key: str) -> str:
    if key not in QUESTION_SET.dimension_keys:
        raise ValueError(f"{key!r} is not a dimension key")
    return key


def _plain(text: str) -> str:
    if _EM_DASH in text:
        raise ValueError("must not contain an em dash; use a comma or a full stop")
    return text


DimensionKey = Annotated[str, AfterValidator(_known_dimension)]

# One plain sentence, short enough to read at a glance.
Sentence = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=10, max_length=300),
    AfterValidator(_plain),
]


class AiOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
