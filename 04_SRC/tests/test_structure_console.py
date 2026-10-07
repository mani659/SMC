"""Milestone L1 — live structure console tests (fake snapshots, no MT5).

Covers the directive's four console sections (POIS / SWEEPS / SEEKING /
PLAN), the honest-empty contract, the read-only snapshot builder, the
sweep-link retention seam (runtime report → LiveLoop), and the adapter's
public workflow accessor. Weekly rows are LIVE snapshot data — the tests
pin that the rendered W1 row carries the actual synthetic zone numbers,
never hardcoded demo rows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from smc.backtest.pipeline_adapter import PipelineAdapter, _Workflow
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.live.loop import LiveLoop
from smc.live.structure_console import (
    build_structure_snapshot,
    render_structure_console,
)
from smc.orchestration.engine import PipelineEngine
from smc.orchestration import multi_tf_runtime as runtime_module
from smc.orchestration.multi_tf import MultiTFDriverResult, PerTFResult

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def _poi(top, bottom, direction, tf, kind=None,
         models=(ModelType.M1,)) -> POI:
    return POI(
        zone=Zone(top=top, bottom=bottom, direction=direction, timeframe=tf),
        models=list(models),
        m8_kind=kind,
    )


def _engine_with_pois(*pois) -> PipelineEngine:
    engine = PipelineEngine()
    for i, poi in enumerate(pois):
        engine.arm_at(poi, arm_bar=i)
    return engine


def _fake_candidate(**overrides) -> SimpleNamespace:
    base = dict(
        direction=Direction.LONG,
        entry_price=2345.0,
        sl_price=2338.0,
        tp_price=2360.0,
        tp_source="structural_swing",
        trigger=SimpleNamespace(value="A"),
        poi_id="aaaaaaaa-1111-2222-3333-444444444444",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class _FakeAdapter:
    """Duck-typed adapter exposing only active_workflows()."""

    def __init__(self, workflows: dict) -> None:
        self._workflows = workflows

    def active_workflows(self) -> dict:
        return dict(self._workflows)


# ---------------------------------------------------------------------- #
# POIS section — grouped by TF, W1 rows are LIVE data
# ---------------------------------------------------------------------- #
def test_snapshot_groups_pois_and_w1_row_is_live_data():
    w1 = _poi(2355.5, 2340.1, Direction.LONG, Timeframe.W1, kind="ob")
    d1 = _poi(2360.0, 2350.0, Direction.SHORT, Timeframe.D1, kind="demand_supply")
    engine = _engine_with_pois(w1, d1)
    snapshot = build_structure_snapshot(engine=engine, now=NOW)

    tfs = [row["tf"] for row in snapshot["pois"]]
    assert tfs == ["W1", "D1"]                       # tracked order preserved
    w1_row = snapshot["pois"][0]
    assert w1_row["zone_low"] == pytest.approx(2340.1)
    assert w1_row["zone_high"] == pytest.approx(2355.5)
    assert w1_row["direction"] == "LONG"
    assert w1_row["kind"] == "ob"
    assert w1_row["armed"] is True
    assert w1_row["id_short"] == w1.id[:8]
    assert w1_row["state"] in {"CREATED", "FRESH", "TESTED", "VIOLATED"}

    board = render_structure_console(snapshot)
    # The W1 row carries the ACTUAL zone numbers (live, not hardcoded).
    assert "2340.10-2355.50" in board
    assert "W1" in board and "D1" in board and "H4" in board and "H1" in board
    assert "H1 : (none)" in board                    # honest empty section
    assert board.isascii()


def test_empty_engine_renders_honest_empty_sections():
    snapshot = build_structure_snapshot(engine=PipelineEngine(), now=NOW)
    board = render_structure_console(snapshot)
    for tf in ("W1", "D1", "H4", "H1"):
        assert f"{tf} : (none)" in board
    assert "SWEEPS: none" in board
    assert "SEEKING: none" in board
    assert "PLAN: none" in board
    assert board.isascii()


# ---------------------------------------------------------------------- #
# SWEEPS section — linked POI + TF + side, or none
# ---------------------------------------------------------------------- #
def test_sweeps_link_to_tracked_pois():
    w1 = _poi(2355.5, 2340.1, Direction.LONG, Timeframe.W1, kind="ob")
    engine = _engine_with_pois(w1)
    sweeps = {
        w1.id: {"side": "LONG", "magnitude_atr": 1.42, "passed": True},
        "dead-poi-id": {"side": "SHORT", "magnitude_atr": 0.9},
    }
    snapshot = build_structure_snapshot(engine=engine, sweeps=sweeps, now=NOW)
    assert len(snapshot["sweeps"]) == 1              # untracked links dropped
    row = snapshot["sweeps"][0]
    assert row["tf"] == "W1" and row["side"] == "LONG"
    assert row["id_short"] == w1.id[:8]
    board = render_structure_console(snapshot)
    assert "side=LONG" in board and "1.42x ATR" in board
    assert "SWEEPS: none" not in board


def test_sweeps_none_when_no_links():
    engine = _engine_with_pois(_poi(100.0, 95.0, Direction.SHORT, Timeframe.H4))
    snapshot = build_structure_snapshot(engine=engine, now=NOW)
    assert snapshot["sweeps"] == []
    assert "SWEEPS: none" in render_structure_console(snapshot)


# ---------------------------------------------------------------------- #
# SEEKING section — armed POIs, state/posture, targeted trigger letter
# ---------------------------------------------------------------------- #
def test_seeking_lists_state_posture_and_targeted_trigger():
    h4 = _poi(101.0, 99.0, Direction.LONG, Timeframe.H4)
    engine = _engine_with_pois(h4)
    adapter = _FakeAdapter({h4.id: _fake_candidate(poi_id=h4.id)})
    snapshot = build_structure_snapshot(engine=engine, adapter=adapter, now=NOW)
    row = snapshot["pois"][0]
    assert row["trigger"] == "A"                     # targeted confirmation
    board = render_structure_console(snapshot)
    assert "SEEKING" in board
    assert f"trigger=A" in board
    assert "posture=" in board and "state=" in board


def test_seeking_without_adapter_shows_no_trigger():
    engine = _engine_with_pois(_poi(101.0, 99.0, Direction.LONG, Timeframe.H1))
    snapshot = build_structure_snapshot(engine=engine, now=NOW)
    assert snapshot["pois"][0]["trigger"] is None
    board = render_structure_console(snapshot)
    assert "trigger=-" in board                      # honest: no route yet


# ---------------------------------------------------------------------- #
# PLAN section — only when a candidate/route exists
# ---------------------------------------------------------------------- #
def test_plan_renders_candidate_fields():
    h4 = _poi(101.0, 99.0, Direction.LONG, Timeframe.H4)
    engine = _engine_with_pois(h4)
    candidate = _fake_candidate(
        poi_id=h4.id, trigger=SimpleNamespace(value="D"),
        tp_source="atr_fallback", tp_price=102.5,
    )
    snapshot = build_structure_snapshot(
        engine=engine, adapter=_FakeAdapter({h4.id: candidate}), now=NOW)
    plan = snapshot["plan"]
    assert len(plan) == 1
    assert plan[0]["direction"] == "LONG"
    assert plan[0]["entry"] == pytest.approx(2345.0)
    assert plan[0]["sl"] == pytest.approx(2338.0)
    assert plan[0]["tp"] == pytest.approx(102.5)
    assert plan[0]["tp_source"] == "atr_fallback"
    assert plan[0]["trigger"] == "D"
    board = render_structure_console(snapshot)
    assert "entry=2345.00" in board and "sl=2338.00" in board
    assert "tp=102.50" in board and "src=atr_fallback" in board
    assert "trig=D" in board and f"poi={h4.id[:8]}" in board


def test_plan_none_without_workflows():
    engine = _engine_with_pois(_poi(101.0, 99.0, Direction.LONG, Timeframe.H4))
    snapshot = build_structure_snapshot(engine=engine, now=NOW)
    assert snapshot["plan"] == []
    assert "PLAN: none" in render_structure_console(snapshot)


# ---------------------------------------------------------------------- #
# Seams: adapter accessor + sweep-link retention
# ---------------------------------------------------------------------- #
def test_adapter_active_workflows_returns_candidate_copy():
    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=Timeframe.M5)
    poi = _poi(101.0, 99.0, Direction.LONG, Timeframe.H4)
    candidate = _fake_candidate(poi_id=poi.id)
    adapter._workflows[poi.id] = _Workflow(
        candidate=candidate, created_bar=3, completion_index=2, expiry_bars=20,
    )
    snapshot = adapter.active_workflows()
    assert snapshot[poi.id] is candidate
    snapshot.clear()                                 # a copy — no aliasing
    assert poi.id in adapter._workflows


def _fabricated_result(poi: POI, displacement) -> MultiTFDriverResult:
    per_tf = {
        Timeframe.H4: PerTFResult(timeframe=Timeframe.H4, detected_raw=1,
                                  merged=1, passed=1, first_failure={},
                                  skipped_models={}),
    }
    details = {
        Timeframe.H4: {"passed": [poi], "results": [],
                       "disp_map": {poi.id: displacement}},
    }
    return MultiTFDriverResult(per_tf=per_tf, single_tf_detect_exec=False,
                               degraded=False, errors={}, details=details)


class _FakeDriver:
    result = None

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def validate_multi(self, series, engine=None, return_details=False):
        return type(self).result


def test_runtime_report_collects_sweep_links(monkeypatch):
    poi = _poi(101.0, 99.0, Direction.LONG, Timeframe.H4)
    displacement = SimpleNamespace(direction=Direction.LONG,
                                   magnitude_atr=1.42, passed=True)
    _FakeDriver.result = _fabricated_result(poi, displacement)
    monkeypatch.setattr(runtime_module, "MultiTFDetectionDriver", _FakeDriver)

    from datetime import timedelta
    start = datetime(2026, 1, 5, tzinfo=timezone.utc)
    candles = [
        SimpleNamespace(timestamp=start + i * timedelta(minutes=60),
                        timeframe=Timeframe.H1)
        for i in range(10)
    ]
    series = {
        Timeframe.H4: [SimpleNamespace(timestamp=start + i * timedelta(minutes=240),
                                       timeframe=Timeframe.H4)
                       for i in range(10)],
        Timeframe.H1: candles,
    }
    runtime = runtime_module.MultiTFProductRuntime()
    report = runtime.run_batch(engine=PipelineEngine(), series_by_tf=series,
                               as_of=candles[-1].timestamp, arm_bar=0)
    link = report.displacements.get(poi.id)
    assert link is not None
    assert link["side"] == "LONG"
    assert link["magnitude_atr"] == pytest.approx(1.42)


class _FakeRunner:
    def __init__(self, report) -> None:
        self._report = report

    def run_one_cycle(self, bar):
        return None

    def arm_multi_tf(self, series, *, as_of, arm_bar, execution_candles=None):
        return self._report


class _FakeConnector:
    def connect(self):
        return True

    def copy_rates(self, symbol, tf, start, count):
        return []


class _FakeHeartbeat:
    def maybe_publish(self):
        return False

    def publish_shutdown(self):
        return None


def test_live_loop_merges_sweep_links_from_report():
    report = SimpleNamespace(
        armed=[], armed_count=0, displacements={
            "poi-1": {"side": "SHORT", "magnitude_atr": 0.8},
        },
        summary=lambda: {},
    )
    loop = LiveLoop(connector=_FakeConnector(), runner=_FakeRunner(report),
                    driver=None, heartbeat=_FakeHeartbeat(),
                    symbol="XAUUSD.x", timeframe=Timeframe.M5,
                    runtime=runtime_module.MultiTFProductRuntime(
                        allow_single_tf_degraded=True))
    loop._window = [SimpleNamespace(timestamp=datetime(2026, 1, 5, tzinfo=timezone.utc),
                                    timeframe=Timeframe.M5)]
    loop._started = True
    loop._detect_and_arm(SimpleNamespace(
        timestamp=datetime(2026, 1, 5, 0, 5, tzinfo=timezone.utc),
        timeframe=Timeframe.M5))
    assert loop.sweep_links["poi-1"]["side"] == "SHORT"
    assert loop.htf_batches == 1
