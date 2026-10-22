"""DUMB FLOWCHART V1 tests — rules, integration, COMPLEX isolation.

DUMB IMPLEMENTATION — DIAGNOSTIC — NOT EDGE.

These tests pin the six locked rules (R1–R6) on synthetic candles and prove
the isolation contract: nothing outside ``smc/dumb/**`` references DUMB, the
DUMB constants live in ``smc.dumb.constants`` (not ``locked_constants``), and
the COMPLEX decision-spine modules still construct and default-build cleanly.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.core.zone import Zone
from smc.dumb import (
    DUMB_ATR_PERIOD,
    DUMB_CONFIRM_MAX_BARS,
    DUMB_SL_BUFFER_ATR,
    DUMB_TP_R_MULTIPLE,
    compute_sl_tp,
    is_confirm,
    is_expired,
    is_sweep,
)
from smc.dumb.runner import M8LibraryZoneFeed, StaticZoneFeed, run_dumb_flowchart

TZ = timezone.utc
BASE = datetime(2025, 1, 1, tzinfo=TZ)

DEMAND = Zone(top=101.0, bottom=100.0, direction=Direction.LONG,
              timeframe=Timeframe.D1)


def C(idx: int, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(BASE + timedelta(minutes=5 * idx), o, h, l, c)


def flat(range_size: float = 0.8) -> tuple[float, float, float, float]:
    lo = 100.5 - range_size / 2.0
    hi = 100.5 + range_size / 2.0
    return (100.5, hi, lo, 100.5)


# ---------------------------------------------------------------------- #
# R2 — sweep, boundary cases (locked strict inequalities)
# ---------------------------------------------------------------------- #

def test_sweep_long_true() -> None:
    bar = C(0, 100.5, 100.7, 99.9, 100.3)
    assert is_sweep(bar, DEMAND) is True


def test_sweep_long_false_when_close_back_through() -> None:
    bar = C(0, 100.5, 100.7, 99.9, 99.8)
    assert is_sweep(bar, DEMAND) is False


def test_sweep_long_false_touch_not_pierce() -> None:
    bar = C(0, 100.5, 100.6, 100.0, 100.3)
    assert is_sweep(bar, DEMAND) is False      # low == bottom: no pierce


def test_sweep_long_false_close_on_extreme() -> None:
    bar = C(0, 100.5, 100.7, 99.9, 100.0)
    assert is_sweep(bar, DEMAND) is False      # close == bottom: not inside


SUPPLY = Zone(top=101.0, bottom=100.0, direction=Direction.SHORT,
              timeframe=Timeframe.D1)


def test_sweep_short_true_and_boundaries() -> None:
    assert is_sweep(C(0, 100.5, 101.1, 100.4, 100.8), SUPPLY) is True
    assert is_sweep(C(0, 100.5, 101.0, 100.4, 100.8), SUPPLY) is False   # high == top
    assert is_sweep(C(0, 100.5, 101.1, 100.4, 101.0), SUPPLY) is False   # close == top
    assert is_sweep(C(0, 100.5, 101.1, 100.4, 101.2), SUPPLY) is False   # genuine breakout


# ---------------------------------------------------------------------- #
# R3 — confirm mid-cross + expiry window
# ---------------------------------------------------------------------- #

def test_confirm_long_strict_mid_cross() -> None:
    assert is_confirm(C(0, 100.2, 100.6, 100.1, 100.6), DEMAND) is True
    assert is_confirm(C(0, 100.2, 100.5, 100.1, 100.5), DEMAND) is False  # == mid


def test_confirm_short_strict_mid_cross() -> None:
    assert is_confirm(C(0, 100.2, 100.3, 99.4, 100.2), SUPPLY) is True
    assert is_confirm(C(0, 100.2, 100.3, 99.4, 100.5), SUPPLY) is False


def test_expiry_window_is_inclusive_of_bar_12() -> None:
    assert is_expired(0, DUMB_CONFIRM_MAX_BARS) is False
    assert is_expired(0, DUMB_CONFIRM_MAX_BARS + 1) is True


# ---------------------------------------------------------------------- #
# R5 + R6 — SL / TP arithmetic (fixed 2R)
# ---------------------------------------------------------------------- #

def test_sl_tp_long() -> None:
    sl, tp = compute_sl_tp(Direction.LONG, 100.55, 99.5, 1.0)
    assert sl == pytest.approx(99.5 - 0.10)
    assert (100.55 - sl) == pytest.approx(1.15)
    assert tp == pytest.approx(100.55 + 2.0 * 1.15)          # 103.85


def test_sl_tp_short() -> None:
    sl, tp = compute_sl_tp(Direction.SHORT, 99.45, 100.5, 1.0)
    assert sl == pytest.approx(100.5 + 0.10)
    assert (sl - 99.45) == pytest.approx(1.15)
    assert tp == pytest.approx(99.45 - 2.0 * 1.15)           # 97.15


def test_sl_tp_rejects_non_positive_r() -> None:
    with pytest.raises(ValueError):
        compute_sl_tp(Direction.LONG, 99.0, 99.5, 1.0)





# ---------------------------------------------------------------------- #
# Runner — integration on a synthetic zone + M5 path
# ---------------------------------------------------------------------- #

def _feed(zone: Zone, valid_from_idx: int = 0) -> StaticZoneFeed:
    return StaticZoneFeed([("dumb-D1-test-000001", Timeframe.D1, zone,
                            BASE + timedelta(minutes=5 * valid_from_idx))])


def _trap_path() -> list[Candle]:
    """Warm-up (flat 0.8-range bars) → sweep bar → confirm bar → exit bar.

    Every bar's true range is exactly 0.8, so Wilder ATR(14) is pinned at
    0.8 from bar index 13 on — SL/TP values are hand-assertable exactly.
    """
    bars = [C(i, *flat()) for i in range(20)]
    bars.append(C(20, 100.5, 100.7, 99.9, 100.3))   # sweep (low 99.9, close 100.3)
    bars.append(C(21, 100.5, 100.9, 100.1, 100.9))  # confirm (close 100.9 > mid)
    bars.extend(C(i, *flat()) for i in range(22, 23))
    bars.append(C(23, 103.0, 103.5, 100.6, 103.0))  # exit bar (high >= TP)
    bars.append(C(24, *flat()))
    return bars


def test_integration_single_trade_expected_brackets() -> None:
    trades, stats = run_dumb_flowchart(_trap_path(), None,
                                       zone_feed=_feed(DEMAND))
    assert stats.n_setups_swept == 1
    assert stats.n_confirmed == 1
    assert stats.n_entry_skipped_outside_zone == 0
    assert len(trades) == 1
    t = trades[0]
    # entry 100.90; SL = 99.9 - 0.10 * 0.8 = 99.82; 1R = 1.08; TP = 103.06
    assert t.entry_price == pytest.approx(100.90)
    assert t.sl_price == pytest.approx(99.9 - DUMB_SL_BUFFER_ATR * 0.8)
    assert t.r_stop == pytest.approx(t.entry_price - t.sl_price)
    assert t.tp_price == pytest.approx(t.entry_price + DUMB_TP_R_MULTIPLE * t.r_stop)
    assert t.close_kind == "take_profit"
    assert t.bars_held == 2
    assert t.pnl == pytest.approx(DUMB_TP_R_MULTIPLE * t.r_stop)
    # the sweep bar must be the anchor (R5), not the confirm bar
    assert t.zone == (100.0, 101.0)


def test_integration_same_bar_sl_wins_over_tp() -> None:
    bars = [C(i, *flat()) for i in range(20)]
    bars.append(C(20, 100.5, 100.7, 99.9, 100.3))
    bars.append(C(21, 100.5, 100.9, 100.1, 100.9))
    # both brackets inside one bar → SL wins (locked conservative rule)
    bars.append(C(22, 101.5, 103.5, 99.7, 101.0))
    bars.append(C(23, *flat()))
    trades, stats = run_dumb_flowchart(bars, None, zone_feed=_feed(DEMAND))
    assert len(trades) == 1
    t = trades[0]
    assert t.close_kind == "stop_loss"
    assert t.exit_price == pytest.approx(t.sl_price)
    assert t.pnl == pytest.approx(t.sl_price - t.entry_price)
    assert t.bars_held == 1


def test_entry_rejected_when_confirm_close_outside_zone() -> None:
    bars = [C(i, *flat()) for i in range(20)]
    bars.append(C(20, 100.5, 100.7, 99.9, 100.3))    # sweep
    bars.append(C(21, 101.0, 101.6, 100.8, 101.5))   # confirm close ABOVE zone top
    bars.extend(C(i, *flat()) for i in range(22, 30))
    trades, stats = run_dumb_flowchart(bars, None, zone_feed=_feed(DEMAND))
    assert stats.n_setups_swept == 1
    assert stats.n_confirmed == 1
    assert stats.n_entry_skipped_outside_zone == 1
    assert stats.n_trades == 0
    # and the episode was consumed: no later bar re-opens it (no chase)
    assert all(t.close_kind != "take_profit" for t in trades)


def test_setup_expires_then_zone_rearms() -> None:
    bars = [C(i, *flat()) for i in range(20)]
    bars.append(C(20, 100.5, 100.7, 99.9, 100.3))    # sweep #1
    bars.extend(C(i, *flat()) for i in range(21, 33))  # waits (close == mid, no confirm)
    bars.append(C(33, *flat()))                                   # expiry fires here
    bars.append(C(34, 100.5, 100.6, 99.8, 100.2))
    bars.append(C(35, 100.5, 100.9, 100.1, 100.9))
    bars.append(C(36, 103.0, 103.5, 100.6, 103.0))
    bars.append(C(37, *flat()))
    trades, stats = run_dumb_flowchart(bars, None, zone_feed=_feed(DEMAND))
    assert stats.n_expired == 1
    assert stats.n_setups_swept == 2          # expired anchor frees the zone
    assert len(trades) == 1
    # new anchor = the re-arm sweep extreme (99.8), not the first sweep (99.9)
    t = trades[0]
    assert t.sl_price == pytest.approx(99.8 - DUMB_SL_BUFFER_ATR * 0.8)
    assert t.close_kind == "take_profit"


# ---------------------------------------------------------------------- #
# Isolation — COMPLEX untouched, DUMB constants DUMB-owned
# ---------------------------------------------------------------------- #

def test_no_dumb_reference_outside_smc_dumb() -> None:
    smc_root = Path(__file__).resolve().parents[1] / "smc"
    offenders = []
    for path in smc_root.rglob("*.py"):
        rel = path.relative_to(smc_root)
        if rel.parts[0] == "dumb":
            continue
        text = path.read_text(encoding="utf-8")
        if ("smc.dumb" in text or "from smc import dumb" in text
                or "smc/dumb" in text):
            offenders.append(str(rel))
    assert offenders == []


def test_dumb_constants_not_in_locked_constants() -> None:
    import smc.config.locked_constants as locked

    for name in ("DUMB_CONFIRM_MAX_BARS", "DUMB_SL_BUFFER_ATR",
                 "DUMB_TP_R_MULTIPLE", "DUMB_ATR_PERIOD"):
        assert not hasattr(locked, name)
    assert DUMB_CONFIRM_MAX_BARS == 12
    assert DUMB_SL_BUFFER_ATR == 0.10
    assert DUMB_TP_R_MULTIPLE == 2.0
    assert DUMB_ATR_PERIOD == 14


def test_complex_decision_spine_still_constructs() -> None:
    from smc.orchestration.engine import PipelineEngine
    from smc.triggers.trigger_router import TriggerRouter, default_triggers

    engine = PipelineEngine()
    assert engine is not None
    router = TriggerRouter()
    assert len(default_triggers()) == 6
    assert router.matrix is not None


def test_m8_feed_still_reuses_product_scan() -> None:
    """The M8 library feed re-runs the product scan on honest prefixes and
    emits zones deterministically for a tiny HTF series."""
    stamps = [BASE + timedelta(hours=4 * (i + 1)) for i in range(6)]
    series = [Candle(stamps[i], 100.5, 100.9, 100.1, 100.5) for i in range(6)]
    feed = M8LibraryZoneFeed({Timeframe.H4: series})
    activated = feed.update(stamps[-1])
    assert isinstance(activated, list)
    assert feed.summary.n_htf_rescans >= 1
