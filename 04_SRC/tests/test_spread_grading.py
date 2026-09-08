"""Phase 5 — spread grading tests (score-tier grade + effective max spread)."""

import pytest

from smc.config.locked_constants import (
    SPREAD_GRADE_MULTIPLIERS,
    SPREAD_GRADE_SCORE_THRESHOLDS,
    SPREAD_MAX_ATR,
)
from smc.risk.spread_grading import (
    SpreadGrade,
    effective_max_spread,
    grade_for_score,
)

ATR = 10.0
BASE = SPREAD_MAX_ATR * ATR  # 1.5 at ATR=10


def test_grade_boundaries():
    assert grade_for_score(8) is SpreadGrade.A_PLUS
    assert grade_for_score(5) is SpreadGrade.A
    assert grade_for_score(3) is SpreadGrade.B
    assert grade_for_score(2) is SpreadGrade.C
    assert grade_for_score(0) is SpreadGrade.C


def test_grade_above_a_plus_stays_a_plus():
    assert grade_for_score(20) is SpreadGrade.A_PLUS


def test_grade_negative_scores_are_c():
    assert grade_for_score(-1) is SpreadGrade.C


def test_effective_max_spread_matches_multiplier_table():
    expected = {
        SpreadGrade.A_PLUS: SPREAD_GRADE_MULTIPLIERS["A+"] * BASE,
        SpreadGrade.A: SPREAD_GRADE_MULTIPLIERS["A"] * BASE,
        SpreadGrade.B: SPREAD_GRADE_MULTIPLIERS["B"] * BASE,
        SpreadGrade.C: SPREAD_GRADE_MULTIPLIERS["C"] * BASE,
    }
    for grade, limit in expected.items():
        score = SPREAD_GRADE_SCORE_THRESHOLDS[grade.value]
        assert effective_max_spread(score, ATR) == pytest.approx(limit)


def test_effective_max_spread_is_atr_scaled():
    low = effective_max_spread(8, atr=10.0)
    high = effective_max_spread(8, atr=20.0)
    assert high == pytest.approx(2 * low)


def test_effective_max_spread_grade_ordering():
    # Higher grade → larger (or equal) tolerance.
    assert effective_max_spread(8, ATR) >= effective_max_spread(5, ATR)
    assert effective_max_spread(5, ATR) >= effective_max_spread(3, ATR)
    assert effective_max_spread(3, ATR) >= effective_max_spread(2, ATR)


def test_effective_max_spread_invalid_atr_raises():
    with pytest.raises(ValueError):
        effective_max_spread(8, 0.0)
    with pytest.raises(ValueError):
        effective_max_spread(8, -1.0)