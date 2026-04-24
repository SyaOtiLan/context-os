from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    ok: bool
    app: str
    db_path: str


class ProfileFactCreate(BaseModel):
    category: str
    key: str
    value: str
    source: str | None = None
    confidence: float = 1.0


class ProfileFact(BaseModel):
    id: int
    category: str
    key: str
    value: str
    source: str | None = None
    confidence: float
    created_at: str
    updated_at: str


class ProfilePreferenceCreate(BaseModel):
    area: str
    value: str
    weight: float = 1.0
    rationale: str | None = None


class ProfilePreference(BaseModel):
    id: int
    area: str
    value: str
    weight: float
    rationale: str | None = None
    created_at: str
    updated_at: str


class ProfileSummary(BaseModel):
    facts: list[ProfileFact]
    preferences: list[ProfilePreference]


class DerivedProfile(BaseModel):
    generated_at: str
    declared_facts: list[str] = Field(default_factory=list)
    recent_projects: list[str] = Field(default_factory=list)
    recent_artifacts: list[str] = Field(default_factory=list)
    activity_status: str
    summary: str


class DerivedProfileSnapshotCreate(BaseModel):
    source: str = "rules"
    generated_at: datetime
    declared_facts: list[str] = Field(default_factory=list)
    recent_projects: list[str] = Field(default_factory=list)
    recent_artifacts: list[str] = Field(default_factory=list)
    activity_status: str
    summary: str


class DerivedProfileSnapshot(BaseModel):
    id: int
    source: str
    generated_at: str
    declared_facts: list[str] = Field(default_factory=list)
    recent_projects: list[str] = Field(default_factory=list)
    recent_artifacts: list[str] = Field(default_factory=list)
    activity_status: str
    summary: str
    created_at: str


class GitHubIssueCreate(BaseModel):
    repo: str
    issue_number: int
    title: str
    url: str
    state: str
    labels: list[str] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)
    author: str | None = None
    body: str = ""
    is_pull_request: bool = False
    created_at: datetime
    updated_at: datetime
    fetched_at: datetime


class GitHubIssue(BaseModel):
    id: int
    repo: str
    issue_number: int
    title: str
    url: str
    state: str
    labels: list[str] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)
    author: str | None = None
    body: str = ""
    is_pull_request: bool = False
    created_at: str
    updated_at: str
    fetched_at: str


class GitHubIssueFilterResultCreate(BaseModel):
    issue_id: int
    eligible: bool
    reason_codes: list[str] = Field(default_factory=list)
    evaluated_at: datetime


class GitHubIssueFilterResult(BaseModel):
    id: int
    issue_id: int
    eligible: bool
    reason_codes: list[str] = Field(default_factory=list)
    evaluated_at: str
    created_at: str


class GitHubIssueAnalysisPayload(BaseModel):
    fit_score: int
    difficulty: str
    why_fit: str
    why_not_fit: str
    likely_blockers: str
    first_step: str
    should_notify: bool


class GitHubIssueAnalysisCreate(BaseModel):
    issue_id: int
    fit_score: int
    difficulty: str
    why_fit: str
    why_not_fit: str
    likely_blockers: str
    first_step: str
    should_notify: bool
    provider: str
    model_name: str
    raw_response: str
    analyzed_at: datetime


class GitHubIssueAnalysis(BaseModel):
    id: int
    issue_id: int
    fit_score: int
    difficulty: str
    why_fit: str
    why_not_fit: str
    likely_blockers: str
    first_step: str
    should_notify: bool
    provider: str
    model_name: str
    raw_response: str
    analyzed_at: str
    created_at: str


class GitHubIssueNotificationCreate(BaseModel):
    issue_id: int
    notification_type: str
    subject: str
    sent_at: datetime


class GitHubIssueNotification(BaseModel):
    id: int
    issue_id: int
    notification_type: str
    subject: str
    sent_at: str
    created_at: str


class GitHubIssueView(BaseModel):
    issue: GitHubIssue
    filter_result: GitHubIssueFilterResult | None = None
    analysis: GitHubIssueAnalysis | None = None


class GitHubIssueSyncRequest(BaseModel):
    repo: str


class GitHubIssueSyncSummary(BaseModel):
    total_fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped_pull_requests: int = 0


class GitHubIssueFilterRequest(BaseModel):
    repo: str | None = None


class GitHubIssueFilterSummary(BaseModel):
    total: int = 0
    eligible: int = 0
    ineligible: int = 0


class GitHubIssueAnalyzeRequest(BaseModel):
    repo: str | None = None
    limit: int | None = None
    force: bool = False


class GitHubIssueAnalyzeSummary(BaseModel):
    requested: int = 0
    analyzed: int = 0
    fallback_used: int = 0


class RadarRecommendedItem(BaseModel):
    title: str
    repo: str
    issue_number: int
    labels: list[str] = Field(default_factory=list)
    fit_score: int
    difficulty: str
    why_fit: str
    likely_blockers: str
    first_step: str
    url: str


class RadarWatchItem(BaseModel):
    title: str
    repo: str
    issue_number: int
    labels: list[str] = Field(default_factory=list)
    fit_score: int
    difficulty: str
    why_fit: str
    why_not_fit: str
    url: str


class RadarScreenedOutItem(BaseModel):
    title: str
    repo: str
    issue_number: int
    labels: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    reason_labels: list[str] = Field(default_factory=list)
    url: str


class RadarDigestSections(BaseModel):
    recommended: list[RadarRecommendedItem] = Field(default_factory=list)
    watchlist: list[RadarWatchItem] = Field(default_factory=list)
    screened_out: list[RadarScreenedOutItem] = Field(default_factory=list)
    lookback_days: int
    generated_at: str


class RadarPipelineRequest(BaseModel):
    repo: str
    analysis_limit: int | None = None
    force_analysis: bool = False


class RadarPipelineSummary(BaseModel):
    sync: GitHubIssueSyncSummary
    filtering: GitHubIssueFilterSummary
    analysis: GitHubIssueAnalyzeSummary
    digest_item_count: int


class NoteCreate(BaseModel):
    kind: str = "note"
    title: str | None = None
    body: str
    source: str | None = None


class Note(BaseModel):
    id: int
    kind: str
    title: str | None = None
    body: str
    source: str | None = None
    created_at: str


class ProjectCreate(BaseModel):
    slug: str
    title: str
    kind: str = "project"
    status: str = "active"
    summary: str | None = None
    repo_url: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Project(BaseModel):
    id: int
    slug: str
    title: str
    kind: str
    status: str
    summary: str | None = None
    repo_url: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class ArtifactCreate(BaseModel):
    project_id: int | None = None
    artifact_type: str
    title: str
    url: str | None = None
    summary: str | None = None
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    published_at: datetime | None = None


class Artifact(BaseModel):
    id: int
    project_id: int | None = None
    artifact_type: str
    title: str
    url: str | None = None
    summary: str | None = None
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    published_at: str | None = None
    created_at: str
    updated_at: str


class OpportunityCreate(BaseModel):
    source: str
    kind: str
    title: str
    external_id: str | None = None
    url: str | None = None
    status: str = "open"
    rating_hint: int | None = None
    tags: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class Opportunity(BaseModel):
    id: int
    source: str
    kind: str
    title: str
    external_id: str | None = None
    url: str | None = None
    status: str
    rating_hint: int | None = None
    tags: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class TaskCreate(BaseModel):
    project_id: int | None = None
    opportunity_id: int | None = None
    kind: str = "task"
    title: str
    status: str = "todo"
    priority: str = "normal"
    due_at: datetime | None = None
    note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    id: int
    project_id: int | None = None
    opportunity_id: int | None = None
    kind: str
    title: str
    status: str
    priority: str
    due_at: str | None = None
    note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class PolicyCreate(BaseModel):
    policy_type: str
    scope: str
    target: str
    value: str
    rationale: str | None = None
    active: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Policy(BaseModel):
    id: int
    policy_type: str
    scope: str
    target: str
    value: str
    rationale: str | None = None
    active: bool
    starts_at: str | None = None
    ends_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class ServiceCreate(BaseModel):
    name: str
    service_type: str
    endpoint: str | None = None
    owner: str | None = None
    status: str = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ServiceCheckCreate(BaseModel):
    status: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str | None = None
    latency_ms: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class Service(BaseModel):
    id: int
    name: str
    service_type: str
    endpoint: str | None = None
    owner: str | None = None
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class ServiceCheck(BaseModel):
    id: int
    service_id: int
    status: str
    checked_at: str
    message: str | None = None
    latency_ms: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class OverviewCounts(BaseModel):
    profile_facts: int
    profile_preferences: int
    notes: int
    projects: int
    artifacts: int
    open_opportunities: int
    open_tasks: int
    active_policies: int
    services: int
    services_by_status: dict[str, int] = Field(default_factory=dict)


class OverviewSnapshot(BaseModel):
    generated_at: str
    counts: OverviewCounts
    profile: ProfileSummary
    recent_projects: list[Project] = Field(default_factory=list)
    recent_artifacts: list[Artifact] = Field(default_factory=list)
    recent_notes: list[Note] = Field(default_factory=list)
    recent_opportunities: list[Opportunity] = Field(default_factory=list)
    recent_tasks: list[Task] = Field(default_factory=list)
    active_policies: list[Policy] = Field(default_factory=list)
    services: list[Service] = Field(default_factory=list)
