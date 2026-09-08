"""Phase 0 validation — locked_constants.py contains every frozen threshold.

The name/value pairs asserted here mirror 00_LOCKED/TODO.md Phase 0 exactly,
which in turn mirror LOCKED_DECISIONS.md sections §2/§3/§5/§6/§13/§23/§24/§27.
"""

import smc.config.locked_constants as lc


# name -> frozen value, as listed in TODO.md Phase 0 "Configuration".
TODO_FROZEN = {
    "EQH_EQL_TOLERANCE": 4.5,          # §2 (pips, XAUUSD)
    "DISPLACEMENT_MIN_ATR": 1.0,       # §3
    "DISPLACEMENT_HARD_FAIL": 0.5,     # §3
    "ZONE_REFINEMENT_ATR": 0.5,        # §13
    "PREMIUM_THRESHOLD": 0.55,         # §6
    "DISCOUNT_THRESHOLD": 0.45,        # §6
    "M5_EXPIRY_BARS": 12,              # §5/§23
    "M1_EXPIRY_BARS": 30,              # §5/§23
    "N_BAR_HTF": 5,                    # §27
    "N_BAR_LTF": 3,                    # §27
    "TRIGGER_A_EXPIRY": 20,            # §24
    "TRIGGER_B_EXPIRY": 30,            # §24
    "TRIGGER_C_EXPIRY_EXTRA": 3,       # §24
    "TRIGGER_D_EXPIRY": 1,             # §24
    "TRIGGER_E_EXPIRY": 15,            # §24
    "TRIGGER_F_EXPIRY": 1,             # §24
}

# Additional frozen values extracted from LOCKED_DECISIONS.md.
EXTRA_FROZEN = {
    "DISPLACEMENT_PREFERRED_ATR": 1.5,    # §3
    "EQUILIBRIUM_MIN": 0.45,              # §6 (45%–55% reject band)
    "EQUILIBRIUM_MAX": 0.55,              # §6
    "INDUCEMENT_WITH_SCORE": 1.0,         # §7
    "INDUCEMENT_WITHOUT_SCORE": 0.7,      # §7
    "NEWS_HARD_CANCEL_MINUTES": 15,       # §11
    "NEWS_RE_EVALUATE_MINUTES": 30,       # §11
    "M8_HTF_OVERLAP_BONUS": 0.10,         # §21/§26
    "M8_MIN_RR": 5.0,                     # §21 (minimum 1:5)
    "ASIA_START_HOUR_UTC": 0,             # §2
    "ASIA_END_HOUR_UTC": 7,               # §2
    "LONDON_START_HOUR_UTC": 7,           # §2
    "LONDON_END_HOUR_UTC": 13,            # §2
    "NY_START_HOUR_UTC": 13,              # §2
    "NY_END_HOUR_UTC": 20,                # §2
}

# Phase 5 risk-layer thresholds, locked 2026-09-07 per the Lead Architect's
# Risk Constants Lock decision (LOCKED_DECISIONS.md §28).
RISK_FROZEN = {
    "PURE_RUNNER_BE_ATR": 1.0,                      # §28.1
    "PURE_RUNNER_BE_BUFFER_ATR": 0.10,              # §28.1
    "CIRCUIT_BREAKER_LOSS_COUNT": 3,                # §28.2
    "CIRCUIT_BREAKER_PAUSE_HOURS": 4,               # §28.2
    "SAME_LEVEL_GUARD_ATR": 0.15,                   # §28.3 (running default; supersedes 0.1 comment)
    "SAME_LEVEL_GUARD_COOLDOWN_BARS": 4,            # §28.3
    "FRIDAY_EOD_CLOSE_HOUR_UTC": 20,                # §28.4
    "SPREAD_MAX_ATR": 0.15,                         # §28.5
    "SPREAD_GRADE_MULTIPLIERS": {"A+": 1.5, "A": 1.0, "B": 0.7, "C": 0.5},  # §28.5
    "SPREAD_GRADE_SCORE_THRESHOLDS": {"A+": 8, "A": 5, "B": 3, "C": 0},    # §28.5
    "SWEEP_GUARD_ZONE_ATR": 0.5,                    # §28.6
    "SWEEP_GUARD_COOLDOWN_BARS": 4,                 # §28.6
    "RISK_PCT_MIN": 0.5,                            # §28.7
    "RISK_PCT_MAX": 1.0,                            # §28.7
    "LOT_MAX_SAFETY": 0.10,                         # §28.7
    "ADX_MIN_ENTRY": 25.0,                          # §28.8 (optional gate)
    "ATR_FLOOR_MIN_SL": 1.0,                        # §28.8 (optional gate)
}


def test_todo_frozen_thresholds_present_with_exact_values():
    for name, expected in TODO_FROZEN.items():
        assert hasattr(lc, name), f"missing frozen constant: {name}"
        assert getattr(lc, name) == expected, f"{name} drifted from {expected}"


def test_additional_locked_thresholds_present_with_exact_values():
    for name, expected in EXTRA_FROZEN.items():
        assert hasattr(lc, name), f"missing frozen constant: {name}"
        assert getattr(lc, name) == expected, f"{name} drifted from {expected}"


def test_risk_frozen_thresholds_present_with_exact_values():
    for name, expected in RISK_FROZEN.items():
        assert hasattr(lc, name), f"missing frozen constant: {name}"
        assert getattr(lc, name) == expected, f"{name} drifted from {expected}"


def test_all_frozen_names_exported():
    for name in [*TODO_FROZEN, *EXTRA_FROZEN, *RISK_FROZEN]:
        assert name in lc.__all__, f"{name} missing from __all__"