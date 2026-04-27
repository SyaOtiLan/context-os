from __future__ import annotations

from personal_agent.models import (
    GitHubIssueAnalyzeSummary,
    GitHubIssueFilterSummary,
    GitHubIssueSyncSummary,
    NotificationOutboxCreate,
    RadarPipelineSummary,
)
from personal_agent.services.repository import Repository
from scripts import run_radar_job


class FakePipelineService:
    def run(
        self,
        repo: str,
        analysis_limit: int | None = None,
        force_analysis: bool = False,
    ) -> RadarPipelineSummary:
        assert repo == "example/repo"
        assert analysis_limit == 2
        assert force_analysis is True
        return RadarPipelineSummary(
            sync=GitHubIssueSyncSummary(total_fetched=3, created=2, updated=1),
            filtering=GitHubIssueFilterSummary(total=3, eligible=2, ineligible=1),
            analysis=GitHubIssueAnalyzeSummary(requested=2, analyzed=2, fallback_used=0),
            digest_item_count=2,
        )


class FakeOutboxService:
    def __init__(self) -> None:
        self.repository = Repository()

    def enqueue_digest(
        self,
        repo: str | None = None,
        lookback_days: int = 3,
        limit: int | None = None,
    ):
        assert repo == "example/repo"
        assert lookback_days == 7
        assert limit == 5
        return self.repository.create_notification_outbox_item(
            NotificationOutboxCreate(
                channel="email",
                subject="Digest",
                body="Body",
            )
        )


class FakeSender:
    def send_pending(self, limit: int = 20) -> int:
        assert limit == 9
        return 1


def test_run_radar_job_runs_pipeline_and_queues_digest(monkeypatch, capsys) -> None:
    monkeypatch.setattr(run_radar_job, "RadarPipelineService", FakePipelineService)
    monkeypatch.setattr(run_radar_job, "RadarOutboxService", FakeOutboxService)

    exit_code = run_radar_job.main(
        [
            "--repo",
            "example/repo",
            "--analysis-limit",
            "2",
            "--force-analysis",
            "--lookback-days",
            "7",
            "--digest-limit",
            "5",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "pipeline:" in output
    assert "queued:" in output
    assert "sent=" not in output


def test_run_radar_job_can_send_after_queueing(monkeypatch, capsys) -> None:
    monkeypatch.setattr(run_radar_job, "RadarPipelineService", FakePipelineService)
    monkeypatch.setattr(run_radar_job, "RadarOutboxService", FakeOutboxService)
    monkeypatch.setattr(run_radar_job, "SMTPNotificationSender", lambda: FakeSender())

    exit_code = run_radar_job.main(
        [
            "--repo",
            "example/repo",
            "--analysis-limit",
            "2",
            "--force-analysis",
            "--lookback-days",
            "7",
            "--digest-limit",
            "5",
            "--send",
            "--send-limit",
            "9",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "sent=1" in output
