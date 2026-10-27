"""Ingestion orchestration and normalized JSON cache."""

from __future__ import annotations

import hashlib
from pathlib import Path

import config

from .chunking import TokenCounter, chunk_document, default_token_counter
from .docling_parser import DoclingParser, IngestError, inspect_source
from .models import IngestResult, SourceInfo


def _config_key(
    source: SourceInfo,
    *,
    parser_version: str,
    ocr: bool,
    counter_name: str,
    max_tokens: int,
    overlap: int,
) -> str:
    payload = "|".join(
        (
            config.INGEST_SCHEMA_VERSION,
            config.INGEST_CACHE_VERSION,
            parser_version,
            "ocr=1" if ocr else "ocr=0",
            counter_name,
            str(max_tokens),
            str(overlap),
            source.sha256,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def cache_path(
    source: SourceInfo,
    *,
    parser_version: str,
    ocr: bool,
    counter_name: str,
    max_tokens: int,
    overlap: int,
    cache_dir: Path | None = None,
) -> Path:
    root = Path(cache_dir) if cache_dir is not None else config.INGEST_CACHE_DIR
    key = _config_key(
        source,
        parser_version=parser_version,
        ocr=ocr,
        counter_name=counter_name,
        max_tokens=max_tokens,
        overlap=overlap,
    )
    return root / f"{source.sha256[:12]}-{key}.json"


def _load_cache(path: Path, source: SourceInfo) -> IngestResult | None:
    if not path.is_file():
        return None
    try:
        result = IngestResult.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if result.document.source.sha256 != source.sha256:
        return None
    return result


def _write_cache(path: Path, result: IngestResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def ingest_file(
    path: Path,
    *,
    ocr: bool | None = None,
    use_cache: bool = True,
    cache_dir: Path | None = None,
    counter: TokenCounter | None = None,
    parser: DoclingParser | None = None,
    max_tokens: int | None = None,
    overlap: int | None = None,
) -> IngestResult:
    source = inspect_source(path)
    token_counter = counter or default_token_counter()
    active_parser = parser or DoclingParser(ocr=ocr)
    active_ocr = active_parser.ocr if ocr is None else ocr
    limit = config.CHUNK_TOKENS if max_tokens is None else max_tokens
    overlap_tokens = config.CHUNK_OVERLAP if overlap is None else overlap
    if limit <= 0:
        raise IngestError("max_tokens must be positive")
    if overlap_tokens < 0 or overlap_tokens >= limit:
        raise IngestError("overlap must be non-negative and less than max_tokens")

    path_cache = cache_path(
        source,
        parser_version=active_parser.parser_info.version,
        ocr=active_ocr,
        counter_name=token_counter.name,
        max_tokens=limit,
        overlap=overlap_tokens,
        cache_dir=cache_dir,
    )
    if use_cache:
        cached = _load_cache(path_cache, source)
        if cached is not None:
            return cached

    document = active_parser.parse(Path(source.path), source=source)
    result = chunk_document(
        document,
        counter=token_counter,
        max_tokens=limit,
        overlap=overlap_tokens,
    )
    if use_cache:
        _write_cache(path_cache, result)
    return result
