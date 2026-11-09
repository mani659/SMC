#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Plan-Complement Chart Pack — visual sample of the 5 menu-path plan submits.

Read-only renderer for Architect review of the plan-complement ledger rows.
No strategy logic, no thresholds, no TP/SL rules touched. LOGIC_CHANGED: NO.

For each ledger row (06_RESEARCH/results/plan_complement_ledger/
plan_complement_ledger.csv):
  * top panel    = detection-TF context (zone band, sweep, confirm, plan lines)
  * bottom panel = confirmation-TF context (same overlays)
  * caption      = poi_id, tier, det->conf, trigger, confirm label, tp_source,
                   entry_anchor, plan complete/consistent flags

Visual language follows generate_d1_poi_pack / ltf_confirmation_pack
(candle colors, footer disclaimer, 14x7 canvas family).

Diagnostic only — does NOT validate profitability or edge.
"""

from __future__ import annotations

import bisect
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "04_SRC"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from smc.config.timeframe import Timeframe  # noqa: E402
from smc.core.candle import Candle  # noqa: E402
from smc.data.resample import resample_ohlcv  # noqa: E402

LEDGER_CSV = ROOT / "06_RESEARCH" / "results" / "plan_complement_ledger" / "plan_complement_ledger.csv"
OUT_DIR = ROOT / "06_RESEARCH" / "results" / "plan_complement_charts"
NOTE_PATH = ROOT / "06_RESEARCH" / "PLAN_COMPLEMENT_CHART_PACK_NOTE.md"
DATA_PATH = ROOT / "07_DATA" / "XAUUSD_M1.parquet"

WARMUP_START = datetime(2023, 12, 1, tzinfo=timezone.utc)
DATA_END = datetime(2024, 5, 1, tzinfo=timezone.utc)

CANVAS_W_IN, CANVAS_H_IN, CANVAS_DPI = 14.0, 11.0, 120
CANDLE_UP = "#2e7d32"
CANDLE_DOWN = "#c62828"
EVENT_COLOR = "#1e88e5"      # zone band (D1-pack)
SWEEP_COLOR = "#ef6c00"      # sweep time
EVENT_BAR_COLOR = "#f9a825"
CONFIRM_COLOR = "#1e88e5"
ENTRY_COLOR = "#6a1b9a"
SL_COLOR = "#c62828"
TP_COLOR = "#00695c"
FOOTER = "sweep + confirm -> plan sample | diagnostic only - NOT a trade/edge claim"


def load_m1(path: Path, start: datetime, end: datetime) -> list[Candle]:
    start_naive = start.replace(tzinfo=None)
    end_naive = end.replace(tzinfo=None)
    cols = ["timestamp", "open", "high", "low", "close", "volume"]
    try:
        import pyarrow.parquet as pq

        table = pq.read_table(
            path, columns=cols,
            filters=[("timestamp", ">=", start_naive), ("timestamp", "<", end_naive)],
        )
        df = table.to_pandas()
    except Exception:
        df = pd.read_parquet(path, columns=cols)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df[(df["timestamp"] >= start) & (df["timestamp"] < end)]
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).sort_values()
    ts = df["timestamp"].dt.to_pydatetime()
    o = df["open"].astype(float).values
    h = df["high"].astype(float).values
    lo = df["low"].astype(float).values
    c = df["close"].astype(float).values
    v = df.get("volume", pd.Series(0, index=df.index)).fillna(0).astype(float).values
    return [
        Candle(
            timestamp=(t if getattr(t, "tzinfo", None) else t.replace(tzinfo=timezone.utc)),
            open=float(o[i]), high=float(h[i]), low=float(lo[i]), close=float(c[i]),
            volume=float(v[i]), timeframe=Timeframe.M1,
        )
        for i, t in enumerate(ts)
    ]


def _parse_ts(value):
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def _tf_by_name(name: str) -> Timeframe:
    for tf in Timeframe:
        if tf.name == name:
            return tf
    raise SystemExit(f"TF_GAP: unknown timeframe {name!r}")


def _window(series, anchor, half: int):
    stamps = [c.timestamp for c in series]
    center = bisect.bisect_left(stamps, anchor)
    center = min(max(center, 0), len(series) - 1)
    lo = max(center - half, 0)
    hi = min(center + half, len(series) - 1)
    return series[lo:hi + 1]


def _index_of(series, stamp):
    if stamp is None or not series:
        return None
    if stamp < series[0].timestamp or stamp > series[-1].timestamp:
        return None
    stamps = [c.timestamp for c in series]
    idx = bisect.bisect_left(stamps, stamp)
    return idx if 0 <= idx < len(series) else None


def _draw_candles(ax, window):
    for i, candle in enumerate(window):
        color = CANDLE_UP if candle.close >= candle.open else CANDLE_DOWN
        ax.plot([i, i], [candle.low, candle.high], color=color, lw=0.8, zorder=2)
        ax.add_patch(
            plt.Rectangle(
                (i - 0.34, min(candle.open, candle.close)), 0.68,
                abs(candle.close - candle.open) + 1e-9,
                facecolor=color, edgecolor=color, zorder=3,
            )
        )


def _draw_levels(ax, row):
    levels = [
        ("entry", row.get("entry_price"), ENTRY_COLOR, "-"),
        ("SL", row.get("sl_price"), SL_COLOR, "--"),
        ("TP", row.get("tp_price"), TP_COLOR, "--"),
    ]
    for label, value, color, style in levels:
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        ax.axhline(price, color=color, lw=1.2, ls=style, alpha=0.95,
                   label=f"{label} {price:.2f}", zorder=4)


def _panel(ax, *, series, anchor, half, zone_low, zone_high, row,
           sweep_ts, confirm_ts, title):
    window = _window(series, anchor, half)
    if not window:
        ax.text(0.5, 0.5, "window unavailable", ha="center", va="center",
                transform=ax.transAxes)
        ax.set_axis_off()
        return
    _draw_candles(ax, window)
    try:
        lo, hi = float(zone_low), float(zone_high)
        if hi > lo:
            ax.axhspan(lo, hi, color=EVENT_COLOR, alpha=0.16,
                       label="HTF zone", zorder=1)
        elif hi == lo:
            ax.axhline(lo, color=EVENT_COLOR, lw=1.4, label="HTF zone", zorder=1)
    except (TypeError, ValueError):
        pass

    for stamp, color, label, style in [
        (sweep_ts, SWEEP_COLOR, "sweep", "--"),
        (confirm_ts, CONFIRM_COLOR, "confirm", ":"),
    ]:
        idx = _index_of(window, stamp)
        if idx is not None:
            ax.axvline(idx, color=color, lw=1.4, ls=style, alpha=0.95,
                       label=label, zorder=4)

    _draw_levels(ax, row)

    step = max(len(window) // 8, 1)
    ax.set_xticks(range(0, len(window), step))
    ax.set_xticklabels(
        [window[i].timestamp.strftime("%Y-%m-%d %H:%M") for i in range(0, len(window), step)],
        fontsize=7, rotation=12, ha="right",
    )
    ax.set_xlim(-1, len(window))
    ax.set_ylabel("price", fontsize=8)
    ax.set_title(title, fontsize=10, loc="left")
    ax.grid(alpha=0.22)
    ax.legend(loc="upper left", fontsize=7, framealpha=0.9)


def render_row(row, series_by_tf, out_path: Path) -> None:
    det_tf = _tf_by_name(str(row["detection_tf"]))
    conf_tf = _tf_by_name(str(row["confirmation_tf"]))
    sweep_ts = _parse_ts(row.get("t_sweep"))
    confirm_ts = _parse_ts(row.get("t_confirm"))
    if sweep_ts is None:
        raise SystemExit(f"ROW_GAP: row {row['submit_index']} has no sweep timestamp")
    if confirm_ts is None:
        raise SystemExit(f"ROW_GAP: row {row['submit_index']} has no confirm timestamp")

    fig, (ax_det, ax_conf) = plt.subplots(
        2, 1, figsize=(CANVAS_W_IN, CANVAS_H_IN), dpi=CANVAS_DPI,
        gridspec_kw={"height_ratios": [1, 1], "hspace": 0.30},
    )
    _panel(
        ax_det, series=series_by_tf[det_tf], anchor=sweep_ts, half=35,
        zone_low=row.get("zone_low"), zone_high=row.get("zone_high"), row=row,
        sweep_ts=sweep_ts, confirm_ts=confirm_ts,
        title=f"Detection context — {det_tf.name} (window: sweep ±35 bars)",
    )
    _panel(
        ax_conf, series=series_by_tf[conf_tf], anchor=confirm_ts, half=60,
        zone_low=row.get("zone_low"), zone_high=row.get("zone_high"), row=row,
        sweep_ts=sweep_ts, confirm_ts=confirm_ts,
        title=f"Confirmation context — {conf_tf.name} (window: confirm ±60 bars)",
    )

    headline = (
        f"Plan #{row['submit_index']} — {row['tier']} tier | "
        f"{row['detection_tf']}→{row['confirmation_tf']} | {row['trigger_type']} | "
        f"{row['zone_direction']} | confirm label: {row['confirm_label']}"
    )
    caption_lines = [
        f"poi_id: {row['poi_id']}",
        f"tier: {row['tier']}   det->conf: {row['detection_tf']}->{row['confirmation_tf']}"
        f"   trigger: {row['trigger_type']}   confirm label: {row['confirm_label']}",
        f"zone: {'[' + str(row['zone_low']) + ', ' + str(row['zone_high']) + ']'}"
        f"   sweep: {row.get('t_sweep')}   confirm: {row.get('t_confirm')}",
        f"plan: entry={row.get('entry_price')}  sl={row.get('sl_price')}  tp={row.get('tp_price')}"
        f"   tp_source={row.get('tp_source')}   entry_anchor={row.get('entry_anchor')}",
        f"plan_complete={row.get('plan_complete')}   plan_consistent={row.get('plan_consistent')}"
        f"   place_or_queue={row.get('place_or_queue')}",
    ]
    fig.text(0.03, 0.975, headline, fontsize=11, fontweight="bold", color="#0d2b45",
             ha="left", va="top")
    fig.text(0.03, 0.945, "\n".join(caption_lines), fontsize=7.6, color="#444444",
             ha="left", va="top", linespacing=1.35)
    fig.text(0.985, 0.012, FOOTER, fontsize=8.2, style="italic", color="#8c1d18",
             ha="right", va="bottom")
    fig.subplots_adjust(left=0.055, right=0.985, top=0.845, bottom=0.075)
    fig.savefig(out_path, dpi=CANVAS_DPI)
    plt.close(fig)


def main() -> int:
    if not LEDGER_CSV.exists():
        raise SystemExit(f"LEDGER_GAP: missing {LEDGER_CSV} (run plan_complement_ledger.py)")
    if not DATA_PATH.exists():
        raise SystemExit(f"DATA_GAP: missing {DATA_PATH}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for stale in OUT_DIR.glob("*.png"):
        try:
            stale.unlink()
        except OSError:
            pass

    with LEDGER_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("LEDGER_GAP: ledger has no rows")
    print(f"rendering {len(rows)} plan rows from {LEDGER_CSV}", flush=True)

    m1 = load_m1(DATA_PATH, WARMUP_START, DATA_END)
    print(f"loaded M1 bars={len(m1)}", flush=True)
    needed = {_tf_by_name(r["detection_tf"]) for r in rows} | {
        _tf_by_name(r["confirmation_tf"]) for r in rows
    }
    series_by_tf = {}
    for tf in sorted(needed, key=lambda t: t.minutes, reverse=True):
        series_by_tf[tf] = resample_ohlcv(m1, tf)
        print(f"  resampled {tf.name}={len(series_by_tf[tf])}", flush=True)

    entries = []
    for row in rows:
        name = (
            f"plan_{int(row['submit_index']):02d}_"
            f"{row['detection_tf']}_{row['confirmation_tf']}_"
            f"{str(row['poi_id'])[:8]}.png"
        )
        out_path = OUT_DIR / name
        render_row(row, series_by_tf, out_path)
        print(f"  wrote {out_path.name}", flush=True)
        entries.append((row, out_path))

    note_rows = "\n".join(
        f"| {r['submit_index']} | `{p.name}` | {r['tier']} | {r['detection_tf']}→{r['confirmation_tf']} | "
        f"{r['trigger_type']} | {r['confirm_label']} | `{r['tp_source']}` | `{r['entry_anchor']}` | "
        f"{r['plan_complete']}/{r['plan_consistent']} |"
        for r, p in entries
    )
    note = f"""# Plan-Complement Chart Pack — 5 menu-path plan submits (visual sample only)

**Diagnostic only — does NOT validate profitability, edge, or that the flowchart is correct.**
Rendered read-only from `06_RESEARCH/results/plan_complement_ledger/plan_complement_ledger.csv`
(menu `queue_menu_candidate` submits only, window `2024-04-01..2024-05-01`, warmup `2023-12-01`,
`07_DATA/XAUUSD_M1.parquet`). `LOGIC_CHANGED=NO` for this pack. OPT-B false, OPT-2 off,
no pillar/R7/threshold/TP-rule edits; multi-TF tier policy unchanged.

## What each chart shows
- **Top panel** — detection-TF context (sweep ±35 bars): HTF zone band [low, high], sweep vline
  (orange dashed), confirm vline (blue dotted), plan entry/SL/TP lines.
- **Bottom panel** — confirmation-TF context (confirm ±60 bars): same overlays.
- **Caption** — poi_id, tier, det→conf, trigger, confirm label, `tp_source`, `entry_anchor`,
  `plan_complete` / `plan_consistent`, place_or_queue.
- Timestamps in captions are UTC; charts use the ledger's own recorded sweep/confirm stamps
  (nothing re-derived). Visual language follows `generate_d1_poi_pack` /
  `ltf_confirmation_pack` (candle colors, zone band, footer disclaimer).

## Charts (all {len(entries)} of {len(rows)})
| # | file | tier | det→conf | trigger | confirm label | tp_source | entry_anchor | complete/consistent |
|---:|---|---|---|---|---|---|---|---|
{note_rows}

Paths: `06_RESEARCH/results/plan_complement_charts/<file>` (gitignored results dir).
Generator: `06_RESEARCH/scripts/plan_complement_charts.py`.

## How to review (human)
For each chart ask only: *would this plan (entry / SL / TP geometry vs the zone, sweep and
confirm bars) match the flowchart's sweep → confirm → plan intent?* Answer CORRECT / PARTIAL /
WRONG in the chart score; geometry PASS from the ledger is **not** flowchart validation.

## Caveats
- Same 5-row sample as the plan-complement ledger; single one-month window; no expectancy, no
  PnL, no edge measurement here.

## Residual (Task C — `t_arm` stamp) — SKIPPED, not trivial
`t_arm` stays unstamped on the `product_menu` stamp. `ProductMenuEngine.register_armed(poi,
 detection_tf)` takes no clock/`as_of`, `MenuEpisode` records only the sweep time, and `POI.created_at`
 is a wall-clock construction default (meaningless in a replay). Doing this properly needs a
 signature change plus threading `as_of` through 9 call sites (2 in `smc/live/loop.py`, 6 tests,
 1 research script) — not a logging-only one-liner. Parked as residual; no behaviour change made.
"""
    NOTE_PATH.write_text(note, encoding="utf-8")
    print(json.dumps({
        "CHARTS_N": len(entries),
        "OUT_DIR": str(OUT_DIR),
        "NOTE_PATH": str(NOTE_PATH),
        "LOGIC_CHANGED": "NO",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
