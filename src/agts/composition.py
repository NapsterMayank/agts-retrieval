"""Deterministic, citation-preserving learning-object composition."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence

from agts.contracts import (
    ApprovalState,
    AuthorityTier,
    BlockType,
    CurriculumIdentity,
    DisclosureClass,
    Language,
    LearningObject,
    Modality,
    ObjectType,
    SourceBlock,
)
from agts.contracts.common import NON_CONTENT_BLOCKS


COMPOSITION_VERSION = "quadratic-section-v1"


def compose_sections(
    blocks: Sequence[SourceBlock],
    *,
    curriculum: CurriculumIdentity,
    section_types: Mapping[str, ObjectType],
    authority_tier: AuthorityTier,
) -> list[LearningObject]:
    """Compose explicit heading sections; never infer curriculum labels from text.

    ``section_types`` is deliberately supplied by the chapter script.  Parsing can
    find headings, but deciding whether a section is a definition or an exercise
    is a curriculum decision.
    """
    ordered = sorted(blocks, key=lambda block: block.order_index)
    starts = [
        index for index, block in enumerate(ordered)
        if block.block_type is BlockType.HEADING and block.text in section_types
    ]
    objects: list[LearningObject] = []
    for number, start in enumerate(starts):
        end = starts[number + 1] if number + 1 < len(starts) else len(ordered)
        section = [block for block in ordered[start:end] if block.block_type not in NON_CONTENT_BLOCKS]
        heading = section[0].text or "Untitled section"
        text = "\n\n".join(block.text for block in section if block.text)
        if not text.strip():
            continue
        has_formula = any(block.block_type is BlockType.FORMULA for block in section)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        objects.append(LearningObject(
            object_id=f"{section[0].document_id}:{COMPOSITION_VERSION}:{number + 1}",
            object_type=section_types[heading],
            source_id=section[0].source_id,
            block_ids=[block.block_id for block in section],
            curriculum=curriculum,
            heading_path=heading,
            text=text,
            language=Language.EN,
            modality=Modality.EQUATION if has_formula else Modality.TEXT,
            authority_tier=authority_tier,
            disclosure_class=DisclosureClass.PUBLIC,
            composition_version=COMPOSITION_VERSION,
            content_hash=digest,
            approval_state=ApprovalState.QUARANTINED,
        ))
    return objects
