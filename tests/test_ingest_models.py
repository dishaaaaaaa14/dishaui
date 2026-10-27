from __future__ import annotations

import pytest
from pydantic import ValidationError

from medha.ingest.models import (
    BBox,
    Block,
    Chunk,
    ChunkingInfo,
    IngestDocument,
    IngestResult,
    ParserInfo,
    SourceInfo,
)


def make_source() -> SourceInfo:
    return SourceInfo(
        path="C:/docs/sample.pdf",
        filename="sample.pdf",
        sha256="a" * 64,
        format="pdf",
        bytes=1234,
    )


def make_document() -> IngestDocument:
    return IngestDocument(
        schema_version="1.0.0",
        doc_id="a" * 64,
        source=make_source(),
        parser=ParserInfo(version="test", schema_version="1.0.0"),
        title="Sample",
        page_count=1,
        locator_kind="page",
        blocks=[
            Block(
                block_id="a" * 12 + "-b0000",
                ordinal=0,
                kind="paragraph",
                text="Sample text.",
                page_no=1,
                locator_kind="page",
                bbox=BBox(left=0, top=0, right=1, bottom=1),
            )
        ],
    )


def test_document_round_trip() -> None:
    result = IngestResult(
        document=make_document(),
        chunks=[
            Chunk(
                chunk_id="a" * 12 + "-c0000",
                doc_id="a" * 64,
                ordinal=0,
                text="Sample text.",
                token_count=2,
                block_ids=["a" * 12 + "-b0000"],
                page_start=1,
                page_end=1,
                locator_kind="page",
                heading_path=["Sample"],
                citation="sample.pdf, page 1",
            )
        ],
        chunking=ChunkingInfo(tokenizer="test", max_tokens=450, overlap=64),
    )
    restored = IngestResult.model_validate_json(result.model_dump_json())
    assert restored == result


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Block(
            block_id="b0",
            ordinal=0,
            kind="paragraph",
            text="text",
            unexpected=True,  # type: ignore[call-arg]
        )


def test_source_rejects_unknown_format() -> None:
    with pytest.raises(ValidationError):
        SourceInfo(
            path="x",
            filename="x.docx",
            sha256="a" * 64,
            format="docx",  # type: ignore[arg-type]
            bytes=1,
        )
