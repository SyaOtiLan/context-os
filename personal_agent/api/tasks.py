from __future__ import annotations

from fastapi import APIRouter

from personal_agent.models import Task, TaskCreate
from personal_agent.services.repository import Repository


router = APIRouter(prefix="/tasks", tags=["tasks"])
repository = Repository()


@router.get("", response_model=list[Task])
def list_tasks(status: str | None = None) -> list[Task]:
    return repository.list_tasks(status=status)


@router.post("", response_model=Task)
def create_task(payload: TaskCreate) -> Task:
    return repository.create_task(payload)
