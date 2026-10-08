"""FR-3 zone/entry geometry + M4 fidelity tests.

Covers: entry_within_zone unit contract (inside/edge/tolerance/missing),
F rejection when the trigger OB sits outside its POI thesis zone, and the
M4/M5 domain-split behavior at the margin (with the acceptance/decoy
fixtures in test_poi_models.py). No thresholds invented — the only numbers
used are frozen (§13 refinement tolerance, §2 EQH tolerance).
"""

from smc.config.timeframe import Timeframe
from smc.core.enums import Direction
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.config.model_type import ModelType
from smc.triggers.base_trigger import TriggerContext, entry_within_zone
from smc.triggers.trigger_f_bos_ob import BosObContinuationTrigger

TF = Timeframe.M5


def test_entry_within_zone_inside_and_edges():
    zone = Zone(top=101.6, bottom=100.5, direction=Direction.LONG, timeframe=TF)
    assert entry_within_zone(101.6, zone, 0.5) is True   # top edge
    assert entry_within_zone(100.5, zone, 0.5) is True   # bottom edge
    assert entry_within_zone(101.0, zone, 0.5) is True   # interior
    assert entry_within_zone(101.6 + 0.5 * 0.5, zone, 0.5) is True  # tol edge


def test_entry_within_zone_outside_and_degenerate():
    zone = Zone(top=101.6, bottom=100.5, direction=Direction.LONG, timeframe=TF)
    assert entry_within_zone(103.0, zone, 0.5) is False
    assert entry_within_zone(99.0, zone, 0.5) is False
    assert entry_within_zone(101.6, zone, None) is True  # strict, no tol needed
    assert entry_within_zone(101.61, zone, None) is False  # strict rejects
    assert entry_within_zone(101.0, None, 0.5) is False  # unlocatable geometry
    flat = Zone(top=100.0, bottom=100.0, direction=Direction.LONG, timeframe=TF)
    assert entry_within_zone(100.0, flat, 0.5) is True
    assert entry_within_zone(100.1, flat, 0.5) is True  # tol covers epsilon


def _f_rows():
    return [
        (99.0, 99.6, 98.9, 99.5),
        (99.5, 100.1, 99.4, 100.0),
        (100.0, 100.6, 99.9, 100.5),
        (100.5, 101.0, 100.4, 100.9),
        (100.9, 101.4, 100.8, 101.3),
        (101.3, 101.6, 101.2, 101.5),
        (101.5, 101.8, 101.4, 101.7),
        (101.7, 101.9, 101.3, 101.4),
        (101.4, 101.7, 100.9, 101.1),
        (101.1, 101.6, 100.5, 100.7),
        (101.8, 102.0, 101.66, 101.9),
        (101.9, 101.95, 101.62, 101.7),
        (101.6, 101.7, 100.4, 101.0),
    ]


def test_f_rejects_trigger_ob_outside_thesis_zone(candle_factory, swing_factory):
    """FR-3.1 SUPERSEDED: the old policy rejected a detached off-zone OB.

    FR-3.1 re-anchors the limit to the zone's direction-proximal edge (the
    fate report showed the only compliant-path attempts were silent +16/+43
    off-zone rejects). The GATE is unchanged — an anchor slip (e.g.
    unlocatable zone) is still rejected; see test_fr31_zone_anchored_entry
    for the re-anchor policy tests.
    """
    candles = candle_factory(_f_rows(), timeframe=TF)
    swings = [swing_factory(candles, 6, True, level=101.0)]
    foreign = Zone(top=110.0, bottom=109.0, direction=Direction.LONG, timeframe=TF)
    poi = POI(zone=foreign, models=[ModelType.M5])
    ctx = TriggerContext(poi=poi, candles=candles, swings=swings,
                         bar_index=12, from_bar=8)
    signal = BosObContinuationTrigger().evaluate(ctx)
    assert signal is not None
    assert signal.entry_price == 110.0  # re-anchored to the proximal (top) edge
    assert signal.data["entry_anchor"] == "zone_edge_reanchor"
    assert entry_within_zone(signal.entry_price, foreign, None) is True


def test_f_accepts_trigger_ob_inside_thesis_zone(candle_factory, swing_factory):
    """Same geometry with the thesis zone ON the OB routes normally."""
    candles = candle_factory(_f_rows(), timeframe=TF)
    swings = [swing_factory(candles, 6, True, level=101.0)]
    home = Zone(top=101.6, bottom=100.5, direction=Direction.LONG, timeframe=TF)
    poi = POI(zone=home, models=[ModelType.M5])
    ctx = TriggerContext(poi=poi, candles=candles, swings=swings,
                         bar_index=12, from_bar=8)
    signal = BosObContinuationTrigger().evaluate(ctx)
    assert signal is not None
    assert signal.entry_price == 101.6
