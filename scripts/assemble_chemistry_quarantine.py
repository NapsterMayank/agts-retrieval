"""Assemble quarantined citation blocks for NCERT Class 10 Science, chapter 1.

The same shape as `assemble_quadratic_quarantine.py`, with one deliberate
difference: the second strategy here is **opendataloader-pdf** (R-008) rather
than Chandra. That is the pairing §7.2 actually specifies, and it exercises the
adapter whose table bug R-010 was written about — against real output, which is
the only way that class of defect shows up.

Run it with the parser environment (`vendor/parse-spike/.venv`): this needs
pypdfium2 for the formula crops.

    python scripts/assemble_chemistry_quarantine.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import pypdfium2

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.contracts.common import BlockType
from agts.parsing.base import ParseOutcome
from agts.parsing.diff import diff_outcomes
from agts.parsing.docling import blocks_from_docling
from agts.parsing.geometry import page_sizes_from_pdf
from agts.parsing.opendataloader import blocks_from_json


PDF = Path(r"D:\onedrive\Desktop\ncert_science_10th_1stchapter.pdf")
OUT = Path(__file__).parents[1] / "artifacts" / "chemical-reactions-quarantine"
DOCLING = OUT / "docling.json"
OPENDATALOADER = Path(r"D:\personal\vendor\parse-spike\out\ncert_science_10th_1stchapter.json")

SOURCE_ID = "ncert-class-10-science-ch01-chemical-reactions-and-equations-2026-27"
DOCUMENT_ID = "chemical-reactions"
DOCLING_VERSION = "2.122.0"
OPENDATALOADER_VERSION = "deterministic"


def crop_assets(document: dict) -> dict[str, str]:
    """Render a PNG crop for every formula and figure region.

    R-008: a formula object stores its crop and raw text alongside any LaTeX,
    never LaTeX alone. Without the crop a wrong conversion is undetectable
    without re-parsing the source.
    """
    assets = OUT / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    pdf = pypdfium2.PdfDocument(PDF)
    uris: dict[str, str] = {}
    rendered: dict[int, object] = {}

    for collection in ("texts", "pictures"):
        for item in document.get(collection) or []:
            if item.get("label") not in {"formula", "picture"}:
                continue
            provenance = (item.get("prov") or [None])[0]
            if not provenance:
                continue
            bbox = provenance["bbox"]
            page_no = provenance["page_no"]
            page = pdf[page_no - 1]
            image = rendered.get(page_no)
            if image is None:
                image = rendered[page_no] = page.render(scale=2).to_pil()
            scale = image.width / page.get_size()[0]
            left = max(0, int(bbox["l"] * scale) - 16)
            right = min(image.width, int(bbox["r"] * scale) + 16)
            top = max(0, int(image.height - bbox["t"] * scale) - 16)
            bottom = min(image.height, int(image.height - bbox["b"] * scale) + 16)
            name = f"{item['self_ref'].rsplit('/', 1)[-1]}.png"
            image.crop((left, top, right, bottom)).convert("RGB").save(assets / name, "PNG")
            uris[item["self_ref"]] = f"assets/{name}"
    return uris


def formula_review(outcome: ParseOutcome) -> list[dict]:
    """Every formula block, queued for human review. Nothing auto-approves."""
    return [
        {
            "block_id": block.block_id,
            "crop": block.image_uri,
            "raw_docling_text": block.text,
            "page": block.region.page,
            "review_status": "PENDING_HUMAN_REVIEW",
            "latex": None,
        }
        for block in outcome.blocks
        if block.block_type is BlockType.FORMULA
    ]


def write_review_csv(review: list[dict]) -> None:
    with (OUT / "formula-review.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "block_id", "crop", "page", "raw_docling_text",
            "review_status", "approved_latex", "reviewer", "notes",
        ])
        writer.writeheader()
        for item in review:
            writer.writerow({
                "block_id": item["block_id"],
                "crop": item["crop"],
                "page": item["page"],
                "raw_docling_text": item["raw_docling_text"],
                "review_status": "PENDING",
                "approved_latex": "",
                "reviewer": "",
                "notes": "",
            })


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    docling = json.loads(DOCLING.read_text(encoding="utf-8"))
    opendataloader = json.loads(OPENDATALOADER.read_text(encoding="utf-8"))
    page_sizes = page_sizes_from_pdf(str(PDF))

    assets = crop_assets(docling)
    primary = blocks_from_docling(
        docling,
        source_id=SOURCE_ID,
        document_id=DOCUMENT_ID,
        page_sizes=page_sizes,
        parser_version=DOCLING_VERSION,
        asset_uris=assets,
    )
    secondary = blocks_from_json(
        opendataloader,
        source_id=SOURCE_ID,
        document_id=DOCUMENT_ID,
        page_sizes=page_sizes,
        parser_version=OPENDATALOADER_VERSION,
    )

    (OUT / "source-blocks.jsonl").write_text(
        "\n".join(block.model_dump_json() for block in primary.blocks) + "\n",
        encoding="utf-8",
    )
    (OUT / "source-blocks-opendataloader.jsonl").write_text(
        "\n".join(block.model_dump_json() for block in secondary.blocks) + "\n",
        encoding="utf-8",
    )

    review = formula_review(primary)
    (OUT / "formula-review-queue.json").write_text(
        json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_review_csv(review)

    diff = diff_outcomes(primary, secondary)
    (OUT / "dual-parse-report.txt").write_text(diff.report() + "\n", encoding="utf-8")

    # §7.1: a page that yields nothing is either blank or unparsed, and the two
    # are indistinguishable from the output. It gates rather than warns.
    empty = primary.empty_pages()

    manifest = {
        "source_id": SOURCE_ID,
        "approval_state": "QUARANTINED",
        "sha256": hashlib.file_digest(PDF.open("rb"), "sha256").hexdigest(),
        "pages": primary.pages,
        "docling_blocks": len(primary.blocks),
        "opendataloader_blocks": len(secondary.blocks),
        "formula_review_queue": len(review),
        "page_coverage_gate": "FAIL" if empty else "PASS",
        "empty_pages": empty,
        "flagged_pages": [p.page for p in diff.flagged_pages],
        "warnings": primary.warnings + secondary.warnings,
        "publication": "FORBIDDEN_PENDING_RIGHTS_RECORD",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    print()
    print(diff.summary())
    if empty:
        raise SystemExit(f"§7.1 page-coverage gate FAILED: empty pages {empty}")


if __name__ == "__main__":
    main()
