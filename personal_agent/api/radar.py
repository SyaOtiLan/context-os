from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from personal_agent.models import (
    GitHubIssueAnalyzeRequest,
    GitHubIssueAnalyzeSummary,
    GitHubIssueFilterRequest,
    GitHubIssueFilterSummary,
    GitHubIssueSyncRequest,
    GitHubIssueSyncSummary,
    GitHubIssueView,
    RadarDigestSections,
    RadarPipelineRequest,
    RadarPipelineSummary,
)
from personal_agent.services.github_issues import GitHubIssueSyncService
from personal_agent.services.issue_radar import (
    IssueAnalysisService,
    IssueFilterService,
    RadarDigestService,
    RadarNotificationService,
    RadarPipelineService,
)
from personal_agent.services.llm import LLMNotConfiguredError
from personal_agent.services.profile_derivation import ProfileDerivationService
from personal_agent.services.repository import Repository


router = APIRouter(prefix="/radar", tags=["radar"])
repository = Repository()
profile_service = ProfileDerivationService(repository)
sync_service = GitHubIssueSyncService(repository)
filter_service = IssueFilterService(repository)
digest_service = RadarDigestService(repository)
notification_service = RadarNotificationService(repository)


@router.get("/issues", response_model=list[GitHubIssueView])
def list_issue_views(
    repo: str | None = None,
    eligible: bool | None = None,
    analyzed: bool | None = None,
    limit: int = Query(default=20, ge=0, le=200),
) -> list[GitHubIssueView]:
    return repository.list_github_issue_views(
        repo=repo,
        eligible=eligible,
        analyzed=analyzed,
        limit=limit,
    )


@router.post("/sync", response_model=GitHubIssueSyncSummary)
def sync_issues(payload: GitHubIssueSyncRequest) -> GitHubIssueSyncSummary:
    return sync_service.sync_open_issues(payload.repo)


@router.post("/filter", response_model=GitHubIssueFilterSummary)
def apply_filters(payload: GitHubIssueFilterRequest) -> GitHubIssueFilterSummary:
    return filter_service.apply_filters(repo=payload.repo)


@router.post("/analyze", response_model=GitHubIssueAnalyzeSummary)
def analyze_issues(payload: GitHubIssueAnalyzeRequest) -> GitHubIssueAnalyzeSummary:
    try:
        analysis_service = IssueAnalysisService(repository, profile_service)
        return analysis_service.analyze_eligible_issues(
            repo=payload.repo,
            limit=payload.limit,
            force=payload.force,
        )
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/digest", response_model=RadarDigestSections)
def get_digest(
    repo: str | None = None,
    lookback_days: int = Query(default=3, ge=1, le=30),
    limit: int | None = Query(default=None, ge=1, le=100),
) -> RadarDigestSections:
    return digest_service.build_digest_sections(
        repo=repo,
        lookback_days=lookback_days,
        limit=limit,
    )


@router.post("/run", response_model=RadarPipelineSummary)
def run_pipeline(payload: RadarPipelineRequest) -> RadarPipelineSummary:
    try:
        pipeline_service = RadarPipelineService(
            repository=repository,
            sync_service=sync_service,
            filter_service=filter_service,
            digest_service=digest_service,
        )
        return pipeline_service.run(
            repo=payload.repo,
            analysis_limit=payload.analysis_limit,
            force_analysis=payload.force_analysis,
        )
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/mark-alerts")
def mark_alerts(
    repo: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=100),
) -> dict[str, int]:
    sent = notification_service.mark_new_issue_alerts(repo=repo, limit=limit)
    return {"sent": sent}
