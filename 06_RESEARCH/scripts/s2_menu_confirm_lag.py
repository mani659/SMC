"""
S2 — MENU CONFIRM-LAG (MEASUREMENT ONLY)
========================================
Drives the MENU spine (register_armed -> sweep -> on_execution_bar -> winner -> queue)
on a documented window and measures confirm timing/lag per MENU WINNER.

Diagnostic only — not performance/edge. No OPT-2. OPT-B false. No pillar/threshold tuning.
LOGIC_CHANGED: NO (research script; no core strategy changes).
"""
from __future__ import annotations

import csv
import json
import sys
from bisect import bisect_left, bisect_right
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
OUT_DIR = ROOT / "06_RESEARCH" / "results" / "s2_menu_confirm_lag"
NOTE_PATH = ROOT / "06_RESEARCH" / "S2_MENU_CONFIRM_LAG_NOTE.md"

# Documented window (measurement slice aligned to confirm-smoke winner region;
# shortened for runnable S2 measurement in this environment; method identical).
WARMUP_START = datetime(2023, 12, 1, tzinfo=timezone.utc)
WINDOW_START = datetime(2024, 4, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2024, 4, 15, tzinfo=timezone.utc)  # covers first proven winners
BATCH_EVERY_STEPS = 48  # sparse arm cadence; menu stream feed remains dense


def load_m1(path: Path, start: datetime, end: datetime) -> list[Candle]:
    start_naive = start.replace(tzinfo=None)
    end_naive = end.replace(tzinfo=None)
    try:
        import pyarrow.parquet as pq
        table = pq.read_table(
            path,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
            filters=[("timestamp", ">=", start_naive), ("timestamp", "<", end_naive)],
        )
        df = table.to_pandas()
    except Exception:
        df = pd.read_parquet(path, columns=["timestamp", "open", "high", "low", "close", "volume"])
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
    return [
        Candle(
            timestamp=(t if t.tzinfo else t.replace(tzinfo=timezone.utc)),
            open=float(o[i]),
            high=float(h[i]),
            low=float(lo[i]),
            close=float(c[i]),
            volume=float(v[i]),
            timeframe=Timeframe.M1,
        )
        for i, t in enumerate(ts)
    ]


class _SubmitCounter:
    def __init__(self):
        self.submits = 0

    def submit_entry(self, candidate):
        self.submits += 1


def _close_ts(bar: Candle) -> datetime:
    return bar.timestamp + timedelta(minutes=bar.timeframe.minutes)


def _parse_ts(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _lag_bars(closes: list[datetime], sweep_close: datetime | None, confirm_close: datetime | None):
    """Count bars with sweep_close < bar_close <= confirm_close."""
    if sweep_close is None or confirm_close is None or not closes:
        return None
    start = bisect_right(closes, sweep_close)
    end = bisect_right(closes, confirm_close)
    return max(0, end - start)


def _quantiles(vals):
    if not vals:
        return {"n": 0, "min": None, "p25": None, "median": None, "p75": None, "max": None}
    s = sorted(vals)
    def q(p):
        if len(s) == 1:
            return float(s[0])
        k = (len(s) - 1) * p
        f = int(k)
        c = min(f + 1, len(s) - 1)
        return float(s[f] + (s[c] - s[f]) * (k - f))
    return {"n": len(s), "min": float(s[0]), "p25": q(0.25), "median": float(median(s)), "p75": q(0.75), "max": float(s[-1])}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_PATH.exists():
        raise SystemExit(f"DATA_GAP: missing {DATA_PATH}")

    print(f"S2 menu confirm-lag | data={DATA_PATH}", flush=True)
    print(f"window={WINDOW_START.date()}..{WINDOW_END.date()} warmup={WARMUP_START.date()}", flush=True)
    print("OPT-B false, OPT-2 off, W1 context_only, no threshold tuning. Diagnostic only.", flush=True)

    m1_all = load_m1(DATA_PATH, WARMUP_START, WINDOW_END)
    print(f"loaded M1 bars={len(m1_all)}", flush=True)
    needed_tfs = set(DETECTION_TFS) | set(PRODUCT_MENU_CONFIRMATION_TIMEFRAMES) | {EXEC_TF}
    series = {}
    for tf in sorted(needed_tfs, key=lambda t: t.minutes, reverse=True):
        series[tf] = resample_ohlcv(m1_all, tf)
        print(f"  resampled {tf.name}={len(series[tf])}", flush=True)
    closes = {tf: [_close_ts(b) for b in bars] for tf, bars in series.items()}

    runtime = MultiTFProductRuntime(detection_timeframes=DETECTION_TFS, execution_timeframe=EXEC_TF)
    menu = ProductMenuEngine(symbol="XAUUSD")  # same_bar_asof default False (OPT-B off)
    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=EXEC_TF, menu_confirmation=menu)
    counter = _SubmitCounter()
    adapter._runner = counter

    m15_win = [c for c in series[Timeframe.M15] if WINDOW_START <= c.timestamp < WINDOW_END]
    exec_series = series[EXEC_TF]
    feed_idx = {tf: 0 for tf in series}
    rows = []
    seen_winner_ids = set()
    register_armed_total = 0
    batch_errors = []

    for step, m15_bar in enumerate(m15_win):
        as_of = _close_ts(m15_bar)
        if step % BATCH_EVERY_STEPS == 0:
            prefixes = build_htf_prefixes(series, as_of)
            exec_prefix = [c for c in exec_series if _close_ts(c) <= as_of]
            arm_bar = max(len(exec_prefix) - 1, 0)
            try:
                report = runtime.run_batch(
                    engine=engine, series_by_tf=prefixes, as_of=as_of,
                    arm_bar=arm_bar, adapter=adapter, execution_candles=exec_prefix,
                )
            except Exception as e:
                batch_errors.append(f"{as_of}: {type(e).__name__}: {e}")
                report = None
            if report is not None:
                for poi in (report.armed or []):
                    det_tf = getattr(getattr(poi, "zone", None), "timeframe", None)
                    if det_tf is not None and menu.register_armed(poi, det_tf):
                        register_armed_total += 1

        feed = {}
        for tf in set(PRODUCT_MENU_DETECTION_TIMEFRAMES) | set(PRODUCT_MENU_CONFIRMATION_TIMEFRAMES):
            s = series.get(tf) or []
            start = feed_idx.get(tf, 0)
            tail_close = menu._closes[tf][-1] if menu._closes.get(tf) else datetime.min.replace(tzinfo=timezone.utc)
            while start < len(s) and _close_ts(s[start]) <= tail_close:
                start += 1
            feed_idx[tf] = start
            if start < len(s):
                feed[tf] = s[start:]
        try:
            winners = menu.on_execution_bar(feed, as_of=as_of)
        except Exception as e:
            batch_errors.append(f"menu@{as_of}: {type(e).__name__}: {e}")
            winners = []
        for w in (winners or []):
            adapter.queue_menu_candidate(w.candidate)
            key = (w.episode_id, w.route_id, w.confirmation_tf.name)
            if key in seen_winner_ids:
                continue
            seen_winner_ids.add(key)
            ep = next((e for e in menu.episodes() if e.episode_id == w.episode_id), None)
            stamp = {}
            try:
                payload = json.loads(getattr(w.candidate, "signal_data_json", "{}") or "{}")
                if isinstance(payload, dict):
                    stamp = payload.get("product_menu") or {}
            except Exception:
                stamp = {}
            t_sweep = ep.sweep_ts if ep else None
            t_sweep_close = ep.sweep_close_ts if ep else None
            t_confirm = _parse_ts(stamp.get("completion_ts"))
            det_name = getattr(getattr(w, "detection_tf", None), "name", None) or stamp.get("detection_tf")
            conf_name = getattr(getattr(w, "confirmation_tf", None), "name", None) or stamp.get("confirmation_tf")
            try:
                det_tf_obj = Timeframe[det_name] if det_name else None
            except Exception:
                det_tf_obj = getattr(w, "detection_tf", None)
            lag_det = _lag_bars(closes.get(det_tf_obj, []), t_sweep_close, t_confirm) if det_tf_obj else None
            lag_exec = _lag_bars(closes.get(EXEC_TF, []), t_sweep_close, t_confirm)
            lag_conf = None
            try:
                ctf_obj = Timeframe[conf_name] if conf_name else None
                lag_conf = _lag_bars(closes.get(ctf_obj, []), t_sweep_close, t_confirm) if ctf_obj else None
            except Exception:
                lag_conf = None
            label = stamp.get("label_at_confirm")
            # zone relation: ON_WINDOW => inside timing band/window; LATE/BEYOND_STOP_SIDE => outside band
            zone_relation = "unknown"
            if label in ("ON_WINDOW",):
                zone_relation = "inside_window"
            elif label in ("LATE", "BEYOND_STOP_SIDE"):
                zone_relation = "outside_band"
            elif label in ("UNLOCATABLE", "OTHER", None):
                zone_relation = "unknown"
            rows.append({
                "episode_id": w.episode_id,
                "poi_id": w.poi_id,
                "tier": w.tier_name,
                "det_tf": det_name,
                "confirm_tf": conf_name,
                "trigger_type": w.trigger,
                "route_id": w.route_id,
                "t_sweep": t_sweep.isoformat() if t_sweep else None,
                "t_sweep_close": t_sweep_close.isoformat() if t_sweep_close else None,
                "t_confirm": t_confirm.isoformat() if t_confirm else None,
                "lag_bars_det_tf": lag_det,
                "lag_bars_confirm_tf": lag_conf,
                "lag_bars_exec_m5": lag_exec,
                "completion_close": stamp.get("completion_close"),
                "atr_at_confirm": stamp.get("atr_at_confirm"),
                "distance_at_confirm_atr": stamp.get("distance_at_confirm_atr"),
                "label_at_confirm": label,
                "zone_relation_at_confirm": zone_relation,
                "zone_direction": stamp.get("zone_direction"),
                "zone": json.dumps(stamp.get("zone")) if stamp.get("zone") is not None else None,
            })
        if (step + 1) % 800 == 0:
            print(f"  step {step+1}/{len(m15_win)} as_of={as_of.date()} armed={register_armed_total} winners={len(rows)}")

    if adapter._runner is not None and adapter._menu_candidates:
        while adapter._menu_candidates:
            counter.submit_entry(adapter._menu_candidates.pop(0))

    csv_path = OUT_DIR / "s2_menu_winners.csv"
    fields = list(rows[0].keys()) if rows else [
        "episode_id","poi_id","tier","det_tf","confirm_tf","trigger_type","route_id",
        "t_sweep","t_sweep_close","t_confirm","lag_bars_det_tf","lag_bars_confirm_tf",
        "lag_bars_exec_m5","completion_close","atr_at_confirm","distance_at_confirm_atr",
        "label_at_confirm","zone_relation_at_confirm","zone_direction","zone",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    lag_det_vals = [r["lag_bars_det_tf"] for r in rows if isinstance(r.get("lag_bars_det_tf"), (int, float))]
    known_zone = [r for r in rows if r.get("zone_relation_at_confirm") in ("inside_window", "outside_band")]
    outside = [r for r in known_zone if r["zone_relation_at_confirm"] == "outside_band"]
    labels = defaultdict(int)
    for r in rows:
        labels[str(r.get("label_at_confirm"))] += 1

    summary = {
        "S2_STATUS": "PASS" if rows else "PASS_EMPTY_SAMPLE",
        "diagnostic_only": True,
        "not_performance": True,
        "opt_b": False,
        "opt2": "deferred",
        "window": {"warmup_start": WARMUP_START.date().isoformat(), "start": WINDOW_START.date().isoformat(), "end": WINDOW_END.date().isoformat()},
        "data": str(DATA_PATH),
        "detection_tfs": [t.name for t in DETECTION_TFS],
        "tiers": [(t.name, t.detection_tf.name, [c.name for c in t.confirmation_tfs]) for t in PRODUCT_MENU_TIERS],
        "N_WINNERS": len(rows),
        "QUEUE_SUBMITS": counter.submits,
        "REGISTER_ARMED": register_armed_total,
        "LAG_DET_BARS": _quantiles(lag_det_vals),
        "CONFIRM_OUTSIDE_BAND_PCT": (round(100.0 * len(outside) / len(known_zone), 2) if known_zone else None),
        "CONFIRM_OUTSIDE_ZONE_PCT": (round(100.0 * len(outside) / len(known_zone), 2) if known_zone else None),
        "ZONE_RELATION_KNOWN_N": len(known_zone),
        "LABEL_COUNTS": dict(labels),
        "BY_TIER": {t: len([r for r in rows if r["tier"] == t]) for t in sorted({r["tier"] for r in rows})},
        "BY_DET_TF": {t: len([r for r in rows if r["det_tf"] == t]) for t in sorted({r["det_tf"] for r in rows})},
        "BATCH_ERRORS": batch_errors[:10],
        "csv": str(csv_path),
        "note": str(NOTE_PATH),
    }
    (OUT_DIR / "s2_menu_confirm_lag_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")

    lag = summary["LAG_DET_BARS"]
    note = f"""# S2 — Menu Confirm Lag (Measurement Only)

**Diagnostic only — not performance/edge.** OPT-B false, OPT-2 deferred, W1 context_only. No pillar/threshold tuning. `LOGIC_CHANGED=NO` (research script only).

## Scope
- Path: MENU spine only — `MultiTFProductRuntime.run_batch` → `menu.register_armed` (sparse cadence, every {BATCH_EVERY_STEPS} M15 steps) + dense M15-timeline `menu.on_execution_bar` (closed detection/confirmation streams) → winner → `queue_menu_candidate` → `submit_entry` stub.
- Not adapter-only scan.
- Data: `{DATA_PATH}`
- Window: `{WINDOW_START.date()} .. {WINDOW_END.date()}` (warmup `{WARMUP_START.date()}`), XAUUSD, detection TFs `{[t.name for t in DETECTION_TFS]}`.
- Tiers: DAY(D1→H1), H4(H4→M5,M15), H1(H1→M5,M1), M15(M15→M1). Exec M5.

## Sample
- `N_WINNERS`: **{summary['N_WINNERS']}** (menu winners, deduped by episode/route/confirm_tf)
- `REGISTER_ARMED`: **{summary['REGISTER_ARMED']}** | `QUEUE_SUBMITS`: **{summary['QUEUE_SUBMITS']}**
- By tier: `{summary['BY_TIER']}` | By detection TF: `{summary['BY_DET_TF']}`

## Lag (detection-TF bars, sweep_close → confirm completion bar)
- n={lag['n']}, min={lag['min']}, p25={lag['p25']}, **median={lag['median']}**, p75={lag['p75']}, max={lag['max']}
- Lag = count of detection-TF bars with `sweep_close < bar_close <= t_confirm` (research measure; see CSV for per-winner `lag_bars_det_tf/confirm_tf/exec_m5`).

## Zone relation at confirm (from `product_menu.label_at_confirm`, timing-study taxonomy)
- `CONFIRM_OUTSIDE_BAND_PCT` (LATE or BEYOND_STOP_SIDE over known labels): **{summary['CONFIRM_OUTSIDE_BAND_PCT']}%** (known n={summary['ZONE_RELATION_KNOWN_N']})
- `CONFIRM_OUTSIDE_ZONE_PCT` (same measurable definition; exact inside/outside raw zone beyond label is NA without extra geometry): **{summary['CONFIRM_OUTSIDE_ZONE_PCT']}%**
- Label counts: `{summary['LABEL_COUNTS']}`
- Mapping note: `ON_WINDOW` = within locked timing band/window; `LATE`/`BEYOND_STOP_SIDE` = outside band (displaced/beyond stop side). `UNLOCATABLE` excluded from %; treat as unknown.

## Artifacts (gitignored results ok)
- `{csv_path}`
- `{OUT_DIR / 's2_menu_confirm_lag_summary.json'}`

## Bans honored
No OPT-2, OPT-B remains false, no pillar/threshold tuning, no profitability claims from lag stats.

## Errors
{json.dumps(summary['BATCH_ERRORS'])}
"""
    NOTE_PATH.write_text(note, encoding="utf-8")

    print(json.dumps({
        "S2_STATUS": "PASS" if rows else "PASS_EMPTY_SAMPLE",
        "N_WINNERS": summary["N_WINNERS"],
        "LAG_MEDIAN_DET_BARS": lag["median"],
        "CONFIRM_OUTSIDE_ZONE_PCT": summary["CONFIRM_OUTSIDE_ZONE_PCT"],
        "LOGIC_CHANGED": "NO",
        "NOTE_PATH": str(NOTE_PATH),
        "CSV": str(csv_path),
        "QUEUE_SUBMITS": counter.submits,
        "REGISTER_ARMED": register_armed_total,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
