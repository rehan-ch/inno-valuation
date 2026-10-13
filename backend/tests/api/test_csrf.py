"""CSRF token, origin check and CORS."""

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.core.sessions import CSRF_COOKIE, CSRF_HEADER
from app.core.settings import get_settings
from app.main import CORS_METHODS, app
from tests.api.helpers import csrf, sign_in, signed_in
from tests.factories import verified_user

ME = "/api/v1/me"


def test_unsafe_request_without_csrf_header_is_rejected(client: TestClient) -> None:
    signed_in(client, verified_user())
    response = client.patch(ME, json={"name": "X"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_csrf_header_must_match_the_cookie(client: TestClient) -> None:
    signed_in(client, verified_user())
    response = client.patch(ME, json={"name": "X"}, headers={CSRF_HEADER: "wrong"})
    assert response.status_code == 403


def test_planted_cookie_and_header_pair_is_rejected(client: TestClient) -> None:
    """Another site that sets its own csrf_token cookie still fails: the token is in the JWT."""
    signed_in(client, verified_user())
    client.cookies.set(CSRF_COOKIE, "attacker-chosen")
    response = client.patch(ME, json={"name": "X"}, headers={CSRF_HEADER: "attacker-chosen"})
    assert response.status_code == 403


def test_matching_csrf_header_passes(client: TestClient) -> None:
    signed_in(client, verified_user())
    assert client.patch(ME, json={"name": "X"}, headers=csrf(client)).status_code == 200


def test_safe_methods_need_no_csrf_header(client: TestClient) -> None:
    signed_in(client, verified_user())
    assert client.get(ME).status_code == 200


def test_cross_site_origin_cannot_sign_in(client: TestClient) -> None:
    user = verified_user()
    response = client.post(
        "/api/v1/auth/sign-in",
        json={"email": user.email, "password": "anything at all"},
        headers={"Origin": "https://evil.example.com"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_cross_site_fetch_without_origin_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/password/forgot",
        json={"email": "a@example.com"},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code == 403


def test_frontend_origin_can_sign_in(client: TestClient) -> None:
    user = verified_user()
    client.headers["Origin"] = get_settings().frontend_origin
    assert sign_in(client, user.email).status_code == 200


def test_cross_site_origin_is_rejected_even_with_a_valid_token(client: TestClient) -> None:
    signed_in(client, verified_user())
    response = client.patch(
        ME, json={"name": "X"}, headers={**csrf(client), "Origin": "https://evil.example.com"}
    )
    assert response.status_code == 403


def test_cors_preflight_allows_the_csrf_header() -> None:
    response = TestClient(app).options(
        ME,
        headers={
            "Origin": get_settings().frontend_origin,
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "content-type,x-csrf-token",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-credentials"] == "true"
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "x-csrf-token" in allowed_headers
    assert "content-type" in allowed_headers


def test_cors_rejects_unused_methods_and_headers() -> None:
    client = TestClient(app)
    origin = get_settings().frontend_origin
    put = client.options(ME, headers={"Origin": origin, "Access-Control-Request-Method": "PUT"})
    assert put.status_code == 400
    header = client.options(
        ME,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-something-else",
        },
    )
    assert header.status_code == 400


def test_every_route_method_is_allowed_by_cors() -> None:
    used = {
        method
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods or ()
    }
    assert used <= set(CORS_METHODS) | {"HEAD"}, "add the new method to CORS_METHODS"


def test_null_origin_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/password/forgot", json={"email": "a@example.com"}, headers={"Origin": "null"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
