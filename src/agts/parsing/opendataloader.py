"""Adapter: opendataloader-pdf JSON to `SourceBlock`.

The second parse strategy (R-008). Deterministic, rule-based, ~1 second per page,
so running it alongside Docling satisfies §7.2's dual-parse requirement for about
1% of the wall clock.

This module is a **pure function over the parser's JSON**. It does not import
opendataloader-pdf and does not shell out, so the mapping is testable from a
fixture without a JVM, and a parser upgrade cannot silently change our blocks
without a failing test.
"""

from __future__ import annotations

from typing import Any, Iterator

from agts.contracts.common import BlockType
from agts.contracts.objects import SourceBlock
from agts.parsing.base import ParseOutcome
from agts.parsing.geometry import DEFAULT_PAGE_SIZE, pdf_points_to_region

STRATEGY = "opendataloader-pdf"

#: Their layout vocabulary to ours. Anything absent becomes `UNKNOWN` and keeps
#: its original label in `raw_label`, so a new parser type is visible rather
#: than quietly folded into a neighbour.
_TYPE_MAP: dict[str, BlockType] = {
    "heading": BlockType.HEADING,
    "paragraph": BlockType.PARAGRAPH,
    "list": BlockType.LIST,
    "list item": BlockType.LIST_ITEM,
    "table": BlockType.TABLE,
    "table row": BlockType.TABLE_ROW,
    "table cell": BlockType.TABLE_CELL,
    "caption": BlockType.CAPTION,
    "image": BlockType.IMAGE,
    "formula": BlockType.FORMULA,
    "text block": BlockType.TEXT_BLOCK,
}

#: Containers that exist to hold other elements. Their children are emitted;
#: they are not, because a block with no content of its own cannot anchor a gold
#: label and would inflate every block count.
_CONTAINERS = {BlockType.LIST, BlockType.TABLE_ROW, BlockType.TEXT_BLOCK}

_CHILD_KEYS = ("kids", "list items", "rows", "cells")


def _walk(node: Any) -> Iterator[dict[str, Any]]:
    """Depth-first in document order, which is the reading order the parser
    established. `order_index` depends on this being stable."""
    if isinstance(node, dict):
        # The root carries no `type` but does carry `kids`, which is already one
        # of _CHILD_KEYS - so it needs no special case, and giving it one walks
        # every child twice.
        if node.get("type"):
            yield node
        for key in _CHILD_KEYS:
            for child in node.get(key) or []:
                yield from _walk(child)
    elif isinstance(node, list):
        for child in node:
            yield from _walk(child)


def _gather_text(node: Any) -> str:
    """All text at or beneath `node`, in reading order.

    Table cells carry no `content` of their own - the text sits in nested `kids`.
    Reading only the cell's own field renders every table as an empty grid, which
    looks like a table with no data rather than like a bug.
    """
    parts: list[str] = []
    for element in _walk(node):
        content = (element.get("content") or "").strip()
        if content:
            parts.append(content)
    return " ".join(parts).strip()


def _table_to_markdown(table: dict[str, Any]) -> str:
    """Render a table's cells as markdown.

    §7.4: preserve tables structurally rather than flattening them into prose.
    Markdown keeps row and column identity in a form that both a reader and a
    lexical index can use, and the cell blocks remain individually addressable
    alongside it.
    """
    rows: list[list[str]] = []
    for row in table.get("rows") or []:
        cells = [
            _gather_text(cell).replace("|", "\\|").replace("\n", " ")
            for cell in row.get("cells") or []
        ]
        if cells:
            rows.append(cells)
    if not rows:
        return ""

    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    head, *body = rows
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(lines)


def blocks_from_json(
    document: dict[str, Any],
    *,
    source_id: str,
    document_id: str,
    page_sizes: dict[int, tuple[float, float]] | None = None,
    parser_version: str = "unknown",
) -> ParseOutcome:
    """Convert one opendataloader-pdf JSON document into blocks."""
    page_sizes = page_sizes or {}
    pages = int(document.get("number of pages") or 0)
    blocks: list[SourceBlock] = []
    warnings: list[str] = []
    skipped_no_geometry = 0

    for order_index, node in enumerate(_walk(document)):
        raw_label = str(node.get("type"))
        block_type = _TYPE_MAP.get(raw_label, BlockType.UNKNOWN)
        if block_type in _CONTAINERS:
            continue

        page = node.get("page number")
        bbox = node.get("bounding box")
        if page is None or not bbox:
            skipped_no_geometry += 1
            continue

        if block_type is BlockType.TABLE:
            text = _table_to_markdown(node) or None
        elif block_type is BlockType.TABLE_CELL:
            text = _gather_text(node) or None
        else:
            text = (node.get("content") or "").strip() or None

        image_uri = node.get("source") if block_type is BlockType.IMAGE else None
        if image_uri in ("missing", ""):
            image_uri = None

        if not (text or image_uri):
            # Nothing retrievable and nothing to anchor to. Counted, not raised:
            # empty decorative elements are normal, a page full of them is not,
            # and the empty-page gate catches the latter.
            continue

        width, height = page_sizes.get(page, DEFAULT_PAGE_SIZE)
        if page not in page_sizes:
            warnings.append(f"page {page}: no page size supplied, assumed Letter")

        linked = node.get("linked content id")

        blocks.append(
            SourceBlock(
                block_id=f"{document_id}:odl:{node.get('id')}",
                source_id=source_id,
                document_id=document_id,
                order_index=order_index,
                block_type=block_type,
                region=pdf_points_to_region(
                    bbox, page=page, page_width=width, page_height=height
                ),
                text=text,
                image_uri=image_uri,
                parse_strategy=STRATEGY,
                parser_version=parser_version,
                raw_label=raw_label,
                linked_block_id=(
                    f"{document_id}:odl:{linked}" if linked is not None else None
                ),
            )
        )

    if skipped_no_geometry:
        warnings.append(
            f"{skipped_no_geometry} elements had no page or bounding box and "
            "were skipped - they cannot anchor a gold label"
        )

    # Deduplicate the page-size warning; one line per document is enough.
    seen: set[str] = set()
    warnings = [w for w in warnings if not (w in seen or seen.add(w))]

    return ParseOutcome(
        strategy=STRATEGY,
        parser_version=parser_version,
        blocks=blocks,
        pages=pages,
        warnings=warnings,
    )
