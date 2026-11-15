"""PFE-3 — EXPERT VALIDATION PACK (structure + confirmation + entry).

Reads the **already-frozen** PFE-2 artifacts and renders a human-scorable
chart pack in flowchart language. It runs no strategy, changes nothing, and
prints no expectancy language anywhere.

Selection is PRE-REGISTERED here and applied mechanically (no cherry-picking
after scoring):

* **Menu fills — ALL of them** (every fill in the three PFE-2 menu windows,
  Jun/Sep/Oct 1–10 2025). Using all avoids any post-hoc choice.
* **Menu winners that did not fill** — none exist in this pack (`placed ==
  fills` in every window); the section is reported as zero, never padded.
* **Armed menu POIs with zero winner** — up to 10, taken by even stride over
  each window's `armed_records.json` and spread across windows (the count is
  capped to the windows with the fewest arms so no window dominates).
* **Seek fills** — up to 10, even stride over the six-month book, labelled
  CONTINUITY ONLY (not the default live product path).

Charts: M5 candles around the event, the POI zone band labelled with its
detection timeframe and model tags, entry / original SL / TP lines, entry and
exit markers, plus the menu sweep/confirm marks when the trade carries a
product-menu stamp. The caption block holds identities and outcomes only.

Outputs (results tree is gitignored; PDF + markdown are for sharing):
  06_RESEARCH/results/pfe3_expert_pack/events.csv
  06_RESEARCH/results/pfe3_expert_pack/summary.json
  06_RESEARCH/results/pfe3_expert_pack/charts/*.png
  06_RESEARCH/results/pfe3_expert_pack/EXPERT_REVIEW_PACK.pdf
  06_RESEARCH/PFE3_EXPERT_VALIDATION_PACK.md
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

OUT_ROOT = REPO_ROOT / "06_RESEARCH" / "results" / "pfe3_expert_pack"
PFE2 = REPO_ROOT / "06_RESEARCH" / "results" / "pfe2_6m"
MD_PATH = REPO_ROOT / "06_RESEARCH" / "PFE3_EXPERT_VALIDATION_PACK.md"

MENU_WINDOWS = {
    "menu_jun01_10": ("2025-06-01", "2025-06-10"),
    "menu_sep01_10": ("2025-09-01", "2025-09-10"),
    "menu_oct01_10": ("2025-10-01", "2025-10-10"),
}
SEEK_DIR = PFE2 / "seek" / "run1"
SEEK_MAX = 10
ARMED_MAX_PER_WINDOW = 10
HALF_WINDOW_BARS = 90


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
def _menu_run(window: str) -> Path:
    return PFE2 / f"menu_short_{window.split('_')[1][:3]}" / "run1"


def _window_dir(tag: str) -> Path:
    mapping = {"menu_jun01_10": "menu_short_jun", "menu_sep01_10": "menu_short_sep",
               "menu_oct01_10": "menu_short_oct"}
    return PFE2 / mapping[tag] / "run1"


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(value)
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


_M5_CACHE: dict[tuple[str, str], list] = {}


def _m5_bars(exec_from: str, exec_to: str) -> list:
    key = (exec_from, exec_to)
    if key in _M5_CACHE:
        return _M5_CACHE[key]
    from smc.config.timeframe import Timeframe
    from smc.data.parquet_loader import load_ohlcv_parquet
    from smc.data.resample import resample_multi

    lo = datetime.fromisoformat(exec_from).replace(tzinfo=timezone.utc)
    hi = datetime.fromisoformat(exec_to).replace(tzinfo=timezone.utc)
    load_from = lo - timedelta(days=30)
    bars = [c for c in load_ohlcv_parquet(REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet")
            if load_from <= c.timestamp <= hi + timedelta(days=2)]
    multi = resample_multi(bars, [Timeframe.M5])
    out = [c for c in multi[Timeframe.M5] if lo <= c.timestamp <= hi]
    _M5_CACHE[key] = out
    return out


def _menu_stamp(trade: dict) -> dict:
    raw = trade.get("signal_data_json") or ""
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except ValueError:
        return {}
    stamp = payload.get("product_menu") if isinstance(payload, dict) else None
    return stamp if isinstance(stamp, dict) else {}


# --------------------------------------------------------------------------- #
# Event construction
# --------------------------------------------------------------------------- #
def menu_fill_events() -> list[dict]:
    events: list[dict] = []
    for tag, (lo, hi) in MENU_WINDOWS.items():
        d = _window_dir(tag)
        for trade in _read_csv(d / "trades.csv"):
            stamp = _menu_stamp(trade)
            events.append({
                "event_id": f"{tag}:fill:{trade['ticket']}",
                "kind": "menu_fill",
                "composition": "menu",
                "window": f"{lo}..{hi}",
                "exec_from": lo, "exec_to": hi,
                "poi_id": trade.get("poi_id", ""),
                "detection_tf": stamp.get("detection_tf", ""),
                "tier": stamp.get("tier", ""),
                "confirmation_tf": stamp.get("confirmation_tf", ""),
                "model_tags": trade.get("model_tags", ""),
                "pillar_path": trade.get("pillar_path", ""),
                "direction": trade.get("direction", ""),
                "zone_low": trade.get("zone_low", ""),
                "zone_high": trade.get("zone_high", ""),
                "trigger": trade.get("trigger", ""),
                "entry": trade.get("entry_price", ""),
                "original_sl": trade.get("original_sl", ""),
                "tp": trade.get("tp", ""),
                "tp_source": trade.get("tp_source", ""),
                "close_kind": trade.get("close_kind", ""),
                "entry_at": trade.get("entry_at", ""),
                "exit_at": trade.get("exit_at", ""),
                "sweep_ts": stamp.get("sweep_ts", ""),
                "completion_ts": stamp.get("completion_ts", ""),
                "chart": "",
                "expert_score": "",
                "expert_note": "",
            })
    events.sort(key=lambda e: (e["entry_at"], e["poi_id"]))
    return events


def menu_negative_events() -> list[dict]:
    """Armed menu POIs that never produced a winner, even stride per window."""
    events: list[dict] = []
    for tag, (lo, hi) in MENU_WINDOWS.items():
        d = _window_dir(tag)
        armed_path = d / "armed_records.json"
        if not armed_path.exists():
            continue
        armed = list(json.loads(armed_path.read_text(encoding="utf-8")).values())
        idle = [r for r in armed if str(r.get("routed", "")) != "true"]
        idle.sort(key=lambda r: int(r["armed_bar"]))
        if not idle:
            continue
        stride = max(1, len(idle) // ARMED_MAX_PER_WINDOW)
        picked = idle[::stride][:ARMED_MAX_PER_WINDOW]
        m5 = _m5_bars(lo, hi)
        for rec in picked:
            bar_index = int(rec["armed_bar"])
            ts = m5[bar_index].timestamp if bar_index < len(m5) else None
            events.append({
                "event_id": f"{tag}:no_winner:{rec['poi_id']}",
                "kind": "menu_no_winner",
                "composition": "menu",
                "window": f"{lo}..{hi}",
                "exec_from": lo, "exec_to": hi,
                "poi_id": rec["poi_id"],
                "detection_tf": rec.get("detection_tf", ""),
                "tier": "", "confirmation_tf": "",
                "model_tags": rec.get("model_tags", ""),
                "pillar_path": rec.get("pillar_path", ""),
                "direction": "",
                "zone_low": rec.get("zone_low", ""),
                "zone_high": rec.get("zone_high", ""),
                "trigger": "", "entry": "", "original_sl": "", "tp": "",
                "tp_source": "", "close_kind": "",
                "entry_at": ts.isoformat() if ts else "",
                "exit_at": "",
                "sweep_ts": "", "completion_ts": "",
                "chart": "", "expert_score": "", "expert_note": "",
                "anchor": "armed",
            })
    return events


def seek_events() -> list[dict]:
    rows = _read_csv(SEEK_DIR / "trades.csv")
    rows.sort(key=lambda r: r.get("entry_at", ""))
    if not rows:
        return []
    stride = max(1, len(rows) // SEEK_MAX)
    picked = rows[::stride][:SEEK_MAX]
    out = []
    for trade in picked:
        out.append({
            "event_id": f"seek6m:fill:{trade['ticket']}",
            "kind": "seek_fill",
            "composition": "seek",
            "window": "2025-05-01..2025-10-31",
            "exec_from": "2025-05-01", "exec_to": "2025-10-31",
            "poi_id": trade.get("poi_id", ""),
            "detection_tf": "", "tier": "", "confirmation_tf": "",
            "model_tags": trade.get("model_tags", ""),
            "pillar_path": trade.get("pillar_path", ""),
            "direction": trade.get("direction", ""),
            "zone_low": trade.get("zone_low", ""),
            "zone_high": trade.get("zone_high", ""),
            "trigger": trade.get("trigger", ""),
            "entry": trade.get("entry_price", ""),
            "original_sl": trade.get("original_sl", ""),
            "tp": trade.get("tp", ""),
            "tp_source": trade.get("tp_source", ""),
            "close_kind": trade.get("close_kind", ""),
            "entry_at": trade.get("entry_at", ""),
            "exit_at": trade.get("exit_at", ""),
            "sweep_ts": "", "completion_ts": "",
            "chart": "", "expert_score": "", "expert_note": "",
        })
    return out


# --------------------------------------------------------------------------- #
# Chart rendering
# --------------------------------------------------------------------------- #
def _f(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _px(value) -> str:
    """Price for the caption: two decimals, or a dash when honestly absent."""
    price = _f(value)
    return f"{price:.2f}" if price is not None else "—"


def render_chart(event: dict, out_png: Path) -> bool:
    entry_at = _parse_ts(event.get("entry_at", ""))
    if entry_at is None:
        return False
    bars = _m5_bars(event["exec_from"], event["exec_to"])
    stamps = [b.timestamp for b in bars]
    idx = None
    for i, ts in enumerate(stamps):
        if ts >= entry_at:
            idx = i
            break
    if idx is None:
        return False
    sweep_ts = _parse_ts(event.get("sweep_ts", ""))
    exit_at_ts = _parse_ts(event.get("exit_at", ""))
    lo = max(0, idx - HALF_WINDOW_BARS)
    if sweep_ts is not None:
        idx_sweep = next((i for i, ts in enumerate(stamps) if ts >= sweep_ts), None)
        if idx_sweep is not None and idx_sweep < lo:
            lo = max(0, idx_sweep - 10)      # show the sweep that armed the window
    hi = min(len(bars), idx + HALF_WINDOW_BARS)
    if exit_at_ts is not None:
        idx_exit = next((i for i, ts in enumerate(stamps) if ts >= exit_at_ts), None)
        if idx_exit is not None and idx_exit + 10 > hi:
            hi = min(len(bars), idx_exit + 10)
    window = bars[lo:hi]
    if not window:
        return False

    fig = plt.figure(figsize=(11.0, 8.5))
    ax = fig.add_axes([0.06, 0.30, 0.90, 0.64])
    xs = [mdates.date2num(b.timestamp) for b in window]
    width = (xs[1] - xs[0]) * 0.6 if len(xs) > 1 else 0.002

    for x, bar in zip(xs, window):
        colour = "#2e7d32" if bar.close >= bar.open else "#c62828"
        ax.vlines(x, bar.low, bar.high, color=colour, linewidth=0.7)
        body_lo = min(bar.open, bar.close)
        height = abs(bar.close - bar.open) or 0.01
        ax.add_patch(Rectangle((x - width / 2, body_lo), width, height,
                               facecolor=colour, edgecolor=colour, alpha=0.85))

    zlo, zhi = _f(event.get("zone_low")), _f(event.get("zone_high"))
    tf_label = event.get("detection_tf") or ""
    if zlo is not None and zhi is not None and zhi > zlo:
        tags = event.get("model_tags") or ""
        label = f"POI ZONE {tf_label}".strip()
        if tags:
            label += f"  [{tags}]"
        ax.axhspan(zlo, zhi, color="#1565c0", alpha=0.14, zorder=0)
        ax.hlines([zlo, zhi], xs[0], xs[-1], color="#1565c0", linewidth=0.8,
                  linestyle="--", alpha=0.7)
        ax.text(xs[0], zhi, " " + label, va="bottom", ha="left",
                fontsize=8, color="#0d47a1")

    colours = {"entry": "#000000", "sl": "#c62828", "tp": "#00695c"}
    for key, value, text in (
        ("entry", _f(event.get("entry")), "ENTRY"),
        ("sl", _f(event.get("original_sl")), "SL"),
        ("tp", _f(event.get("tp")), "TP"),
    ):
        if value is not None:
            ax.axhline(value, color=colours[key], linewidth=1.1,
                       linestyle="-" if key == "entry" else "--")
            ax.text(xs[-1], value, f" {text} {value:.2f}", va="center",
                    ha="left", fontsize=8, color=colours[key])

    completion_ts = _parse_ts(event.get("completion_ts", ""))
    if sweep_ts is not None:
        ax.axvline(mdates.date2num(sweep_ts), color="#ef6c00", linewidth=1.0,
                   linestyle=":")
        ax.text(mdates.date2num(sweep_ts), window[0].low, " sweep", rotation=90,
                va="bottom", ha="right", fontsize=7, color="#ef6c00")
    if completion_ts is not None:
        ax.axvline(mdates.date2num(completion_ts), color="#6a1b9a",
                   linewidth=1.0, linestyle=":")
        ax.text(mdates.date2num(completion_ts), window[0].low, " confirm",
                rotation=90, va="bottom", ha="right", fontsize=7, color="#6a1b9a")

    exit_at = _parse_ts(event.get("exit_at", ""))
    if exit_at is not None and xs[0] <= mdates.date2num(exit_at) <= xs[-1]:
        ax.axvline(mdates.date2num(exit_at), color="#37474f", linewidth=1.0,
                   linestyle="--", alpha=0.8)
        ax.text(mdates.date2num(exit_at), window[-1].high, " exit",
                rotation=90, va="top", ha="left", fontsize=7, color="#37474f")

    # Right padding so the level labels sit inside the canvas (never clipped).
    pad = (xs[-1] - xs[0]) * 0.13 if len(xs) > 1 else 0.004
    ax.set_xlim(xs[0], xs[-1] + pad)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.set_ylabel("XAUUSD  (M5)")
    ax.grid(alpha=0.2, linewidth=0.4)
    ax.set_title(f"{event['kind'].replace('_', ' ').upper()}  ·  "
                 f"{event['event_id']}", fontsize=10, loc="left")

    lines = [
        f"composition={event['composition']}   window={event['window']}   "
        f"tier={event.get('tier') or '—'}   detection_tf={event.get('detection_tf') or '—'}   "
        f"confirm_tf={event.get('confirmation_tf') or '—'}   poi={event['poi_id']}",
        f"direction={event.get('direction') or '—'}   model_tags={event.get('model_tags') or '—'}   "
        f"pillar_path={event.get('pillar_path') or '—'}",
        f"trigger={event.get('trigger') or '—'}   tp_source={event.get('tp_source') or '—'}   "
        f"close_kind={event.get('close_kind') or '—'}   entry={_px(event.get('entry'))}   "
        f"SL={_px(event.get('original_sl'))}   TP={_px(event.get('tp'))}",
        f"entry_at={event.get('entry_at') or '—'}   exit_at={event.get('exit_at') or '—'}   "
        f"sweep_ts={event.get('sweep_ts') or '—'}   confirm_ts={event.get('completion_ts') or '—'}",
        "",
        "EXPERT RATING (circle one):   CORRECT   /   PARTIAL   /   WRONG   /   UNCLEAR",
        "NOTE: ______________________________________________________________________",
        "",
        "No performance wording appears on this chart by design. Diagnostic sample only.",
    ]
    fig.text(0.06, 0.26, "\n".join(lines), ha="left", va="top", fontsize=7.6,
             family="monospace")

    fig.savefig(out_png, dpi=130)
    plt.close(fig)
    return True


# --------------------------------------------------------------------------- #
# Pack assembly
# --------------------------------------------------------------------------- #
def _cover_page(pdf: PdfPages, counts: dict) -> None:
    fig = plt.figure(figsize=(11, 8.5))
    body = [
        "PFE-3 — EXPERT VALIDATION PACK",
        "Structure · Confirmation · Entry  (flowchart language)",
        "",
        "Program: Product Fidelity & Evidence (PFE) — step 3",
        "Date: 2026-11-15        LOGIC_CHANGED: NO",
        "",
        f"Menu fills charted:        {counts['menu_fill']}",
        f"Menu armed, no winner:     {counts['menu_no_winner']}",
        f"Menu winners not filled:   {counts['menu_no_fill_winner']}",
        f"Seek fills (continuity):   {counts['seek_fill']}",
        "",
        "WHAT THIS IS",
        "A reading pack, not a result. Every chart is one event from the frozen",
        "PFE-2 evidence: the product menu law (primary) and the seek composition",
        "(continuity only, never the default live path). Score each event as",
        "CORRECT / PARTIAL / WRONG / UNCLEAR — you are scoring structure, the",
        "sweep/confirmation read, and the entry, not the outcome.",
        "",
        "HOW EACH PAGE READS",
        "Blue band   = the POI zone, labelled with its detection timeframe and model tags",
        "Black line  = entry          Red dashed = original SL        Teal dashed = TP",
        "Orange dot  = sweep instant   Purple dot = confirmation instant",
        "Grey dash   = exit",
        "",
        "SELECTION (pre-registered, mechanical, no post-hoc choice)",
        "· every menu fill in the three PFE-2 windows (Jun/Sep/Oct 1–10 2025)",
        "· up to 10 idle armed menu POIs per window, even stride",
        "· up to 10 seek fills, even stride over the six-month book",
        "No event was added or removed after any score was given.",
        "",
        "NOT CLAIMED ANYWHERE: edge, expectancy, profitability, optimisation.",
    ]
    fig.text(0.07, 0.93, body[0], fontsize=18, weight="bold", va="top")
    fig.text(0.07, 0.885, body[1], fontsize=11, va="top")
    fig.text(0.07, 0.82, "\n".join(body[2:]), fontsize=9.5, va="top", linespacing=1.55)
    pdf.savefig(fig)
    plt.close(fig)


def _section_page(pdf: PdfPages, title: str, lines: list[str]) -> None:
    fig = plt.figure(figsize=(11, 8.5))
    fig.text(0.07, 0.92, title, fontsize=15, weight="bold", va="top")
    fig.text(0.07, 0.84, "\n".join(lines), fontsize=9.5, va="top", linespacing=1.6)
    pdf.savefig(fig)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="PFE-3 expert validation pack")
    ap.add_argument("--out-root", type=Path, default=OUT_ROOT)
    args = ap.parse_args(argv)
    out = args.out_root
    (out / "charts").mkdir(parents=True, exist_ok=True)

    menu_events = menu_fill_events()
    neg_events = menu_negative_events()
    seek_ev = seek_events()
    events = menu_events + neg_events + seek_ev

    rendered = 0
    for event in events:
        slug = (event["event_id"].replace(":", "_").replace(".", "")
                .replace("/", "-"))
        png = out / "charts" / f"{slug}.png"
        if render_chart(event, png):
            event["chart"] = str(png.relative_to(REPO_ROOT)).replace("\\", "/")
            rendered += 1

    fields = ["event_id", "kind", "composition", "window", "detection_tf", "tier",
              "confirmation_tf", "model_tags", "pillar_path", "direction",
              "zone_low", "zone_high", "trigger", "entry", "original_sl", "tp",
              "tp_source", "close_kind", "entry_at", "exit_at", "sweep_ts",
              "completion_ts", "chart", "expert_score", "expert_note"]
    with (out / "events.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for event in events:
            writer.writerow({k: event.get(k, "") for k in fields})

    counts = {
        "menu_fill": sum(1 for e in events if e["kind"] == "menu_fill"),
        "menu_no_winner": sum(1 for e in events if e["kind"] == "menu_no_winner"),
        "menu_no_fill_winner": 0,
        "seek_fill": sum(1 for e in events if e["kind"] == "seek_fill"),
        "charted": rendered,
    }
    summary = {
        "program": "PFE-3",
        "logic_changed": "NO",
        "generated_from": "06_RESEARCH/results/pfe2_6m (PFE-2 artifacts, unchanged)",
        "selection": {
            "menu_fills": "all fills in the three PFE-2 menu windows",
            "menu_no_fill_winners": "none exist (placed == fills in every window)",
            "menu_armed_no_winner": f"up to {ARMED_MAX_PER_WINDOW} per window, even stride",
            "seek_fills": f"up to {SEEK_MAX}, even stride over the 6-month book",
        },
        "counts": counts,
        "menu_tp_source": {
            "structural_swing": sum(1 for e in events
                                    if e["kind"] == "menu_fill"
                                    and e["tp_source"] == "structural_swing"),
            "atr_fallback": sum(1 for e in events
                                if e["kind"] == "menu_fill"
                                and e["tp_source"] == "atr_fallback"),
        },
        "rubric": ["CORRECT", "PARTIAL", "WRONG", "UNCLEAR"],
        "banner": "DIAGNOSTIC / REVIEW PACK — NOT PERFORMANCE",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    pdf_path = out / "EXPERT_REVIEW_PACK.pdf"
    with PdfPages(pdf_path) as pdf:
        _cover_page(pdf, counts)
        _section_page(pdf, "HOW TO SCORE", [
            "One event per page. Score structure, not outcome.",
            "",
            "CORRECT  — the zone, the sweep/confirmation read and the entry all match",
            "           what the flowchart says should happen here.",
            "PARTIAL  — the event is real but one element is arguable (zone width,",
            "           confirmation choice, or entry placement).",
            "WRONG    — the event should not have been a setup at all.",
            "UNCLEAR  — the chart does not carry enough context to decide.",
            "",
            "Write your score in events.csv (expert_score column) or on the page.",
            "The architect-side reading of these same events lives in",
            "06_RESEARCH/PFE3_EXPERT_VALIDATION_PACK.md and is deliberately kept",
            "separate from your column — do not read it before scoring.",
            "",
            "Menu pages are the product law. Seek pages are continuity samples and",
            "are labelled as such on every page and in the CSV.",
        ])
        if menu_events:
            _section_page(pdf, "SECTION A — MENU FILLS (product law)",
                          [f"{len(menu_events)} events. Every fill in the three",
                           "PFE-2 menu windows, Jun/Sep/Oct 1–10 2025.",
                           "", "These are the events to judge first."])
        for event in menu_events:
            png = REPO_ROOT / event["chart"] if event["chart"] else None
            if png and png.exists():
                _page(pdf, png)
        if neg_events:
            _section_page(pdf, "SECTION B — ARMED, NO CONFIRMATION",
                          [f"{len(neg_events)} events. Armed menu POIs that never",
                           "produced a winner. Question: should any of these have",
                           "produced a confirmation the engine missed?"])
        for event in neg_events:
            png = REPO_ROOT / event["chart"] if event["chart"] else None
            if png and png.exists():
                _page(pdf, png)
        if seek_ev:
            _section_page(pdf, "SECTION C — SEEK FILLS (continuity only)",
                          [f"{len(seek_ev)} events from the six-month seek book.",
                           "These are NOT the default live path. They are here for",
                           "zone/entry contrast only and must not be read as the",
                           "product's behaviour."])
        for event in seek_ev:
            png = REPO_ROOT / event["chart"] if event["chart"] else None
            if png and png.exists():
                _page(pdf, png)
        _section_page(pdf, "SCORE SHEET", _score_sheet(events))

    _write_markdown(events, counts)
    print(json.dumps({"counts": counts, "pdf": str(pdf_path),
                      "charted": rendered}, indent=2))
    return 0


def _page(pdf: PdfPages, png: Path) -> None:
    from matplotlib.image import imread

    image = imread(png)
    fig = plt.figure(figsize=(11, 8.5))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(image)
    ax.axis("off")
    pdf.savefig(fig)
    plt.close(fig)


def _score_sheet(events: list[dict]) -> list[str]:
    lines = ["event_id".ljust(46) + "kind".ljust(17) + "score".ljust(10) + "note"]
    for event in events:
        lines.append(event["event_id"].ljust(46)
                     + event["kind"][:16].ljust(17)
                     + "__________".ljust(10) + "____________________")
    return lines


def _write_markdown(events: list[dict], counts: dict) -> None:
    lines = [
        "# PFE-3 — EXPERT VALIDATION PACK (STRUCTURE + CONFIRM + ENTRY)",
        "",
        "**Date:** 2026-11-15 · **Program:** PFE step 3 · **`LOGIC_CHANGED: NO`**",
        "**PDF:** `06_RESEARCH/results/pfe3_expert_pack/EXPERT_REVIEW_PACK.pdf` ·",
        "**Events:** `06_RESEARCH/results/pfe3_expert_pack/events.csv` ·",
        "**Charts:** `06_RESEARCH/results/pfe3_expert_pack/charts/`",
        "",
        "**Diagnostic review pack — not performance. No expectancy language is",
        "used anywhere in the pack, by design.**",
        "",
        "## 1. What is in the pack",
        "",
        "| Section | Events | What it is |",
        "|---|---|---|",
        f"| A — menu fills | {counts['menu_fill']} | every fill in the three PFE-2 menu windows (Jun/Sep/Oct 1–10 2025) — the product law |",
        f"| B — armed, no confirmation | {counts['menu_no_winner']} | armed menu POIs that never produced a winner (up to 10 per window, even stride) |",
        f"| C — seek fills | {counts['seek_fill']} | six-month seek book, even stride — CONTINUITY ONLY, not the live default |",
        "",
        "Selection was fixed in `06_RESEARCH/scripts/pfe3_expert_pack.py` before any",
        "chart existed and applied mechanically: all menu fills, even-stride negative",
        "and seek samples, no additions or removals afterwards.",
        "",
        "## 2. How each chart reads",
        "",
        "| Element | Meaning |",
        "|---|---|",
        "| Blue band | the POI zone, labelled with its detection timeframe and model tags |",
        "| Black solid | entry price |",
        "| Red dashed | original SL |",
        "| Teal dashed | TP |",
        "| Orange dotted | sweep instant (menu stamp) |",
        "| Purple dotted | confirmation instant (menu stamp) |",
        "| Grey dashed | exit |",
        "",
        "## 3. Rubric",
        "",
        "**CORRECT** — zone, sweep/confirmation read and entry all match the flowchart.",
        "**PARTIAL** — real event, one element arguable (zone width, confirmation choice, entry placement).",
        "**WRONG** — this should not have been a setup.",
        "**UNCLEAR** — the chart does not carry enough context.",
        "",
        "Score in `events.csv` (`expert_score`, `expert_note`) or on the PDF page.",
        "Architect-side notes below are deliberately separated so scoring is blind.",
        "",
        "## 4. Architect draft notes (do not read before scoring)",
        "",
        "<details><summary>Notes</summary>",
        "",
        "- All 27 menu fills in the PFE-2 windows are Trigger F; A/D never won. If the",
        "  expert marks F-only entries as PARTIAL/WRONG, that is evidence about the",
        "  menu's trigger subsets, not about C3 or the sweep stage.",
        "- Menu TP source splits 17 structural / 10 fallback across the three windows;",
        "  the pack includes both, so the expert can judge fallback targets on their",
        "  own merits rather than against a single target style.",
        "- Section B is the honest negative set: charting idle armed POIs is how we",
        "  learn whether the confirmation stage is too strict, without touching it.",
        "  Any judgment that these should have fired is a PFE-4 design question.",
        "",
        "</details>",
        "",
        "## 5. Event index",
        "",
        "| # | event_id | kind | tf | trigger | tp_source | close | chart |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, event in enumerate(events, 1):
        lines.append(
            f"| {i} | `{event['event_id']}` | {event['kind']} | "
            f"{event.get('detection_tf') or '—'} | {event.get('trigger') or '—'} | "
            f"{event.get('tp_source') or '—'} | {event.get('close_kind') or '—'} | "
            f"`{event['chart']}` |")
    lines += [
        "",
        "## 6. What this pack does not claim",
        "",
        "No edge, expectancy, win rate, profitability or optimisation. Counts here",
        "are review volume on a boundary sample, not a trading rate. Menu and seek",
        "are never ranked against each other.",
        "",
    ]
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
