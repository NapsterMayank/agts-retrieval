# Conflict register

Contradictions between authorities, and how each is currently resolved. Every
row is also a question to the client — see `docs/03-open-questions.md`.

| # | Conflict | Authorities | Current resolution | Status |
|---|---|---|---|---|
| C-1 | Holdout sealed Hour 0-8 (§6.4) vs adjudicated Days 4-7 (§13) | Build guide, internally | Built for (b): the 72h candidate is not gated on the holdout; `score()` will not touch it without an explicit flag | **Open — Q2** |
| C-2 | "No slice below its gate" (§14) vs 300-500 total cases across the §11.2 axes (§6.4) | Build guide, internally | Slices with n < 20 report but do not gate, as a bootstrapping allowance. **Now quantified:** the pairwise matrix produces 166 slices of which 66 gate at n ≥ 20 and 100 report only (R-031), so the allowance is load-bearing rather than theoretical | **Open — Q2** |
| C-3 | Rights already held and not blocking (prior position) vs *"verbal assurance is not a rights record"* (§5) | Build guide vs prior decision | §5 wins — it is authority 2 and the prior position was authority 3. `SourceRecord` will not reach `APPROVED` without a signed record | **Resolved, client informed — Q3** |
| C-4 | Pack recall measured (§11) but not gated (§14) | Build guide, internally | Computed and reported as `recall_at_pack`; not blocking until the client agrees. **Now with evidence:** ranking recall and delivered recall differ by 6 points on the holdout (76.7% against 96.3%), so the pack is what must be gated rather than the ranked list (R-032) | **Open — Q4** |
| C-5 | §9 pedagogy controller and §9.4 learner state included here vs excluded from this module by the prior architecture | Build guide vs prior decision | Build guide wins on authority. Scope confirmation requested before the workstream is staffed | **Open — Q5** |
| C-6 | §1 forbids deriving design from existing systems; the prior spec carries hard-won operational detail | Build guide vs prior spec | Prior spec is a post-design comparator and a source of *test material*, never of design decisions. Its defect history — 25% duplicate corpus, published objects with no vector — is used as gate design, which is evidence rather than architecture | **Resolved** |

| C-7 | §5 forbids retrieval from an unapproved source; the ruler cannot be validated without real content | Build guide, internally | `EvaluationLicence` permits **measuring** named quarantined sources and never serving them; every number produced under one carries the licence (R-011) | **Resolved, and the first real numbers exist because of it** |

## Rule

A conflict is resolved by authority order (`docs/00-authority.md`), and the
resolution is written down here before code depends on it. An undocumented
resolution is indistinguishable from an accident six weeks later.
