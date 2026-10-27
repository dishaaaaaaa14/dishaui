"""Contracts for retrieval hits and index/query results."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RetrievedChunk(StrictModel):
    chunk_id: str
    doc_id: str
    text: str
    citation: str
    source: str
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    heading_path: list[str] = Field(default_factory=list)
    token_count: int = Field(ge=0)
    vector_score: float
    rerank_score: float | None = None
    score: float


class IndexReport(StrictModel):
    doc_id: str
    indexed: int = Field(ge=0)
    removed: int = Field(ge=0)
    collection_count: int = Field(ge=0)


class QueryResult(StrictModel):
    query: str
    hits: list[RetrievedChunk]
    candidate_count: int = Field(ge=0)
    reranked: bool
    embedder: str
    reranker: str | None = None


class CollectionStats(StrictModel):
    count: int = Field(ge=0)
    collection: str
