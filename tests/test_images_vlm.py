from __future__ import annotations

from pathlib import Path

import pytest

from medha.images import ImageError, SmolVlmDescriber
from medha.images.vlm import clean_description


def test_missing_vlm_artifacts_fail_fast(tmp_path: Path) -> None:
    describer = SmolVlmDescriber(model_dir=tmp_path)
    with pytest.raises(ImageError, match="artifacts are incomplete"):
        describer.check()


def test_vlm_prompt_version_is_pinned() -> None:
    describer = SmolVlmDescriber()
    assert describer.prompt_version
    assert describer.name


def test_description_truncates_at_last_sentence() -> None:
    assert clean_description("A frame. It contains F = ma. The next part is cut") == (
        "A frame. It contains F = ma."
    )
    assert clean_description("F = ma") == "F = ma"
