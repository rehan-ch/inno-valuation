"""The AI task, run eagerly: ids only, re-checks the organisation, idempotent."""

import uuid

import pytest
from sqlalchemy.orm import Session

from app.jobs.tasks.ai import SKIPPED, run_ai
from app.models.enums import AiRunStatus, AiTouchpoint, OrganisationStatus
from tests.factories import AiRunFactory, OrganisationFactory


def test_runs_a_queued_run(db: Session) -> None:
    run = AiRunFactory.create()
    assert run_ai.delay(str(run.id)).get() == "succeeded"
    assert run.status is AiRunStatus.SUCCEEDED


@pytest.mark.parametrize("status", [AiRunStatus.SUCCEEDED, AiRunStatus.FAILED])
def test_a_finished_run_is_never_run_again(db: Session, status: AiRunStatus) -> None:
    run = AiRunFactory.create(status=status)
    assert run_ai.delay(str(run.id)).get() == SKIPPED
    assert run.status is status
    assert run.attempts == 0


def test_a_run_left_running_by_a_lost_worker_runs_again(db: Session) -> None:
    run = AiRunFactory.create(status=AiRunStatus.RUNNING)
    assert run_ai.delay(str(run.id)).get() == "succeeded"


def test_an_unknown_run_is_skipped(db: Session) -> None:
    assert run_ai.delay(str(uuid.uuid4())).get() == SKIPPED


def test_an_archived_organisation_fails_the_run_without_calling_the_ai(db: Session) -> None:
    org = OrganisationFactory.create(status=OrganisationStatus.ARCHIVED)
    run = AiRunFactory.create(organisation=org)
    assert run_ai.delay(str(run.id)).get() == "failed"
    assert run.error == "The organisation is no longer active."
    assert run.attempts == 0


def test_a_touchpoint_not_built_yet_fails_the_run(db: Session) -> None:
    run = AiRunFactory.create(touchpoint=AiTouchpoint.BRIDGE_GAPS)
    assert run_ai.delay(str(run.id)).get() == "failed"
    assert run.error == "Touchpoint bridge_gaps is not built yet."
