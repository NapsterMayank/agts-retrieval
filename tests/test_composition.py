from __future__ import annotations

from agts.composition import compose_sections
from agts.contracts import AuthorityTier, BlockType, Board, Language, ObjectType, Region, SourceBlock
from agts.contracts.objects import CurriculumIdentity


def _block(index: int, kind: BlockType, text: str | None) -> SourceBlock:
    return SourceBlock(
        block_id=f"b{index}", source_id="s", document_id="d", order_index=index,
        block_type=kind, region=Region(page=1, x=0, y=0, width=1, height=1),
        text=text, image_uri="figure.png" if text is None else None,
        parse_strategy="test", parser_version="1",
    )


def test_explicit_sections_preserve_source_lineage_and_quarantine() -> None:
    blocks = [
        _block(0, BlockType.PAGE_HEADER, "header"),
        _block(1, BlockType.HEADING, "4.1 Intro"),
        _block(2, BlockType.PARAGRAPH, "A quadratic equation has degree two."),
        _block(3, BlockType.FORMULA, "ax² + bx + c = 0"),
        _block(4, BlockType.HEADING, "EXERCISE 4.1"),
        _block(5, BlockType.PARAGRAPH, "Find the roots."),
    ]
    curriculum = CurriculumIdentity(
        board=Board.CBSE, curriculum_version="2026-27", grade="10", subject="mathematics",
        unit_id="quadratic-equations", concept_ids=["quadratic-equations"],
    )
    objects = compose_sections(
        blocks, curriculum=curriculum,
        section_types={"4.1 Intro": ObjectType.EXPLANATION, "EXERCISE 4.1": ObjectType.QUESTION},
        authority_tier=AuthorityTier.BOARD_OFFICIAL,
    )
    assert [item.heading_path for item in objects] == ["4.1 Intro", "EXERCISE 4.1"]
    assert objects[0].block_ids == ["b1", "b2", "b3"]
    assert "header" not in objects[0].text
    assert objects[0].modality.value == "equation"
    assert objects[0].approval_state.value == "QUARANTINED"
