"""What a small denominator actually supports (section 11).

`8/8` reads as certainty and is not. With eight observations, the strongest
honest claim at 95% confidence is that the true refusal rate is **at least
68.8%** — a system that wrongly answered three learners in ten would produce
8/8 on this set about one run in twenty.

An outside reviewer asked for exactly this: report a bound and a denominator
rather than a bare fraction. It costs twenty lines and it stops a number
meaning more in a table than it meant in the run that produced it.

Clopper-Pearson, one-sided, exact rather than normal-approximation — at n=8 the
normal approximation is not merely imprecise, it produces intervals extending
past 1.0.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import comb


@dataclass(frozen=True)
class Rate:
    """A count, its denominator, and what the pair supports."""

    successes: int
    trials: int
    lower_bound: float
    confidence: float = 0.95

    @property
    def observed(self) -> float | None:
        return self.successes / self.trials if self.trials else None

    def __str__(self) -> str:
        if not self.trials:
            return "n/a"
        return (
            f"{self.successes}/{self.trials} ({self.observed:.0%}), "
            f"true rate >= {self.lower_bound:.0%} at {self.confidence:.0%}"
        )


def lower_bound(successes: int, trials: int, *, confidence: float = 0.95) -> float:
    """Exact one-sided Clopper-Pearson lower bound on the underlying rate."""
    if trials <= 0:
        return 0.0
    if successes < 0 or successes > trials:
        raise ValueError(f"{successes} successes in {trials} trials is not a rate")
    alpha = 1.0 - confidence
    if successes == 0:
        return 0.0
    if successes == trials:
        # The closed form: the largest p whose chance of producing a clean sweep
        # is still alpha.
        return alpha ** (1.0 / trials)

    low, high = 0.0, 1.0
    for _ in range(200):
        mid = (low + high) / 2.0
        tail = sum(
            comb(trials, i) * mid**i * (1.0 - mid) ** (trials - i)
            for i in range(successes, trials + 1)
        )
        if tail > alpha:
            high = mid
        else:
            low = mid
    return low


def rate(successes: int, trials: int, *, confidence: float = 0.95) -> Rate:
    return Rate(
        successes=successes,
        trials=trials,
        lower_bound=lower_bound(successes, trials, confidence=confidence),
        confidence=confidence,
    )
