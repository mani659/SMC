"""POST-V1 PHASE C — spread-sensitivity calibration (read-only).

The §28.5 spread gate accepts an entry when

    current_spread_price <= SPREAD_MAX_ATR (0.15) x ATR x grade_multiplier

with grade multipliers A+ 1.5 / A 1.0 / B 0.7 / C 0.5 (LOCKED_DECISIONS
§28.5, ``smc.risk.spread_grading``).  Both sides are in PRICE units: the
runner feeds ``current_spread_price`` (e.g. 0.35 on gold) and the ATR is the
M1 Wilder-RMA(14) true-range series the detection driver publishes
(``smc.utils.atr.atr_series``, MT5 ``iATR``-equivalent).

This script answers two questions with data, so the Phase C sensitivity runs
are calibrated rather than guessed:

  1. What spread values actually bite?  -> percentiles of the gate threshold
     ``0.15 x ATR x multiplier`` over the canonical series, per candidate
     window.  A spread below the 5th percentile is nearly non-binding; a
     spread above the 95th percentile blocks essentially all entries.
  2. Which window is representative?  -> per-quarter ATR level, ATR spread
     (volatility of volatility), and processed-bar count, so the selected
     window can be shown to sit near the full-period medians.

Read-only: reads the canonical parquet, writes one JSON summary.  It never
touches run artifacts.

    python 06_RESEARCH/scripts/phase_c_spread_calibration.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
OUT = REPO_ROOT / "06_RESEARCH" / "results" / "phase_c_spread_calibration.json"

ATR_PERIOD = 14
SPREAD_MAX_ATR = 0.15
GRADE_MULTIPLIERS = {"A+": 1.5, "A": 1.0, "B": 0.7, "C": 0.5}

# Candidate representative windows for the §28.5 sensitivity ladder.
CANDIDATE_WINDOWS = {
    "2023Q1": ("2023-01-01", "2023-03-31"),
    "2023_FebApr": ("2023-02-01", "2023-04-30"),
    "2024Q3": ("2024-07-01", "2024-09-30"),
    "2025Q1": ("2025-01-01", "2025-03-31"),
}


def wilder_atr(frame: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """Wilder RMA ATR over M1 bars (MT5 iATR seed: SMA of first `period` TRs)."""
    prev_close = frame["close"].shift(1)
    tr = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prev_close).abs(),
            (frame["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    seed = tr.iloc[:period].mean()
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    atr.iloc[: period - 1] = np.nan
    atr.iloc[period - 1] = seed
    return atr


def pct(series: pd.Series, qs: tuple[float, ...]) -> dict[str, float]:
    values = series.dropna().to_numpy()
    if values.size == 0:
        return {f"p{int(q * 100)}": None for q in qs}
    out = {}
    for q in qs:
        out[f"p{int(q * 100)}"] = round(float(np.percentile(values, q * 100)), 5)
    out["min"] = round(float(values.min()), 5)
    out["max"] = round(float(values.max()), 5)
    out["mean"] = round(float(values.mean()), 5)
    return out


def main() -> int:
    frame = pd.read_parquet(PARQUET, columns=["timestamp", "high", "low", "close"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    frame["atr"] = wilder_atr(frame)

    qs = (0.05, 0.25, 0.5, 0.75, 0.95)
    report: dict = {
        "atr_period": ATR_PERIOD,
        "spread_max_atr": SPREAD_MAX_ATR,
        "grade_multipliers": GRADE_MULTIPLIERS,
        "series": {
            "bars": int(len(frame)),
            "from": str(frame["timestamp"].iloc[0]),
            "to": str(frame["timestamp"].iloc[-1]),
            "atr_price_units": pct(frame["atr"], qs),
        },
        "gate_threshold_price_units": {},
        "per_quarter_atr": {},
        "candidate_windows": {},
    }

    for grade, mult in GRADE_MULTIPLIERS.items():
        threshold = SPREAD_MAX_ATR * frame["atr"] * mult
        report["gate_threshold_price_units"][grade] = pct(threshold, qs)

    frame["quarter"] = frame["timestamp"].dt.to_period("Q").astype(str)
    for quarter, group in frame.groupby("quarter"):
        report["per_quarter_atr"][quarter] = pct(group["atr"], (0.5,))

    for name, (start, end) in CANDIDATE_WINDOWS.items():
        mask = (frame["timestamp"] >= pd.Timestamp(start, tz="UTC")) & (
            frame["timestamp"] <= pd.Timestamp(end + " 23:59", tz="UTC")
        )
        window = frame.loc[mask]
        entry: dict = {
            "from": start,
            "to": end,
            "bars": int(len(window)),
            "atr_price_units": pct(window["atr"], qs),
            "gate_threshold_price_units": {},
        }
        for grade, mult in GRADE_MULTIPLIERS.items():
            entry["gate_threshold_price_units"][grade] = pct(
                SPREAD_MAX_ATR * window["atr"] * mult, qs
            )
        report["candidate_windows"][name] = entry

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"\n[written] {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
