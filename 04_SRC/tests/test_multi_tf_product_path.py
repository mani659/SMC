"""C1 — product multi-TF runtime path tests (contract §5).

Covers the shared seam (``smc/orchestration/multi_tf_runtime.py``), the
live-loop dispatch (new-H1-close cadence + loud fail + explicit degraded
mode), the paper delegation, and the operator-config validation that keeps
detect==exec out of product mode.

All fixtures are synthetic — no MT5, no wall clock, no market data.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from smc.backtest.pipeline_adapter import PipelineAdapter
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.execution.order_manager import OrderResult
from smc.live.loop import LiveLoop
from smc.live.operator_config import ConfigError, load_operator_config
from smc.orchestration import multi_tf_runtime as runtime_module
from smc.orchestration.engine import PipelineEngine
from smc.orchestration.multi_tf import MultiTFDriverResult, PerTFResult
from smc.orchestration.multi_tf_runtime import (
    MissingHtfSeriesError,
    MultiTFProductRuntime,
    ZoneDedup,
    build_htf_prefixes,
)
from smc.paper.runner import PaperRunner
from smc.risk.risk_engine import RiskEngine

M5 = Timeframe.M5
START = datetime(2026, 3, 12, 8, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------- #
# Fixtures
# ---------------------------------------------------------------------- #
def _make_series(tf: Timeframe, count: int, *, start: datetime,
                 base: float = 100.0, amplitude: float = 1.2,
                 step_minutes: int | None = None) -> list[Candle]:
    """Oscillating synthetic series (deterministic, no randomness)."""
    minutes = step_minutes if step_minutes is not None else tf.minutes
    step = timedelta(minutes=minutes)
    out: list[Candle] = []
    for i in range(count):
        wave = amplitude * (1.0 if i % 8 < 4 else -1.0)
        drift = 0.02 * i
        mid = base + wave + drift
        out.append(Candle(
            timestamp=start + i * step,
            open=mid - 0.2,
            high=mid + 0.6,
            low=mid - 0.6,
            close=mid + 0.2,
            timeframe=tf,
        ))
    return out


def _htf_fixture(as_of: datetime | None = None) -> dict:
    """H4 + H1 (+D1) synthetic series ending at/after ``as_of``."""
    end = as_of or (START + timedelta(hours=200))
    h1 = _make_series(Timeframe.H1, 220, start=end - timedelta(hours=220))
    h4 = _make_series(Timeframe.H4, 80, start=end - timedelta(hours=320))
    d1 = _make_series(Timeframe.D1, 40, start=end - timedelta(days=40),
                      step_minutes=1440)
    return {Timeframe.H4: h4, Timeframe.H1: h1, Timeframe.D1: d1}


class _FakeDriver:
    """Driver stand-in: records kwargs and returns a fabricated result."""

    result = None
    calls: list = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def validate_multi(self, series, engine=None, return_details=False):
        type(self).calls.append({"series": series, "kwargs": self.kwargs})
        return type(self).result


def _fabricated_result(poi: POI, tf_list=(Timeframe.H4, Timeframe.H1)):
    per_tf = {
        tf: PerTFResult(timeframe=tf, detected_raw=1, merged=1, passed=1,
                        first_failure={}, skipped_models={})
        for tf in tf_list
    }
    details = {
        tf: {"passed": [poi], "results": [], "disp_map": {}}
        for tf in tf_list
    }
    return MultiTFDriverResult(per_tf=per_tf, single_tf_detect_exec=False,
                               degraded=False, errors={}, details=details)


def _zone_poi(top: float = 110.0, bottom: float = 105.0,
              direction: Direction = Direction.LONG) -> POI:
    return POI(zone=Zone(top=top, bottom=bottom, direction=direction,
                         timeframe=Timeframe.H4),
               models=[ModelType.M1])


# ---------------------------------------------------------------------- #
# 1/2/3 — loud-fail policy
# ---------------------------------------------------------------------- #
def test_run_batch_raises_when_required_htf_missing():
    runtime = MultiTFProductRuntime()
    engine = PipelineEngine()
    with pytest.raises(MissingHtfSeriesError) as excinfo:
        runtime.run_batch(
            engine=engine,
            series_by_tf={Timeframe.H1: _make_series(Timeframe.H1, 10, start=START)},
            as_of=START,
            arm_bar=0,
        )
    message = str(excinfo.value)
    assert "H4" in message and "single-TF" in message
    assert engine.tracked_pois() == []
    assert runtime.batches == 0


def test_degraded_requires_execution_series():
    runtime = MultiTFProductRuntime(allow_single_tf_degraded=True)
    with pytest.raises(MissingHtfSeriesError):
        runtime.run_batch(engine=PipelineEngine(), series_by_tf={},
                          as_of=START, arm_bar=0, execution_candles=[])


def test_degraded_single_tf_report_is_stamped():
    runtime = MultiTFProductRuntime(allow_single_tf_degraded=True)
    engine = PipelineEngine()
    exec_series = _make_series(M5, 60, start=START)
    report = runtime.run_batch(
        engine=engine,
        series_by_tf={},                     # no HTF at all
        as_of=exec_series[-1].timestamp,
        arm_bar=59,
        execution_candles=exec_series,
    )
    assert report.degraded is True
    assert "allow_single_tf_degraded=True" in (report.degraded_reason or "")
    assert report.single_tf_detect_exec is True
    assert report.missing == ("H4", "H1")
    assert "M5" in report.per_tf
    assert runtime.batches == 1


# ---------------------------------------------------------------------- #
# Prefixes + dedup rules
# ---------------------------------------------------------------------- #
def test_build_htf_prefixes_cutoff_semantics():
    series = _make_series(Timeframe.H1, 10, start=START)
    as_of = series[4].timestamp
    prefixes = build_htf_prefixes({Timeframe.H1: series}, as_of)
    assert len(prefixes[Timeframe.H1]) == 5        # bars <= as_of (inclusive)
    assert prefixes[Timeframe.H1][-1].timestamp == as_of
    # Empty input stays empty (policy decision is the runtime's, not here).
    assert build_htf_prefixes({Timeframe.H1: []}, as_of)[Timeframe.H1] == []


def test_build_htf_prefixes_rejects_disorder():
    series = _make_series(Timeframe.H1, 5, start=START)
    series[3], series[4] = series[4], series[3]
    with pytest.raises(ValueError):
        build_htf_prefixes({Timeframe.H1: series}, series[-1].timestamp)


def test_zone_dedup_matches_research_rule():
    dedup = ZoneDedup()
    long_zone = Zone(top=110.0, bottom=105.0, direction=Direction.LONG)
    assert dedup.seen(long_zone) is False
    dedup.register(long_zone)
    assert dedup.seen(long_zone) is True                       # identical
    assert dedup.seen(Zone(top=105.5, bottom=100.0,
                           direction=Direction.LONG)) is True  # overlap
    assert dedup.seen(Zone(top=110.0, bottom=105.0,
                           direction=Direction.SHORT)) is False  # other side
    assert dedup.seen(Zone(top=104.9, bottom=100.0,
                           direction=Direction.LONG)) is False   # disjoint
    assert len(dedup) == 1


# ---------------------------------------------------------------------- #
# 4 — structure on synthetic HTF + arming/dedup behaviour
# ---------------------------------------------------------------------- #
def test_run_batch_structure_on_synthetic_htf():
    runtime = MultiTFProductRuntime()
    engine = PipelineEngine()
    series = _htf_fixture()
    as_of = series[Timeframe.H1][-1].timestamp
    report = runtime.run_batch(engine=engine, series_by_tf=series, as_of=as_of,
                               arm_bar=123)
    assert report.batches == 1
    assert report.single_tf_detect_exec is False
    assert set(report.per_tf) == {"H4", "H1"}
    for counts in report.per_tf.values():
        assert {"detected_raw", "merged", "passed"} <= set(counts)
        assert counts["passed"] <= counts["merged"] <= max(counts["detected_raw"], 1)
    assert report.degraded is False
    assert isinstance(report.summary(), dict)
    # Every armed POI is FRESH and tracked (arming went through the engine).
    for poi in report.armed:
        assert poi in engine.tracked_pois()


def test_run_batch_arms_new_pois_and_skips_duplicate_zone(monkeypatch):
    first, second = _zone_poi(), _zone_poi()          # same zone, new objects
    _FakeDriver.calls = []
    _FakeDriver.result = _fabricated_result(first)
    monkeypatch.setattr(runtime_module, "MultiTFDetectionDriver", _FakeDriver)

    runtime = MultiTFProductRuntime()
    engine = PipelineEngine()
    series = _htf_fixture()
    as_of = series[Timeframe.H1][-1].timestamp

    report1 = runtime.run_batch(engine=engine, series_by_tf=series, as_of=as_of,
                                arm_bar=7)
    assert report1.armed_count == 1
    assert report1.armed[0] is first
    assert engine.episode(first).arm_bar == 7
    assert runtime.dedup.seen(first.zone) is True

    # Second batch: the SAME geometry re-detected as a NEW POI object must not
    # arm twice (uuid4 ids make identity comparison insufficient).
    _FakeDriver.result = _fabricated_result(second)
    report2 = runtime.run_batch(engine=engine, series_by_tf=series, as_of=as_of,
                                arm_bar=8)
    assert report2.armed_count == 0
    assert second.id in report2.duplicates
    assert len(engine.tracked_pois()) == 1
    assert runtime.batches == 2


def test_d1_is_forwarded_to_m8_only_when_supplied():
    series = _htf_fixture()
    runtime = MultiTFProductRuntime()
    driver, driver_series = runtime._build_driver(series)
    assert set(driver_series) == {Timeframe.H4, Timeframe.H1}
    assert set(driver.htf_candles or {}) == {Timeframe.D1, Timeframe.H4}

    no_d1 = MultiTFProductRuntime(supply_d1_to_m8=False)
    driver2, _ = no_d1._build_driver({Timeframe.H4: series[Timeframe.H4],
                                      Timeframe.H1: series[Timeframe.H1]})
    assert not (driver2.htf_candles or {})   # nothing forced into M8's map


# ---------------------------------------------------------------------- #
# Live loop dispatch (fake connector)
# ---------------------------------------------------------------------- #
class MultiTFFakeConnector:
    """MT5-shaped connector serving per-TF series (records copy_rates calls)."""

    def __init__(self, series: dict) -> None:
        self.series = {tf: list(bars) for tf, bars in series.items()}
        self.connect_ok = True
        self.connected = False
        self.copy_calls: list = []

    def connect(self) -> bool:
        self.connected = self.connect_ok
        return self.connect_ok

    def copy_rates(self, symbol, tf, start, count):
        self.copy_calls.append(tf)
        return [
            dict(time=int(b.timestamp.timestamp()), open=b.open, high=b.high,
                 low=b.low, close=b.close)
            for b in self.series.get(tf, [])
        ]

    def positions_get(self, symbol=None):
        return ()

    def account_info(self):
        from types import SimpleNamespace
        return SimpleNamespace(equity=10_000.0)

    def order_send(self, request: dict) -> dict:
        return {"retcode": 10008, "comment": "ok"}


class _FakeOrderManager:
    """Minimal OrderManager shape: no broker, explicit failure verdicts."""

    def __init__(self) -> None:
        self.placed: list = []
        self.cancelled: list = []

    def place_limit(self, request):
        self.placed.append(request)
        return OrderResult(success=False, retcode=0, ticket=None,
                           message="fake broker (no send)")

    def cancel_order(self, ticket):
        self.cancelled.append(ticket)
        return OrderResult(success=True, retcode=0, ticket=ticket, message="ok")


class _FakePositionManager:
    """Minimal PositionManager shape: empty book, successful no-ops."""

    def list_positions(self):
        return []

    def modify_sl(self, ticket, new_sl):
        return True

    def close_position(self, ticket, direction, volume):
        return True


def _live_stack(tmp_path, connector, runtime):
    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=M5)
    runner = PaperRunner(
        connector=connector,
        risk_engine=RiskEngine(),
        pipeline=adapter,
        order_manager=_FakeOrderManager(),
        position_manager=_FakePositionManager(),
        runtime=runtime,
    )
    class _Heartbeat:
        def maybe_publish(self):
            return False

        def publish_shutdown(self):
            return None

    loop = LiveLoop(connector=connector, runner=runner, driver=None,
                    heartbeat=_Heartbeat(), symbol="XAUUSD.x", timeframe=M5,
                    runtime=runtime)
    return loop, runner


def test_live_loop_runs_one_batch_per_new_h1_close(tmp_path):
    series = _htf_fixture()
    h1 = series[Timeframe.H1]
    m5 = _make_series(M5, 240, start=h1[0].timestamp)
    connector = MultiTFFakeConnector({
        **series,
        M5: m5,
    })
    runtime = MultiTFProductRuntime()
    loop, runner = _live_stack(tmp_path, connector, runtime)

    assert loop.start() is True
    assert loop.run_once() == 0                       # cold start anchors
    assert loop.htf_batches == 0

    # New M5 bar → the H1 bar advanced → ONE batch runs.
    connector.series[M5].append(
        Candle(timestamp=m5[-1].timestamp + timedelta(minutes=5),
               open=100.0, high=100.4, low=99.8, close=100.2, timeframe=M5)
    )
    assert loop.run_once() == 1
    assert loop.htf_batches == 1
    assert loop.last_report is not None
    assert loop.last_report.armed_count == len(loop.last_report.armed)

    # Another M5 bar inside the SAME H1 bar → no new batch (cadence honoured).
    connector.series[M5].append(
        Candle(timestamp=connector.series[M5][-1].timestamp
               + timedelta(minutes=5),
               open=100.0, high=100.4, low=99.8, close=100.2, timeframe=M5)
    )
    assert loop.run_once() == 1
    assert loop.htf_batches == 1

    # A NEW H1 bar appears → cadence advances → second batch.
    connector.series[Timeframe.H1].append(
        Candle(timestamp=h1[-1].timestamp + timedelta(hours=1),
               open=100.0, high=101.0, low=99.0, close=100.5,
               timeframe=Timeframe.H1)
    )
    connector.series[M5].append(
        Candle(timestamp=connector.series[M5][-1].timestamp
               + timedelta(minutes=5),
               open=100.0, high=100.4, low=99.8, close=100.2, timeframe=M5)
    )
    assert loop.run_once() == 1
    assert loop.htf_batches == 2


def test_live_loop_product_mode_refuses_to_start_without_htf(tmp_path):
    m5 = _make_series(M5, 60, start=START)
    connector = MultiTFFakeConnector({M5: m5})        # no H1/H4 at all
    runtime = MultiTFProductRuntime()
    loop, _runner = _live_stack(tmp_path, connector, runtime)

    assert loop.start() is False
    assert loop.arm_errors == 1
    assert "HTF probe failed" in (loop.last_arm_error or "" )
    assert Timeframe.H1 in connector.copy_calls or Timeframe.H4 in connector.copy_calls


def test_live_loop_degraded_mode_starts_and_reports_degraded(tmp_path):
    m5 = _make_series(M5, 60, start=START)
    connector = MultiTFFakeConnector({M5: m5})
    runtime = MultiTFProductRuntime(allow_single_tf_degraded=True)
    loop, _runner = _live_stack(tmp_path, connector, runtime)

    assert loop.start() is True
    assert loop.run_once() == 0                        # anchor
    connector.series[M5].append(
        Candle(timestamp=m5[-1].timestamp + timedelta(minutes=5),
               open=100.0, high=100.2, low=99.9, close=100.1, timeframe=M5)
    )
    assert loop.run_once() == 1
    assert loop.htf_batches == 1
    assert loop.last_report.degraded is True


# ---------------------------------------------------------------------- #
# 7 — paper delegation
# ---------------------------------------------------------------------- #
class _SpyRuntime:
    """Records run_batch kwargs; returns a sentinel report object."""

    def __init__(self) -> None:
        self.calls: list = []

    def run_batch(self, **kwargs):
        self.calls.append(kwargs)
        return "REPORT"


def _paper_runner(runtime):
    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=M5)
    return PaperRunner(connector=None, risk_engine=RiskEngine(), pipeline=adapter,
                       order_manager=None, position_manager=None,
                       runtime=runtime), adapter


def test_paper_arm_multi_tf_delegates_to_shared_runtime():
    spy = _SpyRuntime()
    runner, adapter = _paper_runner(spy)
    series = _htf_fixture()
    as_of = series[Timeframe.H1][-1].timestamp
    report = runner.arm_multi_tf(series, as_of=as_of)
    assert report == "REPORT"
    assert len(spy.calls) == 1
    call = spy.calls[0]
    assert call["engine"] is adapter.engine
    assert call["adapter"] is adapter
    assert call["arm_bar"] == 0                     # empty scan series
    # as_of trimming happened before the runtime saw the series.
    assert len(call["series_by_tf"][Timeframe.H1]) == len(
        build_htf_prefixes(series, as_of)[Timeframe.H1])


def test_paper_arm_multi_tf_requires_real_engine():
    class _StubAdapter:                              # protocol stub, no engine
        def attach(self, runner):
            return None

    runner = PaperRunner(connector=None, risk_engine=RiskEngine(),
                         pipeline=_StubAdapter(), order_manager=None,
                         position_manager=None, runtime=_SpyRuntime())
    with pytest.raises(RuntimeError):
        runner.arm_multi_tf({Timeframe.H4: [], Timeframe.H1: []})


# ---------------------------------------------------------------------- #
# 8 — operator config keeps detect==exec out of product mode
# ---------------------------------------------------------------------- #
def _write_config(tmp_path, payload: dict):
    path = tmp_path / "live.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_operator_config_defaults_and_c1_flags(tmp_path):
    cfg = load_operator_config(_write_config(tmp_path, {}))
    assert cfg.detection_timeframes == ("H4", "H1")
    assert cfg.allow_single_tf_degraded is False

    cfg2 = load_operator_config(_write_config(tmp_path, {
        "detection_timeframes": ["h4", "h1"],
        "allow_single_tf_degraded": True,
    }))
    assert cfg2.detection_timeframes == ("H4", "H1")
    assert cfg2.allow_single_tf_degraded is True


def test_operator_config_rejects_single_tf_detect_exec(tmp_path):
    path = _write_config(tmp_path, {"detection_timeframes": ["M5"]})
    with pytest.raises(ConfigError) as excinfo:
        load_operator_config(path)
    assert "single-TF detect+exec" in str(excinfo.value)

    # Explicit degraded opt-in is the only way through.
    cfg = load_operator_config(_write_config(tmp_path, {
        "detection_timeframes": ["M5"], "allow_single_tf_degraded": True,
    }))
    assert cfg.detection_timeframes == ("M5",)


def test_operator_config_rejects_unknown_or_malformed_detection_tfs(tmp_path):
    with pytest.raises(ConfigError):
        load_operator_config(_write_config(tmp_path, {
            "detection_timeframes": ["H4", "NOPE"],
        }))
    with pytest.raises(ConfigError):
        load_operator_config(_write_config(tmp_path, {
            "detection_timeframes": [],
        }))
    with pytest.raises(ConfigError):
        load_operator_config(_write_config(tmp_path, {
            "detection_timeframes": "H4",
        }))
