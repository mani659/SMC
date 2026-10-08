"""FR-1 multi-TF cascade tests — resample, feed, non-M1 detection, M8 wiring, alarm.

Frozen-rule posture: no threshold touches anywhere here — these tests pin
plumbing (which bars reach which detector) and loud-failure behavior.
"""

import pytest

from smc.backtest.data_feed import CandleSeries, MultiTimeframeFeed
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction
from smc.data.resample import resample_multi, resample_ohlcv
from smc.orchestration.detection_driver import DetectionDriver
from smc.orchestration.multi_tf import (
    MultiTFDetectionDriver,
    check_single_tf_detect_exec,
)
from smc.poi.models.m1_origin_base import M1OriginBase


def _trend_rows(n, start=100.0, step=0.1):
    rows, price = [], start
    for _ in range(n):
        rows.append((price, price + 0.05, price - 0.05, price + step / 2))
        price += step
    return rows


def _m8_rows():
    """Bearish candle + qualifying rise (mirrors the M8 acceptance shape)."""
    rows = []
    price = 200.0
    for _ in range(19):
        rows.append((price, price + 0.05, price - 0.05, price + 0.05))
        price += 0.05
    rows.append((200.7, 201.2, 200.6, 201.0))   # last up candle
    rows.append((201.0, 202.0, 199.4, 199.6))   # dump
    rows.append((199.6, 199.9, 199.0, 199.2))
    rows.append((199.2, 199.5, 198.8, 199.0))
    rows.append((199.0, 199.4, 198.9, 199.2))
    return rows


# ---------------------------------------------------------------------- #
# E1a: resampling correctness + determinism
# ---------------------------------------------------------------------- #
def test_resample_m1_to_h1_exact_ohlcv(candle_factory):
    m1 = candle_factory(_trend_rows(120), timeframe=Timeframe.M1)
    h1 = resample_ohlcv(m1, Timeframe.H1)
    assert len(h1) == 2
    first, sixty = m1[0], m1[59]
    assert (h1[0].open, h1[0].high, h1[0].low, h1[0].close) == (
        first.open,
        max(c.high for c in m1[:60]),
        min(c.low for c in m1[:60]),
        sixty.close,
    )
    assert h1[0].volume == sum(c.volume for c in m1[:60])
    assert all(c.timeframe is Timeframe.H1 for c in h1)
    assert h1[0].timestamp < h1[1].timestamp
    again = resample_ohlcv(m1, Timeframe.H1)
    assert again == h1  # deterministic


def test_resample_multi_counts(candle_factory):
    m1 = candle_factory(_trend_rows(120), timeframe=Timeframe.M1)
    out = resample_multi(m1, [Timeframe.M5, Timeframe.H1, Timeframe.H4])
    assert len(out[Timeframe.M5]) == 24
    assert len(out[Timeframe.H1]) == 2
    assert len(out[Timeframe.H4]) == 1  # partial head bin aggregates present bars
    assert out[Timeframe.M5][0].timeframe is Timeframe.M5


def test_resample_rejects_disordered_input(candle_factory):
    m1 = candle_factory(_trend_rows(10), timeframe=Timeframe.M1)
    bad = m1[:5] + list(reversed(m1[5:]))
    with pytest.raises(ValueError):
        resample_ohlcv(bad, Timeframe.H1)


# ---------------------------------------------------------------------- #
# E1b: feed accepts the FR-1 shape (M5 primary + H1/H4)
# ---------------------------------------------------------------------- #
def test_feed_accepts_fr1_shape_and_alignment(candle_factory):
    m1 = candle_factory(_trend_rows(180), timeframe=Timeframe.M1)
    multi = resample_multi(m1, [Timeframe.M5, Timeframe.H1, Timeframe.H4])
    feed = MultiTimeframeFeed(
        primary=CandleSeries(multi[Timeframe.M5], Timeframe.M5),
        htf={Timeframe.H1: CandleSeries(multi[Timeframe.H1], Timeframe.H1),
             Timeframe.H4: CandleSeries(multi[Timeframe.H4], Timeframe.H4)},
    )
    assert feed.has_series(Timeframe.H1) and feed.has_series(Timeframe.H4)
    assert feed.primary_timeframe is Timeframe.M5
    h1 = feed.series(Timeframe.H1)
    assert h1.index_at_or_before(h1[1].timestamp) == 1


# ---------------------------------------------------------------------- #
# E2: detection runs on non-M1 bars (call inspection, not just tags)
# ---------------------------------------------------------------------- #
def test_detection_executes_on_h1_and_h4_bars(candle_factory, monkeypatch):
    seen: set = set()
    original = M1OriginBase.detect

    def spy(self, candles, swings, levels):
        seen.update(c.timeframe for c in candles)
        return original(self, candles, swings, levels)

    monkeypatch.setattr(M1OriginBase, "detect", spy)
    h1 = candle_factory(_trend_rows(120), timeframe=Timeframe.H1)
    h4 = candle_factory(_trend_rows(80), timeframe=Timeframe.H4)
    driver = MultiTFDetectionDriver(
        detection_timeframes=(Timeframe.H4, Timeframe.H1),
        execution_timeframe=Timeframe.M5,
    )
    result = driver.validate_multi({Timeframe.H4: h4, Timeframe.H1: h1})
    assert {Timeframe.H1, Timeframe.H4} <= seen
    assert result.single_tf_detect_exec is False
    assert set(result.counts_by_tf()) == {Timeframe.H4, Timeframe.H1}


# ---------------------------------------------------------------------- #
# E3: M8 emits through the wired driver path (no silent empty map)
# ---------------------------------------------------------------------- #
def test_m8_emits_through_driver_when_htf_map_fed(candle_factory):
    h4 = candle_factory(_m8_rows(), timeframe=Timeframe.H4)
    h1 = candle_factory(_trend_rows(120), timeframe=Timeframe.H1)
    driver = DetectionDriver(Timeframe.H1, htf_candles={Timeframe.H4: h4})
    _passed, _results, _run, _skipped, detected = driver.validate_window(h1)
    m8 = [p for p in detected if ModelType.M8 in p.models]
    assert len(m8) >= 1, "M8 stayed silent despite a fed H4 map"
    assert all(p.zone.timeframe is Timeframe.H4 for p in m8)


def test_multitf_driver_arm_bars_path(candle_factory):
    """arm_bars wiring: passed POIs arm without disturbing validation."""
    from smc.orchestration.engine import PipelineEngine

    h4 = candle_factory(_trend_rows(80), timeframe=Timeframe.H4)
    h1 = candle_factory(_trend_rows(120), timeframe=Timeframe.H1)
    engine = PipelineEngine()
    driver = MultiTFDetectionDriver(
        detection_timeframes=(Timeframe.H4, Timeframe.H1),
        execution_timeframe=Timeframe.M5,
    )
    result = driver.validate_multi(
        {Timeframe.H4: h4, Timeframe.H1: h1},
        engine=engine, arm_bars={Timeframe.H4: 10, Timeframe.H1: 10},
    )
    assert set(result.counts_by_tf()) == {Timeframe.H4, Timeframe.H1}
    assert result.degraded is False


# ---------------------------------------------------------------------- #
# E5: alarm — missing HTF fails loud; single-TF flag is honest
# ---------------------------------------------------------------------- #
def test_missing_htf_series_fails_loud_by_default(candle_factory):
    h1 = candle_factory(_trend_rows(120), timeframe=Timeframe.H1)
    driver = MultiTFDetectionDriver(
        detection_timeframes=(Timeframe.H4, Timeframe.H1),
        execution_timeframe=Timeframe.M5,
    )
    with pytest.raises(ValueError, match="H4"):
        driver.validate_multi({Timeframe.H1: h1})


def test_missing_htf_degraded_only_on_explicit_opt_in(candle_factory):
    h1 = candle_factory(_trend_rows(120), timeframe=Timeframe.H1)
    driver = MultiTFDetectionDriver(
        detection_timeframes=(Timeframe.H4, Timeframe.H1),
        execution_timeframe=Timeframe.M5,
        missing_ok=True,
    )
    result = driver.validate_multi({Timeframe.H1: h1})
    assert result.degraded is True
    assert Timeframe.H4.name in result.errors
    assert Timeframe.H1 in result.counts_by_tf()


def test_single_tf_detect_exec_flag():
    assert check_single_tf_detect_exec([Timeframe.M1], Timeframe.M1) is True
    assert check_single_tf_detect_exec(
        [Timeframe.H4, Timeframe.H1], Timeframe.M5) is False
    assert check_single_tf_detect_exec([], Timeframe.M5) is True


def test_m1_only_driver_reports_noncompliant_flag(candle_factory):
    m1 = candle_factory(_trend_rows(120), timeframe=Timeframe.M1)
    driver = MultiTFDetectionDriver(
        detection_timeframes=(Timeframe.M1,),
        execution_timeframe=Timeframe.M1,
    )
    assert driver.validate_multi(
        {Timeframe.M1: m1}).single_tf_detect_exec is True
