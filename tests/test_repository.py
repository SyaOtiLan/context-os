from __future__ import annotations

from datetime import datetime, timedelta, timezone

from personal_agent.models import (
    ArtifactCreate,
    NoteCreate,
    OpportunityCreate,
    PolicyCreate,
    ProfileFactCreate,
    ProfilePreferenceCreate,
    ProjectCreate,
    ServiceCheckCreate,
    ServiceCreate,
    TaskCreate,
)


def test_upsert_project_updates_existing_slug(repository) -> None:
    created = repository.upsert_project(
        ProjectCreate(
            slug="myagent",
            title="MyAgent",
            summary="first version",
            metadata={"source": "initial"},
        )
    )

    updated = repository.upsert_project(
        ProjectCreate(
            slug="myagent",
            title="MyAgent v2",
            summary="second version",
            metadata={"source": "updated"},
        )
    )

    assert created.id == updated.id
    assert updated.title == "MyAgent v2"
    assert updated.summary == "second version"
    assert updated.metadata == {"source": "updated"}
    assert len(repository.list_projects()) == 1


def test_list_policies_active_only_filters_by_time_and_flag(repository) -> None:
    now = datetime.now(timezone.utc)
    repository.create_policy(
        PolicyCreate(
            policy_type="throttle",
            scope="notifications",
            target="issueradar",
            value="disabled",
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
        )
    )
    repository.create_policy(
        PolicyCreate(
            policy_type="throttle",
            scope="notifications",
            target="future",
            value="disabled",
            starts_at=now + timedelta(hours=1),
        )
    )
    repository.create_policy(
        PolicyCreate(
            policy_type="throttle",
            scope="notifications",
            target="inactive",
            value="disabled",
            active=False,
        )
    )

    active = repository.list_policies(active_only=True)

    assert [policy.target for policy in active] == ["issueradar"]


def test_add_service_check_updates_service_status(repository) -> None:
    service = repository.create_service(
        ServiceCreate(
            name="issueradar",
            service_type="http",
            endpoint="https://example.com/health",
        )
    )

    check = repository.add_service_check(
        service.id,
        ServiceCheckCreate(
            status="up",
            checked_at=datetime.now(timezone.utc),
            message="HTTP 200",
            latency_ms=42,
            payload={"http_status": 200},
        ),
    )

    refreshed_service = repository.get_service(service.id)

    assert check.service_id == service.id
    assert check.status == "up"
    assert refreshed_service is not None
    assert refreshed_service.status == "up"


def test_upsert_profile_fact_updates_existing_fact(repository) -> None:
    first = repository.upsert_profile_fact(
        ProfileFactCreate(
            category="career",
            key="target_role",
            value="backend",
            source="manual",
            confidence=0.7,
        )
    )

    updated = repository.upsert_profile_fact(
        ProfileFactCreate(
            category="career",
            key="target_role",
            value="platform",
            source="derived",
            confidence=0.9,
        )
    )

    assert first.id == updated.id
    assert updated.value == "platform"
    assert updated.source == "derived"
    assert updated.confidence == 0.9


def test_add_profile_preference_preserves_order_by_area_then_id(repository) -> None:
    jobs = repository.add_profile_preference(
        ProfilePreferenceCreate(area="jobs", value="backend-first")
    )
    learning = repository.add_profile_preference(
        ProfilePreferenceCreate(area="learning", value="hands-on")
    )
    jobs_second = repository.add_profile_preference(
        ProfilePreferenceCreate(area="jobs", value="infra")
    )

    preferences = repository.list_profile_preferences()

    assert [item.id for item in preferences] == [jobs.id, jobs_second.id, learning.id]


def test_create_opportunity_updates_existing_source_external_id(repository) -> None:
    created = repository.create_opportunity(
        OpportunityCreate(
            source="issueradar",
            kind="job",
            external_id="job-1",
            title="Backend Intern",
            status="open",
            tags=["backend"],
            payload={"salary": "negotiable"},
        )
    )

    updated = repository.create_opportunity(
        OpportunityCreate(
            source="issueradar",
            kind="job",
            external_id="job-1",
            title="Backend Intern Updated",
            status="ignored",
            tags=["backend", "remote"],
            payload={"salary": "known"},
        )
    )

    assert created.id == updated.id
    assert updated.title == "Backend Intern Updated"
    assert updated.status == "ignored"
    assert updated.tags == ["backend", "remote"]
    assert updated.payload == {"salary": "known"}


def test_list_tasks_can_filter_and_order_by_due_at(repository) -> None:
    earlier = repository.create_task(
        TaskCreate(
            title="earlier",
            status="todo",
            due_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    repository.create_task(
        TaskCreate(
            title="later",
            status="todo",
            due_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )
    )
    repository.create_task(
        TaskCreate(
            title="done-task",
            status="done",
            due_at=datetime.now(timezone.utc) + timedelta(hours=3),
        )
    )

    todo_tasks = repository.list_tasks(status="todo")

    assert [task.title for task in todo_tasks] == ["earlier", "later"]
    assert todo_tasks[0].id == earlier.id


def test_create_opportunity_without_external_id_is_still_returned(repository) -> None:
    opportunity = repository.create_opportunity(
        OpportunityCreate(
            source="issueradar",
            kind="job",
            title="No External Id",
            status="open",
            tags=["backend"],
        )
    )

    assert opportunity.title == "No External Id"
    assert opportunity.external_id is None


def test_recent_lists_use_expected_ordering(repository) -> None:
    project = repository.upsert_project(ProjectCreate(slug="myagent", title="MyAgent"))
    repository.create_note(NoteCreate(kind="daily", body="first"))
    later_note = repository.create_note(NoteCreate(kind="daily", body="second"))
    repository.create_artifact(
        ArtifactCreate(
            project_id=project.id,
            artifact_type="repo",
            title="Older",
            published_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    newer_artifact = repository.create_artifact(
        ArtifactCreate(
            project_id=project.id,
            artifact_type="repo",
            title="Newer",
            published_at=datetime.now(timezone.utc),
        )
    )

    recent_notes = repository.list_recent_notes(limit=1)
    recent_artifacts = repository.list_recent_artifacts(limit=1)

    assert recent_notes[0].id == later_note.id
    assert recent_artifacts[0].id == newer_artifact.id
