"""Release manifests and retrieval traces (sections 11 and 14).

Two of section 14's gates are about lineage rather than quality, and neither was
enforced by anything until now:

**Approved-source and lineage resolution, 100%.** Every object a pack cites must
belong to the release that is serving. Without a manifest there is no way to
answer "which corpus produced this answer", and after a re-import there is no way
to answer it retrospectively at all.

**Security, privacy and rollback evidence: complete and reproducible.** A trace
that cannot name the code, the corpus and the thresholds that produced a number
is not evidence. The `RetrievalTrace` contract already demands `versions` and
`filters_applied`; this module is what fills them in truthfully.

The manifest is built by hashing what is actually in the corpus, not by
recording what someone believed was in it. That distinction is the whole value:
a manifest that is written by hand agrees with the corpus exactly until the
first time it does not.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from agts.contracts.common import PackStatus
from agts.contracts.runtime import (
    CandidateTrace,
    EvidencePack,
    QueryPlan,
    ReleaseManifest,
    RetrievalTrace,
)
from agts.evaluation.corpus import Corpus
from agts.retrieval.sufficiency import SufficiencyDecision


def corpus_checksum(corpus: Corpus) -> str:
    """A checksum over the content, not over the file that described it.

    Sorted so it is order-independent, and built from the content hashes the
    objects and representations already carry, so a change to a single block's
    text moves it.
    """
    digest = hashlib.sha256()
    for source_id in sorted(corpus.sources):
        digest.update(source_id.encode("utf-8"))
        digest.update(corpus.sources[source_id].checksum_sha256.encode("utf-8"))
    for object_id in sorted(corpus.objects):
        digest.update(object_id.encode("utf-8"))
        digest.update(corpus.objects[object_id].content_hash.encode("utf-8"))
    for representation_id in sorted(corpus.representations):
        rep = corpus.representations[representation_id]
        digest.update(representation_id.encode("utf-8"))
        digest.update(rep.content_hash.encode("utf-8"))
        digest.update((rep.embedding_model or "unembedded").encode("utf-8"))
    return digest.hexdigest()


def build_manifest(
    corpus: Corpus,
    *,
    manifest_id: str,
    created_at: datetime,
    commit_sha: str,
    versions: dict[str, str],
    approved_by: list[str] | None = None,
    is_serving: bool = False,
) -> ReleaseManifest:
    """Describe exactly what is in this corpus.

    `approved_by` stays empty unless named humans actually approved it. An
    unsigned manifest is still useful — it answers "which corpus" — and calling
    it approved because it exists is how a release gate becomes decorative.
    """
    return ReleaseManifest(
        release_manifest_id=manifest_id,
        created_at=created_at,
        commit_sha=commit_sha,
        object_ids=sorted(corpus.objects),
        source_ids=sorted(corpus.sources),
        versions=versions,
        checksum_sha256=corpus_checksum(corpus),
        approved_by=list(approved_by or []),
        is_serving=is_serving,
    )


def build_trace(
    plan: QueryPlan,
    decision: SufficiencyDecision,
    corpus: Corpus,
    *,
    trace_id: str,
    manifest: ReleaseManifest,
    stage_latency_ms: dict[str, float] | None = None,
    k_pack: int = 5,
) -> RetrievalTrace:
    """Record what was ranked, what was admitted, and why the rest was not.

    Candidates below the pack cut are recorded as `admitted=False` with a
    reason. A trace of only the winners cannot answer the question anyone
    actually asks of it — why was *that* passage not used.
    """
    candidates: list[CandidateTrace] = []
    for rank, item in enumerate(decision.items, start=1):
        admitted = decision.answerable and rank <= k_pack
        reason = None
        if not decision.answerable:
            reason = "pack abstained: " + "; ".join(decision.reasons)
        elif not admitted:
            reason = f"ranked {rank}, below the pack cut of {k_pack}"
        candidates.append(
            CandidateTrace(
                object_id=item.object_id,
                generator=decision.primary_name,
                rank=rank,
                score=item.score,
                admitted=admitted,
                rejection_reason=reason,
            )
        )

    filters = [
        "approval_state",
        "retired_at",
        "tenant_scope",
        "curriculum(grade, subject, board, version)",
        "disclosure_ceiling",
    ]
    if corpus.evaluation_licence is not None:
        filters.append(f"evaluation_licence({corpus.evaluation_licence.reason})")

    return RetrievalTrace(
        trace_id=trace_id,
        plan_id=plan.plan_id,
        interaction_id=plan.interaction_id,
        candidates=candidates,
        filters_applied=filters,
        corrective_retrievals=0,
        stage_latency_ms=stage_latency_ms or {},
        versions={
            **manifest.versions,
            "corpus_checksum": manifest.checksum_sha256,
            "abstain_threshold": f"{decision.threshold:.6f}",
            "high_confidence": f"{decision.high_confidence:.6f}",
            "primary_retriever": decision.primary_name,
        },
        release_manifest_id=manifest.release_manifest_id,
    )


def lineage_failures(
    pack: EvidencePack, manifest: ReleaseManifest, corpus: Corpus
) -> list[str]:
    """Section 14: approved-source and lineage resolution must be 100%.

    Three ways a pack can fail it, all of which produce a plausible-looking
    answer with an unaccountable origin: it cites an object outside the serving
    release, it cites an object whose source is not in the manifest, or it
    claims a manifest that is not the one it was built against.
    """
    failures: list[str] = []
    if pack.status is PackStatus.ABSTAIN:
        return failures

    if pack.release_manifest_id != manifest.release_manifest_id:
        failures.append(
            f"pack claims manifest {pack.release_manifest_id}, "
            f"scored against {manifest.release_manifest_id}"
        )

    released_objects = set(manifest.object_ids)
    released_sources = set(manifest.source_ids)
    for item in pack.evidence:
        if item.object_id not in released_objects:
            failures.append(f"{item.object_id} is not in the release manifest")
            continue
        obj = corpus.objects.get(item.object_id)
        if obj is None:
            failures.append(f"{item.object_id} is not in the corpus")
        elif obj.source_id not in released_sources:
            failures.append(f"{item.object_id} cites unreleased source {obj.source_id}")
    return failures
