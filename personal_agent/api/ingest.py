from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from personal_agent.models import (
    ExtractionCandidate,
    IngestApplyResponse,
    IngestExtractRequest,
    IngestExtractResponse,
)
from personal_agent.services.ingestion import CandidateApplyError, IngestionError, IngestionService
from personal_agent.services.llm import LLMNotConfiguredError
from personal_agent.services.repository import Repository, RepositoryNotFoundError


router = APIRouter(prefix="/ingest", tags=["ingest"])
repository = Repository()
ingestion_service = IngestionService(repository)


@router.post("/extract", response_model=IngestExtractResponse)
def extract(payload: IngestExtractRequest) -> IngestExtractResponse:
    try:
        return ingestion_service.extract(payload)
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/candidates", response_model=list[ExtractionCandidate])
def list_candidates(
    status: str | None = None,
    kind: str | None = None,
    limit: int = Query(default=50, ge=0, le=200),
) -> list[ExtractionCandidate]:
    try:
        return ingestion_service.list_candidates(status=status, kind=kind, limit=limit)
    except IngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/candidates/{candidate_id}/apply", response_model=IngestApplyResponse)
def apply_candidate(candidate_id: int) -> IngestApplyResponse:
    try:
        return ingestion_service.apply_candidate(candidate_id)
    except RepositoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CandidateApplyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/candidates/{candidate_id}/reject", response_model=ExtractionCandidate)
def reject_candidate(candidate_id: int) -> ExtractionCandidate:
    try:
        return ingestion_service.reject_candidate(candidate_id)
    except RepositoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CandidateApplyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
