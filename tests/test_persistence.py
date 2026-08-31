"""Persistence round-trip, against a real Postgres.

Skipped unless `AGTS_DATABASE_URL` is set. A mocked database proves that the
mock matches the code, which is the thing R-010 was written about: the
opendataloader adapter passed its unit tests and then rendered every real table
as an empty grid, because the fixture encoded an assumption instead of the
parser's actual output. A schema is exactly the same kind of surface.

Each test runs in a transaction that is rolled back, so a configured database is
left as it was found.
"""

from __future__ import annotations

import os

import pytest

from agts.contracts.common import (
    ApprovalState, AuthorityTier, BlockType, Board, DisclosureClass, Language,
    Modality, ObjectType,
)
from agts.contracts.objects import (
    CurriculumIdentity, LearningObject, Region, SearchRepresentation, SourceBlock, SourceRecord,
)
from agts.evaluation.corpus import Corpus
from agts.evaluation.planning import plan_for_case
from agts.evaluation.cases import EvalCase

DATABASE_URL = os.environ.get("AGTS_DATABASE_URL")

#: voyage-3 width. 002_pgvector pins the column to vector(1024), so a fixture
#: with a convenient three-element vector passes on the core schema and fails
#: the moment the pgvector migration is applied -- which is how this constant
#: came to exist.
VECTOR = [round(0.001 * i, 4) for i in range(1024)]

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="set AGTS_DATABASE_URL to run persistence tests"
)


@pytest.fixture()
def connection():
    """A transaction that is always rolled back."""
    import psycopg2

    from agts.platform.repository import migrate

    conn = psycopg2.connect(DATABASE_URL)
    try:
        migrate(conn)
        conn.commit()
        yield conn
        conn.rollback()
    finally:
        conn.rollback()
        conn.close()


def build_corpus(*, approved: bool = False, tenant: str | None = None) -> Corpus:
    curriculum = CurriculumIdentity(
        board=Board.CBSE, curriculum_version="pilot-0", grade="10",
        subject="science", unit_id="u1", concept_ids=["c1"],
    )
    source = SourceRecord(
        source_id="pytest-s1", title="T", publisher="NCERT", board=Board.CBSE,
        edition="2026-27", checksum_sha256="a" * 64,
        authority_tier=AuthorityTier.BOARD_OFFICIAL, language=Language.EN,
        approval_state=ApprovalState.QUARANTINED,
    )
    block = SourceBlock(
        block_id="pytest-b1", source_id="pytest-s1", document_id="doc", order_index=0,
        block_type=BlockType.PARAGRAPH,
        region=Region(page=3, x=0.1, y=0.2, width=0.5, height=0.05),
        text="A paragraph about decomposition.", parse_strategy="docling",
        parser_version="2.122.0",
    )
    obj = LearningObject(
        object_id="pytest-o1", object_type=ObjectType.DEFINITION, source_id="pytest-s1",
        block_ids=["pytest-b1"], curriculum=curriculum, heading_path="1.2.2 Decomposition",
        text="body", language=Language.EN, modality=Modality.TEXT,
        authority_tier=AuthorityTier.BOARD_OFFICIAL, disclosure_class=DisclosureClass.PUBLIC,
        tenant_scope=tenant, composition_version="v1", content_hash="0" * 64,
        approval_state=ApprovalState.QUARANTINED,
    )
    rep = SearchRepresentation(
        representation_id="pytest-r1", object_id="pytest-o1", block_ids=["pytest-b1"],
        search_text="1.2.2 Decomposition\nA paragraph about decomposition.",
        representation_version="block-window-v2", content_hash="0" * 64,
        heading_path="1.2.2 Decomposition", modality=Modality.TEXT,
        embedding_model="voyage-3", embedding_version="voyage-3", vector=VECTOR,
    )
    return Corpus(
        sources={source.source_id: source}, blocks={block.block_id: block},
        objects={obj.object_id: obj}, representations={rep.representation_id: rep},
    )


def test_a_corpus_round_trips_without_loss(connection) -> None:
    from agts.platform.repository import load_corpus, save_corpus

    original = build_corpus()
    save_corpus(connection, original)
    restored = load_corpus(connection)

    assert restored.sources["pytest-s1"] == original.sources["pytest-s1"]
    assert restored.blocks["pytest-b1"] == original.blocks["pytest-b1"]
    assert restored.objects["pytest-o1"].block_ids == ["pytest-b1"]
    rep = restored.representations["pytest-r1"]
    assert rep.search_text == original.representations["pytest-r1"].search_text
    assert rep.vector == pytest.approx(VECTOR)
    assert rep.embedding_model == "voyage-3"


def test_saving_twice_changes_nothing(connection) -> None:
    """The first thing anyone does after a failed import is run it again.

    Counts are scoped to this test's own rows. A configured database is a
    working one -- it holds an imported corpus -- and a test that asserts a
    global row count is asserting that nobody else uses the server.
    """
    from agts.platform.repository import load_corpus, save_corpus

    corpus = build_corpus()
    save_corpus(connection, corpus)
    save_corpus(connection, corpus)

    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM blocks WHERE block_id = 'pytest-b1'")
        assert cursor.fetchone()[0] == 1
        cursor.execute(
            "SELECT count(*) FROM learning_object_blocks WHERE object_id = 'pytest-o1'"
        )
        assert cursor.fetchone()[0] == 1

    restored = load_corpus(connection)
    assert restored.objects["pytest-o1"].block_ids == ["pytest-b1"]


def test_an_approved_source_without_rights_is_refused_by_the_database(connection) -> None:
    """Section 5 in the schema, not only in the contract. The database outlives
    the process that validates."""
    import psycopg2

    with pytest.raises(psycopg2.errors.CheckViolation):
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO sources (source_id, title, publisher, edition,
                       checksum_sha256, authority_tier, language, approval_state)
                   VALUES ('pytest-bad', 'T', 'P', 'E', %s, 'board_official', 'en', 'APPROVED')""",
                ("b" * 64,),
            )
    connection.rollback()


def test_a_public_solution_is_refused_by_the_database(connection) -> None:
    import psycopg2

    with pytest.raises(psycopg2.errors.CheckViolation):
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO sources (source_id, title, publisher, edition,
                       checksum_sha256, authority_tier, language)
                   VALUES ('pytest-s2', 'T', 'P', 'E', %s, 'board_official', 'en')""",
                ("c" * 64,),
            )
            cursor.execute(
                """INSERT INTO learning_objects (object_id, object_type, source_id, board,
                       curriculum_version, grade, subject, unit_id, concept_ids,
                       heading_path, text, language, modality, authority_tier,
                       disclosure_class, composition_version, content_hash)
                   VALUES ('pytest-leak', 'assessment_solution', 'pytest-s2', 'cbse',
                       'pilot-0', '10', 'science', 'u1', ARRAY['c1'], 'h', 't', 'en',
                       'text', 'board_official', 'public', 'v1', %s)""",
                ("0" * 64,),
            )
    connection.rollback()


def test_the_sql_filter_and_the_python_filter_agree(connection) -> None:
    """Two implementations of section 5 that disagree is worse than one, and the
    disagreement would only surface in an audit."""
    from agts.evaluation.corpus import EvaluationLicence
    from agts.platform.repository import authorised_object_ids, load_corpus, save_corpus
    from datetime import date

    save_corpus(connection, build_corpus())
    licence = EvaluationLicence(
        reason="test", granted_by="tests", granted_on=date(2026, 8, 30),
        source_ids=("pytest-s1",),
    )
    corpus = load_corpus(connection, licence=licence)

    case = EvalCase(
        case_id="c1", query="what is decomposition", grade="10", subject="science",
        question_type="definition", teaching_action="explain", concept_ids=["c1"],
        gold_block_ids=["pytest-b1"],
    )
    plan = plan_for_case(case)

    in_python = sorted(o.object_id for o in corpus.authorised(plan))
    in_sql = authorised_object_ids(connection, plan, licensed_sources=("pytest-s1",))
    assert in_python == in_sql == ["pytest-o1"]


def test_an_unlicensed_quarantined_source_is_invisible_to_both(connection) -> None:
    from agts.platform.repository import authorised_object_ids, load_corpus, save_corpus

    save_corpus(connection, build_corpus())
    corpus = load_corpus(connection)  # no licence
    case = EvalCase(
        case_id="c1", query="what is decomposition", grade="10", subject="science",
        question_type="definition", teaching_action="explain", concept_ids=["c1"],
        gold_block_ids=["pytest-b1"],
    )
    plan = plan_for_case(case)

    assert corpus.authorised(plan) == []
    assert authorised_object_ids(connection, plan) == []


def test_the_vector_width_is_pinned_where_pgvector_is_installed(connection) -> None:
    """A different provider with a different width cannot be stored by accident.

    Skipped on the core schema, where embeddings are float8[] and any width is
    accepted -- that difference between the two schemas is the point of the test.
    """
    import psycopg2

    from agts.platform.repository import save_corpus

    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT udt_name FROM information_schema.columns
               WHERE table_name = 'search_representations' AND column_name = 'embedding'"""
        )
        udt = cursor.fetchone()[0]
    if udt != "vector":
        pytest.skip("core schema stores float8[]; width is only pinned by 002_pgvector")

    corpus = build_corpus()
    narrow = corpus.representations["pytest-r1"].model_copy(update={"vector": [0.1, 0.2, 0.3]})
    corpus.representations["pytest-r1"] = narrow

    with pytest.raises(psycopg2.Error):
        save_corpus(connection, corpus)
    connection.rollback()


def test_a_corrected_block_reaches_the_database(connection) -> None:
    """Re-importing after a parse fix must change what the service serves.

    `blocks` was the one table that took `ON CONFLICT DO NOTHING` while sources,
    objects and representations all updated. Every correction to a block --
    decoding a Symbol-font character, attaching a recovered formula -- landed in
    the artefacts and stopped at the database, which went on serving the first
    version ever imported. Nothing failed: the import printed its counts and the
    round-trip check compared retrieval scores, which run off representations
    and cannot see a stale block.

    A learner was reading `2 4 , 2 b b ac a` from a row that had been corrected
    on disk twice.
    """
    from agts.platform.repository import load_corpus, save_corpus

    original = build_corpus()
    save_corpus(connection, original)

    corrected = original.blocks["pytest-b1"].model_copy(
        update={"text": "decoded text", "latex": r"\frac{-b}{2a}"}
    )
    from dataclasses import replace

    save_corpus(connection, replace(original, blocks={"pytest-b1": corrected}))

    restored = load_corpus(connection).blocks["pytest-b1"]
    assert restored.text == "decoded text"
    assert restored.latex == r"\frac{-b}{2a}"
