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
    ServiceCreate,
    TaskCreate,
)
from personal_agent.services.overview import OverviewService


def test_build_snapshot_aggregates_counts_and_recent_items(repository) -> None:
    project = repository.upsert_project(
        ProjectCreate(slug="myagent", title="MyAgent", metadata={"stage": "mvp"})
    )
    repository.create_artifact(
        ArtifactCreate(
            project_id=project.id,
            artifact_type="repo",
            title="GitHub Repo",
            url="https://github.com/example/myagent",
        )
    )
    repository.create_note(
        NoteCreate(kind="daily", title="progress", body="wired overview")
    )
    repository.create_opportunity(
        OpportunityCreate(
            source="issueradar",
            kind="job",
            title="Backend Intern",
            tags=["backend"],
        )
    )
    repository.create_task(
        TaskCreate(
            project_id=project.id,
            title="Ship MVP",
            due_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
    )
    repository.create_policy(
        PolicyCreate(
            policy_type="throttle",
            scope="notifications",
            target="issueradar",
            value="disabled",
            starts_at=datetime.now(timezone.utc) - timedelta(hours=1),
            ends_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    repository.upsert_profile_fact(
        ProfileFactCreate(category="career", key="target_role", value="backend")
    )
    repository.add_profile_preference(
        ProfilePreferenceCreate(area="jobs", value="backend-first")
    )
    repository.create_service(
        ServiceCreate(
            name="issueradar",
            service_type="http",
            endpoint="https://example.com/health",
            status="unknown",
        )
    )

    snapshot = OverviewService(repository).build_snapshot()

    assert snapshot.counts.projects == 1
    assert snapshot.counts.artifacts == 1
    assert snapshot.counts.notes == 1
    assert snapshot.counts.open_opportunities == 1
    assert snapshot.counts.open_tasks == 1
    assert snapshot.counts.active_policies == 1
    assert snapshot.counts.services == 1
    assert snapshot.profile.facts[0].key == "target_role"
    assert snapshot.profile.preferences[0].area == "jobs"
    assert snapshot.recent_projects[0].slug == "myagent"
    assert snapshot.recent_artifacts[0].title == "GitHub Repo"
    assert snapshot.recent_notes[0].kind == "daily"
    assert snapshot.recent_opportunities[0].source == "issueradar"
    assert snapshot.recent_tasks[0].title == "Ship MVP"
    assert snapshot.active_policies[0].target == "issueradar"
    assert snapshot.services[0].name == "issueradar"


def test_build_snapshot_counts_closed_items_as_not_open(repository) -> None:
    repository.create_opportunity(
        OpportunityCreate(
            source="issueradar",
            kind="job",
            title="Ignored Job",
            status="ignored",
        )
    )
    repository.create_task(
        TaskCreate(
            title="Completed task",
            status="done",
        )
    )

    snapshot = OverviewService(repository).build_snapshot()

    assert snapshot.counts.open_opportunities == 0
    assert snapshot.counts.open_tasks == 0
