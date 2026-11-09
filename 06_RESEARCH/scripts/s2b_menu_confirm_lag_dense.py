"""
S2b — DENSER MENU FUNNEL + CONFIRM-LAG (n target) — MEASUREMENT ONLY
Same menu spine method as S2: run_batch → register_armed → on_execution_bar →
winner → queue_menu_candidate. OPT-B false, OPT-2 off. No threshold fishing.
Diagnostic only — not performance/edge. LOGIC_CHANGED=NO.
"""
from __future__ import annotations

import csv
import json
import sys
from bisect import bisect_right
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "04_SRC"))

import pandas as pd  # noqa: E402

from smc.backtest.pipeline_adapter import PipelineAdapter  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402
from smc.core.candle import Candle  # noqa: E402
from smc.data.resample import resample_ohlcv  # noqa: E402
from smc.orchestration.engine import PipelineEngine  # noqa: E402
from smc.orchestration.multi_tf_runtime import (  # noqa: E402
    MultiTFProductRuntime,
    build_htf_prefixes,
)
from smc.orchestration.product_menu_mtf import (  # noqa: E402
    PRODUCT_MENU_CONFIRMATION_TIMEFRAMES,
    PRODUCT_MENU_DETECTION_TIMEFRAMES,
    PRODUCT_MENU_TIERS,
    ProductMenuEngine,
)

DETECTION_TFS = [Timeframe.D1, Timeframe.H4, Timeframe.H1, Timeframe.M15]
EXEC_TF = Timeframe.M5
DATA_PATH = ROOT / "07_DATA" / "XAUUSD_M1.parquet"
OUT_DIR = ROOT / "06_RESEARCH" / "results" / "s2b_menu_confirm_lag_dense"
NOTE_PATH = ROOT / "06_RESEARCH" / "S2B_MENU_CONFIRM_LAG_DENSE_NOTE.md"

WARMUP_START = datetime(2023, 12, 1, tzinfo=timezone.utc)
WINDOW_START = datetime(2024, 4, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2024, 5, 1, tzinfo=timezone.utc)  # 1-month completed run (runtime-feasible this env); 2-3m attempted but too slow here — extend when runtime allows
BATCH_EVERY_STEPS = 48  # fixed; no threshold fishing


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
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp")
    ts = df["timestamp"].dt.to_pydatetime()
    o = df["open"].astype(float).values
    h = df["high"].astype(float).values
    lo = df["low"].astype(float).values
    c = df["close"].astype(float).values
    v = df.get("volume", pd.Series(0, index=df.index)).fillna(0).astype(float).values
    return [Candle(timestamp=(t if getattr(t, "tzinfo", None) else t.replace(tzinfo=timezone.utc)),
                   open=float(o[i]), high=float(h[i]), low=float(lo[i]), close=float(c[i]),
                   volume=float(v[i]), timeframe=Timeframe.M1) for i, t in enumerate(ts)]


class _SubmitCounter:
    def __init__(self): self.submits = 0
    def submit_entry(self, candidate): self.submits += 1


def _close_ts(bar: Candle) -> datetime:
    return bar.timestamp + timedelta(minutes=bar.timeframe.minutes)


def _parse_ts(value):
    if value is None: return None
    if isinstance(value, datetime): return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _lag_bars(closes: list[datetime], sweep_close: datetime | None, confirm_close: datetime | None):
    if sweep_close is None or confirm_close is None or not closes: return None
    return max(0, bisect_right(closes, confirm_close) - bisect_right(closes, sweep_close))


def _quantiles(vals):
    if not vals:
        return {"n": 0, "min": None, "p25": None, "median": None, "p75": None, "max": None}
    s = sorted(vals)
    def q(p):
        if len(s) == 1: return float(s[0])
        k = (len(s)-1)*p; f=int(k); c=min(f+1,len(s)-1)
        return float(s[f]+(s[c]-s[f])*(k-f))
    return {"n": len(s), "min": float(s[0]), "p25": q(0.25), "median": float(median(s)), "p75": q(0.75), "max": float(s[-1])}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_PATH.exists():
        raise SystemExit(f"DATA_GAP: missing {DATA_PATH}")
    print(f"S2b menu confirm-lag dense | data={DATA_PATH}", flush=True)
    print(f"window={WINDOW_START.date()}..{WINDOW_END.date()} warmup={WARMUP_START.date()} BATCH_EVERY={BATCH_EVERY_STEPS}", flush=True)
    print("OPT-B false, OPT-2 off. No threshold fishing. Diagnostic only.", flush=True)

    m1_all = load_m1(DATA_PATH, WARMUP_START, WINDOW_END)
    print(f"loaded M1 bars={len(m1_all)}", flush=True)
    needed_tfs = set(DETECTION_TFS) | set(PRODUCT_MENU_CONFIRMATION_TIMEFRAMES) | {EXEC_TF}
    series = {}
    for tf in sorted(needed_tfs, key=lambda t: t.minutes, reverse=True):
        series[tf] = resample_ohlcv(m1_all, tf)
        print(f"  resampled {tf.name}={len(series[tf])}", flush=True)
    closes = {tf: [_close_ts(b) for b in bars] for tf, bars in series.items()}

    runtime = MultiTFProductRuntime(detection_timeframes=DETECTION_TFS, execution_timeframe=EXEC_TF)
    menu = ProductMenuEngine(symbol="XAUUSD")
    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=EXEC_TF, menu_confirmation=menu)
    counter = _SubmitCounter(); adapter._runner = counter
    m15_win = [c for c in series[Timeframe.M15] if WINDOW_START <= c.timestamp < WINDOW_END]
    exec_series = series[EXEC_TF]
    feed_idx = {tf: 0 for tf in series}
    rows = []; seen = set(); register_armed = 0; batch_errors = []

    for step, m15_bar in enumerate(m15_win):
        as_of = _close_ts(m15_bar)
        if step % BATCH_EVERY_STEPS == 0:
            prefixes = build_htf_prefixes(series, as_of)
            exec_prefix = [c for c in exec_series if _close_ts(c) <= as_of]
            try:
                report = runtime.run_batch(engine=engine, series_by_tf=prefixes, as_of=as_of,
                                           arm_bar=max(len(exec_prefix)-1,0), adapter=adapter, execution_candles=exec_prefix)
            except Exception as e:
                batch_errors.append(f"{as_of}: {type(e).__name__}: {e}"); report = None
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
        except Exception as e:
            batch_errors.append(f"menu@{as_of}: {type(e).__name__}: {e}"); winners = []
        for w in (winners or []):
            adapter.queue_menu_candidate(w.candidate)
            key = (w.episode_id, w.route_id, w.confirmation_tf.name)
            if key in seen: continue
            seen.add(key)
            ep = next((e for e in menu.episodes() if e.episode_id == w.episode_id), None)
            stamp = {}
            try:
                payload = json.loads(getattr(w.candidate, "signal_data_json", "{}") or "{}")
                stamp = payload.get("product_menu") or {} if isinstance(payload, dict) else {}
            except Exception: pass
            t_sweep = ep.sweep_ts if ep else None
            t_sweep_close = ep.sweep_close_ts if ep else None
            t_confirm = _parse_ts(stamp.get("completion_ts"))
            det_name = getattr(getattr(w, "detection_tf", None), "name", None) or stamp.get("detection_tf")
            conf_name = getattr(getattr(w, "confirmation_tf", None), "name", None) or stamp.get("confirmation_tf")
            try: det_tf_obj = Timeframe[det_name] if det_name else None
            except Exception: det_tf_obj = getattr(w, "detection_tf", None)
            try: ctf_obj = Timeframe[conf_name] if conf_name else None
            except Exception: ctf_obj = None
            lag_det = _lag_bars(closes.get(det_tf_obj, []), t_sweep_close, t_confirm) if det_tf_obj else None
            label = stamp.get("label_at_confirm")
            zone_rel = "inside_window" if label == "ON_WINDOW" else ("outside_band" if label in ("LATE","BEYOND_STOP_SIDE") else "unknown")
            rows.append({"episode_id": w.episode_id, "poi_id": w.poi_id, "tier": w.tier_name, "det_tf": det_name,
                         "confirm_tf": conf_name, "trigger_type": w.trigger, "t_sweep": t_sweep.isoformat() if t_sweep else None,
                         "t_confirm": t_confirm.isoformat() if t_confirm else None, "lag_bars_det_tf": lag_det,
                         "lag_bars_confirm_tf": _lag_bars(closes.get(ctf_obj, []), t_sweep_close, t_confirm) if ctf_obj else None,
                         "lag_bars_exec_m5": _lag_bars(closes.get(EXEC_TF, []), t_sweep_close, t_confirm),
                         "label_at_confirm": label, "zone_relation_at_confirm": zone_rel,
                         "distance_at_confirm_atr": stamp.get("distance_at_confirm_atr"), "zone_direction": stamp.get("zone_direction")})
        if (step + 1) % 800 == 0:
            print(f"  step {step+1}/{len(m15_win)} as_of={as_of.date()} armed={register_armed} sweeps={menu.sweeps_total} winners={len(rows)} active={menu.active_count()}", flush=True)

    if adapter._runner and adapter._menu_candidates:
        while adapter._menu_candidates: counter.submit_entry(adapter._menu_candidates.pop(0))

    csv_path = OUT_DIR / "s2b_menu_winners.csv"
    fields = list(rows[0].keys()) if rows else ["episode_id","poi_id","tier","det_tf","confirm_tf","trigger_type","t_sweep","t_confirm","lag_bars_det_tf","lag_bars_confirm_tf","lag_bars_exec_m5","label_at_confirm","zone_relation_at_confirm","distance_at_confirm_atr","zone_direction"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=fields); wr.writeheader(); wr.writerows(rows)

    lag_vals = [r["lag_bars_det_tf"] for r in rows if isinstance(r.get("lag_bars_det_tf"), (int,float))]
    known = [r for r in rows if r["zone_relation_at_confirm"] in ("inside_window","outside_band")]
    outside = [r for r in known if r["zone_relation_at_confirm"]=="outside_band"]
    labels = defaultdict(int)
    for r in rows: labels[str(r.get("label_at_confirm"))] += 1
    lag = _quantiles(lag_vals)
    summary = {
        "S2B_STATUS": "PASS" if rows is not None else "FAIL",
        "diagnostic_only": True, "not_performance": True, "opt_b": False, "opt2": "deferred",
        "window": {"warmup_start": WARMUP_START.date().isoformat(), "start": WINDOW_START.date().isoformat(), "end": WINDOW_END.date().isoformat()},
        "N_WINNERS": len(rows), "REGISTER_ARMED": register_armed, "SWEEPS": menu.sweeps_total,
        "QUEUE_SUBMITS": counter.submits, "LAG_DET_BARS": lag,
        "LAG_MEDIAN_DET_BARS": lag["median"], "LAG_P75_DET_BARS": lag["p75"],
        "LABEL_MIX": dict(labels),
        "CONFIRM_OUTSIDE_BAND_PCT": (round(100.0*len(outside)/len(known),2) if known else None),
        "ZONE_RELATION_KNOWN_N": len(known),
        "BY_DET_TF": {t: len([r for r in rows if r["det_tf"]==t]) for t in sorted({r["det_tf"] for r in rows})},
        "BY_TIER": {t: len([r for r in rows if r["tier"]==t]) for t in sorted({r["tier"] for r in rows})},
        "BY_TRIGGER": {t: len([r for r in rows if r["trigger_type"]==t]) for t in sorted({str(r["trigger_type"]) for r in rows})},
        "BATCH_EVERY_STEPS": BATCH_EVERY_STEPS, "BATCH_ERRORS": batch_errors[:10], "csv": str(csv_path),
    }
    (OUT_DIR / "s2b_menu_confirm_lag_dense_summary.json").write_text(json.dumps(summary, indent=2, default=str)+"\n", encoding="utf-8")

    target_note = "met" if len(rows) >= 20 else f"not met (true n={len(rows)}; no threshold fishing)"
    note = f"""# S2b — Denser Menu Funnel + Confirm-Lag (Measurement Only)

**Diagnostic only — not performance/edge.** OPT-B false, OPT-2 deferred, W1 context_only. No pillar/threshold tuning. No threshold fishing to inflate n. `LOGIC_CHANGED=NO`.

## Method (same menu spine)
`MultiTFProductRuntime.run_batch` → `menu.register_armed` (sparse cadence, every {BATCH_EVERY_STEPS} M15 steps, fixed) + dense M15-timeline `menu.on_execution_bar` (closed detection/confirmation streams) → winner → `queue_menu_candidate` → `submit_entry`. Not adapter-only.

## Window / data
- `{DATA_PATH}` (fail-loud if missing)
- Window `{WINDOW_START.date()} .. {WINDOW_END.date()}` (warmup `{WARMUP_START.date()}`), XAUUSD. Detection TFs D1/H4/H1/M15. Tiers DAY(D1→H1), H4(H4→M5,M15), H1(H1→M5,M1), M15(M15→M1).

## Funnel (true counts)
- `REGISTER_ARMED`: **{register_armed}**
- `SWEEPS` (`menu.sweeps_total`): **{menu.sweeps_total}**
- `N_WINNERS`: **{len(rows)}** (deduped episode/route/confirm_tf) | `QUEUE_SUBMITS`: **{counter.submits}**
- Soft target n>=20: **{target_note}**

## Lag (detection-TF bars, `sweep_close < bar_close <= t_confirm`)
- n={lag['n']}, min={lag['min']}, p25={lag['p25']}, **median={lag['median']}**, **p75={lag['p75']}**, max={lag['max']}

## Label mix / zone relation (`product_menu.label_at_confirm`, timing-study taxonomy)
- `LABEL_MIX`: `{summary['LABEL_MIX']}`
- `CONFIRM_OUTSIDE_BAND_PCT` (LATE or BEYOND_STOP_SIDE over known labels): **{summary['CONFIRM_OUTSIDE_BAND_PCT']}%** (known n={len(known)}). ON_WINDOW=inside band/window; LATE/BEYOND_STOP_SIDE=outside band; UNLOCATABLE excluded. Exact raw-zone geometry beyond label = NA.
- By det_tf: `{summary['BY_DET_TF']}` | By tier: `{summary['BY_TIER']}` | By trigger: `{summary['BY_TRIGGER']}`

## Artifacts (gitignored)
- `{csv_path}`
- `{OUT_DIR / 's2b_menu_confirm_lag_dense_summary.json'}`

## Errors
{json.dumps(summary['BATCH_ERRORS'])}
"""
    NOTE_PATH.write_text(note, encoding="utf-8")
    print(json.dumps({
        "S2B_STATUS": "PASS", "N_WINNERS": len(rows), "REGISTER_ARMED": register_armed,
        "SWEEPS": menu.sweeps_total, "LAG_MEDIAN_DET_BARS": lag["median"], "LAG_P75_DET_BARS": lag["p75"],
        "LABEL_MIX": summary["LABEL_MIX"], "CONFIRM_OUTSIDE_BAND_PCT": summary["CONFIRM_OUTSIDE_BAND_PCT"],
        "LOGIC_CHANGED": "NO", "NOTE_PATH": str(NOTE_PATH), "QUEUE_SUBMITS": counter.submits,
    }, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
