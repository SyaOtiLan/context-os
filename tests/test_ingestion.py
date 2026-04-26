from __future__ import annotations

import pytest
from fastapi import HTTPException

from personal_agent.api import ingest
from personal_agent.models import (
    ExtractionCandidateCreate,
    IngestExtractRequest,
    ProjectCreate,
    RawEvidenceCreate,
)
from personal_agent.services.ingestion import CandidateApplyError, IngestionService
from personal_agent.services.repository import Repository


class FakeLLMService:
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 900,
    ) -> str:
        assert "Evidence:" in messages[-1]["content"]
        return """
        {
          "candidates": [
            {
              "kind": "profile_fact",
              "payload": {
                "category": "background",
                "key": "competitive_programming",
                "value": "ACM background",
                "source": "manual_text",
                "confidence": 0.95
              },
              "confidence": 0.95,
              "reason": "The user explicitly mentions ACM background.",
              "evidence_quote": "我 ACM 背景"
            },
            {
              "kind": "project",
              "payload": {
                "slug": "context-os",
                "title": "ContextOS",
                "kind": "project",
                "status": "active",
                "summary": "Personal context system for profile-driven issue discovery.",
                "repo_url": "https://github.com/SyaOtiLan/context-os",
                "metadata": {}
              },
              "confidence": 0.9,
              "reason": "The user says they are building ContextOS.",
              "evidence_quote": "最近在做 ContextOS"
            },
            {
              "kind": "unsupported",
              "payload": {},
              "confidence": 0.5
            }
          ]
        }
        """.strip()


def test_extract_stores_raw_evidence_and_pending_candidates(repository: Repository) -> None:
    service = IngestionService(repository, FakeLLMService())

    result = service.extract(
        IngestExtractRequest(
            source_type="manual_text",
            content="我 ACM 背景，最近在做 ContextOS。",
        )
    )

    assert result.evidence.id > 0
    assert result.evidence.source_type == "manual_text"
    assert [candidate.kind for candidate in result.candidates] == ["profile_fact", "project"]
    assert all(candidate.status == "pending" for candidate in result.candidates)


def test_extract_from_existing_raw_evidence(repository: Repository) -> None:
    evidence = repository.create_raw_evidence(
        RawEvidenceCreate(
            source_type="manual_text",
            content="我 ACM 背景，最近在做 ContextOS。",
        )
    )
    service = IngestionService(repository, FakeLLMService())

    result = service.extract_from_evidence(evidence.id)

    assert result.evidence.id == evidence.id
    assert [candidate.kind for candidate in result.candidates] == ["profile_fact", "project"]


def test_extract_from_existing_raw_evidence_skips_existing_candidates(
    repository: Repository,
) -> None:
    evidence = repository.create_raw_evidence(
        RawEvidenceCreate(
            source_type="manual_text",
            content="我 ACM 背景，最近在做 ContextOS。",
        )
    )
    service = IngestionService(repository, FakeLLMService())

    assert len(service.extract_from_evidence(evidence.id).candidates) == 2
    assert service.extract_from_evidence(evidence.id).candidates == []


def test_apply_profile_fact_candidate_writes_formal_table(repository: Repository) -> None:
    service = IngestionService(repository, FakeLLMService())
    result = service.extract(
        IngestExtractRequest(
            source_type="manual_text",
            content="我 ACM 背景。",
        )
    )
    fact_candidate = result.candidates[0]

    applied = service.apply_candidate(fact_candidate.id)
    facts = repository.list_profile_facts()

    assert applied.entity_type == "profile_fact"
    assert facts[0].category == "background"
    assert facts[0].key == "competitive_programming"
    assert facts[0].value == "ACM background"
    assert repository.get_extraction_candidate(fact_candidate.id).status == "applied"


def test_apply_project_candidate_writes_project(repository: Repository) -> None:
    service = IngestionService(repository, FakeLLMService())
    result = service.extract(
        IngestExtractRequest(
            source_type="manual_text",
            content="最近在做 ContextOS。",
        )
    )
    project_candidate = result.candidates[1]

    applied = service.apply_candidate(project_candidate.id)
    projects = repository.list_projects()

    assert applied.entity_type == "project"
    assert projects[0].slug == "context-os"
    assert projects[0].title == "ContextOS"


def test_reject_candidate_prevents_later_apply(repository: Repository) -> None:
    service = IngestionService(repository, FakeLLMService())
    result = service.extract(
        IngestExtractRequest(
            source_type="manual_text",
            content="我 ACM 背景。",
        )
    )
    candidate = result.candidates[0]

    rejected = service.reject_candidate(candidate.id)

    assert rejected.status == "rejected"
    with pytest.raises(CandidateApplyError):
        service.apply_candidate(candidate.id)


def test_artifact_candidate_can_attach_by_project_slug(repository: Repository) -> None:
    project = repository.upsert_project(
        payload=ProjectCreate(
            slug="context-os",
            title="ContextOS",
        )
    )
    evidence = repository.create_raw_evidence(
        RawEvidenceCreate(source_type="manual_text", content="ContextOS repo is public.")
    )
    candidate = repository.create_extraction_candidate(
        payload=ExtractionCandidateCreate(
            raw_evidence_id=evidence.id,
            kind="artifact",
            payload={
                "project_slug": "context-os",
                "artifact_type": "repo",
                "title": "ContextOS GitHub repository",
                "url": "https://github.com/SyaOtiLan/context-os",
                "source": "manual_text",
                "metadata": {},
            },
        )
    )
    service = IngestionService(repository, FakeLLMService())

    applied = service.apply_candidate(candidate.id)
    artifacts = repository.list_artifacts(project_id=project.id)

    assert applied.entity_type == "artifact"
    assert artifacts[0].project_id == project.id
    assert artifacts[0].title == "ContextOS GitHub repository"


def test_ingest_api_handlers_apply_and_reject(monkeypatch, repository: Repository) -> None:
    service = IngestionService(repository, FakeLLMService())
    monkeypatch.setattr(ingest, "ingestion_service", service)

    extracted = ingest.extract(
        IngestExtractRequest(
            source_type="manual_text",
            content="我 ACM 背景，最近在做 ContextOS。",
        )
    )
    pending = ingest.list_candidates(status="pending", limit=50)
    applied = ingest.apply_candidate(extracted.candidates[0].id)
    rejected = ingest.reject_candidate(extracted.candidates[1].id)

    assert len(pending) == 2
    assert applied.entity_type == "profile_fact"
    assert rejected.status == "rejected"


def test_ingest_api_rejects_invalid_status(repository: Repository) -> None:
    with pytest.raises(HTTPException) as exc_info:
        ingest.list_candidates(status="unknown")

    assert exc_info.value.status_code == 400
