from __future__ import annotations

import json
from pathlib import Path

import config

ROOT = Path(__file__).resolve().parents[1]


def load_lock() -> dict:
    return json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))


def test_lock_entries_are_complete() -> None:
    lock = load_lock()
    assert lock["entries"]
    for entry in lock["entries"]:
        assert entry["id"]
        assert entry["job"]
        assert entry["profiles"]
        assert entry["license"]
        source = entry["source"]
        if source["type"] == "hf":
            assert source["repo"]
            assert len(source["revision"]) >= 7
        elif source["type"] == "ollama":
            assert ":" in source["model"]
        else:
            raise AssertionError(f"unknown source type: {source['type']}")


def test_license_sidecars_exist() -> None:
    lock = load_lock()
    for entry in lock["entries"]:
        license_file = entry.get("license_file")
        assert license_file, entry["id"]
        assert (config.LICENSES_DIR / license_file).exists(), license_file


def test_not_shipped_models_are_not_entries() -> None:
    lock = load_lock()
    entry_ids = {entry["id"] for entry in lock["entries"]}
    for item in lock["not_shipped"]:
        assert item["id"] not in entry_ids
        assert item["reason"]


def test_indic_models_are_gated() -> None:
    lock = load_lock()
    gated = {entry["id"]: entry["gated"] for entry in lock["entries"]}
    assert gated["indic-parler-tts"] is True
    assert gated["indictrans2-en-indic-dist-200M"] is True


def test_default_model_is_qwen3_instruct() -> None:
    lock = load_lock()
    qwen = next(e for e in lock["entries"] if e["id"] == "qwen3-4b-instruct-2507")
    assert "instruct" in qwen["source"]["model"]
    assert qwen["license"] == "Apache-2.0"
