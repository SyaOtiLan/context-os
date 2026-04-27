from __future__ import annotations

from personal_agent.services.repository import Repository
from scripts import enqueue_radar_digest


def test_enqueue_radar_digest_script_creates_outbox_item(
    repository: Repository,
    capsys,
) -> None:
    exit_code = enqueue_radar_digest.main(["--repo", "example/repo"])

    output = capsys.readouterr().out
    items = repository.list_notification_outbox_items(status="pending")
    assert exit_code == 0
    assert "queued:" in output
    assert len(items) == 1
    assert items[0].channel == "email"
    assert items[0].payload["type"] == "radar_digest"
