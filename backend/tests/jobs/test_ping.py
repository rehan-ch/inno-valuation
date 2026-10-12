from datetime import timedelta

from app.jobs.celery_app import celery_app
from app.jobs.tasks.ping import ping


def test_celery_is_eager_in_tests() -> None:
    assert celery_app.conf.task_always_eager is True
    assert celery_app.conf.task_eager_propagates is True


def test_ping_runs_eagerly() -> None:
    result = ping.delay()
    assert result.get(timeout=1) == "pong"


def test_task_results_expire_within_an_hour() -> None:
    expires = celery_app.conf.result_expires
    assert isinstance(expires, timedelta)
    assert timedelta(0) < expires <= timedelta(hours=1)
