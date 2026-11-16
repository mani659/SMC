"""SCAN 1B — LTF (M5) trigger completions WITH the POI / product link.

Same year window as Scan 1A / product_1y (exec 2024-11-01 -> 2025-10-31).
Reuses the product-linked universe from the segmented 1y menu census
(``06_RESEARCH/results/product_1y_one_story/run1/*/armed_records.json`` +
``trades.csv``) — the accepted zone stories the product actually ARMED —
and runs the SAME Stage-3 trigger inventory over each armed POI's product
horizon window (``[arm, arm + poi_give_up_bars()]``, 20 M5 bars — the
existing frozen constant via ``ltf_confirmation_pack.LA_M5_BARS``).

Per armed POI: TWO synthetic M8 wrappers (LONG and SHORT) carrying the
POI's REAL zone bounds (bounds from the product record; never invented).
Zone bounds and the arm bar are the product link; direction is evaluated
both ways (the direction that fires is recorded). Production trigger code
only — no reimplementation, no new thresholds.

Lifecycle mapping (explicit, from existing product semantics):
- ``FILLED``            armed POI whose routed order filled (routed=true in
                        armed_records; verified == the POI set of
                        trades.csv; 239 total — must reconcile to
                        product_1y, FAIL LOUD otherwise).
- ``ROUTED_NOT_FILLED`` winners that reached the order seam but never
                        filled. AGGREGATE ONLY (submitted-unplaced 33 +
                        placed-unfilled 13 = 46): per-POI placed flags are
                        not exported by the 1y artifacts; documented.
- ``COMPLETED_NOT_ROUTED`` armed POI with >=1 geometric trigger completion
                        in its window whose menu episode never routed
                        (routed != true). Includes menu-guard intake drops
                        (580 aggregate) and never-won episodes.
- ``ARMED_NO_COMPLETION`` armed POI with ZERO M5 trigger completions in
                        its window (armed, but the M5 geometry never
                        completed).
- ``OPEN_SCAN_ROUTED``  non-exclusive marker: armed POIs whose menu episode
                        routed (= the winner set, 865 aggregate); its
                        exclusive outcomes are FILLED / the aggregate
                        ROUTED_NOT_FILLED / intake-dropped winners.

DIAGNOSTIC ONLY: no edge claim, no optimization, no threshold change;
detector/evaluation only (no product decision code is called).
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
from smc.triggers.trigger_f_bos_ob import BosObContinuationTrigger  # noqa: E402
from smc.triggers.trigger_router import TriggerRouter  # noqa: E402

import ltf_confirmation_pack as ltf  # noqa: E402  (LA_M5_BARS, lookahead)

SRC = REPO / "06_RESEARCH" / "results" / "product_1y_one_story" / "run1"
SCAN1A = REPO / "06_RESEARCH" / "results" / "scan1a_ltf_no_poi" / "summary.json"
OUT = REPO / "06_RESEARCH" / "results" / "scan1b_ltf_with_poi"
CHARTS = OUT / "charts"

SEGMENTS = {
    "nov24": ("2024-11-01", "2024-11-30"),
    "dec24": ("2024-12-01", "2024-12-31"),
    "jan25": ("2025-01-01", "2025-01-31"),
    "feb25": ("2025-02-01", "2025-02-28"),
    "mar25": ("2025-03-01", "2025-03-31"),
    "apr25": ("2025-04-01", "2025-04-30"),
    "may25": ("2025-05-01", "2025-05-31"),
    "jun25": ("2025-06-01", "2025-06-30"),
    "jul25": ("2025-07-01", "2025-07-31"),
    "aug25": ("2025-08-01", "2025-08-31"),
    "sep25": ("2025-09-01", "2025-09-30"),
    "oct25": ("2025-10-01", "2025-10-31"),
}

SIX_TRIGGERS = [
    ChochReversalTrigger(), LeadingDiagonalTrigger(), EndingDiagonalTrigger(),
    TwoBarReversalTrigger(), RsiDivergenceTrigger(), BosObContinuationTrigger(),
]
TRIGGER_LETTER = {t.type: t.type.name[0] for t in SIX_TRIGGERS}
TRIGGER_NAMES = {"A": "CHOCH", "B": "LEADING DIAGONAL", "C": "ENDING DIAGONAL",
                 "D": "TWO-BAR REVERSAL", "E": "RSI DIVERGENCE",
                 "F": "BOS+OB"}


def fail_loud(msg: str) -> None:
    raise SystemExit(f"[scan1b] FAIL LOUD: {msg}")


def segment_m5(exec_from: str, exec_to: str) -> list:
    lo = datetime.fromisoformat(exec_from).replace(tzinfo=timezone.utc)
    # exec-to inclusive of the FULL day — phase3 convention
    # (``_parse_day(exec_to) + 1d - 1min``), same as product_1y segments.
    hi = (datetime.fromisoformat(exec_to).replace(tzinfo=timezone.utc)
          + timedelta(days=1) - timedelta(minutes=1))
    m1 = [c for c in load_ohlcv_parquet(REPO / "07_DATA" / "XAUUSD_M1.parquet")
          if lo - timedelta(days=1) <= c.timestamp <= hi + timedelta(days=1)]
    multi = resample_multi(m1, [Timeframe.M5])
    return [c for c in multi[Timeframe.M5] if lo <= c.timestamp <= hi]


def scan_segment(seg: str, m5: list, armed: dict, fills: list[dict]) -> dict:
    """Trigger inventory over every armed POI's product horizon window."""
    from smc.backtest.series_state import SeriesState

    router = TriggerRouter()
    stamps = [c.timestamp for c in m5]
    # per armed POI: real zone bounds, both synthetic directions, M8 wrapper
    jobs: dict[int, list[dict]] = defaultdict(list)
    for poi_id, rec in armed.items():
        arm = int(rec["armed_bar"])
        if arm >= len(m5):
            fail_loud(f"{seg}: armed_bar {arm} out of range "
                      f"(len {len(m5)}) for {poi_id}")
        start, end = ltf.lookahead_window(arm, ltf.LA_M5_BARS, len(m5))
        zlo, zhi = float(rec["zone_low"]), float(rec["zone_high"])
        wrappers = []
        for d in (Direction.LONG, Direction.SHORT):
            poi = POI(zone=Zone(bottom=zlo, top=zhi, direction=d,
                                timeframe=Timeframe.M5),
                      models=[ModelType.M8], m8_kind=None)
            wrappers.append((d, poi, [t for t in SIX_TRIGGERS
                                      if t.type in router.eligible_types(poi)]))
        jobs[start].append({"rec": rec, "poi_id": poi_id, "start": start,
                            "end": end, "wrappers": wrappers,
                            "completions": []})

    filled_ids = {t["poi_id"] for t in fills}
    state = SeriesState(Timeframe.M5)
    active: list[dict] = []
    for bar, candle in enumerate(m5):
        state.extend(candle)
        active.extend(jobs.get(bar, ()))
        keep = []
        for job in active:
            if bar <= job["end"]:
                keep.append(job)
                if job["start"] <= bar:
                    for d, poi, triggers in job["wrappers"]:
                        ctx = TriggerContext(
                            poi=poi, candles=state.candles,
                            swings=state.swings, bar_index=bar,
                            from_bar=job["start"], hints=state)
                        for trigger in triggers:
                            signal = trigger.evaluate(ctx)
                            if signal is None:
                                continue
                            job["completions"].append({
                                "poi_id": job["poi_id"],
                                "segment": seg,
                                "trigger": TRIGGER_LETTER[trigger.type],
                                "direction": d.name.lower(),
                                "bar": bar,
                                "bar_time_utc": candle.timestamp.isoformat(),
                                "data": json.dumps(signal.data or {},
                                                   default=str),
                            })
        active = keep

    out = {"completions": [], "buckets": Counter(), "pois": 0}
    for start_jobs in jobs.values():
        for job in start_jobs:
            rec = job["rec"]
            out["pois"] += 1
            is_filled = rec["poi_id"] in filled_ids
            n_comp = len(job["completions"])
            if is_filled:
                out["buckets"]["FILLED"] += 1
            elif n_comp > 0:
                out["buckets"]["COMPLETED_NOT_ROUTED"] += 1
            else:
                out["buckets"]["ARMED_NO_COMPLETION"] += 1
            out["completions"].extend(job["completions"])
    return out


def render_panel_poi(row: dict, rec: dict, m5: list, bucket: str,
                     out_png: Path) -> None:
    """One M5 POI-linked panel — real zone band from the product record."""
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
    zlo, zhi = float(rec["zone_low"]), float(rec["zone_high"])
    ax.axhspan(zlo, zhi, color="#1565c0", alpha=0.16)
    ax.text(xs[0], zhi, f" POI zone [{zlo:.2f}, {zhi:.2f}]", fontsize=7.5,
            va="bottom", color="#0d47a1")
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
    ax.set_title(f"TRIGGER_{letter} ({TRIGGER_NAMES[letter]}) · {bucket} · "
                 f"{row['direction'].upper()} · {row['bar_time_utc'][:16]} · "
                 f"{row['segment'].upper()}",
                 fontsize=10, loc="left")
    data = json.loads(row["data"]) if row["data"] else {}
    lines = [
        "scan1b product-linked scan — armed POI universe, real zone bounds;",
        "detector/evaluation only; no product decision code called.",
        f"poi_id: {row['poi_id']} | armed_bar: {rec.get('armed_bar')}",
        f"proof fields: {json.dumps(data, default=str)}",
        "Diagnostic census — NOT a trade claim.",
    ]
    fig.text(0.07, 0.26, "\n".join(lines), ha="left", va="top", fontsize=7.6,
             family="monospace")
    fig.savefig(out_png, dpi=130)
    plt.close(fig)


def render_charts(all_completions: list[dict],
                  filled_keys: set[tuple],
                  b_geo_keys: set[tuple]) -> list[dict]:
    """<= 24 panels across three groups; lazy matplotlib (CI-safe).

    Groups: (i) 1A-only completions whose geometry never appears in any
    armed-POI window; (ii) POI-linked not routed; (iii) filled.
    """
    import scan1a_ltf_no_poi as s1a  # reuse year loader + NO_POI_FILTER panel

    cap, per_group = 24, 8
    index: list[dict] = []

    # ---- group (i): 1A-only geometry (no POI link anywhere in the year) ---- #
    a_csv = (REPO / "06_RESEARCH" / "results" / "scan1a_ltf_no_poi" /
             "events_scan1a_completions.csv")
    with a_csv.open(newline="", encoding="utf-8") as fh:
        a_rows = list(csv.DictReader(fh))
    a_only = [r for r in a_rows
              if (r["trigger"], r["direction"], r["data"]) not in b_geo_keys]
    a_only.sort(key=lambda r: (int(r["bar"]), r["trigger"]))
    if a_only:
        stride = max(1, len(a_only) // per_group)
        m5_year = s1a.load_m5()
        seq = 1
        for r in a_only[::stride][:per_group]:
            png = CHARTS / (f"{seq:02d}_1a_only_no_poi_{r['trigger']}_"
                            f"{r['direction']}.png")
            row = dict(r)
            row["bar"] = int(r["bar"])
            s1a.render_panel(row, m5_year, png)
            index.append({"seq": seq, "group": "1A_ONLY_NO_POI",
                          "file": png.name, "trigger": r["trigger"],
                          "direction": r["direction"],
                          "bar_time_utc": r["bar_time_utc"]})
            seq += 1

    # ---- groups (ii) / (iii): POI-linked completions ----------------------- #
    by_group: dict[str, list[dict]] = defaultdict(list)
    for c in all_completions:
        key = (c["segment"], c["poi_id"])
        by_group["FILLED" if key in filled_keys
                 else "POI_LINKED_NOT_ROUTED"].append(c)
    seg_m5: dict[str, list] = {}
    armed_by_seg: dict[str, dict] = {}
    seq = len(index) + 1
    for group in ("POI_LINKED_NOT_ROUTED", "FILLED"):
        rows = sorted(by_group[group],
                      key=lambda c: (c["segment"], c["bar"], c["trigger"]))
        if not rows:
            continue
        stride = max(1, len(rows) // per_group)
        for r in rows[::stride][:per_group]:
            if seq > cap:
                break
            seg = r["segment"]
            if seg not in seg_m5:
                seg_m5[seg] = segment_m5(*SEGMENTS[seg])
                armed_by_seg[seg] = json.loads(
                    (SRC / seg / "armed_records.json").read_text(
                        encoding="utf-8"))
            rec = armed_by_seg[seg].get(r["poi_id"])
            if rec is None:
                continue
            png = CHARTS / (f"{seq:02d}_{group.lower()}_{r['trigger']}_"
                            f"{r['direction']}_{seg}.png")
            render_panel_poi(r, rec, seg_m5[seg], group, png)
            index.append({"seq": seq, "group": group, "file": png.name,
                          "poi_id": r["poi_id"], "segment": seg,
                          "trigger": r["trigger"], "direction": r["direction"],
                          "bar_time_utc": r["bar_time_utc"]})
            seq += 1
    return index[:cap]


def main() -> int:
    import time
    t0 = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    CHARTS.mkdir(parents=True, exist_ok=True)
    if not SCAN1A.exists():
        fail_loud(f"missing Scan 1A summary: {SCAN1A}")

    all_completions: list[dict] = []
    bucket_total: Counter = Counter()
    armed_total = 0
    fills_all: list[dict] = []
    per_segment = {}
    for seg, (lo, hi) in SEGMENTS.items():
        seg_dir = SRC / seg
        armed = json.loads((seg_dir / "armed_records.json").read_text(
            encoding="utf-8"))
        with (seg_dir / "trades.csv").open(newline="",
                                           encoding="utf-8") as fh:
            fills = list(csv.DictReader(fh))
        fills_all.extend(fill | {"_segment": seg} for fill in fills)
        filled_ids = {t["poi_id"] for t in fills}
        routed_ids = {pid for pid, r in armed.items()
                      if str(r.get("routed", "")) == "true"}
        if routed_ids != filled_ids:
            fail_loud(f"{seg}: routed-set != filled-set "
                      f"({len(routed_ids)} vs {len(filled_ids)}) — "
                      f"lifecycle mapping premise violated")
        m5 = segment_m5(lo, hi)
        res = scan_segment(seg, m5, armed, fills)
        per_segment[seg] = {"armed": len(armed), "fills": len(fills),
                            "m5_bars": len(m5),
                            "buckets": dict(res["buckets"]),
                            "completions": len(res["completions"])}
        all_completions.extend(res["completions"])
        bucket_total.update(res["buckets"])
        armed_total += len(armed)
        print(f"[scan1b] {seg}: armed {len(armed)} m5 {len(m5)} "
              f"completions {len(res['completions'])} "
              f"buckets {dict(res['buckets'])}", flush=True)

    # ---- aggregate product funnel (from product_1y artifacts, read-only) --- #
    winners_total = 0
    submitted_total = 0
    placed_total = 0
    for seg in SEGMENTS:
        fs = json.loads((SRC / seg / "funnel_summary.json").read_text(
            encoding="utf-8"))
        winners_total += fs["menu_winners"]
        submitted_total += (fs.get("menu_counters") or {}).get(
            "menu_submitted", 0)
        placed_total += fs["placed"]

    # ---- reconciliation with product_1y (FAIL LOUD) ------------------------ #
    fill_mix = dict(sorted(Counter(
        (t.get("trigger") or "?") for t in fills_all).items()))
    p1y = json.loads((REPO / "06_RESEARCH" / "results" / "product_1y_one_story"
                      / "summary.json").read_text(encoding="utf-8"))
    p1y_mix = p1y["combined"]["fills_by_trigger"]
    if fill_mix != p1y_mix:
        fail_loud(f"fill trigger mix {fill_mix} != product_1y {p1y_mix}")
    if len(fills_all) != p1y["combined"]["raw_fills"]:
        fail_loud("fill count mismatch vs product_1y")

    # ---- cross-tabs -------------------------------------------------------- #
    s1a = json.loads(SCAN1A.read_text(encoding="utf-8"))
    a_by_trigger = s1a["totals"]["by_trigger"]
    b_by_trigger = dict(sorted(Counter(
        c["trigger"] for c in all_completions).items()))
    b_unique_geo = dict(sorted(Counter(
        (c["trigger"], c["direction"], c["data"])
        for c in all_completions).items()))
    xtab = {}
    for letter in sorted(set(a_by_trigger) | set(b_by_trigger)):
        a_n, b_n = a_by_trigger.get(letter, 0), b_by_trigger.get(letter, 0)
        xtab[letter] = {
            "scan1a_no_poi": a_n, "scan1b_poi_linked_occurrences": b_n,
            "link_fraction_occurrences_over_1a":
                (round(b_n / a_n, 4) if a_n else None),
        }

    # validation: filled POIs' product direction vs completion directions
    dir_match = 0
    dir_check = 0
    by_poi_comps: dict[str, list[dict]] = defaultdict(list)
    for c in all_completions:
        by_poi_comps[c["poi_id"]].append(c)
    for t in fills_all:
        comps = by_poi_comps.get(t["poi_id"], [])
        if not comps:
            continue
        dir_check += 1
        if any(c["direction"] == (t.get("direction") or "").lower()
               for c in comps):
            dir_match += 1

    summary = {
        "tag": "scan1b_ltf_with_poi",
        "diagnostic_only": True,
        "window": {"exec": "2024-11-01 -> 2025-10-31", "load_from": "2024-09-01",
                   "segments": 12, "mode": "segmented (product_1y tiling)"},
        "layer": "1B product-linked (armed POI universe, real zone bounds)",
        "m1_scan": 0,
        "m1_scan_reason": ("trigger code never reads a timeframe; the menu "
                           "confirmation TF varies by tier (M1/M5/H1) — an "
                           "M1 scan is out of this engagement's M5-primary "
                           "convention and would double-count windows"),
        "armed_universe": {"total": armed_total,
                           "winners_menu": winners_total,
                           "submitted": submitted_total,
                           "placed": placed_total,
                           "fills": len(fills_all)},
        "lifecycle_buckets": {
            "FILLED": bucket_total.get("FILLED", 0),
            "ROUTED_NOT_FILLED_aggregate_only": placed_total - len(fills_all)
            + (submitted_total - placed_total),
            "ROUTED_NOT_FILLED_note": ("submitted-unplaced + placed-unfilled; "
                                       "per-POI placed flags not exported"),
            "COMPLETED_NOT_ROUTED": bucket_total.get("COMPLETED_NOT_ROUTED", 0),
            "ARMED_NO_COMPLETION": bucket_total.get("ARMED_NO_COMPLETION", 0),
            "OPEN_SCAN_ROUTED_nonexclusive": winners_total,
            "mapping": ("routed=true in armed_records == filled POI set "
                        "(verified per segment, FAIL LOUD on mismatch); "
                        "winners = guard-dropped + submitted-unplaced + "
                        "placed-unfilled + filled (865 = 580+33+13+239)"),
        },
        "by_trigger_1b": b_by_trigger,
        "unique_geometry_1b": {
            "total_unique": len(b_unique_geo),
            "occurrences_by_trigger_direction": {
                f"{t}|{d}": n for (t, d), n in sorted(Counter(
                    (c["trigger"], c["direction"])
                    for c in all_completions).items())},
            "note": ("occurrences are NOT deduped; unique = distinct "
                     "(trigger, direction, signal.data) geometry keys"),
        },
        "crosstab_1a_vs_1b": xtab,
        "filled_direction_validation": {
            "filled_pois_with_completions": dir_check,
            "product_direction_among_completion_directions": dir_match,
        },
        "per_segment": per_segment,
        "fill_trigger_mix_reconciled": fill_mix,
        "runtime_seconds": round(time.perf_counter() - t0, 1),
    }
    filled_keys = {(t["_segment"], t["poi_id"]) for t in fills_all}

    # ---- charts (<= 24 panels, three groups) ------------------------------- #
    chart_index = render_charts(all_completions, filled_keys,
                                set(b_unique_geo))
    summary["chart_index"] = chart_index
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")

    cols = ["poi_id", "segment", "trigger", "direction", "bar",
            "bar_time_utc", "data"]
    with (OUT / "events_scan1b_completions.csv").open(
            "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for c in all_completions:
            w.writerow({k: c.get(k, "") for k in cols})

    print(f"[scan1b] armed {armed_total} | completions {len(all_completions)} "
          f"| buckets {dict(bucket_total)} | fills mix {fill_mix}", flush=True)
    print(f"[scan1b] wrote {OUT / 'summary.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
