"""Touchpoint 4: what one final result means, overall and for each dimension.

The subject is one final readiness result or one confirmed IQ assessment. The answer is
copied into ``interpretations`` once the run succeeds (``app.services.advice``).

Sends the result as stored (the engine's numbers), the dimensions verbatim from the
question set, the company details in ``explain_question.COMPANY_FIELDS`` and, for an idea,
its own words (``propose_iq_scores.IDEA_FIELDS``). Never the money, names or answers.
"""

from typing import Final

from anthropic import transform_schema

from app.ai.prompting import RenderedPrompt, render
from app.ai.runner import Touchpoint
from app.ai.schemas.common import constrain_dimensions
from app.ai.schemas.interpret_results import InterpretResultsOutput
from app.ai.touchpoints import results
from app.ai.touchpoints.results import ResultFacts
from app.models import AiRun
from app.models.enums import AiTouchpoint
from app.scoring.question_set import QuestionSet

KEY: Final = AiTouchpoint.INTERPRET_RESULTS


def asks_about(facts: ResultFacts) -> tuple[results.DimensionFact, ...]:
    return facts.dimensions


def render_prompt(facts: ResultFacts) -> RenderedPrompt:
    return render(KEY.value, facts=facts)


def _sample(question_set: QuestionSet, keys: list[str]) -> str:
    return results.dumps(
        {
            "summary": [
                results.SAMPLE_NOTE,
                "Once it is, this space says in plain words what the result as a whole means.",
            ],
            "dimensions": [
                {
                    "dimension_key": key,
                    "meaning": "Sample text: what the score for "
                    f"{question_set.dimension(key).name} says will appear here.",
                    "strengths": [],
                    "gaps": [],
                }
                for key in keys
            ],
        }
    )


def spec_for(run: AiRun) -> Touchpoint[InterpretResultsOutput]:
    question_set, keys = results.asked(run)
    schema = transform_schema(InterpretResultsOutput)
    constrain_dimensions(schema, "dimensions", keys)

    def check(output: InterpretResultsOutput) -> None:
        results.require_one_scale(run, output)
        results.require_exactly(
            [d.dimension_key for d in output.dimensions], keys, "The explanation"
        )

    return Touchpoint(
        output_model=InterpretResultsOutput,
        output_schema=schema,
        check=check,
        offline_reply=_sample(question_set, keys),
    )
