"""Expert setup review pack — charts + PDF + report (directive 2026-10-06).

RESEARCH / EXPORT ONLY: renders the backfilled setup identification ledger
into a human-reviewable pack. No trading threshold or strategy logic
changes; no expectancy claims — identification quality review, NOT PnL.

Sampling rule (documented, deterministic):
    ALL 3 routed setups (mandatory) + stratified non-routed sample by
    detection TF: up to 4 D1, up to 6 H4, up to 3 H1 — ordered by arm bar
    (earliest first), spread across the window. Total ≤ 16 charts.

Chart language reuses the frozen house style
(``generate_d1_poi_pack.render_d1_chart``): candlesticks, zone band, event
bar, identity caption block. Routed charts additionally carry entry / SL /
TP levels and the exit mark (trade row), plus hypothesis_outcome and
tp_source labels. Honest labels when geometry is missing.

Outputs (under 06_RESEARCH/results/setup_identification_ledger/):
    charts/setup_NN_<poi_id>.png
    EXPERT_SETUP_REVIEW_PACK.pdf   (charts + ledger table + rubric)
    summary.json                   (pack block appended)

Usage:
    python 06_RESEARCH/scripts/setup_ledger_expert_pack.py \
        [--data 07_DATA/XAUUSD_M1.parquet]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import matplotlib                                                    # noqa: E402
matplotlib.use("Agg")                                                # noqa: E402
import matplotlib.pyplot as plt                                      # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages                 # noqa: E402

from smc.config.timeframe import Timeframe                           # noqa: E402
from smc.data.parquet_loader import load_ohlcv_parquet               # noqa: E402
from smc.data.resample import resample_ohlcv                         # noqa: E402

LEDGER_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "setup_identification_ledger"
CHARTS_DIR = LEDGER_DIR / "charts"
DATA_DEFAULT = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"

CANVAS_W_IN, CANVAS_H_IN, CANVAS_DPI = 14.0, 7.0, 130
CANDLE_UP = "#2e7d32"
CANDLE_DOWN = "#c62828"
ZONE_COLOR = "#1e88e5"
EVENT_BAR_COLOR = "#f9a825"
ENTRY_COLOR = "#6a1b9a"
SL_COLOR = "#c62828"
TP_COLOR = "#2e7d32"
DISCLAIMER = "structure identification — NOT a trade or edge claim"

#: Stratified sample caps by detection TF (non-routed rows).
SAMPLE_CAPS = {"D1": 4, "H4": 6, "H1": 3}


def _load_series(data_path: Path, window: dict) -> dict:
    """Per-TF candle series covering the frozen window (+ arm context)."""
    m1 = load_ohlcv_parquet(str(data_path))
    start = datetime.fromisoformat(window["start"])
    end = datetime.fromisoformat(window["end"])
    sliced = [c for c in m1 if start <= c.timestamp <= end]
    out = {}
    for name, tf in (("M5", Timeframe.M5), ("H1", Timeframe.H1),
                     ("H4", Timeframe.H4), ("D1", Timeframe.D1)):
        out[name] = resample_ohlcv(sliced, tf)
    return out


def _candles(ax, window, width=0.35):
    for i, candle in enumerate(window):
        color = CANDLE_UP if candle.close >= candle.open else CANDLE_DOWN
        ax.plot([i, i], [candle.low, candle.high], color=color, lw=0.9)
        ax.add_patch(plt.Rectangle(
            (i - width, min(candle.open, candle.close)), width * 2,
            abs(candle.close - candle.open) + 1e-9,
            facecolor=color, edgecolor=color))


def _window_around(series, anchor_iso: str, half: int):
    stamps = [c.timestamp for c in series]
    try:
        anchor = datetime.fromisoformat(anchor_iso)
    except (TypeError, ValueError):
        anchor = series[-1].timestamp
    center = max(__import__("bisect").bisect_left(stamps, anchor), 0)
    lo = max(center - half, 0)
    hi = min(center + half, len(series) - 1)
    return series[lo:hi + 1], center - lo


def render_chart(row: dict, series: dict, chart_tf: str, out_path: Path) -> None:
    """One setup chart: detection-TF candles, zone, identity, plan levels."""
    half = {"D1": 25, "H4": 40, "H1": 60, "M5": 150}[chart_tf]
    tf_series = series[chart_tf if chart_tf != "M5" else "M5"]
    window, center = _window_around(tf_series, row.get("arm_ts_utc", ""), half)

    direction = (row.get("direction") or "").upper() or "DATA_GAP"
    routed = row.get("routed") == "YES"
    title = (f"SETUP {row['setup_index']} | {row['poi_id']} | "
             f"{row['detection_tf']} | {direction} | "
             f"{'ROUTED ' + row.get('trigger', '') if routed else 'NOT ROUTED'}")

    fig, ax = plt.subplots(figsize=(CANVAS_W_IN, CANVAS_H_IN), dpi=CANVAS_DPI)
    _candles(ax, window)

    has_zone = row.get("zone_low") and row.get("zone_high")
    if has_zone:
        zl, zh = float(row["zone_low"]), float(row["zone_high"])
        if abs(zh - zl) < 1e-9:
            ax.axhline(zl, color=ZONE_COLOR, ls="-", lw=1.5, label="zone")
        else:
            ax.axhspan(zl, zh, color=ZONE_COLOR, alpha=0.18, label="zone")
    ax.axvline(center, color=EVENT_BAR_COLOR, lw=1.6, label="arm bar")

    if routed and has_zone:
        for key, color, label in (("entry", ENTRY_COLOR, "entry"),
                                  ("original_sl", SL_COLOR, "SL"),
                                  ("tp", TP_COLOR, "TP")):
            if row.get(key):
                ax.axhline(float(row[key]), color=color, ls="--", lw=1.3,
                           label=f"{label} {float(row[key]):.2f}")
        if row.get("exit_at"):
            try:
                exit_ts = datetime.fromisoformat(row["exit_at"].replace(" ", "T"))
                stamps = [c.timestamp for c in window]
                exit_idx = min(
                    (abs((ts - exit_ts).total_seconds()), i)
                    for i, ts in enumerate(stamps))[1]
                ax.axvline(exit_idx, color="#37474f", lw=1.4, ls=":",
                           label="exit bar")
            except (ValueError, TypeError):
                pass

    step = max(len(window) // 8, 1)
    ax.set_xticks(range(0, len(window), step))
    ax.set_xticklabels(
        [window[i].timestamp.strftime("%m-%d %H:%M") if chart_tf != "D1"
         else window[i].timestamp.strftime("%Y-%m-%d")
         for i in range(0, len(window), step)], fontsize=8)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.25)

    caption = [
        f"poi_id: {row['poi_id']}  |  kind: {row.get('kind') or 'n/a'}  |  "
        f"direction: {direction} ({row.get('direction_source', 'n/a')})  |  "
        f"posture: {row.get('posture', 'UNKNOWN')}",
        f"zone: [{row.get('zone_low', 'n/a')}, {row.get('zone_high', 'n/a')}]  |  "
        f"armed: {row.get('arm_ts_utc', 'n/a')[:16].replace('T', ' ')} UTC  |  "
        f"pillar_path: {row.get('pillar_path') or 'n/a'}",
        f"disp: {row.get('disp_magnitude_atr') or 'n/a'} xATR  |  "
        f"chart_tf: {chart_tf} (detection_tf: {row['detection_tf']})",
    ]
    if routed:
        caption.append(
            f"plan: entry {row.get('entry') or 'n/a'}  SL {row.get('original_sl') or 'n/a'}  "
            f"TP {row.get('tp') or 'n/a'} ({row.get('tp_source') or 'n/a'})  |  "
            f"trigger {row.get('trigger') or 'n/a'}  |  close {row.get('close_kind') or 'n/a'}  |  "
            f"hyp: {row.get('hypothesis_outcome') or 'n/a'}")
    else:
        caption.append("plan: none (not routed) — identification only")
    caption_text = "\n".join(caption)

    fig.subplots_adjust(left=0.05, right=0.98, top=0.9, bottom=0.16)
    fig.text(0.05, 0.965, title, fontsize=12, fontweight="bold",
             color="#0d2b45", ha="left", va="top")
    fig.text(0.05, 0.075, caption_text, fontsize=8.5, linespacing=1.4,
             color="#1a1a1a", ha="left", va="bottom",
             bbox=dict(boxstyle="round,pad=0.5", facecolor="#f2f6fa",
                       edgecolor="#c3ced9", linewidth=0.8))
    fig.text(0.98, 0.02, DISCLAIMER, fontsize=8.5, style="italic",
             color="#8c1d18", ha="right", va="bottom")
    fig.savefig(out_path, dpi=CANVAS_DPI)
    plt.close(fig)


def pick_sample(rows: list[dict]) -> list[dict]:
    """All routed + stratified non-routed caps (documented, deterministic)."""
    routed = [r for r in rows if r["routed"] == "YES"]
    chosen = list(routed)
    chosen_ids = {r["poi_id"] for r in chosen}
    for tf, cap in SAMPLE_CAPS.items():
        pool = [r for r in rows
                if r["detection_tf"] == tf and r["poi_id"] not in chosen_ids]
        pool.sort(key=lambda r: int(r["armed_bar"]))
        # Spread across the window: take evenly spaced indices.
        if len(pool) > cap:
            step = len(pool) / cap
            picked = [pool[min(int(i * step), len(pool) - 1)] for i in range(cap)]
        else:
            picked = pool
        for row in picked:
            if row["poi_id"] not in chosen_ids:
                chosen.append(row)
                chosen_ids.add(row["poi_id"])
    return chosen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Expert setup review pack")
    parser.add_argument("--data", default=str(DATA_DEFAULT))
    args = parser.parse_args(argv)

    csv_path = LEDGER_DIR / "setups.csv"
    summary_path = LEDGER_DIR / "summary.json"
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    print("loading series …")
    series = _load_series(Path(args.data), summary["window"])

    sample = pick_sample(rows)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    chart_files: list[tuple[dict, Path, str]] = []
    for row in sample:
        chart_tf = {"D1": "D1", "H4": "H4", "H1": "H1"}.get(
            row["detection_tf"], "H4")
        out = CHARTS_DIR / f"setup_{int(row['setup_index']):02d}_{row['poi_id']}.png"
        render_chart(row, series, chart_tf, out)
        chart_files.append((row, out, chart_tf))
        print(f"  chart: {out.name} ({chart_tf})")

    # -------- PDF pack -------- #
    pdf_path = LEDGER_DIR / "EXPERT_SETUP_REVIEW_PACK.pdf"
    with PdfPages(pdf_path) as pdf:
        # Cover page.
        fig = plt.figure(figsize=(8.27, 11.69))          # A4 portrait
        fig.text(0.08, 0.93, "SETUP IDENTIFICATION — EXPERT REVIEW PACK",
                 fontsize=17, fontweight="bold", color="#0d2b45")
        fig.text(0.08, 0.885,
                 f"Window {summary['window']['start'][:10]} .. "
                 f"{summary['window']['end'][:10]} (exec M5)  |  "
                 f"{summary['setups_n']} armed setups  |  pack sample: "
                 f"{len(sample)} charts", fontsize=11)
        rubric = (
            "SCORING RUBRIC (identification quality — NOT PnL / edge)\n"
            "\n"
            "verdict:\n"
            "  CORRECT  — zone and direction match the structure a human\n"
            "             would mark; setup is the kind the system intends.\n"
            "  PARTIAL  — zone or direction partially right (e.g. right\n"
            "             level, wrong side; or zone too wide/narrow).\n"
            "  WRONG    — not a valid POI (noise, wrong level, wrong side).\n"
            "  UNCLEAR  — chart/geometry insufficient to judge.\n"
            "\n"
            "timing (relative to the structure it claims):\n"
            "  EARLY / ON_TIME / LATE / N_A\n"
            "\n"
            "Fill the verdict/timing/notes columns in setups.csv.\n"
            "Human judgement ONLY — the pipeline never pre-fills these."
        )
        fig.text(0.08, 0.84, rubric, fontsize=10, family="monospace",
                 va="top", linespacing=1.45,
                 bbox=dict(boxstyle="round,pad=0.6", facecolor="#f2f6fa",
                           edgecolor="#c3ced9"))
        stats = summary.get("backfill", {})
        fig.text(0.08, 0.30,
                 f"Backfill: direction {stats.get('direction_filled_n', 0)}/"
                 f"{summary['setups_n']} "
                 f"({stats.get('direction_sources', {})}) — the remainder is "
                 f"DATA_GAP (source artifacts lack the zone geometry).\n"
                 f"Posture: UNKNOWN for all rows (not present in any "
                 f"artifact; never inferred from price).\n"
                 f"arm_ts: exec-bar map, validated {stats.get('arm_ts_validation', 'n/a')}.",
                 fontsize=9, va="top", color="#37474f")
        fig.text(0.08, 0.12, DISCLAIMER, fontsize=9, style="italic",
                 color="#8c1d18")
        pdf.savefig(fig)
        plt.close(fig)

        # Ledger table page (compact).
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.text(0.06, 0.95, "LEDGER — ALL ARMED SETUPS (identity only)",
                 fontsize=13, fontweight="bold", color="#0d2b45")
        cols = ("setup_index", "poi_id", "detection_tf", "direction",
                "zone_low", "zone_high", "armed_bar", "routed", "trigger",
                "direction_source")
        y = 0.90
        header = "  ".join(f"{c[:9]:>9}" for c in cols)
        fig.text(0.03, y, header, fontsize=6.6, family="monospace")
        y -= 0.018
        for row in rows:
            line = "  ".join(
                f"{str(row.get(c, ''))[:9]:>9}" for c in cols)
            fig.text(0.03, y, line, fontsize=6.4, family="monospace")
            y -= 0.0122
            if y < 0.04:
                break
        pdf.savefig(fig)
        plt.close(fig)

        # Chart pages (3 per page, scaled to A4 slots via dedicated axes).
        for i in range(0, len(chart_files), 3):
            fig = plt.figure(figsize=(8.27, 11.69))
            fig.text(0.06, 0.96, "SETUP CHARTS", fontsize=13,
                     fontweight="bold", color="#0d2b45")
            slots = (0.62, 0.34, 0.06)                 # axes y for 3 rows
            for j, (row, png, chart_tf) in enumerate(chart_files[i:i + 3]):
                y = slots[j]
                fig.text(0.06, y + 0.275,
                         f"setup {row['setup_index']} — {row['poi_id']} "
                         f"({row['detection_tf']}, {row.get('direction') or 'DATA_GAP'})",
                         fontsize=9, fontweight="bold")
                try:
                    img = plt.imread(png)
                    ax_img = fig.add_axes([0.06, y, 0.88, 0.26])
                    ax_img.imshow(img, aspect="auto")
                    ax_img.axis("off")
                except (OSError, ValueError):
                    fig.text(0.06, y + 0.10,
                             f"[chart unreadable: {png.name}]",
                             fontsize=9, color="#8c1d18")
            pdf.savefig(fig)
            plt.close(fig)
    print(f"  pdf: {pdf_path}")

    # -------- summary pack block -------- #
    summary["pack"] = {
        "sample_n": len(sample),
        "charts": [p.name for _r, p, _tf in chart_files],
        "sampling_rule": ("all routed (3) + stratified non-routed: "
                          f"D1≤{SAMPLE_CAPS['D1']}, H4≤{SAMPLE_CAPS['H4']}, "
                          f"H1≤{SAMPLE_CAPS['H1']} evenly spaced by arm bar"),
        "routed_in_pack": sum(1 for r in sample if r["routed"] == "YES"),
        "pdf": pdf_path.name,
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"  outputs: {csv_path}")
    print(f"           {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
