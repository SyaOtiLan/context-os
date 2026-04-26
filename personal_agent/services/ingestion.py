from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from personal_agent.models import (
    Artifact,
    ArtifactCreate,
    ExtractionCandidate,
    ExtractionCandidateCreate,
    IngestApplyResponse,
    IngestExtractRequest,
    IngestExtractResponse,
    ProfileFact,
    ProfileFactCreate,
    Project,
    ProjectCreate,
)
from personal_agent.services.llm import LLMService
from personal_agent.services.repository import Repository, RepositoryNotFoundError


ALLOWED_CANDIDATE_KINDS = {"profile_fact", "project", "artifact"}
ALLOWED_CANDIDATE_STATUSES = {"pending", "applied", "rejected"}


class IngestionError(ValueError):
    pass


class CandidateApplyError(ValueError):
    pass


class CandidateParseError(ValueError):
    pass


def _strip_json_fence(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _parse_llm_candidates(raw_response: str) -> list[dict[str, Any]]:
    cleaned = _strip_json_fence(raw_response)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise CandidateParseError("LLM response is not valid JSON") from exc

    candidates = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(candidates, list):
        raise CandidateParseError("LLM response must contain a candidates list")
    return [item for item in candidates if isinstance(item, dict)]


def _parse_datetime(value: object) -> datetime | None:
    if value is None or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class IngestionService:
    def __init__(
        self,
        repository: Repository,
        llm_service: LLMService | None = None,
    ) -> None:
        self.repository = repository
        self.llm_service = llm_service

    def extract(self, payload: IngestExtractRequest) -> IngestExtractResponse:
        evidence = self.repository.create_raw_evidence(payload)
        candidates = self._extract_candidates(evidence_id=evidence.id, content=payload.content)
        return IngestExtractResponse(evidence=evidence, candidates=candidates)

    def extract_from_evidence(
        self,
        evidence_id: int,
        *,
        skip_existing: bool = True,
    ) -> IngestExtractResponse:
        evidence = self.repository.get_raw_evidence(evidence_id)
        if evidence is None:
            raise RepositoryNotFoundError("raw_evidence", evidence_id)

        if skip_existing:
            existing = self.repository.list_extraction_candidates(
                raw_evidence_id=evidence.id,
                limit=1,
            )
            if existing:
                return IngestExtractResponse(evidence=evidence, candidates=[])

        candidates = self._extract_candidates(evidence_id=evidence.id, content=evidence.content)
        return IngestExtractResponse(evidence=evidence, candidates=candidates)

    def list_candidates(
        self,
        status: str | None = None,
        kind: str | None = None,
        limit: int = 50,
    ) -> list[ExtractionCandidate]:
        if status is not None and status not in ALLOWED_CANDIDATE_STATUSES:
            raise IngestionError(f"Unsupported candidate status: {status}")
        if kind is not None and kind not in ALLOWED_CANDIDATE_KINDS:
            raise IngestionError(f"Unsupported candidate kind: {kind}")
        return self.repository.list_extraction_candidates(
            status=status,
            kind=kind,
            limit=limit,
        )

    def apply_candidate(self, candidate_id: int) -> IngestApplyResponse:
        candidate = self.repository.get_extraction_candidate(candidate_id)
        if candidate is None:
            raise RepositoryNotFoundError("extraction_candidate", candidate_id)
        if candidate.status != "pending":
            raise CandidateApplyError(f"Candidate {candidate_id} is already {candidate.status}")

        entity = self._apply_payload(candidate)
        applied = self.repository.mark_extraction_candidate_applied(
            candidate_id=candidate.id,
            entity_type=candidate.kind,
            entity_id=entity.id,
        )
        return IngestApplyResponse(
            candidate=applied,
            entity_type=candidate.kind,
            entity_id=entity.id,
        )

    def reject_candidate(self, candidate_id: int) -> ExtractionCandidate:
        candidate = self.repository.get_extraction_candidate(candidate_id)
        if candidate is None:
            raise RepositoryNotFoundError("extraction_candidate", candidate_id)
        if candidate.status != "pending":
            raise CandidateApplyError(f"Candidate {candidate_id} is already {candidate.status}")
        return self.repository.reject_extraction_candidate(candidate_id)

    def _extract_candidates(self, evidence_id: int, content: str) -> list[ExtractionCandidate]:
        llm = self.llm_service or LLMService()
        raw_response = llm.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You extract structured personal context candidates. "
                        "Return JSON only. Do not infer facts that are not supported by the text."
                    ),
                },
                {
                    "role": "user",
                    "content": self._render_extraction_prompt(content),
                },
            ],
            temperature=0.1,
            max_tokens=900,
        )
        parsed = _parse_llm_candidates(raw_response)

        candidates: list[ExtractionCandidate] = []
        for item in parsed:
            candidate = self._normalize_candidate(evidence_id, item)
            if candidate is None:
                continue
            candidates.append(self.repository.create_extraction_candidate(candidate))
        return candidates

    def _normalize_candidate(
        self,
        evidence_id: int,
        item: dict[str, Any],
    ) -> ExtractionCandidateCreate | None:
        kind = str(item.get("kind") or "").strip()
        if kind not in ALLOWED_CANDIDATE_KINDS:
            return None

        payload = item.get("payload")
        if not isinstance(payload, dict):
            return None

        confidence = item.get("confidence", 1.0)
        if not isinstance(confidence, int | float):
            confidence = 1.0
        confidence = max(0.0, min(1.0, float(confidence)))

        return ExtractionCandidateCreate(
            raw_evidence_id=evidence_id,
            kind=kind,
            payload=payload,
            confidence=confidence,
            reason=str(item["reason"]) if item.get("reason") is not None else None,
            evidence_quote=(
                str(item["evidence_quote"]) if item.get("evidence_quote") is not None else None
            ),
        )

    def _apply_payload(self, candidate: ExtractionCandidate) -> ProfileFact | Project | Artifact:
        try:
            if candidate.kind == "profile_fact":
                return self.repository.upsert_profile_fact(
                    ProfileFactCreate(**candidate.payload)
                )
            if candidate.kind == "project":
                return self.repository.upsert_project(
                    ProjectCreate(**self._normalize_project_payload(candidate.payload))
                )
            if candidate.kind == "artifact":
                return self.repository.create_artifact(
                    ArtifactCreate(**self._normalize_artifact_payload(candidate.payload))
                )
        except ValidationError as exc:
            raise CandidateApplyError(f"Invalid {candidate.kind} payload") from exc

        raise CandidateApplyError(f"Unsupported candidate kind: {candidate.kind}")

    def _normalize_project_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        normalized["started_at"] = _parse_datetime(normalized.get("started_at"))
        normalized["ended_at"] = _parse_datetime(normalized.get("ended_at"))
        metadata = normalized.get("metadata")
        if not isinstance(metadata, dict):
            normalized["metadata"] = {}
        return normalized

    def _normalize_artifact_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        project_slug = normalized.pop("project_slug", None)
        if normalized.get("project_id") is None and isinstance(project_slug, str):
            project = self.repository.get_project_by_slug(project_slug)
            if project is not None:
                normalized["project_id"] = project.id

        normalized["published_at"] = _parse_datetime(normalized.get("published_at"))
        metadata = normalized.get("metadata")
        if not isinstance(metadata, dict):
            normalized["metadata"] = {}
        return normalized

    def _render_extraction_prompt(self, content: str) -> str:
        return f"""
Extract reviewable candidates from this raw evidence.

Allowed candidate kinds:
- profile_fact: payload must match {{"category": str, "key": str, "value": str, "source": str | null, "confidence": float}}
- project: payload must match {{"slug": str, "title": str, "kind": str, "status": str, "summary": str | null, "repo_url": str | null, "metadata": object}}
- artifact: payload must match {{"project_slug": str | null, "project_id": int | null, "artifact_type": str, "title": str, "url": str | null, "summary": str | null, "source": str | null, "metadata": object}}

Rules:
- Only extract facts directly supported by the evidence.
- Prefer fewer high-confidence candidates over many speculative candidates.
- Use stable snake_case keys for profile facts.
- Return JSON only in this shape:
{{
  "candidates": [
    {{
      "kind": "profile_fact",
      "payload": {{}},
      "confidence": 0.9,
      "reason": "why this candidate is supported",
      "evidence_quote": "short quote from the evidence"
    }}
  ]
}}

Evidence:
{content}
""".strip()
