"""Pytest bootstrap: make ``04_SRC`` importable and share a candle factory."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

DEFAULT_START = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)


def make_candles(
    rows,
    timeframe: Timeframe = Timeframe.M5,
    start: datetime = DEFAULT_START,
) -> list[Candle]:
    """Build a chronological candle list from OHLC(V) rows.

    Each row is ``(open, high, low, close)`` or ``(open, high, low, close, volume)``.
    Bars are spaced by the timeframe's duration.
    """
    candles: list[Candle] = []
    step = timedelta(minutes=timeframe.minutes)
    for offset, row in enumerate(rows):
        open_, high, low, close = row[0], row[1], row[2], row[3]
        volume = float(row[4]) if len(row) > 4 else 0.0
        candles.append(
            Candle(
                timestamp=start + offset * step,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=volume,
                timeframe=timeframe,
            )
        )
    return candles


@pytest.fixture
def candle_factory():
    """Fixture exposing :func:`make_candles` to every test module."""
    return make_candles


def make_swing(
    candles: list[Candle],
    index: int,
    is_high: bool,
    is_valid: bool = True,
    level: float | None = None,
) -> "Swing":
    """Build a Swing anchored on ``candles[index]``.

    The default ``level`` is the candle's high (``is_high=True``) or low.
    ``candle_index`` mirrors the anchor index (no §18 special-rule shift).
    """
    from smc.core.swing import Swing

    candle = candles[index]
    if level is None:
        level = candle.high if is_high else candle.low
    return Swing(
        is_high=is_high,
        level=level,
        candle_index=index,
        base_candle=candle,
        timeframe=candle.timeframe,
        is_valid=is_valid,
    )


@pytest.fixture
def swing_factory():
    """Fixture exposing :func:`make_swing` for Phase 2 model tests."""
    return make_swing
