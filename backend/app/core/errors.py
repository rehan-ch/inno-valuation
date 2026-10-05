"""Single error envelope and the exception handlers that produce it.

Every error response has the shape ``{"error": {"code": "...", "message": "..."}}``.
Validation errors add ``error.details``.
"""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

HTTP_STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "too_many_requests",
}


class AppError(Exception):
    """Domain error raised by services and dependencies."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def error_body(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def _code_for_status(status_code: int) -> str:
    if status_code in HTTP_STATUS_CODES:
        return HTTP_STATUS_CODES[status_code]
    return "internal_error" if status_code >= 500 else "http_error"


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message))


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    if isinstance(exc.detail, str):
        message = exc.detail
    else:
        try:
            message = HTTPStatus(exc.status_code).phrase
        except ValueError:
            message = "Error"
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(_code_for_status(exc.status_code), message),
        headers=exc.headers,
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Drop the submitted input from details so user text never echoes into responses or logs.
    details = [
        {key: value for key, value in err.items() if key not in ("input", "ctx", "url")}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error_body(
            "validation_error", "The request is not valid.", jsonable_encoder(details)
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=error_body("internal_error", "Something went wrong."),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """The one place where error handlers are attached to the app."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
