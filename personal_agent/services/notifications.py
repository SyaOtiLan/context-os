from __future__ import annotations

import smtplib

from datetime import datetime, timezone
from email.message import EmailMessage

from personal_agent.config import settings
from personal_agent.models import NotificationOutboxItem
from personal_agent.services.repository import Repository


class SMTPNotConfiguredError(RuntimeError):
    pass


class SMTPNotificationSender:
    def __init__(self, repository: Repository | None = None) -> None:
        self.repository = repository or Repository()

    def send_pending(self, limit: int = 20) -> int:
        items = self.repository.list_notification_outbox_items(
            status="pending",
            channel="email",
            limit=limit,
        )
        sent = 0
        for item in items:
            try:
                self._send_email(item)
            except Exception as exc:
                self.repository.mark_notification_outbox_failed(item.id, str(exc))
                continue
            self.repository.mark_notification_outbox_sent(
                item.id,
                datetime.now(timezone.utc),
            )
            sent += 1
        return sent

    def _send_email(self, item: NotificationOutboxItem) -> None:
        if not settings.smtp_host or not settings.smtp_from or not settings.smtp_to:
            raise SMTPNotConfiguredError(
                "SMTP is not configured. Set PCOS_SMTP_HOST, PCOS_SMTP_FROM, and PCOS_SMTP_TO."
            )

        message = EmailMessage()
        message["Subject"] = item.subject
        message["From"] = settings.smtp_from
        message["To"] = settings.smtp_to
        message.set_content(item.body)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
