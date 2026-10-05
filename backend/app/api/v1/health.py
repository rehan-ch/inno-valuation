import logging
from typing import Literal

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.settings import get_settings
from app.schemas.health import HealthOut

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut, status_code=status.HTTP_200_OK)
def health(db: Session = Depends(get_db)) -> HealthOut:
    try:
        db.execute(text("SELECT 1"))
        database: Literal["ok", "error"] = "ok"
    except SQLAlchemyError:
        logger.warning("Health check could not reach the database")
        database = "error"
    return HealthOut(
        status="ok",
        database=database,
        version=get_settings().app_version,
    )
