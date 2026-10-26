"""F-timing follow-on (research annotation, NOT a live gate).

v2 label rules (committed here BEFORE running — single pass, no iteration
to maximize separation; see F_TIMING_FOLLOWON_NOTES.md for rationale):

  chop perjudicial: >= 12 direction reversals in trailing 29 close steps
      AND |net displacement| < 1.0x ATR(14) at entry   (oscillating + net-flat)
  v_shape_recovery: trailing drop >= 1.5x ATR into the window trough AND
      entry recovered >= 50% of that drop            (V-recovery retest shape)
  calm_pullback: chase_pos < 0.45                        (unchanged v1 tail)
  structured_pullback_v2 = v_shape_recovery OR calm_pullback
  late_chase / mid_move: unchanged v1 ladder (0.80 / 0.45)
  unclear: degenerate range or missing data

Rule order: chop -> structured_pullback_v2 -> chase ladder.
v1 labels joined from results/f_timing_wider (itself frozen-v1) for the
v1-vs-v2 comparison — never recomputed here.

Reads: verify_w0 + verify_w1 trades.csv (pooled, deduped like the wider
study) + canonical parquet (timestamp-anchored) + f_timing_wider labels.
Writes: results/f_timing_followon/followon_labels.csv + summary JSON.

No strategy code, no thresholds on trading paths, original_sl only.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "f_timing_followon"
VERIFY_ROOT = REPO_ROOT / "06_RESEARCH" / "results" / "export_patch_verify"
WIDER_CSV = (REPO_ROOT / "06_RESEARCH" / "results" / "f_timing_wider"
             / "f_timing_wider_labels.csv")
PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"

PRE_BARS = 30
REVERSAL_MIN, NET_ATR_MAX = 12, 1.0
VDROP_ATR_MIN, VREC_MIN = 1.5, 0.50


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
    setups = sorted(pooled.values(), key=lambda kv: kv[1]["entry_at"])
    print(f"[followon] pooled unique {trigger} setups: {len(setups)}", flush=True)

    v1 = {r["route_id"]: r["timing_label"] for r in
          csv.DictReader(open(WIDER_CSV, newline="", encoding="utf-8"))}

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
    for _src, t in setups:
        b0 = index_of[t["entry_at"][:16]]
        a0 = max(0, b0 - PRE_BARS)
        w_hi, w_lo = float(hi[a0:b0].max()), float(lo[a0:b0].min())
        w_cl = cl[a0:b0]
        entry = float(t["entry_price"])
        sl_o = float(t["original_sl"]) if t["original_sl"] else float(t["sl"])
        risk = abs(entry - sl_o)
        is_long = t["direction"] == "long"
        a = atr[b0]
        # Chop: reversals + net-flat.
        steps = [1 if w_cl[i + 1] > w_cl[i] else (-1 if w_cl[i + 1] < w_cl[i] else 0)
                 for i in range(len(w_cl) - 1)]
        rev = sum(1 for i in range(1, len(steps))
                  if steps[i] != 0 and steps[i - 1] != 0 and steps[i] != steps[i - 1])
        net = abs(w_cl[-1] - w_cl[0]) / a if a > 0 else float("inf")
        # V-shape: drop into trailing trough + recovery by entry.
        trough = float(lo[a0:b0].min())
        pre_high = float(hi[a0:a0 + int(__import__("numpy").argmin(lo[a0:b0])) + 1].max())
        drop = (pre_high - trough) / a if a > 0 else 0.0
        rec = ((entry - trough) / (pre_high - trough)
               if pre_high > trough else 0.0)
        rng = w_hi - w_lo
        if rng <= 0 or a <= 0:
            label, chase = "unclear", ""
        elif rev >= REVERSAL_MIN and net < NET_ATR_MAX:
            label = "chop"
            chase = (((entry - w_lo) / rng) if is_long
                     else ((w_hi - entry) / rng))
        elif drop >= VDROP_ATR_MIN and rec >= VREC_MIN:
            label = "structured_pullback"
            chase = (((entry - w_lo) / rng) if is_long
                     else ((w_hi - entry) / rng))
        else:
            chase = (((entry - w_lo) / rng) if is_long
                     else ((w_hi - entry) / rng))
            label = ("late_chase" if chase >= 0.80
                     else "mid_move" if chase >= 0.45
                     else "structured_pullback")
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
            "ticket": t["ticket"], "route_id": t["route_id"],
            "direction": t["direction"], "entry_at": t["entry_at"][:16],
            "entry_price": entry, "original_sl": sl_o,
            "label_v1": v1.get(t["route_id"], "missing"),
            "timing_label_v2": label,
            "chase_pos": round(chase, 3) if chase != "" else "",
            "range_atr": round(rng / a, 3) if a > 0 else "",
            "reversals_29": rev, "net_displacement_atr": round(net, 3),
            "v_drop_atr": round(drop, 3), "v_recovery_frac": round(rec, 3),
            "zone_relation": zone_rel,
            "model_tags": t["model_tags"], "pnl": t["pnl"],
            "risk_honest": risk,
            "_b0": b0,
        })

    # Honest MFE walk (original_sl denominator, R1 path rules).
    by_route = {}
    for export in sorted(VERIFY_ROOT.glob("verify_w*/trades.csv")):
        for r in csv.DictReader(open(export, newline="", encoding="utf-8")):
            by_route.setdefault(r["route_id"], r)
    for o in out:
        src_row = by_route[o["route_id"]]
        b1 = index_of[src_row["exit_at"][:16]]
        b0 = o.pop("_b0")
        b0, b1 = min(b0, b1), max(b0, b1)
        is_long = o["direction"] == "long"
        fav = [((hi[b] - o["entry_price"]) if is_long
                else (o["entry_price"] - lo[b])) for b in range(b0, b1 + 1)]
        raw = max(fav)
        o["MFE_R_honest"] = round(max(raw, 0.0) / o["risk_honest"], 4)
        o["never_favorable"] = int(raw < 0)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "followon_labels.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    from collections import Counter
    v1c = dict(Counter(r["label_v1"] for r in out))
    v2c = dict(Counter(r["timing_label_v2"] for r in out))
    xtab: dict = {}
    for r in out:
        xtab.setdefault(r["label_v1"], Counter())[r["timing_label_v2"]] += 1
    xtab = {k: dict(v) for k, v in xtab.items()}

    def med(vals):
        s = sorted(vals)
        m = len(s) // 2
        return (s[m - 1] + s[m]) / 2.0 if len(s) % 2 == 0 else s[m]

    by_v2 = {}
    for lab in sorted(set(v2c)):
        sub = [r for r in out if r["timing_label_v2"] == lab]
        by_v2[lab] = {
            "n": len(sub),
            "median_MFE_R_honest": med([r["MFE_R_honest"] for r in sub]),
            "pct_ge_1R": sum(1 for r in sub if r["MFE_R_honest"] >= 1.0)
            / len(sub) * 100.0,
        }
    summary = {"setups": len(out), "v1_counts": v1c, "v2_counts": v2c,
               "v1_to_v2": xtab, "by_v2": by_v2}
    with open(OUT_DIR / "followon_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[followon] wrote {len(out)} labels: {v2c}", flush=True)
    return summary


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
