from __future__ import annotations

from datetime import datetime, timedelta, timezone

from personal_agent.models import ArtifactCreate, ProfileFactCreate, ProjectCreate
from personal_agent.services.profile_derivation import ProfileDerivationService


def test_build_profile_uses_recent_projects_artifacts_and_facts(repository) -> None:
    repository.upsert_profile_fact(
        ProfileFactCreate(category="career", key="target_role", value="backend")
    )
    active_project = repository.upsert_project(
        ProjectCreate(slug="myagent", title="MyAgent")
    )
    repository.create_artifact(
        ArtifactCreate(
            project_id=active_project.id,
            artifact_type="repo",
            title="GitHub Repo",
            published_at=datetime.now(timezone.utc),
        )
    )
    stale_project = repository.upsert_project(
        ProjectCreate(slug="legacy", title="Legacy")
    )

    repository.upsert_project(
        ProjectCreate(
            slug=stale_project.slug,
            title=stale_project.title,
            ended_at=datetime.now(timezone.utc) - timedelta(days=180),
        )
    )

    service = ProfileDerivationService(repository)
    derived = service.build_profile()

    assert "target_role=backend" in derived.declared_facts
    assert "myagent" in derived.recent_projects
    assert "GitHub Repo" in derived.recent_artifacts
    assert derived.activity_status == "高活跃"
    assert "当前声明目标：" in derived.summary
    assert "最近活跃项目：" in derived.summary
    assert "最近证据：" in derived.summary
    assert "活跃状态：" in derived.summary


def test_build_profile_returns_low_activity_without_recent_inputs(repository) -> None:
    derived = ProfileDerivationService(repository).build_profile()

    assert derived.declared_facts == []
    assert derived.recent_projects == []
    assert derived.recent_artifacts == []
    assert derived.activity_status == "低活跃"


def test_build_and_store_profile_persists_snapshot(repository) -> None:
    repository.upsert_profile_fact(
        ProfileFactCreate(category="career", key="target_role", value="backend")
    )

    snapshot = ProfileDerivationService(repository).build_and_store_profile()
    latest = repository.get_latest_profile_snapshot()

    assert snapshot.id > 0
    assert snapshot.source == "rules"
    assert latest is not None
    assert latest.id == snapshot.id
    assert "target_role=backend" in latest.declared_facts
