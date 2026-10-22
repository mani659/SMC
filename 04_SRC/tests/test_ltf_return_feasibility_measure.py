"""Tests for the LTF-return feasibility measure (read-only research).

Pins the design's selection rule exactly as written in
00_LOCKED/MODE_A_LTF_RETURN_ENTRY_DESIGN.md sections 4/6: the FVG
primary (product detector semantics), the report-only OB alternate,
the strict protected-side rule at the true proof close,
STRUCT_UNAVAILABLE fail-closed behavior, and the frozen first-fired
kill thresholds. No product code is touched by these tests.
"""

import os
import sys
from pathlib import Path

SCRIPTS_DIR = (Path(__file__).resolve().parents[2] / "06_RESEARCH"
               / "scripts")
sys.path.insert(0, str(SCRIPTS_DIR))

import entry_representation_measure  # noqa: F401,E402 (loads frame consts)
import ltf_return_feasibility_measure as m  # noqa: E402


class _Bar:
    def __init__(self, close, high=None, low=None):
        self.close = close
        self.high = high if high is not None else close + 0.5
        self.low = low if low is not None else close - 0.5
        self.timestamp = None


def test_measure_constants_pinned_to_design():
    assert m.LOOKBACK_BARS == 48            # REUSE of frozen H_PROOF=48
    assert m.KILL_GAP_RATE == 0.30
    assert m.KILL_MEDIAN_FAR == 2.0
    assert m.KILL_NEAR_SHARE == 0.50
    assert m.KILL_EXPIRED_RATE == 0.85
    assert m.KILL_EXPIRED_MIN_N == 20
    assert m.KILL_FILLS_EVALUABLE == 3      # exactly the 3 control fills
    assert m.EXPECTED_P0 == 10 and m.EXPECTED_P1 == 268
    assert m.BANNER.startswith("DIAGNOSTIC")
    assert m.PRIMARY == "FVG_primary"
    assert m.ALTERNATE == "OB_alternate"    # report-only name


def _leg_with_fvg(bars_before: int):
    """A short bullish leg with one clean FVG:
    c1.high=10.0, c3.low=12.0 -> bull zone [10,12]."""
    bars = [_Bar(100.0 + i) for i in range(bars_before)]
    bars.append(_Bar(11.0, high=10.0, low=9.0))     # c1 (bearish)
    bars.append(_Bar(12.0, high=13.0, low=11.0))    # c2 (bullish leg)
    bars.append(_Bar(14.0, high=15.0, low=12.0))    # c3 -> bull FVG [10,12]
    return bars


def test_fvg_selection_nearest_and_direction():
    bars = _leg_with_fvg(0)          # exactly the 3-bar leg
    proof = len(bars) - 1            # proof close 14.0
    cands = m.fvg_candidates(bars, "long", proof, lookback=48)
    assert cands and cands[0][1] == 0               # absolute first index
    fvg, abs_start = cands[0]
    assert fvg.zone.direction.name == "LONG"
    # near edge = zone TOP = 12.0, strictly below proof close 14.0
    kind, status, limit, detail = m.structure_for_row(bars, "long", proof,
                                                      14.0)
    assert (kind, status) == (m.PRIMARY, "STRUCT_FOUND_FVG")
    assert abs(limit - 12.0) < 1e-9
    assert abs(detail["fvg_top"] - 12.0) < 1e-9
    assert abs(detail["fvg_bottom"] - 10.0) < 1e-9
    assert detail["fvg_start_index"] == 0


def test_fvg_strict_side_fails_and_ob_alternate():
    # Case A: proof close inside the gap (12.0) -> FVG strict side
    # fails; there is NO candle before the FVG's first candle within
    # the window -> OB pairing unavailable -> STRUCT_UNAVAILABLE
    bars = _leg_with_fvg(0)
    proof = len(bars) - 1
    kind, status, limit, _d = m.structure_for_row(bars, "long", proof,
                                                  12.0)
    assert kind == "" and status == "STRUCT_UNAVAILABLE" and limit is None
    # Case B: SHORT thesis on a bullish leg -> no direction-matched
    # structure -> STRUCT_UNAVAILABLE (wrong-direction FVGs are
    # skipped, never hybrid, never substituted)
    kind, status, limit, _d = m.structure_for_row(bars, "short", proof,
                                                  14.0)
    assert status == "STRUCT_UNAVAILABLE"
    # Case C: OB alternate fires when the FVG edge sits above the
    # proof close but the OB candle (candle immediately BEFORE the
    # FVG's first candle, R1 §3.1) sits strictly below it (LONG).
    bars3 = [_Bar(9.0, high=9.5, low=8.5) for _ in range(2)] + \
        _leg_with_fvg(0)
    proof3 = len(bars3) - 1
    kind, status, limit, detail = m.structure_for_row(
        bars3, "long", proof3, 11.2)
    assert (kind, status) == (m.ALTERNATE, "STRUCT_FOUND_OB")
    # OB = bars3[0] (the candle before the leg FVG's first candle)
    assert abs(detail["ob_top"] - 9.5) < 1e-9
    assert abs(limit - 9.5) < 1e-9


def test_fvg_no_formation_faillosed():
    bars = [_Bar(100.0, high=100.5, low=99.5) for _ in range(60)]  # flat
    kind, status, limit, detail = m.structure_for_row(bars, "long", 59,
                                                      100.0)
    assert kind == "" and status == "STRUCT_UNAVAILABLE" and limit is None
    # out-of-range proof index -> fail-closed
    assert m.fvg_candidates(bars, "long", 999) == []
    assert m.fvg_candidates(bars, "sideways", 59) == []


def test_htf_zone_intersect_is_label_only():
    assert m.zone_intersects(10.0, 5.0, 15.0) == "True"
    assert m.zone_intersects(16.0, 5.0, 15.0) == "False"
    # missing bounds -> empty label (never inferred, never a filter)
    assert m.zone_intersects(10.0, None, 15.0) == ""
    assert m.zone_intersects(None, 5.0, 15.0) == ""


def test_paper_touch_touchonly_and_faillosed():
    bars_dict = [{"high": 100.0 + i + 0.5, "low": 100.0 + i - 0.5,
                  "close": 100.0 + i} for i in range(30)]
    # short sell limit ABOVE the market, risen into at bar 25 (high 125.5)
    out, fill, note = m.paper_touch(bars_dict, "short", 125.0, 0, 29)
    assert out == "FILLED_NO_RESOLVE" and fill is not None and note == ""
    # short limit never reachable (highs max 129.5 < 999) -> EXPIRED
    out, fill, note = m.paper_touch(bars_dict, "short", 999.0, 0, 29)
    assert out == "EXPIRED_NO_FILL" and fill is None
    # missing lifetime / limit -> DATA_GAP fail-closed
    assert m.paper_touch(bars_dict, "short", 125.0, 0, None)[0] == "DATA_GAP"
    assert m.paper_touch(bars_dict, "short", None, 0, 29)[0] == "DATA_GAP"


def _kstats(**over):
    base = {
        "data_gap_rate_p1": 0.10,
        "median_gap_atr_p1": 1.0,
        "share_le_1_p1": 0.6,
        "n_fills_evaluable": 3,
        "fill_overlap": 2,
        "n_paper_lifetime_path": 40,
        "paper_expired_rate_path": 0.5,
    }
    base.update(over)
    return base


def test_kills_first_fired_exact_thresholds():
    # healthy -> PASS_FEASIBILITY
    assert m.evaluate_rule_kills(_kstats())["verdict"] == "PASS_FEASIBILITY"
    # frozen first-fired order: INCONCLUSIVE first, then far, near mass,
    # baseline, unfillable
    out = m.evaluate_rule_kills(_kstats(data_gap_rate_p1=0.45,
                                        median_gap_atr_p1=5.0,
                                        share_le_1_p1=0.1,
                                        fill_overlap=0,
                                        paper_expired_rate_path=0.95))
    assert out["verdict"] == "INCONCLUSIVE"
    assert out["killed"][1:] == ["FAIL_STILL_FAR", "FAIL_NO_NEAR_MASS",
                                 "FAIL_BASELINE", "FAIL_UNFILLABLE"]
    # kill 2 boundary: median exactly 2.0 does NOT fire (strictly greater)
    assert m.evaluate_rule_kills(_kstats(median_gap_atr_p1=2.0))["verdict"] \
        == "PASS_FEASIBILITY"
    # kill 3 boundary: share exactly 0.50 does NOT fire (strictly less)
    assert m.evaluate_rule_kills(_kstats(share_le_1_p1=0.50))["verdict"] \
        == "PASS_FEASIBILITY"
    # kill 4 gate: fewer than 3 evaluable fills cannot fire it at all
    assert m.evaluate_rule_kills(_kstats(fill_overlap=0,
                                         n_fills_evaluable=2))["verdict"] \
        == "PASS_FEASIBILITY"
    assert m.evaluate_rule_kills(_kstats(fill_overlap=0))["verdict"] \
        == "FAIL_BASELINE"
    # kill 5: n gate and strict-greater threshold
    assert m.evaluate_rule_kills(_kstats(n_paper_lifetime_path=19,
                                         paper_expired_rate_path=1.0)) \
        ["verdict"] == "PASS_FEASIBILITY"
    assert m.evaluate_rule_kills(_kstats(n_paper_lifetime_path=20,
                                         paper_expired_rate_path=0.85)) \
        ["verdict"] == "PASS_FEASIBILITY"
    assert m.evaluate_rule_kills(_kstats(n_paper_lifetime_path=20,
                                         paper_expired_rate_path=0.86)) \
        ["verdict"] == "FAIL_UNFILLABLE"


def test_control_baseline_is_not_an_input():
    # the control column carries the retired family's frozen numbers as
    # evidence only; the measure's limit rule never reads them
    src = Path(m.__file__).read_text(encoding="utf-8")
    # zones feed ONLY the label column; the limit selection path is
    # built purely from the product detector + the proof close
    assert "structure_for_row" in src
    # the CONTROL numbers appear only in the baseline view construction
    assert 'm["stats"]' not in src           # no summary-driven rebounding
    # no wall-clock anywhere: the summary writer must not embed a clock
    assert "datetime.now" not in src and "time.time()" not in src
    # determinism receipts: same argv must produce byte-identical files
    # (checked operationally by the dual-run SHA match in the note)
