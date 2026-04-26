from __future__ import annotations

from pathlib import Path

from personal_agent.services.repository import Repository
from scripts import import_private_evidence


def test_import_private_evidence_imports_markdown(tmp_path: Path, repository: Repository) -> None:
    evidence_dir = tmp_path / "extracted"
    evidence_dir.mkdir()
    seed = evidence_dir / "profile_seed.md"
    seed.write_text("# Profile\n\nUser builds ContextOS.", encoding="utf-8")

    exit_code = import_private_evidence.main(["--path", str(evidence_dir)])
    rows = repository.list_raw_evidence(limit=10)

    assert exit_code == 0
    assert len(rows) == 1
    assert rows[0].source_type == import_private_evidence.SOURCE_TYPE
    assert rows[0].source_uri.endswith("profile_seed.md")
    assert "ContextOS" in rows[0].content


def test_import_private_evidence_skips_duplicate_source(
    tmp_path: Path,
    repository: Repository,
) -> None:
    evidence_dir = tmp_path / "extracted"
    evidence_dir.mkdir()
    seed = evidence_dir / "profile_seed.md"
    seed.write_text("# Profile\n\nUser builds ContextOS.", encoding="utf-8")

    assert import_private_evidence.main(["--path", str(evidence_dir)]) == 0
    assert import_private_evidence.main(["--path", str(evidence_dir)]) == 0

    assert len(repository.list_raw_evidence(limit=10)) == 1


def test_import_private_evidence_dry_run_does_not_write(
    tmp_path: Path,
    repository: Repository,
) -> None:
    evidence_dir = tmp_path / "extracted"
    evidence_dir.mkdir()
    seed = evidence_dir / "profile_seed.md"
    seed.write_text("# Profile\n\nUser builds ContextOS.", encoding="utf-8")

    assert import_private_evidence.main(["--path", str(evidence_dir), "--dry-run"]) == 0

    assert repository.list_raw_evidence(limit=10) == []
