"""Email delivery backends.

- ``ResendEmailBackend`` when ``RESEND_API_KEY`` is set.
- ``LogEmailBackend`` otherwise, only in development and test: it writes the recipient,
  subject and link to the application log at INFO. The link holds a live token, which is
  acceptable only on a developer's machine.
- In staging or production without a key, ``get_email_backend`` raises
  ``EmailNotConfiguredError``, so the send task fails loudly instead of dropping the email.

Tests swap in ``MemoryEmailBackend`` with ``override_email_backend``.
"""

import logging
from typing import Protocol

import resend

from app.core.settings import get_settings
from app.emails.messages import EmailMessage

logger = logging.getLogger(__name__)


class EmailNotConfiguredError(RuntimeError):
    pass


class EmailBackend(Protocol):
    def send(self, message: EmailMessage, *, idempotency_key: str) -> None: ...


class LogEmailBackend:
    def send(self, message: EmailMessage, *, idempotency_key: str) -> None:
        if get_settings().is_deployed:  # never print live links on a deployed server
            raise EmailNotConfiguredError("The log email backend is for development only.")
        logger.info(
            "Email (log backend) to %s, subject %r, link %s",
            message.to,
            message.subject,
            message.link,
        )


class ResendEmailBackend:
    def __init__(self, api_key: str, sender: str) -> None:
        self._api_key = api_key
        self._sender = sender

    def send(self, message: EmailMessage, *, idempotency_key: str) -> None:
        resend.api_key = self._api_key
        params: resend.Emails.SendParams = {
            "from": self._sender,
            "to": [message.to],
            "subject": message.subject,
            "html": message.html,
            "text": message.text,
        }
        # Resend drops a repeat with the same key, so a re-delivered task sends once.
        resend.Emails.send(params, {"idempotency_key": idempotency_key})


class MemoryEmailBackend:
    """Collects messages in ``outbox``. For tests."""

    def __init__(self) -> None:
        self.outbox: list[EmailMessage] = []

    def send(self, message: EmailMessage, *, idempotency_key: str) -> None:
        self.outbox.append(message)


_override: EmailBackend | None = None


def override_email_backend(backend: EmailBackend | None) -> None:
    # A module-level switch is how tests swap the backend for the eager Celery tasks.
    global _override  # noqa: PLW0603
    _override = backend


def get_email_backend() -> EmailBackend:
    if _override is not None:
        return _override
    settings = get_settings()
    if settings.resend_api_key:
        return ResendEmailBackend(settings.resend_api_key, settings.email_from)
    if settings.is_deployed:
        raise EmailNotConfiguredError(
            f"RESEND_API_KEY is not set in {settings.environment}; emails cannot be sent."
        )
    return LogEmailBackend()
