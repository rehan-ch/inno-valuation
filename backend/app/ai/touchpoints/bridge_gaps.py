"""Touchpoint 5: 3 to 5 concrete actions per dimension to close its gap.

Asked about the result's priorities (the engine's five lowest, spec 7) and every other
dimension whose target is above its score (spec 6). The answer is the run itself: there is
no separate table (``app.services.advice`` reads it from the run).

Sends what touchpoint 4 sends, plus each asked dimension's target and Amy's fixed
next-step text, verbatim from the question set.
"""

from typing import Final

from anthropic import transform_schema

from app.ai.prompting import RenderedPrompt, render
from app.ai.runner import Touchpoint
from app.ai.schemas.bridge_gaps import MIN_ACTIONS, BridgeGapsOutput
from app.ai.schemas.common import constrain_dimensions
from app.ai.touchpoints import results
from app.ai.touchpoints.results import ResultFacts
from app.models import AiRun
from app.models.enums import AiTouchpoint
from app.scoring.question_set import QuestionSet

KEY: Final = AiTouchpoint.BRIDGE_GAPS


def asks_about(facts: ResultFacts) -> tuple[results.DimensionFact, ...]:
    return facts.focus


def render_prompt(facts: ResultFacts) -> RenderedPrompt:
    return render(KEY.value, facts=facts, focus=asks_about(facts))


def _sample(question_set: QuestionSet, keys: list[str]) -> str:
    return results.dumps(
        {
            "dimensions": [
                {
                    "dimension_key": key,
                    "actions": [
                        results.SAMPLE_NOTE,
                        *[
                            "Sample text: a concrete action for "
                            f"{question_set.dimension(key).name} will appear here."
                        ]
                        * (MIN_ACTIONS - 1),
                    ],
                }
                for key in keys
            ]
        }
    )


def spec_for(run: AiRun) -> Touchpoint[BridgeGapsOutput]:
    question_set, keys = results.asked(run)
    schema = transform_schema(BridgeGapsOutput)
    constrain_dimensions(schema, "dimensions", keys)

    def check(output: BridgeGapsOutput) -> None:
        results.require_one_scale(run, output)
        results.require_exactly([d.dimension_key for d in output.dimensions], keys, "The actions")

    return Touchpoint(
        output_model=BridgeGapsOutput,
        output_schema=schema,
        check=check,
        offline_reply=_sample(question_set, keys),
    )
