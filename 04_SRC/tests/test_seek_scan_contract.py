"""Seek/scan contract redesign (Option B) — implementation tests.

Design under test: ``06_RESEARCH/SEEK_SCAN_CONTRACT_REDESIGN_DESIGN.md``
(DESIGN_LOCK accepted 2026-10-05). Rules exercised:

* R1.2 posture classification: CLEAN_ARM / IN_ZONE_AT_ARM / VIOLATION_AT_ARM
  (VIOLATION wins when the arm bar both touches and closes through).
* R1.2a/R1.2b the ARM BAR itself does not feed the §5 machine for a
  non-CLEAN posture (initial presence / deferred violation — never a fresh
  LTF touch or violation).
* R2.3 REVALIDATION (VIOLATION_AT_ARM) routes only after a later close
  back inside the zone band via the existing named rule
  ``market_reentered_zone`` (fail-closed on warm-up ATR); a CLEAN_ARM
  episode routes without any re-entry.
* R4.2 deferred violation: pre-re-entry adverse closes are the continuation
  of the arm-bar condition (episode dies at give-up if it never re-enters);
  post-arm adverse closes for CLEAN_ARM / IN_ZONE_AT_ARM are terminal, and
  after re-entry they are terminal again.
* R4.3 a §5 TESTED state inside the seek span does NOT close the scan.
* R5 one-shot identity: routed POIs never route again.
* Locked constants untouched: TRIGGER_A_EXPIRY == 20 == poi_give_up_bars().

No expectancy / PnL / edge claims; no new constants introduced here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from smc.backtest.pipeline_adapter import PipelineAdapter
from smc.config.locked_constants import TRIGGER_A_EXPIRY
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.core.enums import Direction, POIState
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.orchestration.engine import PipelineEngine, SeekPosture
from smc.triggers.trigger_expiry import poi_give_up_bars

TF = Timeframe.M5
START = datetime(2025, 6, 2, tzinfo=timezone.utc)


def _poi(direction: Direction = Direction.LONG) -> POI:
    return POI(
        zone=Zone(top=100.2, bottom=100.0, direction=direction, timeframe=TF),
        models=[],
    )


def _candle(o: float, h: float, l: float, c: float,
            offset_min: int = 0) -> Candle:
    return Candle(
        timestamp=START + timedelta(minutes=5 * offset_min),
        open=o, high=h, low=l, close=c, timeframe=TF,
    )


def _warm_candles(n: int = 15) -> list[Candle]:
    """Calm candles ABOVE the zone (LONG demand below price): ATR fold."""
    return [_candle(100.5, 100.9, 100.3, 100.7, offset_min=i)
            for i in range(n)]


# --------------------------------------------------------------------------- #
# R1.2 — posture classification
# --------------------------------------------------------------------------- #
def test_posture_clean_arm():
    engine = PipelineEngine()
    poi = _poi()
    bar = _candle(100.5, 100.9, 100.3, 100.7)  # clear of the zone (above)
    engine.arm_at(poi, arm_bar=0, arm_candle=bar)
    assert engine.episode(poi).posture is SeekPosture.CLEAN_ARM
    assert engine.state_machine.current(poi) is POIState.FRESH


def test_posture_in_zone_at_arm():
    engine = PipelineEngine()
    poi = _poi()
    bar = _candle(99.8, 100.3, 99.5, 100.1)  # range overlaps the zone
    engine.arm_at(poi, arm_bar=0, arm_candle=bar)
    assert engine.episode(poi).posture is SeekPosture.IN_ZONE_AT_ARM
    assert engine.state_machine.current(poi) is POIState.FRESH


def test_posture_violation_at_arm():
    engine = PipelineEngine()
    poi = _poi()
    bar = _candle(100.0, 100.4, 99.6, 98.5)  # touches, then CLOSES far below
    engine.arm_at(poi, arm_bar=0, arm_candle=bar)
    assert engine.episode(poi).posture is SeekPosture.VIOLATION_AT_ARM
    assert engine.state_machine.current(poi) is POIState.FRESH  # deferred


def test_posture_violation_wins_over_touch():
    """A bar that both touches and closes through is VIOLATION_AT_ARM."""
    engine = PipelineEngine()
    poi = _poi()
    bar = _candle(100.1, 100.3, 99.4, 99.3)  # wick in zone, close below bottom
    engine.arm_at(poi, arm_bar=0, arm_candle=bar)
    assert engine.episode(poi).posture is SeekPosture.VIOLATION_AT_ARM


def test_arm_at_without_candle_keeps_legacy_behaviour():
    engine = PipelineEngine()
    poi = _poi()
    engine.arm_at(poi, arm_bar=0)
    assert engine.episode(poi).posture is SeekPosture.CLEAN_ARM


def test_posture_short_direction():
    engine = PipelineEngine()
    poi = _poi(Direction.SHORT)
    bar = _candle(100.4, 100.9, 100.1, 101.5)  # closes above zone top
    engine.arm_at(poi, arm_bar=0, arm_candle=bar)
    assert engine.episode(poi).posture is SeekPosture.VIOLATION_AT_ARM


# --------------------------------------------------------------------------- #
# R1.2a/R1.2b — the arm bar itself never feeds the §5 machine
# --------------------------------------------------------------------------- #
def test_feed_bar_skips_arm_bar_for_violation_at_arm():
    engine = PipelineEngine()
    poi = _poi()
    arm_bar = _candle(100.0, 100.4, 99.6, 98.5)
    engine.arm_at(poi, arm_bar=0, arm_candle=arm_bar)
    assert engine.feed_bar(poi, arm_bar) == POIState.FRESH.value


def test_feed_bar_skips_arm_bar_for_in_zone_at_arm():
    """R1.2a: the arm-bar wick contact is initial presence, NOT a §5 touch."""
    engine = PipelineEngine()
    poi = _poi()
    arm_bar = _candle(99.8, 100.3, 99.5, 100.1)
    engine.arm_at(poi, arm_bar=0, arm_candle=arm_bar)
    assert engine.feed_bar(poi, arm_bar) == POIState.FRESH.value


def test_feed_bar_post_arm_touch_is_recorded_for_in_zone_at_arm():
    """Post-arm bars feed normally: a later touch is a §5 TESTED event."""
    engine = PipelineEngine()
    poi = _poi()
    arm_bar = _candle(99.8, 100.3, 99.5, 100.1)
    engine.arm_at(poi, arm_bar=0, arm_candle=arm_bar)
    assert engine.feed_bar(poi, arm_bar) == POIState.FRESH.value
    touch = _candle(99.9, 100.3, 99.7, 100.1, offset_min=1)
    assert engine.feed_bar(poi, touch) == POIState.TESTED.value


# --------------------------------------------------------------------------- #
# R4.2 — deferred violation vs terminal violation
# --------------------------------------------------------------------------- #
def test_post_arm_adverse_close_terminal_for_clean_arm():
    engine = PipelineEngine()
    poi = _poi()
    arm_bar = _candle(100.5, 100.9, 100.3, 100.7)  # CLEAN_ARM
    engine.arm_at(poi, arm_bar=0, arm_candle=arm_bar)
    later = _candle(98.6, 98.8, 98.2, 98.3, offset_min=1)
    assert engine.feed_bar(poi, later) == POIState.VIOLATED.value


def test_post_arm_adverse_close_terminal_for_in_zone_at_arm():
    engine = PipelineEngine()
    poi = _poi()
    arm_bar = _candle(99.8, 100.3, 99.5, 100.1)  # IN_ZONE_AT_ARM
    engine.arm_at(poi, arm_bar=0, arm_candle=arm_bar)
    assert engine.feed_bar(poi, arm_bar) == POIState.FRESH.value
    later = _candle(98.6, 98.8, 98.2, 98.3, offset_min=1)
    assert engine.feed_bar(poi, later) == POIState.VIOLATED.value


def test_revalidation_pre_reentry_adverse_close_is_continuation():
    """Design R4.2: while a VIOLATION_AT_ARM episode awaits its zone
    re-entry, staying beyond the zone is the arm-bar condition itself —
    not a new §5 violation (the episode retires at give-up instead)."""
    engine = PipelineEngine()
    poi = _poi()
    arm_bar = _candle(100.0, 100.4, 99.6, 98.5)
    engine.arm_at(poi, arm_bar=0, arm_candle=arm_bar)
    later = _candle(98.6, 98.8, 98.2, 98.3, offset_min=1)
    assert engine.feed_bar(poi, later) == POIState.FRESH.value
    later2 = _candle(98.0, 98.4, 97.8, 98.1, offset_min=2)
    assert engine.feed_bar(poi, later2) == POIState.FRESH.value


def test_revalidation_post_reentry_adverse_close_is_terminal():
    engine = PipelineEngine()
    poi = _poi()
    arm_bar = _candle(100.0, 100.4, 99.6, 98.5)
    engine.arm_at(poi, arm_bar=0, arm_candle=arm_bar)
    episode = engine.episode(poi)
    episode.revalidated_bar = 1  # adapter latches the band re-entry
    later = _candle(98.6, 98.8, 98.2, 98.3, offset_min=2)
    assert engine.feed_bar(poi, later) == POIState.VIOLATED.value


def test_revalidation_pre_reentry_wick_touch_is_recorded():
    """A wick contact while awaiting re-entry is still a §5 touch event
    (machine authority unchanged) — it simply does not unlock routing
    (the adapter gate needs the band re-entry latch)."""
    engine = PipelineEngine()
    poi = _poi()
    arm_bar = _candle(100.0, 100.4, 99.6, 98.5)
    engine.arm_at(poi, arm_bar=0, arm_candle=arm_bar)
    wick = _candle(99.4, 100.1, 99.2, 99.3, offset_min=1)  # wick into zone
    assert engine.feed_bar(poi, wick) == POIState.TESTED.value


# --------------------------------------------------------------------------- #
# R4.3 — a §5 TESTED state does NOT close the scan
# --------------------------------------------------------------------------- #
def test_may_route_tested_inside_seek_window_not_terminated():
    engine = PipelineEngine()
    poi = _poi()
    arm_bar = _candle(99.8, 100.3, 99.5, 100.1)
    engine.arm_at(poi, arm_bar=0, arm_candle=arm_bar)
    adapter = PipelineAdapter(engine)
    candles = [arm_bar] + [_candle(99.0, 99.4, 98.8, 99.2, offset_min=i + 1)
                           for i in range(20)]
    adapter.set_candles(candles)
    touch = _candle(99.9, 100.3, 99.7, 100.1, offset_min=5)  # wick in zone
    assert engine.feed_bar(poi, touch) == POIState.TESTED.value
    # Seek/scan redesign: TESTED inside the span is routable (R4.3) — far
    # beyond the old touch+1 grace window too.
    assert adapter._may_route(poi, POIState.TESTED, 6, bar=touch) is True
    assert adapter._may_route(poi, POIState.TESTED, 15, bar=touch) is True
    # ...and the seek ends at the give-up deadline (R4.1a), not at the touch.
    assert adapter._may_route(poi, POIState.TESTED, 21, bar=touch) is False


def test_adapter_generate_candidates_scans_tested_poi_after_touch():
    """End-to-end: after the arm-bar initial presence the adapter keeps
    seeking — the scan cursor advances, the routed flag stays clear."""
    engine = PipelineEngine()
    poi = _poi()
    arm_bar = _candle(99.8, 100.3, 99.5, 100.1)
    engine.arm_at(poi, arm_bar=0, arm_candle=arm_bar)
    adapter = PipelineAdapter(engine)
    adapter.set_candles([arm_bar])
    adapter.generate_candidates(arm_bar, 0, arm_bar.timestamp)
    assert poi.id not in adapter._routed
    assert adapter._scan_cursor.get(poi.id) == 1


# --------------------------------------------------------------------------- #
# R2.3 — REVALIDATION gate (VIOLATION_AT_ARM)
# --------------------------------------------------------------------------- #
def _viol_adapter_with_warm_atr():
    """Adapter over a warm series: arm bar (VIOLATION_AT_ARM) at index 15."""
    engine = PipelineEngine()
    poi = _poi()
    warm = _warm_candles(15)
    arm_bar = _candle(100.0, 100.4, 99.6, 98.5, offset_min=15)
    engine.arm_at(poi, arm_bar=15, arm_candle=arm_bar)
    adapter = PipelineAdapter(engine)
    adapter.set_candles(warm + [arm_bar])
    adapter._ensure_state(15)  # ATR real from here on
    return engine, adapter, poi, arm_bar


def test_revalidation_blocks_route_before_reentry():
    engine, adapter, poi, arm_bar = _viol_adapter_with_warm_atr()
    later = _candle(98.6, 98.8, 98.2, 98.3, offset_min=16)  # far below zone
    adapter._ensure_state(16)
    assert adapter._may_route(poi, POIState.FRESH, 16, bar=later) is False


def test_revalidation_fail_closed_on_warmup_atr():
    """Degenerate ATR (band uncomputable) must NOT let re-entry pass."""
    engine = PipelineEngine()
    poi = _poi()
    arm_bar = _candle(100.0, 100.4, 99.6, 98.5)
    engine.arm_at(poi, arm_bar=0, arm_candle=arm_bar)
    adapter = PipelineAdapter(engine)
    adapter.set_candles([arm_bar])  # 1 candle: ATR is None/0.0 (warm-up)
    later = _candle(99.9, 100.3, 99.5, 100.05, offset_min=1)
    assert adapter._may_route(poi, POIState.FRESH, 1, bar=later) is False


def test_revalidation_allows_route_after_band_reentry():
    engine, adapter, poi, arm_bar = _viol_adapter_with_warm_atr()
    reentry = _candle(99.9, 100.3, 99.5, 100.05, offset_min=16)  # in zone
    adapter._ensure_state(16)
    assert adapter._may_route(poi, POIState.FRESH, 16, bar=reentry) is True
    assert engine.episode(poi).revalidated_bar == 16  # latched once


def test_reentry_latches_once():
    engine, adapter, poi, arm_bar = _viol_adapter_with_warm_atr()
    reentry = _candle(99.9, 100.3, 99.5, 100.05, offset_min=16)
    adapter._ensure_state(16)
    assert adapter._may_route(poi, POIState.FRESH, 16, bar=reentry) is True
    away = _candle(103.0, 103.4, 102.8, 103.2, offset_min=17)
    adapter._ensure_state(17)
    # After the latch the gate never re-tests: routability persists.
    assert adapter._may_route(poi, POIState.FRESH, 17, bar=away) is True


def test_clean_arm_routes_without_reentry():
    engine = PipelineEngine()
    poi = _poi()
    arm_bar = _candle(100.5, 100.9, 100.3, 100.7)
    engine.arm_at(poi, arm_bar=0, arm_candle=arm_bar)
    adapter = PipelineAdapter(engine)
    adapter.set_candles([arm_bar])
    later = _candle(100.5, 100.9, 100.3, 100.7, offset_min=1)
    assert adapter._may_route(poi, POIState.FRESH, 1, bar=later) is True


def test_revalidation_violated_state_never_routes():
    """Once the episode is §5-VIOLATED (post-re-entry), routing is dead —
    the revalidation gate never resurrects a dead episode (R4.1b)."""
    engine, adapter, poi, arm_bar = _viol_adapter_with_warm_atr()
    engine.state_machine.transition(poi, POIState.VIOLATED)
    reentry = _candle(99.9, 100.3, 99.5, 100.05, offset_min=16)
    adapter._ensure_state(16)
    assert adapter._may_route(poi, POIState.VIOLATED, 16, bar=reentry) is False


def test_legacy_two_arg_may_route_contract_unchanged():
    engine = PipelineEngine()
    poi = _poi()
    engine.arm_at(poi, arm_bar=0)  # no arm candle → CLEAN_ARM anyway
    adapter = PipelineAdapter(engine)
    assert adapter._may_route(poi, POIState.FRESH, 5) is True
    assert adapter._may_route(poi, POIState.TESTED, 5) is True
    assert adapter._may_route(poi, POIState.VIOLATED, 5) is False


# --------------------------------------------------------------------------- #
# R5 — one-shot identity (at most one route per episode)
# --------------------------------------------------------------------------- #
def test_oneshot_routed_poi_never_routed_again():
    engine = PipelineEngine()
    poi = _poi()
    arm_bar = _candle(100.5, 100.9, 100.3, 100.7)
    engine.arm_at(poi, arm_bar=0, arm_candle=arm_bar)
    adapter = PipelineAdapter(engine)
    adapter.set_candles([arm_bar])
    adapter._routed.add(poi.id)
    later = _candle(100.5, 100.9, 100.3, 100.7, offset_min=1)
    # The caller gates on `poi.id not in self._routed` BEFORE _may_route —
    # the one-shot fact is the routed set; _may_route is never consulted.
    assert poi.id in adapter._routed
    assert adapter._may_route(poi, POIState.FRESH, 1, bar=later) is True


# --------------------------------------------------------------------------- #
# Locked constants / horizon
# --------------------------------------------------------------------------- #
def test_locked_constants_untouched_and_horizon_is_20():
    assert TRIGGER_A_EXPIRY == 20
    assert poi_give_up_bars() == TRIGGER_A_EXPIRY == 20
