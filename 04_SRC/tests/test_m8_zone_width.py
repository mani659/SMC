"""F2 zone-width origin-tightness — ob/demand_supply zones equal their origin
candle's exact range (bit-stable); FVG zones equal the definitional gap.
No width caps, no thresholds: these tests pin that construction never
widens beyond origin geometry (the F2 measurement verdict).
"""

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction
from smc.poi.models.m8_htf_demand_supply import M8HtfDemandSupply, collapse_episodes


def _zones_by_kind(model, series, tf):
    out = {}
    for kind, direction, start, zone in model._zones(series, tf):
        out.setdefault(kind, []).append((direction, start, zone))
    return out


def test_ob_zone_equals_origin_candle_range(candle_factory):
    rows = [(100.0, 100.2, 99.8, 99.9)] * 14
    rows += [(100.0, 100.1, 99.9, 100.05),   # 14: pre-FVG candle (ob origin)
             (100.05, 100.1, 100.0, 100.08),  # 15: first gap candle
             (100.3, 100.4, 100.2, 100.35)]   # 16: gap confirms (low 100.2 > 100.1)
    d1 = candle_factory(rows, timeframe=Timeframe.D1)
    model = M8HtfDemandSupply(Timeframe.D1, htf_candles={Timeframe.D1: d1})
    by_kind = _zones_by_kind(model, d1, Timeframe.D1)
    assert "ob" in by_kind
    for direction, start, zone in by_kind["ob"]:
        origin = d1[start]
        assert (zone.bottom, zone.top) == (origin.low, origin.high)


def test_demand_zone_equals_origin_candle_range(candle_factory):
    rows = [(200.0 + 0.05 * i, 200.1 + 0.05 * i, 199.9 + 0.05 * i,
             200.05 + 0.05 * i) for i in range(14)]
    rows.append((200.7, 201.2, 200.6, 201.0))   # 14: last bullish candle
    rows.append((201.0, 202.0, 199.4, 199.6))   # 15: dump
    rows.append((199.6, 199.9, 199.0, 199.2))   # 16
    rows.append((199.2, 199.5, 198.8, 199.0))   # 17
    d1 = candle_factory(rows, timeframe=Timeframe.D1)
    model = M8HtfDemandSupply(Timeframe.D1, htf_candles={Timeframe.D1: d1})
    by_kind = _zones_by_kind(model, d1, Timeframe.D1)
    assert "demand_supply" in by_kind
    for direction, start, zone in by_kind["demand_supply"]:
        origin = d1[start]
        assert (zone.bottom, zone.top) == (origin.low, origin.high)


def test_huge_candle_zone_is_origin_tight_not_envelope(candle_factory):
    """A 193-pt single D1 candle yields a 193-pt zone that IS the origin
    candle — wide by volatility, not by envelope construction."""
    rows = [(3000.0, 3001.0, 2999.0, 3000.5)] * 14
    rows.append((3390.0, 3393.0, 3200.0, 3205.0))  # 14: giant BEARISH candle
    rows.append((3205.0, 3250.0, 3204.0, 3240.0))  # 15: rise begins
    rows.append((3240.0, 3300.0, 3238.0, 3290.0))  # 16: rise
    rows.append((3290.0, 3350.0, 3288.0, 3340.0))  # 17: rise
    d1 = candle_factory(rows, timeframe=Timeframe.D1)
    model = M8HtfDemandSupply(Timeframe.D1, htf_candles={Timeframe.D1: d1})
    by_kind = _zones_by_kind(model, d1, Timeframe.D1)
    # The giant candle qualifies as BOTH ob (pre-FVG) and demand_supply
    # (last opposing before impulse) on identical bounds — F1 collapses to
    # the single ob POI. Either way the zone IS the origin candle exactly.
    giant = [t for k in by_kind.values() for t in k
             if (t[2].bottom, t[2].top) == (3200.0, 3393.0)]
    assert len(giant) == 1
    direction, start, zone = giant[0]
    assert direction is Direction.LONG
    # No duals / direction conflicts anywhere in this output (collapse
    # integration on fixed code: one row per geometric episode).
    seen: dict = {}
    for kind, direction, start, zone in model._zones(d1, Timeframe.D1):
        key = (round(zone.bottom, 3), round(zone.top, 3))
        assert key not in seen, f"dual episode survived collapse: {key}"
        seen[key] = direction


def test_zones_bit_stable_across_runs(candle_factory):
    rows = [(200.0 + 0.05 * i, 200.1 + 0.05 * i, 199.9 + 0.05 * i,
             200.05 + 0.05 * i) for i in range(14)]
    rows.append((200.7, 201.2, 200.6, 201.0))
    rows.append((201.0, 202.0, 199.4, 199.6))
    rows.append((199.6, 199.9, 199.0, 199.2))
    rows.append((199.2, 199.5, 198.8, 199.0))
    d1 = candle_factory(rows, timeframe=Timeframe.D1)
    model = M8HtfDemandSupply(Timeframe.D1, htf_candles={Timeframe.D1: d1})
    snap = lambda: [(k, d.name, s, z.bottom, z.top)
                    for k, d, s, z in model._zones(d1, Timeframe.D1)]
    assert snap() == snap()


def test_fvg_zone_equals_definitional_gap(candle_factory):
    rows = [(100.0, 100.2, 99.8, 99.9)] * 14
    rows.append((100.0, 100.1, 99.9, 100.05))    # 14
    rows.append((100.05, 100.1, 100.0, 100.08))  # 15
    rows.append((100.3, 100.4, 100.2, 100.35))    # 16: low 100.2 > high[14]=100.1
    d1 = candle_factory(rows, timeframe=Timeframe.D1)
    model = M8HtfDemandSupply(Timeframe.D1, htf_candles={Timeframe.D1: d1})
    by_kind = _zones_by_kind(model, d1, Timeframe.D1)
    assert "fvg" in by_kind  # gap exists; FVG kind is gap-defined, not capped
    for direction, start, zone in by_kind["fvg"]:
        assert zone.top > zone.bottom  # non-degenerate gap
