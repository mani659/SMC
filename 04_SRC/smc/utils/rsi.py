"""RSI (Relative Strength Index) — Wilder smoothing, stdlib only.

The smoothing matches MetaTrader 5's ``iRSI`` (Wilder RMA with an SMA
seed), so values are comparable with the MQL5 reference implementation.

API
---
``rsi_series(candles, period)`` returns one value per input candle, with
``None`` during the ``period`` warm-up bars.
``latest_rsi(candles, period)`` returns the final value or ``None`` when
there is not enough data.

The indicator period is a parameter (default 14, the RSI(14) cited by the
frozen trigger spec R1 §7 Trigger E / v5 flowchart) — an indicator
parameter like ``atr_period``, not a frozen decision threshold.
"""

from __future__ import annotations

from smc.core.candle import Candle

__all__ = ["DEFAULT_RSI_PERIOD", "rsi_series", "latest_rsi"]

DEFAULT_RSI_PERIOD = 14  # indicator parameter (matches MT5 iRSI default)


def rsi_series(candles: list[Candle], period: int = DEFAULT_RSI_PERIOD) -> list[float | None]:
    """Wilder-smoothed RSI, aligned with the input candles.

    The first ``period`` entries are ``None`` (insufficient warm-up).
    Requires at least ``period + 1`` candles to produce a value.
    """
    if period < 1:
        raise ValueError("period must be >= 1")
    if len(candles) < period + 1:
        return [None] * len(candles)

    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, len(candles)):
        change = candles[index].close - candles[index - 1].close
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    # Seed: simple averages of the first `period` gains/losses (MT5 iRSI).
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    out: list[float | None] = [None] * period
    out.append(_value(avg_gain, avg_loss))

    for offset in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[offset]) / period
        avg_loss = (avg_loss * (period - 1) + losses[offset]) / period
        out.append(_value(avg_gain, avg_loss))
    return out


def latest_rsi(candles: list[Candle], period: int = DEFAULT_RSI_PERIOD) -> float | None:
    """Return the most recent RSI value (``None`` if data is insufficient)."""
    if len(candles) < period + 1:
        return None
    return rsi_series(candles, period)[-1]


def _value(avg_gain: float, avg_loss: float) -> float:
    """RSI from average gain/loss (0–100; 50 when flat)."""
    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0.0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))
