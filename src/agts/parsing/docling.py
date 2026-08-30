"""Docling JSON adapter with citation-grade geometry."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agts.contracts.common import BlockType
from agts.contracts.objects import SourceBlock
from agts.parsing.base import ParseOutcome
from agts.parsing.geometry import DEFAULT_PAGE_SIZE, pdf_points_to_region


STRATEGY = "docling"

_TYPE_MAP = {
    "section_header": BlockType.HEADING,
    "text": BlockType.PARAGRAPH,
    "list_item": BlockType.LIST_ITEM,
    "caption": BlockType.CAPTION,
    "formula": BlockType.FORMULA,
    "picture": BlockType.FIGURE,
    "table": BlockType.TABLE,
    "page_header": BlockType.PAGE_HEADER,
    "page_footer": BlockType.PAGE_FOOTER,
}


def _ref_suffix(self_ref: str) -> str:
    """`#/tables/0` -> `tables-0`.

    The collection has to stay in the id. Docling numbers `texts`, `tables` and
    `pictures` independently, so `#/texts/0` and `#/tables/0` both end in `0` —
    and a gold label anchors on a block id (rule 4). Two blocks sharing one id
    means a citation points at either of them and a corpus keyed by id silently
    keeps whichever was loaded last. On the first real chapter that was 19
    blocks; it raises nothing and fails no gate.
    """
    parts = [part for part in self_ref.lstrip("#/").split("/") if part]
    return "-".join(parts) if parts else "unknown"


def _table_to_markdown(table: Mapping[str, Any]) -> str:
    """Render a Docling table's cells as markdown (§7.4).

    A Docling table carries **no `text` and no `orig`** — the content lives in
    `data.table_cells`, each cell holding its own row and column offsets. Reading
    the item's own text field yields nothing, which is how a real chapter's five
    tables become five blocks that carry no content at all. Same defect class as
    R-010, one parser over.

    Row and column identity is preserved rather than flattened into prose, so
    the cells stay addressable and a lexical index can still use them.
    """
    data = table.get("data") or {}
    cells = data.get("table_cells") or []
    if not cells:
        return ""

    rows = int(data.get("num_rows") or 0) or max(
        int(c.get("end_row_offset_idx", 0)) for c in cells
    )
    columns = int(data.get("num_cols") or 0) or max(
        int(c.get("end_col_offset_idx", 0)) for c in cells
    )
    if rows <= 0 or columns <= 0:
        return ""

    grid = [["" for _ in range(columns)] for _ in range(rows)]
    for cell in cells:
        row = int(cell.get("start_row_offset_idx", 0))
        column = int(cell.get("start_col_offset_idx", 0))
        if not (0 <= row < rows and 0 <= column < columns):
            continue
        text = str(cell.get("text") or "").replace("|", "\\|").replace("\n", " ").strip()
        # A spanning cell writes once, at its origin. Repeating it across the
        # span would make the markdown read as several distinct values.
        grid[row][column] = text

    if not any(any(cell for cell in row) for row in grid):
        return ""

    head, *body = grid
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * columns]
    lines += ["| " + " | ".join(row) + " |" for row in body]
    return "\n".join(lines)


def blocks_from_docling(
    document: Mapping[str, Any],
    *,
    source_id: str,
    document_id: str,
    page_sizes: Mapping[int, tuple[float, float]] | None = None,
    parser_version: str = "unknown",
    asset_uris: Mapping[str, str] | None = None,
) -> ParseOutcome:
    """Convert Docling export JSON to immutable blocks.

    Formula blocks intentionally retain `orig` as raw text and their crop URI;
    no LaTex is manufactured here. A separately reviewed recogniser may attach
    LaTex later, without re-parsing the source PDF.
    """
    page_sizes = page_sizes or {}
    asset_uris = asset_uris or {}
    pages = len(document.get("pages") or {})
    raw_items: list[dict[str, Any]] = []
    for collection in ("texts", "pictures", "tables"):
        raw_items.extend(document.get(collection) or [])

    prepared: list[tuple[int, float, float, dict[str, Any], dict[str, Any]]] = []
    for item in raw_items:
        provenance = (item.get("prov") or [None])[0]
        if not provenance or not provenance.get("bbox"):
            continue
        bbox = provenance["bbox"]
        prepared.append((
            int(provenance["page_no"]),
            -float(bbox["t"]),
            float(bbox["l"]),
            item,
            provenance,
        ))

    blocks: list[SourceBlock] = []
    warnings: list[str] = []
    for order_index, (page, _top, _left, item, provenance) in enumerate(
        sorted(prepared, key=lambda row: (row[0], row[1], row[2], str(row[3].get("self_ref", ""))))
    ):
        raw_label = str(item.get("label", ""))
        block_type = _TYPE_MAP.get(raw_label, BlockType.UNKNOWN)
        width, height = page_sizes.get(page, DEFAULT_PAGE_SIZE)
        if page not in page_sizes:
            warnings.append(f"page {page}: no page size supplied, assumed Letter")
        bbox = provenance["bbox"]
        if block_type is BlockType.TABLE:
            text = _table_to_markdown(item) or None
        else:
            text = (item.get("orig") or item.get("text") or "").strip() or None
        item_ref = str(item.get("self_ref", ""))
        image_uri = asset_uris.get(item_ref)
        if block_type is BlockType.FIGURE and not image_uri and not text:
            warnings.append(f"{item_ref}: figure omitted because no crop URI was supplied")
            continue
        if not (text or image_uri):
            # Carries nothing retrievable and cannot anchor a gold label.
            # Counted rather than raised: empty decorative elements are normal,
            # and a page full of them is what the §7.1 gate is for.
            warnings.append(f"{item_ref}: {raw_label} block had no text or image")
            continue
        blocks.append(
            SourceBlock(
                block_id=f"{document_id}:docling:{_ref_suffix(item_ref)}",
                source_id=source_id,
                document_id=document_id,
                order_index=order_index,
                block_type=block_type,
                region=pdf_points_to_region(
                    [bbox["l"], bbox["b"], bbox["r"], bbox["t"]],
                    page=page,
                    page_width=width,
                    page_height=height,
                ),
                text=text,
                image_uri=image_uri,
                parse_strategy=STRATEGY,
                parser_version=parser_version,
                raw_label=raw_label,
            )
        )
    return ParseOutcome(
        strategy=STRATEGY,
        parser_version=parser_version,
        blocks=blocks,
        pages=pages,
        warnings=list(dict.fromkeys(warnings)),
    )
