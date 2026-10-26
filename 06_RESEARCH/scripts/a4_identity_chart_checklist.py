#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A4 identity chart checklist (read-only / research UX).

Lead Architect directive (after ARMING_FORENSICS_BUCKET_A_NOTE.md):
produce a human review pack to score A4 overlap candidates as
SAME_FOOTPRINT | REFINEMENT_ONLY | DIFFERENT | UNCLEAR. No strategy
changes. Humans score; the script never auto-scores.

Frozen selection (stated before running):
  * Primary: ALL A4-contained rows (41 — strongest candidates).
  * Plus top-15 A4-partial rows by earliest first_sweep_ts.
  * Note examples are verified to sit inside those sets already
    (all 5 fall in the earliest-sweep partials); union logic keeps
    them regardless (deterministic, no duplicates).
Panels reuse the house chart language (M5 candles + zone bands +
event vlines + plain title + footer); no new strategy deps (imports
canvas constants + candle colors only). One panel per episode:
census episode zone (blue) vs matched armed zone (orange), sweep bar
(red solid) + arm bar (purple dashed, when inside the window).

Outputs: results/a4_identity_chart_checklist/{charts/*.png,
index.csv, summary.json}. Note: A4_IDENTITY_CHART_CHECKLIST_NOTE.md
(separate step: rubric + how to fill + NEXT).
LOGIC_CHANGED: NO (04_SRC untouched — constants import only).
"""

from __future__ import annotations

import bisect
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
SCRIPTS_DIR = REPO_ROOT / "06_RESEARCH" / "scripts"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

import matplotlib
matplotlib.use("Agg")

from smc.config.timeframe import Timeframe
from smc.data.parquet_loader import load_ohlcv_parquet
from smc.data.resample import resample_multi

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "a4_identity_chart_checklist"
CHARTS_DIR = OUT_DIR / "charts"
INDEX_CSV = OUT_DIR / "index.csv"
SUMMARY_JSON = OUT_DIR / "summary.json"

BANNER = "DIAGNOSTIC — identity review, NOT edge"
FOOTER = "A4 identity review — NOT a trade claim"

FORENSICS_CSV = (REPO_ROOT / "06_RESEARCH" / "results" /
                 "arming_forensics_bucket_a" / "forensics.csv")
LOAD_FROM = datetime(2025, 5, 1, tzinfo=timezone.utc)
HALF_BARS = 90
N_PARTIAL = 15

INDEX_COLUMNS = [
    "episode_id", "chart_file", "tf", "kind_tag", "direction",
    "zone_low", "zone_high",
    "matched_armed_low", "matched_armed_high", "match_kind",
    "first_seen_date", "first_sweep_ts", "armed_match_ts",
    "human_verdict", "notes",
]


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #
def select_checklist(rows: list[dict], n_partial: int = N_PARTIAL,
                     ) -> list[dict]:
    """Frozen selection: all contained + earliest-N partials (deduped).

    Note examples are covered by construction (verified at runtime);
    the union keeps them regardless. Output sorted by
    (first_sweep_ts, episode_id) — deterministic review order.
    """
    contained = sorted([r for r in rows if r.get("match_kind") == "contained"],
                       key=lambda r: (r.get("first_sweep_ts") or "",
                                      r["episode_id"]))
    partials = sorted([r for r in rows if r.get("match_kind") == "partial"],
                      key=lambda r: (r.get("first_sweep_ts") or "",
                                     r["episode_id"]))
    picked: list[dict] = []
    seen: set[str] = set()
    for r in list(contained) + partials[:n_partial]:
        if r["episode_id"] not in seen:
            picked.append(r)
            seen.add(r["episode_id"])
    picked.sort(key=lambda r: (r.get("first_sweep_ts") or "",
                               r["episode_id"]))
    return picked


def panel_window(n_bars: int, center: int, half: int = HALF_BARS
                 ) -> tuple[int, int, int]:
    """Clamped [start, end) window + center offset (house convention)."""
    start = max(center - half, 0)
    end = min(center + half, n_bars)
    return start, end, center - start


# --------------------------------------------------------------------------- #
# Panel (house chart language, constants only)
# --------------------------------------------------------------------------- #
def render_identity_panel(out_path: Path, *, m5, sweep_ts: str,
                          arm_ts: str, episode: dict) -> bool:
    """One M5 panel: episode zone (blue) vs armed zone (orange)."""
    from generate_d1_poi_pack import (CANVAS_W_IN, CANVAS_H_IN, CANVAS_DPI,
                                      CANDLE_UP, CANDLE_DOWN)
    import matplotlib.pyplot as plt

    stamps = [c.timestamp for c in m5]
    try:
        sweep_dt = datetime.fromisoformat(sweep_ts)
        zlo, zhi = float(episode["zone_low"]), float(episode["zone_high"])
        alo, ahi = float(episode["matched_armed_low"]), float(
            episode["matched_armed_high"])
    except (ValueError, TypeError):
        return False
    center = bisect.bisect_left(stamps, sweep_dt)
    if center >= len(m5):
        return False
    start, end, offset = panel_window(len(m5), center)
    window = m5[start:end]
    if not window:
        return False
    fig, ax = plt.subplots(figsize=(CANVAS_W_IN, CANVAS_H_IN),
                            dpi=CANVAS_DPI)
    for i, candle in enumerate(window):
        color = CANDLE_UP if candle.close >= candle.open else CANDLE_DOWN
        ax.plot([i, i], [candle.low, candle.high], color=color, lw=0.9)
        ax.add_patch(plt.Rectangle(
            (i - 0.35, min(candle.open, candle.close)), 0.7,
            abs(candle.close - candle.open) + 1e-9,
            facecolor=color, edgecolor=color))
    ax.axhspan(zlo, zhi, color="#1e88e5", alpha=0.20,
               label="census episode zone")
    ax.axhline(zlo, color="#1e88e5", ls="-", lw=1.0, alpha=0.7)
    ax.axhline(zhi, color="#1e88e5", ls="-", lw=1.0, alpha=0.7)
    ax.axhspan(alo, ahi, color="#ef6c00", alpha=0.20,
               label="matched armed zone")
    ax.axhline(alo, color="#ef6c00", ls="--", lw=1.2, alpha=0.9)
    ax.axhline(ahi, color="#ef6c00", ls="--", lw=1.2, alpha=0.9)
    ax.axvline(offset, color="#c62828", lw=2.0, label="first sweep bar")
    arm_plotted = False
    if arm_ts:
        try:
            arm_dt = datetime.fromisoformat(arm_ts)
            aidx = bisect.bisect_left(stamps, arm_dt)
            if start <= aidx < end:
                ax.axvline(aidx - start, color="#6a1b9a", lw=1.4,
                           ls="--", label="matched arm bar")
                arm_plotted = True
        except (ValueError, TypeError):
            pass
    step = max(len(window) // 8, 1)
    ax.set_xticks(range(0, len(window), step))
    ax.set_xticklabels(
        [window[i].timestamp.strftime("%Y-%m-%d %H:%M")
         for i in range(0, len(window), step)], fontsize=7)
    ax.legend(loc="upper left", fontsize=7)
    ax.grid(alpha=0.25)
    title = (f"A4 {episode['match_kind']} | {episode['episode_id'][:22]} | "
             f"{episode['direction']} | {episode['tf']}")
    fig.text(0.06, 0.955, title, fontsize=11.5, fontweight="bold",
             color="#0d2b45", ha="left", va="top")
    caption = (f"episode [{zlo:.3f}, {zhi:.3f}] vs armed [{alo:.3f}, "
               f"{ahi:.3f}]  |  sweep: "
               f"{sweep_dt.strftime('%Y-%m-%d %H:%M')} UTC"
               f"  |  arm: {(arm_ts[:16].replace('T', ' ') if arm_ts else 'n/a')}"
               f"{'' if arm_plotted else ' (outside window)'}"
               f"  |  kind: {episode.get('kind_tag', '')}")
    fig.text(0.06, 0.917, caption, fontsize=8, color="#555555",
             ha="left", va="top")
    fig.text(0.98, 0.02, FOOTER, fontsize=8.5, style="italic",
             color="#8c1d18", ha="right", va="bottom")
    fig.subplots_adjust(left=0.06, right=0.98, top=0.855, bottom=0.14)
    fig.savefig(out_path, dpi=CANVAS_DPI)
    plt.close(fig)
    return True


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    for stale in CHARTS_DIR.glob("*.png"):
        try:
            stale.unlink()
        except OSError:
            pass
    if not FORENSICS_CSV.exists():
        raise SystemExit(f"forensics rows missing: {FORENSICS_CSV}")
    with open(FORENSICS_CSV, encoding="utf-8", newline="") as f:
        a4 = [r for r in csv.DictReader(f) if r.get("reason") == "A4"]
    picked = select_checklist(a4)
    n_contained = sum(1 for r in picked if r["match_kind"] == "contained")
    n_partial = sum(1 for r in picked if r["match_kind"] == "partial")
    print(f"[a4check] A4 rows={len(a4)} picked={len(picked)} "
          f"(contained={n_contained} partial={n_partial})", flush=True)

    parquet = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    if not parquet.exists():
        raise SystemExit(f"canonical dataset missing: {parquet}")
    m1_all = load_ohlcv_parquet(str(parquet), Timeframe.M1)
    m1 = [c for c in m1_all if c.timestamp >= LOAD_FROM]
    m5 = resample_multi(m1, [Timeframe.M5])[Timeframe.M5]
    print(f"[a4check] M5={len(m5)}", flush=True)

    index_rows: list[dict] = []
    rendered, skipped = 0, []
    for seq, r in enumerate(picked, start=1):
        name = (f"{seq:03d}_a4_{r['match_kind']}_"
                f"{r['episode_id'][:24]}.png")
        ok = render_identity_panel(
            CHARTS_DIR / name, m5=m5, sweep_ts=r.get("first_sweep_ts") or "",
            arm_ts=r.get("armed_match_ts") or "", episode=r)
        if ok:
            rendered += 1
        else:
            skipped.append(r["episode_id"])
        index_rows.append({
            "episode_id": r["episode_id"], "chart_file": name if ok else "",
            "tf": r.get("tf"), "kind_tag": r.get("kind_tag"),
            "direction": r.get("direction"),
            "zone_low": r.get("zone_low"), "zone_high": r.get("zone_high"),
            "matched_armed_low": r.get("matched_armed_low"),
            "matched_armed_high": r.get("matched_armed_high"),
            "match_kind": r.get("match_kind"),
            "first_seen_date": r.get("first_seen_date"),
            "first_sweep_ts": r.get("first_sweep_ts"),
            "armed_match_ts": r.get("armed_match_ts"),
            "human_verdict": "", "notes": "",
        })
    with open(INDEX_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=INDEX_COLUMNS)
        writer.writeheader()
        for r in index_rows:
            writer.writerow(r)

    summary = {
        "banner": BANNER,
        "selection": ("all A4-contained + earliest-15 A4-partials by "
                      "first_sweep_ts (note examples verified inside); "
                      "deterministic (sweep ts, episode id) order"),
        "n_a4_total": len(a4),
        "n_charts": rendered,
        "contained_n": n_contained,
        "partial_n": n_partial,
        "skipped_unrenderable": skipped,
        "window_rule": (f"center = first M5 bar at/after sweep ts; "
                        f"half = {HALF_BARS} M5 bars clamped; arm vline "
                        "only when inside"),
        "verdict_values": ["SAME_FOOTPRINT", "REFINEMENT_ONLY",
                           "DIFFERENT", "UNCLEAR"],
        "limitations": [
            "M5 candles show context around HTF zones; zone edges are "
            "exact; sweep/arm bars marked when inside the window.",
            "No auto-scoring anywhere (humans only).",
            "No gate, no threshold, no live rule follows (see note).",
        ],
    }
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[a4check] rendered={rendered}/{len(picked)} "
          f"skipped={skipped}", flush=True)
    print(f"[a4check] wrote {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
