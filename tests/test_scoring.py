"""Tests for app/scoring.py — compute_weighted_score().

The function returns a value in [0, 1] where:
    0.0 = all scores are 1  (worst possible)
    1.0 = all scores are 9  (best possible)
    0.5 = all scores are 5  (midpoint)

Normalisation formula per criterion: (score - 1) / 8
Weighted sum:                         Σ wᵢ * normalised_scoreᵢ
"""

import pytest
from app.scoring import compute_weighted_score
from app.models import CRITERIA

EQUAL_WEIGHTS = {k: 1.0 for k in CRITERIA}


# ---------------------------------------------------------------------------
# Case 1: Equal weights, uniform scores
# ---------------------------------------------------------------------------

def test_equal_weights_all_fives():
    """Equal weights + all scores = 5  →  (5-1)/8 = 0.5 for every criterion.

    Expected: 0.5 exactly.
    """
    scores = {k: 5.0 for k in CRITERIA}
    result = compute_weighted_score(scores, EQUAL_WEIGHTS)
    assert abs(result - 0.5) < 1e-9


def test_equal_weights_all_nines():
    """Equal weights + all scores = 9  →  (9-1)/8 = 1.0 for every criterion.

    Expected: 1.0 exactly.
    """
    scores = {k: 9.0 for k in CRITERIA}
    result = compute_weighted_score(scores, EQUAL_WEIGHTS)
    assert abs(result - 1.0) < 1e-9


def test_equal_weights_all_ones():
    """Equal weights + all scores = 1  →  (1-1)/8 = 0.0 for every criterion.

    Expected: 0.0 exactly.
    """
    scores = {k: 1.0 for k in CRITERIA}
    result = compute_weighted_score(scores, EQUAL_WEIGHTS)
    assert abs(result - 0.0) < 1e-9


def test_equal_weights_mixed_known_average():
    """Equal weights, mixed scores.

    Scores: clinical_benefit=7, safety=3, cost_effectiveness=9,
            budget_impact=1, equity_access=5, feasibility=6
    Normalised: 6/8=0.75, 2/8=0.25, 8/8=1.0, 0/8=0.0, 4/8=0.5, 5/8=0.625
    Average: (0.75+0.25+1.0+0.0+0.5+0.625) / 6 = 3.125 / 6 = 0.520833...
    """
    scores = {
        "clinical_benefit":   7.0,
        "safety":             3.0,
        "cost_effectiveness": 9.0,
        "budget_impact":      1.0,
        "equity_access":      5.0,
        "feasibility":        6.0,
    }
    expected = (0.75 + 0.25 + 1.0 + 0.0 + 0.5 + 0.625) / 6  # = 0.52083...
    result = compute_weighted_score(scores, EQUAL_WEIGHTS)
    assert abs(result - expected) < 1e-9


# ---------------------------------------------------------------------------
# Case 2: Single criterion weighted at 100%, rest at 0%
# ---------------------------------------------------------------------------

def test_single_criterion_dominates():
    """weight[cost_effectiveness] = 1.0, all others = 0.

    cost_effectiveness score = 3  →  normalised = (3-1)/8 = 0.25
    Expected: 0.25 exactly, regardless of other scores.
    """
    scores = {
        "clinical_benefit":   9.0,  # would be 1.0 — irrelevant
        "safety":             9.0,
        "cost_effectiveness": 3.0,  # only one that matters
        "budget_impact":      9.0,
        "equity_access":      9.0,
        "feasibility":        9.0,
    }
    weights = {k: 0.0 for k in CRITERIA}
    weights["cost_effectiveness"] = 1.0

    result = compute_weighted_score(scores, weights)
    assert abs(result - 0.25) < 1e-9


def test_single_criterion_dominates_max():
    """weight[clinical_benefit] = 100, others = 0. Score = 9 → expected 1.0."""
    scores = {k: 1.0 for k in CRITERIA}  # all others are 1 (worst)
    scores["clinical_benefit"] = 9.0
    weights = {k: 0.0 for k in CRITERIA}
    weights["clinical_benefit"] = 100.0  # should be normalised to 1.0

    result = compute_weighted_score(scores, weights)
    assert abs(result - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Case 3: Realistic mixed weights — hand-calculated expected value
# ---------------------------------------------------------------------------

def test_realistic_mixed_weights():
    """Realistic HTA weighting scenario.

    Weights (raw, pre-normalisation):
        clinical_benefit:   40
        safety:             25
        cost_effectiveness: 20
        budget_impact:      10
        equity_access:       3
        feasibility:         2
    Total = 100  →  normalised weights = raw / 100

    Scores and step-by-step hand calculation:
        clinical_benefit:   score=7  normalised=(7-1)/8=0.7500  contrib=0.40*0.7500=0.30000
        safety:             score=5  normalised=(5-1)/8=0.5000  contrib=0.25*0.5000=0.12500
        cost_effectiveness: score=3  normalised=(3-1)/8=0.2500  contrib=0.20*0.2500=0.05000
        budget_impact:      score=2  normalised=(2-1)/8=0.1250  contrib=0.10*0.1250=0.01250
        equity_access:      score=4  normalised=(4-1)/8=0.3750  contrib=0.03*0.3750=0.01125
        feasibility:        score=8  normalised=(8-1)/8=0.8750  contrib=0.02*0.8750=0.01750

    Sum of contributions = 0.30000+0.12500+0.05000+0.01250+0.01125+0.01750 = 0.51625
    """
    scores = {
        "clinical_benefit":   7.0,
        "safety":             5.0,
        "cost_effectiveness": 3.0,
        "budget_impact":      2.0,
        "equity_access":      4.0,
        "feasibility":        8.0,
    }
    weights = {
        "clinical_benefit":   40.0,
        "safety":             25.0,
        "cost_effectiveness": 20.0,
        "budget_impact":      10.0,
        "equity_access":       3.0,
        "feasibility":         2.0,
    }
    expected = 0.30000 + 0.12500 + 0.05000 + 0.01250 + 0.01125 + 0.01750  # = 0.51625
    result = compute_weighted_score(scores, weights)
    assert abs(result - expected) < 1e-9


# ---------------------------------------------------------------------------
# Edge cases / error handling
# ---------------------------------------------------------------------------

def test_weights_normalised_internally():
    """Weights given as fractions that already sum to 1 and as large integers
    should produce the same result."""
    scores = {k: 6.0 for k in CRITERIA}
    weights_raw = {k: 100.0 for k in CRITERIA}
    weights_unit = {k: 1 / 6 for k in CRITERIA}

    r1 = compute_weighted_score(scores, weights_raw)
    r2 = compute_weighted_score(scores, weights_unit)
    assert abs(r1 - r2) < 1e-9


def test_score_out_of_range_raises():
    scores = {k: 5.0 for k in CRITERIA}
    scores["safety"] = 10.0  # out of [1, 9]
    with pytest.raises(ValueError, match="out of"):
        compute_weighted_score(scores, EQUAL_WEIGHTS)


def test_unknown_criterion_raises():
    scores = {k: 5.0 for k in CRITERIA}
    scores["nonexistent"] = 5.0
    with pytest.raises(ValueError, match="Unknown"):
        compute_weighted_score(scores, EQUAL_WEIGHTS)


def test_all_zero_weights_raises():
    scores = {k: 5.0 for k in CRITERIA}
    weights = {k: 0.0 for k in CRITERIA}
    with pytest.raises(ValueError, match="zero"):
        compute_weighted_score(scores, weights)
