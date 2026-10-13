"""Email templates: both versions, plain wording, escaped HTML."""

from datetime import timedelta

import pytest

from app.emails.messages import (
    TEMPLATE_DIR,
    AccountEmail,
    describe_duration,
    render_already_registered,
    render_token_email,
)

ORIGIN = "https://app.example.com"
EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)


def test_every_kind_has_html_and_text() -> None:
    for kind in AccountEmail:
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
    ],
)
def test_describe_duration(duration: timedelta, text: str) -> None:
    assert describe_duration(duration) == text
