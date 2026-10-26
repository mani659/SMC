"""Fill/takeability study — focused pure-helper tests (research).

Locks the frozen helpers of ``06_RESEARCH/scripts/fill_takeability_study.py``:

* the fill-eligible window arithmetic (placement at runner step 6 ->
  placement bar never eligible; expiry at step 3 of a later bar; the
  ``placed+1 .. placed+rest-2`` convention, cross-checked against the
  product's own ``PendingOrderBook.expired_by_section23`` boundary);
* touch semantics cross-checked against ``smc.backtest.fill_model`` so the
  study can never drift from the engine it measures;
* mutually-exclusive fate labels (including the touched-live anomaly);
* the counterfactual rest extension and the stop-first resolution rule;
* the pre-registered interpretation branches, including the low-n guard.

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
              / "06_RESEARCH" / "scripts" / "fill_takeability_study.py")


def _load_pack():
    spec = importlib.util.spec_from_file_location(
        "fill_takeability_study", _PACK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["fill_takeability_study"] = module
    spec.loader.exec_module(module)
    return module


ft = _load_pack()


def _bars(points: list[tuple[float, float]]) -> list[dict]:
    start = datetime(2025, 6, 1, tzinfo=timezone.utc)
    return [{"timestamp": start + timedelta(minutes=5 * i),
             "low": low, "high": high, "close": (low + high) / 2.0}
            for i, (low, high) in enumerate(points)]


def _candle(low: float, high: float):
    from smc.config.timeframe import Timeframe
    from smc.core.candle import Candle
    return Candle(timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
                  open=(low + high) / 2.0, high=high, low=low,
                  close=(low + high) / 2.0, timeframe=Timeframe.M5)


# ------------------------------------------------------------------ #
# Touch semantics
# ------------------------------------------------------------------ #
def test_limit_touch_matches_production_fill_model():
    from smc.backtest.fill_model import limit_filled
    from smc.core.enums import Direction

    cases = [
        ("long", 100.0, 99.0, 101.0),
        ("long", 100.0, 100.0, 101.0),   # exact touch is inclusive
        ("long", 100.0, 100.5, 101.0),   # never reaches
        ("short", 100.0, 99.0, 100.0),
        ("short", 100.0, 99.0, 99.9),
        ("short", 100.0, 98.0, 100.5),
    ]
    for direction, limit, low, high in cases:
        ours = ft.limit_touch(direction, limit, low, high)
        theirs = limit_filled(
            Direction.LONG if direction == "long" else Direction.SHORT,
            limit, _candle(low, high))
        assert ours is theirs, (direction, limit, low, high)


# ------------------------------------------------------------------ #
# Eligible window
# ------------------------------------------------------------------ #
def test_live_window_matches_section23_boundary():
    # placed on 100 with rest 12 -> expiry fires at bars_open >= 12 -> 111.
    # Placement bar never eligible; 111 is cancelled before its fills.
    assert ft.live_window(100, 12, None, 10_000) == (101, 110)


def test_live_window_for_r8_lifetimes():
    assert ft.live_window(100, 36, None, 10_000) == (101, 134)
    assert ft.live_window(100, 48, None, 10_000) == (101, 146)


def test_live_window_empty_when_lifetime_is_too_short():
    first, last = ft.live_window(100, 2, None, 10_000)
    assert first > last


def test_live_window_clamps_at_portfolio_cancel_and_series_end():
    # a Friday/news cancel on bar 105 removes the order before 105's fills
    assert ft.live_window(100, 48, 105, 10_000) == (101, 104)
    # cancel on the placement bar itself -> empty
    first, last = ft.live_window(100, 48, 100, 10_000)
    assert first > last
    # series end clamp
    assert ft.live_window(100, 48, None, 120) == (101, 119)


def test_section23_cancel_bar_equals_last_eligible_plus_one():
    """Cross-check against the product book's own expiry predicate."""
    from smc.backtest.orders import PendingOrderBook
    from smc.backtest.fill_model import fill_price  # noqa: F401 (import guard)
    from smc.config.timeframe import Timeframe

    book = PendingOrderBook()
    order = book.place(direction=__import__("smc.core.enums", fromlist=["Direction"]).Direction.LONG,
                       entry_price=100.0, sl=99.0, tp=102.0, volume=0.1,
                       placed_bar=100, placed_at=None, rest_bars=12)
    cancelled_at = None
    for bar_index in range(100, 130):
        if book.expired_by_section23(bar_index, Timeframe.M5):
            cancelled_at = bar_index
            break
    first, last = ft.live_window(100, 12, cancelled_at, 10_000)
    assert cancelled_at == last + 1
    assert first == 101
    assert order.ticket == 1


# ------------------------------------------------------------------ #
# Fate labels
# ------------------------------------------------------------------ #
def test_classify_fate_is_exclusive():
    assert ft.classify_fate(filled_bar=104, live_first=101, live_last=110,
                            touch_live=104, touch_any=104,
                            cancel_reason=None) == ft.FATE_FILLED
    assert ft.classify_fate(filled_bar=None, live_first=101, live_last=110,
                            touch_live=104, touch_any=104,
                            cancel_reason="expired_section23") == \
        ft.FATE_TOUCH_LIVE_UNFILLED
    assert ft.classify_fate(filled_bar=None, live_first=101, live_last=110,
                            touch_live=None, touch_any=140,
                            cancel_reason="expired_section23") == \
        ft.FATE_TOUCH_AFTER_EXPIRY
    assert ft.classify_fate(filled_bar=None, live_first=101, live_last=110,
                            touch_live=None, touch_any=None,
                            cancel_reason="expired_section23") == \
        ft.FATE_NEVER_TOUCHED
    assert ft.classify_fate(filled_bar=None, live_first=101, live_last=104,
                            touch_live=None, touch_any=140,
                            cancel_reason="friday_eod") == ft.FATE_CANCELLED
    assert ft.is_portfolio_cancel("friday_eod") is True
    assert ft.is_portfolio_cancel("news") is True
    assert ft.is_portfolio_cancel("poi_violated") is True
    assert ft.is_portfolio_cancel("expired_section23") is False
    assert ft.is_portfolio_cancel("expired_give_up") is False
    assert ft.is_portfolio_cancel(None) is False


def test_expiry_is_the_end_of_the_window_not_a_cancel():
    """A §23 expiry ends the window; the fate is what the market did."""
    assert ft.classify_fate(filled_bar=None, live_first=101, live_last=110,
                            touch_live=None, touch_any=None,
                            cancel_reason="expired_section23") == \
        ft.FATE_NEVER_TOUCHED
    assert ft.classify_fate(filled_bar=None, live_first=101, live_last=110,
                            touch_live=None, touch_any=140,
                            cancel_reason="expired_give_up") == \
        ft.FATE_TOUCH_AFTER_EXPIRY


def test_fate_labels_are_the_preregistered_set():
    assert ft.FATES == ("FILLED", "TOUCHED_WHILE_LIVE_UNFILLED",
                        "TOUCHED_ONLY_AFTER_EXPIRY", "NEVER_TOUCHED_IN_LIFE",
                        "CANCELLED_OTHER", "DATA_GAP")


# ------------------------------------------------------------------ #
# Touch / approach helpers
# ------------------------------------------------------------------ #
def test_first_touch_and_closest_approach():
    bars = _bars([(97.0, 100.0), (97.0, 99.0), (95.0, 96.0), (101.0, 102.0)])
    # long limit 98.5: bar 0 low 97 touches (inclusive); closest after = 1.5
    assert ft.first_touch("long", 98.5, bars, 0, 3) == 0
    assert ft.first_touch("long", 98.5, bars, 1, 3) == 1
    assert ft.closest_approach("long", 94.0, bars, 0, 0) == (3.0, 0)
    # short limit 100.5: bar 3 high 102 touches
    assert ft.first_touch("short", 100.5, bars, 0, 3) == 3
    # empty window never invents a touch
    assert ft.first_touch("long", 98.5, bars, 3, 2) is None
    assert ft.closest_approach("long", 98.5, bars, 3, 2) == (None, None)


def test_closest_approach_returns_zero_on_touch():
    bars = _bars([(95.0, 96.0)])
    assert ft.closest_approach("long", 96.0, bars, 0, 0) == (0.0, 0)


# ------------------------------------------------------------------ #
# Counterfactual
# ------------------------------------------------------------------ #
def test_counterfactual_extends_only_forward():
    # touch one bar after the base window's last eligible bar
    bars = _bars([(105.0, 106.0)] * 12 + [(99.0, 100.0)] + [(105.0, 106.0)] * 60)
    base_first, base_last = ft.live_window(0, 12, None, len(bars))
    assert base_last == 10
    # without extension the touch at bar 12 is outside the window
    assert ft.first_touch("long", 100.0, bars, base_first, base_last) is None
    assert ft.counterfactual_touch("long", 100.0, bars, placed_bar=0,
                                   rest_bars=12, extension=12,
                                   series_len=len(bars)) == 12
    # a touch inside the base window is unchanged by the extension
    bars2 = _bars([(105.0, 106.0), (98.0, 100.0)] + [(105.0, 106.0)] * 70)
    assert ft.counterfactual_touch("long", 100.0, bars2, placed_bar=0,
                                   rest_bars=12, extension=48,
                                   series_len=len(bars2)) == 1


def test_counterfactual_resolve_is_stop_first():
    bars = _bars([(99.0, 101.0), (98.5, 101.5), (104.0, 105.0)])
    # fill at 1.0 with sl 0.9 tp 1.1 on bar 0: both tagged -> STOP wins (frozen)
    out = ft.counterfactual_resolve("long", 100.0, 99.0, 101.0, bars,
                                    touch_bar=0, horizon_end=2)
    assert out["result"] == "STOPPED"
    assert out["bar"] == 0
    assert out["r"] == pytest.approx(-1.0)


def test_counterfactual_resolve_target_and_open():
    bars = _bars([(99.5, 100.5), (99.8, 102.0)])
    out = ft.counterfactual_resolve("long", 100.0, 99.0, 101.0, bars,
                                    touch_bar=0, horizon_end=1)
    assert out["result"] == "TARGET"
    assert out["r"] == pytest.approx(1.0)
    flat = _bars([(99.5, 100.5), (99.6, 100.4)])
    assert ft.counterfactual_resolve("long", 100.0, 99.0, 101.0, flat,
                                     touch_bar=0, horizon_end=1)["result"] == \
        "OPEN_AT_HORIZON"


def test_counterfactual_resolve_data_gap_never_invents():
    bars = _bars([(99.5, 100.5)])
    assert ft.counterfactual_resolve("long", 100.0, None, None, bars,
                                     touch_bar=0, horizon_end=0)["result"] == \
        "DATA_GAP"
    assert ft.counterfactual_resolve("long", 100.0, 100.0, 101.0, bars,
                                     touch_bar=0, horizon_end=0)["result"] == \
        "DATA_GAP"


# ------------------------------------------------------------------ #
# Causes + interpretation
# ------------------------------------------------------------------ #
def _order(fate: str, *, approach=None, atr=None, reason=None) -> dict:
    return {"fate": fate, "closest_approach_price": approach,
            "atr_at_place": atr, "cancel_reason": reason}


def test_rank_causes_counts_and_shares():
    rows = [
        _order(ft.FATE_FILLED),
        _order(ft.FATE_TOUCH_AFTER_EXPIRY),
        _order(ft.FATE_NEVER_TOUCHED, approach=0.4, atr=1.0),
        _order(ft.FATE_NEVER_TOUCHED, approach=30.0, atr=1.0),
        _order(ft.FATE_CANCELLED, reason="friday_eod"),
    ]
    causes = ft.rank_causes(rows)
    assert causes["n_placed"] == 5
    assert causes["n_filled"] == 1
    assert causes["never_touched"] == 2
    assert causes["never_touched_near_miss_le_0_5atr"] == 1
    assert causes["touched_only_after_end"] == 1
    assert causes["cancelled_other"] == 1
    assert causes["cancel_reasons"] == {"friday_eod": 1}
    assert causes["pct_never_touched"] == pytest.approx(40.0)


def test_interpret_low_n_guard():
    label, _ = ft.interpret({"n_placed": ft.MIN_PLACED_FOR_LABEL - 1})
    assert label == "INCONCLUSIVE_LOW_N"


def test_interpret_healthy_branch():
    causes = {"n_placed": 20, "pct_filled": 80.0, "touched_only_after_end": 1,
              "never_touched_near_miss_le_0_5atr": 1, "pct_never_touched": 20.0}
    assert ft.interpret(causes)[0] == "FILL_PATH_HEALTHY"


def test_interpret_bottleneck_branch():
    causes = {"n_placed": 20, "pct_filled": 10.0, "touched_only_after_end": 8,
              "never_touched_near_miss_le_0_5atr": 3, "pct_never_touched": 20.0}
    assert ft.interpret(causes)[0] == "FILL_PATH_IS_BOTTLENECK"


def test_interpret_mixed_branch():
    causes = {"n_placed": 20, "pct_filled": 40.0, "touched_only_after_end": 2,
              "never_touched_near_miss_le_0_5atr": 2, "pct_never_touched": 40.0}
    assert ft.interpret(causes)[0] == "MIXED"


def test_interpret_labels_are_the_preregistered_set():
    import re
    text = _PACK_PATH.read_text(encoding="utf-8")
    for label in ("FILL_PATH_HEALTHY", "FILL_PATH_IS_BOTTLENECK", "MIXED",
                  "INCONCLUSIVE_LOW_N"):
        assert label in text
