"""Email templates: both versions, plain wording, escaped HTML."""

from datetime import date, timedelta

import pytest

from app.emails.messages import (
    ROLE_PHRASES,
    TEMPLATE_DIR,
    AccountEmail,
    OrganisationEmail,
    describe_duration,
    render_already_registered,
    render_consultant_access,
    render_invitation,
    render_token_email,
)
from app.models.enums import MembershipRole

ORIGIN = "https://app.example.com"
EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)


def test_every_kind_has_html_and_text() -> None:
    for kind in [*AccountEmail, *OrganisationEmail]:
        assert (TEMPLATE_DIR / f"{kind.value}.html").is_file()
        assert (TEMPLATE_DIR / f"{kind.value}.txt").is_file()


def test_templates_have_no_em_or_en_dashes() -> None:
    for path in TEMPLATE_DIR.iterdir():
        text = path.read_text()
        assert EM_DASH not in text, path.name
        assert EN_DASH not in text, path.name


@pytest.mark.parametrize("kind", [AccountEmail.VERIFY_EMAIL, AccountEmail.RESET_PASSWORD])
def test_token_email(kind: AccountEmail) -> None:
    message = render_token_email(
        kind,
        to="a@example.com",
        origin=ORIGIN + "/",
        token="tok_123",
        expires_in=timedelta(hours=1),
    )
    assert message.link.startswith(f"{ORIGIN}/")
    assert message.link.endswith("#token=tok_123")
    assert "?" not in message.link  # never in the query string
    assert message.link in message.text
    assert "1 hour" in message.text
    assert "tok_123" not in message.subject
    assert EM_DASH not in message.text + message.html + message.subject


def test_html_escapes_the_link() -> None:
    message = render_token_email(
        AccountEmail.VERIFY_EMAIL,
        to="a@example.com",
        origin='https://x.example.com/"><script>',
        token="t",
        expires_in=timedelta(hours=24),
    )
    assert "<script>" not in message.html
    assert "24 hours" in message.text


def test_already_registered_has_no_token() -> None:
    message = render_already_registered(to="a@example.com", origin=ORIGIN)
    assert "token" not in message.text
    assert f"{ORIGIN}/forgot-password" in message.text


@pytest.mark.parametrize(
    ("duration", "text"),
    [
        (timedelta(hours=1), "1 hour"),
        (timedelta(hours=24), "24 hours"),
        (timedelta(minutes=30), "30 minutes"),
        (timedelta(minutes=1), "1 minute"),
        (timedelta(days=7), "7 days"),
        (timedelta(days=2), "2 days"),
    ],
)
def test_describe_duration(duration: timedelta, text: str) -> None:
    assert describe_duration(duration) == text


HOSTILE = '<a href="https://evil.example">Click</a>'


def test_invitation_email() -> None:
    message = render_invitation(
        to="new@example.com",
        origin=ORIGIN,
        token="inv_123",
        organisation_name="Acme Ltd",
        inviter_name="Ada",
        role="committee",
        expires_in=timedelta(days=7),
    )
    assert message.link == f"{ORIGIN}/invitations/accept#token=inv_123"
    assert "Ada has invited you to join Acme Ltd" in message.text
    assert "as a committee member" in message.text
    assert "7 days" in message.text
    assert "Acme" not in message.subject  # typed by users, so never in the subject
    assert EM_DASH not in message.text + message.html + message.subject


def test_invitation_without_an_inviter() -> None:
    message = render_invitation(
        to="new@example.com",
        origin=ORIGIN,
        token="t",
        organisation_name="Acme",
        inviter_name=None,
        role="member",
        expires_in=timedelta(days=7),
    )
    assert message.text.startswith("Hello,\n\nSomeone has invited you")


def test_team_emails_escape_user_typed_names() -> None:
    invitation = render_invitation(
        to="new@example.com",
        origin=ORIGIN,
        token="t",
        organisation_name=HOSTILE,
        inviter_name=HOSTILE,
        role="member",
        expires_in=timedelta(days=7),
    )
    access = render_consultant_access(
        to="amy@example.com",
        origin=ORIGIN,
        organisation_name=HOSTILE,
        granter_name=HOSTILE,
        ends_on=date(2099, 1, 31),
    )
    for message in (invitation, access):
        assert HOSTILE not in message.html
        assert "&lt;a href=" in message.html


def test_consultant_access_email() -> None:
    message = render_consultant_access(
        to="amy@example.com",
        origin=ORIGIN,
        organisation_name="Acme Ltd",
        granter_name="Ada",
        ends_on=date(2099, 1, 5),
    )
    assert message.link == f"{ORIGIN}/consultant-access"
    assert "Ada has given you read-only access to the results of Acme Ltd" in message.text
    assert "ends on 5 January 2099" in message.text
    assert "token" not in message.text


def test_every_role_reads_in_a_sentence() -> None:
    assert set(ROLE_PHRASES) == {role.value for role in MembershipRole}
