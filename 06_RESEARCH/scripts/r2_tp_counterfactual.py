"""R2 synthetic TP counterfactuals (Track R, POST_V1_ACTIVE_TODO.md item R2).

Offline diagnosis only. Replays the frozen Phase C entry book (same entries,
same ORIGINAL stops — no BE, no FVG exits) under fixed-R take-profits and
scores first-touch resolution with the frozen same-bar SL-first tie-break.

Arms: TP_1.5R, TP_2R, TP_3R + TP_INF (no-TP machinery check).
Control (reported, not replayed): the published BE-only baseline book
(PF 0.344 — Phase C report; the replay deliberately excludes BE so TP arms
are UPPER BOUNDS on any BE+TP system — disclosed in the report).

Reads (never writes to source data):
  - 06_RESEARCH/results/phase_c_baseline_run1/merged/trades.csv (761 rows)
  - 07_DATA/XAUUSD_M1.parquet via smc.data.parquet_loader.load_ohlcv_parquet

Writes (research artifacts only):
  - 06_RESEARCH/results/r2_tp_counterfactual/trades_r2.csv
  - 06_RESEARCH/results/r2_tp_counterfactual/summary_by_policy.csv
  - 06_RESEARCH/results/r2_tp_counterfactual/per_trigger_policy.csv

Resolution rules per trade, bars [entry_bar .. exit_bar] inclusive:
  - LONG:  sl hit iff low <= sl; tp hit iff high >= tp (SHORT mirrored).
  - SL evaluated from entry_bar; TP evaluated from entry_bar + 1
    (conservative fill-ordering: fill precedes any TP credit on the fill bar;
    mirrors the frozen fill-before-entry conservatism).
  - Same bar touching both -> SL wins (frozen tie-break).
  - Friday-EOD trades unresolved by exit_bar close at the baseline
    exit_price/pnl (real recorded close, not invention).
  - Non-Friday trades unresolved by exit_bar -> OPEN (excluded from
    PF/WR/net, counted per arm and disclosed).

Hard rules honored: no parameter changes, no TP in the live system,
no locked-constant edits, no strategy-code changes (data loader only).
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
OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "r2_tp_counterfactual"

ARMS: dict[str, float | None] = {
    "TP_1.5R": 1.5,
    "TP_2R": 2.0,
    "TP_3R": 3.0,
    "TP_INF": None,  # no-TP machinery check (fixed-SL replay, no BE)
}
PIP_VALUE_PER_LOT = 10.0
EQUITY_START = 10_000.0


def main() -> dict:
    from smc.data.parquet_loader import load_ohlcv_parquet

    print("[r2] loading canonical series via load_ohlcv_parquet ...", flush=True)
    candles = load_ohlcv_parquet(PARQUET)
    n = len(candles)
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    print(f"[r2] {n} canonical bars loaded", flush=True)

    with open(TRADES_CSV, newline="") as f:
        trades = list(csv.DictReader(f))
    print(f"[r2] {len(trades)} baseline trades loaded", flush=True)

    per_trade: list[dict] = []
    for t in trades:
        direction = t["direction"]
        entry = float(t["entry_price"])
        sl = float(t["sl"])
        b0 = int(t["entry_bar"])
        b1 = int(t["exit_bar"])
        risk = abs(entry - sl)
        is_long = direction == "long"
        base = {
            "route_id": t["route_id"],
            "trigger": t["trigger"],
            "direction": direction,
            "risk_distance": risk,
        }
        for arm, mult in ARMS.items():
            tp = entry + (1.0 if is_long else -1.0) * mult * risk if mult else None
            outcome = "OPEN"
            close_r = 0.0
            close_bar = b1
            for b in range(b0, b1 + 1):
                hi, lo = highs[b], lows[b]
                if is_long:
                    sl_hit = lo <= sl
                    tp_hit = tp is not None and b > b0 and hi >= tp
                else:
                    sl_hit = hi >= sl
                    tp_hit = tp is not None and b > b0 and lo <= tp
                if sl_hit:  # SL-first tie-break (frozen rule)
                    outcome, close_r, close_bar = "SL", -1.0, b
                    break
                if tp_hit:
                    outcome, close_r, close_bar = "TP", mult, b
                    break
            if outcome == "OPEN" and t["close_kind"] == "friday_eod":
                # Real recorded Friday close — same as baseline, not invention.
                outcome = "FRIDAY_BASELINE"
                close_r = float(t["pnl"]) / 0.1 / risk
                close_bar = b1
            per_trade.append(
                {**base, "arm": arm, "outcome": outcome,
                 "close_R": close_r, "close_bar": close_bar}
            )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / "trades_r2.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_trade[0].keys()))
        w.writeheader()
        w.writerows(per_trade)

    # Per-arm books (OPEN excluded; FRIDAY_BASELINE scored at baseline R).
    summary_rows: list[dict] = []
    trig_rows: list[dict] = []
    for arm in ARMS:
        sub = [r for r in per_trade if r["arm"] == arm]
        resolved = [r for r in sub if r["outcome"] != "OPEN"]
        opens = len(sub) - len(resolved)
        wins = [r for r in resolved if r["close_R"] > 0]
        gross_w = sum(r["close_R"] * r["risk_distance"] * 0.1 for r in wins)
        gross_l = -sum(
            r["close_R"] * r["risk_distance"] * 0.1
            for r in resolved if r["close_R"] < 0
        )
        net_raw = gross_w - gross_l
        pf = (gross_w / gross_l) if gross_l > 0 else None
        eq, dd, peak = EQUITY_START, 0.0, EQUITY_START
        for r in resolved:
            eq += r["close_R"] * r["risk_distance"] * 0.1 * PIP_VALUE_PER_LOT
            peak = max(peak, eq)
            dd = max(dd, peak - eq)
        summary_rows.append({
            "arm": arm, "trades": len(sub), "resolved": len(resolved),
            "open_excluded": opens,
            "tp_wins": sum(1 for r in resolved if r["outcome"] == "TP"),
            "sl_losses": sum(1 for r in resolved if r["outcome"] == "SL"),
            "win_rate": len(wins) / len(resolved) * 100.0 if resolved else 0.0,
            "net_raw": net_raw, "net_ccy": net_raw * PIP_VALUE_PER_LOT,
            "profit_factor": pf if pf is not None else "None",
            "maxDD_ccy": dd,
        })
        for trig in sorted({r["trigger"] for r in sub}):
            tsub = [r for r in resolved if r["trigger"] == trig]
            if not tsub:
                continue
            tw = sum(r["close_R"] * r["risk_distance"] * 0.1
                     for r in tsub if r["close_R"] > 0)
            tl = -sum(r["close_R"] * r["risk_distance"] * 0.1
                      for r in tsub if r["close_R"] < 0)
            trig_rows.append({
                "arm": arm, "trigger": trig, "n": len(tsub),
                "tp_wins": sum(1 for r in tsub if r["outcome"] == "TP"),
                "win_rate": sum(1 for r in tsub if r["close_R"] > 0)
                / len(tsub) * 100.0,
                "net_raw": tw - tl,
                "profit_factor": (tw / tl) if tl > 0 else "None",
            })

    with open(OUT_DIR / "summary_by_policy.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        w.writeheader()
        w.writerows(summary_rows)
    with open(OUT_DIR / "per_trigger_policy.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(trig_rows[0].keys()))
        w.writeheader()
        w.writerows(trig_rows)

    print(f"[r2] wrote {out_csv} ({len(per_trade)} rows)", flush=True)
    print("[r2] wrote summary_by_policy.csv + per_trigger_policy.csv", flush=True)
    result = {"arms": summary_rows, "by_trigger": trig_rows}
    with open(OUT_DIR / "r2_summary.json", "w") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
