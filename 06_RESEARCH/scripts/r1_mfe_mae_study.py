"""R1 MFE/MAE study (Track R, POST_V1_ACTIVE_TODO.md item R1 + R1b).

Offline diagnosis only. For every trade in the frozen Phase C baseline book,
measure max favorable / max adverse excursion (price + R-multiples) and
time-to-MFE over the trade's stored bar window on the canonical M1 series.

Reads (never writes to source data):
  - 06_RESEARCH/results/phase_c_baseline_run1/merged/trades.csv (761 rows)
  - 07_DATA/XAUUSD_M1.parquet via smc.data.parquet_loader.load_ohlcv_parquet
    (the sanctioned Phase B/C input path; read-only use here)

Writes (research artifacts only):
  - 06_RESEARCH/results/r1_mfe_mae/trades_mfe_mae.csv  (per-trade table)
  - 06_RESEARCH/results/r1_mfe_mae/r1_summary.json     (machine-readable stats)

Method per trade (stored bars only, no strategy code touched):
  - window = canonical bars [entry_bar .. exit_bar] inclusive
  - risk_distance = |entry_price - sl|  (all 761 rows have sl; verified pre-run)
  - LONG:  MFE = max(high - entry), MAE = max(entry - low)
  - SHORT: MFE = max(entry - low),  MAE = max(entry - high)
  - MFE_R = MFE / risk_distance, MAE_R = MAE / risk_distance
  - bars_to_mfe = offset (in bars) from entry_bar to the FIRST bar attaining
    MFE within the window (0 = entry bar itself)

Hard rules honored: no parameter changes, no TP in the live system,
no locked-constant edits, no strategy-code changes (this script imports the
data loader only — no detection/trigger/risk modules).
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

TRADES_CSV = (
    REPO_ROOT
    / "06_RESEARCH"
    / "results"
    / "phase_c_baseline_run1"
    / "merged"
    / "trades.csv"
)
PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "r1_mfe_mae"


def main() -> dict:
    from smc.data.parquet_loader import load_ohlcv_parquet

    print("[r1] loading canonical series via load_ohlcv_parquet ...", flush=True)
    candles = load_ohlcv_parquet(PARQUET)
    n = len(candles)
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    print(f"[r1] {n} canonical bars loaded", flush=True)

    with open(TRADES_CSV, newline="") as f:
        trades = list(csv.DictReader(f))
    print(f"[r1] {len(trades)} baseline trades loaded", flush=True)

    rows: list[dict] = []
    skipped: list[str] = []
    for t in trades:
        route_id = t["route_id"]
        direction = t["direction"]
        entry = float(t["entry_price"])
        sl = float(t["sl"])
        b0 = int(t["entry_bar"])
        b1 = int(t["exit_bar"])
        if not (0 <= b0 <= b1 < n):
            skipped.append(route_id)
            continue
        risk = abs(entry - sl)
        if risk <= 0:
            skipped.append(route_id)
            continue
        if direction == "long":
            fav = [highs[b] - entry for b in range(b0, b1 + 1)]
            adv = [entry - lows[b] for b in range(b0, b1 + 1)]
        elif direction == "short":
            fav = [entry - lows[b] for b in range(b0, b1 + 1)]
            adv = [highs[b] - entry for b in range(b0, b1 + 1)]
        else:  # pragma: no cover - defensive; dataset has long/short only
            skipped.append(route_id)
            continue
        # Standard MFE/MAE convention: excursions floored at 0 (a negative raw
        # max means price never moved that way — recorded via the flags).
        raw_mfe = max(fav)
        raw_mae = max(adv)
        never_fav = raw_mfe < 0
        never_adv = raw_mae < 0
        mfe = 0.0 if never_fav else raw_mfe
        mae = 0.0 if never_adv else raw_mae
        rows.append(
            {
                "route_id": route_id,
                "trigger": t["trigger"],
                "direction": direction,
                "entry_price": entry,
                "sl": sl,
                "risk_distance": risk,
                "entry_bar": b0,
                "exit_bar": b1,
                "window_bars": b1 - b0 + 1,
                "MFE_price": mfe,
                "MAE_price": mae,
                "MFE_R": mfe / risk,
                "MAE_R": mae / risk,
                "bars_to_mfe": "" if never_fav else fav.index(raw_mfe),
                "never_favorable": int(never_fav),
                "never_adverse": int(never_adv),
                "close_kind": t["close_kind"],
                "pnl": float(t["pnl"]),
            }
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / "trades_mfe_mae.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    def pct_ge(key: str, x: float) -> float:
        return sum(1 for r in rows if r[key] >= x) / len(rows) * 100.0

    def median(key: str) -> float:
        s = sorted(r[key] for r in rows)
        m = len(s) // 2
        return (s[m - 1] + s[m]) / 2.0 if len(s) % 2 == 0 else s[m]

    def median_of(vals: list):
        s = sorted(vals)
        if not s:
            return None
        m = len(s) // 2
        return (s[m - 1] + s[m]) / 2.0 if len(s) % 2 == 0 else s[m]

    summary = {
        "trades_analyzed": len(rows),
        "trades_skipped": skipped,
        "pct_mfe_ge_1R": pct_ge("MFE_R", 1.0),
        "pct_mfe_ge_1.5R": pct_ge("MFE_R", 1.5),
        "pct_mfe_ge_2R": pct_ge("MFE_R", 2.0),
        "pct_mfe_ge_3R": pct_ge("MFE_R", 3.0),
        "median_MFE_R": median("MFE_R"),
        "median_MAE_R": median("MAE_R"),
        "mean_MFE_R": sum(r["MFE_R"] for r in rows) / len(rows),
        "mean_MAE_R": sum(r["MAE_R"] for r in rows) / len(rows),
        "median_bars_to_mfe": median_of(
            [r["bars_to_mfe"] for r in rows if r["never_favorable"] == 0]
        ),
        "median_window_bars": median("window_bars"),
        "never_favorable_count": sum(r["never_favorable"] for r in rows),
        "never_adverse_count": sum(r["never_adverse"] for r in rows),
    }
    by_trigger: dict[str, dict] = {}
    for trig in sorted({r["trigger"] for r in rows}):
        sub = [r for r in rows if r["trigger"] == trig]
        by_trigger[trig] = {
            "n": len(sub),
            "median_MFE_R": median_of([r["MFE_R"] for r in sub]),
            "median_MAE_R": median_of([r["MAE_R"] for r in sub]),
            "pct_mfe_ge_1R": sum(1 for r in sub if r["MFE_R"] >= 1.0)
            / len(sub)
            * 100.0,
            "pct_mfe_ge_2R": sum(1 for r in sub if r["MFE_R"] >= 2.0)
            / len(sub)
            * 100.0,
            "pct_mfe_ge_3R": sum(1 for r in sub if r["MFE_R"] >= 3.0)
            / len(sub)
            * 100.0,
            "median_bars_to_mfe": median_of(
                [r["bars_to_mfe"] for r in sub if r["never_favorable"] == 0]
            ),
        }
    summary["by_trigger"] = by_trigger
    out_json = OUT_DIR / "r1_summary.json"
    with open(out_json, "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    print(f"[r1] wrote {out_csv} ({len(rows)} rows, {len(skipped)} skipped)", flush=True)
    print(f"[r1] wrote {out_json}", flush=True)
    return summary


if __name__ == "__main__":
    s = main()
    print(json.dumps(s, indent=2, sort_keys=True))
