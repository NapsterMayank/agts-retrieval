# AGTS retrieval and evidence fabric

Implementation of the client's **Alfanumrik Grounded Teaching RAG — AI-Native
Build Guide** (revised 22 August 2026).

This repository is Track B. It does not modify, refactor or migrate Foxxy's
`retrieval` module, which stays live and demoed.

## Status — Phase 0 complete on fixtures; first real-content run done (30 August 2026)

Built and passing:

| Build guide | Delivered here |
|---|---|
| §6.2 typed learning objects | `src/agts/contracts/objects.py` |
| §6.3 runtime contracts | `src/agts/contracts/runtime.py` |
| §6.4 evaluation case schema | `src/agts/evaluation/cases.py` |
| §6.5 test the tester | `tests/test_scorer_detects_broken_retrievers.py` |
| §8.1 plan builder (Phase-0 seed) | `src/agts/evaluation/planning.py` |

| §7.1/§7.2 parsing, two strategies | `src/agts/parsing/` |
| §7.4 composition | `src/agts/composition.py` |
| Evaluation licence for quarantined sources | `src/agts/evaluation/corpus.py` (R-011) |

**Two real chapters are parsed and scored** — NCERT Class 10 Science ch1 and
Class 10 Maths ch4 — under `artifacts/*-quarantine/`. They are `QUARANTINED`:
measurable, never publishable, `FORBIDDEN_PENDING_RIGHTS_RECORD` in every
manifest.

Run the real-content baseline:

```
PYTHONPATH=src python scripts/real_content_baseline.py
```

**What it found:** the keyword baseline reaches 96% pack recall, and **abstention
does not separate at all** — margin −0.497, because composition yields 38
section-sized objects for 728 blocks. §7.3 search representations are the next
build step (R-015).

Not started, and blocked — see `docs/03-open-questions.md`:

- the real 300-500 case gold set (60 drafted cases exist; the named pilot
  curriculum and two adjudicators do not)
- source *registration* — parsing runs, approval needs signed rights records
- everything from §8.2 onward

## Run it

```
pip install -e ".[dev]"
python -m pytest -q
python scripts/baseline.py
```

`scripts/baseline.py` prints the current baseline against the four broken
retrievers. That table is the only reason to believe any later number.

## The corpus here is fake

`src/agts/evaluation/fixtures.py` is synthetic, carries no curriculum content and
must never reach a student. Build guide §5 permits scaffolding against disposable
fixtures while decisions are pending; it is deleted the moment an approved pilot
source is registered.

## Layout

```
src/agts/contracts/     frozen schemas - every workstream handoff goes through these
src/agts/evaluation/    the ruler: cases, corpus, retrievers, scorer
tests/                  contract invariants + the §6.5 detection suite
docs/                   authority order, gates, workstreams, open questions
scripts/                runnable reports
```
