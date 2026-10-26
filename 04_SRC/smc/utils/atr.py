"""ATR (Average True Range) — Wilder smoothing, stdlib only.

The smoothing matches MetaTrader 5's ``iATR`` (Wilder RMA), so values are
comparable with the MQL5 reference implementation (``GOLD_SMC_v25_DIAG``)
and with ``cab_watcher_v16_3-1.py`` helper conventions.

API
---
``atr_series(candles, period)`` returns one value per input candle, with
``None`` during the ``period - 1`` warm-up bars.
``latest_atr(candles, period)`` returns the final value or ``None`` when
there is not enough data.
"""

from __future__ import annotations

from smc.core.candle import Candle

__all__ = ["atr_series", "latest_atr"]


def _true_ranges(candles: list[Candle]) -> list[float]:
    """True range per candle: max(H-L, |H-prevC|, |L-prevC|)."""
    result: list[float] = []
    previous_close: float | None = None
    for candle in candles:
        if previous_close is None:
            tr = candle.high - candle.low
        else:
            tr = max(
                candle.high - candle.low,
                abs(candle.high - previous_close),
                abs(candle.low - previous_close),
            )
        result.append(tr)
        previous_close = candle.close
    return result


def atr_series(candles: list[Candle], period: int = 14) -> list[float | None]:
    """Wilder-smoothed ATR, aligned with the input candles.

    The first ``period - 1`` entries are ``None`` (insufficient warm-up).
    Requires at least ``period`` candles to produce a value.
    """
    if period < 1:
        raise ValueError("period must be >= 1")
    if len(candles) < period:
        return [None] * len(candles)

    trs = _true_ranges(candles)
    out: list[float | None] = [None] * (period - 1)

    # Seed: simple average of the first `period` true ranges (matches MT5 iATR).
    seed = sum(trs[:period]) / period
    out.append(seed)
    current = seed
    for tr in trs[period:]:
        current = (current * (period - 1) + tr) / period  # Wilder RMA
        out.append(current)
    return out


def latest_atr(candles: list[Candle], period: int = 14) -> float | None:
    """Return the most recent ATR value (``None`` if data is insufficient)."""
    if len(candles) < period:
        return None
    return atr_series(candles, period)[-1]