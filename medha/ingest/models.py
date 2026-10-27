"""Normalized document and chunk contracts for material ingestion."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BlockKind = Literal[
    "title",
    "heading",
    "paragraph",
    "list",
    "table",
    "formula",
    "caption",
    "footnote",
    "code",
    "picture",
    "other",
]
LocatorKind = Literal["page", "slide"]
SourceFormat = Literal["pdf", "pptx"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceInfo(StrictModel):
    path: str
    filename: str
    sha256: str
    format: SourceFormat
    bytes: int = Field(ge=1)


class ParserInfo(StrictModel):
    name: str = "docling"
    version: str
    schema_version: str


class BBox(StrictModel):
    left: float
    top: float
    right: float
    bottom: float


class Block(StrictModel):
    block_id: str
    ordinal: int = Field(ge=0)
    kind: BlockKind
    text: str
    markdown: str | None = None
    page_no: int | None = Field(default=None, ge=1)
    locator_kind: LocatorKind | None = None
    heading_path: list[str] = Field(default_factory=list)
    level: int | None = Field(default=None, ge=0)
    bbox: BBox | None = None


class IngestDocument(StrictModel):
    schema_version: str
    doc_id: str
    source: SourceInfo
    parser: ParserInfo
    title: str
    page_count: int = Field(ge=0)
    locator_kind: LocatorKind
    blocks: list[Block]
    warnings: list[str] = Field(default_factory=list)


class Chunk(StrictModel):
    chunk_id: str
    doc_id: str
    ordinal: int = Field(ge=0)
    text: str
    token_count: int = Field(ge=0)
    block_ids: list[str]
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    locator_kind: LocatorKind
    heading_path: list[str] = Field(default_factory=list)
    citation: str


class ChunkingInfo(StrictModel):
    tokenizer: str
    max_tokens: int = Field(gt=0)
    overlap: int = Field(ge=0)


class IngestResult(StrictModel):
    document: IngestDocument
    chunks: list[Chunk]
    chunking: ChunkingInfo
