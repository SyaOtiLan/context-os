from __future__ import annotations

from typing import Any

import requests

from personal_agent.config import settings


class LLMNotConfiguredError(RuntimeError):
    pass


class LLMAPIError(RuntimeError):
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
        self.wire_api = settings.llm_wire_api
        self.timeout_seconds = settings.llm_timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int = 600) -> str:
        if self.wire_api == "responses":
            return self._chat_with_responses(messages=messages, max_tokens=max_tokens)
        if self.wire_api != "chat_completions":
            raise RuntimeError(f"Unsupported LLM wire API: {self.wire_api}")
        return self._chat_with_completions(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _chat_with_completions(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
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
        payload = _parse_json_response(response)
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("LLM returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not content:
            raise RuntimeError("LLM returned an empty response")
        return content.strip()

    def _chat_with_responses(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
    ) -> str:
        request_body: dict[str, Any] = {
            "model": self.model,
            "input": [
                {
                    "role": message["role"],
                    "content": message["content"],
                }
                for message in messages
            ],
            "max_output_tokens": max_tokens,
        }
        if settings.llm_disable_response_storage:
            request_body["store"] = False
        if settings.llm_reasoning_effort:
            request_body["reasoning"] = {"effort": settings.llm_reasoning_effort}

        response = self.session.post(
            f"{self.api_base}/responses",
            json=request_body,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = _parse_json_response(response)
        content = _extract_responses_text(payload)
        if not content:
            raise RuntimeError("LLM returned an empty response")
        return content.strip()


def _parse_json_response(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        snippet = response.text[:300].replace("\n", " ")
        raise LLMAPIError(
            f"LLM returned non-JSON response: status={response.status_code}, body={snippet!r}"
        ) from exc
    if not isinstance(payload, dict):
        raise LLMAPIError("LLM returned JSON, but the top-level payload is not an object")
    return payload


def _extract_responses_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    parts: list[str] = []
    output = payload.get("output") or []
    if not isinstance(output, list):
        return ""
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content") or []
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts)
