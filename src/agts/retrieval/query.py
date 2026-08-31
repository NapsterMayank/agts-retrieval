"""What a retriever actually searches for (R-049).

A learner who types `endothermic reactions` is asking the same question as one
who writes *"What are endothermic reactions?"*, and the gate answered the second
far more often than the first — 82% against 56%. The short query is not worse,
it is thinner: a full sentence carries the subject along with the question, and
four words do not.

The plan already knows what the four words left out. It has the grade and the
subject, because a learner asking from a Class 10 science lesson is asking inside
that scope whether or not they say so. Composing them back is free, deterministic
and needs no model.

**It is not query rewriting.** Nothing is reworded, dropped or guessed at — the
learner's words survive intact with their context restored in front. A rewriter
that changed the words would need to be measured for changing the meaning; this
cannot change the meaning, because the meaning was already scoped by the plan.

Measured before adoption: acceptance rose from 81/109 to 90/109 on the visible
set with **31/31 refusals unchanged**, and short-form acceptance rose from 59% to
76%. On the holdout, 34/40 answered against 33/40, with refusal at 24/24.
"""

from __future__ import annotations

from agts.contracts.runtime import QueryPlan


def search_query(plan: QueryPlan) -> str:
    """The learner's words, with the scope their sentence would have carried.

    Deliberately the *plan's* curriculum rather than anything inferred from the
    corpus: the scope is what the caller asked within, and a retriever inventing
    a broader one would be answering a question nobody asked.
    """
    # An empty question stays empty. Scope alone is not a question, and without
    # this an empty query would match on "class 10 science" and return content
    # to someone who asked nothing -- caught by the test that already existed
    # for the unscoped path.
    if not plan.query_text.strip():
        return ""

    curriculum = plan.curriculum
    return f"class {curriculum.grade} {curriculum.subject}, {plan.query_text}"
