"""Email delivery backends.

- ``ResendEmailBackend`` when ``RESEND_API_KEY`` is set.
- ``DevSmtpEmailBackend`` in development without a key: logs the line, delivers the
  email to the local mail catcher (Mailpit, web UI on http://localhost:8025), then opens
  it there in a new browser tab, like a letter opener. The link holds a live token,
  which is acceptable only on a developer's machine.
- ``LogEmailBackend`` in test without a key: the log line only.
- In staging or production without a key, ``get_email_backend`` raises
  ``EmailNotConfiguredError``, so the send task fails loudly instead of dropping the email.

Tests swap in ``MemoryEmailBackend`` with ``override_email_backend``.
"""

import json
import logging
import smtplib
import urllib.parse
import urllib.request
import webbrowser
from email.message import EmailMessage as MimeMessage
from email.utils import make_msgid
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


def mime_message(message: EmailMessage, sender: str) -> MimeMessage:
    """The email as a multipart message: plain text first, HTML as the alternative."""
    mime = MimeMessage()
    mime["From"] = sender
    mime["To"] = message.to
    mime["Subject"] = message.subject
    mime["Message-ID"] = make_msgid(domain="innovaluation.local")
    mime.set_content(message.text)
    mime.add_alternative(message.html, subtype="html")
    return mime


class DevSmtpEmailBackend(LogEmailBackend):
    """The log line, delivery to the local mail catcher, then the email in a new tab.

    A catcher that is not running only costs a warning, and a tab that cannot be opened
    costs nothing: the log line already holds the link, so a developer is never stuck.
    The tab opens on the machine running the worker, which in development is the
    developer's own.
    """

    def __init__(
        self,
        host: str,
        port: int,
        sender: str,
        *,
        web_url: str = "http://localhost:8025",
        open_in_browser: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._web_url = web_url.rstrip("/")
        self._open_in_browser = open_in_browser

    def send(self, message: EmailMessage, *, idempotency_key: str) -> None:
        super().send(message, idempotency_key=idempotency_key)
        mime = mime_message(message, self._sender)
        try:
            with smtplib.SMTP(self._host, self._port, timeout=5) as smtp:
                smtp.send_message(mime)
        except OSError:
            logger.warning(
                "The local mail catcher is not reachable on %s:%s, so this email is only "
                "in the log line above. Start it with: docker compose up -d mailpit",
                self._host,
                self._port,
            )
            return
        if self._open_in_browser:
            self._open_in_new_tab(str(mime["Message-ID"]))

    def _open_in_new_tab(self, message_id: str) -> None:
        query = urllib.parse.quote(f'message-id:"{message_id}"')
        try:
            with urllib.request.urlopen(  # noqa: S310  (fixed local http URL from settings)
                f"{self._web_url}/api/v1/search?query={query}", timeout=3
            ) as response:
                found = json.load(response)["messages"]
            if found:
                webbrowser.open_new_tab(f"{self._web_url}/view/{found[0]['ID']}")
        except (OSError, ValueError, KeyError, webbrowser.Error):
            logger.debug("Could not open the email in a browser tab.", exc_info=True)


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
    if settings.environment == "development":
        return DevSmtpEmailBackend(
            settings.dev_smtp_host,
            settings.dev_smtp_port,
            settings.email_from,
            web_url=settings.dev_mail_web_url,
            open_in_browser=settings.dev_email_open_browser,
        )
    return LogEmailBackend()
