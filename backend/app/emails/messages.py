"""Account and team emails, rendered from Jinja2 templates in ``app/emails/templates/``.

Each email has an HTML and a plain-text version. Emails hold no sensitive data: no
passwords, no assessment content, nothing a reader of a forwarded email could misuse except
the single-use link itself. Team emails name the organisation and the person who sent the
invitation, nothing more. Those names are typed by users, so the subject lines stay fixed
and the HTML version escapes them.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final
from urllib.parse import urlencode

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

TEMPLATE_DIR: Final = Path(__file__).parent / "templates"
PRODUCT_NAME: Final = "InnoValuation"

_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=False),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
)


class AccountEmail(StrEnum):
    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"  # noqa: S105  (an email kind, not a password)
    ALREADY_REGISTERED = "already_registered"


SUBJECTS: Final[dict[AccountEmail, str]] = {
    AccountEmail.VERIFY_EMAIL: f"Confirm your email for {PRODUCT_NAME}",
    AccountEmail.RESET_PASSWORD: f"Reset your {PRODUCT_NAME} password",
    AccountEmail.ALREADY_REGISTERED: f"You already have a {PRODUCT_NAME} account",
}


class OrganisationEmail(StrEnum):
    INVITATION = "invitation"
    CONSULTANT_ACCESS = "consultant_access"


ORGANISATION_SUBJECTS: Final[dict[OrganisationEmail, str]] = {
    OrganisationEmail.INVITATION: f"You are invited to join a team on {PRODUCT_NAME}",
    OrganisationEmail.CONSULTANT_ACCESS: f"You have been given access on {PRODUCT_NAME}",
}

# How a role reads in a sentence: "join ... as a committee member".
ROLE_PHRASES: Final[dict[str, str]] = {
    "owner": "an owner",
    "admin": "an admin",
    "member": "a member",
    "committee": "a committee member",
    "investor": "an investor",
}

# Frontend pages the emails link to.
VERIFY_EMAIL_PATH: Final = "/verify-email"
RESET_PASSWORD_PATH: Final = "/reset-password"  # noqa: S105
SIGN_IN_PATH: Final = "/sign-in"
FORGOT_PASSWORD_PATH: Final = "/forgot-password"  # noqa: S105
ACCEPT_INVITATION_PATH: Final = "/invitations/accept"
CONSULTANT_ACCESS_PATH: Final = "/consultant-access"


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str
    # The main link, so the development log backend can print it. Never logged elsewhere.
    link: str


def frontend_link(origin: str, path: str, token: str | None = None) -> str:
    """A frontend URL. The token goes in the fragment (``#token=...``): browsers never send
    the fragment to a server, so it stays out of access logs, proxies and Referer headers.
    The page reads ``location.hash``, posts the token, then clears the hash."""
    base = origin.rstrip("/") + path
    return f"{base}#{urlencode({'token': token})}" if token else base


def describe_duration(duration: timedelta) -> str:
    """'7 days', '24 hours', '1 hour', '30 minutes': for the expiry sentence in emails."""
    minutes = int(duration.total_seconds()) // 60
    if minutes >= 2 * 24 * 60 and minutes % (24 * 60) == 0:
        return f"{minutes // (24 * 60)} days"
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"


def render_token_email(
    kind: AccountEmail, *, to: str, origin: str, token: str, expires_in: timedelta
) -> EmailMessage:
    path = {
        AccountEmail.VERIFY_EMAIL: VERIFY_EMAIL_PATH,
        AccountEmail.RESET_PASSWORD: RESET_PASSWORD_PATH,
    }[kind]
    link = frontend_link(origin, path, token)
    return _render(
        kind.value, SUBJECTS[kind], to=to, link=link, expires_in=describe_duration(expires_in)
    )


def render_already_registered(*, to: str, origin: str) -> EmailMessage:
    link = frontend_link(origin, SIGN_IN_PATH)
    kind = AccountEmail.ALREADY_REGISTERED
    return _render(
        kind.value,
        SUBJECTS[kind],
        to=to,
        link=link,
        forgot_link=frontend_link(origin, FORGOT_PASSWORD_PATH),
    )


def render_invitation(
    *,
    to: str,
    origin: str,
    token: str,
    organisation_name: str,
    inviter_name: str | None,
    role: str,
    expires_in: timedelta,
) -> EmailMessage:
    kind = OrganisationEmail.INVITATION
    return _render(
        kind.value,
        ORGANISATION_SUBJECTS[kind],
        to=to,
        link=frontend_link(origin, ACCEPT_INVITATION_PATH, token),
        organisation=organisation_name,
        inviter=inviter_name or "Someone",
        role=ROLE_PHRASES[role],
        expires_in=describe_duration(expires_in),
    )


def render_consultant_access(
    *, to: str, origin: str, organisation_name: str, granter_name: str | None, ends_on: date
) -> EmailMessage:
    kind = OrganisationEmail.CONSULTANT_ACCESS
    return _render(
        kind.value,
        ORGANISATION_SUBJECTS[kind],
        to=to,
        link=frontend_link(origin, CONSULTANT_ACCESS_PATH),
        organisation=organisation_name,
        granter=granter_name or "Someone",
        ends_on=f"{ends_on.day} {ends_on:%B %Y}",
    )


def _render(template: str, subject: str, *, to: str, link: str, **context: str) -> EmailMessage:
    values = {"product": PRODUCT_NAME, "link": link, **context}
    return EmailMessage(
        to=to,
        subject=subject,
        text=_env.get_template(f"{template}.txt").render(values),
        html=_env.get_template(f"{template}.html").render(values),
        link=link,
    )
