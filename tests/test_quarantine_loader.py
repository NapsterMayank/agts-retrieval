"""The quarantine loader, against the artefacts actually on disk."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from agts.contracts.common import ApprovalState
from agts.evaluation.cases import load_gold_set
from agts.evaluation.corpus import EvaluationLicence
from agts.evaluation.quarantine import ChapterArtefact, load_corpus


ARTIFACTS = Path(__file__).parents[1] / "artifacts"

CHAPTERS = [
    ChapterArtefact(
        directory=ARTIFACTS / "chemical-reactions-quarantine",
        title="Chemical Reactions and Equations",
        publisher="NCERT",
        edition="Science, Class X, 2026-27",
    ),
    ChapterArtefact(
        directory=ARTIFACTS / "quadratic-equations-quarantine",
        title="Quadratic Equations",
        publisher="NCERT",
        edition="Mathematics, Class X, 2026-27",
    ),
]

pytestmark = pytest.mark.skipif(
    not all((c.directory / "learning-objects.jsonl").exists() for c in CHAPTERS),
    reason="chapter artefacts not present; run the assemble and compose scripts",
)


@pytest.fixture(scope="module")
def licence() -> EvaluationLicence:
    return EvaluationLicence(
        reason="test",
        granted_by="tests",
        granted_on=date(2026, 8, 30),
        source_ids=tuple(c.manifest()["source_id"] for c in CHAPTERS),
    )


def test_artefact_sources_load_as_quarantined(licence) -> None:
    corpus = load_corpus(CHAPTERS, licence=licence)
    assert corpus.sources
    assert all(
        s.approval_state is ApprovalState.QUARANTINED for s in corpus.sources.values()
    )


def test_block_ids_are_unique_across_both_chapters(licence) -> None:
    """A gold label is a block id (rule 4). Ids that collide across collections
    or across chapters silently drop blocks from the corpus - R-012."""
    corpus = load_corpus(CHAPTERS, licence=licence)
    on_disk = sum(len(chapter.blocks()) for chapter in CHAPTERS)
    assert len(corpus.blocks) == on_disk


def test_loading_a_source_the_licence_does_not_name_is_refused() -> None:
    narrow = EvaluationLicence(
        reason="one chapter only",
        granted_by="tests",
        granted_on=date(2026, 8, 30),
        source_ids=(CHAPTERS[0].manifest()["source_id"],),
    )
    with pytest.raises(ValueError):
        load_corpus(CHAPTERS, licence=narrow)


def test_every_gold_label_resolves_to_a_block_in_some_object(licence) -> None:
    """Two failures a recall number cannot tell apart from bad retrieval: a gold
    id that does not exist, and a gold block no learning object contains."""
    corpus = load_corpus(CHAPTERS, licence=licence)
    gold_set = load_gold_set(ARTIFACTS / "gold" / "pilot-2-chapters-v0.json")
    composed = {bid for obj in corpus.objects.values() for bid in obj.block_ids}

    for case in gold_set.cases:
        for block_id in case.gold_block_ids:
            assert block_id in corpus.blocks, f"{case.case_id}: no such block {block_id}"
            assert block_id in composed, f"{case.case_id}: {block_id} is in no object"
