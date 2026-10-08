"""CSV loader — historical OHLCV into ``list[Candle]`` (stdlib only).

Intended for backtesting (Phase 6). Expected CSV layout:

    time,open,high,low,close,volume

The ``time`` column accepts ISO-8601 strings or unix timestamps (seconds,
or milliseconds when the value exceeds 1e12). Header names are flexible:
``timestamp``/``date``/``datetime`` for time and ``vol`` for volume.
Rows must be in chronological (ascending) order.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle

__all__ = ["load_ohlcv"]

_TIME_COLUMNS = ("time", "timestamp", "date", "datetime", "t")
_VOLUME_COLUMNS = ("volume", "vol", "tick_volume", "tv")

_UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _parse_timestamp(raw: str) -> datetime:
    value = raw.strip()
    if not value:
        raise ValueError("Empty timestamp cell")
    try:
        number = float(value)
    except ValueError:
        # ISO-8601 (with or without timezone). Naive values are read as UTC.
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    # Numeric: unix seconds, or milliseconds when unreasonably large.
    seconds = number / 1000.0 if abs(number) >= 1e12 else number
    return _UNIX_EPOCH + timedelta(seconds=seconds)


def _coerce_float(raw: str, column: str) -> float:
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid {column!r} value: {raw!r}") from exc


def load_ohlcv(
    filepath: str | Path,
    timeframe: Timeframe = Timeframe.M5,
    symbol: str = "",
) -> list[Candle]:
    """Load a chronological OHLCV CSV file into Candle objects.

    Raises ``FileNotFoundError`` for a missing file, ``ValueError`` for
    malformed rows, and ``KeyError`` when the required OHLC columns are
    absent.
    """
    path = Path(filepath)
    time_col: str | None = None
    volume_col: str | None = None

    candles: list[Candle] = []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = [str(f).strip().lower() for f in (reader.fieldnames or [])]

        def pick(candidates: tuple[str, ...]) -> str | None:
            return next((name for name in fieldnames if name in candidates), None)

        time_col = pick(_TIME_COLUMNS)
        volume_col = pick(_VOLUME_COLUMNS)
        missing = [name for name in ("open", "high", "low", "close") if name not in fieldnames]
        if time_col is None:
            raise ValueError(
                "CSV must include a time column; none of "
                f"{_TIME_COLUMNS!r} found in header {fieldnames!r}"
            )
        if missing:
            raise KeyError(f"CSV is missing required OHLC columns: {missing}")

        for row_number, row in enumerate(reader, start=2):
            try:
                candles.append(
                    Candle(
                        timestamp=_parse_timestamp(row[time_col]),
                        open=_coerce_float(row["open"], "open"),
                        high=_coerce_float(row["high"], "high"),
                        low=_coerce_float(row["low"], "low"),
                        close=_coerce_float(row["close"], "close"),
                        volume=(
                            _coerce_float(row[volume_col], "volume")
                            if volume_col and row.get(volume_col) not in (None, "")
                            else 0.0
                        ),
                        timeframe=timeframe,
                    )
                )
            except ValueError as exc:
                raise ValueError(f"Row {row_number}: {exc}") from exc

    if not candles:
        raise ValueError(f"CSV file contains no data rows: {path}")

    if not symbol:
        symbol = path.stem
    # Validate OHLC sanity on every bar.
    for index, candle in enumerate(candles):
        if not (candle.low <= candle.open <= candle.high and candle.low <= candle.close <= candle.high):
            raise ValueError(
                f"Row {index + 2}: OHLC inconsistent "
                f"(o={candle.open} h={candle.high} l={candle.low} c={candle.close})"
            )
    return candles