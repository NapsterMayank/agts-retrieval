"""Search representations: the unit that is ranked (§7.3, R-015).

A learning object is a *teaching* unit — one chapter section, sometimes several
thousand characters. Ranking those directly is what made the first real-content
run fail: an object that large contains a plausible lexical match for almost any
in-subject query, so answerable and unanswerable queries stopped separating
(margin −0.497) and no abstention threshold existed.

So retrieval gets its own unit, derived from blocks, with the object kept as the
parent that answers and cites. Four rules, each earned:

1. **A block is never split.** Blocks are the anchor for every gold label and
   every citation (rule 4). A representation that ends mid-block cannot cite the
   half it used.
2. **A caption travels with what it captions.** `linked_block_id` is a pairing
   the parser already resolved; splitting it and rebuilding it later from page
   proximity is guesswork.
3. **A formula is never alone.** Formula text is degraded by construction
   (R-008) — the maths chapter yields `a  0` for *a ≠ 0*. A window of nothing
   but formulas is unsearchable text; attached to the prose around it, it is
   reachable and still individually citable.
4. **The heading path prefixes every window.** It is the one piece of context a
   window loses by being small, it is short, and it is what makes "1.2.2
   Decomposition Reaction" findable from the paragraph that never repeats the
   word.

Deterministic and model-free: same blocks in, same representations out, so a
representation id is stable across runs and a rechunk is a diff rather than a
mystery.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence

from agts.contracts.common import NON_CONTENT_BLOCKS, BlockType, Modality
from agts.contracts.objects import LearningObject, SearchRepresentation, SourceBlock


#: Bump when the chunking function changes. Representation ids embed it, so two
#: versions can coexist in one store and be compared on the same gold set.
REPRESENTATION_VERSION = "block-window-v1"

#: Target characters per window. Not a token count: tokenisation belongs to a
#: provider, and this stage is provider-independent on purpose (§7.3).
TARGET_CHARS = 700

#: A window is closed once it passes TARGET_CHARS; this is the point past which
#: a single oversized block is allowed to stand alone rather than be split.
MAX_CHARS = 1400

#: Windows shorter than this are merged into the neighbour rather than shipped.
#: A twelve-character representation matches almost nothing and, when it does,
#: matches it at a confidence the score cannot justify.
MIN_CHARS = 120

_FORMULA_LIKE = {BlockType.FORMULA, BlockType.CODE}


def _text_of(block: SourceBlock) -> str:
    return " ".join((block.text or block.latex or "").split())


def _searchable(blocks: Iterable[SourceBlock]) -> list[SourceBlock]:
    """Content blocks, in reading order.

    Page headers and footers are dropped: they repeat on every page, so they add
    a constant to every score without distinguishing anything.
    """
    return sorted(
        (b for b in blocks if b.block_type not in NON_CONTENT_BLOCKS and _text_of(b)),
        key=lambda b: b.order_index,
    )


def _window_modality(blocks: Sequence[SourceBlock]) -> Modality:
    types = {b.block_type for b in blocks}
    if types & _FORMULA_LIKE:
        return Modality.EQUATION
    if BlockType.TABLE in types:
        return Modality.TABLE
    if types & {BlockType.FIGURE, BlockType.IMAGE}:
        return Modality.DIAGRAM
    return Modality.TEXT


def _group(blocks: Sequence[SourceBlock]) -> list[list[SourceBlock]]:
    """Blocks that must stay together, in reading order.

    A caption and its target, and a formula with the block before it. Both are
    pairings the window boundary must not fall inside.
    """
    by_id = {b.block_id: b for b in blocks}
    attached_to: dict[str, str] = {}

    for block in blocks:
        if block.linked_block_id and block.linked_block_id in by_id:
            attached_to[block.block_id] = block.linked_block_id

    groups: list[list[SourceBlock]] = []
    index_of: dict[str, int] = {}
    for block in blocks:
        anchor = attached_to.get(block.block_id)
        if anchor is not None and anchor in index_of:
            groups[index_of[anchor]].append(block)
            index_of[block.block_id] = index_of[anchor]
            continue
        if block.block_type in _FORMULA_LIKE and groups:
            # Rule 3. The block before a formula is the sentence that introduces
            # it, which is what a learner's words will actually match.
            groups[-1].append(block)
            index_of[block.block_id] = len(groups) - 1
            continue
        groups.append([block])
        index_of[block.block_id] = len(groups) - 1
    return groups


def _windows(groups: Sequence[Sequence[SourceBlock]]) -> list[list[SourceBlock]]:
    windows: list[list[SourceBlock]] = []
    current: list[SourceBlock] = []
    length = 0

    for group in groups:
        group_length = sum(len(_text_of(b)) + 1 for b in group)
        if current and length + group_length > MAX_CHARS:
            windows.append(current)
            current, length = [], 0
        current.extend(group)
        length += group_length
        if length >= TARGET_CHARS:
            windows.append(current)
            current, length = [], 0

    if current:
        windows.append(current)

    # A short tail is merged backwards rather than shipped as its own window.
    if len(windows) > 1 and sum(len(_text_of(b)) for b in windows[-1]) < MIN_CHARS:
        tail = windows.pop()
        windows[-1].extend(tail)
    return windows


def represent(
    obj: LearningObject,
    blocks: Sequence[SourceBlock],
    *,
    version: str = REPRESENTATION_VERSION,
) -> list[SearchRepresentation]:
    """Chunk one learning object into the units that get ranked.

    `blocks` is the corpus's block table; only those the object cites are used,
    so an object can be rechunked without re-reading the document.
    """
    by_id = {b.block_id: b for b in blocks}
    owned = _searchable(by_id[bid] for bid in obj.block_ids if bid in by_id)
    if not owned:
        return []

    representations: list[SearchRepresentation] = []
    for number, window in enumerate(_windows(_group(owned)), start=1):
        body = "\n".join(_text_of(b) for b in window if _text_of(b))
        if not body.strip():
            continue
        # Rule 4: the heading is context the window cannot carry on its own.
        search_text = f"{obj.heading_path}\n{body}" if obj.heading_path else body
        representations.append(
            SearchRepresentation(
                representation_id=f"{obj.object_id}:{version}:{number}",
                object_id=obj.object_id,
                block_ids=[b.block_id for b in window],
                search_text=search_text,
                representation_version=version,
                content_hash=hashlib.sha256(search_text.encode("utf-8")).hexdigest(),
                heading_path=obj.heading_path,
                modality=_window_modality(window),
            )
        )
    return representations


def represent_all(
    objects: Iterable[LearningObject],
    blocks: Sequence[SourceBlock],
    *,
    version: str = REPRESENTATION_VERSION,
) -> list[SearchRepresentation]:
    return [r for obj in objects for r in represent(obj, blocks, version=version)]
