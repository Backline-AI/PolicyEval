"""Compliance metric: weighted harmonic mean of adherence and coverage scores.

The harmonic mean is used because it penalises imbalance: a strong adherence
score cannot compensate for weak coverage, and vice versa.

When either score is exactly 0 the harmonic mean would unconditionally return 0,
which conflates two distinct situations:
- A *genuine* zero (e.g. every rule failed) — should be penalised.
- An *uninformative* zero (e.g. coverage=0.0 because the LLM found no uncovered
  actions in an empty diff) — should not wipe out an otherwise meaningful
  adherence signal.

The arithmetic mean fallback preserves partial information in the second case.
If a hard zero for both situations is desired, callers can clamp the result
themselves or tune adherence/coverage weights.
"""

from __future__ import annotations

from typing import Optional


def compute_compliance_score(
    adherence_score: float,
    coverage_score: float,
    adherence_weight: float = 1.0,
    coverage_weight: float = 1.0,
) -> float:
    """Compute the compliance score as a weighted harmonic mean.

    When both scores are positive, the weighted harmonic mean is used.
    This penalises imbalance — a score of 0.9/0.1 yields ~0.18, not 0.50.

    When either score is 0, falls back to the weighted arithmetic mean to
    preserve partial information (e.g. adherence=0.9 / coverage=0.0 yields
    0.45 rather than 0.0). See the module docstring for the design rationale.

    Args:
        adherence_score: Adherence sub-report score (0–1).
        coverage_score: Coverage sub-report score (0–1).
        adherence_weight: Weight applied to adherence (default 1.0).
        coverage_weight: Weight applied to coverage (default 1.0).

    Returns:
        Compliance score in ``[0, 1]``.
    """
    w_a = adherence_weight
    w_c = coverage_weight
    total_weight = w_a + w_c

    if adherence_score > 0 and coverage_score > 0:
        return total_weight / (w_a / adherence_score + w_c / coverage_score)
    else:
        return (w_a * adherence_score + w_c * coverage_score) / total_weight


def maybe_compute_compliance(
    adherence_score: Optional[float],
    coverage_score: Optional[float],
    adherence_weight: float = 1.0,
    coverage_weight: float = 1.0,
) -> Optional[float]:
    """Compute compliance only when both scores are available.

    Returns ``None`` if either score is ``None`` (i.e. single-metric mode).
    """
    if adherence_score is None or coverage_score is None:
        return None
    return compute_compliance_score(
        adherence_score,
        coverage_score,
        adherence_weight,
        coverage_weight,
    )
