"""Reactive admission measure — focused tests (research only).

Locks the frozen pure helpers of
``06_RESEARCH/scripts/reactive_admission_measure.py``: population
classification, the R1-R6 fail-closed evaluation (a missing field never
invents an admission), R5's engine-true touch-first violation semantics,
the R4 proximity boundary, the R6 one-shot rule, the secondary
paper-outcome labels, and the pre-registered kill-criteria thresholds and
measure constants (a change to the measurement rule must fail loudly,
not silently re-label artifacts).

No threshold change, no gate, no routing rule, no expectancy assertion —
this file tests measurement arithmetic only.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

_SCRIPT_PATH = (Path(__file__).resolve().parents[2]
                / "06_RESEARCH" / "scripts" / "reactive_admission_measure.py")


def _load():
    spec = importlib.util.spec_from_file_location(
        "reactive_admission_measure", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["reactive_admission_measure"] = module
    spec.loader.exec_module(module)
    return module


RAM = _load()


def _candle(i, high, low, close, stamp=None):
    if stamp is None:
        stamp = datetime(2025, 6, 4, 15, 0, tzinfo=timezone.utc)  # in session
    return SimpleNamespace(index=i, timestamp=stamp, high=high, low=low,
                           close=close)


def _flat_bars(n, *, high=120.0, low=118.0, close=119.0):
    return [_candle(i, high, low, close) for i in range(n)]


def _dict_bars(bars):
    return [{"timestamp": b.timestamp, "open": None, "high": b.high,
             "low": b.low, "close": b.close} for b in bars]


def make_row(**overrides):
    base = {
        "population": 1, "direction": "LONG",
        "armed_poi_id": "poi-x", "armed_bar": 90,
        "proof_bar": 100, "proof_trigger": "F",
        "zone_low": 100, "zone_high": 110, "would_be_limit": 110,
        "route_present_bar": None, "route_entry": None, "route_sl": None,
        "route_tp": None, "route_original_sl": None, "route_id": None,
        "rest_bars": 40, "anchor_kind": None, "episode_id": "e1",
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# 1. Frozen measure constants pinned
# --------------------------------------------------------------------------- #
def test_frozen_measure_constants():
    assert RAM.H_PROOF == 48
    assert RAM.H_RETURN == 20
    assert RAM.PROX_ATR_MULT == 1.0
    assert RAM.CHASE_RANGE_ATR_MULT == 1.5
    assert RAM.GAP_INCONCLUSIVE_RATE == 0.20
    assert RAM.EXPECTED_POP == {1: 268, 2: 208, 3: 109}
    assert RAM.EXPECTED_COINCIDENT == 585
    assert RAM.EXPECTED_WARMUP_OFFSET == 6018


# --------------------------------------------------------------------------- #
# 2. Parsers / small helpers
# --------------------------------------------------------------------------- #
def test_parse_direction():
    assert RAM.parse_direction("LONG") == "long"
    assert RAM.parse_direction("short") == "short"
    assert RAM.parse_direction("") is None
    assert RAM.parse_direction(None) is None
    assert RAM.parse_direction(" sideways") is None


def test_parse_tf_fields():
    assert RAM.parse_tf_fields("M8-H4") == ("H4", True)
    assert RAM.parse_tf_fields("H1") == ("H1", False)
    assert RAM.parse_tf_fields("") == (None, False)
    assert RAM.parse_tf_fields("M8") == (None, True)


def test_proximal_edge():
    assert RAM.proximal_edge("long", 100, 110) == 110
    assert RAM.proximal_edge("short", 100, 110) == 100
    assert RAM.proximal_edge(None, 100, 110) is None
    assert RAM.proximal_edge("long", None, 110) is None


def test_sma_tr_atr_exact_and_short_series():
    # TR bars: each bar range 2, no gaps -> ATR = 2.0
    bars = [_candle(i, 12, 10, 11) for i in range(20)]
    assert RAM.sma_tr_atr(bars, 14) == 2.0
    assert RAM.sma_tr_atr(bars, 2) is None   # incomplete period
    assert RAM.sma_tr_atr(bars, 30) is None  # out of range
    # one whole TR of 40 at the inclusive end bar: (13*2 + 40) / 14
    bars2 = list(bars)
    bars2[14] = _candle(14, 50, 10, 11)
    assert RAM.sma_tr_atr(bars2, 14) == (2 * 13 + 40) / 14


# --------------------------------------------------------------------------- #
# 3. Population classification
# --------------------------------------------------------------------------- #
def test_classify_population():
    assert RAM.classify_population("filled", None) == 1
    assert RAM.classify_population("routed", None) == 1
    assert RAM.classify_population("armed_never_routed", None) == 1
    assert RAM.classify_population("armed_never_routed_zone_only", None) == 1
    assert RAM.classify_population("never_armed", True) == 2
    assert RAM.classify_population("never_armed", False) == 3
    assert RAM.classify_population("never_armed", None) == 3


# --------------------------------------------------------------------------- #
# 4. Violation semantics (engine-true touch-first walk)
# --------------------------------------------------------------------------- #
def test_violated_gap_before_touch_is_violation():
    bars = _flat_bars(20)
    bars[1] = _candle(1, high=95, low=90, close=92)   # full gap below zone
    assert RAM.violated_since("long", 100, 110, bars, 0, 10) is True


def test_violated_touch_then_gap_is_not_engine_violation():
    bars = _flat_bars(20)
    bars[1] = _candle(1, high=105, low=95, close=100)  # touches zone -> TESTED
    bars[2] = _candle(2, high=95, low=90, close=92)    # later full gap
    assert RAM.violated_since("long", 100, 110, bars, 0, 10) is False


def test_violated_short_mirror():
    bars = _flat_bars(20)
    bars[1] = _candle(1, high=130, low=125, close=128)  # full gap above zone
    assert RAM.violated_since("short", 100, 110, bars, 0, 10) is True


def test_violated_no_interaction():
    bars = _flat_bars(20)
    assert RAM.violated_since("long", 100, 110, bars, 0, 10) is False


# --------------------------------------------------------------------------- #
# 5. R-rule evaluation: the golden admit path + fail-closed gaps
# --------------------------------------------------------------------------- #
def _bars_with_return_at(proof, *, high=111.0, low=109.5, close=110.5):
    bars = _flat_bars(proof + 30)
    bars[proof] = _candle(proof, high=high, low=low, close=close)
    return bars


def test_golden_admit_path():
    bars = _bars_with_return_at(100)
    rules = RAM.evaluate_r_rules(make_row(), bars, lambda i: 2.0)
    statuses = [rules[k] for k in ("r1_thesis", "r2_proof", "r3_timing",
                                   "r4_location", "r5_exclusion",
                                   "r6_one_shot")]
    assert statuses == ["PASS"] * 6
    assert rules["would_admit"] == "True"
    assert rules["data_gap"] == "False"
    assert rules["presentation_bar"] == 100  # proof bar itself is in-zone


def test_missing_direction_is_data_gap_fail_closed():
    bars = _bars_with_return_at(100)
    rules = RAM.evaluate_r_rules(make_row(direction=""), bars, lambda i: 2.0)
    assert rules["r2_proof"] == "GAP"
    assert rules["data_gap"] == "True"
    assert rules["would_admit"] == "False"


def test_missing_zone_bounds_fail_closed():
    bars = _bars_with_return_at(100)
    rules = RAM.evaluate_r_rules(make_row(zone_low=""), bars, lambda i: 2.0)
    assert rules["data_gap"] == "True"
    assert rules["would_admit"] == "False"


def test_r1_arm_after_proof_fails_reactive_scope():
    bars = _bars_with_return_at(100)
    rules = RAM.evaluate_r_rules(make_row(armed_bar=105), bars, lambda i: 2.0)
    assert rules["r1_thesis"] == "FAIL"
    assert rules["r1_reason"] == "thesis_not_armed_at_proof"
    assert rules["would_admit"] == "False"


def test_r1_missing_armed_facts_is_gap():
    bars = _bars_with_return_at(100)
    rules = RAM.evaluate_r_rules(make_row(armed_poi_id=""), bars, lambda i: 2.0)
    assert rules["r1_thesis"] == "GAP"
    assert rules["would_admit"] == "False"


def test_pop2_row_r1_fails_but_phase2_report_column_exists():
    bars = _bars_with_return_at(100)
    rules = RAM.evaluate_r_rules(make_row(population=2), bars, lambda i: 2.0)
    assert rules["r1_thesis"] == "FAIL"
    assert rules["r1_reason"] == "phase1_scope_unarmed"
    assert rules["would_admit"] == "False"
    assert rules["would_admit_phase2"] == "True"


def test_r3_no_return_in_window():
    bars = _flat_bars(200)  # price never comes back to the zone
    rules = RAM.evaluate_r_rules(make_row(), bars, lambda i: 2.0)
    assert rules["r3_timing"] == "FAIL"
    assert rules["r3_reason"] == "no_return_in_window"
    assert rules["r4_location"] == "FAIL"
    assert rules["presentation_bar"] is None


def test_r4_proximity_boundary_inclusive():
    # distance exactly 1.0 * ATR -> PASS; beyond -> FAIL (limit_far).
    # The bar must still present itself (low pierces the proximal edge).
    for close, expect in ((112.0, "PASS"), (112.06, "FAIL")):
        bars = _bars_with_return_at(100, high=113.0, low=109.5, close=close)
        rules = RAM.evaluate_r_rules(make_row(), bars, lambda i: 2.0)
        assert rules["r4_location"] == expect, (close, rules)


def test_r5_session_out_fails():
    off_hours = datetime(2025, 6, 7, 20, 0, tzinfo=timezone.utc)  # Sat evening
    bars = _bars_with_return_at(100)
    bars[100] = _candle(100, 111.0, 109.5, 110.5, stamp=off_hours)
    rules = RAM.evaluate_r_rules(make_row(), bars, lambda i: 2.0)
    assert rules["r5_exclusion"] == "FAIL"
    assert "session_out" in rules["r5_reason"]
    assert rules["session_ok"] is False


def test_r6_one_shot_consumed_by_route():
    bars = _bars_with_return_at(100)
    rules = RAM.evaluate_r_rules(make_row(route_present_bar=99), bars,
                                 lambda i: 2.0)
    assert rules["r6_one_shot"] == "FAIL"
    assert rules["r6_reason"] == "one_shot_consumed_by_route"


def test_r6_route_presented_at_or_after_presentation_passes():
    bars = _bars_with_return_at(100)
    for route_bar in (100, 101, 250):
        rules = RAM.evaluate_r_rules(make_row(route_present_bar=route_bar),
                                     bars, lambda i: 2.0)
        assert rules["r6_one_shot"] == "PASS", route_bar


def test_missing_proof_bar_is_gap():
    bars = _bars_with_return_at(100)
    rules = RAM.evaluate_r_rules(make_row(proof_bar=None), bars, lambda i: 2.0)
    assert rules["r1_thesis"] == "GAP"
    assert rules["r3_timing"] == "GAP"
    assert rules["would_admit"] == "False"


# --------------------------------------------------------------------------- #
# 6. Paper outcome labels (touch-only for zone-edge rows)
# --------------------------------------------------------------------------- #
def test_paper_not_admitted_is_never_traded():
    row = make_row()
    row.update({"r1_thesis": "FAIL", "r2_proof": "PASS", "r3_timing": "PASS",
                "r4_location": "FAIL", "r5_exclusion": "PASS",
                "r6_one_shot": "PASS", "presentation_bar": None,
                "would_admit": "False", "would_admit_phase2": "False"})
    out = RAM.evaluate_paper_outcome(row, [], 1)
    assert out["paper_outcome"] == "NOT_ADMITTED"


def test_paper_zone_edge_expired_no_fill():
    bars = _bars_with_return_at(100)[0:]
    bars = _bars_with_return_at(160)  # long enough flat tail
    for i in range(101, 140):
        bars[i] = _candle(i, 115.0, 114.0, 114.5)  # never touches 110 again
    dict_bars = _dict_bars(bars)
    row = make_row()
    row.update({"would_admit": "True", "would_admit_phase2": "True",
                "presentation_bar": 100})
    out = RAM.evaluate_paper_outcome(row, dict_bars, 1)
    assert out["paper_outcome"] == "EXPIRED_NO_FILL"
    assert out["paper_touched"] == "False"


def test_paper_zone_edge_filled_no_resolve():
    bars = _bars_with_return_at(100)
    bars[105] = _candle(105, 112.0, 108.0, 109.0)  # touches the limit
    dict_bars = _dict_bars(bars)
    row = make_row()
    row.update({"would_admit": "True", "would_admit_phase2": "True",
                "presentation_bar": 100})
    out = RAM.evaluate_paper_outcome(row, dict_bars, 1)
    assert out["paper_outcome"] == "FILLED_NO_RESOLVE"
    assert out["paper_fill_bar"] == 105


def test_paper_route_row_uses_frozen_simulate():
    bars = _bars_with_return_at(100)
    bars[105] = _candle(105, 109.0, 100.0, 105.0)  # deep into the zone
    dict_bars = _dict_bars(bars)
    row = make_row(route_entry=110.0, route_sl=112.0, route_tp=108.0,
                   route_id="e1:F@100")
    row.update({"would_admit": "True", "would_admit_phase2": "True",
                "presentation_bar": 100})
    out = RAM.evaluate_paper_outcome(row, dict_bars, 1)
    assert out["paper_outcome"] == "SL_HIT"  # SL first (touch order frozen)


def test_paper_missing_lifetime_is_data_gap():
    row = make_row(rest_bars=None)
    row.update({"would_admit": "True", "would_admit_phase2": "True",
                "presentation_bar": 100})
    out = RAM.evaluate_paper_outcome(row, _dict_bars(_bars_with_return_at(100)), 1)
    assert out["paper_outcome"] == "DATA_GAP"


# --------------------------------------------------------------------------- #
# 7. Kill criteria (verbatim thresholds, frozen order)
# --------------------------------------------------------------------------- #
def _stats(*, n=0, expired=None, gap=0.0, overlap_fills=0, evaluable=True):
    return {"n_would_admit_pop1": n,
            "expired_no_fill_rate_pop1": expired,
            "data_gap_rate_pop1": gap,
            "overlap_fills": overlap_fills,
            "fills_evaluable": evaluable}


def test_kill1_under_selective():
    out = RAM.evaluate_kill_criteria(_stats(n=3, expired=0.0))
    assert out["verdict"] == "FAIL_TIGHT"
    assert any("kill1" in k for k in out["killed"])


def test_kill2_representation():
    out = RAM.evaluate_kill_criteria(_stats(n=30, expired=0.90))
    assert out["verdict"] == "FAIL_REPRESENTATION"


def test_kill2_requires_n_at_least_25():
    # overlap with control fills supplied so only the n/expired edge counts
    assert RAM.evaluate_kill_criteria(_stats(n=24, expired=0.90,
                                             overlap_fills=3))["verdict"] \
        == "PASS_MEASURE"
    assert RAM.evaluate_kill_criteria(_stats(n=25, expired=0.9001,
                                             overlap_fills=3))["verdict"] \
        == "FAIL_REPRESENTATION"


def test_kill3_zero_control_overlap_fires_only_when_evaluable():
    fired = RAM.evaluate_kill_criteria(_stats(n=30, expired=0.0,
                                              overlap_fills=0, evaluable=True))
    assert fired["verdict"] == "FAIL_BASELINE"
    not_fired = RAM.evaluate_kill_criteria(_stats(n=30, expired=0.0,
                                                  overlap_fills=0,
                                                  evaluable=False))
    assert not_fired["verdict"] == "PASS_MEASURE"


def test_kill4_flood():
    out = RAM.evaluate_kill_criteria(_stats(n=151, expired=0.0,
                                            overlap_fills=3))
    assert out["verdict"] == "FAIL_FLOOD"


def test_pass_measure():
    out = RAM.evaluate_kill_criteria(_stats(n=30, expired=0.5,
                                            overlap_fills=3))
    assert out["verdict"] == "PASS_MEASURE"
    assert out["killed"] == []


def test_inconclusive_on_data_gap_rate():
    out = RAM.evaluate_kill_criteria(_stats(n=30, expired=0.0, gap=0.30))
    assert out["verdict"] == "INCONCLUSIVE"


def test_boundary_pass_measure_at_kill1_threshold():
    # n == 8 is NOT < 8: the threshold is inclusive on the passing side
    out = RAM.evaluate_kill_criteria(_stats(n=8, expired=0.0, overlap_fills=3))
    assert out["verdict"] == "PASS_MEASURE"
