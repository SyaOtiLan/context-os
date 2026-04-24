from __future__ import annotations

from datetime import datetime, timedelta, timezone

from personal_agent.models import GitHubIssueCreate, ProfileFactCreate
from personal_agent.services.github_issues import GitHubIssueSyncService
from personal_agent.services.issue_radar import (
    IssueAnalysisService,
    IssueFilterService,
    RadarDigestService,
    RadarNotificationService,
    RadarPipelineService,
)
from personal_agent.services.profile_derivation import ProfileDerivationService


class FakeGitHubClient:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = payloads

    def fetch_open_issues(self, repo: str, label: str | None = None, since: datetime | None = None) -> list[dict]:
        if label is None:
            return list(self.payloads)
        return [
            payload
            for payload in self.payloads
            if label in [item["name"] for item in payload.get("labels", [])]
        ]


class FakeLLMService:
    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int = 500) -> str:
        assert any("画像" in item["content"] for item in messages)
        return """
        {
          "fit_score": 8,
          "difficulty": "medium",
          "why_fit": "和当前画像贴近。",
          "why_not_fit": "暂无明显硬阻碍。",
          "likely_blockers": "需要先读仓库代码。",
          "first_step": "先复现 issue 并阅读相关模块。",
          "should_notify": true
        }
        """.strip()


def test_sync_open_issues_creates_issue_rows(repository) -> None:
    payloads = [
        {
            "number": 101,
            "title": "Improve error message",
            "html_url": "https://github.com/example/repo/issues/101",
            "state": "open",
            "labels": [{"name": "good first issue"}],
            "assignees": [],
            "user": {"login": "alice"},
            "created_at": "2026-04-18T10:00:00Z",
            "updated_at": "2026-04-19T12:00:00Z",
            "body": "This issue improves the error message.",
        }
    ]
    service = GitHubIssueSyncService(repository, FakeGitHubClient(payloads))

    summary = service.sync_open_issues("example/repo")
    issues = repository.list_github_issues(repo="example/repo", limit=0)

    assert summary.total_fetched == 1
    assert summary.created == 1
    assert issues[0].issue_number == 101
    assert issues[0].labels == ["good first issue"]


def test_apply_filters_marks_issue_as_eligible(repository) -> None:
    now = datetime.now(timezone.utc)
    repository.upsert_github_issue(
        GitHubIssueCreate(
            repo="example/repo",
            issue_number=101,
            title="Improve error message",
            url="https://github.com/example/repo/issues/101",
            state="open",
            labels=["good first issue"],
            assignees=[],
            author="alice",
            body="Please improve this error message and add tests.",
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=1),
            fetched_at=now,
        )
    )
    service = IssueFilterService(repository)

    summary = service.apply_filters(repo="example/repo")
    views = repository.list_github_issue_views(repo="example/repo", limit=0)

    assert summary.total == 1
    assert summary.eligible == 1
    assert views[0].filter_result is not None
    assert views[0].filter_result.eligible is True


def test_analyze_eligible_issues_writes_analysis(repository) -> None:
    now = datetime.now(timezone.utc)
    repository.upsert_profile_fact(
        ProfileFactCreate(
            category="career",
            key="target_role",
            value="backend",
        )
    )
    repository.upsert_github_issue(
        GitHubIssueCreate(
            repo="example/repo",
            issue_number=101,
            title="Improve error message",
            url="https://github.com/example/repo/issues/101",
            state="open",
            labels=["good first issue"],
            assignees=[],
            author="alice",
            body="Please improve this error message and add tests.",
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=1),
            fetched_at=now,
        )
    )
    filter_service = IssueFilterService(repository)
    filter_service.apply_filters(repo="example/repo")
    profile_service = ProfileDerivationService(repository)
    profile_service.build_and_store_profile()
    analysis_service = IssueAnalysisService(
        repository=repository,
        profile_service=profile_service,
        llm_service=FakeLLMService(),
    )

    summary = analysis_service.analyze_eligible_issues(repo="example/repo")
    views = repository.list_github_issue_views(repo="example/repo", limit=0)

    assert summary.requested == 1
    assert summary.analyzed == 1
    assert summary.fallback_used == 0
    assert views[0].analysis is not None
    assert views[0].analysis.fit_score == 8
    assert views[0].analysis.should_notify is True


def test_build_digest_sections_splits_recommended_and_screened_out(repository) -> None:
    now = datetime.now(timezone.utc)
    repository.upsert_github_issue(
        GitHubIssueCreate(
            repo="example/repo",
            issue_number=101,
            title="Improve error message",
            url="https://github.com/example/repo/issues/101",
            state="open",
            labels=["good first issue"],
            assignees=[],
            author="alice",
            body="Please improve this error message and add tests.",
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
            fetched_at=now,
        )
    )
    repository.upsert_github_issue(
        GitHubIssueCreate(
            repo="example/repo",
            issue_number=102,
            title="Massive distributed scheduler overhaul",
            url="https://github.com/example/repo/issues/102",
            state="open",
            labels=["good first issue"],
            assignees=["bob"],
            author="alice",
            body="Need a distributed scheduler overhaul.",
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
            fetched_at=now,
        )
    )
    repository.upsert_profile_fact(ProfileFactCreate(category="career", key="target_role", value="backend"))
    filter_service = IssueFilterService(repository)
    filter_service.apply_filters(repo="example/repo")
    profile_service = ProfileDerivationService(repository)
    profile_service.build_and_store_profile()
    analysis_service = IssueAnalysisService(
        repository=repository,
        profile_service=profile_service,
        llm_service=FakeLLMService(),
    )
    analysis_service.analyze_eligible_issues(repo="example/repo")

    digest = RadarDigestService(repository).build_digest_sections(repo="example/repo")

    assert len(digest.recommended) == 1
    assert digest.recommended[0].issue_number == 101
    assert len(digest.screened_out) == 1
    assert digest.screened_out[0].issue_number == 102


def test_mark_new_issue_alerts_deduplicates_notifications(repository) -> None:
    now = datetime.now(timezone.utc)
    repository.upsert_profile_fact(ProfileFactCreate(category="career", key="target_role", value="backend"))
    issue = repository.upsert_github_issue(
        GitHubIssueCreate(
            repo="example/repo",
            issue_number=101,
            title="Improve error message",
            url="https://github.com/example/repo/issues/101",
            state="open",
            labels=["good first issue"],
            assignees=[],
            author="alice",
            body="Please improve this error message and add tests.",
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
            fetched_at=now,
        )
    )
    IssueFilterService(repository).apply_filters(repo="example/repo")
    profile_service = ProfileDerivationService(repository)
    profile_service.build_and_store_profile()
    IssueAnalysisService(
        repository=repository,
        profile_service=profile_service,
        llm_service=FakeLLMService(),
    ).analyze_eligible_issues(repo="example/repo")

    notification_service = RadarNotificationService(repository)
    first = notification_service.mark_new_issue_alerts(repo="example/repo")
    second = notification_service.mark_new_issue_alerts(repo="example/repo")
    notifications = repository.list_github_issue_notifications(limit=0)

    assert first == 1
    assert second == 0
    assert notifications[0].issue_id == issue.id


def test_pipeline_runs_full_chain(repository) -> None:
    now = datetime.now(timezone.utc)
    payloads = [
        {
            "number": 101,
            "title": "Improve error message",
            "html_url": "https://github.com/example/repo/issues/101",
            "state": "open",
            "labels": [{"name": "good first issue"}],
            "assignees": [],
            "user": {"login": "alice"},
            "created_at": (now - timedelta(hours=2)).isoformat(),
            "updated_at": (now - timedelta(hours=1)).isoformat(),
            "body": "This issue improves the error message.",
        }
    ]
    repository.upsert_profile_fact(ProfileFactCreate(category="career", key="target_role", value="backend"))
    profile_service = ProfileDerivationService(repository)
    profile_service.build_and_store_profile()
    pipeline = RadarPipelineService(
        repository=repository,
        sync_service=GitHubIssueSyncService(repository, FakeGitHubClient(payloads)),
        filter_service=IssueFilterService(repository),
        analysis_service=IssueAnalysisService(
            repository=repository,
            profile_service=profile_service,
            llm_service=FakeLLMService(),
        ),
        digest_service=RadarDigestService(repository),
    )

    summary = pipeline.run(repo="example/repo")

    assert summary.sync.created == 1
    assert summary.filtering.eligible == 1
    assert summary.analysis.analyzed == 1
    assert summary.digest_item_count == 1
