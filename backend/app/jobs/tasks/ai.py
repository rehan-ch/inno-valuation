"""Run AI touchpoints in the background (every AI call runs in a task, never in a request).

The task receives the run id only. It locks the run, re-checks that it is still to be run
and that its organisation exists and is active, and hands it to the runner. Idempotent: a
finished run is skipped, a run another worker holds is skipped, and a run left ``running``
by a lost worker is run again once its lease is over (``acks_late``).
"""

import logging
import uuid

from app.ai import runner
from app.ai.touchpoints import SPECS
from app.jobs.celery_app import celery_app
from app.jobs.db import task_session
from app.models import Organisation
from app.models.enums import OrganisationStatus

logger = logging.getLogger(__name__)

SKIPPED = "skipped"


@celery_app.task(name="ai.run")
def run_ai(run_id: str) -> str:
    with task_session() as db:
        # The row lock is held until the runner's first commit, so two deliveries of the
        # same id cannot both claim the run.
        run = runner.lock(db, uuid.UUID(run_id))
        if run is not None and runner.expired(run):
            runner.fail(db, run, "The run waited too long for a worker.")
            return run.status.value
        if run is None or not runner.claimable(run):
            db.rollback()
            logger.info("Skipped AI run %s: gone, finished or held by another worker", run_id)
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
