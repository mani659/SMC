"""Tests for the entry-representation study helpers (read-only research).

The study is descriptive: these tests pin the frozen pure helpers --
gap arithmetic, fail-closed DATA_GAP paths, the MECH flag, verdict
family rule, stratum invariants -- so the artifacts' numbers can be
re-verified without re-running the parent admission measure.
"""

import os
import sys
from pathlib import Path

SCRIPTS_DIR = (Path(__file__).resolve().parents[2] / "06_RESEARCH"
               / "scripts")
sys.path.insert(0, str(SCRIPTS_DIR))

import entry_representation_study as er  # noqa: E402


class _Bar:
    def __init__(self, close, high=None, low=None, prev_close=None):
        self.close = close
        self.high = high if high is not None else close * 1.01
        self.low = low if low is not None else close * 0.99
        self._prev_close = prev_close

    @property
    def prev_close(self):  # sma_tr_atr reads `.close` of the prior bar
        return self._prev_close


def _flat_series(n=40, start=100.0, step=1.0):
    bars = []
    for i in range(n):
        close = start + step * i
        bars.append(_Bar(close, high=close + 0.5, low=close - 0.5))
        bars[-1]._prev = None
    return bars


def test_exec_to_grid_basic_and_failclosed():
    assert er.exec_to_grid(18237, 6018) == 24255
    assert er.exec_to_grid(0, 6018) == 6018
    assert er.exec_to_grid(None, 6018) is None
    assert er.exec_to_grid("", 6018) is None
    assert er.exec_to_grid(-1, 6018) is None


def test_limit_source_route_vs_zone_proximal():
    limit, src = er.limit_source_of({"limit": 1.0, "route_id": "R1"})
    assert (limit, src) == (1.0, "recorded_route_entry")
    _, src = er.limit_source_of({"limit": 1.0, "route_id": "",
                                 "zone_source": "armed_record"})
    assert src == "zone_proximal_armed_record"
    assert er.limit_source_of({"limit": None, "route_id": ""}) is None
    assert er.limit_source_of({"limit": "", "route_id": "R1"}) is None


def test_entry_vs_zone_states():
    # short row: proximal edge is zone_low
    assert er.entry_vs_zone_state(10.0, 10.0, 12.0, "short") == "on_edge"
    assert er.entry_vs_zone_state(11.0, 10.0, 12.0, "short") == "inside"
    assert er.entry_vs_zone_state(9.0, 10.0, 12.0, "short") == "beyond_zone"
    # long row: proximal edge is zone_high
    assert er.entry_vs_zone_state(12.0, 10.0, 12.0, "long") == "on_edge"
    assert er.entry_vs_zone_state(11.5, 10.0, 12.0, "long") == "inside"
    assert er.entry_vs_zone_state(13.0, 10.0, 12.0, "long") == "beyond_zone"
    # the far edge shapes
    assert er.entry_vs_zone_state(10.0, 10.0, 12.0, "long") == "on_far_edge"
    assert er.entry_vs_zone_state(12.0, 10.0, 12.0, "short") == "on_far_edge"
    # fail-closed family
    assert er.entry_vs_zone_state(None, 10, 12, "long") == "DATA_GAP"
    assert er.entry_vs_zone_state(11.0, None, 12.0, "long") == "DATA_GAP"
    assert er.entry_vs_zone_state(11.0, 12.0, 10.0, "long") == "DATA_GAP"
    assert er.entry_vs_zone_state(11.0, 10, 12, "sideways") == "DATA_GAP"


def test_gap_vs_basic_arithmetic():
    bars = _flat_series(40)  # close_i = 100 + i
    out = er.gap_vs(bars, limit=115.0, grid_idx=20)  # idx >= ATR period 14
    assert out["close"] == 120.0
    assert abs(out["gap_price"] - 5.0) < 1e-9
    # ATR here is 1.5: TR = max(range 1.0, |close step| 1.5, ...) each bar
    assert abs(out["gap_atr"] - 5.0 / 1.5) < 0.05
    assert out["reason"] == ""


def test_gap_vs_fail_closed_paths():
    bars = _flat_series(40)
    assert er.gap_vs(bars, None, 10)["reason"] == "missing_limit"
    assert er.gap_vs(bars, 100, None)["reason"] == "missing_bar_index"
    assert er.gap_vs(bars, 100, 999)["reason"] == "bar_out_of_range"
    out = er.gap_vs(bars[:5], 100, 0)  # ATR period 14 not yet available
    assert out["reason"] == "atr_unavailable"
    assert out["gap_atr"] is None
    assert out["gap_price"] == 0.0  # price known even when ATR unavailable


def _mech_row(limit, zone_low, zone_high, direction, gap_atr):
    return {
        "limit": limit,
        "gap_atr_proof": gap_atr,
        "entry_vs_zone": er.entry_vs_zone_state(limit, zone_low, zone_high,
                                                direction),
        "direction": direction,
        "zone_low": zone_low,
        "zone_high": zone_high,
    }


def test_is_mech_on_edge_far_and_near():
    row = _mech_row(12.0, 10.0, 12.0, "long", 1.5)
    assert er.is_mech(row) == "on_edge_far"
    assert er.is_mech(_mech_row(12.0, 10.0, 12.0, "long", 0.8)) == "near"
    assert er.is_mech(_mech_row(11.0, 10.0, 12.0, "long", 3.0)) == "off_edge"
    # boundary: exactly 1.0 ATR is NOT far (> 1.0 strictly)
    assert er.is_mech(_mech_row(12.0, 10.0, 12.0, "long", 1.0)) == "near"
    # fail-closed
    assert er.is_mech(_mech_row(12.0, 10.0, 12.0, "long", None)) == "GAP"
    bad = _mech_row(12.0, None, 12.0, "long", 2.0)
    assert er.is_mech(bad) == "GAP"


def test_proof_before_arm_strictly_after():
    assert er.proof_before_arm(100, 90) == "True"   # armed after proof
    assert er.proof_before_arm(100, 100) == "False"  # same bar = before/at
    assert er.proof_before_arm(90, 100) == "False"
    assert er.proof_before_arm(None, 100) == ""
    assert er.proof_before_arm(100, None) == ""


def test_pct_and_dist_summary():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert er.pct(vals, 0.0) == 1.0
    assert er.pct(vals, 1.0) == 5.0
    assert er.pct(vals, 0.5) == 3.0
    assert er.pct([], 0.5) is None
    d = er.dist_summary(vals)
    assert d["n"] == 5
    assert d["median"] == 3.0
    assert d["p25"] == 2.0
    assert d["p75"] == 4.0
    assert er.dist_summary([])["median"] is None


def test_classify_family_frozen_branches():
    # completeness gate
    assert er.classify_family(0.9, 0.1, 0.5) == "INCONCLUSIVE"
    assert er.classify_family(0.9, 0.1, None) == "INCONCLUSIVE"
    # both-shares rule
    assert er.classify_family(0.30, 0.25, 1.0) == "BOTH"
    # tie margin
    assert er.classify_family(0.26, 0.22, 1.0) == "BOTH"
    # dominance
    assert er.classify_family(0.87, 0.05, 1.0) == "MECHANICAL"
    assert er.classify_family(0.05, 0.12, 1.0) == "LIFECYCLE"
    # no mass
    assert er.classify_family(0.05, 0.04, 1.0) == "INCONCLUSIVE"
    # missing shares
    assert er.classify_family(None, 0.5, 1.0) == "INCONCLUSIVE"


def test_share_le_and_strata():
    assert er.share_le([], 1.0) is None
    assert er.share_le([0.5, 1.0, 2.0], 1.0) == 2 / 3  # inclusive at 1.0
    rows = [{"k": "a", "g": "2.0"}, {"k": "a", "g": "0.5"},
            {"k": "b", "g": ""}, {"k": "", "g": "1.0"}]
    out = er.strata(rows, "k", "g")
    assert out["a"]["n"] == 2 and out["a"]["n_usable"] == 2
    assert abs(out["a"]["median_gap_atr"] - 1.25) < 1e-9
    assert out["a"]["pct_le_1"] == 0.5
    assert out["b"]["n_usable"] == 0 and out["b"]["pct_le_1"] is None
    assert er.share([], lambda r: True) is None


def test_p2_flag_exact_conditions():
    base = {"population": "1", "data_gap": "False",
            "r1_thesis": "PASS", "r2_proof": "PASS",
            "r3_timing": "PASS", "r4_location": "FAIL"}
    assert er.p2_flag(base) == "True"          # R4-only failure
    for rule in ("r1_thesis", "r2_proof", "r3_timing"):
        row = dict(base, **{rule: "FAIL"})
        assert er.p2_flag(row) == "False"      # not an R4-ONLY failure
    assert er.p2_flag(dict(base, population="2")) == "False"
    assert er.p2_flag(dict(base, data_gap="True")) == "False"
    assert er.p2_flag(dict(base, r4_location="PASS")) == "False"
    assert er.p2_flag(dict(base, r4_location="GAP")) == "False"


def test_bool_parsing_and_row_fields_frozen():
    assert er._truthy("True") is True
    assert er._truthy("true") is True
    assert er._truthy("FALSE") is False
    assert er._truthy("") is False
    assert er._truthy(None) is False
    # the artifact schema never changes silently
    expected_start = ["episode_id", "population", "direction", "trigger"]
    assert er.ROW_FIELDS[:4] == expected_start
    assert "gap_atr_proof" in er.ROW_FIELDS
    assert "gap_atr_proof_shiftedframe" in er.ROW_FIELDS


def test_radius_hypotheses_frozen_and_bounded():
    assert len(er.HYPOTHESES) <= 5
    for hyp in er.HYPOTHESES:
        for key in ("claim", "support", "refute",
                    "NOT implemented in this task"):
            assert key in hyp
        assert hyp["NOT implemented in this task"] is True


def test_study_constants_pinned():
    from unittest import mock
    import reactive_admission_measure as ram
    assert er.EDGE_TOL == 1e-6
    assert er.GAP_ATR_NEAR == 1.0
    assert er.COMPLETABLE_MIN == 0.70
    assert er.BOTH_SHARE == 0.20
    assert er.TIE_MARGIN == 0.05
    assert er.NO_MASS_SHARE == 0.10
    assert er.EXPECTED_P0 == 10
    assert er.EXPECTED_P1 == 268
    assert er.M3_PUBLISHED_R3_COUNT == 58   # citation only
    assert er.M4_PUBLISHED_R1_COUNT == 64   # cross-check target
    assert er.OUT_DIR.name == "entry_representation"
    assert er.BANNER.startswith("DIAGNOSTIC")
    # the study must reuse the parent measure's frame constant, not assume
    assert er.EXPECTED_WARMUP_OFFSET_SOURCE == ram.EXPECTED_WARMUP_OFFSET
    assert ram.EXPECTED_WARMUP_OFFSET == 6018
