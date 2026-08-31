"""The shipped pair, checked against the distribution it was derived from.

R-060 recorded a ceiling clearing the highest unanswerable score by 0.000282,
about three times the vector drift a cache rebuild produces. That is margin,
and not much of it. A rebuild that pushes one unanswerable score past the
ceiling costs a refusal and would otherwise be found by nobody, because the
gate would go on looking exactly as configured.

These do not re-derive the pair -- that is a decision with a ledger entry
(R-048, R-060). They check the pair still describes the corpus it claims to.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from agts.retrieval.sufficiency import (
    SHIPPED_CEILING,
    SHIPPED_FLOOR,
    SHIPPED_UNDER_MODEL,
)

BASELINE = Path(__file__).parents[1] / "artifacts" / "gold" / "real-content-baseline.json"


@pytest.fixture()
def dense_calibration() -> dict:
    if not BASELINE.exists():
        pytest.skip("no baseline run on disk; run scripts/real_content_baseline.py")
    import json

    report = json.loads(BASELINE.read_text(encoding="utf-8"))
    return report["abstention"]["representation-dense"]


def test_the_ceiling_is_above_every_unanswerable_score(dense_calibration) -> None:
    """Equal is not enough: the gate reads equal as high confidence (R-057)."""
    highest = dense_calibration["unanswerable_ceiling"]
    assert SHIPPED_CEILING > highest, (
        f"the shipped ceiling {SHIPPED_CEILING} no longer clears the highest "
        f"unanswerable score {highest}. An unanswerable question now skips "
        "corroboration. Re-derive the pair (R-060)."
    )


def test_the_ceiling_keeps_usable_margin_over_provider_drift(dense_calibration) -> None:
    """Vectors are not bit-reproducible; the pair has to survive a re-embed.

    0.0002 is the observed drift scale, not a tolerance anyone chose. Failing
    here means the next cache rebuild is a coin flip, which is a reason to
    re-derive rather than to widen the constant.
    """
    margin = SHIPPED_CEILING - dense_calibration["unanswerable_ceiling"]
    assert margin >= 0.0002, (
        f"the ceiling clears the highest unanswerable score by only {margin:.6f}, "
        "which is inside the drift a cache rebuild produces."
    )


def test_the_floor_sits_between_the_two_distributions(dense_calibration) -> None:
    assert dense_calibration["answerable_floor"] < SHIPPED_FLOOR
    assert SHIPPED_FLOOR <= dense_calibration["unanswerable_ceiling"]


def test_the_pair_names_the_model_it_was_derived_under() -> None:
    """A floor is a property of one model's score distribution (R-059)."""
    from agts.platform.embedding import DEFAULT_EMBEDDING_MODEL

    assert SHIPPED_UNDER_MODEL == DEFAULT_EMBEDDING_MODEL, (
        f"the shipped pair was derived under {SHIPPED_UNDER_MODEL} but the build "
        f"ships {DEFAULT_EMBEDDING_MODEL}. Re-derive before shipping."
    )


def test_the_gate_band_is_not_empty() -> None:
    assert SHIPPED_CEILING > SHIPPED_FLOOR
    assert math.isfinite(SHIPPED_CEILING)
