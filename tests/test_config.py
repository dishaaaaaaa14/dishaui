from __future__ import annotations

import config


def test_profile_is_valid() -> None:
    llm = config.active_llm()
    assert llm.key in config.LLM_PROFILES
    assert ":" in llm.model
    assert llm.num_ctx >= 2048


def test_as_dict_has_required_keys() -> None:
    summary = config.as_dict()
    for key in ("app", "schema", "profile", "llm", "embed", "vlm", "tts", "code_license"):
        assert summary[key]


def test_ensure_dirs_creates_runtime_paths() -> None:
    config.ensure_dirs()
    for directory in config.DIRECTORIES:
        assert directory.exists(), directory


def test_no_piper_or_research_models_in_profiles() -> None:
    models = " ".join(p.model for p in config.LLM_PROFILES.values()).lower()
    assert "lessac" not in models
    assert "piper" not in models
    assert "vl" not in models
