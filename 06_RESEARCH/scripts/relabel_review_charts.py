#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Re-render the structure-ledger review charts with PLAIN FLOWCHART LABELS.

PRESENTATION ONLY - read-only over every frozen ledger artifact. This script
does not run the detection pipeline, does not touch ``events.csv`` /
``events.jsonl`` / ``summary.json``, and does not modify ``04_SRC/`` strategy
code, locked constants, pillars, triggers, zone bands or any threshold.

What it changes vs ``structure_identification_ledger.render_review_pack``:

* the chart title becomes the plain flowchart tag
  (``LIQUIDITY SWEEP | H1 | 2025-06-01 22:00 UTC | LONG``,
  ``ORDER BLOCK (M8 HTF) | H4 | ...``,
  ``LTF CONFIRMATION (M5 ENTRY, TRIGGER F) | ...``) instead of engine
  vocabulary;
* the raw ``event_type`` / ``detect_tf`` / tags / ``event_id`` trace is
  demoted to one small "technical row:" footnote line;
* the function paths disappear from the chart entirely (they stay in the PDF
  caption's technical record, which is the audit trail);
* ``route_ltf`` and ``fill`` charts get the mandatory SETUP CHAIN block
  (HTF structure -> LTF confirmation -> entry / original SL, plus the
  "this is the entry step, not the HTF sweep" line);
* the identification-only disclaimer is kept on every chart.

The candle/level/zone/event-bar/entry/SL pixels and the legend labels are
byte-for-byte the same drawing code, so the PDF legend table stays accurate.

Where the labels come from: ``flowchart_labels.py`` (shared with the PDF
builder, so chart and PDF wording cannot drift). A label is emitted only when
the ledger row supports it; an unlabelled POI stays "unlabeled POI".

Output: ``<results>/review_sample_v2/`` with the SAME file names as
``review_sample/`` (so the frozen ``summary.json`` index and REVIEW_INDEX.md
still name each chart), the ORIGINAL PNGs are left untouched, and
``review_sample_v2/relabel_manifest.json`` records the run.

Usage:
  python 06_RESEARCH/scripts/relabel_review_charts.py
  python 06_RESEARCH/scripts/relabel_review_charts.py --out-dir <dir> --force
"""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
SCRIPTS_DIR = SCRIPT_PATH.parent
REPO_ROOT = SCRIPT_PATH.parents[2]
sys.path.insert(0, str(SCRIPTS_DIR))

import flowchart_labels as FL                                   # noqa: E402

LEDGER_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "structure_ledger_6m"
SUMMARY_JSON = LEDGER_DIR / "summary.json"
EVENTS_CSV = LEDGER_DIR / "events.csv"
OUT_DIR = LEDGER_DIR / "review_sample_v2"
MANIFEST = OUT_DIR / "relabel_manifest.json"

#: Identical to render_review_pack: how many bars of context each chart shows.
HALF_WINDOW = {"M5": 60, "H1": 40, "H4": 30, "D1": 25}

CANVAS_W_IN, CANVAS_H_IN, CANVAS_DPI = 14.0, 7.0, 130     # -> 1820 x 910 px

CANDLE_UP = "#2e7d32"
CANDLE_DOWN = "#c62828"
EVENT_COLOR = "#1e88e5"
EVENT_BAR_COLOR = "#f9a825"
ENTRY_COLOR = "#6a1b9a"
SL_COLOR = "#c62828"

HEADLINE_COLOR = "#0d2b45"
TECHNICAL_COLOR = "#4a4a4a"
DISCLAIMER_COLOR = "#8c1d18"
BLOCK_FACE = "#f2f6fa"
BLOCK_EDGE = "#c3ced9"

DISCLAIMER = "structure identification - NOT a trade claim"

BLOCK_FONT = 7.8
BLOCK_LINESPACING = 1.42


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_inputs() -> tuple[dict, dict, list]:
    if not SUMMARY_JSON.is_file():
        raise SystemExit(f"FATAL: required input missing: {SUMMARY_JSON}")
    if not EVENTS_CSV.is_file():
        raise SystemExit(f"FATAL: required input missing: {EVENTS_CSV}")
    summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    sample = summary.get("review_sample")
    if not isinstance(sample, list) or not sample:
        raise SystemExit("FATAL: summary.json has no usable 'review_sample' array")
    with EVENTS_CSV.open("r", newline="", encoding="utf-8") as handle:
        events = {row["event_id"]: row for row in csv.DictReader(handle) if row.get("event_id")}
    if not events:
        raise SystemExit("FATAL: events.csv parsed to zero rows")
    return summary, events, sample


NUMERIC_FIELDS = ("price_low", "price_high", "entry", "original_sl", "disp_magnitude_atr")


def coerce_numeric(row: dict) -> dict:
    """events.csv stores prices as text; the renderer needs floats to draw.

    Blank stays blank (never 0.0) so an absent field cannot become a line at
    the bottom of the chart.
    """
    out = dict(row)
    for field in NUMERIC_FIELDS:
        value = out.get(field)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                out[field] = ""
                continue
            try:
                out[field] = float(text)
            except ValueError:
                out[field] = text
    return out


def chart_window(series: list, anchor, half: int) -> tuple[list, int]:
    """Same even split as render_review_pack: `half` bars either side of anchor."""
    stamps = [candle.timestamp for candle in series]
    if anchor is not None:
        center = max(bisect.bisect_left(stamps, anchor), 0)
    else:
        center = len(series) - 1
    lo = max(center - half, 0)
    hi = min(center + half, len(series) - 1)
    return series[lo:hi + 1], center - lo


def render_chart(row: dict, chart_tf: str, detection_tf: str, window: list,
                 center_offset: int, headline: str, technical: str,
                 block_lines: list[str]):
    """Draw one review chart. Pixels identical to the original renderer;
    only the text surface changed (plain tag headline + demoted technical
    footnote + plain block/chain band + disclaimer)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    lines = block_lines or ["No plain-language detail is derivable from this row."]
    block_h = (len(lines) * BLOCK_FONT * BLOCK_LINESPACING) / (CANVAS_H_IN * 72.0)
    bottom = min(max(0.055 + block_h + 0.055, 0.18), 0.40)

    fig, ax = plt.subplots(figsize=(CANVAS_W_IN, CANVAS_H_IN), dpi=CANVAS_DPI)

    # ---- identical candle drawing ---------------------------------------- #
    for i, candle in enumerate(window):
        color = CANDLE_UP if candle.close >= candle.open else CANDLE_DOWN
        ax.plot([i, i], [candle.low, candle.high], color=color, lw=0.7)
        ax.add_patch(plt.Rectangle(
            (i - 0.3, min(candle.open, candle.close)), 0.6,
            abs(candle.close - candle.open) + 1e-9,
            facecolor=color, edgecolor=color))

    # ---- identical level / zone / event bar / entry / SL drawing --------- #
    low = row.get("price_low")
    high = row.get("price_high")
    has_bounds = isinstance(low, (int, float)) and isinstance(high, (int, float))
    if has_bounds:
        if abs(float(high) - float(low)) < 1e-9:
            ax.axhline(float(low), color=EVENT_COLOR, ls="-", lw=1.4,
                       label="event level")
            ax.axvline(center_offset, color=EVENT_BAR_COLOR, lw=1.2,
                       label="event bar")
        else:
            ax.axhspan(float(low), float(high), color=EVENT_COLOR,
                       alpha=0.18, label="event zone")
            ax.axvline(center_offset, color=EVENT_BAR_COLOR, lw=1.2,
                       label="event bar")
    for key, color, label in (("entry", ENTRY_COLOR, "entry (limit)"),
                              ("original_sl", SL_COLOR, "original SL")):
        value = row.get(key)
        if isinstance(value, (int, float)):
            ax.axhline(float(value), color=color, ls="--", lw=1.2, label=label)

    step = max(len(window) // 8, 1)
    ax.set_xticks(range(0, len(window), step))
    ax.set_xticklabels(
        [window[i].timestamp.strftime("%m-%d %H:%M")
         for i in range(0, len(window), step)], fontsize=7)
    ax.legend(loc="best", fontsize=8)
    ax.grid(alpha=0.25)
    fig.subplots_adjust(left=0.05, right=0.985, top=0.895, bottom=bottom)

    # ---- plain-language text surface ------------------------------------- #
    fig.text(0.05, 0.99, headline, ha="left", va="top", fontsize=12.5,
             fontweight="bold", color=HEADLINE_COLOR)
    fig.text(0.05, 0.945, technical, ha="left", va="top", fontsize=7.0,
             color=TECHNICAL_COLOR)
    fig.text(0.05, max(bottom - 0.045, 0.06), "\n".join(lines), ha="left",
             va="top", fontsize=BLOCK_FONT, linespacing=BLOCK_LINESPACING,
             color="#1a1a1a",
             bbox=dict(boxstyle="round,pad=0.45", facecolor=BLOCK_FACE,
                       edgecolor=BLOCK_EDGE, linewidth=0.7))
    fig.text(0.985, 0.012, DISCLAIMER, ha="right", va="bottom", fontsize=8.0,
             style="italic", color=DISCLAIMER_COLOR)
    return fig


def write_gallery(manifest: dict) -> int:
    """Self-contained HTML gallery of the relabelled charts (base64, no siblings).

    Same reason as the ledger's own gallery: the preview server serves only the
    registered HTML file, so relative PNG srcs would 404.
    """
    import base64
    import html as _html

    groups: dict = {}
    for record in manifest["charts"]:
        groups.setdefault(record["plain_tag"], []).append(record)

    parts = [
        "<!doctype html><meta charset=utf-8>",
        "<title>Structure ledger review charts - plain flowchart labels</title>",
        "<body style='background:#111;color:#ddd;font:12px/1.45 sans-serif;margin:16px'>",
        "<h2>Structure Identification Ledger &mdash; review charts, plain flowchart labels</h2>",
        "<p>%d charts &middot; window 2025-06-01 &rarr; 2025-11-30 &middot; "
        "HTF structure on its detect timeframe, LTF confirmation on M5. "
        "Labels read from the ledger row only (unlabelled POIs stay “unlabeled POI”). "
        "Identification only &mdash; not a trade claim.</p>" % manifest["charts_rendered"],
        "<p style='color:#9ab'>%s</p>" % _html.escape(manifest["label_version"]),
    ]
    embedded = 0
    for tag in sorted(groups):
        rows = groups[tag]
        parts.append("<h3>%s (%d)</h3>" % (_html.escape(tag), len(rows)))
        parts.append("<div style='display:flex;flex-wrap:wrap;gap:14px'>")
        for record in rows:
            png = OUT_DIR / record["file"]
            if not png.is_file():
                continue
            data = base64.b64encode(png.read_bytes()).decode("ascii")
            embedded += 1
            parts.append(
                "<figure><img loading='lazy' src='data:image/png;base64,%s'>"
                "<figcaption>%s<br><code>%s</code> &middot; %s</figcaption></figure>"
                % (data, _html.escape(record["headline"]),
                   _html.escape(record["event_id"]), _html.escape(record["block_kind"])))
        parts.append("</div>")
    parts.append("<style>figure{margin:0;max-width:47%}img{width:100%;border:1px solid #444}"
                 "figcaption{padding:3px 0}code{color:#8ab}</style></body>")
    gallery = OUT_DIR / "review_gallery_v2.html"
    gallery.write_text("".join(parts), encoding="utf-8")
    return embedded


def build() -> dict:
    import time
    t0 = time.perf_counter()
    summary, events, sample = load_inputs()
    window = summary.get("window") or {}
    union_start = window.get("start")
    union_end = window.get("end")
    if not union_start or not union_end:
        raise SystemExit("FATAL: summary.json window has no start/end")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("[relabel] loading chart series (M5/H1/H4/D1) ...", flush=True)
    import structure_identification_ledger as SIL
    series_by_tf = SIL._load_chart_series(
        datetime.fromisoformat(union_start), datetime.fromisoformat(union_end))

    records: list[dict] = []
    skipped: list[dict] = []
    for seq, entry in enumerate(sample, start=1):
        event_id = str(entry.get("event_id") or "")
        event_type = str(entry.get("event_type") or "")
        detect_tf = str(entry.get("detection_tf") or SIL.EXEC_TF_NAME)
        chart_tf = SIL.EXEC_TF_NAME if event_type in FL.M5_EVENT_TYPES else detect_tf
        series = series_by_tf.get(chart_tf) or series_by_tf.get(SIL.EXEC_TF_NAME) or []
        if len(series) < 5:
            skipped.append({"seq": seq, "file": entry.get("file"),
                            "reason": "chart series too short (%s)" % chart_tf})
            continue
        row = events.get(event_id)
        if row is None:
            skipped.append({"seq": seq, "file": entry.get("file"),
                            "reason": "no events.csv row for %s" % event_id})
            continue
        # chart rows come from summary.json (ts_utc/direction/model_tags);
        # the notes/priced fields come from events.csv. They must agree.
        merged = coerce_numeric(row)
        merged["ts_utc"] = e_ts = (entry.get("ts_utc") or row.get("ts_utc") or "")
        for key in ("direction", "model_tags"):
            if entry.get(key):
                merged[key] = entry[key]
        try:
            anchor = datetime.fromisoformat(str(e_ts))
        except (TypeError, ValueError):
            anchor = None
        window_rows, center_offset = chart_window(
            series, anchor, HALF_WINDOW.get(chart_tf, 40))
        if not window_rows:
            skipped.append({"seq": seq, "file": entry.get("file"),
                            "reason": "empty chart window on %s" % chart_tf})
            continue

        caption = FL.caption_lines(event_type, merged, events,
                                    event_id=event_id, chart_tf=chart_tf,
                                    detection_tf=detect_tf)
        block_lines = caption["chain"] or caption["detail"]

        fig = render_chart(merged, chart_tf, detect_tf, window_rows,
                           center_offset, caption["headline"], caption["technical"],
                           block_lines)
        out_name = str(entry.get("file") or f"{seq:03d}_{event_type}.png")
        out_path = OUT_DIR / out_name
        fig.savefig(out_path, dpi=CANVAS_DPI)
        import matplotlib.pyplot as plt
        plt.close(fig)

        records.append({
            "seq": seq,
            "file": out_name,
            "path": str(out_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "event_id": event_id,
            "code_event_type": event_type,
            "plain_tag": caption["tag"],
            "stage": caption["stage"],
            "headline": caption["headline"],
            "chart_tf": chart_tf,
            "detection_tf": detect_tf,
            "block_kind": "setup_chain" if caption["chain"] else "detail",
            "block_lines": len(block_lines),
            "bytes": out_path.stat().st_size,
        })
        if seq % 10 == 0:
            print(f"[relabel] {seq}/{len(sample)} charts", flush=True)

    from PIL import Image as PILImage
    sizes = {}
    for record in records:
        with PILImage.open(OUT_DIR / record["file"]) as image:
            sizes["%dx%d" % image.size] = sizes.get("%dx%d" % image.size, 0) + 1

    manifest = {
        "generated_utc": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"),
        "label_version": FL.LABEL_VERSION,
        "purpose": ("Plain-flowchart relabelling of the review charts. Presentation only; "
                    "detection logic, thresholds and locked constants untouched."),
        "logic_changed": "NO",
        "renderer": "06_RESEARCH/scripts/relabel_review_charts.py",
        "labels_module": "06_RESEARCH/scripts/flowchart_labels.py",
        "sources": {
            "summary_json": str(SUMMARY_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            "events_csv": str(EVENTS_CSV.relative_to(REPO_ROOT)).replace("\\", "/"),
            "events_csv_sha256": sha256_file(EVENTS_CSV),
        },
        "canvas": {"inches": "%gx%g" % (CANVAS_W_IN, CANVAS_H_IN), "dpi": CANVAS_DPI,
                   "pixel_sizes": sizes},
        "output_dir": str(OUT_DIR.relative_to(REPO_ROOT)).replace("\\", "/"),
        "original_dir_untouched": str((LEDGER_DIR / "review_sample").relative_to(REPO_ROOT)).replace("\\", "/"),
        "same_file_names_as_original": True,
        "charts_rendered": len(records),
        "charts_skipped": skipped,
        "chain_charts": [r["file"] for r in records if r["block_kind"] == "setup_chain"],
        "runtime_seconds": round(time.perf_counter() - t0, 1),
        "charts": records,
    }
    manifest["gallery"] = str((OUT_DIR / "review_gallery_v2.html").relative_to(REPO_ROOT)).replace("\\", "/")
    manifest["gallery_charts_embedded"] = write_gallery(manifest)
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=None,
                        help="override the output directory (default review_sample_v2/)")
    parser.add_argument("--force", action="store_true",
                        help="accepted for symmetry; the pack is always rewritten in full")
    args = parser.parse_args()
    global OUT_DIR, MANIFEST
    if args.out_dir:
        OUT_DIR = Path(args.out_dir)
        if not OUT_DIR.is_absolute():
            OUT_DIR = REPO_ROOT / OUT_DIR
        MANIFEST = OUT_DIR / "relabel_manifest.json"

    print("=" * 78)
    print("structure ledger review charts -> plain flowchart labels (presentation only)")
    print("=" * 78)
    try:
        manifest = build()
    except SystemExit as exc:
        print(str(exc))
        return 2
    except Exception as exc:                                     # noqa: BLE001
        print(f"FATAL: relabel failed: {exc}")
        traceback.print_exc()
        return 3

    print("-" * 78)
    print(f"charts rendered: {manifest['charts_rendered']} (skipped "
          f"{len(manifest['charts_skipped'])})")
    print(f"gallery: {manifest['gallery']} ({manifest['gallery_charts_embedded']} embedded)")
    print(f"pixel sizes: {manifest['canvas']['pixel_sizes']}")
    print(f"setup-chain charts: {len(manifest['chain_charts'])}")
    print(f"output dir: {manifest['output_dir']}")
    print(f"events.csv sha256: {manifest['sources']['events_csv_sha256']}")
    print(f"runtime: {manifest['runtime_seconds']}s")
    print("-" * 78)
    print(f"HUMAN_LABELS_STATUS: {'PASS' if not manifest['charts_skipped'] else 'FAIL'}")
    print(f"PLAIN_TAGS_ON_CHARTS: {'YES' if manifest['charts_rendered'] else 'NO'}")
    print(f"LTF_CHAIN_CAPTIONS: {'YES' if manifest['chain_charts'] else 'NO'}")
    print(f"CHARTS_DIR: {manifest['output_dir']}")
    print("LOGIC_CHANGED: NO")
    return 0 if not manifest["charts_skipped"] else 4


if __name__ == "__main__":
    sys.exit(main())
