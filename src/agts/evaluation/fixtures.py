"""Disposable synthetic fixtures.

Build guide §5 permits scaffolding against synthetic fixtures while the pilot
curriculum, source rights and privacy decisions are pending. **None of this is
curriculum content and none of it may reach a student.** It exists to prove the
contracts hold and the scorer can expose a broken retriever, and it is deleted
the moment an approved pilot source is registered.

The corpus is built with four traps in it, one per broken retriever in
:mod:`agts.evaluation.retrievers`:

    * grade-7 near-duplicates of grade-10 content  -> WrongGrade has bait
    * solution and rubric objects                  -> AnswerOnly has bait
    * another tenant's private notes               -> CrossTenant has bait
    * a QUARANTINED source                         -> nothing may ever return it
"""

from __future__ import annotations

from datetime import UTC, datetime

from agts.contracts.common import (
    ApprovalState,
    AuthorityTier,
    BlockType,
    Board,
    DisclosureClass,
    Language,
    Modality,
    ObjectType,
    QuestionType,
    TeachingAction,
)
from agts.contracts.objects import (
    CurriculumIdentity,
    LearningObject,
    Region,
    RightsRecord,
    SourceBlock,
    SourceRecord,
)
from agts.evaluation.cases import EvalCase, GoldSet
from agts.evaluation.corpus import Corpus

_NOW = datetime(2026, 8, 24, tzinfo=UTC)
_TENANT = "tenant-pilot"
_OTHER_TENANT = "tenant-other"
_HASH = "0" * 64


def _rights(owner: str) -> RightsRecord:
    return RightsRecord(
        owner=owner,
        legal_basis="synthetic fixture - no real rights involved",
        permits_storage=True,
        permits_transformation=True,
        permits_display=True,
        permits_model_processing=True,
        approved_by="fixture-builder",
        approved_at=_NOW,
        evidence_uri="fixture://no-real-source",
    )


def _source(source_id: str, *, approved: bool, grade_hint: str) -> SourceRecord:
    return SourceRecord(
        source_id=source_id,
        title=f"Synthetic {grade_hint} reader",
        publisher="fixture",
        board=Board.CBSE,
        edition="fixture-1",
        checksum_sha256=_HASH,
        authority_tier=AuthorityTier.BOARD_OFFICIAL,
        language=Language.EN,
        approval_state=ApprovalState.APPROVED if approved else ApprovalState.QUARANTINED,
        rights=_rights("fixture") if approved else None,
        scanned_clean_at=_NOW if approved else None,
    )


def _block(block_id: str, source_id: str, order: int, text: str) -> SourceBlock:
    return SourceBlock(
        block_id=block_id,
        source_id=source_id,
        document_id=f"{source_id}-doc",
        order_index=order,
        block_type=BlockType.PARAGRAPH,
        region=Region(page=order + 1, x=0.1, y=0.1, width=0.8, height=0.2),
        text=text,
        parse_strategy="fixture",
        parser_version="0",
    )


def _object(
    object_id: str,
    source_id: str,
    block_ids: list[str],
    text: str,
    *,
    grade: str = "10",
    subject: str = "science",
    object_type: ObjectType = ObjectType.EXPLANATION,
    disclosure: DisclosureClass = DisclosureClass.PUBLIC,
    tenant_scope: str | None = None,
    approved: bool = True,
    concept_id: str = "c-reflection",
) -> LearningObject:
    return LearningObject(
        object_id=object_id,
        object_type=object_type,
        source_id=source_id,
        block_ids=block_ids,
        curriculum=CurriculumIdentity(
            board=Board.CBSE,
            curriculum_version="pilot-0",
            grade=grade,
            subject=subject,
            unit_id=f"{subject}-u1",
            concept_ids=[concept_id],
        ),
        heading_path=f"Grade {grade} > {subject} > unit 1",
        text=text,
        language=Language.EN,
        modality=Modality.TEXT,
        authority_tier=AuthorityTier.BOARD_OFFICIAL,
        disclosure_class=disclosure,
        tenant_scope=tenant_scope,
        composition_version="0",
        content_hash=_HASH,
        approval_state=ApprovalState.APPROVED if approved else ApprovalState.QUARANTINED,
    )


#: (object suffix, concept, grade-10 text, the query that should find it)
_TOPICS: list[tuple[str, str, str, str]] = [
    ("reflection", "c-reflection",
     "Regular reflection happens when parallel rays strike a smooth polished surface.",
     "why does a smooth polished surface give regular reflection"),
    ("refraction", "c-refraction",
     "Refraction is the bending of light when it passes between two transparent media.",
     "what is refraction of light between two transparent media"),
    ("mirror", "c-mirror",
     "A concave mirror converges parallel rays towards its principal focus.",
     "how does a concave mirror converge parallel rays"),
    ("lens", "c-lens",
     "A convex lens forms a real inverted image when the object is beyond the focus.",
     "when does a convex lens form a real inverted image"),
    ("dispersion", "c-dispersion",
     "Dispersion splits white light into its constituent colours through a prism.",
     "how does a prism cause dispersion of white light"),
    ("scattering", "c-scattering",
     "Scattering of shorter wavelengths by air molecules makes the sky appear blue.",
     "why does scattering make the sky appear blue"),
]


#: Authorised, on-grade, on-subject content that shares no vocabulary with any
#: evaluation query. Its only job is to make the authorised candidate pool much
#: larger than `k_pack`, so a random ranker cannot look competent by luck.
_FILLER: list[str] = [
    "Sodium reacts vigorously producing hydrogen gas.",
    "Chlorophyll absorbs energy inside plant chloroplasts.",
    "Neurons transmit impulses across synaptic junctions.",
    "Ohm relates potential difference, current and resistance.",
    "Magnesium ribbon burns forming white oxide powder.",
    "Kidneys filter blood through millions of nephrons.",
    "Ionic compounds conduct electricity when molten.",
    "Fossils record evolutionary change across geological eras.",
    "Ozone shields organisms from ultraviolet radiation.",
    "Solenoids generate uniform magnetic fields internally.",
    "Xylem transports water upward against gravity.",
    "Catalysts accelerate reactions without being consumed.",
    "Mendel studied inheritance using pea plants.",
    "Alveoli maximise surface area for gaseous exchange.",
    "Isotopes differ only by neutron count.",
    "Ecosystems transfer energy through trophic levels.",
    "Acids donate protons in aqueous solution.",
    "Generators convert mechanical motion into electricity.",
    "Hormones coordinate slow, sustained physiological responses.",
    "Carbon forms four covalent bonds readily.",
]


def build_corpus() -> Corpus:
    """Synthetic corpus carrying all four traps."""
    sources = {
        "s-g10": _source("s-g10", approved=True, grade_hint="grade 10"),
        "s-g7": _source("s-g7", approved=True, grade_hint="grade 7"),
        "s-quarantined": _source("s-quarantined", approved=False, grade_hint="unapproved"),
    }

    blocks: dict[str, SourceBlock] = {}
    objects: dict[str, LearningObject] = {}

    for i, (suffix, concept, text, _query) in enumerate(_TOPICS):
        # The grade-10 truth.
        bid = f"b-g10-{suffix}"
        blocks[bid] = _block(bid, "s-g10", i, text)
        oid = f"o-g10-{suffix}"
        objects[oid] = _object(oid, "s-g10", [bid], text, concept_id=concept)

        # Trap 1: a topically similar grade-7 passage. Right subject, wrong grade,
        # different blocks -- so preferring it destroys recall without reducing
        # apparent relevance.
        bid7 = f"b-g7-{suffix}"
        blocks[bid7] = _block(bid7, "s-g7", i, f"Simplified note: {text}")
        oid7 = f"o-g7-{suffix}"
        objects[oid7] = _object(
            oid7, "s-g7", [bid7], f"Simplified note: {text}", grade="7", concept_id=concept
        )

        # Trap 2: the protected solution for the same concept.
        bids = f"b-sol-{suffix}"
        blocks[bids] = _block(bids, "s-g10", i, f"Solution: {text} Answer is worked below.")
        oids = f"o-sol-{suffix}"
        objects[oids] = _object(
            oids,
            "s-g10",
            [bids],
            f"Solution: {text} Answer is worked below.",
            object_type=ObjectType.ASSESSMENT_SOLUTION,
            disclosure=DisclosureClass.SOLUTION,
            concept_id=concept,
        )

    # Authorised filler on unrelated concepts. Not a trap -- a denominator.
    # Without it the authorised pool is barely larger than k_pack, and a random
    # ranker would score well by accident, which would make the §6.5 detection
    # test pass for the wrong reason.
    for i, filler in enumerate(_FILLER):
        bid = f"b-fill-{i}"
        blocks[bid] = _block(bid, "s-g10", 20 + i, filler)
        oid = f"o-fill-{i}"
        objects[oid] = _object(oid, "s-g10", [bid], filler, concept_id=f"c-fill-{i}")

    # Trap 3: another tenant's private material.
    bid_other = "b-other-tenant"
    blocks[bid_other] = _block(
        bid_other, "s-g10", 90, "School B internal note on reflection and refraction."
    )
    objects["o-other-tenant"] = _object(
        "o-other-tenant",
        "s-g10",
        [bid_other],
        "School B internal note on reflection and refraction.",
        tenant_scope=_OTHER_TENANT,
    )

    # Trap 4: content from a source that was never approved.
    bid_q = "b-quarantined"
    blocks[bid_q] = _block(
        bid_q, "s-quarantined", 91, "Unapproved third-party note about refraction."
    )
    objects["o-quarantined"] = _object(
        "o-quarantined",
        "s-quarantined",
        [bid_q],
        "Unapproved third-party note about refraction.",
        approved=False,
    )

    return Corpus(sources=sources, blocks=blocks, objects=objects)


def build_gold_set() -> GoldSet:
    """Six answerable cases and three unanswerable ones.

    Far below the 300-500 §6.4 requires and far below the n>=20 a slice needs to
    gate. That is the point: this proves the harness runs, and the real set is
    blocked on the named pilot curriculum (open question Q1).
    """
    cases: list[EvalCase] = []

    for suffix, concept, _text, query in _TOPICS:
        cases.append(
            EvalCase(
                case_id=f"ans-{suffix}",
                query=query,
                grade="10",
                subject="science",
                question_type=QuestionType.SINGLE_HOP,
                teaching_action=TeachingAction.EXPLAIN,
                concept_ids=[concept],
                gold_block_ids=[f"b-g10-{suffix}"],
                answerable=True,
                origin="fixture",
            )
        )

    unanswerable = [
        ("oos-history", "who signed the treaty of versailles", "c-reflection"),
        ("oos-nonsense", "purple recursion sandwich telephone", "c-refraction"),
        ("oos-grade", "explain eigenvalue decomposition of a hermitian matrix", "c-lens"),
    ]
    for case_id, query, concept in unanswerable:
        cases.append(
            EvalCase(
                case_id=case_id,
                query=query,
                grade="10",
                subject="science",
                question_type=QuestionType.SINGLE_HOP,
                teaching_action=TeachingAction.EXPLAIN,
                concept_ids=[concept],
                gold_block_ids=[],
                answerable=False,
                adjudicators=["fixture-a", "fixture-b"],
                origin="fixture",
            )
        )

    return GoldSet(gold_set_id="fixture-0", cases=cases)
