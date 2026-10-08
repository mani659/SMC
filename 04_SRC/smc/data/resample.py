"""Deterministic M1 → higher-timeframe OHLCV resampling (FR-1).

Aggregates an ascending ``list[Candle]`` into coarser UTC-aligned bins
(M5/H1/H4/D1 and — since the 2026-10-06 weekly-provisioning directive —
W1). Pure function: no wall clock, no randomness, no MT5.

Binning contract (frozen by this docstring — tests pin it):
  - bins align to UTC multiples of the target duration
    (H1: minute 0; H4: 00/04/…; D1: 00:00);
  - **W1 exception (market convention, deliberately not epoch-multiples):**
    weekly bins align to UTC MONDAY 00:00 of the candle's ISO week. Epoch-
    multiples of 10080 min would align to Thursdays (the Unix epoch was a
    Thursday) — wrong for MT5/TradingView weekly bars, so W1 gets its own
    Monday-open bin function. Stamp = bin open (the Monday), as for every
    other timeframe;
  - emitted bar stamp = bin OPEN time (tz preserved from input);
  - O/H/L/C/V = first-open / max-high / min-low / last-close / sum-volume;
  - bins aggregate PRESENT bars only (vendor gaps such as the NY-5pm
    rollover omission — and weekends — do not invent bars; documented,
    not filled);
  - input must be strictly ascending (disorder raises loudly);
  - output carries the target ``Timeframe`` on every candle.

Determinism: same input list → identical output list (order-preserving).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle

__all__ = ["resample_ohlcv", "resample_multi"]


def _bin_open(timestamp: datetime, minutes: int) -> datetime:
    """UTC bin-open for ``timestamp`` at ``minutes`` duration."""
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    ts = timestamp if timestamp.tzinfo is not None else timestamp.replace(
        tzinfo=timezone.utc
    )
    elapsed = int((ts - epoch).total_seconds() // 60)
    aligned = (elapsed // minutes) * minutes
    return epoch + timedelta(minutes=aligned)


def _week_open(timestamp: datetime) -> datetime:
    """UTC MONDAY 00:00 of ``timestamp``'s ISO week (W1 bin open)."""
    ts = timestamp if timestamp.tzinfo is not None else timestamp.replace(
        tzinfo=timezone.utc
    )
    day = ts.replace(hour=0, minute=0, second=0, microsecond=0)
    return day - timedelta(days=day.weekday())


def resample_ohlcv(
    candles: list[Candle], timeframe: Timeframe
) -> list[Candle]:
    """Aggregate M1 (or finer) candles into ``timeframe`` bars."""
    minutes = timeframe.minutes
    weekly = timeframe is Timeframe.W1
    if not weekly and (minutes < 1 or 1440 % minutes != 0):
        # Guard: only UTC-aligned integer-minute targets are supported.
        # (All seven locked timeframes divide 1440; W1 is the special-
        # cased weekly bin above; exotic values fail loud.)
        raise ValueError(f"unsupported resample target: {timeframe.name}")
    if minutes == 1 and all(c.timeframe is Timeframe.M1 for c in candles):
        return [
            Candle(timestamp=c.timestamp, open=c.open, high=c.high,
                   low=c.low, close=c.close, volume=c.volume,
                   timeframe=timeframe)
            for c in candles
        ]
    binned: dict[datetime, list[Candle]] = {}
    order: list[datetime] = []
    previous = None
    for candle in candles:
        if previous is not None and not previous < candle.timestamp:
            raise ValueError(
                "resample_ohlcv requires strictly ascending timestamps; "
                f"disorder at {candle.timestamp!r}"
            )
        previous = candle.timestamp
        if weekly:
            key = _week_open(candle.timestamp)
        else:
            key = _bin_open(candle.timestamp, minutes)
        if key not in binned:
            binned[key] = []
            order.append(key)
        binned[key].append(candle)
    out: list[Candle] = []
    for key in order:
        group = binned[key]
        out.append(
            Candle(
                timestamp=key,
                open=group[0].open,
                high=max(c.high for c in group),
                low=min(c.low for c in group),
                close=group[-1].close,
                volume=sum(c.volume for c in group),
                timeframe=timeframe,
            )
        )
    return out


def resample_multi(
    candles: list[Candle], timeframes
) -> dict[Timeframe, list[Candle]]:
    """Resample one series into several timeframes (order-preserving dict)."""
    return {tf: resample_ohlcv(candles, tf) for tf in timeframes}
