"""Touchpoint 6: one recommendation per priority dimension.

Amy's fixed next-step text (spec 8) is passed in and must come back unchanged: the check
compares it with the question set character for character, so the AI's words can never
slip into it. The answer is copied into ``recommendations`` once the run succeeds
(``app.services.advice``), with the fixed text taken from the question set and the rank
from the engine.

Sends what touchpoint 4 sends, plus each priority dimension's target and fixed text.
The company context answers (touchpoint 2) are not built yet; the prompt uses the company
details only.
"""

from typing import Final

from anthropic import transform_schema

from app.ai.prompting import RenderedPrompt, render
from app.ai.runner import OutputRejectedError, Touchpoint
from app.ai.schemas.common import constrain_dimensions
from app.ai.schemas.recommendations import RecommendationsOutput
from app.ai.touchpoints import results
from app.ai.touchpoints.results import ResultFacts
from app.models import AiRun
from app.models.enums import AiTouchpoint
from app.scoring.question_set import QuestionSet

KEY: Final = AiTouchpoint.RECOMMENDATIONS


def asks_about(facts: ResultFacts) -> tuple[results.DimensionFact, ...]:
    return facts.priorities


def render_prompt(facts: ResultFacts) -> RenderedPrompt:
    return render(KEY.value, facts=facts, focus=asks_about(facts))


def _sample(question_set: QuestionSet, keys: list[str]) -> str:
    def text(what: str, key: str) -> str:
        return f"Sample text: {what} for {question_set.dimension(key).name} will appear here."

    return results.dumps(
        {
            "recommendations": [
                {
                    "dimension_key": key,
                    "fixed_text": question_set.dimension(key).next_steps,
                    "initiatives": [results.SAMPLE_NOTE, text("an initiative", key)],
                    "kpis": [text("a measure", key), text("a second measure", key)],
                    "timeline": text("a timeline", key),
                    "resources": [text("the resources needed", key)],
                }
                for key in keys
            ]
        }
    )


def spec_for(run: AiRun) -> Touchpoint[RecommendationsOutput]:
    question_set, keys = results.asked(run)
    schema = transform_schema(RecommendationsOutput)
    constrain_dimensions(schema, "recommendations", keys)

    def check(output: RecommendationsOutput) -> None:
        results.require_one_scale(run, output)
        results.require_exactly(
            [r.dimension_key for r in output.recommendations], keys, "The recommendations"
        )
        for item in output.recommendations:
            if item.fixed_text != question_set.dimension(item.dimension_key).next_steps:
                # Names the dimension by key only: the message is stored with the run.
                raise OutputRejectedError(
                    f"fixed_text for {item.dimension_key} must be the method's next steps "
                    "exactly as given, character for character."
                )

    return Touchpoint(
        output_model=RecommendationsOutput,
        output_schema=schema,
        check=check,
        offline_reply=_sample(question_set, keys),
    )
