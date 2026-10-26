"""Parquet loader — canonical historical OHLCV into ``list[Candle]``.

The Phase A data acceptance (``06_RESEARCH/DATA_ACCEPTANCE_REPORT.md``)
designated ``07_DATA/XAUUSD_M1.parquet`` as the CANONICAL backtest series.
Per the plan (``00_LOCKED/POST_V1_PLAN_OF_ACTION.md`` §3 A6), ALL Phase B/C
runs must load the canonical dataset through this module.

Expected parquet layout (exact Phase A schema):

    timestamp, open, high, low, close, volume

``timestamp`` is tz-NAIVE wall time from the vendor export; values are read
as UTC (``tz_localize``, never ``tz_convert`` — A2 ruling). Rows must be in
chronological (ascending) order; duplicates and non-finite OHLC values are
rejected.

Requires ``pandas`` (with a parquet engine: pyarrow or fastparquet) — the
loader is intentionally thin and raises ``ImportError`` with a clear message
when pandas is unavailable, mirroring the stdlib-only spirit of
``csv_loader`` elsewhere.
"""

from __future__ import annotations

from datetime import timezone
from pathlib import Path

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle

__all__ = ["load_ohlcv_parquet"]

_REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")


def load_ohlcv_parquet(
    filepath: str | Path,
    timeframe: Timeframe = Timeframe.M1,
    symbol: str = "",
) -> list[Candle]:
    """Load a chronological OHLCV parquet file into Candle objects.

    Naive timestamps are localized to UTC; tz-aware timestamps are converted
    to UTC. Prices must be finite and positive; volume must be a
    non-negative number.
    """
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - environment guard
        raise ImportError(
            "load_ohlcv_parquet requires pandas (plus pyarrow or fastparquet)"
        ) from exc

    frame = pd.read_parquet(filepath)
    missing = [c for c in _REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"Parquet {filepath}: missing columns {missing}")

    stamps = pd.to_datetime(frame["timestamp"])
    if stamps.dt.tz is None:
        stamps = stamps.dt.tz_localize("UTC")  # A2: localize, never convert
    else:
        stamps = stamps.dt.tz_convert("UTC")

    candles: list[Candle] = []
    previous = None
    for row, stamp in zip(
        frame[["open", "high", "low", "close", "volume"]].itertuples(
            index=False, name=None
        ),
        stamps,
    ):
        open_, high, low, close, volume = (float(v) for v in row)
        ts = stamp.to_pydatetime().astimezone(timezone.utc)
        if previous is not None and ts <= previous:
            raise ValueError(
                f"Parquet {filepath}: non-chronological or duplicate "
                f"timestamp {ts.isoformat()}"
            )
        previous = ts
        for name, value in (
            ("open", open_),
            ("high", high),
            ("low", low),
            ("close", close),
        ):
            if value != value or value in (float("inf"), float("-inf")):
                raise ValueError(f"Parquet {filepath}: non-finite {name}")
            if value <= 0:
                raise ValueError(f"Parquet {filepath}: non-positive {name} {value}")
        if volume < 0:
            raise ValueError(f"Parquet {filepath}: negative volume {volume}")
        candles.append(
            Candle(
                timestamp=ts,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=volume,
                timeframe=timeframe,
            )
        )
    return candles
