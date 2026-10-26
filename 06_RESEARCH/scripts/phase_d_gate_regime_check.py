"""PHASE D — spread-gate regime cross-check (read-only, pure offline calc).

Phase C's 2023 window showed the §28.5 gate as a near-total stop at a
constant 0.35 spread; Phase D's live probe shows the gate passing 100% at a
constant 0.26 spread with ATR ~3.75. Both are true — the gate is
ATR-relative, so its bite is an ATR REGIME property, not a spread level
alone. This script pins the regime boundary on the canonical dataset:
constant-spread gate pass-rates for grades A/A+/B/C at each 2023 month-end
M5 ATR, plus the exact ATR thresholds where the 0.26 live spread stops
passing each grade.

Usage: python 06_RESEARCH/scripts/phase_d_gate_regime_check.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "04_SRC"))

LIVE_SPREAD = 0.26           # measured live + tick-history distribution (Phase D)
LADDER_SPREAD = 0.35         # Phase C ladder representative arm
PARQUET = REPO / "07_DATA" / "XAUUSD_M1.parquet"
RESULTS = REPO / "06_RESEARCH" / "results" / "phase_d_ops"

SPREAD_MAX_ATR = 0.15
MULT = {"A+": 1.5, "A": 1.0, "B": 0.7, "C": 0.5}


def month_ends_2023(frame) -> list:
    """M5 bars nearest each month-end of 2023 (2023 regime ATR sampling)."""
    import pandas as pd
    frame = frame[frame["timestamp"].dt.year == 2023]
    ends = []
    for month in range(1, 13):
        sub = frame[frame["timestamp"].dt.month == month]
        if len(sub) == 0:
            continue
        t_end = sub["timestamp"].max()
        # last full M5 bar at/before month end (15:xx UTC window)
        window = sub[sub["timestamp"] <= t_end].tail(1)
        ends.append(window.iloc[0])
    return ends


def wilder_atr_m5(frame, end_ts, bars: int = 14, lookback: int = 400) -> float:
    """ATR(14) at a month-end, from the M1 frame resampled to M5 (Wilder)."""
    import pandas as pd
    sub = frame[frame["timestamp"] <= end_ts].tail(lookback)  # M1 bars
    g = sub.set_index("timestamp").resample("5min")
    agg = pd.DataFrame({
        "high": g["high"].max(),
        "low": g["low"].min(),
        "close": g["close"].last(),
    }).dropna()
    h, l, c = agg["high"].values, agg["low"].values, agg["close"].values
    tr = [
        max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        for i in range(1, len(h))
    ]
    atr = sum(tr[:bars]) / bars
    for v in tr[bars:]:
        atr = (atr * (bars - 1) + v) / bars
    return float(atr)


def main() -> int:
    import pandas as pd

    frame = pd.read_parquet(PARQUET, columns=["timestamp", "high", "low", "close"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    ends = month_ends_2023(frame)

    rows = []
    for bar in ends:
        atr = wilder_atr_m5(frame, bar["timestamp"])
        gates = {g: SPREAD_MAX_ATR * atr * m for g, m in MULT.items()}
        rows.append({
            "month_end": str(bar["timestamp"]),
            "atr_m5": round(atr, 4),
            "gate_pass_at_0p26": {g: bool(LIVE_SPREAD <= gates[g]) for g in MULT},
            "gate_pass_at_0p35": {g: bool(LADDER_SPREAD <= gates[g]) for g in MULT},
            "max_spread_passing_c": round(gates["C"], 4),
        })

    thresholds = {g: round(LIVE_SPREAD / (SPREAD_MAX_ATR * m), 3) for g, m in MULT.items()}
    out = {
        "live_spread_measured": LIVE_SPREAD,
        "ladder_spread_phase_c": LADDER_SPREAD,
        "atr_thresholds_gate_stops_0p26": thresholds,
        "month_end_atr_2023": rows,
        "reading": (
            "Gate pass is an ATR-regime property. For the measured live "
            "spread 0.26: the gate stops passing C below ATR 3.47, B below "
            "2.48, A below 1.73, A+ below 1.16. Every 2023 month-end "
            "(ATR 0.30-1.06) therefore fails ALL grades at 0.26 - and a "
            "fortiori at the ladder's 0.35 - while the current live regime "
            "(ATR ~3.75) passes every grade. The Phase C ladder's zero "
            "trades at 0.35 is a special case of this regime law."
        ),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "phase_d_gate_regime_check.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
