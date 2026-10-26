"""Milestone W — Weekly (W1) provisioning tests (Lead Architect directive 2026-10-06).

W1 is an ABOVE-DAILY HTF *context* timeframe: same frozen scanners, same
constants, execution stays M5. These tests pin:

1. Offline resample: M1 → W1 with MONDAY-00:00 bins (market convention —
   epoch-multiples of 10080 min would align to Thursdays), honest OHLCV
   aggregation, no invented weekend bars, deterministic output.
2. Product runtime: W1 accepted in the detection set (required, loud-fail
   applies) and in the optional set (provisioned, M8 scans it when
   supplied). A synthetic window emits ≥0 W1 POIs without crash — zero is
   a PASS as long as the pipeline runs and the TF is provisioned.
3. Live loop: the product HTF fetch list includes W1 (MT5 PERIOD_W1 via
   the int(tf) cast); the batch cadence stays keyed on the H1 close.

No MT5, no wall clock, no market data — synthetic fixtures only.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.data.resample import resample_multi, resample_ohlcv
from smc.live.loop import LiveLoop
from smc.orchestration.engine import PipelineEngine
from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime
from smc.poi.models.m8_htf_demand_supply import M8HtfDemandSupply

W1 = Timeframe.W1
M5 = Timeframe.M5
H1 = Timeframe.H1
H4 = Timeframe.H4
D1 = Timeframe.D1

# 2026-01-05 is a Monday (UTC) — every weekly fixture anchors here.
WEEK_1_MONDAY = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
WEEK_MINUTES = 7 * 1440


def _c(ts: datetime, o: float, h: float, l: float, c: float,
       tf: Timeframe, volume: float = 1.0) -> Candle:
    return Candle(timestamp=ts, open=o, high=h, low=l, close=c,
                  volume=volume, timeframe=tf)


# ---------------------------------------------------------------------- #
# 1 — offline resample: M1 → W1
# ---------------------------------------------------------------------- #
def _m1_window() -> list[Candle]:
    """M1 candles spanning Wed→Fri of week 1 and Monday of week 2.

    Week 1 (Mon 2026-01-05): Wed 07 + Fri 09.
    Week 2 (Mon 2026-01-12): Mon 00:01 — same ISO week, aggregates together.
    """
    wed = datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc)
    fri = datetime(2026, 1, 9, 15, 0, tzinfo=timezone.utc)
    mon2 = datetime(2026, 1, 12, 0, 1, tzinfo=timezone.utc)
    return [
        _c(wed, 100.0, 101.0, 99.5, 100.5, Timeframe.M1, volume=3.0),
        _c(fri, 100.5, 102.0, 100.0, 101.5, Timeframe.M1, volume=4.0),
        _c(mon2, 101.5, 101.8, 100.9, 101.0, Timeframe.M1, volume=2.0),
    ]


def test_resample_w1_bins_align_to_monday_open():
    bars = resample_ohlcv(_m1_window(), W1)
    # Two ISO weeks present → exactly two weekly bars, stamped at the
    # Monday 00:00 UTC open of each week (NOT a Thursday epoch-multiple).
    assert [b.timestamp for b in bars] == [
        WEEK_1_MONDAY,
        WEEK_1_MONDAY + timedelta(minutes=WEEK_MINUTES),
    ]
    for bar in bars:
        assert bar.timestamp.weekday() == 0          # Monday
        assert bar.timestamp.hour == 0 and bar.timestamp.minute == 0
        assert bar.timeframe is W1


def test_resample_w1_ohlcv_aggregation_is_honest():
    bars = resample_ohlcv(_m1_window(), W1)
    week1, week2 = bars
    # Week 1: both candles aggregate (O=first open, H=max, L=min, C=last).
    assert (week1.open, week1.high, week1.low, week1.close) == (
        100.0, 102.0, 99.5, 101.5)
    assert week1.volume == pytest.approx(7.0)        # 3 + 4
    # Week 2: single candle round-trips unchanged.
    assert (week2.open, week2.high, week2.low, week2.close) == (
        101.5, 101.8, 100.9, 101.0)
    assert week2.volume == pytest.approx(2.0)


def test_resample_w1_invents_no_weekend_bars():
    # Candles only Wed + Fri of one week: one bar for the week, and
    # certainly no Saturday/Sunday placeholder bars.
    wed = datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc)
    fri = datetime(2026, 1, 9, 15, 0, tzinfo=timezone.utc)
    bars = resample_ohlcv([
        _c(wed, 100.0, 100.4, 99.8, 100.2, Timeframe.M1),
        _c(fri, 100.2, 100.6, 100.0, 100.4, Timeframe.M1),
    ], W1)
    assert len(bars) == 1
    assert bars[0].timestamp == WEEK_1_MONDAY
    assert all(b.timestamp.weekday() < 5 for b in bars)


def test_resample_w1_is_deterministic_and_guard_bypassed():
    window = _m1_window()
    first = resample_ohlcv(window, W1)
    second = resample_ohlcv(window, W1)
    assert first == second                            # same input → same output
    assert [b.timestamp for b in first] == sorted(b.timestamp for b in first)
    # W1 bypasses the 1440-modulo guard deliberately (10080 % 1440 == 0 in
    # trading weeks but epoch alignment would be Thursday) — it must not raise.
    resample_ohlcv(window, W1)                        # no ValueError
    multi = resample_multi(window, (Timeframe.H1, Timeframe.D1, W1))
    assert set(multi) == {Timeframe.H1, Timeframe.D1, W1}
    assert len(multi[W1]) == 2


# ---------------------------------------------------------------------- #
# 2 — M8 scans a supplied W1 series (same scanner, frozen constants)
# ---------------------------------------------------------------------- #
def _weekly_impulse_series(count: int = 30) -> list[Candle]:
    """Weekly candles: flat warm-up (ATR seed), then a LONG impulse
    (bearish candle + 3-candle rally ≥ 1×ATR) and a SHORT impulse.

    Deterministic: produces OB/FVG/demand-supply zones on W1 without any
    randomness, so M8-on-W1 has real zones to emit.
    """
    start = WEEK_1_MONDAY
    out: list[Candle] = []
    # Warm-up: 16 tight doji-ish candles (ATR ≈ 0.2).
    for i in range(16):
        ts = start + i * timedelta(minutes=WEEK_MINUTES)
        out.append(_c(ts, 100.0, 100.1, 99.9, 100.0, W1))
    # Bearish candle then strong rally (LONG demand zone + FVG + OB).
    base = 16
    out.append(_c(start + base * timedelta(minutes=WEEK_MINUTES),
                  100.5, 100.6, 99.9, 100.0, W1))            # bearish trigger
    out.append(_c(start + (base + 1) * timedelta(minutes=WEEK_MINUTES),
                  100.2, 101.4, 100.1, 101.2, W1))            # rally 1
    out.append(_c(start + (base + 2) * timedelta(minutes=WEEK_MINUTES),
                  101.2, 102.9, 101.1, 102.7, W1))            # rally 2
    out.append(_c(start + (base + 3) * timedelta(minutes=WEEK_MINUTES),
                  102.7, 104.4, 102.6, 104.2, W1))            # rally 3 (FVG c3)
    # Bullish candle then strong drop (SHORT supply zone).
    top = base + 4
    out.append(_c(start + top * timedelta(minutes=WEEK_MINUTES),
                  104.2, 105.2, 104.1, 104.8, W1))            # bullish trigger
    out.append(_c(start + (top + 1) * timedelta(minutes=WEEK_MINUTES),
                  104.8, 104.9, 103.3, 103.5, W1))            # drop 1
    out.append(_c(start + (top + 2) * timedelta(minutes=WEEK_MINUTES),
                  103.5, 103.6, 101.8, 102.0, W1))            # drop 2
    out.append(_c(start + (top + 3) * timedelta(minutes=WEEK_MINUTES),
                  102.0, 102.1, 100.3, 100.5, W1))            # drop 3
    # Flat tail so the series ends well after the impulses.
    for i in range(top + 4, count):
        ts = start + i * timedelta(minutes=WEEK_MINUTES)
        out.append(_c(ts, 100.5, 100.6, 100.4, 100.5, W1))
    return out


def test_m8_emits_w1_zones_from_supplied_weekly_series():
    w1 = _weekly_impulse_series()
    assert all(c.timeframe is W1 for c in w1)
    model = M8HtfDemandSupply(Timeframe.H4, htf_candles={W1: w1})
    pois = model.detect(w1, [], [])
    w1_pois = [p for p in pois if p.zone.timeframe is W1]
    # The impulse fixtures guarantee ≥1 weekly zone (displacement ≥ 1×ATR,
    # frozen DISPLACEMENT_MIN_ATR=1.0 — nothing tuned here).
    assert len(w1_pois) >= 1
    for poi in w1_pois:
        assert poi.zone.timeframe is W1
        assert poi.zone.direction in (Direction.LONG, Direction.SHORT)
    # No series supplied → M8 stays silent on W1 (optional stays optional).
    silent = M8HtfDemandSupply(Timeframe.H4, htf_candles={})
    assert silent.detect(w1, [], []) == []


# ---------------------------------------------------------------------- #
# 3 — product runtime accepts W1 (detection set AND optional set)
# ---------------------------------------------------------------------- #
def _oscillating(tf: Timeframe, count: int, *, start: datetime,
                 base: float = 100.0) -> list[Candle]:
    step = timedelta(minutes=tf.minutes)
    out: list[Candle] = []
    for i in range(count):
        wave = 1.2 * (1.0 if i % 8 < 4 else -1.0)
        mid = base + wave + 0.02 * i
        out.append(_c(start + i * step, mid - 0.2, mid + 0.6, mid - 0.6,
                      mid + 0.2, tf))
    return out


def test_runtime_accepts_w1_in_detection_set():
    """W1 as a REQUIRED detection timeframe: full batch runs, per_tf has W1."""
    start = WEEK_1_MONDAY
    series = {
        W1: _weekly_impulse_series(30),
        H4: _oscillating(H4, 80, start=start),
        H1: _oscillating(H1, 220, start=start),
    }
    runtime = MultiTFProductRuntime(
        detection_timeframes=(W1, H4, H1),
    )
    engine = PipelineEngine()
    as_of = max(s[-1].timestamp for s in series.values())
    report = runtime.run_batch(
        engine=engine, series_by_tf=series, as_of=as_of, arm_bar=0,
    )
    # Pipeline ran end-to-end with W1 in the required set — no crash, and
    # W1 has its own per-TF counts. ≥0 W1 POIs is a PASS by directive.
    assert "W1" in report.per_tf
    counts = report.per_tf["W1"]
    assert {"detected_raw", "merged", "passed"} <= set(counts)
    assert counts["passed"] <= counts["merged"] <= max(counts["detected_raw"], 1)
    assert report.degraded is False
    assert runtime.missing_series(series) == ()
    for poi in report.armed:
        assert poi in engine.tracked_pois()


def test_runtime_provisions_w1_as_optional_and_feeds_m8():
    """Default runtime: W1 optional — supplied series reaches M8's map."""
    start = WEEK_1_MONDAY
    series = {
        H4: _oscillating(H4, 80, start=start),
        H1: _oscillating(H1, 220, start=start),
        W1: _weekly_impulse_series(30),
    }
    runtime = MultiTFProductRuntime()
    driver, driver_series = runtime._build_driver(series)
    assert set(driver_series) == {H4, H1}             # W1 not required
    assert W1 in (driver.htf_candles or {})           # …but fed to M8
    # Without a supplied W1 series the map simply lacks it (tolerated).
    driver2, _ = runtime._build_driver(
        {H4: series[H4], H1: series[H1]})
    assert W1 not in (driver2.htf_candles or {})
    # Full batch with W1 optional: runs, no crash, ≥0 armed.
    engine = PipelineEngine()
    as_of = max(s[-1].timestamp for s in series.values())
    report = runtime.run_batch(
        engine=engine, series_by_tf=series, as_of=as_of, arm_bar=5,
    )
    assert report.degraded is False
    assert report.armed_count >= 0
    for poi in report.armed:
        assert poi in engine.tracked_pois()


# ---------------------------------------------------------------------- #
# 4 — live loop fetches W1 in product mode (cadence unchanged)
# ---------------------------------------------------------------------- #
class _WeeklyFakeConnector:
    """MT5-shaped connector serving per-TF rows (records copy_rates tf)."""

    def __init__(self, series: dict) -> None:
        self.series = {tf: list(bars) for tf, bars in series.items()}
        self.copy_calls: list = []

    def connect(self) -> bool:
        return True

    def copy_rates(self, symbol, tf, start, count):
        self.copy_calls.append(tf)
        return [
            dict(time=int(b.timestamp.timestamp()), open=b.open, high=b.high,
                 low=b.low, close=b.close)
            for b in self.series.get(tf, [])
        ]


class _FakeRunner:
    """Minimal runner seam: records cycles + arm_multi_tf dispatches."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        self.cycles: list = []
        self.batches: list = []

    def run_one_cycle(self, bar):
        self.cycles.append(bar)

    def arm_multi_tf(self, series, *, as_of, arm_bar, execution_candles=None):
        self.batches.append((series, as_of, arm_bar))

        class _Report:
            armed: list = []
            armed_count = 0

            def summary(self):
                return {}

        return _Report()


class _FakeHeartbeat:
    def maybe_publish(self):
        return False

    def publish_shutdown(self):
        return None


def _live_loop(connector, runtime) -> LiveLoop:
    return LiveLoop(
        connector=connector, runner=_FakeRunner(runtime), driver=None,
        heartbeat=_FakeHeartbeat(), symbol="XAUUSD.x", timeframe=M5,
        runtime=runtime,
    )


def _product_fixture() -> dict:
    start = WEEK_1_MONDAY
    h4 = _oscillating(H4, 80, start=start)
    h1 = _oscillating(H1, 220, start=start)
    return {
        H4: h4,
        H1: h1,
        W1: _weekly_impulse_series(30),
        D1: [
            _c(start + i * timedelta(minutes=1440), 100.0, 100.6, 99.4,
               100.2, D1) for i in range(40)
        ],
        M5: _oscillating(M5, 240, start=h1[0].timestamp),
    }


def test_live_loop_provisions_w1_and_fetches_it_in_product_mode():
    series = _product_fixture()
    connector = _WeeklyFakeConnector(series)
    runtime = MultiTFProductRuntime()
    loop = _live_loop(connector, runtime)

    # Product HTF fetch list: detection set + optional context (W1, D1).
    assert loop.htf_timeframes == (H4, H1, W1, D1)

    assert loop.start() is True                       # probe fetched all TFs
    assert W1 in connector.copy_calls                 # W1 included in probe
    assert loop.run_once() == 0                       # cold start anchors
    assert loop.htf_batches == 0

    # New M5 bar → the H1 bar advanced → ONE batch (cadence unchanged).
    m5 = series[M5]
    connector.series[M5].append(
        Candle(timestamp=m5[-1].timestamp + timedelta(minutes=5),
               open=100.0, high=100.4, low=99.8, close=100.2, timeframe=M5))
    assert loop.run_once() == 1
    assert loop.htf_batches == 1
    assert connector.copy_calls.count(W1) >= 1        # W1 fetched for the batch
    assert len(loop.runner.batches) == 1
    batch_series = loop.runner.batches[0][0]
    assert W1 in batch_series and len(batch_series[W1]) > 0

    # Second M5 bar inside the SAME H1 bar → no new batch (cadence honoured;
    # W1 provisioning did not change the batch rhythm).
    connector.series[M5].append(
        Candle(timestamp=connector.series[M5][-1].timestamp
               + timedelta(minutes=5),
               open=100.0, high=100.4, low=99.8, close=100.2, timeframe=M5))
    assert loop.run_once() == 1
    assert loop.htf_batches == 1


def test_live_loop_legacy_mode_stays_without_w1():
    """No runtime → legacy path unchanged: H4/H1/D1 only, no W1 fetch."""
    series = _product_fixture()
    connector = _WeeklyFakeConnector(series)
    loop = LiveLoop(
        connector=connector, runner=_FakeRunner(None), driver=None,
        heartbeat=_FakeHeartbeat(), symbol="XAUUSD.x", timeframe=M5,
        runtime=None,
    )
    assert loop.htf_timeframes == (H4, H1, D1)
    assert W1 not in loop.htf_timeframes
