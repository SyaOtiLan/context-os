from __future__ import annotations

from fastapi import APIRouter

from personal_agent.models import Note, NoteCreate
from personal_agent.services.repository import Repository


router = APIRouter(prefix="/notes", tags=["notes"])
repository = Repository()


@router.get("", response_model=list[Note])
def list_notes() -> list[Note]:
    return repository.list_notes()


@router.post("", response_model=Note)
def create_note(payload: NoteCreate) -> Note:
    return repository.create_note(payload)

