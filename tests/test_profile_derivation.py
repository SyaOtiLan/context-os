from __future__ import annotations

from datetime import datetime, timedelta, timezone

from personal_agent.models import ArtifactCreate, ProfileFactCreate, ProjectCreate
from personal_agent.services.profile_derivation import ProfileDerivationService


class FakeLLMService:
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 700,
    ) -> str:
        assert "Reviewed facts:" in messages[-1]["content"]
        assert "target_role: backend" in messages[-1]["content"]
        return """
- 背景：用户有后端方向的已审核目标。
- 当前目标：寻找适合练手和贡献的 GitHub issue。
- 适合任务：边界清晰、可复现、可验证的后端相关任务。
- 不适合任务：大规模重构或需求不清晰的长期任务。
""".strip()


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

    service = ProfileDerivationService(repository, llm_service=FakeLLMService())
    derived = service.build_profile()

    assert "target_role=backend" in derived.declared_facts
    assert "myagent" in derived.recent_projects
    assert "GitHub Repo" in derived.recent_artifacts
    assert derived.activity_status == "高活跃"
    assert "背景：" in derived.summary
    assert "适合任务" in derived.summary


def test_build_profile_returns_low_activity_without_recent_inputs(repository) -> None:
    derived = ProfileDerivationService(repository).build_profile()

    assert derived.declared_facts == []
    assert derived.recent_projects == []
    assert derived.recent_artifacts == []
    assert derived.activity_status == "低活跃"
    assert "当前声明目标：暂无明确声明" in derived.summary


def test_build_and_store_profile_persists_snapshot(repository) -> None:
    repository.upsert_profile_fact(
        ProfileFactCreate(category="career", key="target_role", value="backend")
    )

    snapshot = ProfileDerivationService(repository, llm_service=FakeLLMService()).build_and_store_profile()
    latest = repository.get_latest_profile_snapshot()

    assert snapshot.id > 0
    assert snapshot.source == "llm"
    assert latest is not None
    assert latest.id == snapshot.id
    assert "target_role=backend" in latest.declared_facts
    assert "适合任务" in latest.summary


def test_build_and_store_profile_marks_rule_fallback_snapshot(repository) -> None:
    repository.upsert_profile_fact(
        ProfileFactCreate(category="career", key="target_role", value="backend")
    )

    snapshot = ProfileDerivationService(repository).build_and_store_profile()

    assert snapshot.source == "rules"
    assert "当前声明目标：" in snapshot.summary
