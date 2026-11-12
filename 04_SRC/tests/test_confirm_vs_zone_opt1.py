"""OPT-1 confirm-vs-zone enrichment tests (measure/export ONLY).

Design: 06_RESEARCH/CONFIRM_VS_ZONE_DESIGN.md (OPT-1, accepted 2026-11-07).
The enrichment joins the three reference frames the wider measures kept apart
(confirm-TF bar CLOSE / zone-anchored resting LIMIT / R7 submit-bar CLOSE) on
the menu winner stamp + one ``menu_confirm`` KPI record per winner.

What these tests pin:
  1. stamp fields populate on a synthetic menu win (H4 sweep → M15 confirm);
  2. the label taxonomy mirrors the FROZEN timing-study semantics on the
     locked ``ZONE_REFINEMENT_ATR`` band — read, never changed;
  3. the distance formula is the frozen timing-study convention
     (nearest zone edge, 0 inside, in ATR);
  4. missing/unresolvable inputs stay None (``UNLOCATABLE``) — never invented;
  5. the ``menu_confirm`` KPI record carries the stamp verbatim and is
     audit-only (absent/None on KPI-less runners — nothing fatals);
  6. OPT-B default OFF is untouched and the live flag stays false.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, POIState, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.config.model_type import ModelType
from smc.live.loop import LiveLoop
from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime
from smc.orchestration.product_menu_mtf import (
    LABEL_BEYOND_STOP_SIDE,
    LABEL_LATE,
    LABEL_ON_WINDOW,
    LABEL_OTHER,
    LABEL_UNLOCATABLE,
    ProductMenuEngine,
    completion_timing_label,
    completion_zone_edge_distance_atr,
)
from smc.paper.kpi_logger import KPILogger
from smc.triggers.base_trigger import (
    Trigger,
    TriggerContext,
    TriggerSignal,
)
from smc.triggers.trigger_router import TriggerRoute, TriggerRouter

ROOT = Path(__file__).resolve().parents[2]
BASE = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
H4_CLOSE = BASE + timedelta(hours=4)

ZONE_LOW = 2490.0
ZONE_HIGH = 2500.0


# --------------------------------------------------------------------------- #
# Fixtures (mirrors of test_product_menu_mtf's stubs — kept local on purpose)
# --------------------------------------------------------------------------- #
class StubTrigger(Trigger):
    """Fires on every evaluation with a configurable completion index."""

    type = TriggerType.A_CHOCH

    def __init__(self, fire: bool = True, completion_offset: int = 0) -> None:
        self.calls = 0
        self.fire = fire
        self.completion_offset = completion_offset  # 0 = newest bar (default)

    def evaluate(self, context: TriggerContext) -> TriggerSignal | None:
        self.calls += 1
        if not self.fire:
            return None
        index = context.bar_index + self.completion_offset  # may be out of range
        candle = context.candles[context.bar_index]
        return TriggerSignal(
            trigger=TriggerType.A_CHOCH,
            direction=Direction.LONG,
            entry_price=candle.close + 0.5,
            stop_reference=candle.low - 1.0,
            completion_index=index,
            expiry_bars=10,
            detail="stub-fire",
            data={"stub_index": index},
        )


def _bar(tf: Timeframe, offset_minutes: float, *, low=2485.0, high=2505.0,
         close=2500.0, open_=2496.0) -> Candle:
    return Candle(
        timestamp=BASE + timedelta(minutes=offset_minutes),
        open=open_, high=high, low=low, close=close, timeframe=tf,
    )


def _sweep(tf: Timeframe, offset_minutes: float = 0.0) -> Candle:
    """LONG sweep of the 2490..2500 demand zone: wick below, body back."""
    return _bar(tf, offset_minutes, low=2485.0, high=2498.0, close=2492.0)


def _calm(tf: Timeframe, offset_minutes: float) -> Candle:
    """Entirely inside the zone (no sweep geometry, constant 8.0 range)."""
    return _bar(tf, offset_minutes, low=2491.0, high=2499.0, close=2495.0)


def _confirm(tf: Timeframe, offset_minutes: float, *, close=2497.0) -> Candle:
    return _bar(tf, offset_minutes, low=2491.0, high=2499.0, close=close)


def _demand_poi(tf: Timeframe = Timeframe.H4, poi_id: str = "poi-1") -> POI:
    zone = Zone(top=ZONE_HIGH, bottom=ZONE_LOW, direction=Direction.LONG,
                timeframe=tf)
    return POI(
        zone=zone, models=[ModelType.M8], score=3.0, state=POIState.CREATED,
        m8_kind="demand_supply", id=poi_id,
    )


def _engine(tier_tf: Timeframe = Timeframe.H4, *, fire: bool = True,
            completion_offset: int = 0):
    engine = ProductMenuEngine(symbol="TEST")
    stub = StubTrigger(fire=fire, completion_offset=completion_offset)
    engine._router = TriggerRouter(triggers=[stub])
    poi = _demand_poi(tier_tf)
    assert engine.register_armed(poi, tier_tf) is True
    return engine, stub, poi


def _win_stamp(engine, confirm_series) -> dict:
    """Sweep → confirm replay; return the winner's product_menu stamp."""
    engine.on_execution_bar({Timeframe.H4: [_sweep(Timeframe.H4)]},
                            as_of=H4_CLOSE)
    winners = engine.on_execution_bar(
        {Timeframe.M15: list(confirm_series)},
        as_of=_close_ts(confirm_series[-1]),
    )
    assert len(winners) == 1
    return json.loads(winners[0].candidate.signal_data_json)["product_menu"]


def _close_ts(bar: Candle) -> datetime:
    return bar.timestamp + timedelta(minutes=bar.timeframe.minutes)


def _seeded_series(n_before: int) -> list[Candle]:
    """M15 stream: ``n_before`` in-zone bars inside the H4 sweep bar + 1 win."""
    bars = [_calm(Timeframe.M15, 15.0 * (i + 1)) for i in range(n_before)]
    bars.append(_confirm(Timeframe.M15, 300))   # opens 05:00, closes 05:15
    return bars


# --------------------------------------------------------------------------- #
# 1. Pure label semantics — the frozen timing-study taxonomy, no new numbers
# --------------------------------------------------------------------------- #
def test_label_on_window_is_the_band_inclusive():
    atr = 10.0
    # inside the zone → ON_WINDOW
    assert completion_timing_label(Direction.LONG, ZONE_LOW, ZONE_HIGH,
                                   2495.0, atr) is LABEL_ON_WINDOW
    # band edge is INCLUSIVE: 0.5 × ATR beyond the nearest edge stays ON_WINDOW
    assert completion_timing_label(Direction.LONG, ZONE_LOW, ZONE_HIGH,
                                   ZONE_HIGH + 0.5 * atr, atr) \
        is LABEL_ON_WINDOW
    assert completion_timing_label(Direction.SHORT, ZONE_LOW, ZONE_HIGH,
                                   ZONE_LOW - 0.5 * atr + 1e-9, atr) \
        is LABEL_ON_WINDOW
    # just past the band is not
    assert completion_timing_label(Direction.LONG, ZONE_LOW, ZONE_HIGH,
                                   ZONE_HIGH + 0.5 * atr + 1e-6, atr) \
        is LABEL_LATE


def test_label_late_is_the_displacement_side_direction_relative():
    atr = 10.0
    # LONG displaced ABOVE the zone = LATE (away from the protective stop)
    assert completion_timing_label(Direction.LONG, ZONE_LOW, ZONE_HIGH,
                                   2507.0, atr) is LABEL_LATE
    # SHORT displaced BELOW the zone = LATE (mirrored)
    assert completion_timing_label(Direction.SHORT, ZONE_LOW, ZONE_HIGH,
                                   2483.0, atr) is LABEL_LATE
    # the opposite sides are BEYOND_STOP_SIDE
    assert completion_timing_label(Direction.LONG, ZONE_LOW, ZONE_HIGH,
                                   2483.0, atr) is LABEL_BEYOND_STOP_SIDE
    assert completion_timing_label(Direction.SHORT, ZONE_LOW, ZONE_HIGH,
                                   2507.0, atr) is LABEL_BEYOND_STOP_SIDE


def test_label_other_and_unlocatable_never_invent():
    atr = 10.0
    assert completion_timing_label("sideways", ZONE_LOW, ZONE_HIGH,
                                   2507.0, atr) is LABEL_OTHER
    # missing zone bounds or non-positive ATR → UNLOCATABLE, never guessed
    assert completion_timing_label(Direction.LONG, None, ZONE_HIGH,
                                   2507.0, atr) is LABEL_UNLOCATABLE
    assert completion_timing_label(Direction.LONG, ZONE_LOW, ZONE_HIGH,
                                   2507.0, None) is LABEL_UNLOCATABLE
    assert completion_timing_label(Direction.LONG, ZONE_LOW, ZONE_HIGH,
                                   2507.0, 0.0) is LABEL_UNLOCATABLE
    assert completion_timing_label(Direction.LONG, ZONE_LOW, ZONE_HIGH,
                                   None, atr) is LABEL_UNLOCATABLE


def test_band_default_is_the_locked_zone_refinement_atr_read_not_changed():
    """0.5 × ATR beyond the edge is exactly the band → ON_WINDOW (inclusive).

    Pins that the default band comes from the locked constant read (the
    ``locked_constants.py`` diff stays empty — value used, not modified).
    """
    from smc.config.locked_constants import ZONE_REFINEMENT_ATR

    assert ZONE_REFINEMENT_ATR == 0.5
    atr = 4.0
    assert completion_timing_label(Direction.LONG, ZONE_LOW, ZONE_HIGH,
                                   ZONE_HIGH + 2.0, atr) is LABEL_ON_WINDOW
    assert completion_timing_label(Direction.LONG, ZONE_LOW, ZONE_HIGH,
                                   ZONE_HIGH + 2.1, atr) is LABEL_LATE
    # an explicit band must not silently override semantics
    assert completion_timing_label(
        Direction.LONG, ZONE_LOW, ZONE_HIGH, ZONE_HIGH + 3.0, atr,
        band_atr=0.75) is LABEL_ON_WINDOW


def test_distance_formula_is_nearest_edge_zero_inside():
    atr = 10.0
    assert completion_zone_edge_distance_atr(
        ZONE_LOW, ZONE_HIGH, 2495.0, atr) == 0.0
    assert completion_zone_edge_distance_atr(
        ZONE_LOW, ZONE_HIGH, ZONE_HIGH, atr) == 0.0
    assert completion_zone_edge_distance_atr(
        ZONE_LOW, ZONE_HIGH, 2510.0, atr) == pytest.approx(1.0)
    assert completion_zone_edge_distance_atr(
        ZONE_LOW, ZONE_HIGH, 2485.0, atr) == pytest.approx(0.5)
    # inverted bounds are normalised; unresolvable inputs stay None
    assert completion_zone_edge_distance_atr(
        ZONE_HIGH, ZONE_LOW, 2510.0, atr) == pytest.approx(1.0)
    assert completion_zone_edge_distance_atr(
        ZONE_LOW, ZONE_HIGH, 2500.0, None) is None
    assert completion_zone_edge_distance_atr(
        ZONE_LOW, ZONE_HIGH, None, atr) is None


# --------------------------------------------------------------------------- #
# 2. Stamp fields populate on a synthetic win (H4 sweep → M15 confirm)
# --------------------------------------------------------------------------- #
def test_winner_stamp_carries_completion_geometry():
    engine, _, poi = _engine(Timeframe.H4)
    series = _seeded_series(13)                    # 13 calm ≙ warm ATR + win
    stamp = _win_stamp(engine, series)

    # identity fields are unchanged from the frozen stamp
    assert stamp["menu"] == "PRODUCT_MTF_MENU"
    assert stamp["tier"] == "H4"
    assert stamp["detection_tf"] == "H4"
    assert stamp["confirmation_tf"] == "M15"
    assert stamp["poi_id"] == poi.id
    assert stamp["zone"] == [ZONE_LOW, ZONE_HIGH]
    assert stamp["sweep_ts"] == BASE.isoformat()

    # OPT-1 completion geometry: the winning M15 bar closes 05:15, its close
    # (2497.0) is INSIDE the zone → 0.0 distance, ON_WINDOW.
    assert stamp["zone_direction"] == "long"
    assert stamp["completion_index"] == 13
    assert stamp["completion_ts"] == (BASE + timedelta(hours=5,
                                                      minutes=15)).isoformat()
    assert stamp["completion_close"] == pytest.approx(2497.0)
    # constant 8.0-range series → Wilder seed ATR = 8.0 at the completion bar
    assert stamp["atr_at_confirm"] == pytest.approx(8.0)
    assert stamp["distance_at_confirm_atr"] == pytest.approx(0.0)
    assert stamp["label_at_confirm"] == LABEL_ON_WINDOW


def test_stamp_distances_are_measured_in_the_confirm_atr():
    """A close past the far edge reports its distance in ATR units.

    C3 note (master card §3.4): an out-of-zone completion is never
    in-between, so it can no longer WIN a menu episode (no candidate is
    built). The enrichment is report-only measurement; it is verified here
    directly on the same series instead of through a winner stamp.
    """
    engine, _, poi = _engine(Timeframe.H4)
    bars = _seeded_series(13)
    bars[-1] = _confirm(Timeframe.M15, 300, close=2520.0)  # 20 pts above 2500
    index = len(bars) - 1
    route = TriggerRoute(
        poi=poi,
        bar=index,
        signal=TriggerSignal(
            trigger=TriggerType.D_TWO_BAR_REVERSAL,
            direction=Direction.LONG,
            entry_price=2497.0,
            stop_reference=2490.0,
            completion_index=index,
            expiry_bars=10,
        ),
    )
    stamp = engine._completion_metrics(route, Timeframe.M15, bars, poi.zone)
    assert stamp["completion_close"] == pytest.approx(2520.0)
    atr = stamp["atr_at_confirm"]
    assert atr is not None and atr > 0
    assert stamp["distance_at_confirm_atr"] == pytest.approx(20.0 / atr)
    assert stamp["label_at_confirm"] == LABEL_LATE


# --------------------------------------------------------------------------- #
# 3. Missing / unresolvable completion → honest None, never invented
# --------------------------------------------------------------------------- #
def test_no_atr_yet_yields_unlocatable_without_invention():
    """A 1-bar confirm stream cannot resolve ATR → UNLOCATABLE, values None."""
    engine, _, _ = _engine(Timeframe.H4)
    stamp = _win_stamp(engine, [_confirm(Timeframe.M15, 300)])
    assert stamp["atr_at_confirm"] is None
    assert stamp["distance_at_confirm_atr"] is None
    assert stamp["label_at_confirm"] == LABEL_UNLOCATABLE
    # the completion bar itself is still materialised honestly
    assert stamp["completion_index"] == 0
    assert stamp["completion_ts"] == (BASE + timedelta(hours=5,
                                                      minutes=15)).isoformat()
    assert stamp["completion_close"] == pytest.approx(2497.0)


def test_out_of_range_completion_index_yields_unlocatable():
    engine, _, _ = _engine(Timeframe.H4, completion_offset=-99)
    stamp = _win_stamp(engine, _seeded_series(13))
    assert stamp["completion_index"] is None
    assert stamp["completion_ts"] is None
    assert stamp["completion_close"] is None
    assert stamp["atr_at_confirm"] is None
    assert stamp["distance_at_confirm_atr"] is None
    assert stamp["label_at_confirm"] == LABEL_UNLOCATABLE


# --------------------------------------------------------------------------- #
# 4. The menu_confirm KPI event (audit-only, one record per winner)
# --------------------------------------------------------------------------- #
class _Adapter:
    def __init__(self) -> None:
        self.queued: list = []

    def queue_menu_candidate(self, candidate):
        self.queued.append(candidate)


class _QueueRunner:
    def __init__(self, kpi=None) -> None:
        self.adapter = _Adapter()
        self.kpi = kpi


class _Connector:
    def connect(self) -> bool:
        return True

    def copy_rates(self, symbol, timeframe, start, count):
        return []


def _loop_with_kpi(kpi):
    menu = ProductMenuEngine(symbol="TEST")
    stub = StubTrigger()
    menu._router = TriggerRouter(triggers=[stub])
    assert menu.register_armed(_demand_poi(Timeframe.H4), Timeframe.H4)
    runtime = MultiTFProductRuntime(
        detection_timeframes=(Timeframe.D1, Timeframe.H4, Timeframe.H1,
                              Timeframe.M15),
    )
    series = {
        Timeframe.H4: [_sweep(Timeframe.H4)],             # closes 04:00
        Timeframe.D1: [],
        Timeframe.H1: [],
        Timeframe.M15: [],
        Timeframe.M1: [],
    }
    return LiveLoop(
        connector=_Connector(),
        runner=_QueueRunner(kpi=kpi),
        heartbeat=None,
        timeframe=Timeframe.M5,
        runtime=runtime,
        menu_confirmation=menu,
        htf_fetch=lambda tf, count: list(series.get(tf, ())),
    ), stub


def test_loop_records_one_menu_confirm_kpi_per_winner():
    kpi = KPILogger()
    loop, stub = _loop_with_kpi(kpi)
    bar = _bar(Timeframe.M5, 241)             # 04:01 → 04:06, a closed bar
    loop._drive_menu_confirmation(bar)

    assert stub.calls == 1
    records = [r for r in kpi.records if r.event == "menu_confirm"]
    assert len(records) == 1
    fields = records[0].fields
    assert fields["tier"] == "H4"
    assert fields["detection_tf"] == "H4"
    assert fields["confirmation_tf"] == "M5"
    assert fields["sweep_ts"] == BASE.isoformat()
    # the 1-bar M5 confirm stream cannot resolve ATR — honest None, no label
    # invention; the completion close of that bar is still reported
    assert fields["completion_close"] is not None
    assert fields["atr_at_confirm"] is None
    assert fields["distance_at_confirm_atr"] is None
    assert fields["label_at_confirm"] == LABEL_UNLOCATABLE
    # the winner was still queued — the KPI event changed nothing
    assert len(loop.runner.adapter.queued) == 1


def test_loop_without_kpi_skips_the_event_and_still_queues():
    loop, stub = _loop_with_kpi(None)
    bar = _bar(Timeframe.M5, 241)
    loop._drive_menu_confirmation(bar)        # must not raise
    assert stub.calls == 1
    assert len(loop.runner.adapter.queued) == 1


# --------------------------------------------------------------------------- #
# 5. Flag / default discipline — OPT-B untouched, live flag stays false
# --------------------------------------------------------------------------- #
def test_opt_b_flag_default_is_still_off():
    engine = ProductMenuEngine(symbol="TEST")
    assert engine.same_bar_asof is False
    # and it stays OFF with the same constructor used in production wiring
    engine2 = ProductMenuEngine(symbol="TEST", same_bar_asof=False)
    assert engine2.same_bar_asof is False


def test_live_demo_opt_b_flag_stays_false():
    cfg = json.loads((ROOT / "config" / "live_demo.json").read_text(
        encoding="utf-8"))
    assert cfg["enable_opt_b_same_bar_confirm"] is False
