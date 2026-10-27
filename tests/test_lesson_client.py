from __future__ import annotations

import io
import json
from email.message import Message
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from medha.lesson import OllamaClient, OllamaError


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return self.payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_chat_posts_structured_request(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[Request, float]] = []

    def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
        seen.append((request, timeout))
        return FakeResponse(
            json.dumps({"message": {"role": "assistant", "content": '{"ok": true}'}}).encode()
        )

    monkeypatch.setattr("medha.lesson.client.urlopen", fake_urlopen)
    client = OllamaClient(
        model="test-model",
        base_url="http://127.0.0.1:11434/",
        timeout_s=7,
        options={"temperature": 0.1},
    )
    content = client.chat(
        [{"role": "user", "content": "hello"}],
        format_schema={"type": "object"},
    )

    assert content == '{"ok": true}'
    request, timeout = seen[0]
    assert request.full_url == "http://127.0.0.1:11434/api/chat"
    assert timeout == 7
    assert isinstance(request.data, bytes)
    body = json.loads(request.data)
    assert body["model"] == "test-model"
    assert body["stream"] is False
    assert body["format"] == {"type": "object"}
    assert body["options"]["temperature"] == 0.1
    assert body["keep_alive"]


def test_chat_reports_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
        raise HTTPError(
            request.full_url,
            404,
            "Not Found",
            Message(),
            io.BytesIO(b'{"error": "model not found"}'),
        )

    monkeypatch.setattr("medha.lesson.client.urlopen", fake_urlopen)
    client = OllamaClient(model="missing")
    with pytest.raises(OllamaError, match=r"HTTP 404.*model not found"):
        client.chat([{"role": "user", "content": "hello"}])


def test_chat_reports_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
        raise URLError("connection refused")

    monkeypatch.setattr("medha.lesson.client.urlopen", fake_urlopen)
    client = OllamaClient(model="test")
    with pytest.raises(OllamaError, match="cannot reach Ollama"):
        client.chat([{"role": "user", "content": "hello"}])


def test_chat_reports_empty_message(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
        return FakeResponse(b'{"message": {"content": ""}}')

    monkeypatch.setattr("medha.lesson.client.urlopen", fake_urlopen)
    client = OllamaClient(model="test")
    with pytest.raises(OllamaError, match="no lesson"):
        client.chat([{"role": "user", "content": "hello"}])


def test_chat_reports_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
        return FakeResponse(b"not json")

    monkeypatch.setattr("medha.lesson.client.urlopen", fake_urlopen)
    client = OllamaClient(model="test")
    with pytest.raises(OllamaError, match="invalid JSON"):
        client.chat([{"role": "user", "content": "hello"}])
