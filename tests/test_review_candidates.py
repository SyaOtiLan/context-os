from __future__ import annotations

from personal_agent.models import ExtractionCandidateCreate, ProjectCreate, RawEvidenceCreate
from personal_agent.services.repository import Repository
from scripts import review_candidates


def create_candidate(repository: Repository) -> int:
    evidence = repository.create_raw_evidence(
        RawEvidenceCreate(
            source_type="manual_text",
            source_uri="manual://seed",
            content="User builds ContextOS.",
        )
    )
    candidate = repository.create_extraction_candidate(
        ExtractionCandidateCreate(
            raw_evidence_id=evidence.id,
            kind="profile_fact",
            payload={
                "category": "project",
                "key": "context_os",
                "value": "User builds ContextOS.",
                "source": "manual_text",
                "confidence": 0.9,
            },
            confidence=0.9,
            reason="The evidence states that the user builds ContextOS.",
            evidence_quote="User builds ContextOS.",
        )
    )
    return candidate.id


def test_review_candidates_lists_pending_candidates(repository: Repository, capsys) -> None:
    candidate_id = create_candidate(repository)

    exit_code = review_candidates.main(["list"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert str(candidate_id) in output
    assert "profile_fact" in output
    assert "context_os" in output


def test_review_candidates_shows_candidate_detail(repository: Repository, capsys) -> None:
    candidate_id = create_candidate(repository)

    exit_code = review_candidates.main(["show", str(candidate_id)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "payload:" in output
    assert "manual://seed" in output
    assert "evidence_quote:" in output


def test_review_candidates_applies_candidate(repository: Repository, capsys) -> None:
    candidate_id = create_candidate(repository)

    exit_code = review_candidates.main(["apply", str(candidate_id)])

    output = capsys.readouterr().out
    facts = repository.list_profile_facts()
    assert exit_code == 0
    assert "applied:" in output
    assert facts[0].key == "context_os"
    assert repository.get_extraction_candidate(candidate_id).status == "applied"


def test_review_candidates_rejects_candidate(repository: Repository, capsys) -> None:
    candidate_id = create_candidate(repository)

    exit_code = review_candidates.main(["reject", str(candidate_id)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "rejected:" in output
    assert repository.get_extraction_candidate(candidate_id).status == "rejected"


def test_review_candidates_returns_error_for_non_pending_candidate(
    repository: Repository,
    capsys,
) -> None:
    project = repository.upsert_project(ProjectCreate(slug="context-os", title="ContextOS"))
    evidence = repository.create_raw_evidence(
        RawEvidenceCreate(source_type="manual_text", content="ContextOS exists.")
    )
    candidate = repository.create_extraction_candidate(
        ExtractionCandidateCreate(
            raw_evidence_id=evidence.id,
            kind="artifact",
            payload={
                "project_id": project.id,
                "artifact_type": "repo",
                "title": "ContextOS repo",
                "metadata": {},
            },
        )
    )
    assert review_candidates.main(["apply", str(candidate.id)]) == 0

    exit_code = review_candidates.main(["reject", str(candidate.id)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "already applied" in captured.err
