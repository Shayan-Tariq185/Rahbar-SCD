from __future__ import annotations

import json

import httpx

from app.config import Settings
from app.providers.llm.ollama import OllamaProvider
from app.schemas import Passage


def _passage() -> Passage:
    return Passage(
        chunk_id="c1",
        text="Attendance is required.",
        source="rules.pdf",
        section="1.21 Attendance",
        page=2,
        score=0.9,
    )


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload


class _FakeClient:
    responses: list[dict[str, object]]

    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = responses
        self.calls = 0

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def post(self, url: str, **kwargs: object) -> _FakeResponse:
        response = _FakeResponse(self.responses[self.calls])
        self.calls += 1
        return response


def _settings() -> Settings:
    return Settings(ollama_url="http://ollama", llm_model="test")


def test_ollama_retries_invalid_json_and_accepts_valid_answer(
    monkeypatch,
) -> None:
    valid = {
        "reasoning": "evidence",
        "answer": "Attendance is required.",
        "citations": [{"source": "rules.pdf", "section": "1.21 Attendance", "page": 2}],
        "answered_from_context": True,
        "confidence": "high",
    }
    client = _FakeClient([
        {"message": {"content": "not json"}},
        {"message": {"content": json.dumps(valid)}},
    ])
    monkeypatch.setattr(httpx, "Client", lambda timeout: client)

    answer = OllamaProvider(_settings()).generate("What is required?", [_passage()])

    assert answer.answer == "Attendance is required."
    assert client.calls == 2


def test_ollama_returns_safe_fallback_after_two_invalid_responses(monkeypatch) -> None:
    client = _FakeClient([
        {"message": {"content": "bad"}},
        {"message": {"content": "still bad"}},
    ])
    monkeypatch.setattr(httpx, "Client", lambda timeout: client)

    answer = OllamaProvider(_settings()).generate("What is required?", [_passage()])

    assert answer.answered_from_context is False
    assert answer.citations == []
    assert client.calls == 2
