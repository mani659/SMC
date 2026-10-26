"""Phase A acceptance — canonical parquet loader unit tests.

``load_ohlcv_parquet`` is the ONLY sanctioned path for loading the canonical
dataset in Phase B/C runs (POST_V1_PLAN_OF_ACTION.md §3 A6). These tests pin
its contract: UTC localization (A2 ruling — localize naive, never convert),
chronology enforcement, OHLC finiteness, and Candle round-trip fidelity.

Synthetic frames only — the 34 MB canonical file stays out of the suite.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.data.parquet_loader import load_ohlcv_parquet


def _frame(
    stamps: list[str],
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(stamps),
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [0] * len(stamps),
        }
    )


def _standard_frame() -> pd.DataFrame:
    return _frame(
        ["2025-10-01 10:00", "2025-10-01 10:01", "2025-10-01 10:02"],
        [100.0, 100.5, 101.0],
        [100.9, 101.2, 101.5],
        [99.8, 100.1, 100.6],
        [100.5, 101.0, 101.2],
    )


def test_loads_naive_timestamps_as_utc(tmp_path):
    path = tmp_path / "m1.parquet"
    _standard_frame().to_parquet(path)

    candles = load_ohlcv_parquet(path)

    assert len(candles) == 3
    assert all(isinstance(c, Candle) for c in candles)
    assert all(c.timeframe is Timeframe.M1 for c in candles)
    first = candles[0]
    assert first.timestamp.tzinfo is not None
    assert first.timestamp.utcoffset().total_seconds() == 0
    assert first.timestamp == datetime(2025, 10, 1, 10, 0, tzinfo=timezone.utc)
    # Round-trip fidelity (A1): OHLC survives the load exactly.
    assert (first.open, first.high, first.low, first.close) == (100.0, 100.9, 99.8, 100.5)


def test_converts_tz_aware_timestamps_to_utc(tmp_path):
    path = tmp_path / "aware.parquet"
    frame = _standard_frame()
    frame["timestamp"] = frame["timestamp"].dt.tz_localize("America/New_York")
    frame.to_parquet(path)

    candles = load_ohlcv_parquet(path)

    assert candles[0].timestamp == datetime(
        2025, 10, 1, 14, 0, tzinfo=timezone.utc
    )  # 10:00 EDT == 14:00 UTC


def test_rejects_duplicate_timestamps(tmp_path):
    path = tmp_path / "dup.parquet"
    frame = _standard_frame()
    frame = pd.concat([frame, frame.iloc[[1]]], ignore_index=True)
    frame.to_parquet(path)

    with pytest.raises(ValueError, match="chronological"):
        load_ohlcv_parquet(path)


def test_rejects_non_finite_and_non_positive_prices(tmp_path):
    path = tmp_path / "bad.parquet"
    frame = _standard_frame()
    frame.loc[1, "close"] = float("nan")
    frame.to_parquet(path)
    with pytest.raises(ValueError, match="non-finite close"):
        load_ohlcv_parquet(path)

    path2 = tmp_path / "zero.parquet"
    frame2 = _standard_frame()
    frame2.loc[0, "open"] = 0.0
    frame2.to_parquet(path2)
    with pytest.raises(ValueError, match="non-positive open"):
        load_ohlcv_parquet(path2)


def test_rejects_missing_columns(tmp_path):
    path = tmp_path / "incomplete.parquet"
    _standard_frame().drop(columns=["volume"]).to_parquet(path)

    with pytest.raises(ValueError, match="missing columns"):
        load_ohlcv_parquet(path)


def test_accepts_negative_volume_rejection_and_zero_volume(tmp_path):
    path = tmp_path / "negvol.parquet"
    frame = _standard_frame()
    frame.loc[0, "volume"] = -1
    frame.to_parquet(path)
    with pytest.raises(ValueError, match="negative volume"):
        load_ohlcv_parquet(path)

    ok = tmp_path / "zerovol.parquet"
    _standard_frame().to_parquet(ok)  # canonical dataset is all-zero volume
    assert all(c.volume == 0.0 for c in load_ohlcv_parquet(ok))
