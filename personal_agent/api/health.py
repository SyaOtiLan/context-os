from __future__ import annotations

from fastapi import APIRouter

from personal_agent.config import settings
from personal_agent.models import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=True, app=settings.app_name, db_path=str(settings.db_path))

