"""AI output models: every output names its dimension, and none can carry a number the
scoring engine owns."""

import importlib
import pkgutil
import uuid
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

import app.ai.schemas
from app.ai.runner import OutputRejectedError
from app.ai.schemas.common import AiOutput
from app.ai.schemas.explain_question import ExplainQuestionOutput
from app.ai.schemas.propose_iq_scores import ProposeIqScoresOutput
from app.ai.touchpoints import propose_iq_scores
from app.models import AiRun
from app.scoring.question_set import QUESTION_SET

# Field names that would mean the AI produced a number the engine owns.
ENGINE_OWNED = (
    "total",
    "band",
    "level",
    "rank",
    "ranking",
    "vfm",
    "value_for_money",
    "iq",
    "priority",
)


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
    assert {ExplainQuestionOutput, ProposeIqScoresOutput} <= set(_output_models())


def _item_definitions(schema: dict[str, Any]) -> list[dict[str, Any]]:
    """The object schemas of every array-of-objects property at the top level."""
    found = []
    for prop in schema.get("properties", {}).values():
        items = prop.get("items")
        if not isinstance(items, dict):
            continue
        if "$ref" in items:
            items = schema["$defs"][items["$ref"].rsplit("/", 1)[-1]]
        if items.get("type") == "object":
            found.append(items)
    return found


@pytest.mark.parametrize("model", _output_models(), ids=lambda m: m.__name__)
def test_dimension_key_is_required(model: type[BaseModel]) -> None:
    """Every output item names its dimension: either the output is the item, or every
    object it lists is one."""
    schema = model.model_json_schema()
    if "dimension_key" in schema.get("required", []):
        return
    items = _item_definitions(schema)
    assert items, f"{model.__name__} has no dimension_key and lists no items that do"
    for item in items:
        assert "dimension_key" in item.get("required", [])


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
    with pytest.raises(ValidationError, match=message) as raised:
        ExplainQuestionOutput.model_validate(data)
    # The messages land in run.error (see runner.parse_output), so they never echo what
    # the model wrote.
    assert not [e for e in raised.value.errors() if "made_up" in e["msg"]]


def _proposal(**changes: Any) -> dict[str, Any]:
    scores = [
        {
            "dimension_key": key,
            "score": 5,
            "rationale": ["The idea says little about this.", "So the score stays in the middle."],
            "confidence": 0.4,
        }
        for key in QUESTION_SET.dimension_keys
    ]
    return {"scores": scores, "missing_information": [], **changes}


def test_a_valid_proposal_passes() -> None:
    output = ProposeIqScoresOutput.model_validate(_proposal())
    assert [s.dimension_key for s in output.scores] == list(QUESTION_SET.dimension_keys)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda p: p["scores"].clear(), "at least 1"),
        (lambda p: p["scores"][1].update(dimension_key="customer_journey"), "only once"),
        (lambda p: p["scores"][0].update(score=11), "less than or equal to 10"),
        (lambda p: p["scores"][0].update(score=0), "greater than or equal to 1"),
        (lambda p: p["scores"][0].update(score=7.5), "integer"),
        (lambda p: p["scores"][0].update(confidence=1.5), "less than or equal to 1"),
        (lambda p: p["scores"][0].update(rationale=["Only one sentence is here."]), "at least 2"),
        (lambda p: p["scores"][0].update(iq=70), "Extra inputs"),
        (lambda p: p.update(iq=70), "Extra inputs"),
        (lambda p: p.update(total=84), "Extra inputs"),
    ],
)
def test_bad_proposals_are_refused(change: Any, message: str) -> None:
    data = _proposal()
    change(data)
    with pytest.raises(ValidationError, match=message):
        ProposeIqScoresOutput.model_validate(data)


def test_the_touchpoint_wants_every_dimension_of_its_question_set() -> None:
    """The set and count of dimensions belong to the assessment's question set version, so
    the touchpoint checks them (and writes them into the schema), not the output model."""
    data = _proposal()
    data["scores"].pop()
    run = AiRun(subject_id=propose_iq_scores.subject_id(QUESTION_SET.version, uuid.uuid4()))
    spec = propose_iq_scores.spec_for(run)
    with pytest.raises(OutputRejectedError, match="exactly once"):
        spec.check(ProposeIqScoresOutput.model_validate(data))
    scores = spec.output_schema["properties"]["scores"]
    assert (scores["minItems"], scores["maxItems"]) == (12, 12)
