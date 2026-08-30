# Blocking release gates

Transcribed from client build guide §14. Automated model judges may assist
evaluation but are never the sole release authority.

| Gate | Minimum bar | Enforced by |
|---|---:|---|
| Approved-source and lineage resolution | 100% | `SourceRecord`, `ReleaseManifest`, `unapproved_source` counter |
| Retrieval from unapproved, retired, deleted or unauthorized source | 0 | `Corpus.authorised`, `unapproved_source` + `retired_content` counters |
| Cross-tenant retrieval or state access | 0 | `Corpus.authorised`, `cross_tenant` counter |
| Recall@20 — single-hop | ≥95% | `ScoreReport.recall_at_candidates` |
| Recall@20 — multi-hop, visual, multilingual | ≥90% each | `ScoreReport.failing_slices` |
| Citation ID resolution | 100% | `EvidencePack` validator |
| Citation precision | ≥98% | not yet built (Phase 3) |
| Citation completeness | ≥95% | not yet built (Phase 3) |
| Supported consequential claims | ≥95%, no unsupported safety- or assessment-critical claim | `VerificationResult` |
| Graded-solution leakage | 0 | `DisclosurePolicy`, `LearningObject` validator, `disclosure_violations` counter |
| Mathematical tool-proof failure on tool-required cases | 0 accepted outputs | not yet built (Phase 3) |
| Hidden-holdout regression | No slice below its gate | `score(..., include_holdout=True)` |
| Human academic review | Passed by named reviewers | `EvalCase.adjudicators` |
| Security/privacy/rollback evidence | Complete and reproducible | not yet built (Phase 4) |
| Latency and cost | Within founder-approved pilot budgets | not yet built |

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
