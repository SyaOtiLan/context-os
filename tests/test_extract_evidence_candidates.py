from __future__ import annotations

from personal_agent.models import ExtractionCandidateCreate, RawEvidenceCreate
from personal_agent.services.repository import Repository
from scripts import extract_evidence_candidates


def test_extract_evidence_candidates_dry_run_does_not_write(
    repository: Repository,
) -> None:
    repository.create_raw_evidence(
        RawEvidenceCreate(source_type="manual_text", content="User builds ContextOS.")
    )

    exit_code = extract_evidence_candidates.main(["--dry-run"])

    assert exit_code == 0
    assert repository.list_extraction_candidates(limit=10) == []


def test_extract_evidence_candidates_skips_existing_candidates(
    repository: Repository,
) -> None:
    evidence = repository.create_raw_evidence(
        RawEvidenceCreate(source_type="manual_text", content="User builds ContextOS.")
    )
    repository.create_extraction_candidate(
        ExtractionCandidateCreate(
            raw_evidence_id=evidence.id,
            kind="profile_fact",
            payload={
                "category": "project",
                "key": "context_os",
                "value": "User builds ContextOS.",
            },
        )
    )

    exit_code = extract_evidence_candidates.main(["--dry-run"])

    assert exit_code == 0
    assert len(repository.list_extraction_candidates(limit=10)) == 1
