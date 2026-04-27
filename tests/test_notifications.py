from __future__ import annotations

from personal_agent.config import settings
from personal_agent.models import NotificationOutboxCreate
from personal_agent.services.notifications import SMTPNotificationSender
from personal_agent.services.repository import Repository
from scripts import send_outbox


class FakeSMTP:
    sent_subjects: list[str] = []

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def starttls(self) -> None:
        return None

    def login(self, username: str, password: str) -> None:
        return None

    def send_message(self, message) -> None:
        self.sent_subjects.append(message["Subject"])


class FailingSMTP(FakeSMTP):
    def send_message(self, message) -> None:
        raise RuntimeError("smtp failed")


def configure_smtp(monkeypatch, smtp_class=FakeSMTP) -> None:
    FakeSMTP.sent_subjects = []
    object.__setattr__(settings, "smtp_host", "smtp.example.com")
    object.__setattr__(settings, "smtp_port", 587)
    object.__setattr__(settings, "smtp_username", "user")
    object.__setattr__(settings, "smtp_password", "pass")
    object.__setattr__(settings, "smtp_from", "from@example.com")
    object.__setattr__(settings, "smtp_to", "to@example.com")
    object.__setattr__(settings, "smtp_use_tls", True)
    monkeypatch.setattr("personal_agent.services.notifications.smtplib.SMTP", smtp_class)


def test_smtp_sender_sends_pending_email(repository: Repository, monkeypatch) -> None:
    configure_smtp(monkeypatch)
    item = repository.create_notification_outbox_item(
        NotificationOutboxCreate(
            channel="email",
            subject="Digest",
            body="Body",
            payload={"type": "test"},
        )
    )

    sent = SMTPNotificationSender(repository).send_pending()
    updated = repository.list_notification_outbox_items(status="sent")

    assert sent == 1
    assert updated[0].id == item.id
    assert updated[0].sent_at is not None
    assert FakeSMTP.sent_subjects == ["Digest"]


def test_smtp_sender_marks_failed_email(repository: Repository, monkeypatch) -> None:
    configure_smtp(monkeypatch, FailingSMTP)
    item = repository.create_notification_outbox_item(
        NotificationOutboxCreate(channel="email", subject="Digest", body="Body")
    )

    sent = SMTPNotificationSender(repository).send_pending()
    failed = repository.list_notification_outbox_items(status="failed")

    assert sent == 0
    assert failed[0].id == item.id
    assert "smtp failed" in (failed[0].error or "")


def test_send_outbox_script(repository: Repository, monkeypatch, capsys) -> None:
    configure_smtp(monkeypatch)
    repository.create_notification_outbox_item(
        NotificationOutboxCreate(channel="email", subject="Digest", body="Body")
    )

    exit_code = send_outbox.main([])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "sent=1" in output
