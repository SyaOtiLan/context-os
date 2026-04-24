from __future__ import annotations

from fastapi import APIRouter

from personal_agent.models import OverviewSnapshot
from personal_agent.services.overview import OverviewService


router = APIRouter(prefix="/overview", tags=["overview"])
service = OverviewService()


@router.get("", response_model=OverviewSnapshot)
def get_overview() -> OverviewSnapshot:
    return service.build_snapshot()
