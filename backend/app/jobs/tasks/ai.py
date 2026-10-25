"""Run AI touchpoints in the background (every AI call runs in a task, never in a request).

The task receives the run id only. It re-loads the run, re-checks that its organisation
still exists and is active, and hands it to the runner. Idempotent: a finished run is
skipped, and a run left ``running`` by a lost worker is run again (``acks_late``).
"""

import logging
import uuid

from app.ai import runner
from app.ai.touchpoints import SPECS
from app.jobs.celery_app import celery_app
from app.jobs.db import task_session
from app.models import AiRun, Organisation
from app.models.enums import AiRunStatus, OrganisationStatus

logger = logging.getLogger(__name__)

SKIPPED = "skipped"

_FINISHED = frozenset({AiRunStatus.SUCCEEDED, AiRunStatus.FAILED})


@celery_app.task(name="ai.run")
def run_ai(run_id: str) -> str:
    with task_session() as db:
        run = db.get(AiRun, uuid.UUID(run_id))
        if run is None or run.status in _FINISHED:
            logger.info("Skipped AI run %s: gone or already finished", run_id)
            return SKIPPED
        org = db.get(Organisation, run.organisation_id)
        if org is None or org.status is not OrganisationStatus.ACTIVE:
            runner.fail(db, run, "The organisation is no longer active.")
            return run.status.value
        spec = SPECS.get(run.touchpoint)
        if spec is None:
            runner.fail(db, run, f"Touchpoint {run.touchpoint} is not built yet.")
            return run.status.value
        runner.execute(db, run, spec(run))
        return run.status.value
