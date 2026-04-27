from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from personal_agent.db import init_db
from personal_agent.models import ExtractionCandidate
from personal_agent.services.ingestion import CandidateApplyError, IngestionError, IngestionService
from personal_agent.services.repository import Repository, RepositoryNotFoundError


def truncate(value: Any, width: int = 60) -> str:
    text = "" if value is None else str(value)
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def print_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    if not rows:
        print("(empty)")
        return

    rendered_rows = [[truncate(cell) for cell in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in rendered_rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * widths[index] for index in range(len(headers))))
    for row in rendered_rows:
        print(" | ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)))


def payload_summary(candidate: ExtractionCandidate) -> str:
    payload = candidate.payload
    if candidate.kind == "profile_fact":
        category = payload.get("category", "")
        key = payload.get("key", "")
        value = payload.get("value", "")
        return f"{category}.{key}={value}"
    if candidate.kind == "project":
        return str(payload.get("title") or payload.get("slug") or payload)
    if candidate.kind == "artifact":
        return str(payload.get("title") or payload.get("url") or payload)
    return json.dumps(payload, ensure_ascii=False)


def cmd_list(args: argparse.Namespace, service: IngestionService) -> int:
    candidates = service.list_candidates(
        status=args.status,
        kind=args.kind,
        limit=args.limit,
    )
    print_table(
        ("id", "status", "kind", "conf", "payload", "quote"),
        [
            (
                item.id,
                item.status,
                item.kind,
                f"{item.confidence:.2f}",
                payload_summary(item),
                item.evidence_quote or "",
            )
            for item in candidates
        ],
    )
    return 0


def cmd_show(args: argparse.Namespace, repository: Repository) -> int:
    candidate = repository.get_extraction_candidate(args.candidate_id)
    if candidate is None:
        raise RepositoryNotFoundError("extraction_candidate", args.candidate_id)

    evidence = repository.get_raw_evidence(candidate.raw_evidence_id)
    print(f"id: {candidate.id}")
    print(f"status: {candidate.status}")
    print(f"kind: {candidate.kind}")
    print(f"confidence: {candidate.confidence:.2f}")
    print(f"raw_evidence_id: {candidate.raw_evidence_id}")
    if evidence is not None:
        print(f"source_type: {evidence.source_type}")
        print(f"source_uri: {evidence.source_uri or ''}")
    print()
    print("payload:")
    print(json.dumps(candidate.payload, ensure_ascii=False, indent=2))
    print()
    print("reason:")
    print(candidate.reason or "")
    print()
    print("evidence_quote:")
    print(candidate.evidence_quote or "")
    return 0


def cmd_apply(args: argparse.Namespace, service: IngestionService) -> int:
    result = service.apply_candidate(args.candidate_id)
    print(
        "applied: "
        f"candidate_id={result.candidate.id} "
        f"entity_type={result.entity_type} "
        f"entity_id={result.entity_id}"
    )
    return 0


def cmd_reject(args: argparse.Namespace, service: IngestionService) -> int:
    candidate = service.reject_candidate(args.candidate_id)
    print(f"rejected: candidate_id={candidate.id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review, apply, or reject ContextOS extraction candidates."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List extraction candidates.")
    list_parser.add_argument("--status", default="pending", help="Candidate status filter.")
    list_parser.add_argument("--kind", help="Candidate kind filter.")
    list_parser.add_argument("--limit", type=int, default=50, help="Maximum rows to show.")

    show_parser = subparsers.add_parser("show", help="Show one candidate in detail.")
    show_parser.add_argument("candidate_id", type=int)

    apply_parser = subparsers.add_parser("apply", help="Apply a candidate into formal tables.")
    apply_parser.add_argument("candidate_id", type=int)

    reject_parser = subparsers.add_parser("reject", help="Reject a candidate.")
    reject_parser.add_argument("candidate_id", type=int)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    init_db()
    repository = Repository()
    service = IngestionService(repository)

    try:
        if args.command == "list":
            return cmd_list(args, service)
        if args.command == "show":
            return cmd_show(args, repository)
        if args.command == "apply":
            return cmd_apply(args, service)
        if args.command == "reject":
            return cmd_reject(args, service)
    except (CandidateApplyError, IngestionError, RepositoryNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
