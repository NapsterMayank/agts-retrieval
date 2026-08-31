"""Content lineage and typed learning objects (build guide §6.2, §7.2).

Four layers, deliberately separate, because each has a different lifecycle and a
different approval rule (rule 3):

    SourceRecord  -> the registered file, its rights and its approval state
    SourceBlock   -> immutable parse output, addressable by page and region
    LearningObject-> the typed teaching unit, composed from blocks
    SearchRepr    -> the smaller thing that gets embedded and ranked

Gold evaluation labels anchor to :class:`SourceBlock` ids, never to learning
object or search-representation ids (rule 4). That is what lets chunking stay a
free variable: re-compose the objects, re-embed, and the answer key still holds.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import (
    ApprovalState,
    AuthorityTier,
    BlockType,
    Board,
    DisclosureClass,
    Language,
    Modality,
    ObjectType,
)


class Frozen(BaseModel):
    """Contract base. Extra fields are a contract violation, not a convenience."""

    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)


# --------------------------------------------------------------------------
# Rights and source registration
# --------------------------------------------------------------------------


class RightsRecord(Frozen):
    """Build guide §5. Required before a source may leave QUARANTINED.

    `approved_by` is a named human. There is deliberately no field for a verbal
    assurance -- the guide is explicit that one is not a rights record.
    """

    owner: str
    legal_basis: str = Field(description="Licence, permission or statutory basis.")
    permits_storage: bool
    permits_transformation: bool
    permits_display: bool
    permits_model_processing: bool
    attribution_required: str | None = None
    territories: list[str] = Field(default_factory=list)
    term_expires: date | None = None
    approved_by: str = Field(min_length=1)
    approved_at: datetime
    evidence_uri: str = Field(min_length=1, description="Link to the signed record.")


class SourceRecord(Frozen):
    """One registered file. Approval is per checksum *and* per version."""

    source_id: str
    title: str
    publisher: str
    board: Board | None = None
    edition: str
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_tier: AuthorityTier
    language: Language
    approval_state: ApprovalState = ApprovalState.QUARANTINED
    rights: RightsRecord | None = None
    supersedes_source_id: str | None = None
    parser_version: str | None = None
    scanned_clean_at: datetime | None = None

    @model_validator(mode="after")
    def _approval_requires_rights_and_scan(self) -> SourceRecord:
        if self.approval_state is ApprovalState.APPROVED:
            if self.rights is None:
                raise ValueError(
                    f"source {self.source_id}: APPROVED requires a RightsRecord "
                    "with a named approver (build guide §5)"
                )
            if self.scanned_clean_at is None:
                raise ValueError(
                    f"source {self.source_id}: APPROVED requires a completed "
                    "malware/injection scan before any parser sees the file (§7.1)"
                )
        return self


# --------------------------------------------------------------------------
# Immutable parse output
# --------------------------------------------------------------------------


class Region(Frozen):
    """Page coordinates, normalised 0-1 so they survive re-rendering."""

    page: int = Field(ge=1)
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    width: float = Field(gt=0.0, le=1.0)
    height: float = Field(gt=0.0, le=1.0)


class SourceBlock(Frozen):
    """Immutable parse output. The anchor for every gold label.

    `parse_strategy` is recorded because §7.2 requires at least two strategies on
    representative pages -- a block only tells you what it saw, and which parser
    saw it is part of the evidence.
    """

    block_id: str
    source_id: str
    document_id: str
    order_index: int = Field(ge=0)
    block_type: BlockType
    region: Region
    text: str | None = None
    latex: str | None = None
    image_uri: str | None = None
    parse_strategy: str
    parser_version: str
    parser_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    raw_label: str | None = Field(
        default=None,
        description="The parser's own label, kept verbatim. An UNKNOWN block "
        "type is then still diagnosable without re-parsing.",
    )
    linked_block_id: str | None = Field(
        default=None,
        description="The block this one belongs to - a caption to its figure or "
        "table. Composition must never separate the pair, and reconstructing "
        "the link later from page proximity is guesswork the parser already "
        "did properly.",
    )

    @model_validator(mode="after")
    def _block_carries_something(self) -> SourceBlock:
        if not (self.text or self.latex or self.image_uri):
            raise ValueError(
                f"block {self.block_id}: has no text, latex or image. A block "
                "that carries nothing cannot anchor a gold label."
            )
        return self


# --------------------------------------------------------------------------
# Typed learning objects
# --------------------------------------------------------------------------


class CurriculumIdentity(Frozen):
    """Curriculum truth, defined before embeddings exist (rule 2)."""

    board: Board
    curriculum_version: str
    grade: str
    subject: str
    unit_id: str
    concept_ids: list[str] = Field(min_length=1)
    prerequisite_concept_ids: list[str] = Field(default_factory=list)


class LearningObject(Frozen):
    """The teaching unit. Composed from blocks by a pure, versioned function."""

    object_id: str
    object_type: ObjectType
    source_id: str
    block_ids: list[str] = Field(min_length=1)
    curriculum: CurriculumIdentity
    heading_path: str
    text: str
    language: Language
    modality: Modality
    authority_tier: AuthorityTier
    disclosure_class: DisclosureClass
    tenant_scope: str | None = Field(
        default=None, description="None means every tenant; a value restricts it."
    )
    parent_object_id: str | None = None
    misconception_id: str | None = None
    tool_proof_required: bool = False
    composition_version: str
    content_hash: str
    approval_state: ApprovalState = ApprovalState.QUARANTINED
    retired_at: datetime | None = None

    @model_validator(mode="after")
    def _solutions_are_never_public(self) -> LearningObject:
        protected = {
            ObjectType.ASSESSMENT_SOLUTION,
            ObjectType.RUBRIC,
            ObjectType.ANSWER,
        }
        if self.object_type in protected and self.disclosure_class is DisclosureClass.PUBLIC:
            raise ValueError(
                f"object {self.object_id}: {self.object_type} may not be PUBLIC. "
                "Answer protection is structural, not a downstream filter."
            )
        return self


class SearchRepresentation(Frozen):
    """The smaller thing that is embedded and ranked (build guide §7.4).

    Separate from :class:`LearningObject` so the child that *matches* a query can
    differ from the parent that *answers* it, and so re-embedding never
    re-composes.
    """

    representation_id: str
    object_id: str
    block_ids: list[str] = Field(min_length=1)
    search_text: str
    representation_version: str = Field(
        description="The chunking function that produced this. Rechunking bumps "
        "it; re-embedding does not."
    )
    content_hash: str

    #: Embedding is a *later* stage, and these are None until it runs. §7.3 asks
    #: for provider independence, which is only real if a representation can
    #: exist unembedded and be re-embedded by a different provider without being
    #: re-chunked. Requiring a vector here would have forced a fake one for every
    #: lexical run and made "which provider" an unrepeatable decision.
    embedding_model: str | None = None
    embedding_version: str | None = None
    vector: list[float] | None = Field(default=None, min_length=1)

    #: Blocks this window is *findable by* but is not made of: the statement a
    #: worked example continues (rule 5). They are real blocks with real pages,
    #: so the pack can serve and cite them -- what they must never do is count
    #: as this window's own evidence, which is why they are a separate field
    #: rather than more `block_ids` (R-046).
    context_block_ids: list[str] = Field(default_factory=list)

    #: Copied from the parent for reporting and slicing only. Authorisation
    #: still resolves through the parent object -- duplicating a disclosure class
    #: onto the child would create two answers to "may this be shown".
    heading_path: str = ""
    modality: Modality = Modality.TEXT

    @model_validator(mode="after")
    def _lineage_is_present(self) -> SearchRepresentation:
        if not self.search_text.strip():
            raise ValueError(
                f"representation {self.representation_id}: empty search_text. "
                "A published representation missing its text fails the run (§7.4)."
            )
        if (self.vector is None) != (self.embedding_model is None):
            raise ValueError(
                f"representation {self.representation_id}: a vector without the "
                "model that produced it, or a model without a vector. Neither "
                "can be reproduced or re-embedded."
            )
        return self

    @property
    def embedded(self) -> bool:
        return self.vector is not None
