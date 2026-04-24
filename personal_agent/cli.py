from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence

from personal_agent.config import settings
from personal_agent.db import init_db
from personal_agent.models import (
    ArtifactCreate,
    NoteCreate,
    OpportunityCreate,
    PolicyCreate,
    ProfileFactCreate,
    ProfilePreferenceCreate,
    ProjectCreate,
    ServiceCreate,
    TaskCreate,
)
from personal_agent.services.ops import OpsService
from personal_agent.services.overview import OverviewService
from personal_agent.services.repository import Repository


@dataclass
class CLIContext:
    repository: Repository
    overview: OverviewService
    ops: OpsService


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid datetime '{value}'. Use ISO format like 2026-04-17 or 2026-04-17T21:30:00") from exc


def _coerce_value(raw: str) -> Any:
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _parse_key_value_pairs(items: Sequence[str] | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"Expected KEY=VALUE, got '{item}'")
        key, raw_value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid key in '{item}'")
        payload[key] = _coerce_value(raw_value.strip())
    return payload


def _truncate(value: Any, width: int = 40) -> str:
    text = "" if value is None else str(value)
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def _print_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    if not rows:
        print("(empty)")
        return

    rendered_rows = [[_truncate(cell) for cell in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in rendered_rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    header_line = " | ".join(header.ljust(widths[index]) for index, header in enumerate(headers))
    divider_line = "-+-".join("-" * widths[index] for index in range(len(headers)))
    print(header_line)
    print(divider_line)
    for row in rendered_rows:
        print(" | ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)))


def _print_section(title: str) -> None:
    print()
    print(title)
    print("=" * len(title))


def _build_context() -> CLIContext:
    repository = Repository()
    return CLIContext(
        repository=repository,
        overview=OverviewService(repository),
        ops=OpsService(repository),
    )


def _find_project_id(repository: Repository, slug: str | None) -> int | None:
    if slug is None:
        return None
    for project in repository.list_projects():
        if project.slug == slug:
            return project.id
    raise ValueError(f"Project '{slug}' not found")


def _find_service(repository: Repository, identifier: str) -> tuple[int, str]:
    if identifier.isdigit():
        service = repository.get_service(int(identifier))
        if service is None:
            raise ValueError(f"Service '{identifier}' not found")
        return service.id, service.name
    for service in repository.list_services():
        if service.name == identifier:
            return service.id, service.name
    raise ValueError(f"Service '{identifier}' not found")


def cmd_home(_args: argparse.Namespace, ctx: CLIContext) -> int:
    snapshot = ctx.overview.build_snapshot()
    counts = snapshot.counts

    print(settings.app_name)
    print(f"DB: {settings.db_path}")
    print(
        "Counts: "
        f"projects={counts.projects}, "
        f"artifacts={counts.artifacts}, "
        f"notes={counts.notes}, "
        f"open_opportunities={counts.open_opportunities}, "
        f"open_tasks={counts.open_tasks}, "
        f"active_policies={counts.active_policies}, "
        f"services={counts.services}"
    )

    _print_section("Active Policies")
    _print_table(
        ("id", "scope", "target", "value"),
        [(item.id, item.scope, item.target, item.value) for item in snapshot.active_policies],
    )

    _print_section("Recent Tasks")
    _print_table(
        ("id", "status", "priority", "title", "due_at"),
        [(item.id, item.status, item.priority, item.title, item.due_at or "") for item in snapshot.recent_tasks],
    )

    _print_section("Recent Projects")
    _print_table(
        ("id", "slug", "status", "title"),
        [(item.id, item.slug, item.status, item.title) for item in snapshot.recent_projects],
    )

    _print_section("Recent Artifacts")
    _print_table(
        ("id", "type", "title", "url"),
        [(item.id, item.artifact_type, item.title, item.url or "") for item in snapshot.recent_artifacts],
    )

    _print_section("Recent Opportunities")
    _print_table(
        ("id", "status", "source", "kind", "title"),
        [(item.id, item.status, item.source, item.kind, item.title) for item in snapshot.recent_opportunities],
    )

    _print_section("Recent Notes")
    _print_table(
        ("id", "kind", "title", "body"),
        [(item.id, item.kind, item.title or "", item.body) for item in snapshot.recent_notes],
    )

    _print_section("Services")
    _print_table(
        ("id", "status", "type", "name", "endpoint"),
        [(item.id, item.status, item.service_type, item.name, item.endpoint or "") for item in snapshot.services],
    )

    return 0


def cmd_capture(args: argparse.Namespace, ctx: CLIContext) -> int:
    note = ctx.repository.create_note(
        NoteCreate(
            kind=args.kind,
            title=args.title,
            body=args.body,
            source=args.source,
        )
    )
    print(f"Captured note #{note.id}: {note.title or note.kind}")
    return 0


def cmd_note_list(_args: argparse.Namespace, ctx: CLIContext) -> int:
    notes = ctx.repository.list_notes()
    _print_table(
        ("id", "kind", "title", "body", "created_at"),
        [(item.id, item.kind, item.title or "", item.body, item.created_at) for item in notes],
    )
    return 0


def cmd_fact_set(args: argparse.Namespace, ctx: CLIContext) -> int:
    fact = ctx.repository.upsert_profile_fact(
        ProfileFactCreate(
            category=args.category,
            key=args.key,
            value=args.value,
            source=args.source,
            confidence=args.confidence,
        )
    )
    print(f"Saved fact {fact.category}.{fact.key} = {fact.value}")
    return 0


def cmd_fact_list(_args: argparse.Namespace, ctx: CLIContext) -> int:
    facts = ctx.repository.list_profile_facts()
    _print_table(
        ("category", "key", "value", "source", "confidence"),
        [(item.category, item.key, item.value, item.source or "", item.confidence) for item in facts],
    )
    return 0


def cmd_preference_add(args: argparse.Namespace, ctx: CLIContext) -> int:
    preference = ctx.repository.add_profile_preference(
        ProfilePreferenceCreate(
            area=args.area,
            value=args.value,
            weight=args.weight,
            rationale=args.rationale,
        )
    )
    print(f"Saved preference #{preference.id}: {preference.area} -> {preference.value}")
    return 0


def cmd_preference_list(_args: argparse.Namespace, ctx: CLIContext) -> int:
    preferences = ctx.repository.list_profile_preferences()
    _print_table(
        ("id", "area", "value", "weight", "rationale"),
        [(item.id, item.area, item.value, item.weight, item.rationale or "") for item in preferences],
    )
    return 0


def cmd_project_add(args: argparse.Namespace, ctx: CLIContext) -> int:
    project = ctx.repository.upsert_project(
        ProjectCreate(
            slug=args.slug,
            title=args.title,
            kind=args.kind,
            status=args.status,
            summary=args.summary,
            repo_url=args.repo_url,
            started_at=_parse_datetime(args.started_at),
            ended_at=_parse_datetime(args.ended_at),
            metadata=_parse_key_value_pairs(args.meta),
        )
    )
    print(f"Saved project #{project.id}: {project.slug} ({project.title})")
    return 0


def cmd_project_list(_args: argparse.Namespace, ctx: CLIContext) -> int:
    projects = ctx.repository.list_projects()
    _print_table(
        ("id", "slug", "status", "kind", "title", "repo_url"),
        [(item.id, item.slug, item.status, item.kind, item.title, item.repo_url or "") for item in projects],
    )
    return 0


def cmd_artifact_add(args: argparse.Namespace, ctx: CLIContext) -> int:
    artifact = ctx.repository.create_artifact(
        ArtifactCreate(
            project_id=_find_project_id(ctx.repository, args.project),
            artifact_type=args.artifact_type,
            title=args.title,
            url=args.url,
            summary=args.summary,
            source=args.source,
            metadata=_parse_key_value_pairs(args.meta),
            published_at=_parse_datetime(args.published_at),
        )
    )
    print(f"Saved artifact #{artifact.id}: {artifact.title}")
    return 0


def cmd_artifact_list(args: argparse.Namespace, ctx: CLIContext) -> int:
    project_id = _find_project_id(ctx.repository, args.project) if args.project else None
    artifacts = ctx.repository.list_artifacts(project_id=project_id)
    _print_table(
        ("id", "project_id", "type", "title", "source", "url"),
        [(item.id, item.project_id or "", item.artifact_type, item.title, item.source or "", item.url or "") for item in artifacts],
    )
    return 0


def cmd_opportunity_add(args: argparse.Namespace, ctx: CLIContext) -> int:
    opportunity = ctx.repository.create_opportunity(
        OpportunityCreate(
            source=args.source,
            kind=args.kind,
            title=args.title,
            external_id=args.external_id,
            url=args.url,
            status=args.status,
            rating_hint=args.rating_hint,
            tags=args.tag or [],
            payload=_parse_key_value_pairs(args.meta),
        )
    )
    print(f"Saved opportunity #{opportunity.id}: {opportunity.title}")
    return 0


def cmd_opportunity_list(_args: argparse.Namespace, ctx: CLIContext) -> int:
    opportunities = ctx.repository.list_opportunities()
    _print_table(
        ("id", "status", "source", "kind", "title", "rating", "tags"),
        [
            (
                item.id,
                item.status,
                item.source,
                item.kind,
                item.title,
                item.rating_hint or "",
                ",".join(item.tags),
            )
            for item in opportunities
        ],
    )
    return 0


def cmd_task_add(args: argparse.Namespace, ctx: CLIContext) -> int:
    task = ctx.repository.create_task(
        TaskCreate(
            project_id=_find_project_id(ctx.repository, args.project),
            opportunity_id=args.opportunity_id,
            kind=args.kind,
            title=args.title,
            status=args.status,
            priority=args.priority,
            due_at=_parse_datetime(args.due_at),
            note=args.note,
            metadata=_parse_key_value_pairs(args.meta),
        )
    )
    print(f"Saved task #{task.id}: {task.title}")
    return 0


def cmd_task_list(args: argparse.Namespace, ctx: CLIContext) -> int:
    tasks = ctx.repository.list_tasks(status=args.status)
    _print_table(
        ("id", "status", "priority", "project_id", "opp_id", "title", "due_at"),
        [
            (
                item.id,
                item.status,
                item.priority,
                item.project_id or "",
                item.opportunity_id or "",
                item.title,
                item.due_at or "",
            )
            for item in tasks
        ],
    )
    return 0


def cmd_policy_add(args: argparse.Namespace, ctx: CLIContext) -> int:
    policy = ctx.repository.create_policy(
        PolicyCreate(
            policy_type=args.policy_type,
            scope=args.scope,
            target=args.target,
            value=args.value,
            rationale=args.rationale,
            active=not args.inactive,
            starts_at=_parse_datetime(args.starts_at),
            ends_at=_parse_datetime(args.ends_at),
            metadata=_parse_key_value_pairs(args.meta),
        )
    )
    print(f"Saved policy #{policy.id}: {policy.scope}/{policy.target} -> {policy.value}")
    return 0


def cmd_policy_list(args: argparse.Namespace, ctx: CLIContext) -> int:
    policies = ctx.repository.list_policies(active_only=not args.all)
    _print_table(
        ("id", "active", "type", "scope", "target", "value"),
        [(item.id, item.active, item.policy_type, item.scope, item.target, item.value) for item in policies],
    )
    return 0


def cmd_service_add(args: argparse.Namespace, ctx: CLIContext) -> int:
    service = ctx.repository.create_service(
        ServiceCreate(
            name=args.name,
            service_type=args.service_type,
            endpoint=args.endpoint,
            owner=args.owner,
            status=args.status,
            metadata=_parse_key_value_pairs(args.meta),
        )
    )
    print(f"Saved service #{service.id}: {service.name}")
    return 0


def cmd_service_list(_args: argparse.Namespace, ctx: CLIContext) -> int:
    services = ctx.repository.list_services()
    _print_table(
        ("id", "status", "type", "name", "endpoint", "owner"),
        [(item.id, item.status, item.service_type, item.name, item.endpoint or "", item.owner or "") for item in services],
    )
    return 0


def cmd_service_probe(args: argparse.Namespace, ctx: CLIContext) -> int:
    if args.all or not args.identifier:
        checks = ctx.ops.probe_all_services()
        _print_table(
            ("service_id", "status", "latency_ms", "message"),
            [(item.service_id, item.status, item.latency_ms or "", item.message or "") for item in checks],
        )
        return 0

    service_id, service_name = _find_service(ctx.repository, args.identifier)
    check = ctx.ops.probe_service(service_id)
    print(
        f"Probe finished for {service_name} (#{service_id}): "
        f"status={check.status}, latency_ms={check.latency_ms}, message={check.message or ''}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="contextos",
        description="ContextOS CLI",
    )
    parser.set_defaults(func=cmd_home)

    subparsers = parser.add_subparsers(dest="command")

    home_parser = subparsers.add_parser("home", help="Show dashboard")
    home_parser.set_defaults(func=cmd_home)

    capture_parser = subparsers.add_parser("capture", help="Quickly capture a note")
    capture_parser.add_argument("body", help="Note content")
    capture_parser.add_argument("--title", help="Optional note title")
    capture_parser.add_argument("--kind", default="note", help="Note kind")
    capture_parser.add_argument("--source", help="Note source")
    capture_parser.set_defaults(func=cmd_capture)

    note_parser = subparsers.add_parser("note", aliases=["notes"], help="Manage notes")
    note_subparsers = note_parser.add_subparsers(dest="note_command", required=True)
    note_list_parser = note_subparsers.add_parser("list", help="List notes")
    note_list_parser.set_defaults(func=cmd_note_list)

    fact_parser = subparsers.add_parser("fact", help="Manage structured profile facts")
    fact_subparsers = fact_parser.add_subparsers(dest="fact_command", required=True)
    fact_set_parser = fact_subparsers.add_parser("set", help="Create or update a fact")
    fact_set_parser.add_argument("category")
    fact_set_parser.add_argument("key")
    fact_set_parser.add_argument("value")
    fact_set_parser.add_argument("--source")
    fact_set_parser.add_argument("--confidence", type=float, default=1.0)
    fact_set_parser.set_defaults(func=cmd_fact_set)
    fact_list_parser = fact_subparsers.add_parser("list", help="List facts")
    fact_list_parser.set_defaults(func=cmd_fact_list)

    preference_parser = subparsers.add_parser("preference", aliases=["pref"], help="Manage preferences")
    preference_subparsers = preference_parser.add_subparsers(dest="preference_command", required=True)
    preference_add_parser = preference_subparsers.add_parser("add", help="Add a preference")
    preference_add_parser.add_argument("area")
    preference_add_parser.add_argument("value")
    preference_add_parser.add_argument("--weight", type=float, default=1.0)
    preference_add_parser.add_argument("--rationale")
    preference_add_parser.set_defaults(func=cmd_preference_add)
    preference_list_parser = preference_subparsers.add_parser("list", help="List preferences")
    preference_list_parser.set_defaults(func=cmd_preference_list)

    project_parser = subparsers.add_parser("project", aliases=["projects"], help="Manage projects")
    project_subparsers = project_parser.add_subparsers(dest="project_command", required=True)
    project_add_parser = project_subparsers.add_parser("add", help="Create or update a project")
    project_add_parser.add_argument("--slug", required=True)
    project_add_parser.add_argument("--title", required=True)
    project_add_parser.add_argument("--kind", default="project")
    project_add_parser.add_argument("--status", default="active")
    project_add_parser.add_argument("--summary")
    project_add_parser.add_argument("--repo-url")
    project_add_parser.add_argument("--started-at")
    project_add_parser.add_argument("--ended-at")
    project_add_parser.add_argument("--meta", action="append", help="Metadata as KEY=VALUE")
    project_add_parser.set_defaults(func=cmd_project_add)
    project_list_parser = project_subparsers.add_parser("list", help="List projects")
    project_list_parser.set_defaults(func=cmd_project_list)

    artifact_parser = subparsers.add_parser("artifact", aliases=["artifacts"], help="Manage artifacts")
    artifact_subparsers = artifact_parser.add_subparsers(dest="artifact_command", required=True)
    artifact_add_parser = artifact_subparsers.add_parser("add", help="Add an artifact")
    artifact_add_parser.add_argument("--project", help="Project slug")
    artifact_add_parser.add_argument("--artifact-type", required=True)
    artifact_add_parser.add_argument("--title", required=True)
    artifact_add_parser.add_argument("--url")
    artifact_add_parser.add_argument("--summary")
    artifact_add_parser.add_argument("--source")
    artifact_add_parser.add_argument("--published-at")
    artifact_add_parser.add_argument("--meta", action="append", help="Metadata as KEY=VALUE")
    artifact_add_parser.set_defaults(func=cmd_artifact_add)
    artifact_list_parser = artifact_subparsers.add_parser("list", help="List artifacts")
    artifact_list_parser.add_argument("--project", help="Project slug")
    artifact_list_parser.set_defaults(func=cmd_artifact_list)

    opportunity_parser = subparsers.add_parser("opportunity", aliases=["opp"], help="Manage opportunities")
    opportunity_subparsers = opportunity_parser.add_subparsers(dest="opportunity_command", required=True)
    opportunity_add_parser = opportunity_subparsers.add_parser("add", help="Add an opportunity")
    opportunity_add_parser.add_argument("--source", required=True)
    opportunity_add_parser.add_argument("--kind", required=True)
    opportunity_add_parser.add_argument("--title", required=True)
    opportunity_add_parser.add_argument("--external-id")
    opportunity_add_parser.add_argument("--url")
    opportunity_add_parser.add_argument("--status", default="open")
    opportunity_add_parser.add_argument("--rating-hint", type=int)
    opportunity_add_parser.add_argument("--tag", action="append", help="Repeat for multiple tags")
    opportunity_add_parser.add_argument("--meta", action="append", help="Metadata as KEY=VALUE")
    opportunity_add_parser.set_defaults(func=cmd_opportunity_add)
    opportunity_list_parser = opportunity_subparsers.add_parser("list", help="List opportunities")
    opportunity_list_parser.set_defaults(func=cmd_opportunity_list)

    task_parser = subparsers.add_parser("task", aliases=["tasks"], help="Manage tasks")
    task_subparsers = task_parser.add_subparsers(dest="task_command", required=True)
    task_add_parser = task_subparsers.add_parser("add", help="Add a task")
    task_add_parser.add_argument("--title", required=True)
    task_add_parser.add_argument("--project", help="Project slug")
    task_add_parser.add_argument("--opportunity-id", type=int)
    task_add_parser.add_argument("--kind", default="task")
    task_add_parser.add_argument("--status", default="todo")
    task_add_parser.add_argument("--priority", default="normal")
    task_add_parser.add_argument("--due-at")
    task_add_parser.add_argument("--note")
    task_add_parser.add_argument("--meta", action="append", help="Metadata as KEY=VALUE")
    task_add_parser.set_defaults(func=cmd_task_add)
    task_list_parser = task_subparsers.add_parser("list", help="List tasks")
    task_list_parser.add_argument("--status")
    task_list_parser.set_defaults(func=cmd_task_list)

    policy_parser = subparsers.add_parser("policy", aliases=["policies"], help="Manage policies")
    policy_subparsers = policy_parser.add_subparsers(dest="policy_command", required=True)
    policy_add_parser = policy_subparsers.add_parser("add", help="Add a policy")
    policy_add_parser.add_argument("--policy-type", required=True)
    policy_add_parser.add_argument("--scope", required=True)
    policy_add_parser.add_argument("--target", required=True)
    policy_add_parser.add_argument("--value", required=True)
    policy_add_parser.add_argument("--rationale")
    policy_add_parser.add_argument("--inactive", action="store_true")
    policy_add_parser.add_argument("--starts-at")
    policy_add_parser.add_argument("--ends-at")
    policy_add_parser.add_argument("--meta", action="append", help="Metadata as KEY=VALUE")
    policy_add_parser.set_defaults(func=cmd_policy_add)
    policy_list_parser = policy_subparsers.add_parser("list", help="List policies")
    policy_list_parser.add_argument("--all", action="store_true", help="Show inactive policies too")
    policy_list_parser.set_defaults(func=cmd_policy_list)

    service_parser = subparsers.add_parser("service", aliases=["services"], help="Manage services")
    service_subparsers = service_parser.add_subparsers(dest="service_command", required=True)
    service_add_parser = service_subparsers.add_parser("add", help="Register a service")
    service_add_parser.add_argument("--name", required=True)
    service_add_parser.add_argument("--service-type", required=True)
    service_add_parser.add_argument("--endpoint")
    service_add_parser.add_argument("--owner")
    service_add_parser.add_argument("--status", default="unknown")
    service_add_parser.add_argument("--meta", action="append", help="Metadata as KEY=VALUE")
    service_add_parser.set_defaults(func=cmd_service_add)
    service_list_parser = service_subparsers.add_parser("list", help="List services")
    service_list_parser.set_defaults(func=cmd_service_list)
    service_probe_parser = service_subparsers.add_parser("probe", help="Probe one service or all services")
    service_probe_parser.add_argument("identifier", nargs="?", help="Service id or name")
    service_probe_parser.add_argument("--all", action="store_true")
    service_probe_parser.set_defaults(func=cmd_service_probe)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    init_db()
    ctx = _build_context()

    try:
        return int(args.func(args, ctx) or 0)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
