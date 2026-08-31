"""The serving surface.

No database and no network: the service is built from an injected state, so
these test the HTTP behaviour and the boundaries rather than the corpus.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from starlette.testclient import TestClient

from agts.contracts.common import (
    ApprovalState, AuthorityTier, BlockType, Board, DisclosureClass, Language,
    Modality, ObjectType,
)
from agts.contracts.objects import (
    CurriculumIdentity, LearningObject, Region, SearchRepresentation, SourceBlock, SourceRecord,
)
from agts.evaluation.corpus import Corpus
from agts.retrieval import BM25Representations
from agts.retrieval.provenance import build_manifest
from agts.retrieval.sufficiency import SufficiencyGate
from agts.service.app import ServiceState, authorise_for_serving, create_app
from agts.service.config import ConfigurationError, ServiceConfig

CURRICULUM = CurriculumIdentity(
    board=Board.CBSE, curriculum_version="2026-27", grade="10",
    subject="science", unit_id="u1", concept_ids=["c1"],
)


def corpus_for(*, approved: bool = True, tenant: str | None = None) -> Corpus:
    state = ApprovalState.APPROVED if approved else ApprovalState.QUARANTINED
    source = SourceRecord(
        source_id="s1", title="Science X", publisher="NCERT", board=Board.CBSE,
        edition="2026-27", checksum_sha256="a" * 64,
        authority_tier=AuthorityTier.BOARD_OFFICIAL, language=Language.EN,
        approval_state=state,
        rights={
            "owner": "NCERT", "legal_basis": "test fixture, not a real licence",
            "permits_storage": True, "permits_transformation": True,
            "permits_display": True, "permits_model_processing": True,
            "approved_by": "tester", "approved_at": datetime(2026, 8, 30, tzinfo=UTC),
            "evidence_uri": "file://test-fixture",
        } if approved else None,
        scanned_clean_at=datetime(2026, 8, 30, tzinfo=UTC) if approved else None,
    )
    blocks = {
        f"b{i}": SourceBlock(
            block_id=f"b{i}", source_id="s1", document_id="doc", order_index=i,
            block_type=BlockType.PARAGRAPH,
            region=Region(page=i + 1, x=0.1, y=0.1, width=0.5, height=0.05),
            text=text, parse_strategy="docling", parser_version="1",
        )
        for i, text in enumerate([
            "A decomposition reaction breaks a single reactant into simpler products.",
            "Photosynthesis stores energy in glucose using chlorophyll and sunlight.",
        ])
    }
    objects = {
        "o1": LearningObject(
            object_id="o1", object_type=ObjectType.DEFINITION, source_id="s1",
            block_ids=["b0"], curriculum=CURRICULUM,
            heading_path="1.2.2 Decomposition Reaction", text=blocks["b0"].text,
            language=Language.EN, modality=Modality.TEXT,
            authority_tier=AuthorityTier.BOARD_OFFICIAL,
            disclosure_class=DisclosureClass.PUBLIC, tenant_scope=tenant,
            composition_version="v1", content_hash="0" * 64, approval_state=state,
        ),
        "o2": LearningObject(
            object_id="o2", object_type=ObjectType.ASSESSMENT_SOLUTION, source_id="s1",
            block_ids=["b1"], curriculum=CURRICULUM,
            heading_path="Answers", text=blocks["b1"].text,
            language=Language.EN, modality=Modality.TEXT,
            authority_tier=AuthorityTier.BOARD_OFFICIAL,
            disclosure_class=DisclosureClass.SOLUTION,
            composition_version="v1", content_hash="1" * 64, approval_state=state,
        ),
    }
    representations = {
        f"{object_id}:v:1": SearchRepresentation(
            representation_id=f"{object_id}:v:1", object_id=object_id,
            block_ids=obj.block_ids, search_text=f"{obj.heading_path}\n{obj.text}",
            representation_version="v", content_hash="0" * 64,
            heading_path=obj.heading_path, modality=Modality.TEXT,
        )
        for object_id, obj in objects.items()
    }
    return Corpus(sources={"s1": source}, blocks=blocks, objects=objects,
                  representations=representations)


def config_for(**overrides) -> ServiceConfig:
    base = dict(
        database_url="postgresql://unused", abstain_floor=0.01, high_confidence=0.02,
        release_manifest_id="rm-test", commit_sha="testsha",
        tenant_tokens={"token-a": "tenant-1", "token-b": "tenant-2"},
        embedding_cache=None,
    )
    return ServiceConfig(**{**base, **overrides})


def client_for(corpus: Corpus | None = None, config: ServiceConfig | None = None) -> TestClient:
    corpus = corpus if corpus is not None else corpus_for()
    config = config or config_for()
    # BM25 on both sides: the point of these tests is the HTTP boundary, and a
    # lexical gate needs no vectors and no network.
    gate = SufficiencyGate(
        BM25Representations(), BM25Representations(),
        threshold=config.abstain_floor, high_confidence=config.high_confidence,
    )
    state = ServiceState(
        config=config, corpus=corpus, gate=gate,
        manifest=build_manifest(
            corpus, manifest_id=config.release_manifest_id,
            created_at=datetime(2026, 8, 30, tzinfo=UTC), commit_sha=config.commit_sha,
            versions={"representation": "v", "embedding": "none"},
        ),
        serves_unapproved=any(
            s.approval_state is not ApprovalState.APPROVED for s in corpus.sources.values()
        ),
    )
    return TestClient(create_app(config, state=state))


AUTH = {"Authorization": "Bearer token-a"}
ASK = {"grade": "10", "subject": "science", "curriculum_version": "2026-27"}


# --------------------------------------------------------------------------
# The serving rule
# --------------------------------------------------------------------------


def test_unapproved_content_refuses_to_serve() -> None:
    """Every chapter measured so far is QUARANTINED. Serving it is a different
    act from measuring it, and the difference is not a default."""
    with pytest.raises(ConfigurationError) as error:
        authorise_for_serving(corpus_for(approved=False), config_for())
    assert "not APPROVED" in str(error.value)


def test_the_override_also_authorises_rather_than_only_booting() -> None:
    """An override that lets the service start and then abstains on every
    question looks enabled and is not."""
    permitted = authorise_for_serving(
        corpus_for(approved=False), config_for(allow_quarantined=True)
    )
    assert permitted.evaluation_licence is not None
    assert "AGTS_ALLOW_QUARANTINED_CONTENT" in permitted.evaluation_licence.reason


def test_approved_content_needs_no_licence() -> None:
    assert authorise_for_serving(corpus_for(), config_for()).evaluation_licence is None


def test_every_response_says_when_the_content_is_unapproved() -> None:
    corpus = authorise_for_serving(corpus_for(approved=False), config_for(allow_quarantined=True))
    with client_for(corpus, config_for(allow_quarantined=True)) as client:
        body = client.post("/v1/evidence",
                           json={"query": "decomposition reaction", **ASK},
                           headers=AUTH).json()
        assert body["unapproved_content"] is True
        assert client.get("/health").json()["unapproved_content"] is True


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------


def test_the_service_will_not_start_without_calibrated_thresholds() -> None:
    with pytest.raises(ConfigurationError) as error:
        ServiceConfig.from_env({"AGTS_API_TOKENS": "t:tenant"})
    assert "EVALUATION_LEDGER" in str(error.value)


def test_the_service_will_not_start_without_tokens() -> None:
    """An open endpoint over curriculum content has no tenant boundary."""
    with pytest.raises(ConfigurationError) as error:
        ServiceConfig.from_env({
            "AGTS_ABSTAIN_FLOOR": "0.7", "AGTS_HIGH_CONFIDENCE": "0.8",
            "AGTS_RELEASE_MANIFEST_ID": "rm-1",
        })
    assert "AGTS_API_TOKENS" in str(error.value)


def test_the_quarantine_override_needs_the_whole_phrase() -> None:
    env = {
        "AGTS_ABSTAIN_FLOOR": "0.7", "AGTS_HIGH_CONFIDENCE": "0.8",
        "AGTS_RELEASE_MANIFEST_ID": "rm-1", "AGTS_API_TOKENS": "t:tenant",
    }
    assert ServiceConfig.from_env({**env, "AGTS_ALLOW_QUARANTINED_CONTENT": "true"}).allow_quarantined is False
    assert ServiceConfig.from_env({**env, "AGTS_ALLOW_QUARANTINED_CONTENT": "1"}).allow_quarantined is False
    assert ServiceConfig.from_env({
        **env, "AGTS_ALLOW_QUARANTINED_CONTENT": "yes-i-accept-unapproved-content"
    }).allow_quarantined is True


# --------------------------------------------------------------------------
# The boundary
# --------------------------------------------------------------------------


def test_a_request_without_a_token_is_refused() -> None:
    with client_for() as client:
        assert client.post("/v1/evidence", json={"query": "x", **ASK}).status_code == 401


def test_an_unknown_token_is_refused_indistinguishably() -> None:
    """A caller learns whether a token exists only by holding it."""
    with client_for() as client:
        unknown = client.post("/v1/evidence", json={"query": "x", **ASK},
                              headers={"Authorization": "Bearer nope"})
        missing = client.post("/v1/evidence", json={"query": "x", **ASK})
        assert unknown.status_code == missing.status_code == 401
        assert unknown.json() == missing.json()


def test_a_request_cannot_name_its_own_tenant() -> None:
    """A caller that chooses its tenant has no tenant boundary at all."""
    with client_for() as client:
        response = client.post(
            "/v1/evidence",
            json={"query": "decomposition", "tenant_id": "tenant-2", **ASK},
            headers=AUTH,
        )
        assert response.status_code == 422


def test_another_tenants_content_is_not_returned() -> None:
    with client_for(corpus_for(tenant="tenant-2")) as client:
        body = client.post("/v1/evidence",
                           json={"query": "decomposition reaction", **ASK},
                           headers=AUTH).json()
        assert body["status"] == "ABSTAIN"
        assert body["evidence"] == []


def test_a_graded_turn_never_receives_the_solution_object() -> None:
    with client_for() as client:
        body = client.post(
            "/v1/evidence",
            json={"query": "photosynthesis chlorophyll glucose sunlight",
                  "assessment_state": "graded", **ASK},
            headers=AUTH,
        ).json()
        assert all(item["object_id"] != "o2" for item in body["evidence"])


# --------------------------------------------------------------------------
# Answers and refusals
# --------------------------------------------------------------------------


def test_an_answerable_question_returns_cited_evidence() -> None:
    with client_for() as client:
        response = client.post("/v1/evidence",
                               json={"query": "what is a decomposition reaction", **ASK},
                               headers=AUTH)
        body = response.json()
        assert response.status_code == 200
        assert body["status"] == "SUFFICIENT"
        item = body["evidence"][0]
        assert item["citation"]["source_id"] == "s1"
        assert item["citation"]["page"] >= 1
        assert item["citation"]["block_ids"]
        assert body["release_manifest_id"] == "rm-test"


def test_a_refusal_is_a_successful_response_carrying_its_reason() -> None:
    """An abstention is an outcome, not an error. A 500 would tell a caller to
    retry something that will refuse again for a good reason."""
    with client_for(config=config_for(abstain_floor=0.99, high_confidence=0.999)) as client:
        response = client.post("/v1/evidence",
                               json={"query": "what is a decomposition reaction", **ASK},
                               headers=AUTH)
        body = response.json()
        assert response.status_code == 200
        assert body["status"] == "ABSTAIN"
        assert body["evidence"] == []
        assert body["reasons"] and "floor" in body["reasons"][0]


def test_content_outside_the_requested_curriculum_is_never_returned() -> None:
    with client_for() as client:
        body = client.post("/v1/evidence",
                           json={"query": "decomposition", **{**ASK, "grade": "11"}},
                           headers=AUTH).json()
        assert body["status"] == "ABSTAIN"
        assert body["evidence"] == []


def test_health_reports_what_is_being_served() -> None:
    with client_for() as client:
        body = client.get("/health").json()
        assert body["release_manifest_id"] == "rm-test"
        assert body["corpus_checksum"]
        assert body["objects"] == 2
        assert body["abstain_floor"] == 0.01
        assert body["approved_by"] == []


def test_a_malformed_body_is_a_client_error() -> None:
    with client_for() as client:
        assert client.post("/v1/evidence", json={"query": ""}, headers=AUTH).status_code == 422
        assert client.post("/v1/evidence", content=b"not json", headers=AUTH).status_code == 400
