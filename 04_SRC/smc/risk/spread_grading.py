"""Phase 5 — spread grading (v25_DIAG v19.7 "Setup Grading A+/A/B/C", ported
to Python).

LOCKED_DECISIONS §28.5: tiered spread tolerance by signal-quality score:

    A+ (score >= 8): 1.5 × base   A (score >= 5): 1.0 × base
    B  (score >= 3): 0.7 × base   C (score  < 3): 0.5 × base

where the base max spread is ``SPREAD_MAX_ATR`` (0.15) × ATR (in points).

v25 semantics preserved verbatim: the grade is picked from the frozen
``SPREAD_GRADE_SCORE_THRESHOLDS`` (highest tier whose threshold is met) and
the effective max spread is ``SPREAD_GRADE_MULTIPLIERS[grade] × SPREAD_MAX_ATR
× ATR`` — the ATR-relative, score-tiered scheme (NOT the fixed point-band
scheme once described in DEVELOPMENT_PLAN).

Pure function of (score, atr) — no MT5 dependency, fully unit-testable.
"""

from __future__ import annotations

from enum import Enum

from smc.config.locked_constants import (
    SPREAD_GRADE_MULTIPLIERS,
    SPREAD_GRADE_SCORE_THRESHOLDS,
    SPREAD_MAX_ATR,
)

__all__ = ["SpreadGrade", "grade_for_score", "effective_max_spread"]


class SpreadGrade(Enum):
    """Setup quality grades (LOCKED_DECISIONS §28.5)."""

    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"


def grade_for_score(score: float) -> SpreadGrade:
    """Map a signal-quality score to its frozen grade.

    Thresholds come from ``SPREAD_GRADE_SCORE_THRESHOLDS`` (A+ ≥ 8, A ≥ 5,
    B ≥ 3, C < 3); the highest tier whose threshold is met wins. Scores
    below the B threshold grade as C.
    """
    for grade_name, threshold in (
        ("A+", SPREAD_GRADE_SCORE_THRESHOLDS["A+"]),
        ("A", SPREAD_GRADE_SCORE_THRESHOLDS["A"]),
        ("B", SPREAD_GRADE_SCORE_THRESHOLDS["B"]),
        ("C", SPREAD_GRADE_SCORE_THRESHOLDS["C"]),
    ):
        if score >= threshold:
            return SpreadGrade(grade_name)
    return SpreadGrade.C  # scores below the C floor (unreachable with C≥0)


def effective_max_spread(score: float, atr: float) -> float:
    """Effective max spread in price units for a setup at ``atr``.

    ``base = SPREAD_MAX_ATR × atr``; the grade multiplier from
    ``SPREAD_GRADE_MULTIPLIERS`` scales it (A+ 1.5 / A 1.0 / B 0.7 / C 0.5).
    """
    if atr <= 0.0:
        raise ValueError("atr must be positive")
    grade = grade_for_score(score)
    multiplier = SPREAD_GRADE_MULTIPLIERS[grade.value]
    return SPREAD_MAX_ATR * atr * multiplier