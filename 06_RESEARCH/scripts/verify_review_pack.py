"""Independent verification of the structure-ledger review pack.

Checks every PNG in ``review_sample/`` against BOTH independent sources:

1. LOCKED RULES (00_LOCKED flowchart §16 + FLOWCHART_CODE_EVIDENCE_MAP +
   FLOWCHART_MATCH_NOTES + SMC_VISUALIZATION_ROADMAP V0/V1):
   - chart TF rule : route_ltf/intent/fill chart on M5 (exec TF); every
                     other type charts on its detection TF.
   - sweep         : related_event_id links to a liquidity_level row
                     (levels -> sweep chain) unless the level was dropped by
                     the documented warm-up rule (rel_dangling mark); price
                     is a level price, not a band; H1/H4 only.
   - fvg           : positive gap height (3-candle imbalance zone bounds).
   - poi_raw       : M8 rows carry only code-yielded kind labels.
   - poi_armed     : linked POI + displacement >= 1xATR (BOS+FVG+1xATR rule).
   - route_ltf/fill: entry + original_sl present; SL on the protective side.
   - all rows      : caption fields equal the ledger CSV row (identity-first
                     V0/V1 rule: charts render code-emitted fields only).
   Divergences BETWEEN code output and locked rules (e.g. entry outside the
   recorded zone = documented open mismatch #5) are FLAGS, not chart
   failures: the deliverable's requirement is to display what the code
   emitted, never to fix or hide it.

2. PIXELS (independent re-read of the PNG): candle colours present, the
   event zone overlay present (strong blue line OR alpha-blended light-blue
   band), the yellow event-bar marker, and the purple entry line when an
   entry exists — so a blank/wrong figure FAILS.

READ-ONLY. Writes verification_matrix.json next to the pack.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT = REPO_ROOT / "06_RESEARCH/results/structure_ledger_6m"
PNG_DIR = RESULT / "review_sample"
M5_TYPES = {"route_ltf", "intent", "fill"}


def load_rows() -> dict[str, dict]:
    with (RESULT / "events.csv").open(encoding="utf-8", newline="") as fh:
        return {r["event_id"]: r for r in csv.DictReader(fh)}


# ---------------------------------------------------------------- pixels ---
def pixel_classes(png: Path) -> dict[str, int]:
    from PIL import Image
    img = Image.open(png).convert("RGB")
    w, h = img.size
    data = img.tobytes()
    n = len(data) // 3
    counts = {"green": 0, "red": 0, "blue_strong": 0, "blue_light": 0,
              "yellow": 0, "purple": 0, "width": w, "height": h, "total": w * h}
    step = max(1, n // 400000)  # sample <=400k px, deterministic
    for i in range(0, n, step):
        r = data[3 * i]
        g = data[3 * i + 1]
        b = data[3 * i + 2]
        # candles
        if abs(r - 0x2E) <= 60 and abs(g - 0x7D) <= 60 and abs(b - 0x32) <= 60:
            counts["green"] += 1
            continue
        if abs(r - 0xC6) <= 60 and abs(g - 0x28) <= 60 and abs(b - 0x28) <= 60:
            counts["red"] += 1
            continue
        # zone line (solid) / zone band (alpha 0.18 over white -> light blue)
        if abs(r - 0x1E) <= 60 and abs(g - 0x88) <= 60 and abs(b - 0xE5) <= 60:
            counts["blue_strong"] += 1
            continue
        if b > r + 25 and b > g + 10 and r > 150:
            counts["blue_light"] += 1
            continue
        # event bar
        if abs(r - 0xF9) <= 60 and abs(g - 0xA8) <= 60 and abs(b - 0x25) <= 60:
            counts["yellow"] += 1
            continue
        # entry / SL dashed lines
        if abs(r - 0x6A) <= 60 and abs(g - 0x1B) <= 60 and abs(b - 0x9A) <= 60:
            counts["purple"] += 1
    return counts


# ------------------------------------------------------------- rule checks --
def check(item: dict, rows: dict[str, dict],
          types: dict[str, str]) -> tuple[list[str], list[str]]:
    """Returns (errors, flags). Errors = chart fails its requirement."""
    errs: list[str] = []
    flags: list[str] = []
    eid = item["event_id"]
    row = rows.get(eid)
    if row is None:
        return [f"event_id {eid} absent from events.csv (fabricated sample?)"], []
    for field in ("event_type", "detection_tf", "direction"):
        if str(row[field]) != str(item.get(field, row[field])):
            errs.append(f"caption {field}={item.get(field)!r} != ledger {row[field]!r}")
    if row["event_type"] not in M5_TYPES and \
            item.get("chart_tf") != item.get("detection_tf"):
        errs.append(f"chart_tf {item['chart_tf']} != detect {row['detection_tf']}"
                    " for a non-LTF type")
    if row["event_type"] in M5_TYPES and item.get("chart_tf") != "M5":
        errs.append(f"{row['event_type']} must chart on M5 (exec TF), got {item.get('chart_tf')}")

    low, high = float(row["price_low"]), float(row["price_high"])
    etype = row["event_type"]

    if etype == "sweep":
        rel = row["related_event_id"]
        if "rel_dangling" in row["notes"]:
            flags.append("linked level dropped by warm-up retain_window "
                         "(documented exception; level price kept in notes)")
        elif rel and types.get(rel) == "liquidity_level":
            pass
        else:
            errs.append(f"sweep not linked to a liquidity_level (rel={rel or '∅'})")
        if abs(high - low) > 1e-9:
            errs.append(f"sweep price is a band {low}-{high}, not a level price")
        if row["detection_tf"] not in ("H1", "H4"):
            errs.append(f"sweep on unexpected TF {row['detection_tf']}")
    elif etype == "fvg":
        if high - low <= 0:
            errs.append("fvg zone has no height (3-candle imbalance bounds empty)")
    elif etype == "poi_raw":
        notes = row["notes"]
        if "M8" in str(row["model_tags"]) and \
                not ("kind=ob" in notes or "kind=demand_supply" in notes):
            errs.append("M8 poi_raw without code-yielded kind label")
    elif etype == "poi_armed":
        disp = row["disp_magnitude_atr"]
        if not disp or float(disp) < 1.0:
            flags.append(f"armed below 1xATR displacement (got {disp or '∅'})")
        if not row["related_event_id"]:
            errs.append("armed row not linked to a POI event")
    elif etype in ("route_ltf", "fill"):
        if not row["entry"]:
            errs.append(f"{etype} without entry price")
        else:
            entry = float(row["entry"])
            if not (low - 1e-6 <= entry <= high + 1e-6):
                flags.append(f"entry {entry} outside recorded zone {low}-{high} "
                             "(documented open mismatch #5: zone-entry divergence)")
        if not row["original_sl"]:
            errs.append(f"{etype} without original_sl at placement")
        else:
            entry, sl = float(row["entry"]), float(row["original_sl"])
            if row["direction"] == "SHORT" and not sl > entry:
                errs.append(f"SHORT sl {sl} not above entry {entry}")
            if row["direction"] == "LONG" and not sl < entry:
                errs.append(f"LONG sl {sl} not below entry {entry}")

    return errs, flags


def check_pixels(row: dict, counts: dict) -> list[str]:
    errs: list[str] = []
    if counts.get("total", 0) < 100_000:
        errs.append("suspiciously small image")
    if counts["green"] < 50 or counts["red"] < 50:
        errs.append(f"candles missing (green={counts['green']} red={counts['red']})")
    if counts["blue_strong"] + counts["blue_light"] < 50:
        errs.append("event zone/level overlay missing (no strong or light blue)")
    if counts["yellow"] < 10:
        errs.append("event-bar marker missing")
    if row.get("entry") and counts["purple"] < 10:
        errs.append("entry line missing though entry exists")
    return errs


def main() -> int:
    global PNG_DIR
    parser = argparse.ArgumentParser(
        description="Independent verification of a structure-ledger review pack.")
    parser.add_argument("--png-dir", default=None,
                        help="folder of review PNGs (default: review_sample/). Use "
                             "review_sample_v2 to verify the plain-labelled rebuild.")
    parser.add_argument("--out", default=None,
                        help="matrix output path (default: verification_matrix.json in the "
                             "results root). Keeps the canonical matrix intact when "
                             "verifying an alternate chart folder.")
    args = parser.parse_args()
    if args.png_dir:
        PNG_DIR = Path(args.png_dir)
        if not PNG_DIR.is_absolute():
            PNG_DIR = REPO_ROOT / PNG_DIR
    print(f"verifying charts in: {PNG_DIR}")
    summary = json.loads((RESULT / "summary.json").read_text(encoding="utf-8"))
    sample = summary["review_sample"]
    rows = load_rows()
    types = {eid: r["event_type"] for eid, r in rows.items()}
    failures = 0
    flagged = 0
    matrix = []
    for item in sample:
        png = PNG_DIR / item["file"]
        errs: list[str] = []
        flags: list[str] = []
        row = rows.get(item["event_id"], {})
        counts: dict = {}
        if not png.is_file():
            errs.append("PNG missing on disk")
        else:
            counts = pixel_classes(png)
            errs += check_pixels(row, counts)
        rule_errs, rule_flags = check(item, rows, types)
        errs += rule_errs
        flags += rule_flags
        status = "PASS" if not errs else "FAIL"
        failures += bool(errs)
        flagged += bool(flags)
        matrix.append({"file": item["file"], "event_id": item["event_id"],
                       "event_type": item["event_type"], "chart_tf": item["chart_tf"],
                       "ts_utc": item.get("ts_utc"), "status": status,
                       "flags": flags, "errors": errs,
                       "pixels": {k: counts.get(k) for k in
                                  ("green", "red", "blue_strong",
                                   "blue_light", "yellow", "purple")}})
        print(f"{status}  {item['file']}")
        for e in errs:
            print(f"      !! {e}")
        for f in flags:
            print(f"      ~~ flag: {f}")

    out = Path(args.out) if args.out else (RESULT / "verification_matrix.json")
    if not out.is_absolute():
        out = REPO_ROOT / out
    out.write_text(json.dumps({
        "pack_size": len(sample), "failures": failures, "flagged": flagged,
        "rules_source": ["00_LOCKED LOCKED_DECISIONS §16 flowchart",
                         "FLOWCHART_CODE_EVIDENCE_MAP",
                         "FLOWCHART_MATCH_NOTES",
                         "SMC_VISUALIZATION_ROADMAP V0/V1"],
        "charts": matrix}, indent=2), encoding="utf-8")
    print(f"\n{len(sample) - failures}/{len(sample)} PASS, {flagged} flagged "
          f"-> {out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
