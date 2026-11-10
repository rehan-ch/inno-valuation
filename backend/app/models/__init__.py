"""SQLAlchemy models, one module per table group.

Import every model module here so ``Base.metadata`` is complete for Alembic.
"""

from app.db.base import Base
from app.models.accounts import (
    ConsultantGrant,
    Invitation,
    Membership,
    Organisation,
    User,
    UserToken,
)
from app.models.ai import AiRun
from app.models.audit import AuditEvent
from app.models.auth import RevokedSession, SignInThrottle
from app.models.ideas import Idea, IqAssessment, IqDimensionScore
from app.models.readiness import (
    ReadinessAssessment,
    ReadinessConsensus,
    ReadinessResponse,
    ReadinessResult,
)
from app.models.targets import DimensionTargets
from app.models.weights import DimensionWeights

__all__ = [
    "AiRun",
    "AuditEvent",
    "Base",
    "ConsultantGrant",
    "DimensionTargets",
    "DimensionWeights",
    "Idea",
    "Invitation",
    "IqAssessment",
    "IqDimensionScore",
    "Membership",
    "Organisation",
    "ReadinessAssessment",
    "ReadinessConsensus",
    "ReadinessResponse",
    "ReadinessResult",
    "RevokedSession",
    "SignInThrottle",
    "User",
    "UserToken",
]
