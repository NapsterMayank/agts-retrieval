"""Evaluation spine. Built before retrieval is optimised (rule 1)."""

from .cases import EvalCase, GoldSet
from .corpus import Corpus
from .planning import SLOTS_BY_ACTION, plan_for_case
from .retrievers import (
    AnswerOnly,
    CrossTenant,
    KeywordBaseline,
    RandomRanking,
    RetrievedItem,
    Retriever,
    WrongGrade,
    broken_retrievers,
)
from .scorer import (
    GATING_MIN_N,
    PROVISIONAL_ABSTAIN_THRESHOLD,
    AbstentionCalibration,
    CaseResult,
    InvariantViolations,
    ScoreReport,
    SliceScore,
    calibrate_abstention,
    score,
    score_case,
)

__all__ = [
    "GATING_MIN_N",
    "PROVISIONAL_ABSTAIN_THRESHOLD",
    "SLOTS_BY_ACTION",
    "AbstentionCalibration",
    "AnswerOnly",
    "CaseResult",
    "calibrate_abstention",
    "Corpus",
    "CrossTenant",
    "EvalCase",
    "GoldSet",
    "InvariantViolations",
    "KeywordBaseline",
    "RandomRanking",
    "RetrievedItem",
    "Retriever",
    "ScoreReport",
    "SliceScore",
    "WrongGrade",
    "broken_retrievers",
    "plan_for_case",
    "score",
    "score_case",
]
