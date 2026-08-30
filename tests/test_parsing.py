"""Parsing adapters and the dual-parse diff (§7.2).

The geometry tests matter more than they look. A flipped vertical axis does not
crash anything - it places every citation on the mirror image of the right spot,
and that surfaces as "the highlighting seems slightly off" long after the corpus
is built.
"""

from __future__ import annotations

import pytest

from agts.contracts.common import BlockType
from agts.parsing import (
    blocks_from_json,
    diff_outcomes,
    pdf_points_to_region,
    region_to_pdf_points,
)
from agts.parsing.base import ParseOutcome

A4 = (595.0, 842.0)


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------


def test_top_of_page_maps_to_top_of_region() -> None:
    """PDF y is largest at the top; Region y is 0 at the top."""
    top_strip = pdf_points_to_region(
        [0.0, 800.0, 595.0, 842.0], page=1, page_width=A4[0], page_height=A4[1]
    )
    assert top_strip.y == pytest.approx(0.0, abs=1e-6)

    bottom_strip = pdf_points_to_region(
        [0.0, 0.0, 595.0, 42.0], page=1, page_width=A4[0], page_height=A4[1]
    )
    assert bottom_strip.y == pytest.approx(1.0 - 42.0 / 842.0, abs=1e-6)
    assert bottom_strip.y > top_strip.y


def test_conversion_round_trips() -> None:
    original = [72.024, 486.91, 289.368, 497.95]  # a real heading from NCERT ch1
    region = pdf_points_to_region(original, page=3, page_width=A4[0], page_height=A4[1])
    back = region_to_pdf_points(region, page_width=A4[0], page_height=A4[1])
    assert back == pytest.approx(tuple(original), abs=1e-3)
    assert region.page == 3


def test_boxes_outside_the_page_are_clamped_not_rejected() -> None:
    """A real full-bleed cover image from NCERT ch1 page 1 exceeds the media box
    on both axes. Clamping beats failing a run over a rounding artefact."""
    region = pdf_points_to_region(
        [-17.15, -39.24, 593.153, 824.044], page=1, page_width=A4[0], page_height=A4[1]
    )
    assert 0.0 <= region.x <= 1.0
    assert 0.0 <= region.y <= 1.0
    assert region.x + region.width <= 1.0 + 1e-9
    assert region.y + region.height <= 1.0 + 1e-9


def test_inverted_boxes_are_normalised() -> None:
    swapped = pdf_points_to_region(
        [400.0, 700.0, 100.0, 300.0], page=1, page_width=A4[0], page_height=A4[1]
    )
    assert swapped.width > 0 and swapped.height > 0


def test_zero_page_size_is_an_error() -> None:
    with pytest.raises(ValueError, match="non-positive page size"):
        pdf_points_to_region([0, 0, 1, 1], page=1, page_width=0.0, page_height=842.0)


# --------------------------------------------------------------------------
# opendataloader adapter
# --------------------------------------------------------------------------


def _doc() -> dict:
    """Mirrors the real JSON shape: kids, nested rows/cells, a linked caption."""
    return {
        "file name": "fixture.pdf",
        "number of pages": 2,
        "kids": [
            {
                "type": "heading",
                "id": 4,
                "page number": 1,
                "bounding box": [60.0, 520.0, 400.0, 550.0],
                "content": "Chemical Reactions",
            },
            {
                "type": "paragraph",
                "id": 5,
                "page number": 1,
                "bounding box": [60.0, 400.0, 500.0, 500.0],
                "content": "  A chemical equation is balanced when...  ",
            },
            {
                "type": "text block",
                "id": 6,
                "page number": 1,
                "bounding box": [50.0, 380.0, 520.0, 520.0],
            },
            {
                "type": "list",
                "id": 7,
                "page number": 2,
                "bounding box": [60.0, 300.0, 500.0, 360.0],
                "list items": [
                    {
                        "type": "list item",
                        "id": 8,
                        "page number": 2,
                        "bounding box": [62.0, 330.0, 498.0, 358.0],
                        "content": "Step I",
                    }
                ],
            },
            {
                "type": "table",
                "id": 9,
                "page number": 2,
                "bounding box": [60.0, 100.0, 500.0, 280.0],
                # Real cells carry NO `content`. Their text sits in nested
                # `kids`, and a fixture that puts it on the cell hides the bug
                # that renders every table as an empty grid.
                "rows": [
                    {
                        "type": "table row",
                        "id": 10,
                        "cells": [
                            {"type": "table cell", "id": 11, "page number": 2,
                             "bounding box": [60.0, 240.0, 280.0, 275.0],
                             "kids": [{"type": "paragraph", "id": 111, "page number": 2,
                                       "bounding box": [61.0, 241.0, 279.0, 274.0],
                                       "content": "Element"}]},
                            {"type": "table cell", "id": 12, "page number": 2,
                             "bounding box": [280.0, 240.0, 500.0, 275.0],
                             "kids": [{"type": "paragraph", "id": 121, "page number": 2,
                                       "bounding box": [281.0, 241.0, 499.0, 274.0],
                                       "content": "Count"}]},
                        ],
                    },
                    {
                        "type": "table row",
                        "id": 13,
                        "cells": [
                            {"type": "table cell", "id": 14, "page number": 2,
                             "bounding box": [60.0, 200.0, 280.0, 238.0],
                             "kids": [{"type": "paragraph", "id": 141, "page number": 2,
                                       "bounding box": [61.0, 201.0, 279.0, 237.0],
                                       "content": "Fe"}]},
                            {"type": "table cell", "id": 15, "page number": 2,
                             "bounding box": [280.0, 200.0, 500.0, 238.0],
                             "kids": [{"type": "paragraph", "id": 151, "page number": 2,
                                       "bounding box": [281.0, 201.0, 499.0, 237.0],
                                       "content": "3"}]},
                        ],
                    },
                ],
            },
            {
                "type": "caption",
                "id": 16,
                "page number": 2,
                "bounding box": [60.0, 80.0, 500.0, 98.0],
                "linked content id": 9,
                "content": "Table 1.1 Atom counts",
            },
            {
                "type": "image",
                "id": 17,
                "page number": 2,
                "bounding box": [60.0, 400.0, 300.0, 600.0],
                "source": "figures/imageFile1.png",
                "alt_source": "missing",
            },
            {
                "type": "image",
                "id": 18,
                "page number": 2,
                "bounding box": [310.0, 400.0, 340.0, 420.0],
                "source": "missing",
            },
            {
                "type": "sidebar",  # a type we do not know about
                "id": 19,
                "page number": 2,
                "bounding box": [60.0, 620.0, 500.0, 700.0],
                "content": "Do You Know?",
            },
        ],
    }


@pytest.fixture(scope="module")
def outcome() -> ParseOutcome:
    return blocks_from_json(
        _doc(),
        source_id="s1",
        document_id="d1",
        page_sizes={1: A4, 2: A4},
        parser_version="2.5.5",
    )


def test_containers_do_not_become_blocks(outcome: ParseOutcome) -> None:
    """A list, a table row and a text block hold other elements. They carry no
    content of their own, so they cannot anchor a gold label."""
    kinds = {b.block_type for b in outcome.blocks}
    assert BlockType.LIST not in kinds
    assert BlockType.TABLE_ROW not in kinds
    assert BlockType.TEXT_BLOCK not in kinds
    assert BlockType.LIST_ITEM in kinds  # its child does


def test_table_is_rendered_as_markdown_not_flattened(outcome: ParseOutcome) -> None:
    """Regression: cell text lives in nested kids, not on the cell. Reading only
    the cell's own field produced `|  |  |` for every table in the real NCERT
    chapter - four tables of nothing, which reads as a table with no data."""
    table = next(b for b in outcome.blocks if b.block_type is BlockType.TABLE)
    assert table.text is not None
    assert "| Element | Count |" in table.text
    assert "| Fe | 3 |" in table.text
    # Cells stay individually addressable alongside the rendered table.
    cells = [b for b in outcome.blocks if b.block_type is BlockType.TABLE_CELL]
    assert len(cells) == 4
    assert {c.text for c in cells} == {"Element", "Count", "Fe", "3"}


def test_caption_keeps_its_link_to_the_table(outcome: ParseOutcome) -> None:
    """Composition must never split a caption from what it describes, and the
    parser already worked out the pairing."""
    caption = next(b for b in outcome.blocks if b.block_type is BlockType.CAPTION)
    table = next(b for b in outcome.blocks if b.block_type is BlockType.TABLE)
    assert caption.linked_block_id == table.block_id


def test_unknown_types_are_recorded_not_guessed(outcome: ParseOutcome) -> None:
    unknown = [b for b in outcome.blocks if b.block_type is BlockType.UNKNOWN]
    assert len(unknown) == 1
    assert unknown[0].raw_label == "sidebar"


def test_images_without_a_source_are_dropped(outcome: ParseOutcome) -> None:
    images = [b for b in outcome.blocks if b.block_type is BlockType.IMAGE]
    assert len(images) == 1
    assert images[0].image_uri == "figures/imageFile1.png"


def test_text_is_stripped_and_order_is_preserved(outcome: ParseOutcome) -> None:
    para = next(b for b in outcome.blocks if b.block_type is BlockType.PARAGRAPH)
    assert para.text == "A chemical equation is balanced when..."
    indices = [b.order_index for b in outcome.blocks]
    assert indices == sorted(indices)


def test_missing_page_sizes_warn_rather_than_assume_silently() -> None:
    result = blocks_from_json(_doc(), source_id="s1", document_id="d1")
    assert any("no page size supplied" in w for w in result.warnings)


# --------------------------------------------------------------------------
# Dual-parse diff
# --------------------------------------------------------------------------


def test_a_page_only_one_strategy_saw_is_flagged(outcome: ParseOutcome) -> None:
    page_one_only = ParseOutcome(
        strategy="other",
        parser_version="0",
        blocks=[b for b in outcome.blocks if b.region.page == 1],
        pages=2,
    )
    diff = diff_outcomes(outcome, page_one_only)
    flagged = {p.page for p in diff.flagged_pages}
    assert 2 in flagged
    assert "produced no blocks" in diff.report()


def test_agreement_flags_nothing(outcome: ParseOutcome) -> None:
    assert diff_outcomes(outcome, outcome).flagged_pages == []


def test_empty_pages_are_reported(outcome: ParseOutcome) -> None:
    """§7.1 gate. Every page here yields blocks, so the list is empty."""
    assert outcome.empty_pages() == []
