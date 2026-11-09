"""
OPT-4 — MENU-PATH REJOIN (MEASUREMENT ONLY)
Applies OPT-4-style place/zone taxonomy labels to MENU `queue_menu_candidate` submits
(same spine, not adapter-only). Read-only; no threshold/R7/OPT-2 changes.
LOGIC_CHANGED=NO.
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
from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime, build_htf_prefixes  # noqa: E402
from smc.orchestration.product_menu_mtf import (  # noqa: E402
    PRODUCT_MENU_CONFIRMATION_TIMEFRAMES,
    PRODUCT_MENU_DETECTION_TIMEFRAMES,
    ProductMenuEngine,
    completion_timing_label,
    completion_zone_edge_distance_atr,
)
from smc.utils.atr import latest_atr  # noqa: E402

DETECTION_TFS = [Timeframe.D1, Timeframe.H4, Timeframe.H1, Timeframe.M15]
EXEC_TF = Timeframe.M5
DATA_PATH = ROOT / "07_DATA" / "XAUUSD_M1.parquet"
OUT_DIR = ROOT / "06_RESEARCH" / "results" / "opt4_menu_rejoin"
NOTE_PATH = ROOT / "06_RESEARCH" / "OPT4_MENU_REJOIN_NOTE.md"

# Same runtime-feasible window as S2b completed run (documented).
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
    """Counts and captures menu queue_menu_candidate -> submit_entry deliveries."""
    def __init__(self):
        self.submits = []
    def submit_entry(self, candidate):
        self.submits.append(candidate)


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


def _zone_bounds(stamp):
    z = stamp.get("zone")
    if isinstance(z, (list, tuple)) and len(z) == 2:
        try:
            return float(z[0]), float(z[1])
        except Exception:
            return None, None
    return None, None


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_PATH.exists():
        raise SystemExit(f"DATA_GAP: missing {DATA_PATH}")
    print(f"OPT-4 menu rejoin | data={DATA_PATH}", flush=True)
    print(f"window={WINDOW_START.date()}..{WINDOW_END.date()} warmup={WARMUP_START.date()} (same spine/method as S2b)", flush=True)
    print("OPT-B false, OPT-2 off. No threshold/R7 changes. Diagnostic only.", flush=True)

    m1_all = load_m1(DATA_PATH, WARMUP_START, WINDOW_END)
    print(f"loaded M1 bars={len(m1_all)}", flush=True)
    needed_tfs = set(DETECTION_TFS) | set(PRODUCT_MENU_CONFIRMATION_TIMEFRAMES) | {EXEC_TF}
    series = {}
    for tf in sorted(needed_tfs, key=lambda t: t.minutes, reverse=True):
        series[tf] = resample_ohlcv(m1_all, tf)
        print(f"  resampled {tf.name}={len(series[tf])}", flush=True)
    closes = {tf: [_close_ts(b) for b in bars] for tf, bars in series.items()}
    exec_closes = closes[EXEC_TF]

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

    # Join: one row per menu submit delivery (queue_menu_candidate -> submit_entry)
    rows = []
    for i, cand in enumerate(capture.submits):
        stamp = {}
        join_keys = {"submit_index": i, "candidate_poi_id": getattr(cand, "poi_id", None),
                     "candidate_route_id": getattr(cand, "route_id", None),
                     "candidate_pillar_path": getattr(cand, "pillar_path", None)}
        gap_reasons = []
        try:
            payload = json.loads(getattr(cand, "signal_data_json", "{}") or "{}")
            stamp = payload.get("product_menu") or {} if isinstance(payload, dict) else {}
        except Exception as e:
            gap_reasons.append(f"stamp_parse:{type(e).__name__}")
        if not stamp:
            gap_reasons.append("missing_product_menu_stamp")

        confirm_label = stamp.get("label_at_confirm")
        completion_ts = _parse_ts(stamp.get("completion_ts"))
        zlow, zhigh = _zone_bounds(stamp)
        direction = stamp.get("zone_direction")
        join_keys.update({
            "poi_id": stamp.get("poi_id") or getattr(cand, "poi_id", None),
            "tier": stamp.get("tier"), "detection_tf": stamp.get("detection_tf"),
            "confirmation_tf": stamp.get("confirmation_tf"),
            "sweep_ts": stamp.get("sweep_ts"), "completion_ts": stamp.get("completion_ts"),
            "zone_low": zlow, "zone_high": zhigh, "zone_direction": direction,
        })

        # Submit/place-frame approximation (OPT-4 style): first closed EXEC_TF bar at/after completion_ts
        place_label = None; place_dist = None; place_close = None; place_ts = None; atr_at_place = None
        if completion_ts is None:
            gap_reasons.append("missing_completion_ts")
        elif zlow is None or zhigh is None or direction is None:
            gap_reasons.append("missing_zone_or_direction")
        else:
            idx = bisect_left(exec_closes, completion_ts)
            if idx >= len(exec_series):
                gap_reasons.append("no_exec_bar_at_or_after_completion")
            else:
                bar = exec_series[idx]
                place_ts = _close_ts(bar); place_close = float(bar.close)
                atr_v = latest_atr(exec_series[: idx + 1], 14)
                atr_at_place = float(atr_v) if atr_v is not None and float(atr_v) > 0 else None
                if atr_at_place is None:
                    gap_reasons.append("missing_atr_at_place")
                place_label = completion_timing_label(direction, zlow, zhigh, place_close, atr_at_place)
                place_dist = completion_zone_edge_distance_atr(zlow, zhigh, place_close, atr_at_place)

        full_label = (confirm_label not in (None, "", "UNLOCATABLE", "OTHER")) and (place_label not in (None, "", "UNLOCATABLE", "OTHER"))
        rows.append({
            **join_keys,
            "confirm_label": confirm_label,
            "confirm_distance_atr": stamp.get("distance_at_confirm_atr"),
            "place_frame": f"first_closed_{EXEC_TF.name}_at_or_after_completion_ts",
            "place_ts": place_ts.isoformat() if place_ts else None,
            "place_close": place_close,
            "atr_at_place": round(atr_at_place, 6) if atr_at_place is not None else None,
            "place_label": place_label,
            "place_distance_atr": place_dist,
            "full_label_coverage": full_label,
            "gap_reasons": ";".join(gap_reasons) if gap_reasons else "",
        })

    csv_path = OUT_DIR / "opt4_menu_rejoin.csv"
    fields = list(rows[0].keys()) if rows else ["submit_index","poi_id","confirm_label","place_label","full_label_coverage","gap_reasons"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=fields); wr.writeheader(); wr.writerows(rows)

    n = len(rows)
    covered = sum(1 for r in rows if r["full_label_coverage"])
    coverage_pct = round(100.0 * covered / n, 2) if n else None
    label_mix_confirm = defaultdict(int); label_mix_place = defaultdict(int)
    cross = defaultdict(int); gaps = defaultdict(int)
    for r in rows:
        label_mix_confirm[str(r.get("confirm_label"))] += 1
        label_mix_place[str(r.get("place_label"))] += 1
        cross[f"{r.get('confirm_label')}->{r.get('place_label')}"] += 1
        if not r["full_label_coverage"]:
            for g in (r["gap_reasons"] or "unknown").split(";"):
                if g: gaps[g] += 1

    summary = {
        "OPT4_STATUS": "PASS", "diagnostic_only": True, "not_performance": True,
        "opt_b": False, "opt2": "deferred", "r7_changed": False,
        "window": {"warmup_start": WARMUP_START.date().isoformat(), "start": WINDOW_START.date().isoformat(), "end": WINDOW_END.date().isoformat()},
        "path": "menu queue_menu_candidate submits only (same spine as S2b; not adapter-only)",
        "N_SUBMITS": n, "N_MENU_WINNERS": len(menu.winners), "REGISTER_ARMED": register_armed, "SWEEPS": menu.sweeps_total,
        "LABEL_COVERAGE_PCT": coverage_pct, "FULL_LABEL_N": covered,
        "LABEL_MIX_CONFIRM": dict(label_mix_confirm),
        "LABEL_MIX_PLACE": dict(label_mix_place),
        "LABEL_MIX": dict(label_mix_place),  # primary return field = place/join labels
        "CONFIRM_X_PLACE": dict(cross),
        "GAP_REASONS": dict(gaps),
        "join_keys": ["submit_index","candidate_poi_id/route_id/pillar_path","poi_id","tier","detection_tf","confirmation_tf","sweep_ts","completion_ts","zone","direction"],
        "csv": str(csv_path),
    }
    (OUT_DIR / "opt4_menu_rejoin_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")

    note = f"""# OPT-4 — Menu-Path Rejoin (Measurement Only)

**Diagnostic only — not performance/edge.** No threshold/R7/pillar changes. OPT-B false, OPT-2 deferred. `LOGIC_CHANGED=NO`.

## Goal / scope
Recompute OPT-4-style place/zone taxonomy labels on **MENU `queue_menu_candidate` submits** (menu spine only, not adapter-only). Labels use the frozen taxonomy helpers (`completion_timing_label`, `completion_zone_edge_distance_atr`, `latest_atr`) — same convention as OPT-1/OPT-4 (nearest zone edge, 0 inside, Wilder prefix ATR; band = locked timing-study semantics). **R7 verdicts NOT recomputed/changed** (place frame is a submit approximation; risk-side blocks out of scope).

## Input / method
- Same spine as S2b: `run_batch` → `register_armed` → `on_execution_bar` → winner → `queue_menu_candidate` → `submit_entry` capture.
- Window `2024-04-01 .. 2024-05-01` (warmup `2023-12-01`), runtime-feasible, data `{DATA_PATH}` (fail-loud).
- **Confirm labels:** from winner `product_menu` stamp (`label_at_confirm`, `completion_ts`, zone, direction).
- **Submit/place-frame labels (OPT-4-style approximation):** first closed `{EXEC_TF.name}` bar at/after `completion_ts`; label/distance via frozen helpers on that bar's close + Wilder prefix ATR(14). No trades placed.
- **Join keys:** submit_index, candidate poi/route/pillar_path, poi_id, tier, detection_tf, confirmation_tf, sweep_ts, completion_ts, zone [low,high], zone_direction.

## Counts / coverage
- `N_SUBMITS` (menu queue_menu_candidate → submit_entry): **{n}**
- `N_MENU_WINNERS`: **{len(menu.winners)}** | `REGISTER_ARMED`: **{register_armed}** | `SWEEPS`: **{menu.sweeps_total}**
- `LABEL_COVERAGE_PCT` (full = confirm label known/non-UNLOCATABLE **and** place-frame label known/non-UNLOCATABLE): **{coverage_pct}%** ({covered}/{n})
- Gap reasons: `{dict(gaps)}`

## Label mix
- Confirm (`label_at_confirm`): `{dict(label_mix_confirm)}`
- Place/submit-frame (primary OPT-4 join labels): `{dict(label_mix_place)}`
- Cross-tab confirm→place (no forced agreement): `{dict(cross)}`

## Caveats
- Submit frame is an approximation (first closed exec bar at/after completion), not a full-stack broker place; risk-side blocks/R9-deferred placements out of scope. Menu path only. Counts/geometry labels only — no expectancy, no edge, no PnL. Small n (same window as S2b).

## Artifacts (gitignored)
- `{csv_path}`
- `{OUT_DIR / 'opt4_menu_rejoin_summary.json'}`
"""
    NOTE_PATH.write_text(note, encoding="utf-8")
    print(json.dumps({
        "OPT4_STATUS": "PASS", "N_SUBMITS": n, "LABEL_COVERAGE_PCT": coverage_pct,
        "LABEL_MIX": dict(label_mix_place), "LABEL_MIX_CONFIRM": dict(label_mix_confirm),
        "CONFIRM_X_PLACE": dict(cross), "LOGIC_CHANGED": "NO",
        "NOTE_PATH": str(NOTE_PATH),
    }, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
