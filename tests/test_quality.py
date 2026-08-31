"""Whether extracted evidence is usable by a learner (R-008)."""

from __future__ import annotations

from agts.contracts.common import BlockType
from agts.contracts.objects import Region, SourceBlock
from agts.parsing.quality import is_unusable, readable_text, unusable_formulas


def formula(text: str, block_type=BlockType.FORMULA) -> SourceBlock:
    return SourceBlock(
        block_id=f"d:docling:texts-{abs(hash(text)) % 999}", source_id="s", document_id="d",
        order_index=0, block_type=block_type,
        region=Region(page=1, x=0.1, y=0.1, width=0.5, height=0.05),
        text=text, parse_strategy="docling", parser_version="1",
    )


def test_the_case_an_outside_reviewer_found() -> None:
    """The chapter answers "what is the quadratic formula", the retrieval found
    the right block, the citation resolved -- and this is what a learner would
    have been shown."""
    assert is_unusable("2 4 , 2 b b ac a    provided b 2 - 4 ac")


def test_a_chemical_equation_survives_extraction() -> None:
    """Chemistry degrades far better than algebra, and the arrow is why."""
    assert not is_unusable("2FeSO 4 (s) Heat -> Fe 2 O3 (s) + SO 2 (g) + SO 3 (g)")
    assert not is_unusable("CaO(s) + H2 O(l) -> Ca(OH) 2 (aq) + Heat")


def test_an_equation_that_still_states_something_is_kept() -> None:
    """Spacing damage alone is not unusability: a reader can still follow it."""
    assert not is_unusable("3 Fe + 4 H 2 O -> Fe 3 O4 + 4 H 2")
    assert not is_unusable("b 2 - 4 ac = (- 4) 2 - (4 x 2 x 3) = 16 - 24 = - 8 < 0")


def test_a_short_formula_is_terse_rather_than_broken() -> None:
    assert not is_unusable("x = 5")
    assert not is_unusable("a b c")


def test_empty_text_is_unusable() -> None:
    assert is_unusable(None)
    assert is_unusable("")


def test_only_formula_blocks_are_judged() -> None:
    """Prose full of short words is not a broken formula."""
    blocks = [
        formula("2 4 , 2 b b ac a provided b 2 - 4 ac"),
        formula("a b c d e f g h", block_type=BlockType.PARAGRAPH),
    ]
    found = unusable_formulas(blocks)
    assert len(found) == 1
    assert found[0].block_type is BlockType.FORMULA


def test_a_relation_with_nothing_after_it_does_not_excuse_loose_text() -> None:
    """The recovered quadratic formula, and why the excuse had to be narrowed.

    `is_unusable` lets a high proportion of single-character tokens pass when
    the text carries a relation, because a chemical equation legitimately looks
    like that. Searching for the symbol anywhere excused this: the block ends
    `... b 2 - 4 ac >=`, where the relation is the final character and relates
    nothing. It was ruled usable, so `readable_text` kept it and the correct
    LaTeX beside it went unread -- R-037 returning through a different door.

    A trailing relation is evidence the extraction stopped, not that it
    survived. Three blocks in the chapter change under this rule and all three
    carry verified LaTeX; no chemistry block changes at all.
    """
    degraded = "2 4 , 2 b b ac a − ± − provided b 2 - 4 ac ≥"
    latex = r"rac{-b \pm \sqrt{b^2 - 4ac}}{2a}, 	ext{ provided } b^2 - 4ac \geq 0."

    assert is_unusable(degraded)
    assert readable_text(degraded, latex) == latex


def test_a_relation_with_operands_on_both_sides_still_excuses_it() -> None:
    """Otherwise every chemical equation in the corpus becomes a backlog item."""
    assert not is_unusable("Mg + O 2 → MgO")
    assert not is_unusable("Zn + H 2 SO 4 → ZnSO 4 + H 2")


def test_text_is_kept_when_there_is_no_latex() -> None:
    assert readable_text("Mg + O 2 -> MgO", None) == "Mg + O 2 -> MgO"
