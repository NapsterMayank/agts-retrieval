"""Platform adapters. No provider name appears outside this package."""

from .embedding import (
    CachedEmbedding,
    DeterministicEmbedding,
    EmbeddingPort,
    VoyageEmbedding,
    cosine,
)

__all__ = [
    "CachedEmbedding",
    "DeterministicEmbedding",
    "EmbeddingPort",
    "VoyageEmbedding",
    "cosine",
]
