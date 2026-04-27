from __future__ import annotations

import json
from datetime import datetime, timezone
from sqlite3 import Row

from personal_agent.db import get_connection
from personal_agent.models import (
    Artifact,
    ArtifactCreate,
    DerivedProfileSnapshot,
    DerivedProfileSnapshotCreate,
    ExtractionCandidate,
    ExtractionCandidateCreate,
    GitHubIssue,
    GitHubIssueAnalysis,
    GitHubIssueAnalysisCreate,
    GitHubIssueCreate,
    GitHubIssueFilterResult,
    GitHubIssueFilterResultCreate,
    GitHubIssueNotification,
    GitHubIssueNotificationCreate,
    GitHubIssueView,
    Note,
    NoteCreate,
    NotificationOutboxCreate,
    NotificationOutboxItem,
    Opportunity,
    OpportunityCreate,
    Policy,
    PolicyCreate,
    Project,
    ProjectCreate,
    ProfileFact,
    ProfileFactCreate,
    ProfilePreference,
    ProfilePreferenceCreate,
    RawEvidence,
    RawEvidenceCreate,
    Service,
    ServiceCheck,
    ServiceCheckCreate,
    ServiceCreate,
    Task,
    TaskCreate,
)
from personal_agent.time_utils import parse_timestamp, serialize_timestamp


class RepositoryNotFoundError(LookupError):
    pass


_CLOSED_OPPORTUNITY_STATUSES = {
    "closed",
    "done",
    "completed",
    "ignored",
    "archived",
    "rejected",
}
_CLOSED_TASK_STATUSES = {
    "done",
    "completed",
    "cancelled",
    "canceled",
    "closed",
    "archived",
}


def _json_loads(value: str | None) -> dict | list:
    if not value:
        return {}
    return json.loads(value)


def _json_loads_list(value: str | None) -> list[str]:
    loaded = _json_loads(value)
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded]


def _require_row(row: Row | None, entity: str, identifier: object) -> Row:
    if row is None:
        raise RepositoryNotFoundError(f"{entity} '{identifier}' not found")
    return row


def _is_effectively_open(status: str | None, closed_statuses: set[str]) -> bool:
    normalized = (status or "").strip().lower()
    return normalized not in closed_statuses


def _is_policy_in_effect(policy: Policy, now: datetime | None = None) -> bool:
    if not policy.active:
        return False

    current_time = now or datetime.now(timezone.utc)
    starts_at = parse_timestamp(policy.starts_at)
    ends_at = parse_timestamp(policy.ends_at)

    if starts_at and starts_at > current_time:
        return False
    if ends_at and ends_at < current_time:
        return False
    return True


def _row_to_profile_fact(row: Row) -> ProfileFact:
    return ProfileFact(**dict(row))


def _row_to_preference(row: Row) -> ProfilePreference:
    return ProfilePreference(**dict(row))


def _row_to_raw_evidence(row: Row) -> RawEvidence:
    data = dict(row)
    data["metadata"] = _json_loads(data.pop("metadata_json")) or {}
    return RawEvidence(**data)


def _row_to_extraction_candidate(row: Row) -> ExtractionCandidate:
    data = dict(row)
    data["payload"] = _json_loads(data.pop("payload_json")) or {}
    return ExtractionCandidate(**data)


def _row_to_note(row: Row) -> Note:
    return Note(**dict(row))


def _row_to_github_issue(row: Row) -> GitHubIssue:
    data = dict(row)
    data["labels"] = _json_loads_list(data.pop("labels_json"))
    data["assignees"] = _json_loads_list(data.pop("assignees_json"))
    data["is_pull_request"] = bool(data["is_pull_request"])
    return GitHubIssue(**data)


def _row_to_github_issue_filter_result(row: Row) -> GitHubIssueFilterResult:
    data = dict(row)
    data["eligible"] = bool(data["eligible"])
    data["reason_codes"] = _json_loads_list(data.pop("reason_codes_json"))
    return GitHubIssueFilterResult(**data)


def _row_to_github_issue_analysis(row: Row) -> GitHubIssueAnalysis:
    data = dict(row)
    data["should_notify"] = bool(data["should_notify"])
    return GitHubIssueAnalysis(**data)


def _row_to_github_issue_notification(row: Row) -> GitHubIssueNotification:
    return GitHubIssueNotification(**dict(row))


def _row_to_notification_outbox_item(row: Row) -> NotificationOutboxItem:
    data = dict(row)
    data["payload"] = _json_loads(data.pop("payload_json")) or {}
    return NotificationOutboxItem(**data)


def _row_to_profile_snapshot(row: Row) -> DerivedProfileSnapshot:
    data = dict(row)
    data["declared_facts"] = _json_loads_list(data.pop("declared_facts_json"))
    data["recent_projects"] = _json_loads_list(data.pop("recent_projects_json"))
    data["recent_artifacts"] = _json_loads_list(data.pop("recent_artifacts_json"))
    return DerivedProfileSnapshot(**data)


def _row_to_project(row: Row) -> Project:
    data = dict(row)
    data["metadata"] = _json_loads(data.pop("metadata_json")) or {}
    return Project(**data)


def _row_to_artifact(row: Row) -> Artifact:
    data = dict(row)
    data["metadata"] = _json_loads(data.pop("metadata_json")) or {}
    return Artifact(**data)


def _row_to_opportunity(row: Row) -> Opportunity:
    data = dict(row)
    data["tags"] = _json_loads_list(data.pop("tags_json"))
    data["payload"] = _json_loads(data.pop("payload_json")) or {}
    return Opportunity(**data)


def _row_to_task(row: Row) -> Task:
    data = dict(row)
    data["metadata"] = _json_loads(data.pop("metadata_json")) or {}
    return Task(**data)


def _row_to_policy(row: Row) -> Policy:
    data = dict(row)
    data["metadata"] = _json_loads(data.pop("metadata_json")) or {}
    data["active"] = bool(data["active"])
    return Policy(**data)


def _row_to_service(row: Row) -> Service:
    data = dict(row)
    data["metadata"] = _json_loads(data.pop("metadata_json")) or {}
    return Service(**data)


def _row_to_service_check(row: Row) -> ServiceCheck:
    data = dict(row)
    data["payload"] = _json_loads(data.pop("payload_json")) or {}
    return ServiceCheck(**data)


class Repository:
    def create_raw_evidence(self, payload: RawEvidenceCreate) -> RawEvidence:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO raw_evidence (source_type, source_uri, content, metadata_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    payload.source_type,
                    payload.source_uri,
                    payload.content,
                    json.dumps(payload.metadata),
                ),
            )
            row = connection.execute(
                "SELECT * FROM raw_evidence WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return _row_to_raw_evidence(row)

    def list_raw_evidence(self, limit: int = 20) -> list[RawEvidence]:
        query = "SELECT * FROM raw_evidence ORDER BY created_at DESC, id DESC"
        params: tuple[object, ...] = ()
        if limit:
            query += " LIMIT ?"
            params = (limit,)
        with get_connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_raw_evidence(row) for row in rows]

    def get_raw_evidence(self, evidence_id: int) -> RawEvidence | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM raw_evidence WHERE id = ?",
                (evidence_id,),
            ).fetchone()
        return _row_to_raw_evidence(row) if row else None

    def get_raw_evidence_by_source(
        self,
        source_type: str,
        source_uri: str,
    ) -> RawEvidence | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM raw_evidence
                WHERE source_type = ? AND source_uri = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (source_type, source_uri),
            ).fetchone()
        return _row_to_raw_evidence(row) if row else None

    def create_extraction_candidate(
        self,
        payload: ExtractionCandidateCreate,
    ) -> ExtractionCandidate:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO extraction_candidates (
                    raw_evidence_id, kind, payload_json, confidence, reason, evidence_quote
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.raw_evidence_id,
                    payload.kind,
                    json.dumps(payload.payload),
                    payload.confidence,
                    payload.reason,
                    payload.evidence_quote,
                ),
            )
            row = connection.execute(
                "SELECT * FROM extraction_candidates WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return _row_to_extraction_candidate(row)

    def get_extraction_candidate(
        self,
        candidate_id: int,
    ) -> ExtractionCandidate | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM extraction_candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()
        return _row_to_extraction_candidate(row) if row else None

    def list_extraction_candidates(
        self,
        status: str | None = None,
        kind: str | None = None,
        raw_evidence_id: int | None = None,
        limit: int = 50,
    ) -> list[ExtractionCandidate]:
        query = "SELECT * FROM extraction_candidates"
        conditions: list[str] = []
        params: list[object] = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if kind:
            conditions.append("kind = ?")
            params.append(kind)
        if raw_evidence_id is not None:
            conditions.append("raw_evidence_id = ?")
            params.append(raw_evidence_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC, id DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        with get_connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [_row_to_extraction_candidate(row) for row in rows]

    def mark_extraction_candidate_applied(
        self,
        candidate_id: int,
        entity_type: str,
        entity_id: int,
    ) -> ExtractionCandidate:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE extraction_candidates
                SET status = 'applied',
                    applied_entity_type = ?,
                    applied_entity_id = ?,
                    applied_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (entity_type, entity_id, candidate_id),
            )
            row = connection.execute(
                "SELECT * FROM extraction_candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()
        return _row_to_extraction_candidate(row)

    def reject_extraction_candidate(self, candidate_id: int) -> ExtractionCandidate:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE extraction_candidates
                SET status = 'rejected',
                    rejected_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (candidate_id,),
            )
            row = connection.execute(
                "SELECT * FROM extraction_candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()
        return _row_to_extraction_candidate(row)

    def upsert_github_issue(self, payload: GitHubIssueCreate) -> GitHubIssue:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO github_issues (
                    repo, issue_number, title, url, state, labels_json, assignees_json,
                    author, body, is_pull_request, created_at, updated_at, fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(repo, issue_number) DO UPDATE SET
                    title = excluded.title,
                    url = excluded.url,
                    state = excluded.state,
                    labels_json = excluded.labels_json,
                    assignees_json = excluded.assignees_json,
                    author = excluded.author,
                    body = excluded.body,
                    is_pull_request = excluded.is_pull_request,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    fetched_at = excluded.fetched_at
                """,
                (
                    payload.repo,
                    payload.issue_number,
                    payload.title,
                    payload.url,
                    payload.state,
                    json.dumps(payload.labels),
                    json.dumps(payload.assignees),
                    payload.author,
                    payload.body,
                    int(payload.is_pull_request),
                    serialize_timestamp(payload.created_at),
                    serialize_timestamp(payload.updated_at),
                    serialize_timestamp(payload.fetched_at),
                ),
            )
            row = connection.execute(
                "SELECT * FROM github_issues WHERE repo = ? AND issue_number = ?",
                (payload.repo, payload.issue_number),
            ).fetchone()
        return _row_to_github_issue(row)

    def list_github_issues(
        self, repo: str | None = None, limit: int = 20
    ) -> list[GitHubIssue]:
        query = "SELECT * FROM github_issues"
        params: tuple[object, ...] = ()
        if repo:
            query += " WHERE repo = ?"
            params = (repo,)
        query += " ORDER BY updated_at DESC, id DESC"
        if limit:
            query += " LIMIT ?"
            params = (*params, limit)
        with get_connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_github_issue(row) for row in rows]

    def get_github_issue(self, issue_id: int) -> GitHubIssue | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM github_issues WHERE id = ?",
                (issue_id,),
            ).fetchone()
        return _row_to_github_issue(row) if row else None

    def upsert_github_issue_filter_result(
        self,
        payload: GitHubIssueFilterResultCreate,
    ) -> GitHubIssueFilterResult:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO github_issue_filter_results (issue_id, eligible, reason_codes_json, evaluated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(issue_id) DO UPDATE SET
                    eligible = excluded.eligible,
                    reason_codes_json = excluded.reason_codes_json,
                    evaluated_at = excluded.evaluated_at
                """,
                (
                    payload.issue_id,
                    int(payload.eligible),
                    json.dumps(payload.reason_codes),
                    serialize_timestamp(payload.evaluated_at),
                ),
            )
            row = connection.execute(
                "SELECT * FROM github_issue_filter_results WHERE issue_id = ?",
                (payload.issue_id,),
            ).fetchone()
        return _row_to_github_issue_filter_result(row)

    def upsert_github_issue_analysis(
        self,
        payload: GitHubIssueAnalysisCreate,
    ) -> GitHubIssueAnalysis:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO github_issue_analyses (
                    issue_id, fit_score, difficulty, why_fit, why_not_fit,
                    likely_blockers, first_step, should_notify, provider, model_name,
                    raw_response, analyzed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(issue_id) DO UPDATE SET
                    fit_score = excluded.fit_score,
                    difficulty = excluded.difficulty,
                    why_fit = excluded.why_fit,
                    why_not_fit = excluded.why_not_fit,
                    likely_blockers = excluded.likely_blockers,
                    first_step = excluded.first_step,
                    should_notify = excluded.should_notify,
                    provider = excluded.provider,
                    model_name = excluded.model_name,
                    raw_response = excluded.raw_response,
                    analyzed_at = excluded.analyzed_at
                """,
                (
                    payload.issue_id,
                    payload.fit_score,
                    payload.difficulty,
                    payload.why_fit,
                    payload.why_not_fit,
                    payload.likely_blockers,
                    payload.first_step,
                    int(payload.should_notify),
                    payload.provider,
                    payload.model_name,
                    payload.raw_response,
                    serialize_timestamp(payload.analyzed_at),
                ),
            )
            row = connection.execute(
                "SELECT * FROM github_issue_analyses WHERE issue_id = ?",
                (payload.issue_id,),
            ).fetchone()
        return _row_to_github_issue_analysis(row)

    def create_github_issue_notification(
        self,
        payload: GitHubIssueNotificationCreate,
    ) -> GitHubIssueNotification:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO github_issue_notifications (issue_id, notification_type, subject, sent_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(issue_id, notification_type) DO UPDATE SET
                    subject = excluded.subject,
                    sent_at = excluded.sent_at
                """,
                (
                    payload.issue_id,
                    payload.notification_type,
                    payload.subject,
                    serialize_timestamp(payload.sent_at),
                ),
            )
            row = connection.execute(
                """
                SELECT * FROM github_issue_notifications
                WHERE issue_id = ? AND notification_type = ?
                """,
                (payload.issue_id, payload.notification_type),
            ).fetchone()
        return _row_to_github_issue_notification(row)

    def list_github_issue_notifications(
        self,
        notification_type: str | None = None,
        limit: int = 20,
    ) -> list[GitHubIssueNotification]:
        query = "SELECT * FROM github_issue_notifications"
        params: tuple[object, ...] = ()
        if notification_type:
            query += " WHERE notification_type = ?"
            params = (notification_type,)
        query += " ORDER BY sent_at DESC, id DESC"
        if limit:
            query += " LIMIT ?"
            params = (*params, limit)
        with get_connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_github_issue_notification(row) for row in rows]

    def create_notification_outbox_item(
        self,
        payload: NotificationOutboxCreate,
    ) -> NotificationOutboxItem:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO notification_outbox (channel, subject, body, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    payload.channel,
                    payload.subject,
                    payload.body,
                    json.dumps(payload.payload),
                ),
            )
            row = connection.execute(
                "SELECT * FROM notification_outbox WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return _row_to_notification_outbox_item(row)

    def list_notification_outbox_items(
        self,
        status: str | None = None,
        channel: str | None = None,
        limit: int = 20,
    ) -> list[NotificationOutboxItem]:
        query = "SELECT * FROM notification_outbox"
        conditions: list[str] = []
        params: list[object] = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if channel:
            conditions.append("channel = ?")
            params.append(channel)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at ASC, id ASC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        with get_connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [_row_to_notification_outbox_item(row) for row in rows]

    def mark_notification_outbox_sent(
        self,
        item_id: int,
        sent_at: datetime,
    ) -> NotificationOutboxItem:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE notification_outbox
                SET status = 'sent',
                    sent_at = ?,
                    error = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (serialize_timestamp(sent_at), item_id),
            )
            row = connection.execute(
                "SELECT * FROM notification_outbox WHERE id = ?",
                (item_id,),
            ).fetchone()
        return _row_to_notification_outbox_item(_require_row(row, "notification_outbox", item_id))

    def mark_notification_outbox_failed(
        self,
        item_id: int,
        error: str,
    ) -> NotificationOutboxItem:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE notification_outbox
                SET status = 'failed',
                    error = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (error, item_id),
            )
            row = connection.execute(
                "SELECT * FROM notification_outbox WHERE id = ?",
                (item_id,),
            ).fetchone()
        return _row_to_notification_outbox_item(_require_row(row, "notification_outbox", item_id))

    def list_github_issue_views(
        self,
        repo: str | None = None,
        eligible: bool | None = None,
        analyzed: bool | None = None,
        limit: int = 20,
    ) -> list[GitHubIssueView]:
        query = """
            SELECT
                i.id AS issue_id,
                i.repo,
                i.issue_number,
                i.title,
                i.url,
                i.state,
                i.labels_json,
                i.assignees_json,
                i.author,
                i.body,
                i.is_pull_request,
                i.created_at,
                i.updated_at,
                i.fetched_at,
                f.id AS filter_id,
                f.eligible AS filter_eligible,
                f.reason_codes_json AS filter_reason_codes_json,
                f.evaluated_at AS filter_evaluated_at,
                f.created_at AS filter_created_at,
                a.id AS analysis_id,
                a.fit_score,
                a.difficulty,
                a.why_fit,
                a.why_not_fit,
                a.likely_blockers,
                a.first_step,
                a.should_notify,
                a.provider,
                a.model_name,
                a.raw_response,
                a.analyzed_at,
                a.created_at AS analysis_created_at
            FROM github_issues i
            LEFT JOIN github_issue_filter_results f ON f.issue_id = i.id
            LEFT JOIN github_issue_analyses a ON a.issue_id = i.id
        """
        conditions: list[str] = []
        params: list[object] = []
        if repo:
            conditions.append("i.repo = ?")
            params.append(repo)
        if eligible is not None:
            conditions.append("f.eligible = ?")
            params.append(int(eligible))
        if analyzed is True:
            conditions.append("a.id IS NOT NULL")
        elif analyzed is False:
            conditions.append("a.id IS NULL")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY i.updated_at DESC, i.id DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        with get_connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()

        views: list[GitHubIssueView] = []
        for row in rows:
            issue = GitHubIssue(
                id=row["issue_id"],
                repo=row["repo"],
                issue_number=row["issue_number"],
                title=row["title"],
                url=row["url"],
                state=row["state"],
                labels=_json_loads_list(row["labels_json"]),
                assignees=_json_loads_list(row["assignees_json"]),
                author=row["author"],
                body=row["body"],
                is_pull_request=bool(row["is_pull_request"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                fetched_at=row["fetched_at"],
            )
            filter_result = None
            if row["filter_id"] is not None:
                filter_result = GitHubIssueFilterResult(
                    id=row["filter_id"],
                    issue_id=row["issue_id"],
                    eligible=bool(row["filter_eligible"]),
                    reason_codes=_json_loads_list(row["filter_reason_codes_json"]),
                    evaluated_at=row["filter_evaluated_at"],
                    created_at=row["filter_created_at"],
                )
            analysis = None
            if row["analysis_id"] is not None:
                analysis = GitHubIssueAnalysis(
                    id=row["analysis_id"],
                    issue_id=row["issue_id"],
                    fit_score=row["fit_score"],
                    difficulty=row["difficulty"],
                    why_fit=row["why_fit"],
                    why_not_fit=row["why_not_fit"],
                    likely_blockers=row["likely_blockers"],
                    first_step=row["first_step"],
                    should_notify=bool(row["should_notify"]),
                    provider=row["provider"],
                    model_name=row["model_name"],
                    raw_response=row["raw_response"],
                    analyzed_at=row["analyzed_at"],
                    created_at=row["analysis_created_at"],
                )
            views.append(
                GitHubIssueView(
                    issue=issue,
                    filter_result=filter_result,
                    analysis=analysis,
                )
            )
        return views

    def create_profile_snapshot(
        self, payload: DerivedProfileSnapshotCreate
    ) -> DerivedProfileSnapshot:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO profile_snapshots (
                    source, generated_at, declared_facts_json, recent_projects_json,
                    recent_artifacts_json, activity_status, summary
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.source,
                    serialize_timestamp(payload.generated_at),
                    json.dumps(payload.declared_facts),
                    json.dumps(payload.recent_projects),
                    json.dumps(payload.recent_artifacts),
                    payload.activity_status,
                    payload.summary,
                ),
            )
            row = connection.execute(
                "SELECT * FROM profile_snapshots WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return _row_to_profile_snapshot(row)

    def get_latest_profile_snapshot(self) -> DerivedProfileSnapshot | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM profile_snapshots ORDER BY generated_at DESC, id DESC LIMIT 1"
            ).fetchone()
        return _row_to_profile_snapshot(row) if row else None

    def upsert_project(self, payload: ProjectCreate) -> Project:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO projects (
                    slug, title, kind, status, summary, repo_url, started_at, ended_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    title = excluded.title,
                    kind = excluded.kind,
                    status = excluded.status,
                    summary = excluded.summary,
                    repo_url = excluded.repo_url,
                    started_at = excluded.started_at,
                    ended_at = excluded.ended_at,
                    metadata_json = excluded.metadata_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    payload.slug,
                    payload.title,
                    payload.kind,
                    payload.status,
                    payload.summary,
                    payload.repo_url,
                    serialize_timestamp(payload.started_at),
                    serialize_timestamp(payload.ended_at),
                    json.dumps(payload.metadata),
                ),
            )
            row = connection.execute(
                "SELECT * FROM projects WHERE slug = ?",
                (payload.slug,),
            ).fetchone()
        return _row_to_project(row)

    def list_projects(self) -> list[Project]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        return [_row_to_project(row) for row in rows]

    def get_project_by_slug(self, slug: str) -> Project | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE slug = ?",
                (slug,),
            ).fetchone()
        return _row_to_project(row) if row else None

    def list_recent_projects(self, limit: int = 5) -> list[Project]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_project(row) for row in rows]

    def create_artifact(self, payload: ArtifactCreate) -> Artifact:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO artifacts (
                    project_id, artifact_type, title, url, summary, source, metadata_json, published_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.project_id,
                    payload.artifact_type,
                    payload.title,
                    payload.url,
                    payload.summary,
                    payload.source,
                    json.dumps(payload.metadata),
                    serialize_timestamp(payload.published_at),
                ),
            )
            row = connection.execute(
                "SELECT * FROM artifacts WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return _row_to_artifact(row)

    def list_artifacts(self, project_id: int | None = None) -> list[Artifact]:
        query = "SELECT * FROM artifacts"
        params: tuple = ()
        if project_id is not None:
            query += " WHERE project_id = ?"
            params = (project_id,)
        query += (
            " ORDER BY COALESCE(published_at, updated_at, created_at) DESC, id DESC"
        )
        with get_connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_artifact(row) for row in rows]

    def list_recent_artifacts(self, limit: int = 5) -> list[Artifact]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM artifacts
                ORDER BY COALESCE(published_at, updated_at, created_at) DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_row_to_artifact(row) for row in rows]

    def upsert_profile_fact(self, payload: ProfileFactCreate) -> ProfileFact:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO profile_facts (category, key, value, source, confidence)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(category, key) DO UPDATE SET
                    value = excluded.value,
                    source = excluded.source,
                    confidence = excluded.confidence,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    payload.category,
                    payload.key,
                    payload.value,
                    payload.source,
                    payload.confidence,
                ),
            )
            row = connection.execute(
                "SELECT * FROM profile_facts WHERE category = ? AND key = ?",
                (payload.category, payload.key),
            ).fetchone()
        return _row_to_profile_fact(row)

    def add_profile_preference(
        self, payload: ProfilePreferenceCreate
    ) -> ProfilePreference:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO profile_preferences (area, value, weight, rationale)
                VALUES (?, ?, ?, ?)
                """,
                (payload.area, payload.value, payload.weight, payload.rationale),
            )
            row = connection.execute(
                "SELECT * FROM profile_preferences WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return _row_to_preference(row)

    def list_profile_facts(self) -> list[ProfileFact]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM profile_facts ORDER BY category, key"
            ).fetchall()
        return [_row_to_profile_fact(row) for row in rows]

    def list_profile_preferences(self) -> list[ProfilePreference]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM profile_preferences ORDER BY area, id"
            ).fetchall()
        return [_row_to_preference(row) for row in rows]

    def create_note(self, payload: NoteCreate) -> Note:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO notes (kind, title, body, source)
                VALUES (?, ?, ?, ?)
                """,
                (payload.kind, payload.title, payload.body, payload.source),
            )
            row = connection.execute(
                "SELECT * FROM notes WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return _row_to_note(row)

    def list_notes(self) -> list[Note]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM notes ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [_row_to_note(row) for row in rows]

    def list_recent_notes(self, limit: int = 5) -> list[Note]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM notes ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_note(row) for row in rows]

    def create_opportunity(self, payload: OpportunityCreate) -> Opportunity:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO opportunities (
                    source, kind, external_id, title, url, status, rating_hint, tags_json, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, external_id) DO UPDATE SET
                    kind = excluded.kind,
                    title = excluded.title,
                    url = excluded.url,
                    status = excluded.status,
                    rating_hint = excluded.rating_hint,
                    tags_json = excluded.tags_json,
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    payload.source,
                    payload.kind,
                    payload.external_id,
                    payload.title,
                    payload.url,
                    payload.status,
                    payload.rating_hint,
                    json.dumps(payload.tags),
                    json.dumps(payload.payload),
                ),
            )
            if cursor.lastrowid:
                row = connection.execute(
                    "SELECT * FROM opportunities WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT * FROM opportunities
                    WHERE source = ? AND external_id = ?
                    """,
                    (payload.source, payload.external_id),
                ).fetchone()
        return _row_to_opportunity(row)

    def list_opportunities(self) -> list[Opportunity]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM opportunities ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        return [_row_to_opportunity(row) for row in rows]

    def list_recent_opportunities(
        self, limit: int = 5, status: str | None = None
    ) -> list[Opportunity]:
        query = "SELECT * FROM opportunities"
        params: tuple = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY updated_at DESC, id DESC LIMIT ?"
        params = (*params, limit)
        with get_connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_opportunity(row) for row in rows]

    def create_task(self, payload: TaskCreate) -> Task:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tasks (
                    project_id, opportunity_id, kind, title, status, priority, due_at, note, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.project_id,
                    payload.opportunity_id,
                    payload.kind,
                    payload.title,
                    payload.status,
                    payload.priority,
                    serialize_timestamp(payload.due_at),
                    payload.note,
                    json.dumps(payload.metadata),
                ),
            )
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return _row_to_task(row)

    def list_tasks(self, status: str | None = None) -> list[Task]:
        query = "SELECT * FROM tasks"
        params: tuple = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY COALESCE(due_at, updated_at, created_at) ASC, id DESC"
        with get_connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_task(row) for row in rows]

    def list_recent_tasks(
        self, limit: int = 5, status: str | None = None
    ) -> list[Task]:
        query = "SELECT * FROM tasks"
        params: tuple = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += (
            " ORDER BY COALESCE(due_at, updated_at, created_at) ASC, id DESC LIMIT ?"
        )
        params = (*params, limit)
        with get_connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_task(row) for row in rows]

    def create_policy(self, payload: PolicyCreate) -> Policy:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO policies (
                    policy_type, scope, target, value, rationale, active,
                    starts_at, ends_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.policy_type,
                    payload.scope,
                    payload.target,
                    payload.value,
                    payload.rationale,
                    int(payload.active),
                    serialize_timestamp(payload.starts_at),
                    serialize_timestamp(payload.ends_at),
                    json.dumps(payload.metadata),
                ),
            )
            row = connection.execute(
                "SELECT * FROM policies WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return _row_to_policy(row)

    def list_policies(self, active_only: bool = False) -> list[Policy]:
        query = "SELECT * FROM policies"
        params: tuple = ()
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY updated_at DESC, id DESC"
        with get_connection() as connection:
            rows = connection.execute(query, params).fetchall()
        policies = [_row_to_policy(row) for row in rows]
        if not active_only:
            return policies

        now = datetime.now(timezone.utc)
        return [policy for policy in policies if _is_policy_in_effect(policy, now)]

    def create_service(self, payload: ServiceCreate) -> Service:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO services (name, service_type, endpoint, owner, status, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    service_type = excluded.service_type,
                    endpoint = excluded.endpoint,
                    owner = excluded.owner,
                    status = excluded.status,
                    metadata_json = excluded.metadata_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    payload.name,
                    payload.service_type,
                    payload.endpoint,
                    payload.owner,
                    payload.status,
                    json.dumps(payload.metadata),
                ),
            )
            row = connection.execute(
                "SELECT * FROM services WHERE name = ?",
                (payload.name,),
            ).fetchone()
        return _row_to_service(row)

    def list_services(self) -> list[Service]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM services ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        return [_row_to_service(row) for row in rows]

    def get_service(self, service_id: int) -> Service | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM services WHERE id = ?",
                (service_id,),
            ).fetchone()
        return _row_to_service(row) if row else None

    def get_overview_counts(self) -> dict:
        with get_connection() as connection:
            opportunity_status_rows = connection.execute(
                "SELECT status FROM opportunities"
            ).fetchall()
            task_status_rows = connection.execute("SELECT status FROM tasks").fetchall()
            policy_rows = connection.execute("SELECT * FROM policies").fetchall()
            now = datetime.now(timezone.utc)
            counts = {
                "profile_facts": connection.execute(
                    "SELECT COUNT(*) FROM profile_facts"
                ).fetchone()[0],
                "profile_preferences": connection.execute(
                    "SELECT COUNT(*) FROM profile_preferences"
                ).fetchone()[0],
                "notes": connection.execute("SELECT COUNT(*) FROM notes").fetchone()[0],
                "projects": connection.execute(
                    "SELECT COUNT(*) FROM projects"
                ).fetchone()[0],
                "artifacts": connection.execute(
                    "SELECT COUNT(*) FROM artifacts"
                ).fetchone()[0],
                "open_opportunities": sum(
                    1
                    for row in opportunity_status_rows
                    if _is_effectively_open(row["status"], _CLOSED_OPPORTUNITY_STATUSES)
                ),
                "open_tasks": sum(
                    1
                    for row in task_status_rows
                    if _is_effectively_open(row["status"], _CLOSED_TASK_STATUSES)
                ),
                "active_policies": sum(
                    1
                    for row in policy_rows
                    if _is_policy_in_effect(_row_to_policy(row), now)
                ),
                "services": connection.execute(
                    "SELECT COUNT(*) FROM services"
                ).fetchone()[0],
            }
            status_rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM services GROUP BY status"
            ).fetchall()
        counts["services_by_status"] = {
            row["status"]: row["count"] for row in status_rows
        }
        return counts

    def add_service_check(
        self, service_id: int, payload: ServiceCheckCreate
    ) -> ServiceCheck:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO service_checks (service_id, status, message, checked_at, latency_ms, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    service_id,
                    payload.status,
                    payload.message,
                    serialize_timestamp(payload.checked_at),
                    payload.latency_ms,
                    json.dumps(payload.payload),
                ),
            )
            connection.execute(
                """
                UPDATE services
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (payload.status, service_id),
            )
            row = connection.execute(
                "SELECT * FROM service_checks WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return _row_to_service_check(row)
