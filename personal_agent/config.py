from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _strip_env_value(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1]
    return stripped


def load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _strip_env_value(value)


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = "ContextOS"
    db_path: Path = Path(os.getenv("PCOS_DB_PATH", "data/app.db"))
    debug: bool = os.getenv("PCOS_DEBUG", "false").lower() == "true"
    github_api_base_url: str = os.getenv("PCOS_GITHUB_API_BASE_URL", "https://api.github.com")
    github_token: str | None = os.getenv("PCOS_GITHUB_TOKEN")
    github_per_page: int = int(os.getenv("PCOS_GITHUB_PER_PAGE", "100"))
    github_only_priority_labels: bool = os.getenv("PCOS_GITHUB_ONLY_PRIORITY_LABELS", "true").lower() == "true"
    github_max_issue_staleness_days: int = int(os.getenv("PCOS_GITHUB_MAX_ISSUE_STALENESS_DAYS", "90"))
    llm_api_base: str | None = os.getenv("PCOS_LLM_API_BASE")
    llm_api_key: str | None = os.getenv("PCOS_LLM_API_KEY")
    llm_model: str | None = os.getenv("PCOS_LLM_MODEL")
    llm_wire_api: str = os.getenv("PCOS_LLM_WIRE_API", "chat_completions")
    llm_reasoning_effort: str | None = os.getenv("PCOS_LLM_REASONING_EFFORT")
    llm_disable_response_storage: bool = os.getenv("PCOS_LLM_DISABLE_RESPONSE_STORAGE", "true").lower() == "true"
    llm_timeout_seconds: int = int(os.getenv("PCOS_LLM_TIMEOUT_SECONDS", "60"))
    smtp_host: str | None = os.getenv("PCOS_SMTP_HOST")
    smtp_port: int = int(os.getenv("PCOS_SMTP_PORT", "587"))
    smtp_username: str | None = os.getenv("PCOS_SMTP_USERNAME")
    smtp_password: str | None = os.getenv("PCOS_SMTP_PASSWORD")
    smtp_from: str | None = os.getenv("PCOS_SMTP_FROM")
    smtp_to: str | None = os.getenv("PCOS_SMTP_TO")
    smtp_use_tls: bool = os.getenv("PCOS_SMTP_USE_TLS", "true").lower() == "true"


settings = Settings()
