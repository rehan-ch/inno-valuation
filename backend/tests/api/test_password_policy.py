"""The new-password policy (NIST style): no commonly used or context-derived
passwords, checked wherever a password is set, with refused links staying usable."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.passwords import common_passwords
from app.emails.backends import MemoryEmailBackend
from tests.api.helpers import csrf, sign_in, signed_in, token_from
from tests.factories import TEST_PASSWORD, verified_user

SIGN_UP = "/api/v1/auth/sign-up"
FORGOT = "/api/v1/auth/password/forgot"
RESET = "/api/v1/auth/password/reset"
CHANGE_PASSWORD = "/api/v1/me/password"

# Any list entry works; a fixed one keeps failures readable.
COMMON = "1234567890"


def sign_up_body(password: str, email: str = "new@example.com") -> dict[str, object]:
    return {"name": "New Person", "email": email, "password": password, "accepted_terms": True}


def test_the_list_is_loaded_and_passes_the_length_rule() -> None:
    passwords = common_passwords()
    assert COMMON in passwords
    assert len(passwords) > 5_000
    assert all(len(p) >= 10 for p in passwords)


def test_sign_up_refuses_a_common_password(client: TestClient) -> None:
    response = client.post(SIGN_UP, json=sign_up_body(COMMON))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "weak_password"


def test_sign_up_refuses_a_password_containing_the_email(client: TestClient) -> None:
    response = client.post(
        SIGN_UP, json=sign_up_body("the.new.person~2026", "new.person@example.com")
    )
    assert response.status_code == 422
    assert "email" in response.json()["error"]["message"]


def test_sign_up_refuses_a_password_containing_the_name_or_product(client: TestClient) -> None:
    for password in ("person of the year", "my innovaluation login"):
        response = client.post(SIGN_UP, json=sign_up_body(password))
        assert response.status_code == 422, password
        assert response.json()["error"]["code"] == "weak_password"


def test_sign_up_accepts_an_unusual_passphrase(client: TestClient) -> None:
    response = client.post(SIGN_UP, json=sign_up_body("quiet llama paints the fence"))
    assert response.status_code == 202


def test_a_refused_reset_keeps_the_link_usable(
    client: TestClient, db: Session, outbox: MemoryEmailBackend
) -> None:
    verified_user(email="person@example.com")
    client.post(FORGOT, json={"email": "person@example.com"})
    token = token_from(outbox.outbox[0])

    refused = client.post(RESET, json={"token": token, "new_password": COMMON})
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "weak_password"

    accepted = client.post(RESET, json={"token": token, "new_password": "quiet llama paints"})
    assert accepted.status_code == 200
    assert sign_in(client, "person@example.com", "quiet llama paints").status_code == 200


def test_change_password_refuses_a_common_password(client: TestClient) -> None:
    user = verified_user(email="person@example.com")
    signed_in(client, user)

    response = client.post(
        CHANGE_PASSWORD,
        json={"current_password": TEST_PASSWORD, "new_password": COMMON},
        headers=csrf(client),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "weak_password"
