from __future__ import annotations

from fastapi import APIRouter

from personal_agent.models import Artifact, ArtifactCreate
from personal_agent.services.repository import Repository


router = APIRouter(prefix="/artifacts", tags=["artifacts"])
repository = Repository()


@router.get("", response_model=list[Artifact])
def list_artifacts(project_id: int | None = None) -> list[Artifact]:
    return repository.list_artifacts(project_id=project_id)


@router.post("", response_model=Artifact)
def create_artifact(payload: ArtifactCreate) -> Artifact:
    return repository.create_artifact(payload)
