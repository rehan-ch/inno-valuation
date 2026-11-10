from fastapi import APIRouter, Depends

from app.api.v1 import (
    audit,
    auth,
    consultants,
    dashboard,
    health,
    ideas,
    me,
    organisation,
    readiness,
    targets,
    team,
    weights,
)
from app.core.csrf import require_trusted_origin

# Every unsafe request must come from the frontend origin (see app.core.csrf).
api_router = APIRouter(dependencies=[Depends(require_trusted_origin)])
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(organisation.create_router)
api_router.include_router(organisation.router)
api_router.include_router(team.router)
api_router.include_router(team.invitation_router)
api_router.include_router(consultants.router)
api_router.include_router(readiness.router)
api_router.include_router(ideas.router)
api_router.include_router(weights.router)
api_router.include_router(targets.router)
api_router.include_router(dashboard.router)
api_router.include_router(audit.router)
