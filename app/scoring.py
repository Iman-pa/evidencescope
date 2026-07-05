"""MCDA weighted-sum scoring for EvidenceScope.

pyDecision's built-in ranking methods (saw_method, smart_method, waspas_method) all
normalize scores *relative to the set of alternatives* — i.e. they are designed for
ranking drug A vs. B vs. C against each other. With a single alternative the
normalization is degenerate (division by zero or all-ones), so those methods cannot be
used here without producing meaningless results.

We implement the SMART-style linear weighted sum directly using numpy (a pyDecision
dependency). The formula is:

    weighted_score = Σ  wᵢ * (scoreᵢ − SCORE_MIN) / (SCORE_MAX − SCORE_MIN)

This maps 1-9 criterion scores to [0, 1] on a linear scale, then combines them with
normalised weights. The result is a number in [0, 1]; multiply by SCORE_MAX to get a
human-readable 1–9-equivalent total if desired.

If we later need to *rank multiple drugs against each other*, pyDecision's saw_method
or topsis_method become appropriate and will be introduced at that point.
"""

import numpy as np

from app.models import CRITERIA

SCORE_MIN: float = 1.0
SCORE_MAX: float = 9.0
_SCALE: float = SCORE_MAX - SCORE_MIN  # 8.0


def compute_weighted_score(
    scores: dict[str, float],
    weights: dict[str, float],
) -> float:
    """Compute a SMART-style linear weighted sum for a single drug.

    Args:
        scores:  Mapping of criterion key → raw score (expected range 1–9).
        weights: Mapping of criterion key → relative weight (any positive values;
                 will be normalised to sum to 1 internally).

    Returns:
        Weighted score in [0.0, 1.0].
        Multiply by 9 for a 1–9-equivalent presentation value.

    Raises:
        ValueError: if any criterion key in scores or weights is not in CRITERIA,
                    if weights sum to zero, or if any score is outside [1, 9].
    """
    # Validate keys
    unknown_scores = set(scores) - set(CRITERIA)
    unknown_weights = set(weights) - set(CRITERIA)
    if unknown_scores:
        raise ValueError(f"Unknown criterion keys in scores: {unknown_scores}")
    if unknown_weights:
        raise ValueError(f"Unknown criterion keys in weights: {unknown_weights}")

    # Use only criteria present in both dicts; order deterministically
    keys = [k for k in CRITERIA if k in scores and k in weights]
    if not keys:
        raise ValueError("No overlapping criteria found between scores and weights.")

    raw_scores = np.array([scores[k] for k in keys], dtype=float)
    raw_weights = np.array([weights[k] for k in keys], dtype=float)

    if np.any(raw_scores < SCORE_MIN) or np.any(raw_scores > SCORE_MAX):
        bad = {k: scores[k] for k in keys if not (SCORE_MIN <= scores[k] <= SCORE_MAX)}
        raise ValueError(f"Scores out of [{SCORE_MIN}, {SCORE_MAX}] range: {bad}")

    weight_sum = raw_weights.sum()
    if weight_sum == 0:
        raise ValueError("Weights must not all be zero.")

    normalised_weights = raw_weights / weight_sum
    normalised_scores = (raw_scores - SCORE_MIN) / _SCALE  # maps [1,9] → [0,1]

    return float(np.dot(normalised_weights, normalised_scores))
