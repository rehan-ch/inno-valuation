"""Touchpoint 1: "What does this mean?" on a readiness question.

The subject is one question of one question set version, for one organisation: the
explanation may use the company's details, so it is saved per organisation and reused by
everyone there until the prompt or those details change (``app.services.explanations``).

Sends the question and its dimension, verbatim from the question set, plus only the
company details in ``COMPANY_FIELDS``. Never sends names, people or answers.
"""

import json
from typing import Final

from anthropic import transform_schema

from app.ai.prompting import RenderedPrompt, render
from app.ai.runner import OutputRejectedError, Touchpoint
from app.ai.schemas.explain_question import ExplainQuestionOutput
from app.models import AiRun, Organisation
from app.models.enums import AiTouchpoint
from app.scoring.question_set import Dimension, QuestionSet, question_set_for

KEY: Final = AiTouchpoint.EXPLAIN_QUESTION
SUBJECT_TYPE: Final = "readiness_question"

# PROVISIONAL: see open-questions Q10. Until Amy decides what client data may go to the AI
# provider, an explanation is fitted to the company with these general details only. The
# name, description, founders, contacts and website are never sent.
COMPANY_FIELDS: Final = (
    ("industry", "Industry"),
    ("size_band", "Size"),
    ("country", "Country"),
)


def subject_id(version: int, question_id: str) -> str:
    return f"{version}:{question_id}"


def parse_subject(value: str) -> tuple[int, str]:
    version, _, question_id = value.partition(":")
    return int(version), question_id


def company_details(org: Organisation) -> str:
    """The details in ``COMPANY_FIELDS`` that are filled in, one "Label: value" per line."""
    lines = []
    for field, label in COMPANY_FIELDS:
        value = getattr(org, field)
        if value and str(value).strip():
            lines.append(f"{label}: {str(value).strip()}")
    return "\n".join(lines)


def render_prompt(question_set: QuestionSet, question_id: str, org: Organisation) -> RenderedPrompt:
    """The prompt for one question. ScoringError if the question id is unknown."""
    dimension = question_set.dimension_of_question(question_id)
    question = next(q for q in dimension.questions if q.id == question_id)
    scale = question_set.readiness_scale
    labels = dict(scale.labels)
    return render(
        KEY.value,
        dimension=dimension,
        question=question,
        scale={
            "min": scale.min,
            "max": scale.max,
            "min_label": labels.get(scale.min, ""),
            "max_label": labels.get(scale.max, ""),
        },
        company=company_details(org),
    )


def _sample(dimension: Dimension) -> str:
    """The offline stand-in's answer: valid, and plainly a sample, never mistaken for advice."""
    return json.dumps(
        {
            "dimension_key": dimension.key,
            "explanation": [
                "This is sample text, because the AI service is not connected yet.",
                f"Once it is, this space explains the question in plain words, "
                f"within {dimension.name}.",
            ],
            "example": "A real example from a company like yours will appear here.",
        }
    )


def spec_for(run: AiRun) -> Touchpoint[ExplainQuestionOutput]:
    version, question_id = parse_subject(run.subject_id)
    dimension = question_set_for(version).dimension_of_question(question_id)
    schema = transform_schema(ExplainQuestionOutput)
    # Constrain generation to the question's own dimension; the check below still applies.
    schema["properties"]["dimension_key"]["enum"] = [dimension.key]

    def check(output: ExplainQuestionOutput) -> None:
        if output.dimension_key != dimension.key:
            raise OutputRejectedError(
                f"dimension_key must be {dimension.key!r}, the question's own dimension."
            )

    return Touchpoint(
        output_model=ExplainQuestionOutput,
        output_schema=schema,
        check=check,
        offline_reply=_sample(dimension),
    )
