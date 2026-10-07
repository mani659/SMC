"""Stop-vs-structure study (research measurement, NOT a live rule).

Stop placement quality against structure using original_sl ONLY.
Primary: Trigger B shelf/stop relationship. Secondary: Trigger F contrast.

Per trade (timestamp-anchored bars, own window):
  - risk_o = |entry - original_sl|; stop_atr = risk_o / ATR14(entry)
  - entry↔zone and SL↔zone relations (INSIDE / above|below % of height)
  - shelf touches: pre-30 bars whose range includes original_sl (wick or
    body through the exact stop level) and zone-edge touches
  - exit classification for SL exits: close-through (exit bar CLOSES
    beyond SL = structure break) vs wick-tag (touches but closes back)
  - hold bars, honest MFE/MAE (original_sl denominator), R3-taxonomy mode

Reads: verify_w0 + verify_w1 trades.csv (deduped like the wider study) +
canonical parquet. Writes: results/stop_vs_structure/{table.csv, summary}.

No strategy code, no thresholds, no live gates.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "stop_vs_structure"
VERIFY_ROOT = REPO_ROOT / "06_RESEARCH" / "results" / "export_patch_verify"
PARQUET = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"

PRE_BARS = 30


def zone_rel(price, zl, zh):
    if zl is None or zh is None or zh <= zl:
        return "unknown"
    if zl <= price <= zh:
        return "INSIDE"
    off = price - zh if price > zh else zl - price
    side = "above" if price > zh else "below"
    return f"{side} {100.0 * off / (zh - zl):.0f}%"


def main() -> dict:
    import pandas as pd

    pooled: dict = {}
    for export in sorted(VERIFY_ROOT.glob("verify_w*/trades.csv")):
        for r in csv.DictReader(open(export, newline="", encoding="utf-8")):
            k = (r["direction"], r["entry_price"], r["original_sl"] or r["sl"])
            if k not in pooled or r["entry_at"] < pooled[k][1]["entry_at"]:
                pooled[k] = (export.parent.name, r)
    setups = sorted(pooled.values(), key=lambda kv: kv[1]["entry_at"])
    print(f"[stopstruct] pooled unique setups: {len(setups)}", flush=True)

    frame = pd.read_parquet(PARQUET, columns=["timestamp", "open", "high",
                                              "low", "close"])
    tskeys = frame["timestamp"].astype(str).str[:16].tolist()
    index_of = {}
    for i, k in enumerate(tskeys):
        index_of.setdefault(k, i)
    op, hi, lo, cl = (frame["open"].to_numpy(), frame["high"].to_numpy(),
                      frame["low"].to_numpy(), frame["close"].to_numpy())
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
    for src, t in setups:
        b0 = index_of[t["entry_at"][:16]]
        b1 = index_of[t["exit_at"][:16]]
        b0, b1 = min(b0, b1), max(b0, b1)
        entry = float(t["entry_price"])
        sl_o = float(t["original_sl"]) if t["original_sl"] else float(t["sl"])
        risk = abs(entry - sl_o)
        is_long = t["direction"] == "long"
        a = atr[b0] if b0 < n else 0.0
        zl = float(t["zone_low"]) if t["zone_low"] else None
        zh = float(t["zone_high"]) if t["zone_high"] else None
        # Shelf touches: pre-30 bars whose range includes a level.
        pre = range(max(0, b0 - PRE_BARS), b0)
        sl_touches = sum(1 for b in pre if lo[b] <= sl_o <= hi[b])
        zl_t = sum(1 for b in pre
                   if zl is not None and lo[b] <= zl <= hi[b])
        zh_t = sum(1 for b in pre
                   if zh is not None and lo[b] <= zh <= hi[b])
        # Exit classification (SL exits only): close-through vs wick-tag.
        exit_kind = "non_sl_exit"
        if t["close_kind"] == "stop_loss":
            c1 = cl[b1]
            through = (c1 <= sl_o) if is_long else (c1 >= sl_o)
            exit_kind = "close_through_break" if through else "wick_tag_noise"
        # Honest MFE walk (original_sl denominator, R1 path rules).
        fav = [((hi[b] - entry) if is_long else (entry - lo[b]))
               for b in range(b0, b1 + 1)]
        adv = [((entry - lo[b]) if is_long else (hi[b] - entry))
               for b in range(b0, b1 + 1)]
        raw_mfe, raw_mae = max(fav), max(adv)
        mfe_r = max(raw_mfe, 0.0) / risk
        pnl = float(t["pnl"])
        if t["close_kind"] == "friday_eod":
            mode = "friday_artifact"
        elif pnl > 0:
            mode = "be_scratch"
        elif raw_mfe < 0:
            mode = "instant_stop"
        elif mfe_r < 1.0:
            mode = "no_follow_through"
        else:
            mode = "gave_back"
        has_sig = bool(t.get("signal_data_json"))
        out.append({
            "src": src, "ticket": t["ticket"], "route_id": t["route_id"],
            "trigger": t["trigger"], "direction": t["direction"],
            "entry_at": t["entry_at"][:16], "entry_price": entry,
            "original_sl": sl_o, "risk_honest": risk,
            "stop_atr_honest": round(risk / a, 3) if a > 0 else "",
            "entry_zone_rel": zone_rel(entry, zl, zh),
            "sl_zone_rel": zone_rel(sl_o, zl, zh),
            "sl_level_touches_30": sl_touches,
            "zone_low_touches_30": zl_t, "zone_high_touches_30": zh_t,
            "exit_kind": exit_kind, "hold_bars": b1 - b0,
            "MFE_R_honest": round(mfe_r, 4),
            "MAE_R_honest": round(max(raw_mae, 0.0) / risk, 4),
            "failure_mode": mode, "pnl": pnl,
            "model_tags": t["model_tags"], "signal_geometry": int(has_sig),
        })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "stop_vs_structure.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    def med(vals):
        s = sorted(vals)
        m = len(s) // 2
        return (s[m - 1] + s[m]) / 2.0 if len(s) % 2 == 0 else s[m]

    summary: dict = {"setups": len(out)}
    for trig in sorted({r["trigger"] for r in out}):
        sub = [r for r in out if r["trigger"] == trig]
        sl_exits = [r for r in sub if r["exit_kind"] in
                    ("close_through_break", "wick_tag_noise")]
        summary[trig] = {
            "n": len(sub),
            "median_stop_atr": med([r["stop_atr_honest"] for r in sub
                                    if r["stop_atr_honest"] != ""]),
            "median_sl_touches": med([r["sl_level_touches_30"] for r in sub]),
            "exit_split": {k: sum(1 for r in sl_exits if r["exit_kind"] == k)
                           for k in ("close_through_break", "wick_tag_noise")},
            "inside_zone_entry": sum(1 for r in sub
                                     if r["entry_zone_rel"] == "INSIDE"),
            "modes": {m: sum(1 for r in sub if r["failure_mode"] == m)
                      for m in sorted({r["failure_mode"] for r in sub})},
        }
    with open(OUT_DIR / "stop_vs_structure_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[stopstruct] wrote {len(out)} rows", flush=True)
    return summary


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
