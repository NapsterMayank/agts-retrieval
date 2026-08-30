"""Platform adapters. No provider name appears outside this package."""

from .embedding import (
    CachedEmbedding,
    DeterministicEmbedding,
    EmbeddingPort,
    VoyageEmbedding,
    cosine,
)
from .reranking import CachedReranker, IdentityReranker, RerankPort, VoyageReranker

__all__ = [
    "CachedEmbedding",
    "CachedReranker",
    "DeterministicEmbedding",
    "EmbeddingPort",
    "IdentityReranker",
    "RerankPort",
    "VoyageEmbedding",
    "VoyageReranker",
    "cosine",
]
