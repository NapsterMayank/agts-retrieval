# Open questions for the client

Four items. Two are contradictions inside the build guide, two are decisions only
the client can make. **Q1 and Q3 block work that is otherwise ready to start.**

Raised 24 August 2026. Nothing here is a disagreement with the approach.

---

## Q1 — Name the pilot curriculum · BLOCKING

**Needed:** one grade, one Mathematics unit, one Science unit, the board and the
edition. Plus the 50-100 representative concepts §6.1 asks for.

**Blocks:** §6.1 curriculum spine, §6.4 gold set, §7.1 source registration —
which is most of Phase 1.

**Cost of waiting:** contracts and the scorer run on synthetic fixtures, so the
first few hours are productive without it. Everything touching real content stops
at roughly Hour 3.

---

## Q2 — When is the hidden holdout sealed, and by whom? · CONTRADICTION

§6.4 seals the holdout **before tuning begins**, inside Hour 0-8.
§13 schedules two-reviewer adjudication for **Days 4-7**.

A holdout cannot be both sealed at Hour 8 and adjudicated on Day 5. Either:

- **(a)** the Hour-8 seal is an unadjudicated draft, in which case §14's
  hidden-holdout gate is weaker than it reads until Day 7; or
- **(b)** the 72-hour release candidate is not gated on the holdout at all, and
  the gate belongs to the pilot-ready decision.

We have built for **(b)** — `score()` refuses to touch the holdout unless asked
explicitly. Confirm or correct.

**Related:** §14 requires no slice below its gate, and §11.2 crosses grade ×
subject × concept state × language × modality × teaching action × accessibility ×
provider × failure condition. §8.1 alone names twelve teaching actions. At n ≥ 20
per gating slice that is 240 cases for the action axis before any crossing, and
the guide budgets 300-500 in total. Our reading: **slices below n = 20 report but
do not gate** while the set is bootstrapped. Confirm.

---

## Q3 — Signed rights records per source · BLOCKING

§5 is explicit: every source starts `QUARANTINED`, only a named human reviewer
moves a **specific checksum and version** to `APPROVED`, and *"verbal assurance is
not a rights record."*

This supersedes the earlier position that rights were already held and no longer
gated the build. We have implemented §5 as written — `SourceRecord` will not
construct in an `APPROVED` state without a `RightsRecord` carrying an approver, a
date and an evidence link.

**Needed per source:** owner or licensor, legal or licence basis, permitted
storage / transformation / display / model processing, attribution, term,
approver, evidence link.

**Blocks:** §7.1 registration and everything downstream of it.

---

## Q4 — Add post-rerank pack recall to §14 · RECOMMENDED, NOT BLOCKING

§11 measures "final evidence survival by slice". §14 does not gate it.

A reranker can hold twenty correct candidates and still order the gold span into
position nine of a five-slot pack. Recall@20 passes at 95%, the teaching loop
receives nothing usable, and it surfaces two phases later as a faithfulness
problem whose cause is three stages upstream.

**Ask:** add *"final evidence survival (pack recall), ≥90% per slice"* to §14.
Already computed as `ScoreReport.recall_at_pack`; this is a one-line change to
the gate table, not new work.

**Update, 30 August — the ask is now sharper.** Building the evidence pack showed
that *two* pack numbers exist and they disagree:

| | visible | holdout |
|---|---:|---:|
| `recall_at_pack` — what the retriever ranked | 94.0% | 76.7% |
| `delivered_recall` — what the pack carried | 100.0% | 96.3% |

The gap is sibling expansion, which adds windows after ranking (R-025). Gating
the first would gate something no learner experiences. **The ask is therefore for
delivered recall**, and the same run also produced citation completeness at 97.2%
/ 96.3% against §14's existing ≥95% bar, so the two rows can be read together.

---

## Also worth confirming — scope

§9 specifies a deterministic pedagogy controller and §9.4 a learner-state
boundary. The prior architecture assigned both to AGTS and excluded them from
this module by name.

**Ask:** does this repository build §9, or consume it? The answer changes the
workstream split in `docs/02-workstreams.md`, not the Phase 0 work already done.
