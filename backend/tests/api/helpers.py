"""Helpers for request tests that need a signed-in user."""

from urllib.parse import parse_qs, urlparse

import httpx
from fastapi.testclient import TestClient

from app.core.sessions import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from app.emails.messages import EmailMessage
from app.models import Organisation, User
from app.models.enums import MembershipRole
from tests.factories import TEST_PASSWORD, MembershipFactory, OrganisationFactory, verified_user


def sign_in(client: TestClient, email: str, password: str = TEST_PASSWORD) -> httpx.Response:
    response: httpx.Response = client.post(
        "/api/v1/auth/sign-in", json={"email": email, "password": password}
    )
    return response


def signed_in(client: TestClient, user: User, organisation: Organisation | None = None) -> None:
    """Sign ``user`` in, and make ``organisation`` the active one if given."""
    response = sign_in(client, user.email)
    assert response.status_code == 200, response.text
    if organisation is not None and response.json()["active_organisation_id"] != str(
        organisation.id
    ):
        switched = client.post(
            "/api/v1/me/active-organisation",
            json={"organisation_id": str(organisation.id)},
            headers=csrf(client),
        )
        assert switched.status_code == 200, switched.text


def csrf(client: TestClient) -> dict[str, str]:
    return {CSRF_HEADER: client.cookies[CSRF_COOKIE]}


def session_cookies(client: TestClient) -> dict[str, str]:
    return {name: client.cookies[name] for name in (SESSION_COOKIE, CSRF_COOKIE)}


def use_cookies(client: TestClient, cookies: dict[str, str]) -> None:
    client.cookies.clear()
    for name, value in cookies.items():
        client.cookies.set(name, value)


def member(
    role: MembershipRole, organisation: Organisation | None = None, **user_kwargs: object
) -> tuple[User, Organisation]:
    """A verified user with ``role`` in ``organisation`` (a new one if not given)."""
    org = organisation or OrganisationFactory.create()
    user = verified_user(**user_kwargs)
    MembershipFactory.create(organisation=org, user=user, role=role)
    return user, org


def token_from(message: EmailMessage) -> str:
    """The token from an email link. It sits in the fragment, never in the query."""
    url = urlparse(message.link)
    assert url.query == ""
    return parse_qs(url.fragment)["token"][0]
