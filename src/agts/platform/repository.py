"""Postgres persistence for the corpus (sections 7.1 and 7.3).

Everything until now lived in JSONL files, which was right while the shapes were
still moving and is wrong now: nothing survives a process, two runs cannot share
an index, and there is no place for a rights record to be recorded against a
checksum.

Two properties this module is responsible for:

**The authorisation filter is applied in SQL, not after the rows arrive.** A
query that fetches everything and filters in Python has already read another
tenant's content into memory, and the difference only shows up in an audit. The
`WHERE` clause here mirrors `Corpus.authorised` exactly, and the pair is checked
by a test that runs both over the same data.

**Writes are idempotent.** Re-running an import must not duplicate blocks or
strand old representations, because a rechunk is a normal operation and the
first thing anyone does after a failed import is run it again.

The connection is psycopg2, taken from `AGTS_DATABASE_URL`. No credentials are
read from anywhere else and none are defaulted: a database that gets written to
because a default pointed at it is the wrong kind of surprise.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path

from agts.contracts.common import DISCLOSURE_RANK, ApprovalState
from agts.contracts.objects import (
    CurriculumIdentity,
    LearningObject,
    Region,
    SearchRepresentation,
    SourceBlock,
    SourceRecord,
)
from agts.contracts.runtime import QueryPlan
from agts.evaluation.corpus import Corpus, EvaluationLicence

MIGRATIONS = Path(__file__).parents[3] / "migrations"


def database_url() -> str | None:
    return os.environ.get("AGTS_DATABASE_URL") or None


@contextmanager
def connect(url: str | None = None):
    """A transaction. Committed on success, rolled back on any exception."""
    import psycopg2

    target = url or database_url()
    if not target:
        raise RuntimeError("set AGTS_DATABASE_URL to a Postgres connection string")
    connection = psycopg2.connect(target)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def migrate(connection, *, with_pgvector: bool = False) -> list[str]:
    """Apply the schema. Returns the migrations that ran.

    `002_pgvector` is opt-in and reports rather than raises when the extension
    is unavailable — a stock Postgres is a supported target, and failing the
    whole import over a missing index would be a lie about what is required.
    """
    applied = []
    with connection.cursor() as cursor:
        cursor.execute((MIGRATIONS / "001_core.sql").read_text(encoding="utf-8"))
        applied.append("001_core")
        if with_pgvector:
            try:
                cursor.execute((MIGRATIONS / "002_pgvector.sql").read_text(encoding="utf-8"))
                applied.append("002_pgvector")
            except Exception as error:  # pragma: no cover - depends on the server
                connection.rollback()
                applied.append(f"002_pgvector SKIPPED: {error}")
    return applied


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------


def save_corpus(connection, corpus: Corpus) -> dict[str, int]:
    """Write sources, blocks, objects and representations. Idempotent."""
    counts = {"sources": 0, "blocks": 0, "objects": 0, "representations": 0}
    with connection.cursor() as cursor:
        for source in corpus.sources.values():
            cursor.execute(
                """
                INSERT INTO sources (source_id, title, publisher, board, edition,
                    checksum_sha256, authority_tier, language, approval_state, rights,
                    supersedes_source_id, parser_version, scanned_clean_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (source_id) DO UPDATE SET
                    approval_state = EXCLUDED.approval_state,
                    rights = EXCLUDED.rights,
                    scanned_clean_at = EXCLUDED.scanned_clean_at
                """,
                (
                    source.source_id, source.title, source.publisher,
                    source.board.value if source.board else None, source.edition,
                    source.checksum_sha256, source.authority_tier.value,
                    source.language.value, source.approval_state.value,
                    json.dumps(source.rights.model_dump(mode="json")) if source.rights else None,
                    source.supersedes_source_id, source.parser_version,
                    source.scanned_clean_at,
                ),
            )
            counts["sources"] += 1

        for block in corpus.blocks.values():
            cursor.execute(
                """
                INSERT INTO blocks (block_id, source_id, document_id, order_index,
                    block_type, raw_label, page, region_x, region_y, region_width,
                    region_height, text, latex, image_uri, parse_strategy,
                    parser_version, parser_confidence, linked_block_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (block_id) DO NOTHING
                """,
                (
                    block.block_id, block.source_id, block.document_id, block.order_index,
                    block.block_type.value, block.raw_label, block.region.page,
                    block.region.x, block.region.y, block.region.width, block.region.height,
                    block.text, block.latex, block.image_uri, block.parse_strategy,
                    block.parser_version, block.parser_confidence, block.linked_block_id,
                ),
            )
            counts["blocks"] += 1

        for obj in corpus.objects.values():
            cursor.execute(
                """
                INSERT INTO learning_objects (object_id, object_type, source_id, board,
                    curriculum_version, grade, subject, unit_id, concept_ids,
                    prerequisite_concept_ids, heading_path, text, language, modality,
                    authority_tier, disclosure_class, tenant_scope, parent_object_id,
                    misconception_id, tool_proof_required, composition_version,
                    content_hash, approval_state, retired_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (object_id) DO UPDATE SET
                    approval_state = EXCLUDED.approval_state,
                    retired_at = EXCLUDED.retired_at
                """,
                (
                    obj.object_id, obj.object_type.value, obj.source_id,
                    obj.curriculum.board.value, obj.curriculum.curriculum_version,
                    obj.curriculum.grade, obj.curriculum.subject, obj.curriculum.unit_id,
                    obj.curriculum.concept_ids, obj.curriculum.prerequisite_concept_ids,
                    obj.heading_path, obj.text, obj.language.value, obj.modality.value,
                    obj.authority_tier.value, obj.disclosure_class.value, obj.tenant_scope,
                    obj.parent_object_id, obj.misconception_id, obj.tool_proof_required,
                    obj.composition_version, obj.content_hash, obj.approval_state.value,
                    obj.retired_at,
                ),
            )
            cursor.executemany(
                """
                INSERT INTO learning_object_blocks (object_id, block_id, position)
                VALUES (%s,%s,%s) ON CONFLICT (object_id, block_id) DO NOTHING
                """,
                [(obj.object_id, b, i) for i, b in enumerate(obj.block_ids)],
            )
            counts["objects"] += 1

        for rep in corpus.representations.values():
            cursor.execute(
                """
                INSERT INTO search_representations (representation_id, object_id,
                    search_text, representation_version, content_hash, heading_path,
                    modality, embedding_model, embedding_version, embedding)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (representation_id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    embedding_model = EXCLUDED.embedding_model,
                    embedding_version = EXCLUDED.embedding_version
                """,
                (
                    rep.representation_id, rep.object_id, rep.search_text,
                    rep.representation_version, rep.content_hash, rep.heading_path,
                    rep.modality.value, rep.embedding_model, rep.embedding_version,
                    rep.vector,
                ),
            )
            cursor.executemany(
                """
                INSERT INTO representation_blocks (representation_id, block_id, position)
                VALUES (%s,%s,%s) ON CONFLICT (representation_id, block_id) DO NOTHING
                """,
                [(rep.representation_id, b, i) for i, b in enumerate(rep.block_ids)],
            )
            counts["representations"] += 1

    return counts


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def _block_from_row(row) -> SourceBlock:
    return SourceBlock(
        block_id=row[0], source_id=row[1], document_id=row[2], order_index=row[3],
        block_type=row[4], raw_label=row[5],
        region=Region(page=row[6], x=row[7], y=row[8], width=row[9], height=row[10]),
        text=row[11], latex=row[12], image_uri=row[13], parse_strategy=row[14],
        parser_version=row[15], parser_confidence=row[16], linked_block_id=row[17],
    )


def load_corpus(
    connection, *, licence: EvaluationLicence | None = None
) -> Corpus:
    """Read the whole corpus back into memory.

    Deliberately not a query path: it exists so a stored corpus can be scored by
    the same in-memory harness that scores a freshly parsed one, which is what
    makes a persistence change measurable rather than merely plausible.
    """
    sources: dict[str, SourceRecord] = {}
    blocks: dict[str, SourceBlock] = {}
    objects: dict[str, LearningObject] = {}
    representations: dict[str, SearchRepresentation] = {}

    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT source_id, title, publisher, board, edition, checksum_sha256,
                      authority_tier, language, approval_state, rights,
                      supersedes_source_id, parser_version, scanned_clean_at
               FROM sources"""
        )
        for row in cursor.fetchall():
            sources[row[0]] = SourceRecord(
                source_id=row[0], title=row[1], publisher=row[2], board=row[3],
                edition=row[4], checksum_sha256=row[5], authority_tier=row[6],
                language=row[7], approval_state=row[8],
                rights=row[9], supersedes_source_id=row[10], parser_version=row[11],
                scanned_clean_at=row[12],
            )

        cursor.execute(
            """SELECT block_id, source_id, document_id, order_index, block_type,
                      raw_label, page, region_x, region_y, region_width, region_height,
                      text, latex, image_uri, parse_strategy, parser_version,
                      parser_confidence, linked_block_id
               FROM blocks"""
        )
        for row in cursor.fetchall():
            block = _block_from_row(row)
            blocks[block.block_id] = block

        cursor.execute(
            """SELECT o.object_id, o.object_type, o.source_id, o.board, o.curriculum_version,
                      o.grade, o.subject, o.unit_id, o.concept_ids, o.prerequisite_concept_ids,
                      o.heading_path, o.text, o.language, o.modality, o.authority_tier,
                      o.disclosure_class, o.tenant_scope, o.parent_object_id,
                      o.misconception_id, o.tool_proof_required, o.composition_version,
                      o.content_hash, o.approval_state, o.retired_at,
                      array_agg(b.block_id ORDER BY b.position)
               FROM learning_objects o
               JOIN learning_object_blocks b ON b.object_id = o.object_id
               GROUP BY o.object_id"""
        )
        for row in cursor.fetchall():
            objects[row[0]] = LearningObject(
                object_id=row[0], object_type=row[1], source_id=row[2],
                curriculum=CurriculumIdentity(
                    board=row[3], curriculum_version=row[4], grade=row[5], subject=row[6],
                    unit_id=row[7], concept_ids=row[8], prerequisite_concept_ids=row[9],
                ),
                heading_path=row[10], text=row[11], language=row[12], modality=row[13],
                authority_tier=row[14], disclosure_class=row[15], tenant_scope=row[16],
                parent_object_id=row[17], misconception_id=row[18],
                tool_proof_required=row[19], composition_version=row[20],
                content_hash=row[21], approval_state=row[22], retired_at=row[23],
                block_ids=row[24],
            )

        cursor.execute(
            """SELECT r.representation_id, r.object_id, r.search_text,
                      r.representation_version, r.content_hash, r.heading_path, r.modality,
                      r.embedding_model, r.embedding_version, r.embedding,
                      array_agg(rb.block_id ORDER BY rb.position)
               FROM search_representations r
               JOIN representation_blocks rb ON rb.representation_id = r.representation_id
               GROUP BY r.representation_id"""
        )
        for row in cursor.fetchall():
            vector = list(row[9]) if row[9] is not None else None
            representations[row[0]] = SearchRepresentation(
                representation_id=row[0], object_id=row[1], search_text=row[2],
                representation_version=row[3], content_hash=row[4], heading_path=row[5],
                modality=row[6], embedding_model=row[7], embedding_version=row[8],
                vector=vector, block_ids=row[10],
            )

    return Corpus(
        sources=sources, blocks=blocks, objects=objects,
        representations=representations, evaluation_licence=licence,
    )


def authorised_object_ids(connection, plan: QueryPlan, *, licensed_sources: tuple[str, ...] = ()) -> list[str]:
    """The section 5 filter, in SQL.

    Mirrors `Corpus.authorised`. Filtering after the rows arrive means another
    tenant's content was already read into this process, and that difference is
    invisible until an audit asks for it.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT o.object_id
            FROM learning_objects o
            JOIN sources s ON s.source_id = o.source_id
            WHERE o.retired_at IS NULL
              AND (
                    (o.approval_state = %(approved)s AND s.approval_state = %(approved)s)
                 OR (o.approval_state = %(quarantined)s AND s.approval_state = %(quarantined)s
                     AND o.source_id = ANY(%(licensed)s))
              )
              AND (o.tenant_scope IS NULL OR o.tenant_scope = %(tenant)s)
              AND o.grade = %(grade)s
              AND o.subject = %(subject)s
              AND o.board = %(board)s
              AND o.curriculum_version = %(version)s
              AND o.disclosure_class = ANY(%(allowed_disclosure)s)
              AND NOT (o.object_id = ANY(%(forbidden)s))
            ORDER BY o.object_id
            """,
            {
                "approved": ApprovalState.APPROVED.value,
                "quarantined": ApprovalState.QUARANTINED.value,
                "licensed": list(licensed_sources),
                "tenant": plan.learner.tenant_id,
                "grade": plan.curriculum.grade,
                "subject": plan.curriculum.subject,
                "board": plan.curriculum.board.value,
                "version": plan.curriculum.curriculum_version,
                # The ceiling admits everything at or below its own rank. Computed
                # here rather than encoded as SQL so there is one rank table,
                # not two that can drift.
                "allowed_disclosure": [
                    cls.value
                    for cls, rank in DISCLOSURE_RANK.items()
                    if rank <= DISCLOSURE_RANK[plan.disclosure.max_disclosure]
                ],
                "forbidden": list(plan.disclosure.forbidden_object_ids),
            },
        )
        return [row[0] for row in cursor.fetchall()]
