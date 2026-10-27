from __future__ import annotations

from pathlib import Path

import pytest

from medha.rag import BgeM3Embedder, RagError


def test_empty_input_needs_no_model(tmp_path: Path) -> None:
    embedder = BgeM3Embedder(
        model_path=tmp_path / "missing.onnx",
        tokenizer_path=tmp_path / "missing.json",
    )
    assert embedder.embed([]) == []
    with pytest.raises(RagError, match="empty"):
        embedder.embed(["   "])
    with pytest.raises(RagError, match="missing"):
        embedder.embed(["force"])


def test_dimension_contract() -> None:
    embedder = BgeM3Embedder()
    assert embedder.name == "bge-m3-onnx"
    assert embedder.dimension == 1024
