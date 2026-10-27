"""Offline PDF/PPTX ingestion with normalized blocks and cited chunks."""

from .chunking import (
    BgeTokenCounter,
    TokenCounter,
    WhitespaceTokenCounter,
    chunk_document,
    default_token_counter,
)
from .docling_parser import (
    DoclingParser,
    IngestError,
    docling_version,
    inspect_source,
    missing_artifacts,
)
from .models import (
    BBox,
    Block,
    BlockKind,
    Chunk,
    ChunkingInfo,
    IngestDocument,
    IngestResult,
    ParserInfo,
    SourceInfo,
)
from .service import cache_path, ingest_file

__all__ = [
    "BBox",
    "BgeTokenCounter",
    "Block",
    "BlockKind",
    "Chunk",
    "ChunkingInfo",
    "DoclingParser",
    "IngestDocument",
    "IngestError",
    "IngestResult",
    "ParserInfo",
    "SourceInfo",
    "TokenCounter",
    "WhitespaceTokenCounter",
    "cache_path",
    "chunk_document",
    "default_token_counter",
    "docling_version",
    "ingest_file",
    "inspect_source",
    "missing_artifacts",
]
