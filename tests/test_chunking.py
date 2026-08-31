"""Search representations: the four rules, and the boundary they must not cross."""

from __future__ import annotations

from agts.contracts.common import (
    ApprovalState,
    AuthorityTier,
    BlockType,
    Board,
    DisclosureClass,
    Language,
    Modality,
    ObjectType,
)
from agts.contracts.objects import (
    CurriculumIdentity,
    LearningObject,
    Region,
    SourceBlock,
)
from agts.retrieval.chunking import MAX_CHARS, represent


CURRICULUM = CurriculumIdentity(
    board=Board.CBSE,
    curriculum_version="2026-27",
    grade="10",
    subject="science",
    unit_id="u1",
    concept_ids=["c1"],
)


def block(index: int, text: str, block_type=BlockType.PARAGRAPH, linked=None) -> SourceBlock:
    return SourceBlock(
        block_id=f"doc:docling:texts-{index}",
        source_id="s1",
        document_id="doc",
        order_index=index,
        block_type=block_type,
        region=Region(page=1, x=0.1, y=0.1, width=0.5, height=0.05),
        text=text,
        parse_strategy="docling",
        parser_version="2.122.0",
        linked_block_id=linked,
    )


def obj(blocks: list[SourceBlock], heading: str = "1.2.2 Decomposition Reaction") -> LearningObject:
    return LearningObject(
        object_id="o1",
        object_type=ObjectType.EXPLANATION,
        source_id="s1",
        block_ids=[b.block_id for b in blocks],
        curriculum=CURRICULUM,
        heading_path=heading,
        text=" ".join(b.text or "" for b in blocks),
        language=Language.EN,
        modality=Modality.TEXT,
        authority_tier=AuthorityTier.BOARD_OFFICIAL,
        disclosure_class=DisclosureClass.PUBLIC,
        composition_version="v1",
        content_hash="0" * 64,
        approval_state=ApprovalState.QUARANTINED,
    )


def test_a_block_is_never_split_across_representations() -> None:
    """Blocks anchor citations (rule 4). A representation ending mid-block
    cannot cite the half it used."""
    blocks = [block(i, f"Sentence {i}. " + "filler words here. " * 30) for i in range(6)]
    reps = represent(obj(blocks), blocks)

    assigned = [bid for rep in reps for bid in rep.block_ids]
    assert sorted(assigned) == sorted(b.block_id for b in blocks)
    assert len(assigned) == len(set(assigned)), "a block landed in two windows"


def test_a_caption_travels_with_what_it_captions() -> None:
    figure = block(0, "Figure 1.4 apparatus", block_type=BlockType.FIGURE)
    caption = block(1, "Heating ferrous sulphate crystals", block_type=BlockType.CAPTION,
                    linked=figure.block_id)
    tail = [block(i, "Body text. " * 40) for i in range(2, 6)]
    blocks = [figure, caption, *tail]

    reps = represent(obj(blocks), blocks)
    home = {bid: rep.representation_id for rep in reps for bid in rep.block_ids}
    assert home[figure.block_id] == home[caption.block_id]


def test_a_formula_is_never_alone_in_a_window() -> None:
    """Formula text is degraded by construction (R-008). Alone it is
    unsearchable; attached to the prose that introduces it, it is reachable."""
    blocks = [
        block(0, "Ferrous sulphate decomposes on heating. " * 12),
        block(1, "2FeSO 4 (s) Heat -> Fe 2 O3 (s) + SO 2 (g)", block_type=BlockType.FORMULA),
        block(2, "The green colour changes. " * 12),
        block(3, "CaCO3 (s) Heat -> CaO(s) + CO 2 (g)", block_type=BlockType.FORMULA),
    ]
    reps = represent(obj(blocks), blocks)
    by_id = {b.block_id: b for b in blocks}

    for rep in reps:
        types = {by_id[bid].block_type for bid in rep.block_ids}
        assert types != {BlockType.FORMULA}, (
            f"{rep.representation_id} is formulas only, which is unsearchable text"
        )
    assert all(r.modality is Modality.EQUATION for r in reps if "FeSO" in r.search_text)


def test_the_heading_prefixes_every_window() -> None:
    """The one piece of context a small window loses. It is what makes a
    paragraph findable by a section name it never repeats."""
    blocks = [block(i, "Body sentence about crystals. " * 30) for i in range(4)]
    reps = represent(obj(blocks), blocks)

    assert len(reps) > 1
    assert all(r.search_text.startswith("1.2.2 Decomposition Reaction") for r in reps)


def test_windows_stay_under_the_ceiling_unless_one_block_exceeds_it() -> None:
    blocks = [block(i, "word " * 60) for i in range(10)]
    reps = represent(obj(blocks), blocks)
    bodies = [len(r.search_text) for r in reps]
    assert max(bodies) <= MAX_CHARS + len("1.2.2 Decomposition Reaction") + 1


def test_an_oversized_single_block_is_kept_whole() -> None:
    """Splitting it would break rule 1, so the window is allowed to exceed the
    ceiling instead. The ceiling is a target for grouping, not a licence to cut."""
    blocks = [block(0, "x " * 2000)]
    reps = represent(obj(blocks), blocks)
    assert len(reps) == 1
    assert reps[0].block_ids == [blocks[0].block_id]


def test_chunking_is_deterministic_and_carries_no_vector() -> None:
    blocks = [block(i, "Body sentence. " * 30) for i in range(5)]
    first = represent(obj(blocks), blocks)
    second = represent(obj(blocks), blocks)

    assert [r.representation_id for r in first] == [r.representation_id for r in second]
    assert [r.content_hash for r in first] == [r.content_hash for r in second]
    assert all(not r.embedded for r in first), "chunking must not invent an embedding"


def test_page_furniture_is_left_out() -> None:
    blocks = [
        block(0, "Chemical Reactions and Equations", block_type=BlockType.PAGE_FOOTER),
        block(1, "Real body text about decomposition. " * 20),
    ]
    reps = represent(obj(blocks), blocks)
    assigned = {bid for rep in reps for bid in rep.block_ids}
    assert blocks[0].block_id not in assigned
    assert blocks[1].block_id in assigned


def test_a_window_carries_the_previous_one_s_last_prose_block_as_context() -> None:
    """The prayer-hall failure: "Example 6 : Find the dimensions of the prayer
    hall" ended one window and its answer began the next, which never repeats
    the phrase. Retrieval was correct and scored below the abstention floor for
    want of two words."""
    # Sized so the window closes *after* the Example line, putting the
    # statement at the end of one window and the answer at the start of the next.
    blocks = [
        block(0, "Body about factorisation. " * 25),
        block(1, "Example 6 : Find the dimensions of the prayer hall discussed in Section 4.1."),
        block(2, "Thus, the breadth of the hall is 12 m. Its length is 25 m. " * 12),
    ]
    reps = represent(obj(blocks), blocks)

    assert len(reps) > 1, "fixture must straddle a window boundary"
    assert blocks[1].block_id in reps[0].block_ids, "Example line must end the first window"
    later = reps[1]
    assert "prayer hall" in later.search_text
    # Context, not lineage.
    assert blocks[1].block_id not in later.block_ids


def test_carried_context_is_never_a_formula() -> None:
    """Carrying degraded formula text forward adds noise, not meaning."""
    blocks = [
        block(0, "Prose that introduces the working. " * 20),
        block(1, "2 x 2 - 24 x + 25 x - 300 = 0", block_type=BlockType.FORMULA),
        block(2, "Second window body text here. " * 30),
    ]
    reps = represent(obj(blocks), blocks)
    if len(reps) > 1:
        assert "300 = 0" not in reps[1].search_text.split(reps[1].search_text[-50:])[0][:200]


def test_a_caption_extracted_before_its_figure_still_travels_with_it() -> None:
    """Reported by an outside review. The pairing used to depend on the figure
    having been seen already, so a caption emitted first split the pair while
    the docstring promised it could not."""
    caption = block(0, "Fig. 1.4 Heating ferrous sulphate", block_type=BlockType.CAPTION,
                    linked="doc:docling:texts-1")
    figure = block(1, "figure body", block_type=BlockType.FIGURE)
    tail = [block(i, "Body text. " * 40) for i in range(2, 6)]
    blocks = [caption, figure, *tail]

    reps = represent(obj(blocks), blocks)
    home = {bid: rep.representation_id for rep in reps for bid in rep.block_ids}
    assert home[caption.block_id] == home[figure.block_id]


def test_the_index_takes_words_and_the_pack_takes_the_formula() -> None:
    """Searching and displaying are different questions (R-069).

    A block with degraded text and recovered LaTeX must be *indexed* on the
    text, because a query is a sentence somebody typed and `\frac{-b}{2a}` is
    not words. It must be *shown* as the LaTeX, because the degraded text is
    what R-037 was about. Measured: indexing the LaTeX cost a case of candidate
    recall, and appending it to the text did not recover it.
    """
    from agts.parsing.quality import readable_text
    from agts.retrieval.chunking import _text_of

    degraded = block(
        1,
        "2 4 , 2 b b ac a − ± − provided b 2 - 4 ac ≥",
        block_type=BlockType.FORMULA,
    ).model_copy(update={"latex": '\\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}'})

    assert "frac" not in _text_of(degraded), "the index must not carry LaTeX markup"
    assert "provided" in _text_of(degraded)
    assert readable_text(degraded.text, degraded.latex) == degraded.latex
