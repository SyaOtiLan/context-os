from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from personal_agent.db import init_db
from personal_agent.services.notifications import SMTPNotificationSender


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send pending ContextOS notification_outbox email items."
    )
    parser.add_argument("--limit", type=int, default=20, help="Maximum pending emails to send.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    init_db()
    sent = SMTPNotificationSender().send_pending(limit=args.limit)
    print(f"sent={sent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
