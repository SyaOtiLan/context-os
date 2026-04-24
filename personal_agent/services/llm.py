from __future__ import annotations

import requests

from personal_agent.config import settings


class LLMNotConfiguredError(RuntimeError):
    pass


class LLMService:
    def __init__(self) -> None:
        if not settings.llm_api_base or not settings.llm_api_key or not settings.llm_model:
            raise LLMNotConfiguredError(
                "LLM is not configured. Set PCOS_LLM_API_BASE, PCOS_LLM_API_KEY, and PCOS_LLM_MODEL."
            )

        self.api_base = settings.llm_api_base.rstrip("/")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.timeout_seconds = settings.llm_timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int = 600) -> str:
        response = self.session.post(
            f"{self.api_base}/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("LLM returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not content:
            raise RuntimeError("LLM returned an empty response")
        return content.strip()
