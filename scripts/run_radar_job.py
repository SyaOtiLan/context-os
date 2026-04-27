from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from personal_agent.db import init_db
from personal_agent.services.issue_radar import RadarOutboxService, RadarPipelineService
from personal_agent.services.notifications import SMTPNotificationSender


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the ContextOS radar pipeline, enqueue a digest, and optionally send it."
    )
    parser.add_argument("--repo", required=True, help="GitHub repo like owner/repo.")
    parser.add_argument("--analysis-limit", type=int, default=5)
    parser.add_argument("--force-analysis", action="store_true")
    parser.add_argument("--lookback-days", type=int, default=3)
    parser.add_argument("--digest-limit", type=int, help="Maximum items per digest section.")
    parser.add_argument(
        "--send",
        action="store_true",
        help="Send pending email outbox items after queueing the digest.",
    )
    parser.add_argument(
        "--send-limit",
        type=int,
        default=20,
        help="Maximum pending emails to send when --send is enabled.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    init_db()

    pipeline_summary = RadarPipelineService().run(
        repo=args.repo,
        analysis_limit=args.analysis_limit,
        force_analysis=args.force_analysis,
    )
    print(
        "pipeline: "
        f"fetched={pipeline_summary.sync.total_fetched} "
        f"created={pipeline_summary.sync.created} "
        f"updated={pipeline_summary.sync.updated} "
        f"eligible={pipeline_summary.filtering.eligible} "
        f"ineligible={pipeline_summary.filtering.ineligible} "
        f"analyzed={pipeline_summary.analysis.analyzed} "
        f"fallback={pipeline_summary.analysis.fallback_used} "
        f"digest_items={pipeline_summary.digest_item_count}"
    )

    outbox_item = RadarOutboxService().enqueue_digest(
        repo=args.repo,
        lookback_days=args.lookback_days,
        limit=args.digest_limit,
    )
    print(f"queued: outbox_id={outbox_item.id} subject={outbox_item.subject!r}")

    if args.send:
        sent = SMTPNotificationSender().send_pending(limit=args.send_limit)
        print(f"sent={sent}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
