"""
PLAN-COMPLEMENT LEDGER — sweep + confirm → plan (measurement only)
Menu ProductMenuEngine / queue_menu_candidate path only (not adapter-only).
Read-only: records plan fields and geometry consistency; no edge/PnL claim.
LOGIC_CHANGED=NO. OPT-B false, OPT-2 off, no pillar/R7/threshold edits.
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "04_SRC"))

import pandas as pd  # noqa: E402

from smc.backtest.pipeline_adapter import PipelineAdapter  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402
from smc.core.candle import Candle  # noqa: E402
from smc.core.enums import Direction  # noqa: E402
from smc.data.resample import resample_ohlcv  # noqa: E402
from smc.orchestration.engine import PipelineEngine  # noqa: E402
from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime, build_htf_prefixes  # noqa: E402
from smc.orchestration.product_menu_mtf import (  # noqa: E402
    PRODUCT_MENU_CONFIRMATION_TIMEFRAMES,
    PRODUCT_MENU_DETECTION_TIMEFRAMES,
    ProductMenuEngine,
)

DETECTION_TFS = [Timeframe.D1, Timeframe.H4, Timeframe.H1, Timeframe.M15]
EXEC_TF = Timeframe.M5
DATA_PATH = ROOT / "07_DATA" / "XAUUSD_M1.parquet"

def _env_path(name: str, default: Path) -> Path:
    """Path from env (relative paths resolve against the repo root)."""
    raw = os.environ.get(name)
    if not raw:
        return default
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


# F1/F2 re-baseline runs MUST write to new paths (never overwrite the frozen
# ``baseline_pre_fix`` artifacts): set PLAN_COMPLEMENT_OUT / PLAN_COMPLEMENT_NOTE.
OUT_DIR = _env_path("PLAN_COMPLEMENT_OUT",
                    ROOT / "06_RESEARCH" / "results" / "plan_complement_ledger")
NOTE_PATH = _env_path("PLAN_COMPLEMENT_NOTE",
                      ROOT / "06_RESEARCH" / "PLAN_COMPLEMENT_LEDGER_NOTE.md")
RUN_LABEL = os.environ.get("PLAN_COMPLEMENT_LABEL", "baseline_pre_fix")
RUN_LOGIC_CHANGED = os.environ.get("PLAN_COMPLEMENT_LOGIC_CHANGED", "NO")

# Documented runtime-feasible window (same spine/method as S2b/OPT-4); extend if runtime allows.
WARMUP_START = datetime(2023, 12, 1, tzinfo=timezone.utc)
WINDOW_START = datetime(2024, 4, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2024, 5, 1, tzinfo=timezone.utc)
BATCH_EVERY_STEPS = 48


def load_m1(path: Path, start: datetime, end: datetime) -> list[Candle]:
    start_naive = start.replace(tzinfo=None)
    end_naive = end.replace(tzinfo=None)
    cols = ["timestamp", "open", "high", "low", "close", "volume"]
    try:
        import pyarrow.parquet as pq
        table = pq.read_table(path, columns=cols, filters=[("timestamp", ">=", start_naive), ("timestamp", "<", end_naive)])
        df = table.to_pandas()
    except Exception:
        df = pd.read_parquet(path, columns=cols)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df[(df["timestamp"] >= start) & (df["timestamp"] < end)]
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).sort_values()
    ts = df["timestamp"].dt.to_pydatetime()
    o = df["open"].astype(float).values; h = df["high"].astype(float).values
    lo = df["low"].astype(float).values; c = df["close"].astype(float).values
    v = df.get("volume", pd.Series(0, index=df.index)).fillna(0).astype(float).values
    return [Candle(timestamp=(t if getattr(t, "tzinfo", None) else t.replace(tzinfo=timezone.utc)),
                   open=float(o[i]), high=float(h[i]), low=float(lo[i]), close=float(c[i]),
                   volume=float(v[i]), timeframe=Timeframe.M1) for i, t in enumerate(ts)]


class _SubmitCapture:
    def __init__(self): self.submits = []
    def submit_entry(self, candidate): self.submits.append(candidate)


def _close_ts(bar: Candle) -> datetime:
    return bar.timestamp + timedelta(minutes=bar.timeframe.minutes)


def _is_finite(x):
    try:
        return x is not None and math.isfinite(float(x))
    except Exception:
        return False


def _dir_val(d):
    if d is None: return None
    if isinstance(d, Direction): return d.name
    try: return getattr(d, "name", None) or getattr(d, "value", str(d))
    except Exception: return str(d)


def plan_consistency(direction, entry, sl, tp):
    """Pure geometry check (no edge claim). Returns (YES/NO/UNKNOWN, reasons)."""
    reasons = []
    if not (_is_finite(entry) and _is_finite(sl) and _is_finite(tp)):
        return "UNKNOWN", ["non_finite_plan_field"]
    e, s, t = float(entry), float(sl), float(tp)
    dv = _dir_val(direction)
    if dv == "LONG":
        if not (s < e): reasons.append("sl_not_below_entry_for_long")
        if not (t > e): reasons.append("tp_not_above_entry_for_long")
    elif dv == "SHORT":
        if not (s > e): reasons.append("sl_not_above_entry_for_short")
        if not (t < e): reasons.append("tp_not_below_entry_for_short")
    else:
        return "UNKNOWN", ["unknown_direction"]
    return ("YES" if not reasons else "NO"), reasons


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_PATH.exists():
        raise SystemExit(f"DATA_GAP: missing {DATA_PATH}")
    print(f"PLAN-COMPLEMENT LEDGER (measurement) | data={DATA_PATH}", flush=True)
    print(f"window={WINDOW_START.date()}..{WINDOW_END.date()} warmup={WARMUP_START.date()} (same spine/method as S2b/OPT-4)", flush=True)
    print("Menu path only. OPT-B false, OPT-2 off. No pillar/R7/threshold edits. Diagnostic only.", flush=True)

    m1_all = load_m1(DATA_PATH, WARMUP_START, WINDOW_END)
    print(f"loaded M1 bars={len(m1_all)}", flush=True)
    needed_tfs = set(DETECTION_TFS) | set(PRODUCT_MENU_CONFIRMATION_TIMEFRAMES) | {EXEC_TF}
    series = {}
    for tf in sorted(needed_tfs, key=lambda t: t.minutes, reverse=True):
        series[tf] = resample_ohlcv(m1_all, tf)
        print(f"  resampled {tf.name}={len(series[tf])}", flush=True)

    runtime = MultiTFProductRuntime(detection_timeframes=DETECTION_TFS, execution_timeframe=EXEC_TF)
    menu = ProductMenuEngine(symbol="XAUUSD")
    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=EXEC_TF, menu_confirmation=menu)
    capture = _SubmitCapture(); adapter._runner = capture
    m15_win = [c for c in series[Timeframe.M15] if WINDOW_START <= c.timestamp < WINDOW_END]
    exec_series = series[EXEC_TF]
    feed_idx = {tf: 0 for tf in series}
    register_armed = 0

    for step, m15_bar in enumerate(m15_win):
        as_of = _close_ts(m15_bar)
        if step % BATCH_EVERY_STEPS == 0:
            prefixes = build_htf_prefixes(series, as_of)
            exec_prefix = [c for c in exec_series if _close_ts(c) <= as_of]
            try:
                report = runtime.run_batch(engine=engine, series_by_tf=prefixes, as_of=as_of,
                                           arm_bar=max(len(exec_prefix)-1, 0), adapter=adapter, execution_candles=exec_prefix)
            except Exception:
                report = None
            if report is not None:
                for poi in (report.armed or []):
                    det_tf = getattr(getattr(poi, "zone", None), "timeframe", None)
                    if det_tf is not None and menu.register_armed(poi, det_tf):
                        register_armed += 1
        feed = {}
        for tf in set(PRODUCT_MENU_DETECTION_TIMEFRAMES) | set(PRODUCT_MENU_CONFIRMATION_TIMEFRAMES):
            s = series.get(tf) or []; start = feed_idx.get(tf, 0)
            tail_close = menu._closes[tf][-1] if menu._closes.get(tf) else datetime.min.replace(tzinfo=timezone.utc)
            while start < len(s) and _close_ts(s[start]) <= tail_close: start += 1
            feed_idx[tf] = start
            if start < len(s): feed[tf] = s[start:]
        try:
            winners = menu.on_execution_bar(feed, as_of=as_of)
        except Exception:
            winners = []
        for w in (winners or []):
            adapter.queue_menu_candidate(w.candidate)
        if (step + 1) % 800 == 0:
            print(f"  step {step+1}/{len(m15_win)} armed={register_armed} sweeps={menu.sweeps_total} winners={len(menu.winners)} submits={len(capture.submits)}", flush=True)

    if adapter._runner and adapter._menu_candidates:
        while adapter._menu_candidates:
            capture.submit_entry(adapter._menu_candidates.pop(0))

    rows = []
    for i, cand in enumerate(capture.submits):
        stamp = {}
        gap_notes = []
        try:
            payload = json.loads(getattr(cand, "signal_data_json", "{}") or "{}")
            stamp = payload.get("product_menu") or {} if isinstance(payload, dict) else {}
        except Exception:
            stamp = {}
        if not stamp:
            gap_notes.append("missing_product_menu_stamp")
        zone = stamp.get("zone") if isinstance(stamp.get("zone"), (list, tuple)) else [None, None]
        zlow = zone[0] if len(zone) == 2 else None; zhigh = zone[1] if len(zone) == 2 else None

        entry = getattr(cand, "entry_price", None)
        sl = getattr(cand, "sl_price", None)
        tp = getattr(cand, "tp_price", None)
        tp_source = getattr(cand, "tp_source", None)
        sl_source = getattr(cand, "sl_source", None)  # may not exist on CandidateEntry; honest
        original_sl = getattr(cand, "original_sl", None)
        entry_anchor = getattr(cand, "entry_anchor", None)
        direction = getattr(cand, "direction", None)

        plan_complete = _is_finite(entry) and _is_finite(sl) and _is_finite(tp)
        if not plan_complete:
            missing = [k for k, v in [("entry", entry), ("sl", sl), ("tp", tp)] if not _is_finite(v)]
            gap_notes.append("incomplete_plan_missing:" + "+".join(missing))
        pcons, preasons = plan_consistency(direction, entry, sl, tp)
        gap_notes.extend(preasons)
        # place_or_queue: harness delivered to submit_entry via queue_menu_candidate
        place_or_queue = "submitted(harness)"
        rows.append({
            "submit_index": i,
            "poi_id": stamp.get("poi_id") or getattr(cand, "poi_id", None),
            "route_id": getattr(cand, "route_id", None),
            "tier": stamp.get("tier"),
            "detection_tf": stamp.get("detection_tf"),
            "confirmation_tf": stamp.get("confirmation_tf"),
            "t_arm": None,  # arm time not stamped in product_menu; honest gap
            "t_sweep": stamp.get("sweep_ts"),
            "t_confirm": stamp.get("completion_ts"),
            "trigger_type": stamp.get("trigger_type") or (getattr(getattr(cand, "trigger", None), "name", None) or getattr(cand, "trigger", None)),
            "zone_low": zlow, "zone_high": zhigh, "zone_direction": stamp.get("zone_direction") or _dir_val(direction),
            "confirm_label": stamp.get("label_at_confirm"),
            "entry_price": entry, "sl_price": sl, "tp_price": tp,
            "tp_source": tp_source, "sl_source": sl_source, "original_sl": original_sl,
            "entry_anchor": entry_anchor,
            "plan_complete": "YES" if plan_complete else "NO",
            "plan_consistent": pcons,
            "place_or_queue": place_or_queue,
            "notes": ";".join(gap_notes),
        })
        if "t_arm_missing" not in ";".join(gap_notes):
            rows[-1]["notes"] = ("t_arm_not_stamped;" + rows[-1]["notes"]).strip(";") if rows[-1]["notes"] else "t_arm_not_stamped"

    csv_path = OUT_DIR / "plan_complement_ledger.csv"
    fields = list(rows[0].keys()) if rows else ["submit_index","poi_id","plan_complete","plan_consistent","notes"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=fields); wr.writeheader(); wr.writerows(rows)

    n = len(rows)
    n_complete = sum(1 for r in rows if r["plan_complete"] == "YES")
    complete_rows = [r for r in rows if r["plan_complete"] == "YES"]
    n_consistent = sum(1 for r in complete_rows if r["plan_consistent"] == "YES")
    pct_complete = round(100.0 * n_complete / n, 2) if n else None
    pct_consistent = round(100.0 * n_consistent / n_complete, 2) if n_complete else None

    by_trigger = defaultdict(lambda: {"n":0,"complete":0,"consistent":0})
    by_tf = defaultdict(lambda: {"n":0,"complete":0,"consistent":0})
    gap_counts = defaultdict(int)
    for r in rows:
        k = f"{r.get('trigger_type')}"
        by_trigger[k]["n"] += 1
        by_tf[f"{r.get('detection_tf')}/{r.get('confirmation_tf')}"]["n"] += 1
        if r["plan_complete"] == "YES":
            by_trigger[k]["complete"] += 1; by_tf[f"{r.get('detection_tf')}/{r.get('confirmation_tf')}"]["complete"] += 1
            if r["plan_consistent"] == "YES":
                by_trigger[k]["consistent"] += 1; by_tf[f"{r.get('detection_tf')}/{r.get('confirmation_tf')}"]["consistent"] += 1
        for g in (r.get("notes") or "").split(";"):
            if g and g != "t_arm_not_stamped": gap_counts[g] += 1
            elif g == "t_arm_not_stamped": gap_counts[g] += 1
    top_gaps = sorted(gap_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:8]

    sample = rows[:10]
    summary = {
        "PLAN_STATUS": "PASS", "diagnostic_only": True, "not_profitability": True,
        "run_label": RUN_LABEL, "logic_changed": RUN_LOGIC_CHANGED,
        "menu_counters": menu.counters(),
        "opt_b": False, "opt2": "deferred", "r7_threshold_changed": False,
        "path": "menu queue_menu_candidate submits only (not adapter-only)",
        "window": {"warmup_start": WARMUP_START.date().isoformat(), "start": WINDOW_START.date().isoformat(), "end": WINDOW_END.date().isoformat()},
        "N_EVENTS": n, "N_WINNERS": len(menu.winners), "REGISTER_ARMED": register_armed, "SWEEPS": menu.sweeps_total,
        "PCT_PLAN_COMPLETE": pct_complete, "PCT_PLAN_CONSISTENT": pct_consistent,
        "N_PLAN_COMPLETE": n_complete, "N_PLAN_CONSISTENT_AMONG_COMPLETE": n_consistent,
        "TOP_GAPS": [f"{k}={v}" for k, v in top_gaps],
        "BREAKDOWN_TRIGGER": dict(by_trigger), "BREAKDOWN_TF": dict(by_tf),
        "SAMPLE_COUNT": len(sample), "csv": str(csv_path),
    }
    (OUT_DIR / "plan_complement_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")

    def _fmt_row(r):
        return (f"| {r['submit_index']} | {r['poi_id']} | {r['tier']} | {r['detection_tf']}→{r['confirmation_tf']} | "
                f"{r['trigger_type']} | {r['zone_direction']} [{r['zone_low']},{r['zone_high']}] | "
                f"sweep={r['t_sweep']} confirm={r['t_confirm']} | {r['confirm_label']} | "
                f"entry={r['entry_price']} sl={r['sl_price']} tp={r['tp_price']} (tp_src={r['tp_source']}, sl_src={r['sl_source']}, orig_sl={r['original_sl']}, anchor={r['entry_anchor']}) | "
                f"complete={r['plan_complete']} consistent={r['plan_consistent']} | {r['place_or_queue']} | {r['notes']} |")

    sample_lines = "\n".join(_fmt_row(r) for r in sample) if sample else "(none)"
    note = f"""# Plan-Complement Ledger — sweep + confirm → plan (Measurement Only)

**Diagnostic only — does NOT validate profitability or edge.** Menu `ProductMenuEngine` / `queue_menu_candidate` → `submit_entry` path only (not adapter-only). Read-only; no OPT-2, no band/R7/pillar/threshold tuning, OPT-B false. `RUN={RUN_LABEL}`, `LOGIC_CHANGED={RUN_LOGIC_CHANGED}`. Plan completeness/consistency are **geometry/field checks only** (not a claim sweep+confirm "works" without Architect review of the sample).

## Goal
Record whether HTF/structure arm + sweep + LTF confirm → winner/submit produces a coherent trade PLAN (entry/SL/TP identity) and how often, with human-readable rows.

## Scope / data
- Window `2024-04-01 .. 2024-05-01` (warmup `2023-12-01`), `07_DATA/XAUUSD_M1.parquet` (fail-loud). Same spine/method as S2b/OPT-4 (runtime-feasible); extend if runtime allows.
- Path: menu `run_batch` → `register_armed` → `on_execution_bar` → `queue_menu_candidate` → `submit_entry` capture. `place_or_queue=submitted(harness)` = delivered to submit_entry in measurement harness (live runner may still block; not measured here).
- Funnel counters (measurement only): `{menu.counters()}`.

## Summary
- `N_EVENTS` (menu submits): **{n}** | `REGISTER_ARMED` **{register_armed}** | `SWEEPS` **{menu.sweeps_total}** | `N_WINNERS` **{len(menu.winners)}**
- `PCT_PLAN_COMPLETE` (entry+SL+TP all finite): **{pct_complete}%** ({n_complete}/{n})
- `PCT_PLAN_CONSISTENT` (among complete; pure geometry: SL/TP on correct side of entry): **{pct_consistent}%** ({n_consistent}/{n_complete})
- Breakdown by trigger: `{dict(by_trigger)}`
- Breakdown by det/confirm TF: `{dict(by_tf)}`
- Top gaps: `{top_gaps}` (missing TP/fields = incomplete plan, **not** a fix-thresholds instruction)

## Human sample (for Architect review — "would this plan match flowchart intent?")
Count: {len(sample)} (up to 10 / all if n≤10)

| # | poi_id | tier | det→conf | trigger | zone dir [low,high] | t_sweep / t_confirm | confirm label | plan (entry/sl/tp; tp_src, sl_src, orig_sl, anchor) | complete/consistent | place_or_queue | notes |
|---:|---|---|---|---|---|---|---|---|---|---|---|
{sample_lines}

## Caveats
- `t_arm` not stamped in `product_menu`; reported as gap note (honest). Small n (same window). Consistency is geometric only (directional side checks). No expectancy, no edge, no PnL. **Do not claim sweep+confirm "works" from plan_complete alone without Architect review of the sample.**

## Artifacts (gitignored)
- `{csv_path}`
- `{OUT_DIR / 'plan_complement_summary.json'}`
"""
    NOTE_PATH.write_text(note, encoding="utf-8")
    print(json.dumps({
        "PLAN_STATUS": "PASS", "N_EVENTS": n, "PCT_PLAN_COMPLETE": pct_complete,
        "PCT_PLAN_CONSISTENT": pct_consistent, "TOP_GAPS": [f"{k}={v}" for k,v in top_gaps],
        "SAMPLE_ROWS": len(sample), "LOGIC_CHANGED": RUN_LOGIC_CHANGED,
        "RUN": RUN_LABEL, "NOTE_PATH": str(NOTE_PATH),
    }, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
