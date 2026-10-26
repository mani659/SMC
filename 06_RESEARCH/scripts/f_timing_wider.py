"""F-timing wider-sample validation (Lead Architect instruction).

Applies FROZEN rule v1 (imported, not copied, from f_timing_labels — any
drift would be an import error, not a silent retune) to a pooled,
deduplicated set of unique F setups from all instrumented verify exports.
Honest MFE with original_sl; timestamp-anchored bars.

Reads: results/export_patch_verify/verify_w*/trades.csv + canonical parquet.
Writes: results/f_timing_wider/f_timing_wider_labels.csv + summary JSON.

Windows overlap in time (w0 = Oct 1-8, w1 = Oct 1-15) so cross-window
dedup by (direction, entry, original_sl) keeping the earliest fill is
mandatory — reported. No strategy code, no thresholds, no live gates.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

from f_timing_labels import CHASE_HI, CHASE_LO, CHOP_ATR_MULT, PRE_BARS

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "f_timing_wider"
VERIFY_ROOT = REPO_ROOT / "06_RESEARCH" / "results" / "export_patch_verify"
PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"


def label_v1(chase_pos, range_atr):
    if chase_pos == "" or range_atr == "":
        return "unclear"
    if range_atr < CHOP_ATR_MULT:
        return "chop"
    if chase_pos >= CHASE_HI:
        return "late_chase"
    if chase_pos >= CHASE_LO:
        return "mid_move"
    return "structured_pullback"


def main(trigger: str = "F") -> dict:
    import pandas as pd

    pooled: dict = {}
    for export in sorted(VERIFY_ROOT.glob("verify_w*/trades.csv")):
        for r in csv.DictReader(open(export, newline="", encoding="utf-8")):
            if r["trigger"] != trigger:
                continue
            k = (r["direction"], r["entry_price"], r["original_sl"] or r["sl"])
            if k not in pooled or r["entry_at"] < pooled[k][1]["entry_at"]:
                pooled[k] = (export.parent.name, r)
    print(f"[wider] pooled unique {trigger} setups: {len(pooled)}", flush=True)

    frame = pd.read_parquet(PARQUET, columns=["timestamp", "high", "low",
                                              "close"])
    tskeys = frame["timestamp"].astype(str).str[:16].tolist()
    index_of = {}
    for i, k in enumerate(tskeys):
        index_of.setdefault(k, i)
    hi, lo, cl = (frame["high"].to_numpy(), frame["low"].to_numpy(),
                  frame["close"].to_numpy())
    n = len(frame)
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
    for src, t in sorted(pooled.values(), key=lambda kv: kv[1]["entry_at"]):
        b0 = index_of[t["entry_at"][:16]]
        a0 = max(0, b0 - PRE_BARS)
        w_hi, w_lo = float(hi[a0:b0].max()), float(lo[a0:b0].min())
        entry = float(t["entry_price"])
        sl_o = float(t["original_sl"]) if t["original_sl"] else float(t["sl"])
        risk = abs(entry - sl_o)
        rng = w_hi - w_lo
        is_long = t["direction"] == "long"
        if rng <= 0 or atr[b0] <= 0:
            chase, ratr, label = "", "", "unclear"
        else:
            chase = ((entry - w_lo) / rng) if is_long else ((w_hi - entry) / rng)
            ratr = rng / atr[b0]
            label = label_v1(chase, ratr)
        zl = float(t["zone_low"]) if t["zone_low"] else None
        zh = float(t["zone_high"]) if t["zone_high"] else None
        if zl is None or zh is None or zh <= zl:
            zone_rel = "unknown"
        elif zl <= entry <= zh:
            zone_rel = "INSIDE"
        else:
            off = entry - zh if entry > zh else zl - entry
            side = "above" if entry > zh else "below"
            zone_rel = f"{side} {100.0 * off / (zh - zl):.0f}%"
        out.append({
            "src_export": src, "ticket": t["ticket"], "route_id": t["route_id"],
            "direction": t["direction"], "entry_at": t["entry_at"][:16],
            "entry_price": entry, "original_sl": sl_o,
            "chase_pos": round(chase, 3) if chase != "" else "",
            "range_atr": round(ratr, 3) if ratr != "" else "",
            "timing_label": label, "zone_relation": zone_rel,
            "model_tags": t["model_tags"],
            "disp_magnitude_atr": t["disp_magnitude_atr"],
            "pnl": t["pnl"], "close_kind": t["close_kind"],
            "_b0": b0,
        })

    # Honest MFE walk needs each setup's own exit bar: resolve from export.
    by_route = {}
    for export in sorted(VERIFY_ROOT.glob("verify_w*/trades.csv")):
        for r in csv.DictReader(open(export, newline="", encoding="utf-8")):
            by_route.setdefault(r["route_id"], r)
    for o in out:
        src_row = by_route[o["route_id"]]
        b1 = index_of[src_row["exit_at"][:16]]
        b0 = o.pop("_b0")
        b0, b1 = min(b0, b1), max(b0, b1)
        entry, risk = o["entry_price"], abs(o["entry_price"] - o["original_sl"])
        is_long = o["direction"] == "long"
        fav = [((hi[b] - entry) if is_long else (entry - lo[b]))
               for b in range(b0, b1 + 1)]
        raw = max(fav)
        o["MFE_R_honest"] = round(max(raw, 0.0) / risk, 4)
        o["never_favorable"] = int(raw < 0)
        o["reach_1R"] = int(max(raw, 0.0) / risk >= 1.0)
        o["reach_2R"] = int(max(raw, 0.0) / risk >= 2.0)
        o["hold_bars"] = b1 - b0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "f_timing_wider_labels.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    from collections import Counter
    counts = dict(Counter(r["timing_label"] for r in out))

    def med(vals):
        s = sorted(vals)
        m = len(s) // 2
        return (s[m - 1] + s[m]) / 2.0 if len(s) % 2 == 0 else s[m]

    by_label = {}
    for lab in sorted(set(counts)):
        sub = [r for r in out if r["timing_label"] == lab]
        by_label[lab] = {
            "n": len(sub),
            "median_MFE_R_honest": med([r["MFE_R_honest"] for r in sub]),
            "pct_ge_1R": sum(r["reach_1R"] for r in sub) / len(sub) * 100.0,
            "pct_ge_2R": sum(r["reach_2R"] for r in sub) / len(sub) * 100.0,
        }
    summary = {"setups": len(out), "label_counts": counts,
               "by_label": by_label,
               "rule": {"pre_bars": PRE_BARS, "chop_atr_mult": CHOP_ATR_MULT,
                        "chase_hi": CHASE_HI, "chase_lo": CHASE_LO,
                        "imported_from": "f_timing_labels (frozen v1)"}}
    with open(OUT_DIR / "f_timing_wider_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[wider] wrote {len(out)} labels: {counts}", flush=True)
    return summary


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
