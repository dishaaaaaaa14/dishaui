from __future__ import annotations

from pathlib import Path

import pytest

from medha.rag import BgeReranker, RagError


def test_empty_texts_need_no_model(tmp_path: Path) -> None:
    reranker = BgeReranker(model_dir=tmp_path / "missing")
    assert reranker.rerank("query", []) == []
    with pytest.raises(RagError, match="empty"):
        reranker.rerank("  ", ["text"])
    with pytest.raises(RagError, match="missing"):
        reranker.rerank("query", ["text"])


def test_reranker_contract() -> None:
    reranker = BgeReranker()
    assert reranker.name == "bge-reranker-v2-m3"
