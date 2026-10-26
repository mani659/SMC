"""Tests for the offline entry-representation measure (read-only).

Pins the frozen rule functions (RL-1 shelf + guard rails, RL-2
parameter-free midpoint, RL-3 deferred presentation), the fail-closed
gaps, and the design's pre-registered kill branches exactly as written
in 00_LOCKED/ENTRY_REPRESENTATION_DESIGN.md section 4/5.
"""

import os
import sys
from pathlib import Path

SCRIPTS_DIR = (Path(__file__).resolve().parents[2] / "06_RESEARCH"
               / "scripts")
sys.path.insert(0, str(SCRIPTS_DIR))

import entry_representation_measure as m  # noqa: E402


class _Bar:
    def __init__(self, close, high=None, low=None):
        self.close = close
        self.high = high if high is not None else close + 0.5
        self.low = low if low is not None else close - 0.5


def test_measure_constants_pinned_to_design():
    assert m.K_SHELF == 1.0
    assert m.RETRACE_FRACTION == 0.5
    assert m.LEG_SPAN_LOOKBACK == 96
    assert m.PRESENT_PROX_ATR == 1.0
    # design section 5 frozen kill thresholds
    assert m.KILL_MEDIAN_FAR == 6.0
    assert m.KILL_NEAR_SHARE == 0.10
    assert m.KILL_EXPIRED_RATE == 0.90
    assert m.KILL_EXPIRED_MIN_N == 20
    assert m.KILL_GAP_RATE == 0.20
    assert m.RULES == (m.RULE_CONTROL, m.RULE_RL1, m.RULE_RL2, m.RULE_RL3)
    assert m.BANNER.startswith("DIAGNOSTIC")
    # the four rules x two populations shape
    assert m.EXPECTED_P0 == 10 and m.EXPECTED_P1 == 268


def test_rl1_long_formula_and_guards():
    # C=110, ATR=2 -> shelf at 108; zone 100..105 (distal edge 100),
    # proof high/low 111/107 -- every guard passes
    limit, reason = m.rl1_limit("long", 110.0, 2.0, 100.0, 105.0, 111.0, 107.0)
    assert abs(limit - 108.0) < 1e-9 and reason is None
    # guard 2: shelf would tunnel through the zone (108 < 100? no -- use a
    # zone whose distal edge is above the shelf)
    limit, reason = m.rl1_limit("long", 110.0, 5.0, 108.0, 109.0, 111.0, 109.0)
    assert reason == "guard2_zone_tunneling"        # 105 < 108 distal edge
    # guard 3: shelf below the proof bar's low
    limit, reason = m.rl1_limit("long", 110.0, 2.0, 100.0, 105.0, 111.0, 109.5)
    assert reason == "guard3_proof_extreme"         # 108 < 109.5
    # guard 1: k <= 0 would sit at/above the proof close -> protected side
    # guard 1: k <= 0 would sit at/above the proof close -> protected side
    limit, reason = m.rl1_limit("long", 110.0, 0.0, 100.0, 105.0, 111.0, 109.0)
    assert reason == "guard1_protected_side"
    # unknown direction fails closed
    assert m.rl1_limit("sideways", 110.0, 2.0, 100.0, 105.0, 111.0, 109.0) \
        == (None, "missing_direction")


def test_rl1_short_formula_and_guards():
    # C=100, ATR=2 -> shelf 102; zone 95..103 (distal short edge 103),
    # proof high/low 102.5/98 -- every guard passes
    limit, reason = m.rl1_limit("short", 100.0, 2.0, 95.0, 103.0, 102.5, 98.0)
    assert abs(limit - 102.0) < 1e-9 and reason is None
    limit, reason = m.rl1_limit("short", 100.0, 3.0, 95.0, 101.0, 100.5, 98.0)
    assert reason == "guard2_zone_tunneling"        # 103 > 101 zone high
    limit, reason = m.rl1_limit("short", 100.0, 2.0, 95.0, 103.0, 101.0, 98.0)
    assert reason == "guard3_proof_extreme"         # 102 > 101 proof high
    limit, reason = m.rl1_limit("short", 100.0, 0.0, 95.0, 99.0, 100.5, 98.0)
    assert reason == "guard1_protected_side"


def test_rl2_midpoint_parameter_free():
    # long: edge below -> midpoint toward the leg extreme above
    assert abs(m.rl2_limit("long", 100.0, 110.0) - 105.0) < 1e-9
    # extreme equal to the edge -> limit = edge (degenerate leg)
    assert abs(m.rl2_limit("long", 100.0, 100.0) - 100.0) < 1e-9
    # short: edge above -> midpoint toward the leg extreme below
    assert abs(m.rl2_limit("short", 100.0, 90.0) - 95.0) < 1e-9
    assert abs(m.rl2_limit("short", 100.0, 100.0) - 100.0) < 1e-9
    assert m.rl2_limit("sideways", 100.0, 110.0) is None


def test_leg_extreme_span_and_fail_closed():
    bars = [_Bar(100.0 + i) for i in range(30)]
    # long: edge 104 touched at bar 4 (range 103.5..104.5); extreme = high 29
    extreme, span = m.leg_extreme(bars, "long", 104.0, 29, lookback=96)
    assert span == 4
    assert abs(extreme - 129.5) < 1e-9
    # edge never touched inside the lookback -> DATA_GAP contract
    extreme, span = m.leg_extreme(bars, "short", 50.0, 29, lookback=10)
    assert extreme is None and span is None
    # unknown direction / missing edge fail closed
    assert m.leg_extreme(bars, "sideways", 104.0, 29) == (None, None)


def _atr_const(value):
    return lambda _i: value


def test_rl3_presentation_immediate_and_deferred():
    class NamedBar:  # the NAMED rule reads low/high/close/timestamp
        def __init__(self, close, high, low):
            self.close, self.high, self.low = close, high, low
            self.timestamp = None

    # short thesis: zone 98..102, limit at edge 98, market starts at 110
    bars = [NamedBar(110.0 - 1.0 * i, 110.5 - 1.0 * i, 109.5 - 1.0 * i)
            for i in range(12)]
    atr_at = _atr_const(2.0)
    # bar 12 is out of range; from close 110 down to 99.5
    # reentry: close inside band? band 98..102: close reaches 99 at bar 11
    present, kind = m.rl3_presentation(bars, "short", 98.0, 98.0, 102.0,
                                       0, 30, atr_at)
    # bar 10: close 100 -> in band; |98 - 100| = 2 <= 1.0*2.0 (ATR const)
    # -> first deferred presentation at bar 10 (inclusive guard boundary)
    assert present == 10 and kind == "deferred"
    # tighter ATR constant 0.9: bar 10 (distance 2) fails proximity;
    # bar 11 distance 1 > 0.9 fails too; later bars leave the band
    present, _ = m.rl3_presentation(bars, "short", 98.0, 98.0, 102.0,
                                    0, 30, _atr_const(0.9))
    assert present is None
    # already-near at the proof bar presents immediately (proof included)
    bars2 = [NamedBar(99.0, 99.5, 98.5)] * 5
    present, kind = m.rl3_presentation(bars2, "short", 98.0, 98.0, 102.0,
                                       0, 30, _atr_const(2.0))
    assert present == 0 and kind == "immediate"
    # zone bounds missing -> fail closed (never invents a band)
    assert m.rl3_presentation(bars2, "short", 98.0, None, None,
                              0, 30, _atr_const(2.0)) == (None, None)
    # unknown direction -> fail closed
    assert m.rl3_presentation(bars2, "sideways", 98.0, 98.0, 102.0,
                              0, 30, _atr_const(2.0)) == (None, None)


def _kill_stats(**over):
    base = {
        "median_gap_atr_p1": 1.0,
        "share_le_1_p1": 0.5,
        "n_fills_evaluable": 3,
        "fill_overlap": 2,
        "n_paper_lifetime_path": 40,
        "paper_expired_rate_path": 0.5,
        "data_gap_rate_p1": 0.0,
    }
    base.update(over)
    return base


def test_kill_branches_first_fired_order():
    # all healthy -> PASS_MEASURE
    assert m.evaluate_rule_kills(_kill_stats())["verdict"] == "PASS_MEASURE"
    # kill 1 fires first even when several thresholds are breached
    out = m.evaluate_rule_kills(_kill_stats(median_gap_atr_p1=7.0,
                                            share_le_1_p1=0.05,
                                            fill_overlap=0,
                                            paper_expired_rate_path=0.95))
    assert out["verdict"] == "FAIL_STILL_FAR"
    assert out["killed"] == ["FAIL_STILL_FAR", "FAIL_NO_NEAR_MASS",
                             "FAIL_BASELINE", "FAIL_UNFILLABLE"]
    # kill 2 boundary: exactly 10% do NOT fail (strictly less-than kills)
    assert m.evaluate_rule_kills(_kill_stats(share_le_1_p1=0.10,
                                             median_gap_atr_p1=1.0)) \
        ["verdict"] == "PASS_MEASURE"
    # kill 3: fills must be evaluable N=3; overlap 0 -> FAIL_BASELINE
    assert m.evaluate_rule_kills(_kill_stats(fill_overlap=0)) \
        ["verdict"] == "FAIL_BASELINE"
    # kill 3: fills NOT evaluable -> kill cannot fire (gate, not filé)
    assert m.evaluate_rule_kills(_kill_stats(fill_overlap=0,
                                             n_fills_evaluable=2)) \
        ["verdict"] == "PASS_MEASURE"
    # kill 4: n gate below 20 -> cannot fire at any rate
    assert m.evaluate_rule_kills(_kill_stats(n_paper_lifetime_path=19,
                                             paper_expired_rate_path=1.0)) \
        ["verdict"] == "PASS_MEASURE"
    assert m.evaluate_rule_kills(_kill_stats(n_paper_lifetime_path=20,
                                             paper_expired_rate_path=0.90)) \
        ["verdict"] == "PASS_MEASURE"          # strictly greater fires
    assert m.evaluate_rule_kills(_kill_stats(n_paper_lifetime_path=20,
                                             paper_expired_rate_path=0.91)) \
        ["verdict"] == "FAIL_UNFILLABLE"
    # kill 5: INCONCLUSIVE even when healthy otherwise
    assert m.evaluate_rule_kills(_kill_stats(data_gap_rate_p1=0.21)) \
        ["verdict"] == "INCONCLUSIVE"
    # kill 1 boundary: median exactly 6.0 fires (>= freezes)
    assert m.evaluate_rule_kills(_kill_stats(median_gap_atr_p1=6.0)) \
        ["verdict"] == "FAIL_STILL_FAR"


def test_no_post_hoc_threshold_drift():
    # the thresholds are frozen module constants; a regression that
    # retunes any of them must fail this test loudly
    import importlib
    import entry_representation_measure as fresh
    importlib.reload(fresh)
    assert fresh.KILL_MEDIAN_FAR == 6.0
    assert fresh.K_SHELF == 1.0
    assert fresh.RETRACE_FRACTION == 0.5
    assert fresh.LEG_SPAN_LOOKBACK == 96
