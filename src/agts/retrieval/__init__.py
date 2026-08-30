"""Retrieval fabric (build guide sections 7.3 and 8).

Owns the search representations and the retrievers over them. It does not own
the ruler: a retrieval change that also edits `agts/evaluation/scorer.py` is
marking its own homework (`docs/02-workstreams.md`).
"""

from .bm25 import BM25Representations
from .chunking import REPRESENTATION_VERSION, represent, represent_all
from .dense import DenseRetriever, HybridRetriever
from .lexical import RepresentationKeyword
from .provenance import build_manifest, build_trace, corpus_checksum, lineage_failures
from .rerank import RerankedRetriever

__all__ = [
    "REPRESENTATION_VERSION",
    "BM25Representations",
    "DenseRetriever",
    "HybridRetriever",
    "RepresentationKeyword",
    "RerankedRetriever",
    "build_manifest",
    "build_trace",
    "corpus_checksum",
    "lineage_failures",
    "represent",
    "represent_all",
]
