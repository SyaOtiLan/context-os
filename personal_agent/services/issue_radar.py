from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
from string import Template

from personal_agent.config import settings
from personal_agent.models import (
    GitHubIssue,
    GitHubIssueAnalysisCreate,
    GitHubIssueAnalysisPayload,
    GitHubIssueAnalyzeSummary,
    GitHubIssueFilterResultCreate,
    GitHubIssueFilterSummary,
    GitHubIssueNotificationCreate,
    RadarDigestSections,
    RadarPipelineSummary,
    RadarRecommendedItem,
    RadarScreenedOutItem,
    RadarWatchItem,
)
from personal_agent.services.llm import LLMService
from personal_agent.services.github_issues import GitHubIssueSyncService
from personal_agent.services.profile_derivation import ProfileDerivationService
from personal_agent.services.repository import Repository
from personal_agent.time_utils import parse_timestamp


PRIORITY_LABEL_REASON_CODES = {
    "good first issue": "priority_label_good_first_issue",
    "help wanted": "priority_label_help_wanted",
}

ALLOW_KEYWORD_REASON_CODES = {
    "docs": "small_scope_docs",
    "tests": "small_scope_tests",
    "benchmark": "small_scope_benchmark",
    "config": "small_scope_config",
    "bugfix": "small_scope_bugfix",
    "error message": "small_scope_error_message",
}

LARGE_SCOPE_REASON_CODES = {
    "multimodal": "large_scope_multimodal",
    "distributed": "large_scope_distributed",
    "moe": "large_scope_moe",
    "kernel rewrite": "large_scope_kernel_rewrite",
    "major refactor": "large_scope_major_refactor",
    "scheduler overhaul": "large_scope_scheduler_overhaul",
}

# TODO: This module has minimal effect; consider removing if no longer needed.
TEXT_PATTERNS = {
    "mentions_existing_pr": re.compile(
        r"\b(?:pull request|linked pr|pr\s*#\d+|fix(?:ed|es)?\s+by\s+#\d+)\b",
        re.IGNORECASE,
    ),
    "mentions_duplicate": re.compile(r"\bduplicate\b", re.IGNORECASE),
    "mentions_active_work": re.compile(
        r"\b(?:working on this|working on it|i am working on|i'm working on|taking this)\b",
        re.IGNORECASE,
    ),
}

JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
INSTANT_ALERT_NOTIFICATION_TYPE = "instant_alert"


@dataclass
class FilterDecision:
    eligible: bool
    reason_codes: list[str]


def _normalize_text(value: str) -> str:
    return " ".join((value or "").lower().split())


def evaluate_issue(
    issue: GitHubIssue, reference_time: datetime | None = None
) -> FilterDecision:
    positive_codes: list[str] = []
    blocker_codes: list[str] = []
    normalized_labels = {label.lower().strip() for label in issue.labels}
    combined_text = _normalize_text(f"{issue.title}\n{issue.body}")
    reference_time = reference_time or datetime.now(timezone.utc)

    if issue.state.lower() != "open":
        blocker_codes.append("not_open")

    if issue.is_pull_request:
        blocker_codes.append("is_pull_request")

    if settings.github_max_issue_staleness_days > 0:
        stale_before = reference_time - timedelta(
            days=settings.github_max_issue_staleness_days
        )
        issue_updated_at = parse_timestamp(issue.updated_at) or datetime.min.replace(
            tzinfo=timezone.utc
        )
        if issue_updated_at < stale_before:
            blocker_codes.append("stale_issue")

    label_codes = [
        code
        for label, code in PRIORITY_LABEL_REASON_CODES.items()
        if label in normalized_labels
    ]
    positive_codes.extend(label_codes)

    if settings.github_only_priority_labels and not label_codes:
        blocker_codes.append("missing_priority_label")

    if issue.assignees:
        blocker_codes.append("has_assignee")

    for code, pattern in TEXT_PATTERNS.items():
        if pattern.search(combined_text):
            blocker_codes.append(code)

    for keyword, code in LARGE_SCOPE_REASON_CODES.items():
        if keyword in combined_text:
            blocker_codes.append(code)

    for keyword, code in ALLOW_KEYWORD_REASON_CODES.items():
        if keyword in combined_text:
            positive_codes.append(code)

    reason_codes = list(dict.fromkeys(positive_codes + blocker_codes))
    return FilterDecision(eligible=not blocker_codes, reason_codes=reason_codes)


class IssueFilterService:
    def __init__(self, repository: Repository | None = None) -> None:
        self.repository = repository or Repository()

    def apply_filters(self, repo: str | None = None) -> GitHubIssueFilterSummary:
        issues = self.repository.list_github_issues(repo=repo, limit=0)
        summary = GitHubIssueFilterSummary(total=len(issues))
        now = datetime.now(timezone.utc)

        for issue in issues:
            decision = evaluate_issue(issue, reference_time=now)
            self.repository.upsert_github_issue_filter_result(
                GitHubIssueFilterResultCreate(
                    issue_id=issue.id,
                    eligible=decision.eligible,
                    reason_codes=decision.reason_codes,
                    evaluated_at=now,
                )
            )
            if decision.eligible:
                summary.eligible += 1
            else:
                summary.ineligible += 1

        return summary


class IssueAnalysisService:
    def __init__(
        self,
        repository: Repository | None = None,
        profile_service: ProfileDerivationService | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        self.repository = repository or Repository()
        self.profile_service = profile_service or ProfileDerivationService(
            self.repository
        )
        self.llm_service = llm_service or LLMService()

    def analyze_eligible_issues(
        self,
        repo: str | None = None,
        limit: int | None = None,
        force: bool = False,
    ) -> GitHubIssueAnalyzeSummary:
        views = self.repository.list_github_issue_views(
            repo=repo,
            eligible=True,
            analyzed=None if force else False,
            limit=limit or 0,
        )
        summary = GitHubIssueAnalyzeSummary(requested=len(views))
        if not views:
            return summary

        profile_snapshot = self.repository.get_latest_profile_snapshot()
        profile_summary = (
            profile_snapshot.summary
            if profile_snapshot is not None
            else self.profile_service.build_profile().summary
        )

        for view in views:
            payload, raw_response, used_fallback = self._analyze_issue(
                view.issue,
                view.filter_result.reason_codes if view.filter_result else [],
                profile_summary,
            )
            self.repository.upsert_github_issue_analysis(
                GitHubIssueAnalysisCreate(
                    issue_id=view.issue.id,
                    fit_score=payload.fit_score,
                    difficulty=payload.difficulty,
                    why_fit=payload.why_fit,
                    why_not_fit=payload.why_not_fit,
                    likely_blockers=payload.likely_blockers,
                    first_step=payload.first_step,
                    should_notify=payload.should_notify,
                    provider="openai-compatible",
                    model_name=settings.llm_model or "unknown",
                    raw_response=raw_response,
                    analyzed_at=datetime.now(timezone.utc),
                )
            )
            summary.analyzed += 1
            if used_fallback:
                summary.fallback_used += 1

        return summary

    def _analyze_issue(
        self,
        issue: GitHubIssue,
        filter_reason_codes: list[str],
        profile_summary: str,
    ) -> tuple[GitHubIssueAnalysisPayload, str, bool]:
        system_prompt = self._render_prompt(
            "radar_analyzer_system.txt",
            profile_summary=profile_summary,
        )
        user_prompt = self._render_prompt(
            "radar_analyzer_user.txt",
            repo=issue.repo,
            issue_number=str(issue.issue_number),
            title=issue.title,
            url=issue.url,
            labels=", ".join(issue.labels) or "(none)",
            assignees=", ".join(issue.assignees) or "(none)",
            filter_reason_codes=", ".join(filter_reason_codes) or "(none)",
            body=issue.body.strip() or "(empty)",
        )
        return self._analyze_with_retries(system_prompt, user_prompt)

    def _render_prompt(self, name: str, **context: str) -> str:
        template = Template((PROMPT_DIR / name).read_text(encoding="utf-8"))
        return template.substitute(**context).strip()

    def _analyze_with_retries(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[GitHubIssueAnalysisPayload, str, bool]:
        max_attempts = 3
        last_raw_response = ""
        last_error = ""
        for attempt in range(1, max_attempts + 1):
            try:
                raw_response = self.llm_service.chat(
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    max_tokens=500,
                )
                last_raw_response = raw_response
                payload, _, used_fallback = self._parse_analysis_response(raw_response)
                if not used_fallback:
                    return payload, raw_response, False
                last_error = payload.why_not_fit
            except Exception as exc:
                last_error = str(exc)
            if attempt < max_attempts:
                time.sleep(float(attempt))

        fallback = GitHubIssueAnalysisPayload(
            fit_score=1,
            difficulty="hard",
            why_fit="需要人工复核。",
            why_not_fit=last_error or "分析器连续失败。",
            likely_blockers="模型输出不稳定或不可解析。",
            first_step="重新运行分析并人工检查该 issue。",
            should_notify=False,
        )
        return fallback, (last_raw_response or last_error), True

    def _parse_analysis_response(
        self,
        raw_response: str,
    ) -> tuple[GitHubIssueAnalysisPayload, str, bool]:
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        candidates = [cleaned]
        match = JSON_OBJECT_PATTERN.search(cleaned)
        if match and match.group(0) not in candidates:
            candidates.append(match.group(0))

        for candidate in candidates:
            try:
                payload = GitHubIssueAnalysisPayload.model_validate(
                    json.loads(candidate)
                )
                return payload, raw_response, False
            except Exception:
                continue

        fallback = GitHubIssueAnalysisPayload(
            fit_score=1,
            difficulty="hard",
            why_fit="当前无法可靠判断匹配度。",
            why_not_fit="模型输出无法解析为有效 JSON。",
            likely_blockers="需要重新分析该 issue。",
            first_step="重新运行分析并检查模型输出。",
            should_notify=False,
        )
        return fallback, raw_response, True


REASON_LABELS = {
    "priority_label_good_first_issue": "带有 good first issue 标签",
    "priority_label_help_wanted": "带有 help wanted 标签",
    "small_scope_docs": "范围偏 docs",
    "small_scope_tests": "范围偏 tests",
    "small_scope_benchmark": "范围偏 benchmark",
    "small_scope_config": "范围偏 config",
    "small_scope_bugfix": "范围偏 bugfix",
    "small_scope_error_message": "范围偏错误信息改进",
    "not_open": "不是 open issue",
    "is_pull_request": "这是 PR 不是 issue",
    "stale_issue": "超过时效窗口",
    "missing_priority_label": "没有优先标签",
    "has_assignee": "已经有人认领",
    "mentions_existing_pr": "正文提到已有 PR",
    "mentions_duplicate": "正文提到 duplicate",
    "mentions_active_work": "正文提到有人正在处理",
    "large_scope_multimodal": "范围偏 multimodal",
    "large_scope_distributed": "范围偏 distributed",
    "large_scope_moe": "范围偏 MoE",
    "large_scope_kernel_rewrite": "范围偏 kernel rewrite",
    "large_scope_major_refactor": "范围偏 major refactor",
    "large_scope_scheduler_overhaul": "范围偏 scheduler overhaul",
}


def humanize_reason_code(code: str) -> str:
    return REASON_LABELS.get(code, code.replace("_", " "))


class RadarDigestService:
    def __init__(self, repository: Repository | None = None) -> None:
        self.repository = repository or Repository()

    def build_digest_sections(
        self,
        repo: str | None = None,
        lookback_days: int = 3,
        limit: int | None = None,
    ) -> RadarDigestSections:
        generated_at = datetime.now(timezone.utc)
        cutoff = generated_at - timedelta(days=lookback_days)
        views = self.repository.list_github_issue_views(repo=repo, limit=0)
        recommended: list[RadarRecommendedItem] = []
        watchlist: list[RadarWatchItem] = []
        screened_out: list[RadarScreenedOutItem] = []

        for view in views:
            created_at = parse_timestamp(view.issue.created_at) or datetime.min.replace(
                tzinfo=timezone.utc
            )
            if created_at < cutoff:
                continue
            if view.analysis and view.filter_result and view.filter_result.eligible:
                if view.analysis.should_notify:
                    recommended.append(
                        RadarRecommendedItem(
                            title=view.issue.title,
                            repo=view.issue.repo,
                            issue_number=view.issue.issue_number,
                            labels=view.issue.labels,
                            fit_score=view.analysis.fit_score,
                            difficulty=view.analysis.difficulty,
                            why_fit=view.analysis.why_fit,
                            likely_blockers=view.analysis.likely_blockers,
                            first_step=view.analysis.first_step,
                            url=view.issue.url,
                        )
                    )
                else:
                    watchlist.append(
                        RadarWatchItem(
                            title=view.issue.title,
                            repo=view.issue.repo,
                            issue_number=view.issue.issue_number,
                            labels=view.issue.labels,
                            fit_score=view.analysis.fit_score,
                            difficulty=view.analysis.difficulty,
                            why_fit=view.analysis.why_fit,
                            why_not_fit=view.analysis.why_not_fit,
                            url=view.issue.url,
                        )
                    )
            elif view.filter_result and not view.filter_result.eligible:
                screened_out.append(
                    RadarScreenedOutItem(
                        title=view.issue.title,
                        repo=view.issue.repo,
                        issue_number=view.issue.issue_number,
                        labels=view.issue.labels,
                        reason_codes=view.filter_result.reason_codes,
                        reason_labels=[
                            humanize_reason_code(code)
                            for code in view.filter_result.reason_codes
                        ],
                        url=view.issue.url,
                    )
                )

        if limit:
            recommended = recommended[:limit]
            watchlist = watchlist[:limit]
            screened_out = screened_out[:limit]

        return RadarDigestSections(
            recommended=recommended,
            watchlist=watchlist,
            screened_out=screened_out,
            lookback_days=lookback_days,
            generated_at=generated_at.isoformat(),
        )


class RadarNotificationService:
    def __init__(self, repository: Repository | None = None) -> None:
        self.repository = repository or Repository()

    def mark_new_issue_alerts(
        self, repo: str | None = None, limit: int | None = None
    ) -> int:
        views = self.repository.list_github_issue_views(
            repo=repo, eligible=True, analyzed=True, limit=0
        )
        existing = {
            item.issue_id
            for item in self.repository.list_github_issue_notifications(
                notification_type=INSTANT_ALERT_NOTIFICATION_TYPE,
                limit=0,
            )
        }
        sent = 0
        for view in views:
            if not view.analysis or not view.analysis.should_notify:
                continue
            if view.issue.id in existing:
                continue
            self.repository.create_github_issue_notification(
                GitHubIssueNotificationCreate(
                    issue_id=view.issue.id,
                    notification_type=INSTANT_ALERT_NOTIFICATION_TYPE,
                    subject=f"[Radar] {view.issue.repo}#{view.issue.issue_number} {view.issue.title}",
                    sent_at=datetime.now(timezone.utc),
                )
            )
            sent += 1
            if limit and sent >= limit:
                break
        return sent


class RadarPipelineService:
    def __init__(
        self,
        repository: Repository | None = None,
        sync_service: GitHubIssueSyncService | None = None,
        filter_service: IssueFilterService | None = None,
        analysis_service: IssueAnalysisService | None = None,
        digest_service: RadarDigestService | None = None,
    ) -> None:
        self.repository = repository or Repository()
        self.sync_service = sync_service or GitHubIssueSyncService(self.repository)
        self.filter_service = filter_service or IssueFilterService(self.repository)
        self.analysis_service = analysis_service or IssueAnalysisService(
            self.repository
        )
        self.digest_service = digest_service or RadarDigestService(self.repository)

    def run(
        self,
        repo: str,
        analysis_limit: int | None = None,
        force_analysis: bool = False,
    ) -> RadarPipelineSummary:
        sync_summary = self.sync_service.sync_open_issues(repo)
        filter_summary = self.filter_service.apply_filters(repo=repo)
        analysis_summary = self.analysis_service.analyze_eligible_issues(
            repo=repo,
            limit=analysis_limit,
            force=force_analysis,
        )
        sections = self.digest_service.build_digest_sections(repo=repo)
        return RadarPipelineSummary(
            sync=sync_summary,
            filtering=filter_summary,
            analysis=analysis_summary,
            digest_item_count=(
                len(sections.recommended)
                + len(sections.watchlist)
                + len(sections.screened_out)
            ),
        )
