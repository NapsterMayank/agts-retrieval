"""The evaluation licence, and every way around it that must not work.

A permission that widens the §5 authorisation boundary is only safe if its edges
are tested harder than its happy path. These tests are mostly about what stays
excluded.
"""

from __future__ import annotations

from datetime import date

import pytest

from agts.contracts.common import ApprovalState
from agts.evaluation.corpus import Corpus, EvaluationLicence
from agts.evaluation.fixtures import build_corpus, build_gold_set
from agts.evaluation.planning import plan_for_case
from agts.evaluation.retrievers import KeywordBaseline
from agts.evaluation.scorer import score


LICENCE = EvaluationLicence(
    reason="first real-content run, quarantined pending rights records (Q3)",
    granted_by="mayank",
    granted_on=date(2026, 8, 30),
    source_ids=("s-quarantined",),
)


@pytest.fixture()
def plan():
    return plan_for_case(build_gold_set().visible[0])


def licensed_corpus(**overrides) -> Corpus:
    base = build_corpus()
    return Corpus(
        sources=overrides.get("sources", base.sources),
        blocks=base.blocks,
        objects=base.objects,
        evaluation_licence=overrides.get("licence", LICENCE),
    )


def test_quarantined_content_is_excluded_without_a_licence(plan) -> None:
    corpus = build_corpus()
    assert corpus.evaluation_licence is None
    assert "o-quarantined" not in {o.object_id for o in corpus.authorised(plan)}


def test_a_licence_admits_only_the_sources_it_names(plan) -> None:
    admitted = {o.object_id for o in licensed_corpus().authorised(plan)}
    assert "o-quarantined" in admitted


def test_a_licence_for_another_source_admits_nothing(plan) -> None:
    licence = EvaluationLicence(
        reason="a different chapter entirely",
        granted_by="mayank",
        granted_on=date(2026, 8, 30),
        source_ids=("s-some-other-source",),
    )
    admitted = {o.object_id for o in licensed_corpus(licence=licence).authorised(plan)}
    assert "o-quarantined" not in admitted


def test_a_licence_cannot_be_blanket() -> None:
    with pytest.raises(ValueError):
        EvaluationLicence(reason="r", granted_by="g", granted_on=date(2026, 8, 30), source_ids=())


def test_a_licence_must_say_who_granted_it_and_why() -> None:
    with pytest.raises(ValueError):
        EvaluationLicence(reason="  ", granted_by="g", granted_on=date(2026, 8, 30), source_ids=("s",))
    with pytest.raises(ValueError):
        EvaluationLicence(reason="r", granted_by="", granted_on=date(2026, 8, 30), source_ids=("s",))


def test_a_withdrawn_source_stays_excluded_even_when_named(plan) -> None:
    """Withdrawal is the mechanism a rights holder has. An evaluation run is not
    a reason to ignore it, so the licence deliberately unlocks QUARANTINED only."""
    base = build_corpus()
    withdrawn = base.sources["s-quarantined"].model_copy(
        update={"approval_state": ApprovalState.WITHDRAWN}
    )
    corpus = licensed_corpus(sources={**base.sources, "s-quarantined": withdrawn})
    assert "o-quarantined" not in {o.object_id for o in corpus.authorised(plan)}


def test_a_licence_does_not_widen_any_other_filter(plan) -> None:
    """Grade, tenant and disclosure filters are untouched: the licence answers
    'may this source be measured', never 'may this learner see it'."""
    admitted = {o.object_id for o in licensed_corpus().authorised(plan)}
    assert not any(oid.startswith("o-g7-") for oid in admitted)      # wrong grade
    assert "o-other-tenant" not in admitted                          # other tenant
    assert not any(oid.startswith("o-sol-") for oid in admitted)     # solution disclosure


def test_a_licensed_run_does_not_report_unapproved_source_violations() -> None:
    """Otherwise the counter fires on every object of every real-content run and
    stops carrying the signal it exists for."""
    report = score(build_gold_set(), KeywordBaseline(), licensed_corpus())
    assert report.violations.unapproved_source == 0


def test_a_licensed_report_says_so_in_its_summary() -> None:
    report = score(build_gold_set(), KeywordBaseline(), licensed_corpus())
    assert report.evaluation_licence == LICENCE.reason
    assert "evaluation licence" in report.summary()


def test_an_unlicensed_report_carries_no_licence_marker() -> None:
    report = score(build_gold_set(), KeywordBaseline(), build_corpus())
    assert report.evaluation_licence is None
    assert "evaluation licence" not in report.summary()
