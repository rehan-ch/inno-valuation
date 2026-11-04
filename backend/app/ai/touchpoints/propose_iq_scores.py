"""Touchpoint 3: propose a 1 to 10 score per dimension for one idea (Amy Q1).

The subject is one IQ assessment of one idea. The proposal is stored as the run's answer
and copied into the assessment's dimension rows once it succeeds
(``app.services.ideas.load_scores``), where the owner confirms or changes each score.

Sends the 12 dimensions and the IQ levels verbatim from the question set, the idea's own
text, and only the company details in ``explain_question.COMPANY_FIELDS``. Never sends the
investment or expected value: money is for the engine's Value for Money only (spec 5), and
a model that saw it might let it colour the scores.
"""

import json
import uuid
from typing import Final

from anthropic import transform_schema

from app.ai.prompting import RenderedPrompt, render
from app.ai.runner import OutputRejectedError, Touchpoint
from app.ai.schemas.propose_iq_scores import ProposeIqScoresOutput
from app.ai.touchpoints.explain_question import company_details
from app.models import AiRun, Idea, Organisation
from app.models.enums import AiTouchpoint, IdeaStage
from app.scoring.question_set import QuestionSet, question_set_for

KEY: Final = AiTouchpoint.PROPOSE_IQ_SCORES
SUBJECT_TYPE: Final = "iq_assessment"

# PROVISIONAL: see open-questions Q10. An idea can only be scored from its own words, so
# these fields go to the AI provider; the money fields never do. Amy's answer to IN.02
# decides whether this stays.
IDEA_FIELDS: Final = (
    ("title", "Title"),
    ("summary", "Summary"),
    ("problem", "Problem or opportunity"),
    ("target_market", "Target market"),
    ("uniqueness", "What makes it different"),
    ("team", "Team"),
    ("risks", "Risks"),
)

STAGE_LABELS: Final = {
    IdeaStage.IDEA: "an idea, not yet worked up",
    IdeaStage.CONCEPT: "a worked-up concept, not built",
    IdeaStage.PROTOTYPE: "a prototype, being built or tested",
    IdeaStage.PILOT: "a pilot, in use with some customers",
    IdeaStage.LAUNCHED: "launched, in the market",
}


def subject_id(version: int, assessment_id: uuid.UUID) -> str:
    return f"{version}:{assessment_id}"


def parse_subject(value: str) -> tuple[int, uuid.UUID]:
    version, _, assessment_id = value.partition(":")
    return int(version), uuid.UUID(assessment_id)


def idea_details(idea: Idea) -> str:
    """The idea's filled-in fields in ``IDEA_FIELDS``, one labelled block each, plus its stage."""
    lines = []
    for field, label in IDEA_FIELDS:
        value = getattr(idea, field)
        if value and str(value).strip():
            lines.append(f"{label}: {str(value).strip()}")
    lines.append(f"Stage: {STAGE_LABELS[idea.stage]}")
    return "\n\n".join(lines)


def render_prompt(question_set: QuestionSet, idea: Idea, org: Organisation) -> RenderedPrompt:
    scale = question_set.iq_scale
    return render(
        KEY.value,
        dimensions=question_set.dimensions,
        levels=question_set.iq_levels,
        scale={"min": scale.min, "max": scale.max},
        idea=idea_details(idea),
        company=company_details(org),
    )


def _sample(question_set: QuestionSet) -> str:
    """The offline stand-in's answer: valid, and plainly a sample, never mistaken for a
    real proposal. Every dimension gets the middle of the scale."""
    middle = (question_set.iq_scale.min + question_set.iq_scale.max) // 2
    return json.dumps(
        {
            "scores": [
                {
                    "dimension_key": d.key,
                    "score": middle,
                    "rationale": [
                        "This is sample text, because the AI service is not connected yet.",
                        f"Once it is, this space explains the proposed score for {d.name} "
                        "from the idea's own words.",
                    ],
                    "confidence": 0,
                }
                for d in question_set.dimensions
            ],
            "missing_information": [],
        }
    )


def spec_for(run: AiRun) -> Touchpoint[ProposeIqScoresOutput]:
    version, _ = parse_subject(run.subject_id)
    question_set = question_set_for(version)
    keys = list(question_set.dimension_keys)
    schema = transform_schema(ProposeIqScoresOutput)
    # Constrain generation to the known dimension keys; the check below still applies.
    scores = schema["properties"]["scores"]
    scores["minItems"] = scores["maxItems"] = len(keys)
    items = scores["items"]
    if "$ref" in items:  # the item model is shared through $defs
        items = schema["$defs"][items["$ref"].rsplit("/", 1)[-1]]
    items["properties"]["dimension_key"]["enum"] = keys

    def check(output: ProposeIqScoresOutput) -> None:
        if sorted(s.dimension_key for s in output.scores) != sorted(keys):
            raise OutputRejectedError("Every one of the 12 dimensions must be scored exactly once.")

    return Touchpoint(
        output_model=ProposeIqScoresOutput,
        output_schema=schema,
        check=check,
        offline_reply=_sample(question_set),
    )
