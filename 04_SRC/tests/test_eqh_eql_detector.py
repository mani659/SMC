"""Phase 1 — Equal Highs / Equal Lows detection (§2, §8, ≤ 4.5 pip tolerance)."""

import pytest

from smc.config.timeframe import Timeframe
from smc.core.enums import LiquidityType, PoolType
from smc.core.swing import Swing
from smc.detection.eqh_eql_detector import detect_equal_levels


def _swings(candle_factory, highs=(), lows=()):
    """Build Swing objects with levels ``highs``/``lows`` (one candle each)."""
    rows = []
    for level in (*highs, *lows):
        rows.append((level, level, level, level))
    candles = candle_factory(rows, Timeframe.M5)
    swings = []
    index = 0
    for level in highs:
        swings.append(
            Swing(
                is_high=True,
                level=level,
                candle_index=index,
                base_candle=candles[index],
                timeframe=Timeframe.M5,
            )
        )
        index += 1
    for level in lows:
        swings.append(
            Swing(
                is_high=False,
                level=level,
                candle_index=index,
                base_candle=candles[index],
                timeframe=Timeframe.M5,
            )
        )
        index += 1
    return swings, candles


def test_detects_bsl_and_ssl_clusters_concurrently(candle_factory):
    swings, _ = _swings(
        candle_factory,
        highs=(100.00, 100.44),   # 0.44 apart <= 4.5 pips (0.45 price)
        lows=(99.50, 99.44),      # 0.06 apart
    )
    levels = detect_equal_levels(swings, Timeframe.M5)
    assert len(levels) == 2

    bsl = next(lv for lv in levels if lv.pool is PoolType.BSL)
    ssl = next(lv for lv in levels if lv.pool is PoolType.SSL)
    assert bsl.type is LiquidityType.EQUAL_HIGHS_LOWS
    assert bsl.level == pytest.approx(100.44)  # extreme high of the cluster
    assert ssl.type is LiquidityType.EQUAL_HIGHS_LOWS
    assert ssl.level == pytest.approx(99.44)   # extreme low of the cluster


def test_out_of_tolerance_highs_not_clustered(candle_factory):
    swings, _ = _swings(candle_factory, highs=(100.00, 100.50))  # 0.50 > 0.45
    assert detect_equal_levels(swings, Timeframe.M5) == []


def test_single_member_clusters_dropped(candle_factory):
    swings, _ = _swings(candle_factory, highs=(100.00, 105.00), lows=(99.00,))
    assert detect_equal_levels(swings, Timeframe.M5) == []


def test_cluster_uses_anchor_tolerance_not_pairwise_chaining(candle_factory):
    # 100.4 chains to 100.0, but 101.0 is beyond the anchor bound -> the
    # running cluster must NOT absorb it (a 1.0 spread is not "equal").
    swings, _ = _swings(candle_factory, highs=(100.00, 100.40, 101.00))
    levels = detect_equal_levels(swings, Timeframe.M5)
    assert len(levels) == 1
    assert levels[0].pool is PoolType.BSL
    assert levels[0].level == pytest.approx(100.40)


def test_formed_at_is_most_recent_member(candle_factory):
    swings, candles = _swings(candle_factory, highs=(100.00, 100.30))
    levels = detect_equal_levels(swings, Timeframe.M5)
    assert levels[0].formed_at == candles[1].timestamp  # second top is later


def test_empty_swing_list_returns_empty():
    assert detect_equal_levels([], Timeframe.M5) == []