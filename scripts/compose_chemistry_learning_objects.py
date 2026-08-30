"""Create quarantined learning objects for NCERT Class 10 Science, chapter 1.

The section map below is a **curriculum decision written by hand**, exactly as in
the quadratic script: parsing can find a heading, but deciding that "Activity
1.4" is a worked example and "E X E R C I S E S" is a set of questions is a
judgement no parse stage is qualified to make (R-009).

Headings absent from the map are not sections. Docling labels a few figure
captions and stray lines as headings ("Figure 1.2", "Barium bromide(s)"); leaving
them out folds their blocks into the section they belong to, which is what a
reader would do.

    python scripts/compose_chemistry_learning_objects.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agts.composition import compose_sections
from agts.contracts import AuthorityTier, Board, ObjectType, SourceBlock
from agts.contracts.objects import CurriculumIdentity


INPUT = Path(__file__).parents[1] / "artifacts" / "chemical-reactions-quarantine" / "source-blocks.jsonl"
OUTPUT = INPUT.parent / "learning-objects.jsonl"

# Heading strings are copied **verbatim** from the parse, doubled glyphs and all
# — see the heading-doubling note in EVALUATION_LEDGER.md. Silently rewriting
# them here would hide a real extraction defect behind a tidy-looking map.
SECTION_TYPES = {
    "Chemical Reactions and Equations CHAPTER1": ObjectType.EXPLANATION,
    "Activity  1.1 Activity  1.1": ObjectType.WORKED_EXAMPLE,
    "Activity  1.2 Activity  1.2": ObjectType.WORKED_EXAMPLE,
    "Activity  1.3 Activity  1.3": ObjectType.WORKED_EXAMPLE,
    "1.1  CHEMIC 1.1  CHEMICAL  EQUA AL  EQUATIONS TIONS": ObjectType.CONCEPT,
    "1.1.1 Writing a Chemical Equation": ObjectType.EXPLANATION,
    "1.1.2 Balanced Chemical Equations": ObjectType.DEFINITION,
    "1.2  TYPES  OF  CHEMIC 1.2  TYPES  OF  CHEMICAL  REA AL  REACTIONS CTIONS": ObjectType.CONCEPT,
    "1.2.1 Combination Reaction": ObjectType.DEFINITION,
    "Activity  1.4 Activity  1.4": ObjectType.WORKED_EXAMPLE,
    "1.2.2 Decomposition Reaction": ObjectType.DEFINITION,
    "Activity  1.5 Activity  1.5": ObjectType.WORKED_EXAMPLE,
    "Activity  1.6 Activity  1.6": ObjectType.WORKED_EXAMPLE,
    "Activity  1.7 Activity  1.7": ObjectType.WORKED_EXAMPLE,
    "Activity  1.8 Activity  1.8": ObjectType.WORKED_EXAMPLE,
    "1.2.3  Displacement Reaction": ObjectType.DEFINITION,
    "Activity  1.9 Activity  1.9": ObjectType.WORKED_EXAMPLE,
    "1.2.4 Double Displacement Reaction": ObjectType.DEFINITION,
    "Activity  1.10 Activity  1.10": ObjectType.WORKED_EXAMPLE,
    "1.2.5 Oxidation and Reduction": ObjectType.DEFINITION,
    "Activity  1.11 Activity  1.11": ObjectType.WORKED_EXAMPLE,
    "1.3 1.3 HA HAVE YOU OBSERVED THE EFFECTS OF O VE  YOU  OBSERVED  THE  EFFECTS  OF  OXID XIDA ATION TION REA REACTIONS  IN  EVERYD CTIONS  IN  EVERYDA AY  LIFE? Y  LIFE?": ObjectType.CONCEPT,
    "1.3.1 Corrosion": ObjectType.DEFINITION,
    "1.3.2  Rancidity": ObjectType.DEFINITION,
    "Q U E S T I O N S": ObjectType.QUESTION,
    "What you have learnt": ObjectType.CONCEPT,
    "E X E R C I S E S": ObjectType.QUESTION,
    "Group  Activity": ObjectType.WORKED_EXAMPLE,
}


def main() -> None:
    blocks = [
        SourceBlock.model_validate_json(line)
        for line in INPUT.read_text(encoding="utf-8").splitlines()
    ]
    curriculum = CurriculumIdentity(
        board=Board.CBSE,
        curriculum_version="2026-27",
        grade="10",
        subject="science",
        unit_id="chemical-reactions-and-equations",
        concept_ids=["chemical-reactions-and-equations"],
    )
    objects = compose_sections(
        blocks,
        curriculum=curriculum,
        section_types=SECTION_TYPES,
        authority_tier=AuthorityTier.BOARD_OFFICIAL,
    )
    OUTPUT.write_text(
        "\n".join(item.model_dump_json() for item in objects) + "\n", encoding="utf-8"
    )
    covered = sum(len(item.block_ids) for item in objects)
    print(json.dumps({
        "objects": len(objects),
        "blocks_in": len(blocks),
        "blocks_covered": covered,
        "output": str(OUTPUT),
    }, indent=2))
    for item in objects:
        print(f"  {item.object_type.value:<15} {len(item.block_ids):>3} blocks  {item.heading_path}")


if __name__ == "__main__":
    main()
