"""AI advice on a final readiness result or a confirmed IQ assessment (Phase 6; spec 8, 10).

Reading needs the permission to see the result; asking needs ``advice.request``, which a
consultant never has. Asking returns at once with the parts "pending"; poll the GET.
"""

import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Final

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permission
from app.core.permissions import OrgContext, Permission
from app.models.enums import AiTouchpoint
from app.schemas.advice import (
    AdviceOut,
    AdviceRequestIn,
    ConsultationOut,
    ConsultationReasonOut,
    DimensionActionsOut,
    DimensionMeaningOut,
    GapActionsOut,
    InterpretationOut,
    PartName,
    RecommendationOut,
    RecommendationsOut,
    UsageOut,
)
from app.scoring.question_set import QuestionSet
from app.services import advice

router = APIRouter(tags=["advice"])

_PARTS: Final[dict[PartName, AiTouchpoint]] = {
    "interpretation": AiTouchpoint.INTERPRET_RESULTS,
    "gap_actions": AiTouchpoint.BRIDGE_GAPS,
    "recommendations": AiTouchpoint.RECOMMENDATIONS,
    "consultation": AiTouchpoint.CONSULTATION_NUDGE,
}


def _dollars(micro_usd: int) -> str:
    """Millionths of a US dollar as dollars with four decimals, rounded half up."""
    return str((Decimal(micro_usd) / 1_000_000).quantize(Decimal("0.0001"), ROUND_HALF_UP))


def _meta(ctx: OrgContext, part: advice.Part) -> dict[str, Any]:
    run = part.run
    usage = None
    if run is not None and ctx.user.is_platform_admin:
        usage = UsageOut(
            model=run.response_model,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            cost_usd=_dollars(run.cost_micro_usd),
        )
    return {
        "status": part.status,
        "sample": part.sample,
        "outdated": part.outdated,
        "generated_at": run.finished_at if run is not None else None,
        "usage": usage,
    }


def _answer(part: advice.Part) -> dict[str, Any]:
    return dict(part.run.response_json or {}) if part.run is not None else {}


def _name(question_set: QuestionSet, key: Any) -> str:
    return question_set.dimension(str(key)).name


def _out(ctx: OrgContext, found: advice.Advice) -> AdviceOut:
    facts = found.subject.facts
    question_set = facts.question_set
    parts = found.parts
    interpretation = found.interpretation
    gaps = _answer(parts[AiTouchpoint.BRIDGE_GAPS])
    nudge = _answer(parts[AiTouchpoint.CONSULTATION_NUDGE])
    return AdviceOut(
        subject=facts.subject,
        assessment_id=facts.subject_id,
        question_set_version=question_set.version,
        can_request=ctx.can(Permission.REQUEST_ADVICE),
        interpretation=InterpretationOut(
            **_meta(ctx, parts[AiTouchpoint.INTERPRET_RESULTS]),
            version=interpretation.version if interpretation is not None else None,
            summary=[str(s) for s in interpretation.summary] if interpretation is not None else [],
            dimensions=[
                DimensionMeaningOut(
                    key=str(d["dimension_key"]),
                    name=_name(question_set, d["dimension_key"]),
                    meaning=str(d["meaning"]),
                    strengths=[str(s) for s in d["strengths"]],
                    gaps=[str(s) for s in d["gaps"]],
                )
                for d in (interpretation.per_dimension if interpretation is not None else [])
            ],
        ),
        gap_actions=GapActionsOut(
            **_meta(ctx, parts[AiTouchpoint.BRIDGE_GAPS]),
            dimensions=[
                DimensionActionsOut(
                    key=str(d["dimension_key"]),
                    name=_name(question_set, d["dimension_key"]),
                    actions=[str(a) for a in d["actions"]],
                )
                for d in gaps.get("dimensions", [])
            ],
        ),
        recommendations=RecommendationsOut(
            **_meta(ctx, parts[AiTouchpoint.RECOMMENDATIONS]),
            version=found.recommendations[0].version if found.recommendations else None,
            items=[
                RecommendationOut(
                    key=row.dimension_key,
                    name=_name(question_set, row.dimension_key),
                    rank=row.priority_rank,
                    fixed_text=row.fixed_text,
                    initiatives=[str(s) for s in row.ai_json["initiatives"]],
                    kpis=[str(s) for s in row.ai_json["kpis"]],
                    timeline=str(row.ai_json["timeline"]),
                    resources=[str(s) for s in row.ai_json["resources"]],
                )
                for row in found.recommendations
            ],
        ),
        consultation=ConsultationOut(
            **_meta(ctx, parts[AiTouchpoint.CONSULTATION_NUDGE]),
            suggest=bool(nudge.get("suggest", False)),
            message=[str(s) for s in nudge.get("message", [])],
            reasons=[
                ConsultationReasonOut(
                    key=str(r["dimension_key"]),
                    name=_name(question_set, r["dimension_key"]),
                    reason=str(r["reason"]),
                )
                for r in nudge.get("reasons", [])
            ],
        ),
    )


def _ask(db: Session, ctx: OrgContext, subject: advice.Subject, body: AdviceRequestIn) -> AdviceOut:
    advice.request(
        db,
        ctx,
        subject,
        parts=[_PARTS[name] for name in body.parts] if body.parts is not None else None,
        regenerate=body.regenerate,
    )
    return _out(ctx, advice.get(db, ctx, subject))


READINESS: Final = "/readiness/assessments/{assessment_id}/advice"
IQ: Final = "/ideas/{idea_id}/assessments/{assessment_id}/advice"


@router.get(READINESS, response_model=AdviceOut, status_code=status.HTTP_200_OK)
def get_readiness_advice(
    assessment_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_ASSESSMENTS)),
    db: Session = Depends(get_db),
) -> AdviceOut:
    """The AI advice on a final readiness result, part by part, as it stands."""
    return _out(ctx, advice.get(db, ctx, advice.readiness_subject(db, ctx, assessment_id)))


@router.post(READINESS, response_model=AdviceOut, status_code=status.HTTP_200_OK)
def request_readiness_advice(
    assessment_id: uuid.UUID,
    body: AdviceRequestIn,
    ctx: OrgContext = Depends(require_permission(Permission.REQUEST_ADVICE)),
    db: Session = Depends(get_db),
) -> AdviceOut:
    """Ask the AI for advice on a final readiness result, or ask again. Returns at once;
    poll the GET until no part is "pending"."""
    return _ask(db, ctx, advice.readiness_subject(db, ctx, assessment_id), body)


@router.get(IQ, response_model=AdviceOut, status_code=status.HTTP_200_OK)
def get_iq_advice(
    idea_id: uuid.UUID,
    assessment_id: uuid.UUID,
    ctx: OrgContext = Depends(require_permission(Permission.VIEW_IDEAS)),
    db: Session = Depends(get_db),
) -> AdviceOut:
    """The AI advice on an idea's confirmed scores, part by part, as it stands."""
    return _out(ctx, advice.get(db, ctx, advice.iq_subject(db, ctx, idea_id, assessment_id)))


@router.post(IQ, response_model=AdviceOut, status_code=status.HTTP_200_OK)
def request_iq_advice(
    idea_id: uuid.UUID,
    assessment_id: uuid.UUID,
    body: AdviceRequestIn,
    ctx: OrgContext = Depends(require_permission(Permission.REQUEST_ADVICE)),
    db: Session = Depends(get_db),
) -> AdviceOut:
    """Ask the AI for advice on an idea's confirmed scores, or ask again. Returns at once;
    poll the GET until no part is "pending"."""
    return _ask(db, ctx, advice.iq_subject(db, ctx, idea_id, assessment_id), body)
