"""ESSENCE contract v1 slice tests — signed-rule unit + integration battery.

ESSENCE V1 SLICE — NOT FULL COMPLEX REWRITE.

Covers: §2 zone sweep vs breakout · §3 set-C allow-list + the ending-diagonal
confirm (band / terminal-expiry / first-reclaim) · §4 LIMIT resting window ·
§5 signed 2–5 pip SL band · §6 macro-target + hard 1:5 gate · PureRunner BE
per-trade latch + conservative ordering · same-bar entry+SL → SL wins ·
isolation battery (no essence references outside the parallel package; no
essence names in locked_constants; COMPLEX imports untouched).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from smc.config.locked_constants import (
    M1_EXPIRY_BARS,
    M8_MIN_RR,
    M8_SL_MAX_PIPS,
    M8_SL_MIN_PIPS,
    PURE_RUNNER_BE_ATR,
    PURE_RUNNER_BE_BUFFER_ATR,
)
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.core.swing import Swing
from smc.core.zone import Zone
from smc.config.timeframe import Timeframe
from smc.detection.structural_swing_detector import detect_swings
from smc.essence import (
    ESSENCE_BE_ATR,
    ESSENCE_BE_BUFFER_ATR,
    ESSENCE_CONFIRM_KINDS,
    ESSENCE_LIMIT_EXPIRY_BARS,
    ESSENCE_MIN_RR,
    ESSENCE_SL_MAX_PIPS,
    ESSENCE_SL_MIN_PIPS,
)
from smc.essence.rules import (
    confirm_kind_allowed,
    essence_stop,
    essence_target,
    find_ed_confirm,
    is_zone_violation,
    is_zone_sweep,
    m1_atr_series,
    risk_reward,
    rr_gate_ok,
)
from smc.essence.runner import EssenceZoneFeed, StaticZoneFeed, run_essence_v1

T0 = datetime(2025, 6, 1, tzinfo=timezone.utc)


def _bar(minute: int, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(timestamp=T0 + timedelta(minutes=minute), open=o, high=h,
                  low=l, close=c, timeframe=Timeframe.M1)


# --------------------------------------------------------------------------- #
# The fully-specified integration path (numbers AS_INET in the docstring).
# Zone A demand LONG [100.00, 100.20]; zone B supply SHORT [102.50, 102.70].
# --------------------------------------------------------------------------- #
def _drama_bars() -> list[Candle]:
    bars: list[Candle] = []
    for i in range(10):                                   # 0..9 warm-up flat
        bars.append(_bar(i, 100.58, 100.68, 100.48, 100.58))
    bars += [
        _bar(10, 100.58, 100.60, 100.40, 100.44),   # w1 low 100.40
        _bar(11, 100.44, 100.46, 100.42, 100.46),
        _bar(12, 100.46, 100.48, 100.43, 100.48),
        _bar(13, 100.48, 100.50, 100.44, 100.50),
        _bar(14, 100.50, 100.55, 100.48, 100.50),   # w2 high 100.55
        _bar(15, 100.50, 100.52, 100.47, 100.48),
        _bar(16, 100.36, 100.38, 100.32, 100.34),
        _bar(17, 100.30, 100.33, 100.28, 100.31),
        _bar(18, 100.30, 100.31, 100.26, 100.29),   # w3 low 100.26
        _bar(19, 100.29, 100.32, 100.28, 100.31),
        _bar(20, 100.31, 100.35, 100.30, 100.34),
        _bar(21, 100.34, 100.40, 100.33, 100.39),
        _bar(22, 100.39, 100.42, 100.38, 100.39),   # w4 high 100.42
        _bar(23, 100.39, 100.40, 100.36, 100.37),
        _bar(24, 100.37, 100.38, 100.31, 100.32),
        _bar(25, 100.32, 100.33, 100.22, 100.23),
        _bar(26, 100.23, 100.24, 99.95, 100.05),    # w5 low + §2 sweep
        _bar(27, 100.05, 100.10, 100.00, 100.03),
        _bar(28, 100.03, 100.11, 100.01, 100.04),
        _bar(29, 100.04, 100.16, 100.03, 100.15),   # ED reclaim → LIMIT placed
        _bar(30, 100.15, 100.30, 100.05, 100.10),   # touch → filled at 100.12
        _bar(31, 100.10, 100.40, 100.09, 100.30),   # BE probe bar (1R move)
        _bar(32, 100.30, 100.34, 100.10, 100.12),   # stopped at the BE level
    ]
    for i in range(33, 41):                               # flat tail
        bars.append(_bar(i, 100.12, 100.14, 100.10, 100.12))
    return bars


_ZONE_A = Zone(top=100.20, bottom=100.00, direction=Direction.LONG,
               timeframe=Timeframe.H4)
_ZONE_B = Zone(top=102.70, bottom=102.50, direction=Direction.SHORT,
               timeframe=Timeframe.H4)


def _static_feed() -> StaticZoneFeed:
    from smc.essence.types import EssenceZoneEntry
    a = EssenceZoneEntry(poi_id="zA", detection_tf=Timeframe.H4, zone=_ZONE_A,
                         kind="demand_supply", valid_from_ts=T0,
                         bottom=_ZONE_A.bottom, top=_ZONE_A.top)
    b = EssenceZoneEntry(poi_id="zB", detection_tf=Timeframe.H4, zone=_ZONE_B,
                         kind="demand_supply", valid_from_ts=T0,
                         bottom=_ZONE_B.bottom, top=_ZONE_B.top)
    return StaticZoneFeed([a, b])


def test_swing_path_yields_exactly_the_five_diagonal_swings():
    bars = _drama_bars()
    swings = detect_swings(bars, Timeframe.M1)
    got = [(s.candle_index, s.level, s.is_high) for s in swings]
    # first FIVE swings are the diagonal chain; the BE probe bar (high 100.40)
    # forms one extra late swing at 31 — after the confirm (zone already busy)
    assert got[:5] == [
        (10, 100.40, False),
        (14, 100.55, True),
        (18, 100.26, False),
        (22, 100.42, True),
        (26, 99.95, False),
    ], got


# --------------------------------------------------------------------------- #
# §2 — sweep vs breakout
# --------------------------------------------------------------------------- #
def test_zone_sweep_long_wick_pierce_close_back_inside():
    bar = _bar(0, 100.10, 100.12, 99.95, 100.05)
    assert is_zone_sweep(bar, _ZONE_A) is True


def test_zone_close_through_is_breakout_not_sweep():
    bar = _bar(0, 100.10, 100.12, 99.95, 99.90)      # LOW pierces, CLOSE below
    assert is_zone_sweep(bar, _ZONE_A) is False
    assert is_zone_violation(bar, _ZONE_A) is True


def test_zone_sweep_short_mirrored():
    bar = _bar(0, 102.60, 102.75, 102.60, 102.65)    # HIGH pierces, CLOSE below
    assert is_zone_sweep(bar, _ZONE_B) is True
    bar_bad = _bar(0, 102.60, 102.75, 102.60, 102.80)  # closes ABOVE top
    assert is_zone_sweep(bar_bad, _ZONE_B) is False
    assert is_zone_violation(bar_bad, _ZONE_B) is True


# --------------------------------------------------------------------------- #
# §3 — signed set C allow-list + ending-diagonal confirm
# --------------------------------------------------------------------------- #
def test_confirm_allow_list_is_set_c_primary_only():
    assert confirm_kind_allowed("c_ending_diagonal") is True
    for not_in_v1 in (
        "b_leading_diagonal",        # B — leading diagonal: signed OUT
        "e_rsi_divergence",          # E — RSI divergence: signed OUT
        "a_choch",                   # in the signed SET but unwired in this slice
        "f_bos_ob",                  # in the signed SET but unwired in this slice
        "d_two_bar",                 # in the signed SET but unwired in this slice
        "dumb_mid_reclaim",          # DUMB's mid-cross: banned as a confirm
    ):
        assert confirm_kind_allowed(not_in_v1) is False


def test_essence_constants_wire_the_signed_locked_values():
    assert ESSENCE_SL_MIN_PIPS == M8_SL_MIN_PIPS == 2.0
    assert ESSENCE_SL_MAX_PIPS == M8_SL_MAX_PIPS == 5.0
    assert ESSENCE_MIN_RR == M8_MIN_RR == 5.0
    assert ESSENCE_LIMIT_EXPIRY_BARS == M1_EXPIRY_BARS == 30
    assert ESSENCE_BE_ATR == PURE_RUNNER_BE_ATR == 1.0
    assert ESSENCE_BE_BUFFER_ATR == PURE_RUNNER_BE_BUFFER_ATR == 0.10


def _chain_swings(bars: list[Candle]) -> list[Swing]:
    return detect_swings(bars, Timeframe.M1)


def test_ed_confirm_confirms_on_first_reclaim():
    bars = _drama_bars()
    swings = _chain_swings(bars)
    atr = m1_atr_series(bars)
    cand = find_ed_confirm(_ZONE_A, 29, bars, swings, atr[29])
    assert cand is not None
    assert cand.confirm_idx == 29
    assert cand.boundary == pytest.approx(100.12)
    assert cand.terminal_level == pytest.approx(99.95)
    # boundary strictly inside the demand zone (§4 gate prerequisite)
    assert _ZONE_A.contains(cand.boundary)
    # no earlier reclaim close between terminal+1 and the confirm bar
    assert all(b.close <= cand.boundary for b in bars[27:29])


def test_ed_confirm_rejects_when_terminal_outside_zone_band():
    bars = _drama_bars()
    tight = Zone(top=100.20, bottom=100.19, direction=Direction.LONG,
                 timeframe=Timeframe.H4)                 # excludes 99.95 even +ATR
    swings = _chain_swings(bars)
    assert find_ed_confirm(tight, 29, bars, swings, m1_atr_series(bars)[29]) is None


def test_ed_confirm_rejects_stale_terminal():
    bars = _drama_bars()                                 # valid confirm at 29
    swings = _chain_swings(bars)
    atr30 = m1_atr_series(bars)[30]
    # one bar past the terminal window (confirm bar 30 > terminal 26 + 3)
    bars = bars[:31] + [_bar(31, 100.15, 100.30, 100.13, 100.17)]
    assert find_ed_confirm(_ZONE_A, 30, bars, _chain_swings(bars), atr30) is None
    late_bars = bars + [_bar(40, 100.15, 100.30, 100.13, 100.17) for _ in range(10)]
    late_bars = late_bars[:41]
    late_bars[40] = _bar(40, 100.15, 100.30, 100.13, 100.17)
    assert find_ed_confirm(_ZONE_A, 40, late_bars, _chain_swings(late_bars),
                           m1_atr_series(late_bars)[40]) is None


def test_ed_confirm_rejects_earlier_reclaim():
    bars = _drama_bars()
    bars[27] = _bar(27, 100.05, 100.10, 100.00, 100.13)   # early reclaim close
    swings = _chain_swings(bars)
    assert find_ed_confirm(_ZONE_A, 29, bars, swings, m1_atr_series(bars)[29]) is None


# --------------------------------------------------------------------------- #
# §5 — signed SL band · §6 target + hard gate
# --------------------------------------------------------------------------- #
def test_essence_stop_is_band_floor_beyond_m1_structure():
    sl_long, pips_long = essence_stop(Direction.LONG, 123.45)
    sl_short, pips_short = essence_stop(Direction.SHORT, 123.45)
    assert pips_long == pips_short == 2.0
    assert sl_long == pytest.approx(123.45 - 0.20)
    assert sl_short == pytest.approx(123.45 + 0.20)


def test_essence_target_picks_nearest_opposite_structure_and_skips_others():
    refs = [
        (102.50, 102.70, Direction.SHORT),   # usable for LONG
        (101.00, 101.10, Direction.SHORT),   # nearer — must win
        (103.00, 103.10, Direction.LONG),    # same direction — ignored
        (100.05, 100.15, Direction.SHORT),   # near edge BELOW entry — unusable
    ]
    target, ref = essence_target(refs, Direction.LONG, 100.12)
    assert target == pytest.approx(101.00)
    assert ref == "opposite-zone:low"
    assert essence_target(refs[:1], Direction.SHORT, 102.60) == (None, None)


def test_rr_gate_is_hard_min_1x5():
    assert risk_reward(Direction.LONG, 100.12, 99.75, 102.50) == pytest.approx(2.38 / 0.37)
    assert rr_gate_ok(5.0) is True
    assert rr_gate_ok(4.999) is False


# --------------------------------------------------------------------------- #
# Integration — one trade end-to-end on the synthetic M1 path
# --------------------------------------------------------------------------- #
def test_run_opens_and_manages_one_trade_end_to_end():
    bars = _drama_bars()
    trades, stats = run_essence_v1(bars, None, zone_feed=_static_feed())

    assert stats.n_setups_swept == 1
    assert stats.n_confirmed == 1
    assert stats.n_limits_placed == 1
    assert stats.n_filled == 1
    assert stats.n_be_moves == 1
    assert stats.n_trades == len(trades) == 1
    assert stats.exits_by_kind == {"stop_loss": 1}
    t = trades[0]

    # identity for expert stage scoring
    assert t.detection_tf is Timeframe.H4
    assert t.zone_kind == "demand_supply"
    assert t.direction is Direction.LONG
    assert t.zone == (_ZONE_A.bottom, _ZONE_A.top)
    assert t.confirm_kind == "c_ending_diagonal"
    assert t.entry_level == pytest.approx(100.12)      # the ED boundary
    assert t.entry_price == pytest.approx(100.12)      # touch = limit (locked)

    # §5 — stop beyond the M1 structure inside the signed band
    assert t.sl_pips_buffer == 2.0
    assert t.r_stop == pytest.approx(0.37)

    # §6 — macro target + planned RR ≥ 1:5
    assert t.tp_price == pytest.approx(102.50)
    assert t.target_ref[1] == pytest.approx(102.50)
    assert t.rr_planned >= 5.0

    # §6 — PureRunner BE applied, then stopped at the BE level
    assert t.be_applied is True
    atr = m1_atr_series(bars)
    be_price = 100.12 + ESSENCE_BE_BUFFER_ATR * atr[31]
    assert t.exit_price == pytest.approx(be_price)
    assert t.pnl == pytest.approx(be_price - 100.12)
    assert t.close_kind == "stop_loss"


def test_same_bar_entry_and_sl_stops_out_at_placement_brackets():
    bars = _drama_bars()
    # touch the 100.12 limit AND the 99.75 stop on the fill bar (close stays
    # inside the zone so the breakout-cancel cannot pre-empt the fill)
    bars[30] = _bar(30, 100.15, 100.30, 99.70, 100.02)
    trades, stats = run_essence_v1(bars, None, zone_feed=_static_feed())
    assert stats.n_filled == 1
    assert stats.n_be_moves == 0
    t = trades[0]
    assert t.close_kind == "stop_loss"
    assert t.exit_price == pytest.approx(99.75)          # ORIGINAL placement stop
    assert t.be_applied is False                          # no same-bar rescue


def test_be_never_rescues_on_its_own_bar():
    bars = _drama_bars()
    bars[31] = _bar(31, 100.10, 100.45, 99.70, 99.72)    # BE trigger + stop hit
    trades, stats = run_essence_v1(bars, None, zone_feed=_static_feed())
    assert stats.n_be_moves == 0
    t = trades[0]
    assert t.close_kind == "stop_loss"
    assert t.exit_price == pytest.approx(99.75)
    assert t.be_applied is False
    assert t.pnl == pytest.approx(99.75 - 100.12)


def test_unfilled_limit_expires_after_m1_resting_window():
    bars = _drama_bars()[:30]                            # through confirm bar 29
    bars += [_bar(i, 100.15, 100.30, 100.13, 100.17)     # 30..59: never touches
             for i in range(30, 60)]
    bars.append(_bar(60, 100.15, 100.30, 100.13, 100.17))  # expiry bar
    trades, stats = run_essence_v1(bars, None, zone_feed=_static_feed())
    assert stats.n_limits_placed == 1
    assert stats.n_limits_expired == 1
    assert stats.n_filled == 0
    assert stats.n_trades == 0


def test_zone_violation_cancels_resting_limit():
    bars = _drama_bars()[:30]
    bars += [
        _bar(30, 100.15, 100.30, 100.13, 100.17),
        _bar(31, 100.15, 100.30, 99.95, 99.90),          # close-through breakout
        _bar(32, 100.05, 100.20, 100.01, 100.10),
    ]
    trades, stats = run_essence_v1(bars, None, zone_feed=_static_feed())
    assert stats.n_limits_cancelled_breakout == 1
    assert stats.n_filled == 0


def test_runner_is_deterministic_over_identical_inputs():
    trades_a, stats_a = run_essence_v1(_drama_bars(), None, zone_feed=_static_feed())
    trades_b, stats_b = run_essence_v1(_drama_bars(), None, zone_feed=_static_feed())
    fa = [(t.ticket, t.entry_idx, t.exit_idx, t.exit_price, t.close_kind) for t in trades_a]
    fb = [(t.ticket, t.entry_idx, t.exit_idx, t.exit_price, t.close_kind) for t in trades_b]
    assert fa == fb
    assert stats_a.n_trades == stats_b.n_trades


def test_feeds_update_no_series_and_release_in_order():
    feed = EssenceZoneFeed({})
    step = feed.update(T0)
    assert step.activated == []
    assert step.removed_poi_ids == []
    assert feed.active() == []

    from smc.essence.types import EssenceZoneEntry
    a = EssenceZoneEntry(poi_id="zA", detection_tf=Timeframe.H4, zone=_ZONE_A,
                         kind="demand_supply", valid_from_ts=T0,
                         bottom=_ZONE_A.bottom, top=_ZONE_A.top)
    b = EssenceZoneEntry(poi_id="zB", detection_tf=Timeframe.H4, zone=_ZONE_B,
                         kind="demand_supply", valid_from_ts=T0 + timedelta(minutes=5),
                         bottom=_ZONE_B.bottom, top=_ZONE_B.top)
    static = StaticZoneFeed([b, a])            # out of order on purpose
    late = T0 + timedelta(minutes=1)
    step1 = static.update(late)
    assert [e.poi_id for e in step1.activated] == ["zA"]
    step2 = static.update(T0 + timedelta(minutes=6))
    assert [e.poi_id for e in step2.activated] == ["zB"]
    assert sorted(e.poi_id for e in static.active()) == ["zA", "zB"]


# --------------------------------------------------------------------------- #
# Isolation battery — the parallel path must not poison anything
# --------------------------------------------------------------------------- #
from pathlib import Path

_SMC_ROOT = (Path(__file__).resolve().parents[1] / "smc").resolve()
assert _SMC_ROOT.is_dir()
_SKIP_DIRS = {"essence", "dumb", "__pycache__"}


def _smc_files():
    for p in sorted(_SMC_ROOT.rglob("*.py")):
        rel = p.relative_to(_SMC_ROOT)
        if rel.parts and rel.parts[0] in _SKIP_DIRS:
            continue
        if "__pycache__" in rel.parts:
            continue
        yield p, rel


def test_no_essence_reference_outside_essence_and_dumb_packages():
    offenders = []
    for p, rel in _smc_files():
        text = p.read_text(encoding="utf-8", errors="replace")
        if "essence" in text.lower():
            offenders.append(str(rel))
    assert offenders == [], "essence leaked into these modules"


def test_essence_names_absent_from_locked_constants():
    text = (_SMC_ROOT / "config" / "locked_constants.py").read_text(
        encoding="utf-8", errors="replace")
    assert "ESSENCE" not in text, "essence-owned constants leaked into the lock"
    assert locked_constants_diff_empty(text)


def locked_constants_diff_empty(text: str) -> bool:
    """The frozen trading constants this wiring relies on still carry the
    signed values (guards against a later silent edit of the lock)."""
    for expected in (
        "M8_MIN_RR = 5.0",
        "M8_SL_MIN_PIPS = 2.0",
        "M8_SL_MAX_PIPS = 5.0",
        "M1_EXPIRY_BARS = 30",
        "PURE_RUNNER_BE_ATR = 1.0",
        "PURE_RUNNER_BE_BUFFER_ATR = 0.10",
    ):
        assert expected in text, f"locked value changed: {expected}"
    return True


def test_complex_smoke_imports_untouched_by_essence():
    from smc.orchestration.engine import PipelineEngine
    from smc.triggers.trigger_router import TriggerRouter

    assert PipelineEngine is not None
    assert TriggerRouter is not None


def test_essence_module_never_imports_dumb():
    essence_files = list((_SMC_ROOT / "essence").rglob("*.py"))
    offenders = [str(p.relative_to(_SMC_ROOT)) for p in essence_files
                 if "smc.dumb" in p.read_text(encoding="utf-8", errors="replace")]
    assert offenders == [], "essence must be self-contained (no dumb dependency)"
