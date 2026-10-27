from __future__ import annotations

from pathlib import Path

import pytest

from medha.ingest import (
    DoclingParser,
    IngestError,
    chunk_document,
    inspect_source,
    missing_artifacts,
)
from medha.ingest.models import IngestDocument

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "ingest"


@pytest.fixture(scope="module")
def parsed() -> tuple[IngestDocument, IngestDocument]:
    pytest.importorskip("docling")
    if missing_artifacts():
        pytest.skip("Docling artifacts are not prefetched")
    parser = DoclingParser()
    pdf_source = inspect_source(FIXTURES / "sample.pdf")
    pptx_source = inspect_source(FIXTURES / "sample.pptx")
    return parser.parse(FIXTURES / "sample.pdf", pdf_source), parser.parse(
        FIXTURES / "sample.pptx", pptx_source
    )


def test_pdf_blocks_and_formula(parsed: tuple[IngestDocument, IngestDocument]) -> None:
    document, _ = parsed
    assert document.source.format == "pdf"
    assert document.page_count == 2
    assert "Newton" in document.title
    assert any(block.kind == "formula" and "F" in block.text for block in document.blocks)
    assert any("Worked Example" in block.text for block in document.blocks)
    assert all(block.page_no is not None for block in document.blocks)


def test_pptx_table_and_notes(parsed: tuple[IngestDocument, IngestDocument]) -> None:
    _, document = parsed
    assert document.locator_kind == "slide"
    assert document.page_count == 3
    tables = [block for block in document.blocks if block.kind == "table"]
    assert len(tables) == 1
    assert "Quantity" in (tables[0].markdown or "")
    assert "Speaker note" not in " ".join(block.text for block in document.blocks)
    assert {block.page_no for block in document.blocks} == {1, 2, 3}


def test_chunks_have_citations(parsed: tuple[IngestDocument, IngestDocument]) -> None:
    for document in parsed:
        result = chunk_document(document)
        assert result.chunks
        assert all(chunk.token_count <= 450 for chunk in result.chunks)
        assert all(document.source.filename in chunk.citation for chunk in result.chunks)
        assert all(chunk.block_ids for chunk in result.chunks)


def test_inspect_source_rejects_unknown_format(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("not a supported document", encoding="utf-8")
    with pytest.raises(IngestError):
        inspect_source(path)


def test_inspect_source_rejects_empty(tmp_path: Path) -> None:
    path = tmp_path / "empty.pdf"
    path.write_bytes(b"")
    with pytest.raises(IngestError):
        inspect_source(path)


def test_parser_error_has_context(tmp_path: Path) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"not a real pdf")
    source = inspect_source(path)
    with pytest.raises(IngestError):
        DoclingParser().parse(path, source)


def test_picture_metadata_is_skipped(parsed: tuple[IngestDocument, IngestDocument]) -> None:
    _, document = parsed
    assert all(block.kind != "picture" for block in document.blocks)
    assert isinstance(document.warnings, list)
    assert isinstance(document.blocks[0].block_id, str)
    assert isinstance(document.parser.version, str)
