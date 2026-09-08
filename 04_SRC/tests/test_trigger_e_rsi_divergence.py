"""Phase 4 — Trigger E: double top/bottom + RSI(14) divergence (R1 §7).

Fixtures are generated programmatically so the RSI relationship at the two
pattern extremes is deterministic:

* bearish: closes rise strictly through the first top (RSI saturates 100),
  then decline + grind to an EQUAL second top (RSI < 100 → divergence);
* bullish: closes fall strictly through the first bottom (RSI 0), then a
  rally + drift to an EQUAL second bottom (RSI > 0 → divergence).
"""

from smc.config.model_type import ModelType
from smc.config.timeframe import Timeframe
from smc.core.enums import Direction, TriggerType
from smc.core.poi import POI
from smc.core.zone import Zone
from smc.triggers.base_trigger import TriggerContext
from smc.triggers.trigger_e_rsi_divergence import RsiDivergenceTrigger

TF = Timeframe.M5

HIGH = 110.0
LOW = 95.0
PEAK_1 = 18      # first top/bottom index (after the RSI warm-up)
PEAK_2 = 33      # second (equal) top/bottom index
BREAK_BAR = 34   # neckline break bar


def _bearish_rows():
    """Strictly rising closes through PEAK_1, then drop + slow grind to an
    equal second high at PEAK_2 (RSI lower there), then a break below the
    neckline at BREAK_BAR."""
    rows = []
    price = 99.0
    for _ in range(5):                      # idx 0..4
        price += 0.2
        rows.append((price, price + 0.3, price - 0.2, price))
    for _ in range(14):                     # idx 5..18 strict rise (RSI=100)
        price += 0.5
        rows.append((price, price + 0.2, price - 0.1, price))
    for _ in range(6):                      # idx 19..24 decline (neckline low)
        price -= 0.7
        rows.append((price, price + 0.2, price - 0.3, price))
    for _ in range(8):                      # idx 25..32 slow grind higher
        price += 0.15
        rows.append((price, price + 0.2, price - 0.1, price))
    rows.append((price, HIGH, price - 0.1, price))  # idx 33 second equal high
    price = 102.0
    rows.append((price, price + 0.2, price - 0.4, price - 0.5))  # idx 34 neckline break
    return rows


def _bullish_rows():
    """Mirror image for the double bottom: strict decline to PEAK_1, rally +
    slow drift to an equal second low at PEAK_2 (RSI higher there), then a
    break above the neckline at BREAK_BAR."""
    rows = []
    price = 108.0
    for _ in range(5):                      # idx 0..4
        price -= 0.2
        rows.append((price, price + 0.2, price - 0.3, price))
    for _ in range(14):                     # idx 5..18 strict decline (RSI=0)
        price -= 0.5
        rows.append((price, price + 0.1, price - 0.2, price))
    for _ in range(6):                      # idx 19..24 rally (neckline high)
        price += 0.7
        rows.append((price, price + 0.3, price - 0.2, price))
    for _ in range(8):                      # idx 25..32 slow drift lower
        price -= 0.15
        rows.append((price, price + 0.1, price - 0.2, price))
    rows.append((price, price + 0.1, LOW, price))  # idx 33 second equal low
    price = 105.0
    rows.append((price, price + 0.3, price - 0.2, price + 0.4))  # idx 34 break
    return rows


def _ctx(candles, swings, direction, bar=BREAK_BAR, from_bar=0):
    if direction is Direction.SHORT:
        zone = Zone(top=HIGH + 5.0, bottom=HIGH - 5.0, direction=direction, timeframe=TF)
    else:
        zone = Zone(top=LOW + 10.0, bottom=LOW, direction=direction, timeframe=TF)
    poi = POI(zone=zone, models=[ModelType.M6])
    return TriggerContext(poi=poi, candles=candles, swings=swings, bar_index=bar, from_bar=from_bar)


def test_bearish_double_top_with_divergence(candle_factory, swing_factory):
    candles = candle_factory(_bearish_rows(), timeframe=TF)
    swings = [
        swing_factory(candles, PEAK_1, True, level=HIGH),
        swing_factory(candles, PEAK_2, True, level=HIGH),
    ]
    signal = RsiDivergenceTrigger().evaluate(_ctx(candles, swings, Direction.SHORT))
    assert signal is not None
    assert signal.trigger is TriggerType.E_RSI_DIVERGENCE
    assert signal.direction is Direction.SHORT
    # Entry at the neckline (lowest low between the two peaks).
    neckline = min(c.low for c in candles[PEAK_1 + 1 : PEAK_2 + 1])
    assert signal.entry_price == neckline
    assert signal.stop_reference == HIGH  # beyond the pattern extreme
    assert signal.completion_index == BREAK_BAR
    assert signal.expiry_bars == 15


def test_bullish_double_bottom_with_divergence(candle_factory, swing_factory):
    candles = candle_factory(_bullish_rows(), timeframe=TF)
    swings = [
        swing_factory(candles, PEAK_1, False, level=LOW),
        swing_factory(candles, PEAK_2, False, level=LOW),
    ]
    signal = RsiDivergenceTrigger().evaluate(_ctx(candles, swings, Direction.LONG))
    assert signal is not None
    assert signal.direction is Direction.LONG
    neckline = max(c.high for c in candles[PEAK_1 + 1 : PEAK_2 + 1])
    assert signal.entry_price == neckline
    assert signal.stop_reference == LOW


def test_no_signal_without_divergence(candle_factory, swing_factory):
    rows = _bearish_rows()
    # Second top LOWER than the first — not an equal/higher high (no pattern).
    candles = candle_factory(rows, timeframe=TF)
    swings = [
        swing_factory(candles, PEAK_1, True, level=HIGH),
        swing_factory(candles, PEAK_2, True, level=HIGH - 3.0),
    ]
    assert RsiDivergenceTrigger().evaluate(_ctx(candles, swings, Direction.SHORT)) is None


def test_no_signal_before_neckline_break(candle_factory, swing_factory):
    candles = candle_factory(_bearish_rows(), timeframe=TF)
    swings = [
        swing_factory(candles, PEAK_1, True, level=HIGH),
        swing_factory(candles, PEAK_2, True, level=HIGH),
    ]
    ctx = _ctx(candles, swings, Direction.SHORT, bar=BREAK_BAR - 1)
    assert RsiDivergenceTrigger().evaluate(ctx) is None
