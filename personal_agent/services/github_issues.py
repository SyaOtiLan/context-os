from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from personal_agent.config import settings
from personal_agent.models import GitHubIssueCreate, GitHubIssueSyncSummary
from personal_agent.services.repository import Repository
from personal_agent.time_utils import parse_timestamp


class GitHubClient:
    def __init__(self) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Personal-Context-OS/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"

        self.per_page = settings.github_per_page
        self.session = requests.Session()
        self.session.headers.update(headers)
        self.api_base = settings.github_api_base_url.rstrip("/")

    def fetch_open_issues(
        self,
        repo: str,
        label: str | None = None,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        next_url: str | None = f"{self.api_base}/repos/{repo}/issues"
        params: dict[str, Any] | None = {
            "state": "open",
            "per_page": self.per_page,
            "page": 1,
        }
        if label:
            params["labels"] = label
        if since:
            params["since"] = since.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

        while next_url:
            response = self.session.get(next_url, params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
            if not payload:
                break

            issues.extend(payload)
            next_link = response.links.get("next")
            next_url = next_link["url"] if next_link else None
            params = None

        return issues


class GitHubIssueSyncService:
    PRIORITY_LABELS = ("good first issue", "help wanted")

    def __init__(
        self,
        repository: Repository | None = None,
        client: GitHubClient | None = None,
    ) -> None:
        self.repository = repository or Repository()
        self.client = client or GitHubClient()

    def sync_open_issues(self, repo: str) -> GitHubIssueSyncSummary:
        summary = GitHubIssueSyncSummary()
        fetched_at = datetime.now(timezone.utc)
        since = None
        if settings.github_max_issue_staleness_days > 0:
            since = fetched_at - timedelta(days=settings.github_max_issue_staleness_days)

        if settings.github_only_priority_labels:
            deduped_payloads: dict[int, dict[str, Any]] = {}
            for label in self.PRIORITY_LABELS:
                for payload in self.client.fetch_open_issues(repo, label=label, since=since):
                    deduped_payloads[payload["number"]] = payload
            payloads = list(deduped_payloads.values())
        else:
            payloads = self.client.fetch_open_issues(repo, since=since)

        summary.total_fetched = len(payloads)
        existing = {
            (issue.repo, issue.issue_number): issue
            for issue in self.repository.list_github_issues(repo=repo, limit=0)
        }

        for payload in payloads:
            if payload.get("pull_request"):
                summary.skipped_pull_requests += 1
                continue

            issue = self.repository.upsert_github_issue(
                GitHubIssueCreate(
                    repo=repo,
                    issue_number=payload["number"],
                    title=payload["title"],
                    url=payload["html_url"],
                    state=payload["state"],
                    labels=[
                        label["name"]
                        for label in payload.get("labels", [])
                        if label.get("name")
                    ],
                    assignees=[
                        user["login"]
                        for user in payload.get("assignees", [])
                        if user.get("login")
                    ],
                    author=(payload.get("user") or {}).get("login"),
                    body=payload.get("body") or "",
                    is_pull_request=bool(payload.get("pull_request")),
                    created_at=parse_timestamp(payload["created_at"])
                    or datetime.now(timezone.utc),
                    updated_at=parse_timestamp(payload["updated_at"])
                    or datetime.now(timezone.utc),
                    fetched_at=fetched_at,
                )
            )
            if (issue.repo, issue.issue_number) in existing:
                summary.updated += 1
            else:
                summary.created += 1

        return summary
