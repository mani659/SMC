"""Near-miss counterfactual study — focused pure-helper tests (research).

Locks the frozen helpers of
``06_RESEARCH/scripts/near_miss_counterfactual.py``:

* fill/label semantics (touch = fill, SL before TP on the same bar) —
  cross-checked against the product's own ``smc.backtest.fill_model`` so
  the paper engine can never drift from the engine it measures;
* the frozen eligible-window rule (placement at runner step 6 -> the
  placement bar is never fill-eligible; §23/R8 lifetime bounds);
* label exclusivity, DATA_GAP discipline (never invent prices), the
  disclosed 100-bar secondary horizon, and the pre-registered
  kill-criteria verdict branches.

No series loading, no runner, no MT5, no threshold, no expectancy
assertion anywhere.  ``LOGIC_CHANGED: NO``.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_PACK_PATH = (Path(__file__).resolve().parents[2]
              / "06_RESEARCH" / "scripts" / "near_miss_counterfactual.py")


def _load_pack():
    spec = importlib.util.spec_from_file_location(
        "near_miss_counterfactual", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["near_miss_counterfactual"] = module
    spec.loader.exec_module(module)
    return module


nm = _load_pack()


def _bar(low: float, high: float, index: int = 0) -> dict:
    return {"timestamp": datetime(2025, 6, 1, tzinfo=timezone.utc)
            + timedelta(minutes=5 * index),
            "low": low, "high": high, "close": (low + high) / 2.0}


def _candle(low: float, high: float):
    """A real Candle for the fill_model cross-check (product semantics)."""
    from smc.config.timeframe import Timeframe
    from smc.core.candle import Candle
    return Candle(timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
                  open=(low + high) / 2.0, high=high, low=low,
                  close=(low + high) / 2.0, timeframe=Timeframe.M5)


def _route(**overrides) -> dict:
    route = {
        "route_id": "poi-000001:F@10",
        "arm": "blocked_r7_far",
        "direction": "long",
        "entry": 100.0,
        "sl": 90.0,
        "tp": 120.0,
        "original_sl": 90.0,
        "present_bar": 10,
        "rest_bars": 12,
    }
    route.update(overrides)
    return route


# ---------------------------------------------------------------------- #
# Frozen-fill-model agreement
# ---------------------------------------------------------------------- #
def test_limit_touch_matches_product_fill_model():
    from smc.backtest.fill_model import limit_filled
    from smc.core.enums import Direction

    cases = [(100.0, 99.0), (100.0, 100.0), (100.0, 101.0),
             (99.99, 99.98), (100.01, 100.02)]
    for limit, level in cases:
        long_bar = _candle(low=level, high=max(level, limit) + 1)
        assert nm.limit_touch("long", limit, long_bar.low, long_bar.high) \
            == limit_filled(Direction.LONG, limit, long_bar)
        short_bar = _candle(low=min(level, limit) - 1, high=level)
        assert nm.limit_touch("short", limit, short_bar.low, short_bar.high) \
            == limit_filled(Direction.SHORT, limit, short_bar)


def test_sl_and_tp_tags_match_product_fill_model():
    from smc.backtest.fill_model import sl_hit, tp_hit
    from smc.core.enums import Direction

    for limit, level in [(90.0, 89.5), (90.0, 90.0), (90.0, 91.0)]:
        bar = _candle(low=level, high=level + 5)
        assert nm.sl_tag("long", limit, bar.low, bar.high) \
            == sl_hit(Direction.LONG, limit, bar)
        assert nm.tp_tag("long", 200.0, bar.low, bar.high) \
            == tp_hit(Direction.LONG, 200.0, bar)
        assert nm.sl_tag("short", 95.0, bar.low, bar.high) \
            == sl_hit(Direction.SHORT, 95.0, bar)
        assert nm.tp_tag("short", 50.0, bar.low, bar.high) \
            == tp_hit(Direction.SHORT, 50.0, bar)


# ---------------------------------------------------------------------- #
# Eligible window (frozen runner order)
# ---------------------------------------------------------------------- #
def test_eligible_window_m5_default_lifetime():
    # §23 M5 = 12: an order placed on N is fill-eligible on N+1 .. N+10.
    assert nm.eligible_window(100, 12, 1000) == (101, 110)
    # R8 HTF/M8 = 48.
    assert nm.eligible_window(100, 48, 1000) == (101, 146)
    # H1 = 36.
    assert nm.eligible_window(100, 36, 1000) == (101, 134)


def test_eligible_window_clamps_and_can_be_empty():
    assert nm.eligible_window(98, 12, 100) == (99, 99)
    first, last = nm.eligible_window(99, 12, 100)
    assert last < first  # window ends at the series end (never invented)


def test_no_fill_on_the_placement_bar():
    bars = [_bar(101.0, 105.0, index) for index in range(20)]
    bars[10] = _bar(99.0, 105.0, 10)   # touches on the PLACEMENT bar only
    row = nm.simulate_route(_route(), bars)
    assert row["outcome"] == "EXPIRED_NO_FILL"
    assert row["fill_index"] is None


def test_first_eligible_bar_fills():
    bars = [_bar(101.0, 105.0, index) for index in range(20)]
    bars[11] = _bar(99.0, 105.0, 11)
    bars[12] = _bar(99.0, 121.0, 12)   # TP tagged, SL not
    row = nm.simulate_route(_route(), bars)
    assert row["outcome"] == "TP_HIT"
    assert row["fill_index"] == 11
    assert row["bars_to_fill"] == 1
    assert row["exit_index"] == 12
    assert row["bars_to_outcome"] == 1


def test_same_bar_sl_wins_over_tp():
    bars = [_bar(101.0, 105.0, index) for index in range(20)]
    bars[11] = _bar(85.0, 125.0, 11)   # both SL (90) and TP (120) inside range
    row = nm.simulate_route(_route(), bars)
    assert row["outcome"] == "SL_HIT"
    assert row["exit_index"] == 11


def test_sl_first_across_bars():
    bars = [_bar(101.0, 105.0, index) for index in range(20)]
    bars[11] = _bar(99.0, 106.0, 11)
    bars[12] = _bar(88.0, 121.0, 12)
    row = nm.simulate_route(_route(), bars)
    assert row["outcome"] == "SL_HIT"
    assert row["exit_index"] == 12


def test_sl_then_tp_research_flag():
    bars = [_bar(101.0, 105.0, index) for index in range(30)]
    bars[11] = _bar(95.0, 106.0, 11)    # fill
    bars[12] = _bar(85.0, 100.0, 12)    # SL
    bars[14] = _bar(100.0, 125.0, 14)   # TP later (after the stop)
    row = nm.simulate_route(_route(), bars)
    assert row["outcome"] == "SL_HIT"
    assert row["sl_then_tp"] is True


def test_mfe_mae_in_r_units_from_original_sl():
    bars = [_bar(101.0, 105.0, index) for index in range(30)]
    bars[11] = _bar(97.0, 110.0, 11)    # fill at 100, MFE +10, MAE -3
    bars[12] = _bar(99.0, 121.0, 12)    # TP
    row = nm.simulate_route(_route(), bars)
    assert row["outcome"] == "TP_HIT"
    # risk = |100 - 90| = 10; excursion runs fill bar (11) through exit (12):
    # MFE = max(highs) - entry = 121 - 100 = 21 -> 2.1 R; MAE = entry - 97
    # = 3 -> 0.3 R.
    assert row["mfe_r"] == 2.1
    assert row["mae_r"] == 0.3


def test_open_unresolved_is_never_folded_into_win_or_loss():
    bars = [_bar(99.5, 100.5, index) for index in range(20)]
    bars[11] = _bar(99.0, 101.0, 11)    # fill, then nothing ever tags SL or TP
    row = nm.simulate_route(_route(), bars)
    assert row["outcome"] == "OPEN_UNRESOLVED"
    assert row["fill_index"] == 11


def test_missing_geometry_is_data_gap_and_never_invented():
    for override in ({"tp": None}, {"entry": None}, {"sl": None},
                     {"present_bar": None}):
        row = nm.simulate_route(_route(**override),
                               [_bar(99.0, 105.0, i) for i in range(20)])
        assert row["outcome"] == "DATA_GAP", override


def test_truncated_series_is_data_gap():
    bars = [_bar(99.0, 105.0, index) for index in range(11)]
    row = nm.simulate_route(_route(present_bar=10), bars)
    assert row["outcome"] == "DATA_GAP"


def test_late_touch_is_recorded_but_never_fills_outside_the_lifetime():
    bars = [_bar(101.0, 105.0, index) for index in range(60)]
    bars[40] = _bar(95.0, 105.0, 40)    # touched long after the 12-bar life
    row = nm.simulate_route(_route(), bars)
    assert row["outcome"] == "EXPIRED_NO_FILL"
    assert row["touched_inside_lifetime"] is False
    assert row["touched_at_any_horizon"] is True
    assert row["late_touch_index"] == 40
    # the 12-bar lifetime ends on bar 20; the touch came 20 bars later
    assert row["bars_after_lifetime"] == 20


def test_closest_approach_is_non_negative_and_zero_only_when_touched():
    # LONG buy-limit 100: never touched -> smallest (low - limit)
    bars = [_bar(low, low + 5.0, index) for index, low in
            enumerate([102.0, 101.5, 103.0, 104.0])]
    assert nm.closest_approach("long", 100.0, bars, 0, 3) == 1.5
    # touched -> 0.0 (never negative)
    bars[2] = _bar(95.0, 105.0, 2)
    assert nm.closest_approach("long", 100.0, bars, 0, 3) == 0.0
    # SHORT sell-limit 100: price must rise to the limit, so the
    # distance is (limit - high) — smallest = 2.0 here (not the 3.5 bar)
    short_bars = [_bar(90.0, 98.0, 0), _bar(90.0, 96.5, 1)]
    assert nm.closest_approach("short", 100.0, short_bars, 0, 1) == 2.0
    # empty window -> None (never invented)
    assert nm.closest_approach("long", 100.0, bars, 5, 4) is None


def test_expired_outcome_records_the_closest_approach_texture():
    bars = [_bar(103.0, 105.0, index) for index in range(20)]
    bars[14] = _bar(100.9, 105.0, 14)   # 0.9 units away while live
    row = nm.simulate_route(_route(), bars)
    assert row["outcome"] == "EXPIRED_NO_FILL"
    assert row["min_distance_live"] == pytest.approx(0.9)


def test_extended_horizon_override_can_fill_what_the_lifetime_missed():
    bars = [_bar(101.0, 105.0, index) for index in range(200)]
    bars[40] = _bar(95.0, 105.0, 40)
    bars[41] = _bar(95.0, 125.0, 41)
    short = nm.simulate_route(_route(), bars)
    long_ = nm.simulate_route(_route(), bars,
                              horizon_bars=nm.EXTENDED_HORIZON_BARS)
    assert short["outcome"] == "EXPIRED_NO_FILL"
    assert long_["outcome"] == "TP_HIT"
    assert long_["rest_bars_used"] == nm.EXTENDED_HORIZON_BARS


def test_short_direction_semantics_are_mirrored():
    bars = [_bar(95.0, 99.0, index) for index in range(20)]
    bars[11] = _bar(95.0, 101.0, 11)     # SHORT sell-limit 100 touched
    bars[12] = _bar(79.0, 101.0, 12)     # SHORT target 80 tagged
    row = nm.simulate_route(_route(direction="short", entry=100.0, sl=110.0,
                                   tp=80.0, original_sl=110.0), bars)
    assert row["outcome"] == "TP_HIT"
    assert row["fill_index"] == 11


# ---------------------------------------------------------------------- #
# Arm classification + label exclusivity
# ---------------------------------------------------------------------- #
def test_classify_arm_priority_and_exclusivity():
    assert nm.classify_arm(placed=True, filled=True,
                           first_block="session") == "filled_control"
    assert nm.classify_arm(placed=True, filled=False,
                           first_block="skip_place_far_from_zone") \
        == "placed_unfilled"
    assert nm.classify_arm(placed=False, filled=False,
                           first_block="session") == "blocked_session"
    assert nm.classify_arm(placed=False, filled=False,
                           first_block="skip_place_far_from_zone") \
        == "blocked_r7_far"
    assert nm.classify_arm(placed=False, filled=False,
                           first_block="spread") == "blocked_other"
    assert nm.classify_arm(placed=False, filled=False,
                           first_block=None) == "blocked_other"
    assert set(nm.ARMS) == {"filled_control", "placed_unfilled",
                            "blocked_session", "blocked_r7_far",
                            "blocked_other"}


def test_every_outcome_label_is_exclusive_and_known():
    frozen = {"TP_HIT", "SL_HIT", "EXPIRED_NO_FILL", "DATA_GAP",
              "OPEN_UNRESOLVED"}
    for override, bars in (
            ({}, [_bar(99.0, 121.0, i) for i in range(20)]),
            ({}, [_bar(85.0, 105.0, i) for i in range(20)]),
            ({}, [_bar(101.0, 105.0, i) for i in range(20)]),
            ({"tp": None}, [_bar(99.0, 105.0, i) for i in range(20)]),
            ({}, [_bar(99.5, 101.0, i) for i in range(20)]),
    ):
        row = nm.simulate_route(_route(**override), bars)
        assert row["outcome"] in frozen


def test_outcome_mix_counts_sorted_and_zero_free():
    mix = nm.outcome_mix([{"outcome": "TP_HIT"}, {"outcome": "TP_HIT"},
                          {"outcome": "SL_HIT"}])
    assert mix == {"SL_HIT": 1, "TP_HIT": 2}


# ---------------------------------------------------------------------- #
# Pre-registered kill criteria
# ---------------------------------------------------------------------- #
def _rows(*labels):
    return [{"outcome": label} for label in labels]


def test_kill_criteria_no_untaken_is_inconclusive():
    verdict = nm.evaluate_kill_criteria(_rows("TP_HIT"), [])
    assert verdict["verdict"] == "INCONCLUSIVE"
    assert verdict["untaken_tp_hit_rate"] is None


def test_kill_criteria_zero_resolved_untaken_is_not_primary():
    verdict = nm.evaluate_kill_criteria(
        _rows("TP_HIT", "SL_HIT"),
        _rows("EXPIRED_NO_FILL", "EXPIRED_NO_FILL", "DATA_GAP"))
    assert verdict["verdict"] == "PLACEMENT_NOT_PRIMARY"
    assert verdict["n_resolved_untaken"] == 0
    assert verdict["untaken_expired_no_fill_rate"] == round(2 / 3, 6)


def test_kill_criteria_small_resolved_n_is_inconclusive():
    verdict = nm.evaluate_kill_criteria(
        _rows("SL_HIT", "SL_HIT"),
        _rows("TP_HIT", "TP_HIT", "SL_HIT", "SL_HIT"))  # 4 resolved < 5
    assert verdict["verdict"] == "INCONCLUSIVE"
    assert verdict["n_resolved_untaken"] == 4


def test_kill_criteria_higher_untaken_tp_rate_is_bottleneck_candidate():
    verdict = nm.evaluate_kill_criteria(
        _rows("SL_HIT", "SL_HIT", "TP_HIT", "SL_HIT"),
        _rows("TP_HIT", "TP_HIT", "TP_HIT", "SL_HIT", "SL_HIT"))
    assert verdict["verdict"] == "PLACEMENT_BOTTLENECK_CANDIDATE"
    assert verdict["tp_hit_rate_diff"] > 0


def test_kill_criteria_lower_or_equal_untaken_tp_rate_is_not_primary():
    verdict = nm.evaluate_kill_criteria(
        _rows("TP_HIT", "TP_HIT", "TP_HIT", "SL_HIT", "SL_HIT"),
        _rows("SL_HIT", "SL_HIT", "TP_HIT", "SL_HIT", "SL_HIT"))
    assert verdict["verdict"] == "PLACEMENT_NOT_PRIMARY"
    assert verdict["tp_hit_rate_diff"] <= 0


# ---------------------------------------------------------------------- #
# Governance locks
# ---------------------------------------------------------------------- #
def test_banner_and_logic_changed_lock():
    assert "NOT EDGE" in nm.BANNER
    assert nm.LOGIC_CHANGED == "NO"
