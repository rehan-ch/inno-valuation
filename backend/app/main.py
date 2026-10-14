import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.errors import UnhandledErrorMiddleware, register_exception_handlers
from app.core.sessions import CSRF_HEADER
from app.core.settings import get_settings

logger = logging.getLogger(__name__)

# Interactive docs and the schema are served only where developers work. Deployed APIs do
# not advertise their routes.
DOCS_ENVIRONMENTS = frozenset({"development", "test"})

# Only what the frontend sends. A test fails if a route uses a method missing here.
CORS_METHODS = ("GET", "POST", "PATCH", "DELETE")
CORS_HEADERS = ("Content-Type", CSRF_HEADER)


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.is_deployed and not settings.resend_api_key:
        # Account emails will fail (loudly, in the task) until the key is set.
        logger.error("RESEND_API_KEY is not set: verification and reset emails cannot be sent.")
    docs_on = settings.environment in DOCS_ENVIRONMENTS
    app = FastAPI(
        title="InnoValuation API",
        version=settings.app_version,
        docs_url="/docs" if docs_on else None,
        redoc_url="/redoc" if docs_on else None,
        openapi_url="/openapi.json" if docs_on else None,
    )
    # Added first so it sits inside CORSMiddleware and 500 responses keep CORS headers.
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=list(CORS_METHODS),
        allow_headers=list(CORS_HEADERS),
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
