"""AI output models: every output names its dimension, and none can carry a number the
scoring engine owns."""

import importlib
import pkgutil
import uuid
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

import app.ai.schemas
from app.ai.runner import OutputRejectedError, parse_output
from app.ai.schemas.bridge_gaps import BridgeGapsOutput
from app.ai.schemas.common import AiOutput
from app.ai.schemas.consultation_nudge import ConsultationNudgeOutput
from app.ai.schemas.explain_question import ExplainQuestionOutput
from app.ai.schemas.interpret_results import InterpretResultsOutput
from app.ai.schemas.propose_iq_scores import ProposeIqScoresOutput
from app.ai.schemas.recommendations import RecommendationsOutput
from app.ai.touchpoints import (
    bridge_gaps,
    consultation_nudge,
    interpret_results,
    propose_iq_scores,
    recommendations,
    results,
)
from app.models import AiRun
from app.models.enums import AdviceSubject
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


# Touchpoints 4, 5, 6 and 8: advice


def _run(keys: list[str], subject: AdviceSubject = AdviceSubject.READINESS_RESULT) -> AiRun:
    return AiRun(
        subject_type=subject.value,
        subject_id=results.subject_id(QUESTION_SET.version, uuid.uuid4()),
        params={"keys": keys},
    )


KEYS = list(QUESTION_SET.dimension_keys)
FIVE = KEYS[:5]


def _interpretation() -> dict[str, Any]:
    return {
        "summary": ["The result shows a sound base.", "A few areas need steady work."],
        "dimensions": [
            {
                "dimension_key": key,
                "meaning": "This area is in a workable place.",
                "strengths": ["The basics are in place."],
                "gaps": [],
            }
            for key in KEYS
        ],
    }


def _actions() -> dict[str, Any]:
    return {
        "dimensions": [
            {"dimension_key": key, "actions": ["Name one owner for this area."] * 3} for key in FIVE
        ]
    }


def _recommendations() -> dict[str, Any]:
    return {
        "recommendations": [
            {
                "dimension_key": key,
                "fixed_text": QUESTION_SET.dimension(key).next_steps,
                "initiatives": ["Run a short review.", "Start one small pilot."],
                "kpis": ["Share of planned work finished.", "Feedback gathered each quarter."],
                "timeline": "Review first, then pilot, then decide.",
                "resources": ["One owner and a few hours a week."],
            }
            for key in FIVE
        ]
    }


def _nudge() -> dict[str, Any]:
    return {
        "suggest": True,
        "message": ["Several areas sit well below where you want them."],
        "reasons": [{"dimension_key": FIVE[0], "reason": "This area is well short of its target."}],
    }


def test_every_advice_schema_is_found() -> None:
    assert {
        InterpretResultsOutput,
        BridgeGapsOutput,
        RecommendationsOutput,
        ConsultationNudgeOutput,
    } <= set(_output_models())


@pytest.mark.parametrize(
    ("model", "valid"),
    [
        (InterpretResultsOutput, _interpretation),
        (BridgeGapsOutput, _actions),
        (RecommendationsOutput, _recommendations),
        (ConsultationNudgeOutput, _nudge),
    ],
    ids=lambda v: getattr(v, "__name__", ""),
)
def test_valid_advice_passes_and_a_total_is_refused(model: type[BaseModel], valid: Any) -> None:
    model.model_validate(valid())
    with pytest.raises(ValidationError, match="Extra inputs"):
        model.model_validate({**valid(), "total": 190})


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda o: o["summary"].__setitem__(0, "The total is 190 out of 300."), "number"),
        (lambda o: o["dimensions"][0].update(meaning="This scores 15 out of 25."), "number"),
        (lambda o: o["dimensions"][0].update(gaps=["Only 2 of the parts are covered."]), "number"),
        (lambda o: o["dimensions"][0].update(strengths=["Good."] * 1), "at least 10"),
        (lambda o: o["dimensions"][0].update(gaps=["A gap that is real."] * 4), "at most 3"),
        (lambda o: o["dimensions"][1].update(dimension_key=KEYS[0]), "only once"),
        (lambda o: o["dimensions"][0].update(dimension_key="made_up"), "not a dimension key"),
        (lambda o: o["dimensions"][0].update(score=15), "Extra inputs"),
        (lambda o: o["summary"].__setitem__(0, "We guarantee a strong result."), "guarantee"),
        (lambda o: o.update(summary=["Only one sentence here."]), "at least 2"),
    ],
)
def test_bad_interpretations_are_refused(change: Any, message: str) -> None:
    data = _interpretation()
    change(data)
    with pytest.raises(ValidationError, match=message):
        InterpretResultsOutput.model_validate(data)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda o: o["dimensions"][0].update(actions=["Name one owner."] * 2), "at least 3"),
        (lambda o: o["dimensions"][0].update(actions=["Name one owner."] * 6), "at most 5"),
        (lambda o: o["dimensions"][1].update(dimension_key=FIVE[0]), "only once"),
        (lambda o: o["dimensions"][0]["actions"].__setitem__(0, "Do this — at once."), "em dash"),
        (
            lambda o: o["dimensions"][0]["actions"].__setitem__(0, "This is guaranteed to work."),
            "guarantee",
        ),
        (lambda o: o["dimensions"][0].update(target=20), "Extra inputs"),
    ],
)
def test_bad_gap_actions_are_refused(change: Any, message: str) -> None:
    data = _actions()
    change(data)
    with pytest.raises(ValidationError, match=message):
        BridgeGapsOutput.model_validate(data)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda o: o["recommendations"][0].update(initiatives=["Run a review."]), "at least 2"),
        (lambda o: o["recommendations"][0].update(resources=[]), "at least 1"),
        (lambda o: o["recommendations"][0].update(fixed_text=""), "at least 1"),
        (lambda o: o["recommendations"][0].update(timeline="A guaranteed quick win."), "guarantee"),
        (lambda o: o["recommendations"][1].update(dimension_key=FIVE[0]), "only once"),
        (lambda o: o["recommendations"][0].update(priority=1), "Extra inputs"),
    ],
)
def test_bad_recommendations_are_refused(change: Any, message: str) -> None:
    data = _recommendations()
    change(data)
    with pytest.raises(ValidationError, match=message):
        RecommendationsOutput.model_validate(data)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda o: o.update(reasons=[]), "needs a message and at least one reason"),
        (lambda o: o.update(message=[]), "needs a message and at least one reason"),
        (lambda o: o.update(suggest=False), "no message and no reason"),
        (lambda o: o.update(message=["We guarantee results if you book today."]), "guarantee"),
        (lambda o: o["reasons"].append(dict(o["reasons"][0])), "only once"),
        (lambda o: o.update(threshold=5), "Extra inputs"),
    ],
)
def test_bad_consultation_suggestions_are_refused(change: Any, message: str) -> None:
    data = _nudge()
    change(data)
    with pytest.raises(ValidationError, match=message):
        ConsultationNudgeOutput.model_validate(data)


# Every place the AI writes a sentence of its own, in each of the four parts.
AI_TEXT: list[tuple[type[BaseModel], Any, Any]] = [
    (InterpretResultsOutput, _interpretation, lambda o, t: o["summary"].__setitem__(0, t)),
    (InterpretResultsOutput, _interpretation, lambda o, t: o["dimensions"][0].update(meaning=t)),
    (InterpretResultsOutput, _interpretation, lambda o, t: o["dimensions"][0].update(gaps=[t])),
    (BridgeGapsOutput, _actions, lambda o, t: o["dimensions"][0]["actions"].__setitem__(0, t)),
    (
        RecommendationsOutput,
        _recommendations,
        lambda o, t: o["recommendations"][0].update(initiatives=[t, t]),
    ),
    (
        RecommendationsOutput,
        _recommendations,
        lambda o, t: o["recommendations"][0].update(kpis=[t, t]),
    ),
    (
        RecommendationsOutput,
        _recommendations,
        lambda o, t: o["recommendations"][0].update(timeline=t),
    ),
    (
        RecommendationsOutput,
        _recommendations,
        lambda o, t: o["recommendations"][0].update(resources=[t]),
    ),
    (ConsultationNudgeOutput, _nudge, lambda o, t: o.update(message=[t])),
    (ConsultationNudgeOutput, _nudge, lambda o, t: o["reasons"][0].update(reason=t)),
]
# What an obeyed injection or a careless model would put inside a sentence.
REFUSED_TEXT = [
    ("Raise Customer Journey from 12 to 20 out of 25 by next quarter.", "number"),
    ("Your total is 300 out of 300, the best there is.", "number"),
    ("The gap of 8 points is the widest; book a consultation today.", "number"),
    ("Revenue will go up by several % in a month.", "number"),
    ("One owner and a budget of several thousand $ will do.", "number"),
    ("This reaches level \u00b2 and covers \u00bd of the parts.", "number"),
    ("This will deliver a strong return, we promise.", "promise or guarantee"),
    ("Success is assured once you book today.", "promise or guarantee"),
    ("A tenfold return is guaran\u00adteed.".replace("\u00ad", ""), "promise or guarantee"),
    ("Visit http://evil.example now to claim it.", "link"),
    ("See www.evil.example for the full plan.", "link"),
]


@pytest.mark.parametrize(("model", "valid", "put"), AI_TEXT)
@pytest.mark.parametrize(("text", "message"), REFUSED_TEXT)
def test_no_ai_sentence_may_hold_a_number_a_promise_or_a_link(
    model: type[BaseModel], valid: Any, put: Any, text: str, message: str
) -> None:
    data = valid()
    put(data, text)
    with pytest.raises(ValidationError, match=message):
        model.model_validate(data)


@pytest.mark.parametrize(("model", "valid", "put"), AI_TEXT)
def test_ordinary_advice_words_are_not_mistaken_for_a_promise(
    model: type[BaseModel], valid: Any, put: Any
) -> None:
    data = valid()
    put(data, "Start with the most promising part and add quality assurance within three months.")
    model.model_validate(data)


def test_the_fixed_text_may_hold_digits_because_it_is_not_the_ais() -> None:
    data = _recommendations()
    data["recommendations"][0]["fixed_text"] = "Review 3 journeys in 30 days."
    RecommendationsOutput.model_validate(data)


SPECS: dict[type[BaseModel], tuple[Any, list[str]]] = {
    InterpretResultsOutput: (interpret_results, KEYS),
    BridgeGapsOutput: (bridge_gaps, FIVE),
    RecommendationsOutput: (recommendations, FIVE),
    ConsultationNudgeOutput: (consultation_nudge, FIVE),
}


@pytest.mark.parametrize(("model", "valid", "put"), AI_TEXT)
@pytest.mark.parametrize(
    ("subject", "text", "allowed"),
    [
        (
            AdviceSubject.READINESS_RESULT,
            "Add this to your Innovation Quotient for the full picture.",
            False,
        ),
        (AdviceSubject.READINESS_RESULT, "Together with the IQ of the idea this is strong.", False),
        (AdviceSubject.IQ_ASSESSMENT, "Your innovation readiness makes up for this idea.", False),
        (AdviceSubject.IQ_ASSESSMENT, "Check the market readiness of this idea first.", True),
        (AdviceSubject.READINESS_RESULT, "Give one person the time to own this area.", True),
    ],
)
def test_advice_never_brings_in_the_other_score(
    model: type[BaseModel],
    valid: Any,
    put: Any,
    subject: AdviceSubject,
    text: str,
    *,
    allowed: bool,
) -> None:
    """Spec 4: readiness and the IQ are never added, blended or set against each other."""
    touchpoint, keys = SPECS[model]
    data = valid()
    put(data, text)
    output = model.model_validate(data)
    spec = touchpoint.spec_for(_run(keys, subject))
    if allowed:
        spec.check(output)
    else:
        with pytest.raises(OutputRejectedError, match="other score") as raised:
            spec.check(output)
        assert text not in str(raised.value)  # stored with the run: never the model's words


def test_no_suggestion_is_a_valid_answer() -> None:
    output = ConsultationNudgeOutput.model_validate(
        {"suggest": False, "message": [], "reasons": []}
    )
    assert output.suggest is False


def test_advice_is_checked_against_exactly_the_dimensions_asked_about() -> None:
    spec = bridge_gaps.spec_for(_run(FIVE))
    spec.check(BridgeGapsOutput.model_validate(_actions()))
    short = _actions()
    short["dimensions"].pop()
    with pytest.raises(OutputRejectedError, match="exactly the dimensions asked about"):
        spec.check(BridgeGapsOutput.model_validate(short))
    other = _actions()
    other["dimensions"][0]["dimension_key"] = KEYS[-1]
    with pytest.raises(OutputRejectedError, match="exactly the dimensions asked about"):
        spec.check(BridgeGapsOutput.model_validate(other))
    listed = spec.output_schema["properties"]["dimensions"]
    assert (listed["minItems"], listed["maxItems"]) == (5, 5)

    every = interpret_results.spec_for(_run(KEYS))
    every.check(InterpretResultsOutput.model_validate(_interpretation()))
    with pytest.raises(OutputRejectedError, match="does not say which dimensions"):
        interpret_results.spec_for(_run([]))
    with pytest.raises(OutputRejectedError, match="does not say which dimensions"):
        interpret_results.spec_for(_run(["made_up"]))


def test_the_fixed_text_must_come_back_unchanged() -> None:
    spec = recommendations.spec_for(_run(FIVE))
    spec.check(RecommendationsOutput.model_validate(_recommendations()))
    for changed in (lambda t: t + " ", lambda t: t.lower(), lambda t: t[:-1], lambda t: "Do more."):
        data = _recommendations()
        data["recommendations"][2]["fixed_text"] = changed(data["recommendations"][2]["fixed_text"])
        with pytest.raises(OutputRejectedError, match="character for character") as raised:
            spec.check(RecommendationsOutput.model_validate(data))
        # The message is stored with the run: it names the dimension, never the text.
        assert FIVE[2] in str(raised.value)
        assert "Do more." not in str(raised.value)


def test_a_consultation_reason_must_name_a_dimension_that_was_asked_about() -> None:
    spec = consultation_nudge.spec_for(_run(FIVE))
    spec.check(ConsultationNudgeOutput.model_validate(_nudge()))
    data = _nudge()
    data["reasons"][0]["dimension_key"] = KEYS[-1]
    with pytest.raises(OutputRejectedError, match="one of the dimensions asked about"):
        spec.check(ConsultationNudgeOutput.model_validate(data))


@pytest.mark.parametrize(
    "touchpoint",
    [interpret_results, bridge_gaps, recommendations, consultation_nudge],
    ids=lambda m: m.KEY.value,
)
def test_the_offline_sample_is_a_valid_answer(touchpoint: Any) -> None:
    spec = touchpoint.spec_for(_run(KEYS if touchpoint is interpret_results else FIVE))
    parse_output(spec, spec.offline_reply)
