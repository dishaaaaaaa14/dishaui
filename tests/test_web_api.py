"""Smoke tests for the Medha web API using the bundled sample lesson."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import config
from medha.web.app import create_app

SAMPLE = config.SPEC_DIR / "board-action" / "v1" / "examples" / "newton.json"


@pytest.fixture()
def client() -> TestClient:
    config.ensure_dirs()
    return TestClient(create_app())


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_open_sample_and_frame(client: TestClient) -> None:
    if not SAMPLE.is_file() and not (config.LESSON_CONTENT_DIR / "newton.json").is_file():
        pytest.skip("sample lesson missing")
    response = client.post("/api/lessons/open", json={"tts": False})
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    for _ in range(50):
        status = client.get(f"/api/sessions/{session_id}").json()
        if status["state"] in {"ready", "error"}:
            break
        import time

        time.sleep(0.1)
    assert status["state"] == "ready", status.get("error")
    assert status["duration_ms"] > 0
    assert status["title"]

    frame = client.get(f"/api/sessions/{session_id}/frame", params={"t": 5000})
    assert frame.status_code == 200
    body = frame.json()
    assert body["t"] == 5000
    assert len(body["strokes"]) > 0
    stroke = body["strokes"][0]
    assert len(stroke["points"]) >= 2
    assert stroke["color"].startswith("#")


def test_library_list(client: TestClient) -> None:
    response = client.get("/api/lessons")
    assert response.status_code == 200
    assert "lessons" in response.json()
