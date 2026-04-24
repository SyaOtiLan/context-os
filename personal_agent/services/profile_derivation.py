from __future__ import annotations

from datetime import datetime, timedelta, timezone

from personal_agent.models import (
    Artifact,
    DerivedProfile,
    DerivedProfileSnapshot,
    DerivedProfileSnapshotCreate,
    ProfileFact,
    Project,
)
from personal_agent.services.repository import Repository
from personal_agent.time_utils import parse_timestamp


class ProfileDerivationService:
    def __init__(self, repository: Repository | None = None) -> None:
        self.repository = repository or Repository()

    def build_profile(self, recent_project_limit: int = 5, recent_artifact_limit: int = 10) -> DerivedProfile:
        now = datetime.now(timezone.utc)
        active_cutoff = now - timedelta(days=30)
        high_activity_cutoff = now - timedelta(days=7)

        facts = self.repository.list_profile_facts()
        recent_projects = self.repository.list_recent_projects(limit=recent_project_limit)
        recent_artifacts = self.repository.list_recent_artifacts(limit=recent_artifact_limit)

        declared_facts = self._render_declared_facts(facts)
        active_projects = [
            project.slug
            for project in recent_projects
            if self._project_activity_time(project) >= active_cutoff
        ]
        active_artifacts = [
            artifact.title
            for artifact in recent_artifacts
            if self._artifact_activity_time(artifact) >= active_cutoff
        ]
        activity_status = self._build_activity_status(
            recent_projects,
            recent_artifacts,
            high_activity_cutoff,
            active_cutoff,
        )

        summary_lines = [
            f"当前声明目标：{', '.join(declared_facts)}" if declared_facts else "当前声明目标：暂无明确声明",
            f"最近活跃项目：{', '.join(active_projects)}" if active_projects else "最近活跃项目：暂无明显活跃项目",
            f"最近证据：{', '.join(active_artifacts)}" if active_artifacts else "最近证据：暂无近期证据",
            f"活跃状态：{activity_status}",
        ]

        return DerivedProfile(
            generated_at=now.isoformat(),
            declared_facts=declared_facts,
            recent_projects=active_projects,
            recent_artifacts=active_artifacts,
            activity_status=activity_status,
            summary="\n".join(summary_lines),
        )

    def build_and_store_profile(
        self,
        recent_project_limit: int = 5,
        recent_artifact_limit: int = 10,
    ) -> DerivedProfileSnapshot:
        profile = self.build_profile(
            recent_project_limit=recent_project_limit,
            recent_artifact_limit=recent_artifact_limit,
        )
        return self.repository.create_profile_snapshot(
            DerivedProfileSnapshotCreate(
                generated_at=parse_timestamp(profile.generated_at)
                or datetime.now(timezone.utc),
                declared_facts=profile.declared_facts,
                recent_projects=profile.recent_projects,
                recent_artifacts=profile.recent_artifacts,
                activity_status=profile.activity_status,
                summary=profile.summary,
            )
        )

    def _render_declared_facts(self, facts: list[ProfileFact]) -> list[str]:
        rendered: list[str] = []
        for fact in facts:
            rendered.append(f"{fact.key}={fact.value}")
        return rendered

    def _project_activity_time(self, project: Project) -> datetime:
        return parse_timestamp(project.updated_at) or datetime.min.replace(tzinfo=timezone.utc)

    def _artifact_activity_time(self, artifact: Artifact) -> datetime:
        return (
            parse_timestamp(artifact.published_at)
            or parse_timestamp(artifact.updated_at)
            or parse_timestamp(artifact.created_at)
            or datetime.min.replace(tzinfo=timezone.utc)
        )

    def _build_activity_status(
        self,
        projects: list[Project],
        artifacts: list[Artifact],
        high_activity_cutoff: datetime,
        active_cutoff: datetime,
    ) -> str:
        most_recent_activity = max(
            [self._project_activity_time(project) for project in projects]
            + [self._artifact_activity_time(artifact) for artifact in artifacts]
            + [datetime.min.replace(tzinfo=timezone.utc)]
        )
        if most_recent_activity >= high_activity_cutoff:
            return "高活跃"
        if most_recent_activity >= active_cutoff:
            return "近期活跃"
        return "低活跃"
