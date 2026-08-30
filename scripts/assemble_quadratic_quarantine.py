"""Assemble quarantined citation blocks from the quadratic parser bake-off."""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import csv
from pathlib import Path

import pypdfium2

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.contracts.common import BlockType
from agts.contracts.objects import Region, SourceBlock
from agts.parsing.base import ParseOutcome
from agts.parsing.diff import diff_outcomes
from agts.parsing.docling import blocks_from_docling
from agts.parsing.geometry import page_sizes_from_pdf


PDF = Path(r"D:\onedrive\Desktop\class 10th_maths_4_quadraticEquation.pdf")
DOCLING = Path(r"D:\personal\foxxy\artifacts\quadratic-equations-docling\docling.json")
CHANDRA = Path(r"D:\Downloads\quadratic-chandra\quadratic.json")
OUT = Path(r"D:\personal\agts-retrieval\artifacts\quadratic-equations-quarantine")
SOURCE_ID = "ncert-class-10-maths-ch04-quadratic-equations-2026-27"
DOCUMENT_ID = "quadratic-equations"


def crop_assets(document: dict) -> dict[str, str]:
    assets = OUT / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    pdf = pypdfium2.PdfDocument(PDF)
    uris: dict[str, str] = {}
    for collection in ("texts", "pictures"):
        for item in document.get(collection) or []:
            if item.get("label") not in {"formula", "picture"}:
                continue
            provenance = (item.get("prov") or [None])[0]
            if not provenance:
                continue
            bbox = provenance["bbox"]
            page = pdf[provenance["page_no"] - 1]
            image = page.render(scale=2).to_pil()
            scale = image.width / page.get_size()[0]
            left, right = max(0, int(bbox["l"] * scale) - 16), min(image.width, int(bbox["r"] * scale) + 16)
            top, bottom = max(0, int(image.height - bbox["t"] * scale) - 16), min(image.height, int(image.height - bbox["b"] * scale) + 16)
            name = f"{item['self_ref'].rsplit('/', 1)[-1]}.png"
            image.crop((left, top, right, bottom)).convert("RGB").save(assets / name, "PNG")
            uris[item["self_ref"]] = f"assets/{name}"
    return uris


def chandra_outcome(chandra: dict) -> ParseOutcome:
    blocks: list[SourceBlock] = []
    for page, item in enumerate(chandra["children"], start=1):
        text = html.unescape(re.sub(r"<[^>]+>", " ", item["html"]))
        text = " ".join(text.split())
        blocks.append(SourceBlock(
            block_id=f"{DOCUMENT_ID}:chandra:page-{page}", source_id=SOURCE_ID,
            document_id=DOCUMENT_ID, order_index=page - 1, block_type=BlockType.TEXT_BLOCK,
            region=Region(page=page, x=0, y=0, width=1, height=1), text=text,
            parse_strategy="chandra", parser_version="forge-export", raw_label="Page",
        ))
    return ParseOutcome(strategy="chandra", parser_version="forge-export", blocks=blocks, pages=len(blocks))


def chandra_formula_candidates(chandra: dict) -> dict[int, list[str]]:
    return {
        page: [html.unescape(" ".join(value.split())) for value in re.findall(r'<math display="block">(.*?)</math>', item["html"], re.DOTALL)]
        for page, item in enumerate(chandra["children"], start=1)
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    docling = json.loads(DOCLING.read_text(encoding="utf-8"))
    chandra = json.loads(CHANDRA.read_text(encoding="utf-8"))
    assets = crop_assets(docling)
    docling_outcome = blocks_from_docling(
        docling, source_id=SOURCE_ID, document_id=DOCUMENT_ID,
        page_sizes=page_sizes_from_pdf(str(PDF)), parser_version="2.122.0", asset_uris=assets,
    )
    (OUT / "source-blocks.jsonl").write_text(
        "\n".join(block.model_dump_json() for block in docling_outcome.blocks) + "\n", encoding="utf-8"
    )
    candidates = chandra_formula_candidates(chandra)
    review = [
        {"block_id": block.block_id, "crop": block.image_uri, "raw_docling_text": block.text,
         "chandra_page_candidates": candidates[block.region.page],
         "chandra_status": "PENDING_HUMAN_REVIEW", "latex": None}
        for block in docling_outcome.blocks if block.block_type is BlockType.FORMULA
    ]
    (OUT / "formula-review-queue.json").write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")
    with (OUT / "formula-review.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "block_id", "crop", "raw_docling_text", "chandra_page_candidates",
            "review_status", "approved_latex", "reviewer", "notes",
        ])
        writer.writeheader()
        for item in review:
            writer.writerow({
                "block_id": item["block_id"],
                "crop": item["crop"],
                "raw_docling_text": item["raw_docling_text"],
                "chandra_page_candidates": "\n---\n".join(item["chandra_page_candidates"]),
                "review_status": "PENDING",
                "approved_latex": "",
                "reviewer": "",
                "notes": "",
            })
    diff = diff_outcomes(docling_outcome, chandra_outcome(chandra))
    (OUT / "dual-parse-report.txt").write_text(diff.report() + "\n", encoding="utf-8")
    manifest = {
        "source_id": SOURCE_ID, "approval_state": "QUARANTINED", "sha256": hashlib.file_digest(PDF.open("rb"), "sha256").hexdigest(),
        "docling_blocks": len(docling_outcome.blocks), "formula_review_queue": len(review),
        "warnings": docling_outcome.warnings, "publication": "FORBIDDEN_PENDING_RIGHTS_RECORD",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
