from __future__ import annotations

from fastapi import APIRouter

from personal_agent.models import Policy, PolicyCreate
from personal_agent.services.repository import Repository


router = APIRouter(prefix="/policies", tags=["policies"])
repository = Repository()


@router.get("", response_model=list[Policy])
def list_policies(active_only: bool = False) -> list[Policy]:
    return repository.list_policies(active_only=active_only)


@router.post("", response_model=Policy)
def create_policy(payload: PolicyCreate) -> Policy:
    return repository.create_policy(payload)
