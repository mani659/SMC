"""SCAN 1A — LTF (M5) trigger-confirmation BASELINE census, NO POI filter.

Question: "does the structure exist / does the detector fire?" for the six
locked triggers (A CHOCH, B Leading Diagonal, C Ending Diagonal, D Two-Bar,
E RSI Divergence, F BOS+OB) over the SAME year window as the product 1y
census, WITHOUT requiring any armed/accepted POI and WITHOUT the product
menu one-story gate.

METHOD (pre-registered):
- PRODUCTION trigger code is imported and evaluated as-is (no
  reimplementation): the six trigger classes + TriggerRouter eligibility,
  exactly as ``stage3_trigger_visibility`` Pass 2 evaluates them
  (TriggerContext: candles/swings prefix through bar_index, hints =
  SeriesState).
- Window: exec 2024-11-01 -> 2025-10-31 UTC on M5 (the product horizon TF;
  the product wires triggers only to the M5 execution path). NO M5 load
  warm-up — the product's own 1y segments started M5 at exec start; the
  census uses the identical information. (An M1 scan is NOT run: trigger
  code never reads a timeframe; scanning M1 would duplicate the same
  TF-agnostic windows and double-count — recorded as m1_scan = 0 with this
  reason, same convention as STAGE3_TRIGGER_VISIBILITY.)
- NO POI filter: every bar is evaluated for BOTH directions against a
  synthetic M8 POI whose sentinel zone spans [0, 1e6] — zone BOUNDS never
  accept/reject anything, so no accepted-zone story is required. Direction
  comes from the synthetic zone (both evaluated; the direction that fires
  is the geometry's own direction). Matrix eligibility via
  ``TriggerRouter.eligible_types`` on the synthetic M8 POI (all six
  triggers eligible — verified).
- Scan window rule = the SAME frozen product horizon as Stage 3:
  ``from_bar = max(0, bar - poi_give_up_bars())`` (20 M5 bars — existing
  constant, imported, not re-typed).
- DEDUPE (mechanical, documented): one completion per
  (trigger letter, direction, signal.data proof geometry). Triggers are
  self-limiting per geometry (F: first-touch; A: break bar), but the
  rolling window can re-present the same geometry — the key collapses it.
- Entries/stops: recorded from the signal but flagged — under the sentinel
  zone, F's FR-3.1 anchor always re-anchors to a zone edge
  (``entry_degenerate``); A/D/E entries are geometry-derived and
  meaningful. 1A is a DETECTOR census: no arm/route/fill code is called.
- HARD RULE: this layer must NOT call product arm/route/fill. Detector /
  evaluation only.

DIAGNOSTIC ONLY: no edge claim, no optimization, no threshold change.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "04_SRC"))
sys.path.insert(0, str(REPO / "06_RESEARCH" / "scripts"))

from smc.config.model_type import ModelType  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402
from smc.core.enums import Direction  # noqa: E402
from smc.core.poi import POI  # noqa: E402
from smc.core.zone import Zone  # noqa: E402
from smc.data.parquet_loader import load_ohlcv_parquet  # noqa: E402
from smc.data.resample import resample_multi  # noqa: E402
from smc.triggers.base_trigger import TriggerContext  # noqa: E402
from smc.triggers.trigger_a_choch import ChochReversalTrigger  # noqa: E402
from smc.triggers.trigger_b_leading_diagonal import (  # noqa: E402
    LeadingDiagonalTrigger)
from smc.triggers.trigger_c_ending_diagonal import (  # noqa: E402
    EndingDiagonalTrigger)
from smc.triggers.trigger_d_two_bar import TwoBarReversalTrigger  # noqa: E402
from smc.triggers.trigger_e_rsi_divergence import (  # noqa: E402
    RsiDivergenceTrigger)
from smc.triggers.trigger_expiry import poi_give_up_bars  # noqa: E402
from smc.triggers.trigger_f_bos_ob import BosObContinuationTrigger  # noqa: E402
from smc.triggers.trigger_router import TriggerRouter  # noqa: E402

OUT = REPO / "06_RESEARCH" / "results" / "scan1a_ltf_no_poi"
CHARTS = OUT / "charts"

EXEC_FROM, EXEC_TO = "2024-11-01", "2025-10-31"
LOAD_FROM = "2024-09-01"          # documented (HTF warm-up only; M5 = exec)
SENTINEL_BOTTOM, SENTINEL_TOP = 0.0, 1.0e6
HORIZON = poi_give_up_bars()      # 20 M5 bars — existing frozen constant

SIX_TRIGGERS = [
    ChochReversalTrigger(), LeadingDiagonalTrigger(), EndingDiagonalTrigger(),
    TwoBarReversalTrigger(), RsiDivergenceTrigger(), BosObContinuationTrigger(),
]
LETTER = {t.type.name[0] for t in SIX_TRIGGERS}  # sanity: {A,B,C,D,E,F}
TRIGGER_LETTER = {t.type: t.type.name[0] for t in SIX_TRIGGERS}

# Proof fields expected per trigger — ACTUAL signal.data keys (verified from
# the 1A events census; never invent fields). B exports wave5_index/
# origin_level/fib_band; C exports terminal_index/converging/boundary; D can
# never emit on this feed (frozen volume gate — feed has no volume, all 0.0).
PROOF_FIELDS = {
    "A": ["rule", "sweep_index", "broken_level"],
    "B": ["origin_level", "wave5_index", "fib_band"],
    "C": ["terminal_index", "converging", "boundary"],
    "D": ["engulfing_index"],
    "E": ["peak1_index", "peak2_index"],
    "F": ["bos_index", "ob_index", "entry_anchor"],
}


def fail_loud(msg: str) -> None:
    raise SystemExit(f"[scan1a] FAIL LOUD: {msg}")


def load_m5() -> list:
    lo = datetime.fromisoformat(EXEC_FROM).replace(tzinfo=timezone.utc)
    # exec-to inclusive of the FULL day — phase3 convention
    # (``_parse_day(exec_to) + 1d - 1min``), same as product_1y segments.
    hi = (datetime.fromisoformat(EXEC_TO).replace(tzinfo=timezone.utc)
          + timedelta(days=1) - timedelta(minutes=1))
    m1 = [c for c in load_ohlcv_parquet(REPO / "07_DATA" / "XAUUSD_M1.parquet")
          if lo - timedelta(days=1) <= c.timestamp <= hi + timedelta(days=1)]
    multi = resample_multi(m1, [Timeframe.M5])
    m5 = [c for c in multi[Timeframe.M5] if lo <= c.timestamp <= hi]
    print(f"[scan1a] M5 exec bars: {len(m5)}", flush=True)
    return m5


def census(m5: list) -> list[dict]:
    """One pass over the window; returns deduped completion rows."""
    from smc.backtest.series_state import SeriesState

    router = TriggerRouter()
    synthetic = {}
    for d in (Direction.LONG, Direction.SHORT):
        poi = POI(zone=Zone(bottom=SENTINEL_BOTTOM, top=SENTINEL_TOP,
                            direction=d, timeframe=Timeframe.M5),
                  models=[ModelType.M8], m8_kind=None)
        synthetic[d] = (poi, [t for t in SIX_TRIGGERS
                              if t.type in router.eligible_types(poi)])
    seen: set[tuple] = set()
    rows: list[dict] = []
    state = SeriesState(Timeframe.M5)
    for bar, candle in enumerate(m5):
        state.extend(candle)
        if bar < 1:
            continue
        from_bar = max(0, bar - HORIZON)
        for d, (poi, triggers) in synthetic.items():
            ctx = TriggerContext(poi=poi, candles=state.candles,
                                 swings=state.swings, bar_index=bar,
                                 from_bar=from_bar, hints=state)
            for trigger in triggers:
                signal = trigger.evaluate(ctx)
                if signal is None:
                    continue
                letter = TRIGGER_LETTER[trigger.type]
                data = dict(signal.data or {})
                key = (letter, d.name, tuple(sorted(
                    (k, repr(v)) for k, v in data.items())))
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "trigger": letter,
                    "direction": d.name.lower(),
                    "bar": bar,
                    "bar_time_utc": candle.timestamp.isoformat(),
                    "completion_index": signal.completion_index,
                    "entry_price": signal.entry_price,
                    "stop_reference": signal.stop_reference,
                    "detail": signal.detail,
                    "data": json.dumps(data, default=str),
                    "month": candle.timestamp.strftime("%Y-%m"),
                })
        if bar % 10000 == 0:
            print(f"[scan1a] bar {bar}/{len(m5)} rows={len(rows)}", flush=True)
    return rows


def summarize(rows: list[dict], n_bars: int, elapsed_s: float,
              dual_pass_equal: bool) -> dict:
    by_trigger = dict(sorted(Counter(r["trigger"] for r in rows).items()))
    by_direction = dict(sorted(Counter(r["direction"] for r in rows).items()))
    by_month = dict(sorted(Counter(r["month"] for r in rows).items()))
    proof = {}
    for letter, fields in PROOF_FIELDS.items():
        lrows = [r for r in rows if r["trigger"] == letter]
        if not lrows:
            proof[letter] = {f: None for f in fields} | {"n": 0}
            continue
        datas = [json.loads(r["data"]) for r in lrows]
        proof[letter] = {
            **{f: round(sum(1 for d in datas if d.get(f) is not None)
                        / len(datas), 4) for f in fields},
            "n": len(lrows)}
    # gap between setup geometry and signal bar (cheap, proof-field based)
    gaps_out = {}
    f_rows = [(r["bar"], json.loads(r["data"])) for r in rows
              if r["trigger"] == "F"]
    f_gaps = sorted(bar - d["bos_index"] for bar, d in f_rows
                    if d.get("bos_index") is not None)
    if f_gaps:
        gaps_out["F_setup_to_signal"] = {
            "median_bars": f_gaps[len(f_gaps) // 2],
            "definition": "signal bar - bos_index (F only, cheap)"}
    a_rows = [(r["bar"], json.loads(r["data"])) for r in rows
              if r["trigger"] == "A"]
    a_gaps = sorted(bar - d["sweep_index"] for bar, d in a_rows
                    if d.get("sweep_index") is not None)
    if a_gaps:
        gaps_out["A_sweep_to_signal"] = {
            "median_bars": a_gaps[len(a_gaps) // 2],
            "definition": "signal bar - sweep_index (A only, where sweep present)"}
    return {
        "tag": "scan1a_ltf_no_poi",
        "diagnostic_only": True,
        "window": {"exec": f"{EXEC_FROM} -> {EXEC_TO}", "load_from": LOAD_FROM,
                   "m5_bars": n_bars},
        "layer": "1A baseline detector census (NO POI filter, no menu/one-story gate)",
        "m1_scan": 0,
        "m1_scan_reason": ("trigger code never reads a timeframe; an M1 scan "
                           "would duplicate the same TF-agnostic windows and "
                           "double-count (STAGE3_TRIGGER_VISIBILITY convention)"),
        "method": {
            "synthetic_zone": "[0, 1e6] sentinel — zone bounds never filter",
            "scan_window_rule": f"from_bar = max(0, bar - {HORIZON}) "
                                "(poi_give_up_bars, existing frozen constant)",
            "dedupe": "one row per (trigger, direction, signal.data geometry)",
            "dual_run": "census computed twice in-process; counts compared",
            "dual_pass_counts_equal": dual_pass_equal,
        },
        "totals": {"completions": len(rows), "by_trigger": by_trigger,
                   "by_direction": by_direction, "by_month": by_month},
        "proof_field_presence": proof,
        "setup_to_signal_gaps": gaps_out,
        "runtime_seconds": round(elapsed_s, 1),
        "charts": {"cap": 36, "stratified_by": "trigger, spread in time"},
    }


def pick_chart_sample(rows: list[dict], cap: int = 36) -> list[dict]:
    """Per-trigger quota, spread deterministically across the year."""
    by_t: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_t[r["trigger"]].append(r)
    letters = sorted(by_t)
    quota = max(1, cap // max(len(letters), 1))
    picked = []
    for letter in letters:
        rs = sorted(by_t[letter], key=lambda r: (r["bar"], r["direction"]))
        if len(rs) <= quota:
            picked.extend(rs)
            continue
        stride = max(1, len(rs) // quota)
        picked.extend(rs[::stride][:quota])
    picked.sort(key=lambda r: (r["bar"], r["trigger"]))
    return picked[:cap]


def render_panel(row: dict, m5: list, out_png: Path) -> None:
    """One M5 census panel — lazy matplotlib (CI-safe), NO zone band (no POI)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    bar = row["bar"]
    lo, hi = max(0, bar - 60), min(len(m5), bar + 60)
    window = m5[lo:hi]
    fig = plt.figure(figsize=(11.0, 8.5))
    ax = fig.add_axes([0.07, 0.30, 0.90, 0.64])
    xs = [mdates.date2num(c.timestamp) for c in window]
    width = (xs[1] - xs[0]) * 0.6 if len(xs) > 1 else 0.002
    for x, c in zip(xs, window):
        colour = "#2e7d32" if c.close >= c.open else "#c62828"
        ax.vlines(x, c.low, c.high, color=colour, linewidth=0.7)
        body_lo = min(c.open, c.close)
        h = abs(c.close - c.open) or 0.01
        ax.add_patch(Rectangle((x - width / 2, body_lo), width, h,
                               facecolor=colour, edgecolor=colour, alpha=0.85))
    x_bar = xs[bar - lo]
    ax.axvline(x_bar, color="#000000", linewidth=1.2, linestyle="-")
    ax.text(x_bar, window[0].low, " completion", rotation=90, va="bottom",
            ha="right", fontsize=8, color="#000000")
    pad = (xs[-1] - xs[0]) * 0.05
    ax.set_xlim(xs[0], xs[-1] + pad)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.set_ylabel("XAUUSD  (M5)")
    ax.grid(alpha=0.2, linewidth=0.4)
    letter = row["trigger"]
    names = {"A": "CHOCH REVERSAL", "B": "LEADING DIAGONAL",
             "C": "ENDING DIAGONAL", "D": "TWO-BAR REVERSAL",
             "E": "RSI DIVERGENCE", "F": "BOS + OB CONTINUATION"}
    ax.set_title(f"TRIGGER_{letter} ({names[letter]}) · NO_POI_FILTER · "
                 f"{row['direction'].upper()} · {row['bar_time_utc'][:16]}",
                 fontsize=10, loc="left")
    data = json.loads(row["data"])
    lines = [
        f"scan1a baseline census — detector/eval only; no arm/route/fill called",
        f"proof fields: {json.dumps(data)}",
        f"detail: {row['detail']}",
        "",
        "NO_POI_FILTER: synthetic sentinel zone; no accepted-zone story",
        "required. Diagnostic census — NOT a trade claim.",
    ]
    fig.text(0.07, 0.26, "\n".join(lines), ha="left", va="top", fontsize=7.6,
             family="monospace")
    fig.savefig(out_png, dpi=130)
    plt.close(fig)


def main() -> int:
    import time
    t0 = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    CHARTS.mkdir(parents=True, exist_ok=True)
    m5 = load_m5()
    if len(m5) < 60000:
        fail_loud(f"M5 exec series too small: {len(m5)} bars")
    rows1 = census(m5)
    t1 = time.perf_counter()
    rows2 = census(m5)
    dual_equal = (Counter((r["trigger"], r["direction"]) for r in rows1)
                  == Counter((r["trigger"], r["direction"]) for r in rows2)
                  and len(rows1) == len(rows2))
    if not dual_equal:
        fail_loud("dual in-process census passes disagree")
    rows = rows1
    elapsed = t1 - t0

    summary = summarize(rows, len(m5), elapsed, dual_equal)
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")

    cols = ["trigger", "direction", "bar", "bar_time_utc", "month",
            "completion_index", "entry_price", "stop_reference", "detail",
            "data"]
    with (OUT / "events_scan1a_completions.csv").open(
            "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})

    sample = pick_chart_sample(rows)
    index = []
    for i, row in enumerate(sample, start=1):
        png = CHARTS / (f"{i:02d}_trigger_{row['trigger']}_"
                        f"{row['direction']}_no_poi_filter.png")
        render_panel(row, m5, png)
        index.append({"seq": i, "file": png.name,
                      "trigger": row["trigger"], "direction": row["direction"],
                      "bar_time_utc": row["bar_time_utc"]})
    summary["chart_index"] = index
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")

    print(f"[scan1a] completions: {len(rows)} in {elapsed:.0f}s "
          f"| by trigger: {summary['totals']['by_trigger']}", flush=True)
    print(f"[scan1a] dual in-process pass counts equal: {dual_equal}",
          flush=True)
    print(f"[scan1a] charts: {len(index)} -> {CHARTS}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
