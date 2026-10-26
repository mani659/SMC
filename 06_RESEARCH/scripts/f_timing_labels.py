"""F-timing discriminator labels (research annotation, NOT a live gate).

Mechanical-as-possible timing labels for unique F setups from an
instrumented export: direction-adjusted position inside the trailing
30-bar range plus range/ATR chop detection. Rule v1 (frozen; definitions
in F_TIMING_DISCRIMINATOR_NOTES.md):

  chop                30-bar range < 1.5x ATR(14) at entry
  late_chase          chase_pos >= 0.80
  mid_move            0.45 <= chase_pos < 0.80
  structured_pullback chase_pos < 0.45
  unclear             degenerate range or missing data

chase_pos is direction-adjusted so 1 = extreme in trade direction
(long: (entry-lo)/(hi-lo); short: (hi-entry)/(hi-lo)) over trailing
30 bars. Zone relation reported on a separate axis (inside / above /
below + % of zone height) — timing and zone-distance are independent.

Reads: instrumented trades.csv (needs original_sl + zone bounds) +
canonical parquet (timestamp-anchored bars) + honest_r table (join by
ticket for MFE/failure columns where present).
Writes: results/f_timing/f_timing_labels.csv + f_timing_summary.json.

No strategy code, no thresholds on trading paths — labels only.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "f_timing"
TRADES_CSV = (REPO_ROOT / "06_RESEARCH" / "results" / "export_patch_verify"
              / "verify_w0" / "trades.csv")
HONEST_CSV = (REPO_ROOT / "06_RESEARCH" / "results" / "honest_r_recompute"
              / "trades_honest_r.csv")
PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"

PRE_BARS = 30
CHOP_ATR_MULT = 1.5
CHASE_HI, CHASE_LO = 0.80, 0.45


def main(trigger: str = "F") -> dict:
    import pandas as pd

    rows = list(csv.DictReader(open(TRADES_CSV, newline="", encoding="utf-8")))
    seen: dict = {}
    for r in rows:
        if r["trigger"] != trigger:
            continue
        k = (r["direction"], r["entry_price"], r["original_sl"] or r["sl"])
        if k not in seen or r["entry_at"] < seen[k]["entry_at"]:
            seen[k] = r
    setups = sorted(seen.values(), key=lambda r: r["entry_at"])
    print(f"[f-timing] {trigger} unique setups: {len(setups)}", flush=True)

    hon = {}
    try:
        hon = {r["ticket"]: r for r in
               csv.DictReader(open(HONEST_CSV, newline="", encoding="utf-8"))}
    except FileNotFoundError:
        print("[f-timing] honest_r table absent — R columns will be empty",
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
        a0 = max(0, b0 - PRE_BARS)
        w_hi, w_lo = float(hi[a0:b0].max()), float(lo[a0:b0].min())
        entry = float(t["entry_price"])
        rng = w_hi - w_lo
        is_long = t["direction"] == "long"
        if rng <= 0 or atr[b0] <= 0:
            label, chase, ratr = "unclear", "", ""
        else:
            chase = ((entry - w_lo) / rng) if is_long else ((w_hi - entry) / rng)
            ratr = rng / atr[b0]
            if ratr < CHOP_ATR_MULT:
                label = "chop"
            elif chase >= CHASE_HI:
                label = "late_chase"
            elif chase >= CHASE_LO:
                label = "mid_move"
            else:
                label = "structured_pullback"
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
        h = hon.get(t["ticket"], {})
        out.append({
            "ticket": t["ticket"], "route_id": t["route_id"],
            "direction": t["direction"], "entry_at": t["entry_at"][:16],
            "entry_price": entry,
            "original_sl": t["original_sl"] or t["sl"],
            "chase_pos": round(chase, 3) if chase != "" else "",
            "range_atr": round(ratr, 3) if ratr != "" else "",
            "timing_label": label,
            "zone_relation": zone_rel,
            "model_tags": t["model_tags"],
            "disp_magnitude_atr": t["disp_magnitude_atr"],
            "MFE_R_honest": h.get("MFE_R_honest", ""),
            "failure_mode_honest": h.get("failure_mode_honest", ""),
            "pnl": t["pnl"],
        })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "f_timing_labels.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    from collections import Counter
    counts = dict(Counter(r["timing_label"] for r in out))
    summary = {"setups": len(out), "label_counts": counts,
               "rule": {"pre_bars": PRE_BARS, "chop_atr_mult": CHOP_ATR_MULT,
                        "chase_hi": CHASE_HI, "chase_lo": CHASE_LO}}
    with open(OUT_DIR / "f_timing_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[f-timing] wrote {len(out)} labels: {counts}", flush=True)
    return summary


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
