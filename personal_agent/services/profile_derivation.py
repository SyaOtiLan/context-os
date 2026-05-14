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
from personal_agent.services.llm import LLMNotConfiguredError, LLMService
from personal_agent.services.repository import Repository
from personal_agent.time_utils import parse_timestamp


RULE_SUMMARY_PREFIXES = ("当前声明目标：",)


class ProfileDerivationService:
    def __init__(
        self,
        repository: Repository | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        self.repository = repository or Repository()
        self.llm_service = llm_service

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

        fallback_summary = self._build_rule_summary(
            declared_facts,
            active_projects,
            active_artifacts,
            activity_status,
        )
        summary = self._build_llm_summary(
            facts=facts,
            projects=recent_projects,
            artifacts=recent_artifacts,
            activity_status=activity_status,
            fallback_summary=fallback_summary,
        )

        return DerivedProfile(
            generated_at=now.isoformat(),
            declared_facts=declared_facts,
            recent_projects=active_projects,
            recent_artifacts=active_artifacts,
            activity_status=activity_status,
            summary=summary,
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
                source=self._summary_source(profile.summary),
                generated_at=parse_timestamp(profile.generated_at)
                or datetime.now(timezone.utc),
                declared_facts=profile.declared_facts,
                recent_projects=profile.recent_projects,
                recent_artifacts=profile.recent_artifacts,
                activity_status=profile.activity_status,
                summary=profile.summary,
            )
        )

    def _summary_source(self, summary: str) -> str:
        return "rules" if summary.startswith(RULE_SUMMARY_PREFIXES) else "llm"

    def _render_declared_facts(self, facts: list[ProfileFact]) -> list[str]:
        rendered: list[str] = []
        for fact in facts:
            rendered.append(f"{fact.key}={fact.value}")
        return rendered

    def _build_rule_summary(
        self,
        declared_facts: list[str],
        active_projects: list[str],
        active_artifacts: list[str],
        activity_status: str,
    ) -> str:
        summary_lines = [
            f"当前声明目标：{', '.join(declared_facts)}" if declared_facts else "当前声明目标：暂无明确声明",
            f"最近活跃项目：{', '.join(active_projects)}" if active_projects else "最近活跃项目：暂无明显活跃项目",
            f"最近证据：{', '.join(active_artifacts)}" if active_artifacts else "最近证据：暂无近期证据",
            f"活跃状态：{activity_status}",
        ]
        return "\n".join(summary_lines)

    def _build_llm_summary(
        self,
        facts: list[ProfileFact],
        projects: list[Project],
        artifacts: list[Artifact],
        activity_status: str,
        fallback_summary: str,
    ) -> str:
        try:
            llm = self.llm_service or LLMService()
        except LLMNotConfiguredError:
            return fallback_summary

        try:
            summary = llm.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "You generate a concise derived profile for GitHub issue matching. "
                            "Use only the reviewed facts, projects, and artifacts provided by the user. "
                            "Do not invent facts. Write in Chinese. Return plain text only."
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._render_summary_prompt(
                            facts=facts,
                            projects=projects,
                            artifacts=artifacts,
                            activity_status=activity_status,
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=700,
            )
        except Exception:
            return fallback_summary

        return summary.strip() or fallback_summary

    def _render_summary_prompt(
        self,
        facts: list[ProfileFact],
        projects: list[Project],
        artifacts: list[Artifact],
        activity_status: str,
    ) -> str:
        fact_lines = [
            f"- {fact.category}.{fact.key}: {fact.value} (source={fact.source or 'unknown'}, confidence={fact.confidence:.2f})"
            for fact in facts
        ]
        project_lines = [
            f"- {project.slug}: title={project.title}, kind={project.kind}, status={project.status}, summary={project.summary or 'none'}"
            for project in projects
        ]
        artifact_lines = [
            f"- {artifact.title}: type={artifact.artifact_type}, source={artifact.source or 'unknown'}, summary={artifact.summary or 'none'}"
            for artifact in artifacts
        ]
        return f"""
Generate a derived profile summary for a GitHub issue recommendation system.

Requirements:
- Use only the reviewed data below.
- Do not mention unsupported claims.
- Focus on issue matching, not biography writing.
- Include 4 to 6 concise bullet points.
- Cover background, technical base, current goals, relevant projects, suitable issue types, and unsuitable issue types when supported.
- If information is missing, omit that part instead of guessing.

Reviewed facts:
{chr(10).join(fact_lines) if fact_lines else "- none"}

Reviewed projects:
{chr(10).join(project_lines) if project_lines else "- none"}

Reviewed artifacts:
{chr(10).join(artifact_lines) if artifact_lines else "- none"}

Activity status: {activity_status}
""".strip()

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
