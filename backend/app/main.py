from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.errors import UnhandledErrorMiddleware, register_exception_handlers
from app.core.settings import get_settings

# Interactive docs and the schema are served only where developers work. Deployed APIs do
# not advertise their routes.
DOCS_ENVIRONMENTS = frozenset({"development", "test"})


def create_app() -> FastAPI:
    settings = get_settings()
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
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
