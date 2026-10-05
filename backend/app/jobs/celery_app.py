"""Celery application. Every AI call, PDF render and email send runs as a task here."""

from celery import Celery

from app.core.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "innovaluation",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.jobs.tasks.ping"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # acks_late (plus reject_on_worker_lost) means a task can be delivered more than once,
    # for example after a worker crash. Every task must therefore be idempotent.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_always_eager=settings.is_test,
    task_eager_propagates=settings.is_test,
)
