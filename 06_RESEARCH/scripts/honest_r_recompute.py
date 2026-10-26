"""Honest-R recompute (Track R follow-on): MFE/MAE with original_sl denominator.

Corrects the BE contamination found in flowchart match notes: exported `sl`
is post-BE-modify, so R1/R2/R3 R-multiples on BE-touched trades used a
BE-tightened denominator. Here every trade is measured TWICE over its own
stored window (R1 path rules — full bar ranges, floored at 0):

  honest        risk = |entry - original_sl|
  contaminated  risk = |entry - working sl|   (replica of R1's denominator)

Sample (labeled, NOT generalized): unique setups from the instrumented
verify_w0 window (2025-10-01..08), deduplicated post-hoc by
(direction, entry, original_sl) keeping the earliest fill — the verify run
over-arms without ZoneRegistry dedup, so 115 rows collapse to unique setups.
Phase C book comparison is book-level side-by-side (different trades).

Reads: results/export_patch_verify/verify_w0/trades.csv +
07_DATA/XAUUSD_M1.parquet (timestamp-anchored bars; short-window bar indices
are window-relative and must NOT index the canonical series directly).
Writes: results/honest_r_recompute/trades_honest_r.csv + honest_r_summary.json.

No strategy code, no thresholds, no reruns — pure measurement.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "honest_r_recompute"
TRADES_CSV = (REPO_ROOT / "06_RESEARCH" / "results" / "export_patch_verify"
              / "verify_w0" / "trades.csv")
PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"


def main() -> dict:
    import pandas as pd

    rows = list(csv.DictReader(open(TRADES_CSV, newline="", encoding="utf-8")))
    # Dedup to unique setups (same limit + same original stop = same setup
    # re-armed); keep earliest fill.
    seen: dict = {}
    for r in rows:
        k = (r["direction"], r["entry_price"], r["original_sl"] or r["sl"])
        if k not in seen or r["entry_at"] < seen[k]["entry_at"]:
            seen[k] = r
    setups = sorted(seen.values(), key=lambda r: r["entry_at"])
    print(f"[honest-r] {len(rows)} rows -> {len(setups)} unique setups",
          flush=True)

    frame = pd.read_parquet(PARQUET, columns=["timestamp", "high", "low",
                                              "close"])
    tskeys = frame["timestamp"].astype(str).str[:16].tolist()
    index_of = {}
    for i, k in enumerate(tskeys):
        index_of.setdefault(k, i)
    hi, lo, cl = (frame["high"].to_numpy(), frame["low"].to_numpy(),
                  frame["close"].to_numpy())
    n = len(frame)
    # Wilder ATR(14), diagnostic context only (same construction as R3).
    tr = hi - lo
    tr[1:] = __import__("numpy").maximum(
        tr[1:], __import__("numpy").maximum(
            abs(hi[1:] - cl[:-1]), abs(lo[1:] - cl[:-1])))
    atr = __import__("numpy").zeros(n)
    s = tr[:14].mean()
    atr[13] = s
    for i in range(14, n):
        s = (s * 13.0 + tr[i]) / 14.0
        atr[i] = s

    out: list[dict] = []
    for t in setups:
        b0 = index_of[t["entry_at"][:16]]
        b1 = index_of[t["exit_at"][:16]]
        b0, b1 = min(b0, b1), max(b0, b1)
        entry = float(t["entry_price"])
        sl_w = float(t["sl"])
        sl_o = float(t["original_sl"]) if t["original_sl"] else sl_w
        risk_h = abs(entry - sl_o)
        risk_w = abs(entry - sl_w)
        is_long = t["direction"] == "long"
        fav, adv = [], []
        for b in range(b0, b1 + 1):
            if is_long:
                fav.append(hi[b] - entry)
                adv.append(entry - lo[b])
            else:
                fav.append(entry - lo[b])
                adv.append(hi[b] - entry)
        raw_mfe, raw_mae = max(fav), max(adv)
        never_fav = raw_mfe < 0
        mfe, mae = max(raw_mfe, 0.0), max(raw_mae, 0.0)
        pnl = float(t["pnl"])
        if t["close_kind"] == "friday_eod":
            mode = "friday_artifact"
        elif pnl > 0:
            mode = "be_scratch"
        elif never_fav:
            mode = "instant_stop"
        elif mfe / risk_h < 1.0:
            mode = "no_follow_through"
        else:
            mode = "gave_back"
        out.append({
            "ticket": t["ticket"], "route_id": t["route_id"],
            "trigger": t["trigger"], "direction": t["direction"],
            "entry_price": entry, "original_sl": sl_o, "working_sl": sl_w,
            "be_modified": int(abs(sl_w - sl_o) > 1e-9),
            "risk_honest": risk_h, "risk_working": risk_w,
            "MFE_price": mfe, "MAE_price": mae,
            "MFE_R_honest": mfe / risk_h, "MAE_R_honest": mae / risk_h,
            "MFE_R_contam": mfe / risk_w, "MAE_R_contam": mae / risk_w,
            "bars_to_mfe": "" if never_fav else fav.index(raw_mfe),
            "never_favorable": int(never_fav),
            "reach_1R_honest": int(mfe / risk_h >= 1.0),
            "reach_2R_honest": int(mfe / risk_h >= 2.0),
            "reach_3R_honest": int(mfe / risk_h >= 3.0),
            "failure_mode_honest": mode,
            "stop_atr_honest": risk_h / atr[b0] if atr[b0] > 0 else "",
            "hold_bars": b1 - b0, "pnl": pnl,
            "close_kind": t["close_kind"],
            "model_tags": t["model_tags"], "pillar_path": t["pillar_path"],
            "disp_magnitude_atr": t["disp_magnitude_atr"],
        })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "trades_honest_r.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    def med(vals):
        s = sorted(vals)
        m = len(s) // 2
        return (s[m - 1] + s[m]) / 2.0 if len(s) % 2 == 0 else s[m]

    def pct(key, x):
        return sum(1 for r in out if r[key] >= x) / len(out) * 100.0

    by_trig = {}
    for trig in sorted({r["trigger"] for r in out}):
        sub = [r for r in out if r["trigger"] == trig]
        by_trig[trig] = {
            "n": len(sub), "median_MFE_R_honest": med([r["MFE_R_honest"] for r in sub]),
            "pct_ge_1R_honest": sum(r["reach_1R_honest"] for r in sub) / len(sub) * 100.0,
            "median_stop_atr_honest": med([r["stop_atr_honest"] for r in sub
                                           if r["stop_atr_honest"] != ""]),
        }
    summary = {
        "setups": len(out),
        "be_modified_setups": sum(r["be_modified"] for r in out),
        "median_MFE_R_honest": med([r["MFE_R_honest"] for r in out]),
        "median_MAE_R_honest": med([r["MAE_R_honest"] for r in out]),
        "median_MFE_R_contam": med([r["MFE_R_contam"] for r in out]),
        "pct_ge_1R_honest": pct("MFE_R_honest", 1.0),
        "pct_ge_2R_honest": pct("MFE_R_honest", 2.0),
        "pct_ge_3R_honest": pct("MFE_R_honest", 3.0),
        "pct_ge_1R_contam": pct("MFE_R_contam", 1.0),
        "never_favorable": sum(r["never_favorable"] for r in out),
        "median_stop_atr_honest": med([r["stop_atr_honest"] for r in out
                                       if r["stop_atr_honest"] != ""]),
        "by_trigger": by_trig,
        "full_sl_only": {},  # filled below
    }
    full = [r for r in out if not (r["pnl"] > 0 and r["close_kind"] == "stop_loss")]
    summary["full_sl_only"] = {
        "n": len(full), "median_MFE_R_honest": med([r["MFE_R_honest"] for r in full]),
        "pct_ge_1R_honest": sum(r["reach_1R_honest"] for r in full) / len(full) * 100.0,
    }
    with open(OUT_DIR / "honest_r_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[honest-r] wrote {len(out)} setup rows", flush=True)
    return summary


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
