"""R3 baseline attribution + rule identity (Track R, POST_V1_ACTIVE_TODO.md item R3).

Offline diagnosis only. Explains the frozen Phase C book by exit attribution,
trigger-family decomposition, recoverable rule identity, and a mechanical
failure-mode taxonomy. No strategy redesign, no locked-constant edits.

Reads (never writes to source data):
  - results/phase_c_baseline_run1/merged/trades.csv (761 rows)
  - results/r1_mfe_mae/trades_mfe_mae.csv (R1 excursions)
  - results/r2_tp_counterfactual/r2_summary.json (no-BE control arm only)
  - 07_DATA/XAUUSD_M1.parquet via load_ohlcv_parquet (session/ATR context)

Writes (research artifacts only):
  - results/r3_attribution/trades_identity.csv  (per-trade identity table)
  - results/r3_attribution/summary_by_trigger.csv
  - results/r3_attribution/summary_by_failure_mode.csv
  - results/r3_attribution/r3_summary.json

Identity recovery (honest): trigger/poi_id/route_id/direction/entry/sl/exit/
timestamps/bars come from the trade export. Model tags are NOT on the export
(report.json by_poi carries P/L only) -> recorded as 'unknown', never
invented. Session is derived from entry_at hour (locked §2 windows); year
from entry_at; ATR(14) Wilder at entry_bar + stop/ATR ratio computed from the
canonical series (diagnostic context, not a rule).

Failure taxonomy (mutually exclusive, evaluated in order):
  1. friday_artifact : close_kind == 'friday_eod'
  2. be_scratch      : pnl > 0 (BE-protected positive close, stop_loss kind)
  3. instant_stop    : never_favorable == 1 (zero favorable excursion)
  4. no_follow_through : 0 < MFE_R < 1.0
  5. gave_back       : MFE_R >= 1.0 with pnl <= 0 (reached 1R+, still lost)
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

RES = REPO_ROOT / "06_RESEARCH" / "results"
TRADES_CSV = RES / "phase_c_baseline_run1" / "merged" / "trades.csv"
R1_CSV = RES / "r1_mfe_mae" / "trades_mfe_mae.csv"
R2_JSON = RES / "r2_tp_counterfactual" / "r2_summary.json"
PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
OUT_DIR = RES / "r3_attribution"


def session_of(hour: int) -> str:
    if 0 <= hour < 7:
        return "asia"
    if 7 <= hour < 13:
        return "london"
    if 13 <= hour < 20:
        return "new_york"
    return "off_session"


def main() -> dict:
    from smc.data.parquet_loader import load_ohlcv_parquet

    print("[r3] loading canonical series ...", flush=True)
    candles = load_ohlcv_parquet(PARQUET)
    n = len(candles)
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    closes = [c.close for c in candles]
    # Wilder ATR(14) over the full series (diagnostic context only).
    tr = [highs[0] - lows[0]]
    for i in range(1, n):
        tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]),
                      abs(lows[i] - closes[i - 1])))
    atr = [0.0] * n
    s = sum(tr[:14]) / 14.0
    atr[13] = s
    for i in range(14, n):
        s = (s * 13.0 + tr[i]) / 14.0
        atr[i] = s
    print(f"[r3] {n} bars; ATR(14) ready", flush=True)

    trades = {r["route_id"]: r for r in
              csv.DictReader(open(TRADES_CSV, newline=""))}
    r1 = {r["route_id"]: r for r in
          csv.DictReader(open(R1_CSV, newline=""))}
    assert set(trades) == set(r1), "R1/trades route mismatch"
    r2 = json.load(open(R2_JSON))["arms"] if R2_JSON.exists() else []
    print(f"[r3] {len(trades)} trades x R1 rows aligned", flush=True)

    ident: list[dict] = []
    for rid, t in trades.items():
        m = r1[rid]
        b0 = int(t["entry_bar"])
        pnl = float(t["pnl"])
        mfe_r = float(m["MFE_R"])
        never_fav = int(m["never_favorable"])
        entry = float(t["entry_price"])
        risk = abs(entry - float(t["sl"]))
        a = atr[b0] if b0 < n else 0.0
        from datetime import datetime
        ts = datetime.fromisoformat(t["entry_at"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if t["close_kind"] == "friday_eod":
            mode = "friday_artifact"
        elif pnl > 0:
            mode = "be_scratch"
        elif never_fav == 1:
            mode = "instant_stop"
        elif mfe_r < 1.0:
            mode = "no_follow_through"
        else:
            mode = "gave_back"
        exit_class = ("friday" if mode == "friday_artifact"
                      else "be_scratch" if mode == "be_scratch"
                      else "full_sl")
        ident.append({
            "route_id": rid, "poi_id": t["poi_id"], "trigger": t["trigger"],
            "model_tags": "unknown", "direction": t["direction"],
            "entry_price": entry, "sl": float(t["sl"]),
            "exit_price": float(t["exit_price"]),
            "entry_bar": b0, "exit_bar": int(t["exit_bar"]),
            "hold_bars": int(t["exit_bar"]) - b0,
            "entry_at": t["entry_at"], "year": ts.year,
            "session": session_of(ts.hour),
            "atr14_at_entry": a,
            "stop_atr_ratio": (risk / a) if a > 0 else "",
            "MFE_R": mfe_r, "MAE_R": float(m["MAE_R"]),
            "never_favorable": never_fav,
            "bars_to_mfe": m["bars_to_mfe"],
            "close_kind": t["close_kind"], "pnl": pnl,
            "exit_class": exit_class, "failure_mode": mode,
        })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "trades_identity.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ident[0].keys()))
        w.writeheader()
        w.writerows(ident)

    def med(vals):
        s = sorted(vals)
        if not s:
            return None
        m = len(s) // 2
        return (s[m - 1] + s[m]) / 2.0 if len(s) % 2 == 0 else s[m]

    def pf(rows):
        w = sum(r["pnl"] for r in rows if r["pnl"] > 0)
        los = -sum(r["pnl"] for r in rows if r["pnl"] < 0)
        return (w / los) if los > 0 else "None"

    trig_rows, mode_rows = [], []
    for trig in sorted({r["trigger"] for r in ident}):
        sub = [r for r in ident if r["trigger"] == trig]
        wins = sum(1 for r in sub if r["pnl"] > 0)
        modes = Counter(r["failure_mode"] for r in sub)
        trig_rows.append({
            "trigger": trig, "n": len(sub), "wins": wins,
            "win_rate": wins / len(sub) * 100.0,
            "net_raw": sum(r["pnl"] for r in sub),
            "profit_factor": pf(sub),
            "median_hold_bars": med([r["hold_bars"] for r in sub]),
            "median_MFE_R": med([r["MFE_R"] for r in sub]),
            "median_MAE_R": med([r["MAE_R"] for r in sub]),
            "pct_never_favorable": sum(r["never_favorable"] for r in sub)
            / len(sub) * 100.0,
            "dominant_death_mode": modes.most_common(1)[0][0],
            "exit_mix_full_sl": sum(1 for r in sub
                                    if r["exit_class"] == "full_sl"),
            "exit_mix_be_scratch": sum(1 for r in sub
                                       if r["exit_class"] == "be_scratch"),
            "exit_mix_friday": sum(1 for r in sub
                                   if r["exit_class"] == "friday"),
        })
    for mode in ["friday_artifact", "be_scratch", "instant_stop",
                 "no_follow_through", "gave_back"]:
        sub = [r for r in ident if r["failure_mode"] == mode]
        if not sub:
            continue
        mode_rows.append({
            "failure_mode": mode, "n": len(sub),
            "pct_book": len(sub) / len(ident) * 100.0,
            "net_raw": sum(r["pnl"] for r in sub),
            "median_hold_bars": med([r["hold_bars"] for r in sub]),
            "top_trigger": Counter(r["trigger"] for r in sub).most_common(1)[0][0],
        })

    with open(OUT_DIR / "summary_by_trigger.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(trig_rows[0].keys()))
        w.writeheader()
        w.writerows(trig_rows)
    with open(OUT_DIR / "summary_by_failure_mode.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(mode_rows[0].keys()))
        w.writeheader()
        w.writerows(mode_rows)

    # Ablations from the stored book (measurement only, no re-runs).
    def book(rows):
        wins = sum(1 for r in rows if r["pnl"] > 0)
        return {"n": len(rows),
                "win_rate": wins / len(rows) * 100.0 if rows else 0.0,
                "net_raw": sum(r["pnl"] for r in rows), "pf": pf(rows)}

    no_be = next((a for a in r2 if a["arm"] == "TP_INF"), None)
    summary = {
        "trades": len(ident),
        "exit_mix": {k: sum(1 for r in ident if r["exit_class"] == k)
                     for k in ("full_sl", "be_scratch", "friday")},
        "by_trigger": trig_rows,
        "by_failure_mode": mode_rows,
        "ablations": {
            "F_only": book([r for r in ident if r["trigger"] == "F"]),
            "no_F": book([r for r in ident if r["trigger"] != "F"]),
            "B_only": book([r for r in ident if r["trigger"] == "B"]),
            "A_only": book([r for r in ident if r["trigger"] == "A"]),
            "BE_on_baseline": {"n": 761, "net_raw": -47.81,
                               "pf": 0.344, "note": "cited Phase C"},
            "no_BE_TP_INF": ({"n": no_be["trades"],
                              "net_raw": no_be["net_raw"],
                              "pf": no_be["profit_factor"]}
                             if no_be else "r2_summary.json absent"),
        },
        "year_net": {str(y): round(sum(r["pnl"] for r in ident
                                       if r["year"] == y), 3)
                     for y in sorted({r["year"] for r in ident})},
        "session_counts": dict(Counter(r["session"] for r in ident)),
    }
    with open(OUT_DIR / "r3_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[r3] wrote identity ({len(ident)} rows) + summaries", flush=True)
    return summary


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
