from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from personal_agent.db import init_db
from personal_agent.services.ingestion import IngestionService
from personal_agent.services.repository import Repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract reviewable candidates from existing raw_evidence rows."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of raw_evidence rows to inspect.",
    )
    parser.add_argument(
        "--evidence-id",
        type=int,
        help="Extract a single raw_evidence row by id.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Extract even if this raw_evidence row already has candidates.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print rows that would be extracted without calling the LLM.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    init_db()
    repository = Repository()
    service = IngestionService(repository)

    if args.evidence_id is not None:
        evidence = repository.get_raw_evidence(args.evidence_id)
        evidence_rows = [evidence] if evidence is not None else []
    else:
        evidence_rows = repository.list_raw_evidence(limit=args.limit)

    if not evidence_rows:
        print("No raw_evidence rows found.")
        return 0

    extracted = 0
    skipped = 0
    for evidence in evidence_rows:
        existing = repository.list_extraction_candidates(
            raw_evidence_id=evidence.id,
            limit=1,
        )
        if existing and not args.force:
            skipped += 1
            print(f"skipped: raw_evidence_id={evidence.id} already has candidates")
            continue

        source = evidence.source_uri or evidence.source_type
        if args.dry_run:
            print(f"would_extract: raw_evidence_id={evidence.id} source={source}")
            continue

        result = service.extract_from_evidence(
            evidence.id,
            skip_existing=not args.force,
        )
        extracted += len(result.candidates)
        print(
            "extracted: "
            f"raw_evidence_id={evidence.id} "
            f"candidates={len(result.candidates)} "
            f"source={source}"
        )

    print(f"Summary: extracted_candidates={extracted}, skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
