from __future__ import annotations

from datetime import datetime, timezone

from personal_agent.models import OverviewCounts, OverviewSnapshot, ProfileSummary
from personal_agent.services.repository import Repository


class OverviewService:
    def __init__(self, repository: Repository | None = None) -> None:
        self.repository = repository or Repository()

    def build_snapshot(self) -> OverviewSnapshot:
        counts = OverviewCounts(**self.repository.get_overview_counts())
        profile = ProfileSummary(
            facts=self.repository.list_profile_facts(),
            preferences=self.repository.list_profile_preferences(),
        )
        return OverviewSnapshot(
            generated_at=datetime.now(timezone.utc).isoformat(),
            counts=counts,
            profile=profile,
            recent_projects=self.repository.list_recent_projects(),
            recent_artifacts=self.repository.list_recent_artifacts(),
            recent_notes=self.repository.list_recent_notes(),
            recent_opportunities=self.repository.list_recent_opportunities(),
            recent_tasks=self.repository.list_recent_tasks(),
            active_policies=self.repository.list_policies(active_only=True),
            services=self.repository.list_services(),
        )
