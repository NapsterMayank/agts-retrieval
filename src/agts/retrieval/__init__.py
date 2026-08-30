"""Retrieval fabric (build guide §7.3, §8).

Owns the search representations and the retrievers over them. It does not own
the ruler: a retrieval change that also edits `agts/evaluation/scorer.py` is
marking its own homework (`docs/02-workstreams.md`).
"""

from .bm25 import BM25Representations
from .chunking import REPRESENTATION_VERSION, represent, represent_all
from .dense import DenseRetriever, HybridRetriever
from .lexical import RepresentationKeyword

__all__ = [
    "REPRESENTATION_VERSION",
    "BM25Representations",
    "DenseRetriever",
    "HybridRetriever",
    "RepresentationKeyword",
    "represent",
    "represent_all",
]
