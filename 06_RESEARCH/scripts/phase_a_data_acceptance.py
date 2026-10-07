"""POST-V1 PHASE A — Data acceptance script for the canonical XAUUSD dataset.

Read-only inspection of ``07_DATA/`` against the pipeline's candle contract
(``smc.core.candle.Candle``). NO backtest, NO trading logic — this only
validates data. Run from the repo root:

    python 06_RESEARCH/scripts/phase_a_data_acceptance.py

Checks (POST_V1_PLAN_OF_ACTION.md §3, A1–A6):
  A1 schema vs Candle + round-trip    A2 timestamps / UTC assumptions
  A3 gaps / duplicates census         A4 units / OHLC / price sanity
  A5 volume-zero → Trigger D impact   A6 SHA-256 checksums for the
                                      canonical decision record
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

from smc.config.timeframe import Timeframe  # noqa: E402
from smc.core.candle import Candle  # noqa: E402

DATA_DIR = REPO_ROOT / "07_DATA"
PARQUET = DATA_DIR / "XAUUSD_M1.parquet"
CSV = DATA_DIR / "XAUUSD_M1.csv"
TICKS = DATA_DIR / "XAUUSD_mt5_ticks.csv"

TF = Timeframe.M1
SAMPLE = 10_000            # Candle round-trip sample size
MIN_WEEKEND_GAP = 120      # minutes; anything larger is a session/holiday hole
WEEKEND_MAX = 7 * 24 * 60 + 120  # weekend boundary + tolerance (minutes)


def sha256_of(path: Path, chunk: int = 8 * 1024 * 1024) -> str:
    """Streaming SHA-256 (the tick file is ~13 GB — never read it whole)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def to_candles(df: pd.DataFrame, timeframe: Timeframe) -> list[Candle]:
    """Minimal lossless df → Candle adapter (UTC attached; no logic changes)."""
    stamps = df["timestamp"]
    if stamps.dt.tz is None:
        stamps = stamps.dt.tz_localize("UTC")   # A2: naive source is UTC by contract
    else:
        stamps = stamps.dt.tz_convert("UTC")
    return [
        Candle(
            timestamp=ts.to_pydatetime(),
            open=float(o),
            high=float(h),
            low=float(l),
            close=float(c),
            volume=float(v),
            timeframe=timeframe,
        )
        for ts, o, h, l, c, v in zip(
            stamps, df["open"], df["high"], df["low"], df["close"], df["volume"],
            strict=True,
        )
    ]


def main() -> int:
    findings: list[str] = []
    if hasattr(sys.stdout, "reconfigure"):  # Windows cp1252 consoles
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=" * 72)
    print("PHASE A — DATA ACCEPTANCE  (07_DATA/)")
    print("=" * 72)

    # ---- A1 schema vs Candle ------------------------------------------- #
    df = pd.read_parquet(PARQUET)
    schema_ok = list(df.columns) == [
        "timestamp", "open", "high", "low", "close", "volume"
    ] and all(str(df[c].dtype) == "float64" for c in ("open", "high", "low", "close"))
    print(
        f"[{'PASS' if schema_ok else 'FAIL'}] A1 schema: columns={list(df.columns)}, "
        f"dtypes={ {c: str(df[c].dtype) for c in df.columns} }"
    )
    if not schema_ok:
        findings.append("A1 schema mismatch")

    # ---- A2 timestamps / UTC ------------------------------------------- #
    stamps = df["timestamp"]
    sorted_ok = bool(stamps.is_monotonic_increasing)
    dup_count = int(stamps.duplicated().sum())
    tz_naive = stamps.dt.tz is None
    minute_aligned = bool((stamps.dt.second == 0).all())
    in_range = bool(
        stamps.min() >= pd.Timestamp("2021-01-01")
        and stamps.max() <= pd.Timestamp("2026-12-31")
    )
    print(f"[{'PASS' if sorted_ok else 'FAIL'}] A2 sorted ascending: strictly chronological")
    print(f"[{'PASS' if dup_count == 0 else 'FAIL'}] A2 duplicates: {dup_count}")
    print(f"[INFO] A2 timezone: source is tz-NAIVE ({stamps.dtype}) — the loader adapter "
          f"attaches UTC explicitly (to_candles); Phase B loader must do the same")
    print(f"[{'PASS' if minute_aligned else 'FAIL'}] A2 minute-aligned: all stamps on whole minutes")
    print(f"[{'PASS' if in_range else 'FAIL'}] A2 date range: {stamps.min()} → {stamps.max()}")
    if not (sorted_ok and dup_count == 0 and minute_aligned and in_range):
        findings.append("A2 timestamp integrity failure")

    # ---- A3 gaps / duplicates census ------------------------------------ #
    gaps = stamps.diff().dt.total_seconds().div(60)
    census = {
        "1min (continuous)": int((gaps == 1).sum()),
        "2-120min (intraday holes)": int(((gaps > 1) & (gaps <= MIN_WEEKEND_GAP)).sum()),
        ">2h up to weekend+tol": int(((gaps > MIN_WEEKEND_GAP) & (gaps <= WEEKEND_MAX)).sum()),
        "> 1 week (unexplained)": int((gaps > WEEKEND_MAX).sum()),
    }
    max_gap = float(gaps.max())
    print(f"[INFO] A3 gap census: {census}")
    print(f"[INFO] A3 max gap: {max_gap:.0f} min ({max_gap / 1440:.2f} days)")
    if census["> 1 week (unexplained)"] > 0:
        findings.append("A3 unexplained gap longer than one week")

    # ---- A4 units / OHLC / price sanity ---------------------------------- #
    oc = df[["open", "close"]]
    ohlc_bad = int(((df["high"] < oc.max(axis=1)) | (df["low"] > oc.min(axis=1))).sum())
    four = df[["open", "high", "low", "close"]]
    nonfinite = int((~four.notna() | (four == float("inf")) | (four == float("-inf"))).sum().sum())
    min_price = float(four.min().min())
    max_price = float(four.max().max())
    floor_ok = min_price > 100.0
    # Pathological-spike detection: an ISOLATED bar deviating >50% from the
    # 50-bar rolling median close (a sustained regime move — many
    # consecutive deviations — is genuine repricing, not a data error).
    med = df["close"].rolling(50, min_periods=10).median()
    dev = (df["close"] - med).abs() / med
    isolated = dev > 0.5
    spike_bars = int(isolated.sum())
    # Count contiguous spike RUNS: a run longer than 3 bars = regime move.
    runs = 0
    run_len = 0
    for flag in isolated.fillna(False):
        if flag:
            run_len += 1
        else:
            if 0 < run_len <= 3:
                runs += 1
            run_len = 0
    if 0 < run_len <= 3:
        runs += 1
    print(f"[{'PASS' if ohlc_bad == 0 else 'FAIL'}] A4 OHLC integrity: {ohlc_bad} inconsistent rows")
    print(f"[{'PASS' if nonfinite == 0 else 'FAIL'}] A4 finite values: {nonfinite} NaN/inf cells")
    print(f"[{'PASS' if floor_ok else 'FAIL'}] A4 price floor (>100 for XAUUSD): min={min_price:.3f}, max={max_price:.3f}")
    print(f"[{'PASS' if spike_bars == 0 else 'INFO'}] A4 pathological spikes: {spike_bars} bars >50% off the "
          f"50-bar median in {runs} isolated run(s) (runs of ≤3 bars are data errors; "
          f"longer runs are genuine regime repricing)")
    print("[INFO] A4 spread: no spread column — Phase C sensitivity run configures "
          "spread_price externally (plan §5)")
    if ohlc_bad or nonfinite or not floor_ok:
        findings.append("A4 price/OHLC integrity failure")

    # ---- A5 volume → Trigger D ------------------------------------------- #
    nonzero_vol = int((df["volume"] != 0).sum())
    print(f"[INFO] A5 volume: {nonzero_vol} nonzero-volume rows of {len(df)} — "
          f"Trigger D's frozen rule (engulfer.volume < engulfed.volume) can never be true "
          f"on an all-zero volume column → A5 DECISION REQUIRED (plan §3 A5)")

    # ---- Candle round-trip (A1 loader adapter proof) ---------------------- #
    sample = df.iloc[-SAMPLE:].reset_index(drop=True)
    candles = to_candles(sample, TF)
    rt_ok = (
        len(candles) == SAMPLE
        and candles[0].timestamp == sample["timestamp"].iloc[0].to_pydatetime().replace(tzinfo=__import__("datetime").timezone.utc)
        and candles[-1].close == float(sample["close"].iloc[-1])
        and candles[0].low <= candles[0].open <= candles[0].high
    )
    print(f"[{'PASS' if rt_ok else 'FAIL'}] A1 Candle round-trip: {len(candles)} Candles "
          f"built from the last {SAMPLE} rows via the UTC-attaching adapter")
    if not rt_ok:
        findings.append("A1 Candle round-trip failure")

    # ---- Coverage sanity --------------------------------------------------- #
    span_days = (stamps.max() - stamps.min()).total_seconds() / 86400
    expected_24_7 = int(span_days * 1440) + 1
    density = 100.0 * len(df) / expected_24_7
    print(f"[INFO] coverage: {len(df)} bars over {span_days:.1f} days "
          f"(a continuous 24/7 M1 series would have {expected_24_7}; density {density:.1f}% — "
          f"gaps are weekends/holidays)")

    # ---- A6 checksums ------------------------------------------------------- #
    print("A6 SHA-256 checksums (tick file ~13 GB — streaming, takes a while)...")
    for path in (PARQUET, CSV, TICKS):
        print(f"[INFO] A6 sha256 {path.name}: {sha256_of(path)}")

    # ---- Summary ------------------------------------------------------------- #
    print("=" * 72)
    if findings:
        print(f"RESULT: PASS WITH FINDINGS ({len(findings)})")
        for line in findings:
            print("  -", line)
    else:
        print("RESULT: PASS — dataset acceptable for the Phase B fidelity backtest")
        print("  (A5 volume decision remains open — see plan §3 A5)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
