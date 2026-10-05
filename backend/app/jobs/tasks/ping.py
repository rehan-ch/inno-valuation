from app.jobs.celery_app import celery_app


@celery_app.task(name="jobs.ping")
def ping() -> str:
    """Liveness check for the worker. Idempotent, takes no input."""
    return "pong"
