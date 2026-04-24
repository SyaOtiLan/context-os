from __future__ import annotations

from fastapi import APIRouter

from personal_agent.models import Project, ProjectCreate
from personal_agent.services.repository import Repository


router = APIRouter(prefix="/projects", tags=["projects"])
repository = Repository()


@router.get("", response_model=list[Project])
def list_projects() -> list[Project]:
    return repository.list_projects()


@router.post("", response_model=Project)
def upsert_project(payload: ProjectCreate) -> Project:
    return repository.upsert_project(payload)
