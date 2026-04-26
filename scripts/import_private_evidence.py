from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from personal_agent.db import init_db
from personal_agent.models import IngestExtractRequest, RawEvidenceCreate
from personal_agent.services.ingestion import IngestionService
from personal_agent.services.repository import Repository


DEFAULT_EVIDENCE_DIR = ROOT / "private" / "extracted"
SOURCE_TYPE = "private_seed"
DEFAULT_EXCLUDED_FILENAMES = {"README.md", "deepseek_index.md"}


def iter_markdown_files(evidence_dir: Path) -> list[Path]:
    if not evidence_dir.exists():
        raise FileNotFoundError(f"Evidence directory does not exist: {evidence_dir}")
    if not evidence_dir.is_dir():
        raise NotADirectoryError(f"Evidence path is not a directory: {evidence_dir}")
    return sorted(
        path
        for path in evidence_dir.glob("*.md")
        if path.is_file() and path.name not in DEFAULT_EXCLUDED_FILENAMES
    )


def display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def import_file(
    repository: Repository,
    path: Path,
    *,
    extract: bool,
    dry_run: bool,
) -> tuple[str, int | None]:
    source_uri = display_path(path)
    existing = repository.get_raw_evidence_by_source(SOURCE_TYPE, source_uri)
    if existing is not None:
        return "skipped", existing.id

    content = path.read_text(encoding="utf-8")
    if dry_run:
        return "would_import", None

    if extract:
        service = IngestionService(repository)
        result = service.extract(
            IngestExtractRequest(
                source_type=SOURCE_TYPE,
                source_uri=source_uri,
                content=content,
                metadata={
                    "filename": path.name,
                    "kind": "seed",
                    "importer": "scripts/import_private_evidence.py",
                },
            )
        )
        return "imported_extracted", result.evidence.id

    evidence = repository.create_raw_evidence(
        RawEvidenceCreate(
            source_type=SOURCE_TYPE,
            source_uri=source_uri,
            content=content,
            metadata={
                "filename": path.name,
                "kind": "seed",
                "importer": "scripts/import_private_evidence.py",
            },
        )
    )
    return "imported", evidence.id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import private extracted markdown evidence into ContextOS raw_evidence."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_EVIDENCE_DIR,
        help="Directory containing cleaned markdown seed files.",
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Also call the LLM ingestion extractor to create pending candidates.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be imported without writing to the database.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    evidence_dir = args.path
    if not evidence_dir.is_absolute():
        evidence_dir = ROOT / evidence_dir

    init_db()
    repository = Repository()
    files = iter_markdown_files(evidence_dir)
    if not files:
        print(f"No markdown files found in {evidence_dir}")
        return 0

    counts = {
        "imported": 0,
        "imported_extracted": 0,
        "skipped": 0,
        "would_import": 0,
    }
    for path in files:
        status, evidence_id = import_file(
            repository,
            path,
            extract=args.extract,
            dry_run=args.dry_run,
        )
        counts[status] += 1
        id_part = f" raw_evidence_id={evidence_id}" if evidence_id is not None else ""
        print(f"{status}: {display_path(path)}{id_part}")

    print(
        "Summary: "
        f"imported={counts['imported']}, "
        f"imported_extracted={counts['imported_extracted']}, "
        f"skipped={counts['skipped']}, "
        f"would_import={counts['would_import']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
