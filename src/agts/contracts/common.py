"""Shared vocabulary for every AGTS contract.

Authority: the client AI-native build guide, §6.2 (typed learning objects) and
§6.3 (runtime contracts). These enums are the vocabulary the acceptance gates in
`docs/01-acceptance-gates.md` are written against, so widening one silently
widens a gate. Add a DECISION_LOG entry before changing anything here.
"""

from __future__ import annotations

from enum import StrEnum


class Board(StrEnum):
    """Curriculum authority. Pilot board is not yet named (open question Q1)."""

    CBSE = "cbse"
    ICSE = "icse"
    STATE = "state"


class Language(StrEnum):
    """Query and content languages.

    `HINGLISH` and `TRANSLITERATED` are distinct: the first is romanised Hindi
    mixed with English technical terms, the second is a wholly romanised Hindi
    string. They degrade lexical retrieval differently, so they score as
    separate slices.
    """

    EN = "en"
    HI = "hi"
    HINGLISH = "hinglish"
    TRANSLITERATED = "transliterated"


class Modality(StrEnum):
    TEXT = "text"
    EQUATION = "equation"
    TABLE = "table"
    DIAGRAM = "diagram"
    PAGE_IMAGE = "page_image"


class TeachingAction(StrEnum):
    """The actions a QueryPlan may request (build guide §8.1).

    Retrieval is for an action, not a topic: an explanation, a misconception
    repair and a hint want different evidence from the same concept.
    """

    EXPLAIN = "explain"
    EXPLAIN_SIMPLER = "explain_simpler"
    PREREQUISITE_REPAIR = "prerequisite_repair"
    MISCONCEPTION_CORRECTION = "misconception_correction"
    SOCRATIC_QUESTION = "socratic_question"
    HINT_1 = "hint_1"
    HINT_2 = "hint_2"
    HINT_3 = "hint_3"
    WORKED_EXAMPLE = "worked_example"
    PRACTICE_ITEM = "practice_item"
    ANSWER_FEEDBACK = "answer_feedback"
    REVISION = "revision"
    ENRICHMENT = "enrichment"
    ESCALATION = "escalation"


class DisclosureClass(StrEnum):
    """How far an object may be revealed.

    Ordered least to most protected. The pedagogy controller sets a ceiling per
    turn; anything above it is filtered out *before* ranking, never after.
    """

    PUBLIC = "public"
    HINT_GATED = "hint_gated"
    WORKED_STEP = "worked_step"
    FINAL_ANSWER = "final_answer"
    SOLUTION = "solution"
    RUBRIC = "rubric"
    PROTECTED_ITEM = "protected_item"


#: Rank order for :class:`DisclosureClass`. A ceiling admits everything at or
#: below its own rank.
DISCLOSURE_RANK: dict[DisclosureClass, int] = {
    DisclosureClass.PUBLIC: 0,
    DisclosureClass.HINT_GATED: 1,
    DisclosureClass.WORKED_STEP: 2,
    DisclosureClass.FINAL_ANSWER: 3,
    DisclosureClass.SOLUTION: 4,
    DisclosureClass.RUBRIC: 5,
    DisclosureClass.PROTECTED_ITEM: 6,
}


class AssessmentState(StrEnum):
    """What the learner is doing, which decides the disclosure ceiling."""

    LEARN = "learn"
    GUIDED_PRACTICE = "guided_practice"
    HOMEWORK = "homework"
    GRADED = "graded"
    POST_SUBMISSION = "post_submission"
    REVISION = "revision"


class Role(StrEnum):
    LEARNER = "learner"
    TEACHER = "teacher"
    GUARDIAN = "guardian"
    ADMIN = "admin"
    SYSTEM = "system"


class AuthorityTier(StrEnum):
    """Source trust, highest first."""

    BOARD_OFFICIAL = "board_official"
    SCHOOL_APPROVED = "school_approved"
    LICENSED_PUBLISHER = "licensed_publisher"
    ALFANUMRIK_AUTHORED = "alfanumrik_authored"
    UNTRUSTED_RESEARCH = "untrusted_research"


AUTHORITY_RANK: dict[AuthorityTier, int] = {
    AuthorityTier.BOARD_OFFICIAL: 0,
    AuthorityTier.SCHOOL_APPROVED: 1,
    AuthorityTier.LICENSED_PUBLISHER: 2,
    AuthorityTier.ALFANUMRIK_AUTHORED: 3,
    AuthorityTier.UNTRUSTED_RESEARCH: 4,
}


class ApprovalState(StrEnum):
    """Build guide §5: every source starts QUARANTINED.

    Only a named human reviewer moves a specific checksum and version to
    APPROVED. Verbal assurance is not a rights record.
    """

    QUARANTINED = "QUARANTINED"
    APPROVED = "APPROVED"
    RETIRED = "RETIRED"
    WITHDRAWN = "WITHDRAWN"


class BlockType(StrEnum):
    """What a parser saw on the page — layout, not pedagogy.

    Deliberately separate from :class:`ObjectType`. A parser reports a heading
    or a table cell; it has no idea whether the text is a definition or a
    misconception. Conflating the two vocabularies would push a curriculum
    judgement into the parse stage, where nothing is qualified to make it.

    `UNKNOWN` exists so an unrecognised parser label is recorded rather than
    guessed at. A block typed UNKNOWN is still addressable and can still anchor
    a gold label.
    """

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    TABLE_ROW = "table_row"
    TABLE_CELL = "table_cell"
    CAPTION = "caption"
    FIGURE = "figure"
    IMAGE = "image"
    FORMULA = "formula"
    CODE = "code"
    PAGE_HEADER = "page_header"
    PAGE_FOOTER = "page_footer"
    TEXT_BLOCK = "text_block"
    UNKNOWN = "unknown"


#: Block types that carry no retrievable content on their own. Kept in `blocks`
#: for lineage and page reconstruction, skipped when composing learning objects.
NON_CONTENT_BLOCKS: frozenset[BlockType] = frozenset(
    {BlockType.PAGE_HEADER, BlockType.PAGE_FOOTER}
)


class ObjectType(StrEnum):
    """Typed learning objects (build guide §6.2)."""

    CONCEPT = "concept"
    DEFINITION = "definition"
    EXPLANATION = "explanation"
    MISCONCEPTION = "misconception"
    CORRECTIVE_EXPLANATION = "corrective_explanation"
    COUNTEREXAMPLE = "counterexample"
    WORKED_EXAMPLE = "worked_example"
    WORKED_STEP = "worked_step"
    HINT = "hint"
    QUESTION = "question"
    ANSWER = "answer"
    DISTRACTOR = "distractor"
    RUBRIC = "rubric"
    EQUATION = "equation"
    TOOL_PROOF = "tool_proof"
    TABLE = "table"
    DIAGRAM_REGION = "diagram_region"
    ASSESSMENT_SOLUTION = "assessment_solution"


class EvidenceRole(StrEnum):
    """What an EvidenceSlot is asking for.

    Distinct from :class:`ObjectType`: a slot asks for a *role in the argument*
    and several object types can fill it.
    """

    DEFINITION = "definition"
    EXPLANATION = "explanation"
    PREREQUISITE = "prerequisite"
    MISCONCEPTION = "misconception"
    CORRECTION = "correction"
    EXAMPLE = "example"
    COUNTEREXAMPLE = "counterexample"
    WORKED_EXAMPLE = "worked_example"
    HINT = "hint"
    PRACTICE_ITEM = "practice_item"
    RUBRIC = "rubric"
    VISUAL = "visual"
    TOOL_PROOF = "tool_proof"


class PackStatus(StrEnum):
    """Outcome of the sufficiency gate.

    Abstention is a successful outcome decided before generation, never a model
    judgement (build guide §8.4).
    """

    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    CLARIFY = "CLARIFY"
    ABSTAIN = "ABSTAIN"
    ESCALATE = "ESCALATE"


class QuestionType(StrEnum):
    """Evaluation axis. `NUMERICAL` routes to a tool proof rather than to
    retrieval, and is gated by §14's tool-proof row instead of by recall."""

    SINGLE_HOP = "single_hop"
    MULTI_HOP = "multi_hop"
    NUMERICAL = "numerical"
    VISUAL = "visual"
    MISCONCEPTION = "misconception"
    DEFINITION = "definition"


class LearnerStateClass(StrEnum):
    COLD_START = "cold_start"
    PREREQUISITE_GAP = "prerequisite_gap"
    MISCONCEPTION = "misconception"
    PARTIAL = "partial"
    MASTERED = "mastered"
    FORGETTING = "forgetting"
