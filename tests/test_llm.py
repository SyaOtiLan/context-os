from __future__ import annotations

from personal_agent.config import settings
from personal_agent.services import llm
from personal_agent.services.llm import LLMService


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, payload: dict) -> None:
        self.headers = {}
        self.payload = payload
        self.calls: list[dict] = []

    def post(self, url: str, json: dict, timeout: int) -> FakeResponse:
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse(self.payload)


def _configure_llm(wire_api: str) -> None:
    object.__setattr__(settings, "llm_api_base", "https://example.test/v1")
    object.__setattr__(settings, "llm_api_key", "test-key")
    object.__setattr__(settings, "llm_model", "test-model")
    object.__setattr__(settings, "llm_wire_api", wire_api)
    object.__setattr__(settings, "llm_reasoning_effort", None)
    object.__setattr__(settings, "llm_disable_response_storage", True)
    object.__setattr__(settings, "llm_timeout_seconds", 12)


def test_llm_service_chat_completions(monkeypatch) -> None:
    _configure_llm("chat_completions")
    fake_session = FakeSession({"choices": [{"message": {"content": "ok"}}]})
    monkeypatch.setattr(llm.requests, "Session", lambda: fake_session)

    service = LLMService()
    result = service.chat([{"role": "user", "content": "hello"}], max_tokens=50)

    assert result == "ok"
    assert fake_session.calls[0]["url"] == "https://example.test/v1/chat/completions"
    assert fake_session.calls[0]["json"]["messages"][0]["content"] == "hello"
    assert fake_session.calls[0]["json"]["max_tokens"] == 50


def test_llm_service_responses_api(monkeypatch) -> None:
    _configure_llm("responses")
    object.__setattr__(settings, "llm_reasoning_effort", "xhigh")
    fake_session = FakeSession({"output_text": "candidate json"})
    monkeypatch.setattr(llm.requests, "Session", lambda: fake_session)

    service = LLMService()
    result = service.chat([{"role": "user", "content": "extract"}], max_tokens=80)

    request_body = fake_session.calls[0]["json"]
    assert result == "candidate json"
    assert fake_session.calls[0]["url"] == "https://example.test/v1/responses"
    assert request_body["input"][0]["content"] == "extract"
    assert request_body["max_output_tokens"] == 80
    assert request_body["store"] is False
    assert request_body["reasoning"] == {"effort": "xhigh"}


def test_extract_responses_text_from_output_blocks() -> None:
    payload = {
        "output": [
            {
                "content": [
                    {"type": "output_text", "text": "first"},
                    {"type": "output_text", "text": "second"},
                ]
            }
        ]
    }

    assert llm._extract_responses_text(payload) == "first\nsecond"
