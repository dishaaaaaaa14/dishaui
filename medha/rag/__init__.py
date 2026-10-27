"""Offline embeddings, Chroma indexing, and cited retrieval."""

from .embeddings import BgeM3Embedder, Embedder
from .errors import RagError
from .models import CollectionStats, IndexReport, QueryResult, RetrievedChunk
from .reranker import BgeReranker, Reranker
from .service import ChunkStore, RagService
from .store import ChromaStore, StoreHit

__all__ = [
    "BgeM3Embedder",
    "BgeReranker",
    "ChromaStore",
    "ChunkStore",
    "CollectionStats",
    "Embedder",
    "IndexReport",
    "QueryResult",
    "RagError",
    "RagService",
    "Reranker",
    "RetrievedChunk",
    "StoreHit",
]
