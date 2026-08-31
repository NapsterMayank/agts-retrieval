"""The scope a short question leaves out (R-049)."""

from __future__ import annotations

from agts.evaluation.cases import EvalCase
from agts.evaluation.planning import plan_for_case
from agts.retrieval.query import search_query


def plan_for(query: str, grade: str = "10", subject: str = "science"):
    return plan_for_case(EvalCase(
        case_id="c", query=query, grade=grade, subject=subject,
        question_type="definition", teaching_action="explain",
        concept_ids=["c"], gold_block_ids=["b"],
    ))


def test_the_learners_words_survive_intact() -> None:
    """Not query rewriting: nothing is reworded, dropped or guessed at."""
    assert "endothermic reactions" in search_query(plan_for("endothermic reactions"))


def test_the_scope_comes_from_the_plan_not_the_corpus() -> None:
    """A retriever inventing a broader scope would answer a question nobody asked."""
    assert search_query(plan_for("x", grade="9", subject="mathematics")).startswith(
        "class 9 mathematics,"
    )


def test_two_subjects_produce_two_different_searches() -> None:
    """The same four words mean different things in two chapters, which is the
    whole reason the scope is restored."""
    assert search_query(plan_for("solution", subject="science")) != search_query(
        plan_for("solution", subject="mathematics")
    )


def test_an_empty_question_stays_empty() -> None:
    """Scope alone is not a question. Without this, asking nothing returns
    whatever best matches "class 10 science"."""
    assert search_query(plan_for("   ").model_copy(update={"query_text": "   "})) == ""
