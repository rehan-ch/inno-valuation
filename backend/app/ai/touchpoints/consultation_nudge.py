"""Touchpoint 8: suggest booking a consultation when the gap is significant.

Amy Q11 (spec 10): there is no fixed threshold; the AI judges the gap between where the
company is and where it wants to be. The judgement is about the same dimensions as the gap
actions (touchpoint 5): the priorities and every dimension with a target above its score.
The answer is the run itself (``app.services.advice`` reads it from the run).

PROVISIONAL: where no target is set, the AI judges from the score against its scale. Amy
has not said what "where they want to be" means without a target.

PROVISIONAL: the judgement is also made for an idea's Innovation Quotient, by the idea
targets the company set. Spec 10 speaks of the company; Amy has not said whether an idea's
result should lead to a suggestion.

The offline stand-in never suggests a consultation: a sample must not sell anything.
"""

from typing import Final

from anthropic import transform_schema

from app.ai.prompting import RenderedPrompt, render
from app.ai.runner import OutputRejectedError, Touchpoint
from app.ai.schemas.common import item_schema
from app.ai.schemas.consultation_nudge import ConsultationNudgeOutput
from app.ai.touchpoints import results
from app.ai.touchpoints.results import ResultFacts
from app.models import AiRun
from app.models.enums import AiTouchpoint

KEY: Final = AiTouchpoint.CONSULTATION_NUDGE


def asks_about(facts: ResultFacts) -> tuple[results.DimensionFact, ...]:
    return facts.focus


def render_prompt(facts: ResultFacts) -> RenderedPrompt:
    return render(KEY.value, facts=facts, focus=asks_about(facts))


def spec_for(run: AiRun) -> Touchpoint[ConsultationNudgeOutput]:
    _, keys = results.asked(run)
    schema = transform_schema(ConsultationNudgeOutput)
    item_schema(schema, "reasons")["properties"]["dimension_key"]["enum"] = keys

    def check(output: ConsultationNudgeOutput) -> None:
        results.require_one_scale(run, output)
        if any(reason.dimension_key not in keys for reason in output.reasons):
            raise OutputRejectedError(
                f"Every reason must name one of the dimensions asked about: {', '.join(keys)}."
            )

    return Touchpoint(
        output_model=ConsultationNudgeOutput,
        output_schema=schema,
        check=check,
        offline_reply=results.dumps({"suggest": False, "message": [], "reasons": []}),
    )
