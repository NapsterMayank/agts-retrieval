# Blocking release gates

Transcribed from client build guide §14. Automated model judges may assist
evaluation but are never the sole release authority.

Last measured 30 August 2026 over two quarantined chapters, 98 gold cases.
"Measured" below means a number exists in `EVALUATION_LEDGER.md`; it does not
mean the gate is satisfied for release, which additionally needs a real gold set,
a sealed holdout and human sign-off.

| Gate | Minimum bar | Enforced by | Last measured |
|---|---:|---|---|
| Approved-source and lineage resolution | 100% | `provenance.lineage_failures`, `ReleaseManifest`, `unapproved_source` counter — **also enforced at serve time**, where a pack that fails is withheld rather than annotated (R-034) | **0 failures / 98 packs** |
| Retrieval from unapproved, retired, deleted or unauthorized source | 0 | `Corpus.authorised` + the same filter in SQL, `unapproved_source` + `retired_content` counters | **0** |
| Cross-tenant retrieval or state access | 0 | `Corpus.authorised`, `cross_tenant` counter | **0** |
| Recall@20 — single-hop | ≥95% | `ScoreReport.recall_at_candidates` | 94.0% visible — **below bar** |
| Recall@20 — multi-hop, visual, multilingual | ≥90% each | `ScoreReport.failing_slices`, now pairwise (R-031) | reported per slice; several below bar |
| Citation ID resolution | 100% | `EvidencePack` validator + `citations.score_citations` | **100%** |
| Citation precision | ≥98% | **not measurable until generation exists** — the proxy is named `evidence_precision` and is not this row (R-026) | not claimed |
| Citation completeness | ≥95% | `citations.score_citations` | **97.2% visible, 96.3% holdout** |
| Supported consequential claims | ≥95%, no unsupported safety- or assessment-critical claim | `VerificationResult` | not built (Phase 3) |
| Graded-solution leakage | 0 | `DisclosurePolicy`, `LearningObject` validator and a CHECK constraint, `disclosure_violations` counter | **0** |
| Mathematical tool-proof failure on tool-required cases | 0 accepted outputs | not yet built (Phase 3) | — |
| Hidden-holdout regression | No slice below its gate | `score(..., include_holdout=True)`, 38 unseen cases | measured, **seal not real** — see Q2 |
| Human academic review | Passed by named reviewers | `EvalCase.adjudicators` | **0 of 48 release-critical cases adjudicated** |
| Security/privacy/rollback evidence | Complete and reproducible | `provenance.build_trace` covers reproducibility; rollback and privacy are not built | partial |
| Latency and cost | Within founder-approved pilot budgets | not yet built | — |

## One gate this repository added to itself

**Delivered recall**, reported beside `recall_at_pack`. Ranking recall measures
what the retriever ordered; delivered recall measures what the pack carried, and
on the holdout they differ by six points (76.7% against 96.3%). A gate on the
first is a gate on something no learner experiences (R-032).

## Per-slice rule

Rule 9: every slice gets its own score and a blended average may not hide a
failing one. A slice with **n < 20** is reported but does not gate — see
`GATING_MIN_N`. That is a bootstrapping allowance while the gold set is being
built, not a standing exemption, and it is open question **Q2**.

## One gate we are asking the client to add

**Post-rerank pack recall, ≥90%.**

§11 lists "final evidence survival by slice" under required measurements. §14
does not gate it. The failure it catches is specific and common: a reranker holds
twenty correct candidates and still orders the gold span into position nine of a
five-slot pack. Recall@20 passes at 95%, the teaching loop receives nothing
usable, and the failure surfaces two phases later as a faithfulness regression
whose real cause is the reranker.

Measuring it without gating it means the number exists and nothing happens when
it drops. `ScoreReport.recall_at_pack` already computes it.

Tracked as **Q4** in `docs/03-open-questions.md`.
