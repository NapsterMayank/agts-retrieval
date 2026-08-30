"""Export a Docling parse of one PDF as JSON, with the R-008 configuration.

    python scripts/export_docling.py <pdf> <out.json>

OCR **on** and formula enrichment **off**, per R-008. Neither is a flag here:
enrichment hallucinated in 23% of formulas and turning OCR off silently dropped
20% of the text, so making either switchable at the call site invites the run
that quietly disagrees with the decision log.

Needs the parser environment (`vendor/parse-spike/.venv`), not the repository's.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    pdf, out = Path(sys.argv[1]), Path(sys.argv[2])
    if not pdf.exists():
        raise SystemExit(f"not found: {pdf}")

    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions()
    options.do_ocr = True
    options.do_formula_enrichment = False
    options.generate_page_images = False

    started = time.perf_counter()
    document = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    ).convert(str(pdf)).document
    seconds = time.perf_counter() - started

    payload = document.export_to_dict()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    pages = len(payload.get("pages") or {})
    print(json.dumps({
        "pdf": str(pdf),
        "out": str(out),
        "seconds": round(seconds, 1),
        "seconds_per_page": round(seconds / pages, 1) if pages else None,
        "pages": pages,
        "texts": len(payload.get("texts") or []),
        "pictures": len(payload.get("pictures") or []),
        "tables": len(payload.get("tables") or []),
    }, indent=2))


if __name__ == "__main__":
    main()
