from fastapi import APIRouter, Depends

from app.api.v1 import auth, health, me, organisation
from app.core.csrf import require_trusted_origin

# Every unsafe request must come from the frontend origin (see app.core.csrf).
api_router = APIRouter(dependencies=[Depends(require_trusted_origin)])
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(organisation.router)
