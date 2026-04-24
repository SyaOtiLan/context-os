from __future__ import annotations

from fastapi import APIRouter

from personal_agent.models import Opportunity, OpportunityCreate
from personal_agent.services.repository import Repository


router = APIRouter(prefix="/opportunities", tags=["opportunities"])
repository = Repository()


@router.get("", response_model=list[Opportunity])
def list_opportunities() -> list[Opportunity]:
    return repository.list_opportunities()


@router.post("", response_model=Opportunity)
def create_opportunity(payload: OpportunityCreate) -> Opportunity:
    return repository.create_opportunity(payload)

