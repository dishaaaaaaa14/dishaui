from __future__ import annotations

import pytest

from medha.ingest.chunking import WhitespaceTokenCounter, chunk_document
from medha.ingest.models import Block, IngestDocument, ParserInfo, SourceInfo


def make_document(blocks: list[Block]) -> IngestDocument:
    sha = "b" * 64
    return IngestDocument(
        schema_version="1.0.0",
        doc_id=sha,
        source=SourceInfo(
            path="C:/docs/sample.pdf",
            filename="sample.pdf",
            sha256=sha,
            format="pdf",
            bytes=100,
        ),
        parser=ParserInfo(version="test", schema_version="1.0.0"),
        title="Sample",
        page_count=max((block.page_no or 0 for block in blocks), default=0),
        locator_kind="page",
        blocks=blocks,
    )


def block(
    ordinal: int,
    text: str,
    *,
    page: int = 1,
    kind: str = "paragraph",
    heading: list[str] | None = None,
    markdown: str | None = None,
) -> Block:
    return Block(
        block_id=f"{'b' * 12}-b{ordinal:04d}",
        ordinal=ordinal,
        kind=kind,  # type: ignore[arg-type]
        text=text,
        markdown=markdown,
        page_no=page,
        locator_kind="page",
        heading_path=heading or [],
    )


def test_chunks_respect_limit_and_overlap() -> None:
    document = make_document(
        [
            block(
                0,
                "alpha beta gamma. delta epsilon zeta. eta theta iota. kappa lambda mu.",
            )
        ]
    )
    result = chunk_document(
        document,
        counter=WhitespaceTokenCounter(),
        max_tokens=7,
        overlap=3,
    )
    assert len(result.chunks) > 1
    assert all(chunk.token_count <= 7 for chunk in result.chunks)
    assert result.chunks[1].text.startswith("delta epsilon zeta")
    assert result.chunks[0].text.endswith("delta epsilon zeta.")


def test_table_chunks_repeat_header() -> None:
    markdown = (
        "| Quantity | Symbol | Unit |\n"
        "|---|---|---|\n"
        "| Force | F | newton |\n"
        "| Mass | m | kilogram |"
    )
    document = make_document(
        [block(0, markdown, kind="table", markdown=markdown, heading=["Quantities"])]
    )
    result = chunk_document(
        document,
        counter=WhitespaceTokenCounter(),
        max_tokens=20,
        overlap=0,
    )
    assert len(result.chunks) == 2
    assert all("Quantity" in chunk.text and "Symbol" in chunk.text for chunk in result.chunks)
    assert all(chunk.token_count <= 20 for chunk in result.chunks)
    assert all(chunk.heading_path == ["Quantities"] for chunk in result.chunks)


def test_page_range_and_citation() -> None:
    document = make_document(
        [
            block(0, "Alpha beta.", page=1, heading=["Lesson"]),
            block(1, "Gamma delta.", page=2, heading=["Lesson"]),
        ]
    )
    result = chunk_document(
        document,
        counter=WhitespaceTokenCounter(),
        max_tokens=50,
        overlap=0,
    )
    assert len(result.chunks) == 1
    chunk = result.chunks[0]
    assert chunk.page_start == 1
    assert chunk.page_end == 2
    assert "sample.pdf" in chunk.citation
    assert "pages 1-2" in chunk.citation
    assert "Lesson" in chunk.citation


def test_stable_ids_and_empty_document() -> None:
    document = make_document([block(0, "Stable text.")])
    first = chunk_document(
        document, counter=WhitespaceTokenCounter(), max_tokens=10, overlap=0
    )
    second = chunk_document(
        document, counter=WhitespaceTokenCounter(), max_tokens=10, overlap=0
    )
    assert [chunk.chunk_id for chunk in first.chunks] == [
        chunk.chunk_id for chunk in second.chunks
    ]
    empty = chunk_document(make_document([]), counter=WhitespaceTokenCounter())
    assert empty.chunks == []


def test_invalid_overlap() -> None:
    with pytest.raises(ValueError):
        chunk_document(make_document([]), max_tokens=4, overlap=4)
    with pytest.raises(ValueError):
        chunk_document(make_document([]), max_tokens=0, overlap=0)
