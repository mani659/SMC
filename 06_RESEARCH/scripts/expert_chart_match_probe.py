#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Expert marked charts — system match probe (READ-ONLY).

Lead Architect directive (2026-10-05): archive + inventory + match probe
for the operator's 11 human-marked example charts. No strategy-code edits,
no threshold changes, no new detectors — this script only READS:

  * the archived chart images (03_REFERENCE_CODE/expert_marked_charts/);
  * the pre-computed OCR text (06_RESEARCH/results/expert_marked_charts/
    ocr/ocr_full.json — RapidOCR, harness-local);
  * the frozen 6-month structure ledger (06_RESEARCH/results/
    structure_ledger_6m/events.csv — the existing detection/Stage 3/M8
    outputs the project already uses, events SHA 903e5a3b…).

Mark extraction: saturated-red pixel mask → connected components →
component classes (horizontal zone line / zone box / diagonal line / text
glyph run — glyph runs are the operator's red WRITING, not zones, and are
excluded from matching). Price calibration: linear y→price from the
extreme OCR'd right-axis ticks per chart (approximate; tick spacing
~25–70 price units depending on chart — recorded per chart).

Matching rule (no new detectors): each extracted mark's price zone is
probed against ledger events of the class the operator's marking names.
TF honesty: the ledger has H4/H1/D1 detection only — M5/M1/W1 charts are
probed on the nearest available TF and capped at PARTIAL per the
adjacent-TF rule; displacement events carry no prices in the ledger
(DATA_GAP for that class). Verdicts:
  YES      — same TF, same class event band intersects the mark zone;
  PARTIAL  — match only on nearest available TF (M5/M1/W1 charts), or
             related class;
  NO       — class exists in the ledger window but no band near the zone
             (distance reported);
  DATA_GAP — class carries no usable prices, or chart time unrecoverable
             (no dates are readable on any chart — only a bare clock
             "170000" on chart 6 — so TIME matching is DATA_GAP by design
             for all charts; price-zone matching only, never invented).

Outputs: 06_RESEARCH/results/expert_marked_charts/match_probe.json.
Honesty: verdicts are reported as computed — misses are NOT explained away.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
CHART_DIR = REPO / "03_REFERENCE_CODE" / "expert_marked_charts"
OCR_JSON = REPO / "06_RESEARCH" / "results" / "expert_marked_charts" / "ocr" / "ocr_full.json"
LEDGER_CSV = REPO / "06_RESEARCH" / "results" / "structure_ledger_6m" / "events.csv"
OUT_JSON = REPO / "06_RESEARCH" / "results" / "expert_marked_charts" / "match_probe.json"

# Linear y→price calibration from extreme OCR'd right-axis ticks.
AXIS = {
    "chart_1.jfif": (4529.05, 4103.05),
    "chart_2.jfif": (4236.80, 4116.20),
    "chart_3.jfif": (4723.10, 4099.40),
    "chart_4.jfif": (4306.65, 4252.40),   # partial axis (Fib overlay) — approximate
    "chart_5.jfif": (4529.05, 4103.05),
    "chart_6.jfif": (4407.50, 4297.70),
    "chart_7.jfif": (4932.25, 3924.25),
    "chart_8.jfif": (4402.80, 4280.20),
    "chart_9.jfif": (5705.80, 3347.40),
    "chart_10.jfif": (4188.00, 4109.20),
    "chart_11.jfif": (4412.50, 4105.00),
}

# operator red-text markings (verbatim from the OCR reading, spelling kept)
MARKINGS = {
    "chart_1.jfif": "sweep in H4",
    "chart_2.jfif": "Double TOP in M5 / Here selling confirm",
    "chart_3.jfif": "Sweep in H4",
    "chart_4.jfif": "Confirmaton in M1 @ Fibu golden level / CHOCH / buying",
    "chart_5.jfif": "H4 FVG area",
    "chart_6.jfif": "Ending Diagnol @ H4 FVG area in M1",
    "chart_7.jfif": "D1 structural level sweep",
    "chart_8.jfif": "CHOCH / Fibu Golden ARea in M5",
    "chart_9.jfif": "OB Week",
    "chart_10.jfif": "Double Bottom in M5 / Buying confirmatoin",
    "chart_11.jfif": "entry / entry",
}

# Probe spec per chart: (ledger class, operator TF). TFs the ledger does
# not have (M5, M1, W1) are probed on the nearest TF and capped at PARTIAL.
PROBES = {
    "chart_1.jfif":  [("sweep", "H4")],
    "chart_2.jfif":  [("sweep", "M5→H1"), ("route_ltf", "M5")],
    "chart_3.jfif":  [("sweep", "H4")],
    "chart_4.jfif":  [("fvg", "M1→H1"), ("displacement", "M1→H1")],
    "chart_5.jfif":  [("fvg", "H4")],
    "chart_6.jfif":  [("fvg", "M1/H4")],
    "chart_7.jfif":  [("sweep", "D1")],
    "chart_8.jfif":  [("fvg", "M5→H1"), ("sweep", "M5→H1")],
    "chart_9.jfif":  [("ob", "W1→D1"), ("demand_supply", "W1→D1")],
    "chart_10.jfif": [("sweep", "M5→H1"), ("route_ltf", "M5")],
    "chart_11.jfif": [("poi_armed", "H1"), ("route_ltf", "H1"), ("fill", "H1")],
}


def red_rows(path: Path) -> np.ndarray:
    """Rows containing saturated-red annotation pixels (chart plot area only)."""
    im = np.asarray(Image.open(path).convert("RGB"))
    r = im[:, :1380, 0].astype(int)
    g = im[:, :1380, 1].astype(int)
    b = im[:, :1380, 2].astype(int)
    red = (r > 150) & (r - g > 70) & (r - b > 70)
    return np.where(red.sum(axis=1) > 8)[0]


def red_components(path: Path) -> list[dict]:
    """Saturated-red connected components, classified by shape.

    Plot area only (x < 1380 keeps the price axis text out).
    """
    im = np.asarray(Image.open(path).convert("RGB"))
    r = im[:, :1380, 0].astype(int)
    g = im[:, :1380, 1].astype(int)
    b = im[:, :1380, 2].astype(int)
    red = ((r > 150) & (r - g > 70) & (r - b > 70)).astype(np.uint8)
    num, _, stats, _ = cv2.connectedComponentsWithStats(red, connectivity=8)
    comps = []
    for i in range(1, num):
        x, y, w, h, area = (int(v) for v in stats[i])
        if area < 40:
            continue  # noise / glyph fragments
        if w <= 120:
            continue  # small blob or short text glyph run
        if h <= 10:
            kind = "horizontal_line"
        elif area / (w * h) >= 0.30:
            kind = "filled_box"
        elif w > 150 and h <= 60 and area / (w * h) < 0.30:
            kind = "outlined_band"
        elif h > 60:
            kind = "diagonal_line"
        else:
            kind = "small_mark"
        comps.append({"kind": kind, "x": x, "y": y, "w": w, "h": h, "area": area})
    return comps


def y_price(y: float, H: int, top: float, bot: float) -> float:
    return float(top + (bot - top) * (y / (H - 1)))


def component_zone(c: dict, H: int, top: float, bot: float) -> dict:
    if c["kind"] == "diagonal_line":
        return {"type": "diagonal_line",
                "price_top": round(y_price(c["y"], H, top, bot), 2),
                "price_bottom": round(y_price(c["y"] + c["h"], H, top, bot), 2)}
    hi = y_price(c["y"], H, top, bot)
    lo = y_price(c["y"] + c["h"], H, top, bot)
    return {"type": c["kind"], "price_low": round(lo, 2), "price_high": round(hi, 2)}


def zone_matches(zone: dict, sub: pd.DataFrame, price_col: str = "band") -> tuple:
    """Return (n_hits, detail) for ledger events vs the mark zone.

    Distance is computed PER EVENT (above-zone events measured from the
    zone top, below-zone events from the zone bottom) — never the naive
    min of two clipped sides.
    """
    if zone["type"] == "diagonal_line":
        zlo = min(zone["price_top"], zone["price_bottom"])
        zhi = max(zone["price_top"], zone["price_bottom"])
    else:
        zlo, zhi = zone["price_low"], zone["price_high"]
    if price_col == "band":
        sub = sub[sub["price_low"].notna() & sub["price_high"].notna()]
        if sub.empty:
            return None, "no priced rows in ledger for this class"
        lo, hi = sub["price_low"], sub["price_high"]
        hit = (lo <= zhi + 5) & (hi >= zlo - 5)
        n = int(hit.sum())
        if n:
            band = (float(sub.loc[hit, "price_low"].min()),
                    float(sub.loc[hit, "price_high"].max()))
            return n, f"bands {band[0]:.2f}–{band[1]:.2f}"
        dist = np.maximum(zlo - hi, lo - zhi).clip(lower=0)
        return 0, f"closest band {float(dist.min()):.1f} price units away (n={len(sub)})"
    px = sub[price_col].dropna()
    if px.empty:
        return None, "no priced rows"
    hits = px[(px >= zlo - 5) & (px <= zhi + 5)]
    return int(len(hits)), f"{len(px)} priced rows"


def best_verdict(verdicts: list[str]) -> str:
    order = ["YES", "PARTIAL", "NO", "DATA_GAP"]
    for v in order:
        if any(x.startswith(v) for x in verdicts):
            return v
    return "NO"


def main() -> int:
    led = pd.read_csv(LEDGER_CSV)
    led["kind"] = led["notes"].str.extract(r"kind=(\w+)")

    def class_df(cls: str) -> pd.DataFrame:
        if cls == "ob":
            return led[(led["event_type"] == "poi_raw") & (led["kind"] == "ob")]
        if cls == "demand_supply":
            return led[(led["event_type"] == "poi_raw") & (led["kind"] == "demand_supply")]
        if cls == "fvg":
            f1 = led[(led["event_type"] == "fvg")]
            f2 = led[(led["event_type"] == "poi_raw") & (led["kind"] == "fvg")]
            return pd.concat([f1, f2])
        return led[led["event_type"] == cls]

    CLASS_N = {c: len(class_df(c)) for c in
               ("sweep", "fvg", "ob", "demand_supply", "poi_armed", "route_ltf", "fill")}

    probe = {
        "directive": "expert chart system match probe — READ-ONLY, diagnostic",
        "ledger": {
            "path": "06_RESEARCH/results/structure_ledger_6m/events.csv",
            "event_class_counts": CLASS_N,
            "tf_note": ("ledger detection TFs: H4/H1/D1 only — M5/M1/W1 "
                        "charts probed on nearest TF, capped at PARTIAL"),
        },
        "time_recoverable": False,
        "time_note": ("no dates readable on any chart (only a bare clock "
                      "'170000' on chart 6) → TIME matching DATA_GAP by "
                      "design; price-zone matching only, nothing invented"),
        "charts": {},
    }

    for fname, probes in PROBES.items():
        top, bot = AXIS[fname]
        W, H = Image.open(CHART_DIR / fname).size
        comps = [c for c in red_components(CHART_DIR / fname)
                 if c["kind"] in ("horizontal_line", "filled_box",
                                  "outlined_band", "diagonal_line")]
        entry = {
            "operator_marking": MARKINGS[fname],
            "calibration": {"top_tick": top, "bottom_tick": bot,
                            "approximate": fname == "chart_4.jfif",
                            "tick_span_price": round(abs(top - bot), 2)},
            "marks": [],
            "verdicts": {},
        }
        if not comps:
            # Fallback: the operator marked with text/arrows only — use the
            # full red-annotation row span as ONE COARSE region. Honest:
            # this is where the operator's writing/clustering sits, not a
            # drawn zone boundary.
            rows = red_rows(CHART_DIR / fname)
            if len(rows) == 0:
                entry["verdicts"]["_"] = "DATA_GAP (no red annotation pixels)"
                probe["charts"][fname] = entry
                continue
            zhi = round(y_price(int(rows.min()), H, top, bot), 2)
            zlo = round(y_price(int(rows.max()), H, top, bot), 2)
            comps = [{"kind": "annotation_region_coarse", "x": 0, "y": int(rows.min()),
                      "w": 1380, "h": int(rows.max() - rows.min()), "area": 0}]
            zone = {"type": "annotation_region_coarse",
                    "price_low": zlo, "price_high": zhi,
                    "note": "coarse red-annotation span (text/arrow marks only — "
                            "no drawn zone geometry on this chart)"}
            mark = {"component": comps[0], "zone": zone, "class_verdicts": {}}
            for cls, op_tf in probes:
                sub = class_df(cls)
                if cls == "displacement":
                    mark["class_verdicts"][f"{cls} ({op_tf})"] = "DATA_GAP (class has no prices in ledger)"
                    continue
                if sub.empty:
                    mark["class_verdicts"][f"{cls} ({op_tf})"] = "DATA_GAP"
                    continue
                n, detail = zone_matches(zone, sub)
                cap_partial = op_tf not in ("H4", "H1", "D1")
                coarse_cap = True  # coarse region never claims YES
                if n is None:
                    verdict = "DATA_GAP"
                elif n > 0:
                    verdict = "PARTIAL"
                else:
                    verdict = "NO"
                mark["class_verdicts"][f"{cls} ({op_tf})"] = f"{verdict} ({detail}; n={n})"
            entry["marks"].append(mark)
            entry["verdicts"] = dict(mark["class_verdicts"])
            probe["charts"][fname] = entry
            continue
        for c in comps:
            zone = component_zone(c, H, top, bot)
            mark = {"component": c, "zone": zone, "class_verdicts": {}}
            for cls, op_tf in probes:
                sub = class_df(cls)
                if sub.empty:
                    mark["class_verdicts"][f"{cls} ({op_tf})"] = "DATA_GAP"
                    continue
                price_col = "band"
                if cls in ("route_ltf", "fill"):
                    price_col = "entry"
                n, detail = zone_matches(zone, sub, price_col)
                cap_partial = op_tf not in ("H4", "H1", "D1")
                if n is None:
                    verdict = "DATA_GAP"
                elif n > 0:
                    verdict = "PARTIAL" if cap_partial else "YES"
                else:
                    verdict = "NO"
                mark["class_verdicts"][f"{cls} ({op_tf})"] = f"{verdict} ({detail}; n={n})"
            entry["marks"].append(mark)
            for k, v in mark["class_verdicts"].items():
                prev = entry["verdicts"].get(k)
                if prev is None or best_verdict([v]) != "NO" and best_verdict([prev]) == "NO":
                    entry["verdicts"][k] = v
                elif best_verdict([v]) == "YES" and best_verdict([prev]) != "YES":
                    entry["verdicts"][k] = v
        probe["charts"][fname] = entry

    OUT_JSON.write_text(json.dumps(probe, indent=1), encoding="utf-8")
    for f, e in probe["charts"].items():
        print(f"== {f}: {len(e.get('marks', []))} marks")
        for k, v in e.get("verdicts", {}).items():
            print(f"   {k}: {v}")
    print("wrote", OUT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
