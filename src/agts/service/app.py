"""The serving surface (section 8).

One endpoint that matters: given a learner's question and scope, return the
evidence pack a teaching loop is allowed to use, or a refusal that says why.

What this service deliberately does **not** do:

**It does not generate text.** There is no model here. It returns evidence with
citations, and the section 14 rows about what a *sentence* may claim belong to
the teaching loop that writes sentences (Q5). Retrieval without generation is the
honest half to ship first: it can only be wrong in ways a human can check by
opening the cited page.

**It does not let a caller choose its own tenant.** The tenant comes from the
bearer token, server-side. A request that names its own tenant has no tenant
boundary at all, and `Corpus.authorised` would be filtering on a value the caller
supplied.

**It does not calibrate anything at request time.** Thresholds are configuration
(see `config.py`). A gate that re-derives its floor from live traffic loosens
exactly when the corpus gets harder, and the number in a trace stops matching the
number in the ledger.

**It refuses to serve unapproved content.** Every chapter measured so far is
`QUARANTINED` under an evaluation licence, which is legitimate for measuring and
not for serving. The service refuses to boot rather than defaulting to
permissive; with the override set, every response carries
`unapproved_content: true`.

Built on Starlette rather than FastAPI: the FastAPI installed here is
incompatible with the installed Starlette, and pinning a global environment to
suit one service is a worse trade than writing three route functions by hand.
Request bodies are still validated by pydantic contracts, which is the part that
was ever worth having.
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from agts.contracts.common import (
    ApprovalState,
    AssessmentState,
    Board,
    EvidenceRole,
    Language,
    LearnerStateClass,
    Modality,
    Role,
    TeachingAction,
)
from agts.contracts.runtime import (
    CEILING_BY_ASSESSMENT_STATE,
    CurriculumScope,
    DisclosurePolicy,
    EvidenceSlot,
    FallbackPolicy,
    LearnerScope,
    QueryPlan,
)
from agts.evaluation.corpus import Corpus
from agts.platform.embedding import CachedEmbedding
from agts.retrieval import BM25Representations, DenseRetriever
from agts.retrieval.chunking import REPRESENTATION_VERSION
from agts.retrieval.packing import build_pack
from agts.retrieval.provenance import build_manifest, build_trace, lineage_failures
from agts.retrieval.sufficiency import SufficiencyGate
from agts.service.config import ConfigurationError, ServiceConfig


@dataclass
class ServiceState:
    config: ServiceConfig
    corpus: Corpus
    gate: SufficiencyGate
    manifest: Any
    serves_unapproved: bool


class EvidenceRequest(BaseModel):
    """What a teaching loop asks for.

    There is no tenant field, on purpose: it comes from the token.
    """

    model_config = {"extra": "forbid"}

    query: str = Field(min_length=1, max_length=2000)
    grade: str
    subject: str
    curriculum_version: str
    board: Board = Board.CBSE
    concept_ids: list[str] = Field(default_factory=list)
    teaching_action: TeachingAction = TeachingAction.EXPLAIN
    assessment_state: AssessmentState = AssessmentState.LEARN
    #: The caller's, not ours. This service holds no learner state and computes
    #: no mastery -- section 9.4 puts that boundary elsewhere on purpose.
    learner_state: LearnerStateClass = LearnerStateClass.COLD_START
    language: Language = Language.EN
    modality: Modality = Modality.TEXT
    learner_id: str = Field(default="anonymous", max_length=128)


def authorise_for_serving(corpus: Corpus, config: ServiceConfig) -> Corpus:
    """Refuse a corpus that is not fit to serve, or permit it loudly.

    Separate from loading because *reading* quarantined content is normal — the
    evaluation harness does it constantly — and serving it is not. Pure, so the
    rule can be tested without a database.
    """
    unapproved = sorted(
        source_id
        for source_id, source in corpus.sources.items()
        if source.approval_state is not ApprovalState.APPROVED
    )
    if not unapproved:
        return corpus

    if not config.allow_quarantined:
        raise ConfigurationError(
            f"{len(unapproved)} of {len(corpus.sources)} sources are not APPROVED "
            f"({', '.join(unapproved[:3])}). Section 5 forbids serving them, and an "
            "evaluation licence does not apply outside evaluation. Register rights "
            "records, or set AGTS_ALLOW_QUARANTINED_CONTENT explicitly and accept "
            "that every response is marked as unapproved."
        )

    # Booting is not enough: `Corpus.authorised` admits QUARANTINED content only
    # under a named permission, so without one the service starts and then
    # abstains on every question with "no candidate survived the authorisation
    # filter" -- an override that looks enabled and is not.
    from datetime import date as _date

    from agts.evaluation.corpus import EvaluationLicence

    return Corpus(
        sources=corpus.sources,
        blocks=corpus.blocks,
        objects=corpus.objects,
        representations=corpus.representations,
        evaluation_licence=EvaluationLicence(
            reason="AGTS_ALLOW_QUARANTINED_CONTENT: operator serving unapproved content knowingly",
            granted_by="service operator",
            granted_on=_date.today(),
            source_ids=tuple(unapproved),
        ),
    )


def load_corpus_for_serving(config: ServiceConfig) -> Corpus:
    """Read the persisted corpus, then apply the serving rule."""
    if not config.database_url:
        raise ConfigurationError(
            "AGTS_DATABASE_URL is required. The service serves a persisted corpus "
            "so that what it returns has a release manifest behind it."
        )

    from agts.platform.repository import connect, load_corpus

    with connect(config.database_url) as connection:
        corpus = load_corpus(connection)
    return authorise_for_serving(corpus, config)


def build_state(config: ServiceConfig) -> ServiceState:
    corpus = load_corpus_for_serving(config)

    if not (config.embedding_cache and Path(config.embedding_cache).exists()):
        raise ConfigurationError(
            "AGTS_EMBEDDING_CACHE must point at a populated vector cache. The "
            "sufficiency gate is calibrated against dense scores, and running it "
            "on a lexical retriever applies a threshold to a different scale."
        )
    # With a key, the cache writes through and unseen questions are embedded on
    # demand. Without one the service still runs, and answers only questions
    # whose vectors were cached by an earlier run -- useful for a reproducible
    # demo, useless for a learner, and distinguished in /health rather than
    # discovered at request time.
    inner = None
    if config.embedding_api_key:
        from agts.platform.embedding import VoyageEmbedding

        inner = VoyageEmbedding(config.embedding_api_key)
    embedder = CachedEmbedding(inner, Path(config.embedding_cache), model="voyage-3")

    gate = SufficiencyGate(
        DenseRetriever(embedder),
        BM25Representations(),
        threshold=config.abstain_floor,
        high_confidence=config.high_confidence,
    )
    manifest = build_manifest(
        corpus,
        manifest_id=config.release_manifest_id,
        created_at=datetime.now(UTC),
        commit_sha=config.commit_sha,
        versions={
            "representation": REPRESENTATION_VERSION,
            "embedding": "voyage-3",
            "abstain_floor": f"{config.abstain_floor:.6f}",
            "high_confidence": f"{config.high_confidence:.6f}",
        },
    )
    return ServiceState(
        config=config,
        corpus=corpus,
        gate=gate,
        manifest=manifest,
        serves_unapproved=any(
            source.approval_state is not ApprovalState.APPROVED
            for source in corpus.sources.values()
        ),
    )


def _tenant_for(request: Request, config: ServiceConfig) -> str:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise PermissionError("bearer token required")
    tenant = config.tenant_tokens.get(token)
    if tenant is None:
        # The same message either way: a caller learns whether a token exists
        # only by holding it.
        raise PermissionError("bearer token required")
    return tenant


def create_app(config: ServiceConfig | None = None, state: ServiceState | None = None) -> Starlette:
    settings = config or ServiceConfig.from_env()

    @asynccontextmanager
    async def lifespan(app: Starlette):
        # Built at boot, so a misconfiguration is a failed start rather than a
        # failed request an hour later.
        app.state.service = state or build_state(settings)
        yield

    async def health(request: Request) -> JSONResponse:
        service: ServiceState = request.app.state.service
        return JSONResponse({
            "status": "ok",
            "release_manifest_id": service.manifest.release_manifest_id,
            "corpus_checksum": service.manifest.checksum_sha256,
            "commit_sha": service.manifest.commit_sha,
            "sources": len(service.corpus.sources),
            "objects": len(service.corpus.objects),
            "representations": len(service.corpus.representations),
            "abstain_floor": service.config.abstain_floor,
            "high_confidence": service.config.high_confidence,
            "unapproved_content": service.serves_unapproved,
            "approved_by": service.manifest.approved_by,
            "embedding": "live" if service.config.embedding_api_key else "cache-only",
        })

    async def evidence(request: Request) -> JSONResponse:
        service: ServiceState = request.app.state.service
        started = time.perf_counter()

        try:
            tenant = _tenant_for(request, service.config)
        except PermissionError as error:
            return JSONResponse({"detail": str(error)}, status_code=401)

        try:
            body = EvidenceRequest.model_validate(await request.json())
        except ValidationError as error:
            return JSONResponse({"detail": error.errors(include_url=False)}, status_code=422)
        except Exception:
            return JSONResponse({"detail": "body must be JSON"}, status_code=400)

        interaction_id = str(uuid.uuid4())
        plan = QueryPlan(
            plan_id=f"plan-{interaction_id}",
            interaction_id=interaction_id,
            created_at=datetime.now(UTC),
            learner=LearnerScope(
                tenant_id=tenant,
                pseudonymous_learner_id=body.learner_id,
                role=Role.LEARNER,
                learner_state_class=body.learner_state,
            ),
            curriculum=CurriculumScope(
                board=body.board,
                curriculum_version=body.curriculum_version,
                grade=body.grade,
                subject=body.subject,
                concept_ids=body.concept_ids or ["unspecified"],
            ),
            query_text=body.query,
            query_language=body.language,
            response_language=body.language,
            modalities=[body.modality],
            teaching_action=body.teaching_action,
            disclosure=DisclosurePolicy(
                assessment_state=body.assessment_state,
                max_disclosure=CEILING_BY_ASSESSMENT_STATE[body.assessment_state],
            ),
            evidence_slots=[
                EvidenceSlot(
                    slot_id=f"{interaction_id}-s0",
                    role=EvidenceRole.EXPLANATION,
                    required=True,
                    min_items=1,
                    max_items=service.config.k_pack,
                )
            ],
            fallback=FallbackPolicy(),
            policy_version="serving-0",
        )

        try:
            decision = service.gate.decide(plan, service.corpus, service.config.k_candidates)
        except RuntimeError as error:
            # The read-only vector cache cannot embed an unseen question. That is
            # a deployment state, not a bad request, and it says so rather than
            # returning an empty pack that reads like an abstention.
            return JSONResponse(
                {"detail": "cannot embed this query", "cause": str(error)},
                status_code=503,
            )
        pack = build_pack(
            plan, decision, service.corpus,
            pack_id=f"pack-{interaction_id}",
            trace_id=f"trace-{interaction_id}",
            release_manifest_id=service.manifest.release_manifest_id,
            k_pack=service.config.k_pack,
        )
        build_trace(
            plan, decision, service.corpus,
            trace_id=f"trace-{interaction_id}",
            manifest=service.manifest,
            stage_latency_ms={"retrieve_and_gate": (time.perf_counter() - started) * 1000},
            k_pack=service.config.k_pack,
        )

        # Section 14 is a serving check, not only a reporting one: a pack whose
        # lineage does not resolve is withheld rather than returned with a note.
        failures = lineage_failures(pack, service.manifest, service.corpus)
        if failures:
            return JSONResponse(
                {"detail": "lineage resolution failed, evidence withheld",
                 "failures": failures[:3]},
                status_code=500,
            )

        return JSONResponse({
            "status": pack.status.value,
            "pack_id": pack.pack_id,
            "trace_id": pack.trace_id,
            "release_manifest_id": pack.release_manifest_id,
            "evidence": [
                {
                    "object_id": item.object_id,
                    "heading_path": item.heading_path,
                    "text": item.text,
                    "role": item.role.value,
                    "citation": {
                        "source_id": item.span.source_id,
                        "edition": item.span.edition,
                        "page": item.span.page,
                        "block_ids": item.span.block_ids,
                    },
                    "score": item.rerank_score,
                }
                for item in pack.evidence
            ],
            "reasons": list(pack.sufficiency.gap_reasons),
            "unapproved_content": service.serves_unapproved,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        })

    return Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/v1/evidence", evidence, methods=["POST"]),
        ],
        lifespan=lifespan,
    )
