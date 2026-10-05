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
    task_acks_late=True,
    task_always_eager=settings.is_test,
    task_eager_propagates=settings.is_test,
)
