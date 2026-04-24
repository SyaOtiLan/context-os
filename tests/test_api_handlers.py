from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from personal_agent.api import artifacts, health, notes, opportunities, ops, overview, policies, profile, projects, radar, tasks
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


def test_health_handler_returns_basic_status() -> None:
    response = health.health()

    assert response.ok is True
    assert response.app == "ContextOS"


def test_profile_handlers_round_trip() -> None:
    fact = profile.upsert_fact(
        ProfileFactCreate(category="career", key="target_role", value="backend")
    )
    preference = profile.add_preference(
        ProfilePreferenceCreate(area="jobs", value="backend-first")
    )
    summary = profile.summary()

    assert fact.key == "target_role"
    assert preference.area == "jobs"
    assert len(summary.facts) == 1
    assert len(summary.preferences) == 1


def test_profile_derived_handler_returns_summary() -> None:
    profile.upsert_fact(
        ProfileFactCreate(category="career", key="target_role", value="backend")
    )
    projects.upsert_project(ProjectCreate(slug="myagent", title="MyAgent"))
    artifacts.create_artifact(
        ArtifactCreate(
            artifact_type="repo",
            title="GitHub Repo",
            published_at=datetime.now(timezone.utc),
        )
    )

    derived = profile.derived_profile()

    assert "target_role=backend" in derived.declared_facts
    assert "myagent" in derived.recent_projects
    assert "GitHub Repo" in derived.recent_artifacts
    assert "活跃状态：" in derived.summary


def test_profile_derived_refresh_and_latest_handlers() -> None:
    profile.upsert_fact(
        ProfileFactCreate(category="career", key="target_role", value="backend")
    )

    refreshed = profile.refresh_derived_profile()
    latest = profile.latest_derived_profile()

    assert refreshed.id > 0
    assert latest is not None
    assert latest.id == refreshed.id
    assert "target_role=backend" in latest.declared_facts


def test_projects_and_artifacts_handlers_round_trip() -> None:
    project = projects.upsert_project(
        ProjectCreate(slug="myagent", title="MyAgent", metadata={"stage": "mvp"})
    )
    artifact = artifacts.create_artifact(
        ArtifactCreate(
            project_id=project.id,
            artifact_type="repo",
            title="GitHub Repo",
            url="https://github.com/example/myagent",
        )
    )

    listed_projects = projects.list_projects()
    listed_artifacts = artifacts.list_artifacts(project_id=project.id)

    assert listed_projects[0].slug == "myagent"
    assert artifact.project_id == project.id
    assert listed_artifacts[0].title == "GitHub Repo"


def test_notes_opportunities_and_tasks_handlers_round_trip() -> None:
    note = notes.create_note(NoteCreate(kind="daily", body="wired api handlers"))
    opportunity = opportunities.create_opportunity(
        OpportunityCreate(
            source="issueradar",
            kind="job",
            title="Backend Intern",
            tags=["backend"],
        )
    )
    task = tasks.create_task(
        TaskCreate(
            opportunity_id=opportunity.id,
            title="Evaluate and apply",
            status="todo",
            priority="high",
        )
    )

    listed_tasks = tasks.list_tasks(status="todo")

    assert note.kind == "daily"
    assert task.opportunity_id == opportunity.id
    assert listed_tasks[0].title == "Evaluate and apply"


def test_policies_handler_active_only_filters_effective_policies() -> None:
    now = datetime.now(timezone.utc)
    policies.create_policy(
        PolicyCreate(
            policy_type="throttle",
            scope="notifications",
            target="issueradar",
            value="disabled",
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
        )
    )
    policies.create_policy(
        PolicyCreate(
            policy_type="throttle",
            scope="notifications",
            target="future",
            value="disabled",
            starts_at=now + timedelta(hours=1),
        )
    )

    active = policies.list_policies(active_only=True)

    assert len(active) == 1
    assert active[0].target == "issueradar"


def test_overview_handler_builds_snapshot() -> None:
    profile.upsert_fact(
        ProfileFactCreate(category="career", key="target_role", value="backend")
    )
    projects.upsert_project(ProjectCreate(slug="myagent", title="MyAgent"))
    notes.create_note(NoteCreate(kind="daily", body="overview seed"))

    snapshot = overview.get_overview()

    assert snapshot.counts.projects == 1
    assert snapshot.counts.notes == 1
    assert snapshot.profile.facts[0].key == "target_role"
    assert snapshot.recent_projects[0].slug == "myagent"


def test_ops_handlers_create_and_probe_service() -> None:
    service = ops.create_service(
        ServiceCreate(
            name="issueradar",
            service_type="http",
            endpoint="https://example.com/health",
        )
    )
    original_get = ops.ops_service.session.get

    def fake_get(url: str, timeout: int, allow_redirects: bool) -> SimpleNamespace:
        return SimpleNamespace(status_code=200, url=url)

    ops.ops_service.session.get = fake_get  # type: ignore[method-assign]
    try:
        check = ops.probe_service(service.id)
        services = ops.list_services()
    finally:
        ops.ops_service.session.get = original_get  # type: ignore[method-assign]

    assert check.status == "up"
    assert services[0].status == "up"


def test_ops_add_service_check_handler() -> None:
    service = ops.create_service(
        ServiceCreate(
            name="issueradar",
            service_type="http",
            endpoint="https://example.com/health",
        )
    )

    check = ops.add_service_check(
        service.id,
        ServiceCheckCreate(
            status="up",
            checked_at=datetime.now(timezone.utc),
            message="HTTP 200",
            latency_ms=12,
            payload={"http_status": 200},
        ),
    )

    assert check.service_id == service.id
    assert check.status == "up"


def test_ops_probe_missing_service_raises_404() -> None:
    with pytest.raises(HTTPException) as exc_info:
        ops.probe_service(999)

    assert exc_info.value.status_code == 404


def test_ops_probe_all_skips_services_without_endpoint() -> None:
    ops.create_service(
        ServiceCreate(
            name="with-endpoint",
            service_type="http",
            endpoint="https://example.com/health",
        )
    )
    ops.create_service(ServiceCreate(name="without-endpoint", service_type="worker"))
    original_get = ops.ops_service.session.get

    def fake_get(url: str, timeout: int, allow_redirects: bool) -> SimpleNamespace:
        return SimpleNamespace(status_code=204, url=url)

    ops.ops_service.session.get = fake_get  # type: ignore[method-assign]
    try:
        checks = ops.probe_all_services()
    finally:
        ops.ops_service.session.get = original_get  # type: ignore[method-assign]

    assert len(checks) == 1
    assert checks[0].payload["service_name"] == "with-endpoint"


def test_ops_probe_handler_returns_404_for_service_without_endpoint() -> None:
    service = ops.create_service(
        ServiceCreate(
            name="no-endpoint",
            service_type="worker",
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        ops.probe_service(service.id)


def test_radar_handlers_sync_filter_and_list() -> None:
    class FakeGitHubClient:
        def fetch_open_issues(self, repo: str, label: str | None = None, since: datetime | None = None) -> list[dict]:
            payload = {
                "number": 101,
                "title": "Improve error message",
                "html_url": "https://github.com/example/repo/issues/101",
                "state": "open",
                "labels": [{"name": "good first issue"}],
                "assignees": [],
                "user": {"login": "alice"},
                "created_at": "2026-04-18T10:00:00Z",
                "updated_at": "2026-04-19T12:00:00Z",
                "body": "Please improve this error message.",
            }
            if label and label != "good first issue":
                return []
            return [payload]

    original_client = radar.sync_service.client
    radar.sync_service.client = FakeGitHubClient()  # type: ignore[assignment]
    try:
        sync_summary = radar.sync_issues(radar.GitHubIssueSyncRequest(repo="example/repo"))
        filter_summary = radar.apply_filters(radar.GitHubIssueFilterRequest(repo="example/repo"))
        views = radar.list_issue_views(repo="example/repo", eligible=True, analyzed=None, limit=20)
    finally:
        radar.sync_service.client = original_client  # type: ignore[assignment]

    assert sync_summary.created == 1
    assert filter_summary.eligible == 1
    assert len(views) == 1
    assert views[0].issue.issue_number == 101
    assert views[0].filter_result is not None


def test_radar_analyze_handler_uses_service_result() -> None:
    class FakeAnalysisService:
        def __init__(self, repository, profile_service) -> None:
            pass

        def analyze_eligible_issues(self, repo: str | None = None, limit: int | None = None, force: bool = False):
            return radar.GitHubIssueAnalyzeSummary(requested=1, analyzed=1, fallback_used=0)

    original_service = radar.IssueAnalysisService
    radar.IssueAnalysisService = FakeAnalysisService  # type: ignore[assignment]
    try:
        summary = radar.analyze_issues(radar.GitHubIssueAnalyzeRequest(repo="example/repo"))
    finally:
        radar.IssueAnalysisService = original_service  # type: ignore[assignment]

    assert summary.requested == 1
    assert summary.analyzed == 1


def test_radar_digest_and_mark_alerts_handlers() -> None:
    class FakeDigestService:
        def build_digest_sections(self, repo: str | None = None, lookback_days: int = 3, limit: int | None = None):
            return radar.RadarDigestSections(
                recommended=[],
                watchlist=[],
                screened_out=[],
                lookback_days=lookback_days,
                generated_at="2026-04-20T00:00:00+00:00",
            )

    class FakeNotificationService:
        def mark_new_issue_alerts(self, repo: str | None = None, limit: int | None = None) -> int:
            return 2

    original_digest_service = radar.digest_service
    original_notification_service = radar.notification_service
    radar.digest_service = FakeDigestService()  # type: ignore[assignment]
    radar.notification_service = FakeNotificationService()  # type: ignore[assignment]
    try:
        digest = radar.get_digest(repo="example/repo", lookback_days=5, limit=10)
        result = radar.mark_alerts(repo="example/repo", limit=5)
    finally:
        radar.digest_service = original_digest_service  # type: ignore[assignment]
        radar.notification_service = original_notification_service  # type: ignore[assignment]

    assert digest.lookback_days == 5
    assert result["sent"] == 2


def test_radar_run_pipeline_handler() -> None:
    class FakePipelineService:
        def __init__(self, **kwargs) -> None:
            pass

        def run(self, repo: str, analysis_limit: int | None = None, force_analysis: bool = False):
            return radar.RadarPipelineSummary(
                sync=radar.GitHubIssueSyncSummary(total_fetched=1, created=1, updated=0, skipped_pull_requests=0),
                filtering=radar.GitHubIssueFilterSummary(total=1, eligible=1, ineligible=0),
                analysis=radar.GitHubIssueAnalyzeSummary(requested=1, analyzed=1, fallback_used=0),
                digest_item_count=1,
            )

    original_pipeline_service = radar.RadarPipelineService
    radar.RadarPipelineService = FakePipelineService  # type: ignore[assignment]
    try:
        summary = radar.run_pipeline(radar.RadarPipelineRequest(repo="example/repo"))
    finally:
        radar.RadarPipelineService = original_pipeline_service  # type: ignore[assignment]

    assert summary.sync.created == 1
    assert summary.digest_item_count == 1
