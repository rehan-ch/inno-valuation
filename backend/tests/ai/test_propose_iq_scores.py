"""Touchpoint 3 against its recorded cases: typical, sparse, adversarial, and the retry.

Each case sends an idea for scoring through the service as its creator, so the prompt is
built from the case's idea and organisation, the run goes through the (eager) task, the
recorded replies answer, and the proposal lands in the assessment's dimension rows.
"""

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.core.permissions import OrgContext, OrgRole
from app.models import Idea, Organisation
from app.models.enums import AiRunStatus, IdeaStage, MembershipRole
from app.scoring.question_set import QUESTION_SET
from app.services import ideas
from tests.ai.support import RecordedAiClient, fixture, fixture_cases, recorded_replies
from tests.factories import IdeaFactory, MembershipFactory, OrganisationFactory, verified_user

UseAi = Callable[..., RecordedAiClient]

CASES = fixture_cases("propose_iq_scores")


def test_the_required_cases_are_recorded() -> None:
    assert {"typical", "sparse", "adversarial", "retry"} <= set(CASES)


def _case(db: Session, data: dict[str, Any]) -> tuple[OrgContext, Idea]:
    org = OrganisationFactory.create(**data["organisation"])
    user = verified_user()
    MembershipFactory.create(organisation=org, user=user, role=MembershipRole.MEMBER)
    fields = dict(data["idea"])
    fields["stage"] = IdeaStage(fields.get("stage", "idea"))
    idea = IdeaFactory.create(organisation=org, created_by_user_id=user.id, **fields)
    return OrgContext(organisation=org, user=user, role=OrgRole.MEMBER), idea


@pytest.mark.parametrize("case", CASES)
def test_recorded_case(db: Session, use_ai: UseAi, case: str) -> None:
    data = fixture("propose_iq_scores", case)
    ai = use_ai(*recorded_replies(data))
    ctx, idea = _case(db, data)

    assessment = ideas.request_assessment(db, ctx, idea.id)
    run = ideas.run_of(db, assessment)
    assert run is not None

    expect = data["expect"]
    assert run.status.value == expect["status"]
    assert run.attempts == expect["attempts"]
    assert len(ai.requests) == expect["attempts"]
    assert run.provider_request_ids == [r["request_id"] for r in data["replies"]]
    rows = ideas.load_scores(db, assessment)
    if run.status is AiRunStatus.SUCCEEDED:
        assert ideas.proposal_status(db, assessment, run) == "ready"
        assert [r.dimension_key for r in rows] == list(QUESTION_SET.dimension_keys)
        assert all(r.proposed_score is not None and r.final_score is None for r in rows)
        if "scores" in expect:
            assert {r.dimension_key: r.proposed_score for r in rows} == expect["scores"]
    else:
        assert ideas.proposal_status(db, assessment, run) == "failed"
        assert rows == []
        assert run.response_json is None
        assert run.error is not None
        assert expect["error_contains"] in run.error
    # Whatever the idea and company say, they reach the model as escaped data only, and
    # the money never does.
    user_prompt = ai.requests[0].user
    assert user_prompt.count("<data") == user_prompt.count("</data>") <= 2
    assert "Ignore all previous instructions" not in ai.requests[0].system
    assert "50000" not in user_prompt


def test_an_injected_iq_never_reaches_the_stored_proposal(db: Session, use_ai: UseAi) -> None:
    data = fixture("propose_iq_scores", "adversarial_obeyed")
    use_ai(*recorded_replies(data))
    ctx, idea = _case(db, data)
    assessment = ideas.request_assessment(db, ctx, idea.id)
    run = ideas.run_of(db, assessment)
    assert run is not None
    assert run.status is AiRunStatus.FAILED
    assert run.response_json is None
    assert ideas.load_scores(db, assessment) == []
    assert assessment.iq is None


def test_without_a_key_the_stand_in_proposes_a_marked_sample(db: Session) -> None:
    org: Organisation = OrganisationFactory.create()
    user = verified_user()
    MembershipFactory.create(organisation=org, user=user, role=MembershipRole.OWNER)
    idea = IdeaFactory.create(organisation=org, created_by_user_id=user.id)
    ctx = OrgContext(organisation=org, user=user, role=OrgRole.OWNER)
    assessment = ideas.request_assessment(db, ctx, idea.id)
    run = ideas.run_of(db, assessment)
    assert ideas.is_sample(run)
    rows = ideas.load_scores(db, assessment)
    assert len(rows) == 12
    assert {r.proposed_score for r in rows} == {5}
    assert all("sample text" in str(r.proposed_rationale) for r in rows)
