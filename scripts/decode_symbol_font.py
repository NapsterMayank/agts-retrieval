"""Decode Symbol-font private-use characters in the parsed chapters (R-054).

    PYTHONPATH=src python scripts/decode_symbol_font.py            # dry run
    PYTHONPATH=src python scripts/decode_symbol_font.py --apply

A PDF that sets operators in Adobe's Symbol font stores them by font position,
and an extractor that cannot resolve the font emits them into the Unicode
private-use area. A minus sign arrives as U+F02D. Nothing is damaged; it is
simply written in an encoding nothing downstream reads, so the retriever saw
noise and the quality gate saw a formula with no relation symbol in it.

This rewrites the text field in place. It changes stored content, so anything
derived from it -- representations, embeddings, every measured number -- has to
be rebuilt afterwards:

    PYTHONPATH=src python scripts/embed_representations.py
    PYTHONPATH=src python scripts/holdout_validation.py
    PYTHONPATH=src python scripts/citation_report.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.parsing.quality import is_unusable
from agts.parsing.symbol_font import decode_symbol_font, undecoded_private_use

ROOT = Path(__file__).parents[1]
CHAPTERS = ["chemical-reactions", "quadratic-equations"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the blocks back")
    args = parser.parse_args()

    total_touched = total_rescued = 0
    unmapped: set[str] = set()

    for chapter in CHAPTERS:
        path = ROOT / "artifacts" / f"{chapter}-quarantine" / "source-blocks.jsonl"
        if not path.exists():
            print(f"{chapter}: no parsed blocks, skipped")
            continue

        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        blocks = [json.loads(line) for line in lines]

        touched, rescued = 0, 0
        for block in blocks:
            text = block.get("text") or ""
            decoded = decode_symbol_font(text)
            if decoded == text:
                continue
            touched += 1
            unmapped |= undecoded_private_use(decoded)
            if is_unusable(text) and not is_unusable(decoded):
                rescued += 1
                print(f"  rescued {block['block_id']} (page {block['region']['page']})")
            block["text"] = decoded

        print(f"{chapter}: {touched} blocks decoded, {rescued} newly readable")
        total_touched += touched
        total_rescued += rescued

        if args.apply and touched:
            path.write_text(
                "\n".join(json.dumps(block, ensure_ascii=False) for block in blocks) + "\n",
                encoding="utf-8",
            )

    print(f"\n{total_touched} blocks decoded, {total_rescued} moved from unreadable to readable")

    if unmapped:
        # A font position with no entry in the table. Never approximate it --
        # look it up in the Symbol encoding, corroborate it, then add it.
        codes = ", ".join(f"U+{ord(character):04X}" for character in sorted(unmapped))
        print(f"WARNING unmapped private-use characters remain: {codes}")

    if not args.apply:
        print("\ndry run -- nothing written. Re-run with --apply.")
    else:
        print("\nWritten. Representations and every measured number must now be rebuilt.")


if __name__ == "__main__":
    main()
