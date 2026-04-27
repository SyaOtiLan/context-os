from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from personal_agent.db import init_db
from personal_agent.services.issue_radar import RadarOutboxService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a notification_outbox email item from the current radar digest."
    )
    parser.add_argument("--repo", help="Optional GitHub repo filter like owner/repo.")
    parser.add_argument("--lookback-days", type=int, default=3)
    parser.add_argument("--limit", type=int, help="Maximum items per digest section.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    init_db()
    item = RadarOutboxService().enqueue_digest(
        repo=args.repo,
        lookback_days=args.lookback_days,
        limit=args.limit,
    )
    print(f"queued: outbox_id={item.id} subject={item.subject!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
