from __future__ import annotations

from agts.contracts.common import BlockType
from agts.parsing.docling import blocks_from_docling


def test_docling_formula_keeps_raw_text_and_geometry() -> None:
    document = {
        "pages": {"1": {}},
        "texts": [
            {
                "self_ref": "#/texts/7",
                "label": "formula",
                "orig": "x 2 - 4 = 0",
                "prov": [{"page_no": 1, "bbox": {"l": 10, "b": 20, "r": 110, "t": 40}}],
            }
        ],
        "pictures": [],
        "tables": [],
    }
    outcome = blocks_from_docling(
        document,
        source_id="source-1",
        document_id="doc-1",
        page_sizes={1: (200, 100)},
        parser_version="2.122.0",
    )

    assert outcome.empty_pages() == []
    block = outcome.blocks[0]
    assert block.block_type is BlockType.FORMULA
    assert block.text == "x 2 - 4 = 0"
    assert block.latex is None
    assert block.block_id == "doc-1:docling:texts-7"
    assert block.region.page == 1
    assert block.region.x == 0.05
    assert block.region.y == 0.6


def test_docling_table_renders_cells_that_live_only_in_data() -> None:
    """R-010, one parser over: a Docling table carries no `text` and no `orig`.

    The cells sit in `data.table_cells`. Reading the item's own text field
    yields nothing, and a block carrying nothing fails validation - which is how
    this surfaced, on the first real chapter with tables in it. The shape below
    is taken from real output, not written from memory.
    """
    document = {
        "pages": {"3": {}},
        "texts": [],
        "pictures": [],
        "tables": [
            {
                "self_ref": "#/tables/0",
                "label": "table",
                "prov": [{"page_no": 3, "bbox": {"l": 59.0, "b": 163.8, "r": 349.9, "t": 248.8}}],
                "data": {
                    "num_rows": 2,
                    "num_cols": 3,
                    "table_cells": [
                        {"text": "Element", "start_row_offset_idx": 0, "start_col_offset_idx": 0},
                        {"text": "Number of atoms in reactants (LHS)", "start_row_offset_idx": 0, "start_col_offset_idx": 1},
                        {"text": "Number of atoms in products (RHS)", "start_row_offset_idx": 0, "start_col_offset_idx": 2},
                        {"text": "Zn", "start_row_offset_idx": 1, "start_col_offset_idx": 0},
                        {"text": "1", "start_row_offset_idx": 1, "start_col_offset_idx": 1},
                        {"text": "1", "start_row_offset_idx": 1, "start_col_offset_idx": 2},
                    ],
                },
            }
        ],
    }
    outcome = blocks_from_docling(
        document,
        source_id="source-1",
        document_id="doc-1",
        page_sizes={3: (612, 792)},
        parser_version="2.122.0",
    )

    block = outcome.blocks[0]
    assert block.block_type is BlockType.TABLE
    assert block.text is not None
    assert "| Element | Number of atoms in reactants (LHS) |" in block.text
    assert "| Zn | 1 | 1 |" in block.text


def test_docling_block_with_neither_text_nor_image_is_skipped_not_raised() -> None:
    """An empty decorative element is normal; a page of them is what §7.1 catches."""
    document = {
        "pages": {"1": {}},
        "texts": [
            {
                "self_ref": "#/texts/1",
                "label": "text",
                "orig": "",
                "prov": [{"page_no": 1, "bbox": {"l": 10, "b": 20, "r": 110, "t": 40}}],
            },
            {
                "self_ref": "#/texts/2",
                "label": "text",
                "orig": "Real content.",
                "prov": [{"page_no": 1, "bbox": {"l": 10, "b": 50, "r": 110, "t": 70}}],
            },
        ],
        "pictures": [],
        "tables": [],
    }
    outcome = blocks_from_docling(
        document, source_id="s", document_id="d", page_sizes={1: (200, 100)}
    )

    assert [b.text for b in outcome.blocks] == ["Real content."]
    assert any("no text or image" in w for w in outcome.warnings)


def test_block_ids_are_unique_across_docling_collections() -> None:
    """`#/texts/0` and `#/tables/0` are different blocks. A gold label anchors on
    a block id, so an id collision points a citation at either of them."""
    document = {
        "pages": {"1": {}},
        "texts": [
            {
                "self_ref": "#/texts/0",
                "label": "text",
                "orig": "A paragraph.",
                "prov": [{"page_no": 1, "bbox": {"l": 10, "b": 20, "r": 110, "t": 40}}],
            }
        ],
        "pictures": [],
        "tables": [
            {
                "self_ref": "#/tables/0",
                "label": "table",
                "prov": [{"page_no": 1, "bbox": {"l": 10, "b": 50, "r": 110, "t": 70}}],
                "data": {
                    "num_rows": 1,
                    "num_cols": 1,
                    "table_cells": [
                        {"text": "cell", "start_row_offset_idx": 0, "start_col_offset_idx": 0}
                    ],
                },
            }
        ],
    }
    outcome = blocks_from_docling(
        document, source_id="s", document_id="d", page_sizes={1: (200, 100)}
    )

    ids = [b.block_id for b in outcome.blocks]
    assert sorted(ids) == ["d:docling:tables-0", "d:docling:texts-0"]
    assert len(set(ids)) == len(ids)
