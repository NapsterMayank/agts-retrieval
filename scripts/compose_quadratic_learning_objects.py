"""Create quarantined learning objects for the validated quadratic chapter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.composition import compose_sections
from agts.contracts import AuthorityTier, Board, ObjectType, SourceBlock
from agts.contracts.objects import CurriculumIdentity


INPUT = Path(r"D:\personal\agts-retrieval\artifacts\quadratic-equations-quarantine\source-blocks.jsonl")
OUTPUT = INPUT.parent / "learning-objects.jsonl"

# These are explicit curriculum decisions, not parser guesses.
SECTION_TYPES = {
    "4.1 Introduction": ObjectType.EXPLANATION,
    "4.2 Quadratic Equations": ObjectType.DEFINITION,
    "EXERCISE 4.1": ObjectType.QUESTION,
    "4.3 Solution of a Quadratic Equation by Factorisation": ObjectType.WORKED_EXAMPLE,
    "EXERCISE 4.2": ObjectType.QUESTION,
    "4.4 Nature of Roots": ObjectType.EXPLANATION,
    "EXERCISE 4.3": ObjectType.QUESTION,
    "4.5 Summary": ObjectType.CONCEPT,
}


def main() -> None:
    blocks = [SourceBlock.model_validate_json(line) for line in INPUT.read_text(encoding="utf-8").splitlines()]
    curriculum = CurriculumIdentity(
        board=Board.CBSE, curriculum_version="2026-27", grade="10", subject="mathematics",
        unit_id="quadratic-equations", concept_ids=["quadratic-equations"],
    )
    objects = compose_sections(
        blocks, curriculum=curriculum, section_types=SECTION_TYPES,
        authority_tier=AuthorityTier.BOARD_OFFICIAL,
    )
    OUTPUT.write_text("\n".join(item.model_dump_json() for item in objects) + "\n", encoding="utf-8")
    print(f"Wrote {len(objects)} quarantined learning objects to: {OUTPUT}")


if __name__ == "__main__":
    main()
