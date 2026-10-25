"""Database constraints and foreign key behaviour of the AI run log."""

from typing import Any

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import AiRun, Organisation, User
from app.models.enums import AiRunStatus
from tests.factories import AiRunFactory, OrganisationFactory, UserFactory
from tests.models.test_accounts import _insert, expect_violation


def _row(org: Organisation, **values: Any) -> dict[str, Any]:
    return {
        "organisation_id": org.id,
        "touchpoint": "explain_question",
        "subject_type": "readiness_question",
        "subject_id": "1:customer_journey_1",
        "status": "queued",
        "model": "claude-sonnet-5-5",
        "effort": "low",
        "prompt_version": "1",
        "system_prompt": "s",
        "user_prompt": "u",
        **values,
    }


def test_defaults(db: Session) -> None:
    run = AiRunFactory.create()
    db.refresh(run)
    assert run.status is AiRunStatus.QUEUED
    assert (run.attempts, run.input_tokens, run.output_tokens, run.cost_micro_usd) == (0, 0, 0, 0)
    assert run.provider_request_ids == []
    assert run.response_json is None


@pytest.mark.parametrize(
    ("values", "constraint"),
    [
        ({"status": "done"}, "ck_ai_runs_status"),
        ({"touchpoint": "write_a_poem"}, "ck_ai_runs_touchpoint"),
        ({"input_tokens": -1}, "ck_ai_runs_counts_positive"),
        ({"attempts": -1}, "ck_ai_runs_counts_positive"),
        ({"cost_micro_usd": -5}, "ck_ai_runs_cost_positive"),
    ],
)
def test_the_database_refuses_bad_values(
    db: Session, values: dict[str, Any], constraint: str
) -> None:
    org = OrganisationFactory.create()
    with expect_violation(db, constraint):
        _insert(db, "ai_runs", **_row(org, **values))


def test_runs_die_with_their_organisation(db: Session) -> None:
    run = AiRunFactory.create()
    run_id = run.id
    db.execute(delete(Organisation).where(Organisation.id == run.organisation_id))
    db.expire_all()
    assert db.scalar(select(AiRun).where(AiRun.id == run_id)) is None


def test_a_run_outlives_the_person_who_asked(db: Session) -> None:
    person = UserFactory.create()
    run = AiRunFactory.create(requested_by_user_id=person.id)
    db.execute(delete(User).where(User.id == person.id))
    db.expire_all()
    kept = db.get(AiRun, run.id)
    assert kept is not None
    assert kept.requested_by_user_id is None
