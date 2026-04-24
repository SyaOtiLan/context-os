from __future__ import annotations

from datetime import datetime, timezone


def normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def serialize_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return normalize_timestamp(value).isoformat()


def parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return normalize_timestamp(datetime.fromisoformat(text))
