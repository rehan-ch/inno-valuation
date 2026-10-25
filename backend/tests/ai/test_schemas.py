"""AI output models: every output names its dimension, and none can carry a number the
scoring engine owns (CLAUDE.md rules 3 and 4)."""

import importlib
import pkgutil
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

import app.ai.schemas
from app.ai.schemas.common import AiOutput
from app.ai.schemas.explain_question import ExplainQuestionOutput

# Field names that would mean the AI produced a number the engine owns.
ENGINE_OWNED = ("total", "band", "rank", "ranking", "vfm", "value_for_money", "iq", "priority")


def _output_models() -> list[type[BaseModel]]:
    for module in pkgutil.iter_modules(app.ai.schemas.__path__):
        importlib.import_module(f"app.ai.schemas.{module.name}")
    return [m for m in AiOutput.__subclasses__() if m is not AiOutput]


def _field_names(schema: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for definition in [schema, *schema.get("$defs", {}).values()]:
        names |= set(definition.get("properties", {}))
    return names


def test_every_touchpoint_schema_is_found() -> None:
    assert ExplainQuestionOutput in _output_models()


@pytest.mark.parametrize("model", _output_models(), ids=lambda m: m.__name__)
def test_dimension_key_is_required(model: type[BaseModel]) -> None:
    schema = model.model_json_schema()
    assert "dimension_key" in schema.get("required", [])


@pytest.mark.parametrize("model", _output_models(), ids=lambda m: m.__name__)
def test_no_engine_owned_number_can_appear(model: type[BaseModel]) -> None:
    names = _field_names(model.model_json_schema())
    assert not [n for n in names if any(word in n for word in ENGINE_OWNED)]
    assert model.model_config.get("extra") == "forbid"


def _valid() -> dict[str, Any]:
    return {
        "dimension_key": "customer_journey",
        "explanation": [
            "This question asks how well you know your customers.",
            "It covers every step they take with you.",
        ],
        "example": "A shop maps each step from first visit to repeat purchase.",
    }


def test_a_valid_explanation_passes() -> None:
    output = ExplainQuestionOutput.model_validate(_valid())
    assert output.dimension_key == "customer_journey"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"dimension_key": None}, "dimension_key"),
        ({"dimension_key": "made_up"}, "not a dimension key"),
        ({"explanation": ["Only one sentence here."]}, "at least 2"),
        ({"explanation": ["A sentence that is long enough."] * 5}, "at most 4"),
        ({"example": "Short"}, "at least 10"),
        ({"example": "A team acts — at once."}, "em dash"),
        ({"total": 240}, "Extra inputs"),
        ({"band": "Building Blocks"}, "Extra inputs"),
    ],
)
def test_bad_explanations_are_refused(change: dict[str, Any], message: str) -> None:
    data = {**_valid(), **change}
    data = {k: v for k, v in data.items() if v is not None}
    with pytest.raises(ValidationError, match=message):
        ExplainQuestionOutput.model_validate(data)
