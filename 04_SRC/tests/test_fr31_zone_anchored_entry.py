"""FR-3.1 on-zone entry anchor — trigger F / shared helper tests.

Covers the four instructed areas:

1. Helper unit contract: on-zone passthrough, off-zone re-anchor
   (direction-aware PROXIMAL edge — LONG -> zone high, SHORT -> zone low),
   degenerate zones, NaN/inverted passthrough.
2. LONG/SHORT proximal anchor via the trigger: a detached OB re-anchors to
   the proximal edge, the stop moves to the zone's distal edge (stop stays
   on the protective side), and the pre-gate entry is already on-zone.
3. M8 fixture: the October-fate geometry (LONG, OB +43.78-style above the
   zone high) now emits an on-zone entry instead of a silent off-zone
   reject — same gate, same tolerance, no widening.
4. Regression anchors: the classic on-zone F fixtures keep their exact
   pre-FR-3.1 prices (bit-identical on-zone behavior), and the degenerate
   flat-zone/no-ATR case emits nothing (zero-SL-distance signal is not a
   trade).

No thresholds invented: zones/ATRs come from the fixtures; the only
tolerance involved is the frozen ZONE_REFINEMENT_ATR via entry_within_zone.
"""

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.triggers.base_trigger import (
    TriggerContext,
    entry_within_zone,
    zone_anchored_entry,
)
from smc.triggers.trigger_f_bos_ob import BosObContinuationTrigger

TF = Timeframe.M5

# The classic F fixture (test_trigger_f_bos_ob._ROWS): uptrend into a
# bearish OB candle idx9 (zone [100.5, 101.6]), BOS idx10, first touch idx12.
_ROWS = [
    (99.0, 99.6, 98.9, 99.5),      # 0
    (99.5, 100.1, 99.4, 100.0),    # 1
    (100.0, 100.6, 99.9, 100.5),   # 2
    (100.5, 101.0, 100.4, 100.9),  # 3
    (100.9, 101.4, 100.8, 101.3),  # 4
    (101.3, 101.6, 101.2, 101.5),  # 5
    (101.5, 101.8, 101.4, 101.7),  # 6 swing-high area (level 101.0)
    (101.7, 101.9, 101.3, 101.4),  # 7 pullback candle A
    (101.4, 101.7, 100.9, 101.1),  # 8 pullback candle B
    (101.1, 101.6, 100.5, 100.7),  # 9 OB (bearish) — zone [100.5, 101.6]
    (101.8, 102.0, 101.66, 101.9),  # 10 BOS: close 101.9 > 101.0
    (101.9, 101.95, 101.62, 101.7),  # 11 pullback (no touch yet)
    (101.6, 101.7, 100.4, 101.0),   # 12 FIRST touch of the OB top (101.6)
]


# --------------------------------------------------------------------- #
# 1) Helper unit contract
# --------------------------------------------------------------------- #

def test_helper_on_zone_passthrough_is_exact():
    assert zone_anchored_entry(Direction.LONG, 100.5, 101.6, 101.0) == 101.0
    assert zone_anchored_entry(Direction.SHORT, 100.5, 101.6, 100.8) == 100.8


def test_helper_anchors_to_direction_proximal_edge():
    # LONG off-zone reference (either side) -> zone HIGH.
    assert zone_anchored_entry(Direction.LONG, 100.5, 101.6, 104.0) == 101.6
    assert zone_anchored_entry(Direction.LONG, 100.5, 101.6, 96.0) == 101.6
    # SHORT off-zone reference (either side) -> zone LOW.
    assert zone_anchored_entry(Direction.SHORT, 100.5, 101.6, 96.0) == 100.5
    assert zone_anchored_entry(Direction.SHORT, 100.5, 101.6, 104.0) == 100.5


def test_helper_edge_and_exact_boundaries():
    # Exact edge references stay on the edge.
    assert zone_anchored_entry(Direction.LONG, 100.5, 101.6, 101.6) == 101.6
    assert zone_anchored_entry(Direction.SHORT, 100.5, 101.6, 100.5) == 100.5


def test_helper_degenerate_and_unlocatable_zones():
    # Flat zone: inside reference passes through; off-zone anchors to the
    # single price level.
    assert zone_anchored_entry(Direction.LONG, 100.0, 100.0, 100.0) == 100.0
    assert zone_anchored_entry(Direction.LONG, 100.0, 100.0, 105.0) == 100.0
    # Inverted bounds and NaN pass the reference through untouched so the
    # FR-3 gate — not the anchor — is what rejects them.
    assert zone_anchored_entry(Direction.LONG, 101.6, 100.5, 104.0) == 104.0
    nan = float("nan")
    assert zone_anchored_entry(Direction.LONG, nan, 101.6, 104.0) == 104.0
    # Non-numeric reference is passed through (gate handles rejection).
    assert zone_anchored_entry(Direction.LONG, 100.5, 101.6, None) is None


# --------------------------------------------------------------------- #
# 2) LONG / SHORT proximal anchor through the trigger
# --------------------------------------------------------------------- #

def _f_ctx(candles, swings, zone, direction=Direction.LONG, bar=12, from_bar=8):
    poi = POI(zone=zone, models=[ModelType.M5])
    return TriggerContext(poi=poi, candles=candles, swings=swings,
                          bar_index=bar, from_bar=from_bar)


def test_f_long_detached_ob_above_zone_reanchors_to_proximal_high(candle_factory, swing_factory):
    """The October fate shape: LONG, trigger OB ABOVE the zone high.

    Entry re-anchors to the zone high (proximal), the stop reference moves
    to the zone's distal (bottom) edge with the FR-2 buffer, and the entry
    is on-zone pre-gate (the gate then passes).
    """
    candles = candle_factory(_ROWS, timeframe=TF)
    swings = [swing_factory(candles, 6, True, level=101.0)]
    zone = Zone(top=97.0, bottom=95.0, direction=Direction.LONG, timeframe=TF)
    signal = BosObContinuationTrigger().evaluate(_f_ctx(candles, swings, zone))
    assert signal is not None
    assert signal.direction is Direction.LONG
    assert signal.entry_price == 97.0          # proximal (top) edge
    assert signal.stop_reference == 95.0       # zone distal edge reference
    assert signal.data["entry_anchor"] == "zone_edge_reanchor"
    # Pre-gate on-zone: the raw containment passes without any tolerance.
    assert entry_within_zone(signal.entry_price, zone, None) is True


# SHORT mirror of the classic fixture (point reflection about 100.25):
# downtrend, valid swing LOW 99.5 (idx6) → bullish OB candle idx9 (zone
# [98.9, 100.0]) → BOS idx10 (close 98.6 < 99.5, high stays below the OB
# bottom so it does NOT touch) → pullback idx11 (high 98.88 < 98.9) →
# first touch of the OB bottom at idx12 (high 100.1).
_ROWS_SHORT = [
    (101.5, 101.6, 100.9, 101.0),  # 0
    (100.5, 101.1, 100.4, 100.5),  # 1
    (100.5, 100.6, 99.9, 100.0),   # 2
    (100.0, 100.1, 99.5, 99.6),    # 3
    (99.6, 99.7, 99.1, 99.2),      # 4
    (99.0, 99.3, 98.9, 99.2),      # 5
    (98.8, 99.1, 98.7, 98.8),      # 6 swing-low area (level 99.5 supplied)
    (98.8, 99.2, 98.6, 99.1),      # 7 pullback candle A
    (99.4, 99.6, 98.8, 99.4),      # 8 pullback candle B
    (99.4, 100.0, 98.9, 99.8),     # 9 OB (bullish) — zone [98.9, 100.0]
    (98.7, 98.84, 98.5, 98.6),     # 10 BOS: close 98.6 < 99.5, high below OB
    (98.8, 98.88, 98.55, 98.8),    # 11 pullback (no touch yet)
    (99.5, 100.1, 98.8, 99.5),     # 12 FIRST touch of the OB bottom (98.9)
]


def test_f_short_detached_ob_below_zone_reanchors_to_proximal_low(candle_factory, swing_factory):
    """Mirror shape: SHORT with the trigger OB BELOW the zone low."""
    candles = candle_factory(_ROWS_SHORT, timeframe=TF)
    swings = [swing_factory(candles, 6, False, level=99.5)]
    zone = Zone(top=105.0, bottom=103.0, direction=Direction.SHORT, timeframe=TF)
    signal = BosObContinuationTrigger().evaluate(_f_ctx(candles, swings, zone,
                                                        direction=Direction.SHORT))
    assert signal is not None
    assert signal.direction is Direction.SHORT
    assert signal.entry_price == 103.0         # proximal (bottom) edge
    assert signal.stop_reference == 105.0      # zone distal edge reference
    assert signal.data["entry_anchor"] == "zone_edge_reanchor"
    assert entry_within_zone(signal.entry_price, zone, None) is True


def test_f_long_detached_ob_below_zone_anchors_proximal_with_zone_stop(
        candle_factory, swing_factory):
    """Deep shape: LONG with the OB far BELOW the zone — the limit anchors
    to the zone high and the stop reference is the zone BOTTOM (the OB is
    below the entry, so it cannot be the stop reference anymore).
    """
    candles = candle_factory(_ROWS, timeframe=TF)
    swings = [swing_factory(candles, 6, True, level=101.0)]
    zone = Zone(top=109.0, bottom=108.0, direction=Direction.LONG, timeframe=TF)
    signal = BosObContinuationTrigger().evaluate(_f_ctx(candles, swings, zone))
    assert signal is not None
    assert signal.entry_price == 109.0
    assert signal.stop_reference == 108.0      # zone bottom, NOT the OB
    assert signal.data["entry_anchor"] == "zone_edge_reanchor"


def test_f_reanchored_entry_is_resting_limit_on_touch_bar(candle_factory, swing_factory):
    """Reachability sanity: on the touch bar (bar 12, low 100.4) a
    re-anchored LONG limit at the zone high (101.6) is BELOW the market's
    recent range top — the signal is a genuine resting buy-limit shape, and
    the touch-fill model semantics are unchanged (touch = fill at limit).
    """
    candles = candle_factory(_ROWS, timeframe=TF)
    swings = [swing_factory(candles, 6, True, level=101.0)]
    zone = Zone(top=97.0, bottom=95.0, direction=Direction.LONG, timeframe=TF)
    signal = BosObContinuationTrigger().evaluate(_f_ctx(candles, swings, zone))
    assert signal is not None
    # Touch bar low (100.4) is ABOVE the re-anchored limit (97.0): the
    # resting buy-limit sits below the current market — correct order side.
    assert signal.entry_price < candles[12].low


# --------------------------------------------------------------------- #
# 3) M8 fixture (the fate-report counterfactual)
# --------------------------------------------------------------------- #

def test_m8_fate_geometry_now_routes_on_zone(candle_factory, swing_factory):
    """M8-fate fixture: HTF POI zone below the LTF OB; entry ends on-zone.

    Zone high 3995.775, OB top 4039.555 (the poi-002480 October geometry,
    scaled) — the FR-3.1 anchor turns the silent +43.78 off-zone reject
    into an on-zone limit at the proximal edge. The gate is unchanged.
    """
    candles = candle_factory(_ROWS, timeframe=TF)
    swings = [swing_factory(candles, 6, True, level=101.0)]
    zone = Zone(top=3995.775, bottom=3961.555, direction=Direction.LONG,
                timeframe=TF)
    signal = BosObContinuationTrigger().evaluate(_f_ctx(candles, swings, zone))
    assert signal is not None
    assert signal.entry_price == 3995.775
    assert signal.stop_reference == 3961.555
    assert signal.data["entry_anchor"] == "zone_edge_reanchor"
    assert entry_within_zone(signal.entry_price, zone, None) is True
    # No threshold was touched: the gate's frozen band still applies.
    assert entry_within_zone(3995.775 + 0.1, zone, None) is False


def test_m8_tagged_poi_on_zone_short_path(candle_factory, swing_factory):
    """M8-tagged SHORT POI whose OB sits below the zone low — proximal
    anchor at the zone low, distal stop above."""
    candles = candle_factory(_ROWS_SHORT, timeframe=TF)
    swings = [swing_factory(candles, 6, False, level=99.5)]
    zone = Zone(top=96.0, bottom=94.5, direction=Direction.SHORT, timeframe=TF)
    poi = POI(zone=zone, models=[ModelType.M8])
    ctx = TriggerContext(poi=poi, candles=candles, swings=swings,
                         bar_index=12, from_bar=8)
    signal = BosObContinuationTrigger().evaluate(ctx)
    assert signal is not None
    assert signal.direction is Direction.SHORT
    assert signal.entry_price == 94.5
    assert signal.stop_reference == 96.0
    assert signal.data["entry_anchor"] == "zone_edge_reanchor"


def test_short_on_zone_fixture_keeps_pre_fr31_prices_bit_exactly(candle_factory, swing_factory):
    """SHORT with the thesis zone ON the OB keeps the classic rule:"""
    candles = candle_factory(_ROWS_SHORT, timeframe=TF)
    swings = [swing_factory(candles, 6, False, level=99.5)]
    zone = Zone(top=100.0, bottom=98.9, direction=Direction.SHORT, timeframe=TF)
    signal = BosObContinuationTrigger().evaluate(_f_ctx(candles, swings, zone,
                                                        direction=Direction.SHORT))
    assert signal is not None
    assert signal.entry_price == 98.9   # OB proximal edge (bottom)
    assert signal.stop_reference == 100.0  # OB distal edge (top)
    assert signal.data["entry_anchor"] == "ob_proximal"


# --------------------------------------------------------------------- #
# 4) Regression anchors: on-zone behavior is bit-identical
# --------------------------------------------------------------------- #

def test_on_zone_fixture_keeps_pre_fr31_prices_bit_exactly(candle_factory, swing_factory):
    """The classic on-zone fixture keeps the exact pre-FR-3.1 entry/stop."""
    candles = candle_factory(_ROWS, timeframe=TF)
    swings = [swing_factory(candles, 6, True, level=101.0)]
    zone = Zone(top=101.6, bottom=100.5, direction=Direction.LONG, timeframe=TF)
    signal = BosObContinuationTrigger().evaluate(_f_ctx(candles, swings, zone))
    assert signal is not None
    assert signal.entry_price == 101.6   # OB proximal edge (== zone top)
    assert signal.stop_reference == 100.5  # OB distal edge (== zone bottom)
    assert signal.data["entry_anchor"] == "ob_proximal"


def test_flat_zone_without_atr_emits_nothing(candle_factory, swing_factory):
    """Degenerate geometry: a flat zone at a level INSIDE the OB body makes
    the reference off-zone, so the re-anchored entry equals the zone's
    distal stop reference (zero SL distance — sizing raises). No signal is
    a trade; the guard emits nothing rather than a broken one.
    """
    candles = candle_factory(_ROWS, timeframe=TF)
    swings = [swing_factory(candles, 6, True, level=101.0)]
    zone = Zone(top=100.8, bottom=100.8, direction=Direction.LONG, timeframe=TF)
    signal = BosObContinuationTrigger().evaluate(_f_ctx(candles, swings, zone))
    assert signal is None


def test_ob_partially_overlapping_zone_top_uses_ob_reference(candle_factory, swing_factory):
    """An OB overlapping the zone keeps its own reference: the entry is
    on-zone either way, and the OB distal edge remains the stop reference
    when the entry is the OB proximal edge.
    """
    candles = candle_factory(_ROWS, timeframe=TF)
    swings = [swing_factory(candles, 6, True, level=101.0)]
    # Zone top (102.0) above the OB top (101.6): LONG anchor keeps the
    # OB-top reference (on-zone), stop stays the OB distal edge.
    zone = Zone(top=102.0, bottom=100.8, direction=Direction.LONG, timeframe=TF)
    signal = BosObContinuationTrigger().evaluate(_f_ctx(candles, swings, zone))
    assert signal is not None
    assert signal.entry_price == 101.6
    assert signal.stop_reference == 100.5
    assert signal.data["entry_anchor"] == "ob_proximal"
