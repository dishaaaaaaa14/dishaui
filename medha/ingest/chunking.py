"""Token-aware chunking with citations and bounded overlap."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import config

from .models import (
    Block,
    Chunk,
    ChunkingInfo,
    IngestDocument,
    IngestResult,
)

_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$")


class TokenCounter(Protocol):
    name: str

    def count(self, text: str) -> int: ...


class WhitespaceTokenCounter:
    name = "whitespace"

    def count(self, text: str) -> int:
        return len(text.split())


class BgeTokenCounter:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or config.CHUNK_TOKENIZER_PATH)
        self.name = "bge-m3"
        self._tokenizer: Any = None
        if not self.path.is_file():
            raise FileNotFoundError(f"tokenizer missing: {self.path}")

    def _load(self) -> Any:
        if self._tokenizer is None:
            from tokenizers import Tokenizer

            self._tokenizer = Tokenizer.from_file(str(self.path))
        return self._tokenizer

    def count(self, text: str) -> int:
        tokenizer = self._load()
        encoding = tokenizer.encode(text, add_special_tokens=False)
        return len(encoding.ids)


def default_token_counter() -> TokenCounter:
    try:
        return BgeTokenCounter()
    except (ImportError, OSError):
        return WhitespaceTokenCounter()


@dataclass(frozen=True)
class Segment:
    text: str
    block_id: str
    page_no: int | None
    heading_path: tuple[str, ...]


def _join(segments: list[Segment]) -> str:
    return "\n".join(segment.text for segment in segments).strip()


def _split_oversized(
    text: str,
    *,
    counter: TokenCounter,
    max_tokens: int,
) -> list[str]:
    words = text.split()
    if not words:
        return []
    pieces: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and counter.count(candidate) > max_tokens:
            pieces.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        pieces.append(" ".join(current))
    return pieces


def _segments_for_block(
    block: Block,
    *,
    counter: TokenCounter,
    max_tokens: int,
) -> list[Segment]:
    path = tuple(block.heading_path)
    if block.kind == "table":
        markdown = block.markdown or block.text
        lines = [line for line in markdown.splitlines() if line.strip()]
        if not lines:
            return []
        if counter.count(markdown) <= max_tokens:
            return [Segment(markdown, block.block_id, block.page_no, path)]
        header: list[str] = []
        rows = lines
        if len(lines) >= 2 and _TABLE_SEPARATOR_RE.match(lines[1]):
            header = lines[:2]
            rows = lines[2:]
        segments: list[Segment] = []
        for row in rows:
            row_text = "\n".join([*header, row]) if header else row
            if counter.count(row_text) <= max_tokens:
                segments.append(Segment(row_text, block.block_id, block.page_no, path))
                continue
            for piece in _split_oversized(row_text, counter=counter, max_tokens=max_tokens):
                segments.append(Segment(piece, block.block_id, block.page_no, path))
        return segments

    text = block.text.strip()
    if not text:
        return []
    parts = [part.strip() for part in _SPLIT_RE.split(text) if part.strip()]
    if len(parts) == 1:
        parts = [text]
    segments = []
    for part in parts:
        if counter.count(part) <= max_tokens:
            segments.append(Segment(part, block.block_id, block.page_no, path))
            continue
        for piece in _split_oversized(part, counter=counter, max_tokens=max_tokens):
            segments.append(Segment(piece, block.block_id, block.page_no, path))
    return segments


def _tail(segments: list[Segment], *, counter: TokenCounter, overlap: int) -> list[Segment]:
    if overlap <= 0:
        return []
    tail: list[Segment] = []
    for segment in reversed(segments):
        candidate = [segment, *tail]
        if counter.count(_join(candidate)) > overlap:
            break
        tail = candidate
    return tail


def _citation(document: IngestDocument, start: int | None, end: int | None, path: list[str]) -> str:
    name = document.source.filename
    if start is None:
        location = "location unknown"
    elif start == end or end is None:
        location = f"{document.locator_kind} {start}"
    else:
        location = f"{document.locator_kind}s {start}-{end}"
    if path:
        location += " > " + " > ".join(path)
    return f"{name}, {location}"


def _make_chunk(
    document: IngestDocument,
    segments: list[Segment],
    ordinal: int,
    *,
    counter: TokenCounter,
) -> Chunk | None:
    text = _join(segments)
    if not text:
        return None
    pages = [segment.page_no for segment in segments if segment.page_no is not None]
    page_start = min(pages) if pages else None
    page_end = max(pages) if pages else None
    block_ids: list[str] = []
    for segment in segments:
        if segment.block_id not in block_ids:
            block_ids.append(segment.block_id)
    heading_path = list(segments[0].heading_path)
    return Chunk(
        chunk_id=f"{document.doc_id[:12]}-c{ordinal:04d}",
        doc_id=document.doc_id,
        ordinal=ordinal,
        text=text,
        token_count=counter.count(text),
        block_ids=block_ids,
        page_start=page_start,
        page_end=page_end,
        locator_kind=document.locator_kind,
        heading_path=heading_path,
        citation=_citation(document, page_start, page_end, heading_path),
    )


def chunk_document(
    document: IngestDocument,
    *,
    counter: TokenCounter | None = None,
    max_tokens: int | None = None,
    overlap: int | None = None,
) -> IngestResult:
    token_counter = counter or default_token_counter()
    limit = config.CHUNK_TOKENS if max_tokens is None else max_tokens
    overlap_tokens = config.CHUNK_OVERLAP if overlap is None else overlap
    if limit <= 0:
        raise ValueError("max_tokens must be positive")
    if overlap_tokens < 0 or overlap_tokens >= limit:
        raise ValueError("overlap must be non-negative and less than max_tokens")

    segments: list[Segment] = []
    for block in document.blocks:
        segments.extend(
            _segments_for_block(block, counter=token_counter, max_tokens=limit)
        )

    chunks: list[Chunk] = []
    current: list[Segment] = []
    for segment in segments:
        if not current:
            current = [segment]
            continue
        candidate = [*current, segment]
        if token_counter.count(_join(candidate)) <= limit:
            current = candidate
            continue

        chunk = _make_chunk(document, current, len(chunks), counter=token_counter)
        if chunk is not None:
            chunks.append(chunk)
        tail = _tail(current, counter=token_counter, overlap=overlap_tokens)
        while tail and token_counter.count(_join([*tail, segment])) > limit:
            tail = tail[1:]
        current = [*tail, segment]

    if current:
        chunk = _make_chunk(document, current, len(chunks), counter=token_counter)
        if chunk is not None:
            chunks.append(chunk)

    return IngestResult(
        document=document,
        chunks=chunks,
        chunking=ChunkingInfo(
            tokenizer=token_counter.name,
            max_tokens=limit,
            overlap=overlap_tokens,
        ),
    )
