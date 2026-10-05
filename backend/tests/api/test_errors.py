"""Every error leaves the API in the single envelope {"error": {"code", "message"}}."""

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.errors import AppError
from app.main import app, create_app


class _Body(BaseModel):
    score: int = Field(ge=1, le=10)


class _Out(BaseModel):
    ok: bool


@pytest.fixture(scope="module")
def error_client() -> TestClient:
    test_app: FastAPI = create_app()

    @test_app.get("/boom/app-error", response_model=_Out, status_code=200, tags=["test"])
    def raise_app_error() -> _Out:
        raise AppError("idea_locked", "This idea is locked.", status_code=409)

    @test_app.get("/boom/unhandled", response_model=_Out, status_code=200, tags=["test"])
    def raise_unhandled() -> _Out:
        raise RuntimeError("secret internal detail")

    @test_app.post("/boom/validate", response_model=_Out, status_code=200, tags=["test"])
    def validate(body: _Body) -> _Out:
        return _Out(ok=True)

    return TestClient(test_app, raise_server_exceptions=False)


def test_app_error(error_client: TestClient) -> None:
    response = error_client.get("/boom/app-error")
    assert response.status_code == 409
    assert response.json() == {"error": {"code": "idea_locked", "message": "This idea is locked."}}


def test_not_found_route() -> None:
    response = TestClient(app).get("/api/v1/does-not-exist")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"error": {"code": "not_found", "message": "Not Found"}}


def test_method_not_allowed() -> None:
    response = TestClient(app).post("/api/v1/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_validation_error(error_client: TestClient) -> None:
    response = error_client.post("/boom/validate", json={"score": 11})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"]
    assert error["details"][0]["loc"] == ["body", "score"]
    assert "input" not in error["details"][0]


def test_unhandled_error_hides_details(error_client: TestClient) -> None:
    response = error_client.get("/boom/unhandled")
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Something went wrong."}
    }
    assert "secret internal detail" not in response.text
