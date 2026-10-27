from __future__ import annotations

import json
from pathlib import Path

from tools import fetch_docling, fetch_models, license_audit

ROOT = Path(__file__).resolve().parents[1]


def load_lock() -> dict:
    return json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))


def test_core_entries_are_selected_for_every_profile() -> None:
    lock = load_lock()
    for entry in lock["entries"]:
        if "core" in entry["profiles"]:
            assert fetch_models.selected(entry, "demo_gpu")
            assert fetch_models.selected(entry, "cpu")
            assert fetch_models.selected(entry, "indic")


def test_profile_selection_is_specific() -> None:
    lock = load_lock()
    qwen = next(e for e in lock["entries"] if e["id"] == "qwen3-4b-instruct-2507")
    phi = next(e for e in lock["entries"] if e["id"] == "phi4-mini-3.8b")
    assert fetch_models.selected(qwen, "demo_gpu")
    assert not fetch_models.selected(qwen, "safe_gpu")
    assert fetch_models.selected(phi, "safe_gpu")


def test_license_audit_has_no_failures() -> None:
    findings = license_audit.audit_models(load_lock())
    failures = [finding for finding in findings if finding.status == "fail"]
    assert not failures, failures


def test_docling_manifest_round_trip(tmp_path: Path) -> None:
    for spec in fetch_docling.SPECS:
        for required in spec.required:
            target = tmp_path / spec.folder / required
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"artifact")
    manifest_path = tmp_path / ".medha_docling.json"
    assert fetch_docling.verify(tmp_path) == [f"manifest missing: {manifest_path}"]
    fetch_docling.write_manifest(tmp_path)
    assert fetch_docling.verify(tmp_path) == []

    missing = tmp_path / fetch_docling.SPECS[0].folder / fetch_docling.SPECS[0].required[0]
    missing.unlink()
    assert any("missing" in problem for problem in fetch_docling.verify(tmp_path))
