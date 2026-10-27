from __future__ import annotations

import json

import pytest

from medha import health


def test_run_all_returns_expected_checks() -> None:
    checks = health.run_all()
    names = {check.name for check in checks}
    for expected in (
        "python",
        "venv",
        "paths",
        "config",
        "model_lock",
        "licenses",
        "ollama",
        "docling_artifacts",
        "rag_artifacts",
        "image_artifacts",
    ):
        assert expected in names


def test_json_output_is_parseable(capsys: pytest.CaptureFixture[str]) -> None:
    health.main(["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert all({"name", "status", "detail", "required"} <= set(item) for item in payload)


def test_cpu_only_gpu_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health.config, "CPU_ONLY", True)
    result = health.check_gpu()
    assert result.status == "skip"


def test_compute_apps_ignores_na_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health.config, "CPU_ONLY", False)
    monkeypatch.setattr(
        health,
        "_run",
        lambda _cmd: (0, "4242, C:\\Windows\\StartMenu.exe, [N/A]"),
    )
    result = health.check_compute_apps()
    assert result.status == "ok"
