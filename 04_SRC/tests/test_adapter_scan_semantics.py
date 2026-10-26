"""Per-bar trigger-scan semantics of the backtest PipelineAdapter (Phase B perf).

Pins the scan contract the full-October fidelity run depends on, after the
performance patch that replaced the adapter's every-bar full re-scan with a
guarded, exactly-once chronological scan (see ``PipelineAdapter._scan_cursor``):

1. GUARDED EXHAUSTION — a POI whose §24 give-up window is over
   (``arm_bar + poi_give_up_bars()``) stops triggering scan attempts
   entirely while its §5 feed keeps running; it must not re-derive the
   empty scan range with an O(n) swing detection every bar.
2. LOCKSTEP CURSOR — while seeking a route, each bar of the §24 window is
   evaluated exactly once, in order, with the honest prefix ending at that
   bar (the old path re-scanned arm→now every bar).
3. EXACT FIRST-FIRE — resuming the scan from the cursor returns the same
   first route a full re-scan from the arm bar returns (safe because every
   trigger evaluation at bar b depends only on candles ≤ b — the engine's
   no-lookahead contract).

The scenarios drive a REAL PipelineEngine + PipelineAdapter with a
recording stub trigger (no detection stack), feeding calm bars above the
POI zone so the POI stays FRESH and nothing else interferes with the scan.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from smc.backtest.pipeline_adapter import PipelineAdapter
from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, POIState, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.detection.structural_swing_detector import detect_swings
from smc.orchestration.engine import PipelineEngine
from smc.triggers.base_trigger import Trigger, TriggerContext, TriggerSignal
from smc.triggers.trigger_expiry import poi_give_up_bars

TF = Timeframe.M5
START = datetime(2026, 3, 12, 9, 0, tzinfo=timezone.utc)  # Thursday, London
GIVE_UP = poi_give_up_bars()  # §24 POI-wide window (20 bars, Trigger A's)

CALM = (100.4, 100.6, 100.3, 100.5)            # above the zone — no §5 event
TOUCH = (100.15, 100.25, 100.05, 100.2)        # low inside [100.0, 100.2]


class RecordingTrigger(Trigger):
    """Trigger-D stand-in: records every evaluation, optionally fires once."""

    type = TriggerType.D_TWO_BAR_REVERSAL
    name = "recording"

    def __init__(self, fire_at: int | None = None) -> None:
        self.seen: list[tuple[int, int]] = []  # (bar_index, prefix_len)
        self.fire_at = fire_at

    def evaluate(self, context: TriggerContext) -> TriggerSignal | None:
        self.seen.append((context.bar_index, len(context.candles)))
        if self.fire_at is not None and context.bar_index == self.fire_at:
            return TriggerSignal(
                trigger=self.type,
                direction=Direction.LONG,
                entry_price=100.1,
                stop_reference=99.9,
                completion_index=context.bar_index,
                expiry_bars=10,
                detail="recorded",
            )
        return None


def _candles(rows: list[tuple[float, ...]]) -> list[Candle]:
    return [
        Candle(
            timestamp=START + timedelta(minutes=5 * i),
            open=row[0],
            high=row[1],
            low=row[2],
            close=row[3],
            volume=0.0,
            timeframe=TF,
        )
        for i, row in enumerate(rows)
    ]


def _fitted_adapter(rows: list[tuple[float, ...]], fire_at: int | None):
    """Fresh engine + adapter + armed LONG POI with the recording trigger."""
    candles = _candles(rows)
    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=TF)
    adapter.set_candles(candles)
    stub = RecordingTrigger(fire_at=fire_at)
    engine.router._by_type[TriggerType.D_TWO_BAR_REVERSAL] = stub
    engine.router.eligible_types = lambda poi: [TriggerType.D_TWO_BAR_REVERSAL]
    poi = POI(
        zone=Zone(top=100.2, bottom=100.0, direction=Direction.LONG, timeframe=TF),
        models=[ModelType.M1],
    )
    engine.arm_at(poi, arm_bar=0)
    return engine, adapter, poi, stub, candles


def _drive(adapter: PipelineAdapter, candles: list[Candle], upto: int) -> None:
    for index in range(upto + 1):
        adapter.generate_candidates(candles[index], index, candles[index].timestamp)


def test_poi_past_give_up_window_stops_scanning_but_keeps_section5_feed():
    """After arm+GIVE_UP the scan is retired (no evaluations, no O(n) swings)
    while the §5 feed keeps transitioning the POI (touch → TESTED)."""
    rows = [CALM] * (GIVE_UP + 1) + [TOUCH] * 4  # touch only AFTER exhaustion
    engine, adapter, poi, stub, candles = _fitted_adapter(rows, fire_at=None)

    _drive(adapter, candles, len(rows) - 1)

    # Evaluated exactly once per bar through the last window bar (arm 0 +
    # GIVE_UP inclusive), never after — the old path re-scanned every bar.
    assert stub.seen == [(b, b + 1) for b in range(GIVE_UP + 1)]
    # The §5 feed still ran for the exhausted POI: the post-window touch
    # moved it FRESH → TESTED.
    assert engine.state_machine.current(poi) is POIState.TESTED
    # Scan bookkeeping retired, §11 one-shot marked (never seeks again).
    assert poi.id in adapter._routed
    assert poi.id not in adapter._scan_cursor


def test_route_seek_evaluates_each_window_bar_exactly_once_then_stops():
    """While seeking, each §24-window bar is evaluated exactly once in order
    with its honest prefix; after the fire, no further evaluations happen."""
    fire_at = 3
    rows = [CALM] * 7  # well inside the give-up window
    engine, adapter, poi, stub, candles = _fitted_adapter(rows, fire_at=fire_at)

    _drive(adapter, candles, len(rows) - 1)

    assert stub.seen == [(b, b + 1) for b in range(fire_at + 1)]
    # One-shot consumed: the workflow exists and the scan cursor is cleared.
    workflow = adapter._workflows[poi.id]
    assert workflow.completion_index == fire_at
    assert workflow.expiry_bars == 10
    assert workflow.created_bar == fire_at
    assert poi.id in adapter._routed
    assert poi.id not in adapter._scan_cursor


def test_incremental_cursor_returns_the_same_first_route_as_full_rescan():
    """The cursor-resumed scan fires the same first route a full re-scan
    from the arm bar returns (no-lookahead contract → order independence)."""
    fire_at = 3
    rows = [CALM] * 7
    engine, adapter, poi, _stub, candles = _fitted_adapter(rows, fire_at=fire_at)

    _drive(adapter, candles, fire_at)  # cursor path: one bar per call

    workflow = adapter._workflows[poi.id]
    reference = engine.scan_route(
        poi,
        candles[: fire_at + 1],
        detect_swings(candles[: fire_at + 1], TF),
        to_bar=fire_at,  # full re-scan from the arm bar
    )
    assert reference is not None
    assert workflow.completion_index == reference.signal.completion_index
    assert workflow.expiry_bars == reference.signal.expiry_bars
    assert workflow.candidate.entry_price == reference.signal.entry_price
    assert workflow.candidate.sl_price == reference.signal.stop_reference
