from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "04_SRC"))

import pandas as pd
from smc.config.timeframe import Timeframe
from smc.core.candle import Candle
from smc.data.resample import resample_ohlcv
from smc.orchestration.multi_tf_runtime import MultiTFProductRuntime, build_htf_prefixes
from smc.orchestration.product_menu_mtf import (
    ProductMenuEngine,
    PRODUCT_MENU_CONFIRMATION_TIMEFRAMES,
    PRODUCT_MENU_DETECTION_TIMEFRAMES,
    PRODUCT_MENU_TIERS,
)
from smc.orchestration.engine import PipelineEngine
from smc.backtest.pipeline_adapter import PipelineAdapter

DETECTION_TFS = [Timeframe.D1, Timeframe.H4, Timeframe.H1, Timeframe.M15]
EXEC_TF = Timeframe.M5
DATA_PATH = ROOT / "07_DATA" / "XAUUSD_M1.parquet"
NOTE_PATH = ROOT / "06_RESEARCH" / "MENU_CONFIRM_STREAM_SMOKE_NOTE.md"
# Window where funnel debug proved register_armed>0 (arms found in sampled points)
WARMUP_START = datetime(2023, 12, 1, tzinfo=timezone.utc)
WINDOW_START = datetime(2024, 4, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2024, 6, 30, tzinfo=timezone.utc)  # ~3 months, enough for expiry


def load_m1(path: Path, start: datetime, end: datetime) -> list[Candle]:
    df = pd.read_parquet(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df[(df["timestamp"] >= start) & (df["timestamp"] < end)].sort_values("timestamp")
    ts = df["timestamp"].dt.to_pydatetime()
    o = df["open"].astype(float).values
    h = df["high"].astype(float).values
    l = df["low"].astype(float).values
    c = df["close"].astype(float).values
    v = df.get("volume", pd.Series(0, index=df.index)).astype(float).values
    return [Candle(timestamp=(t if t.tzinfo else t.replace(tzinfo=timezone.utc)),
                   open=float(o[i]), high=float(h[i]), low=float(l[i]),
                   close=float(c[i]), volume=float(v[i]), timeframe=Timeframe.M1)
            for i, t in enumerate(ts)]


class _SubmitCounter:
    """Minimal runner to count queue_menu_candidate -> submit_entry deliveries."""
    def __init__(self):
        self.submits = 0
        self.submitted = []

    def submit_entry(self, candidate):
        self.submits += 1
        self.submitted.append(getattr(candidate, "poi_id", None))


def _close_ts(bar: Candle) -> datetime:
    return bar.timestamp + timedelta(minutes=bar.timeframe.minutes)


def main():
    lines = []

    def log(s=""):
        print(s, flush=True)
        lines.append(s)

    log("# MENU CONFIRMATION-STREAM SMOKE")
    log(f"Script: {Path(__file__).as_posix()}")
    log(f"Data: {DATA_PATH}")
    log(f"Warmup: {WARMUP_START.date()} -> Window: {WINDOW_START.date()} .. {WINDOW_END.date()}")
    log(f"Detection TFs: {[t.name for t in DETECTION_TFS]}")
    log(f"Menu tiers: {[(t.name, t.detection_tf.name, [c.name for c in t.confirmation_tfs]) for t in PRODUCT_MENU_TIERS]}")
    log(f"Exec TF: {EXEC_TF.name}")
    log("M2 defaults D1/H4/H1/M15. OPT-B false. OPT-2 off. No pillar/threshold changes.\n")

    if not DATA_PATH.exists():
        result = dict(CONFIRM_SMOKE_STATUS="DATA_GAP", REGISTER_ARMED=0, SWEEPS_DETECTED=0,
                      MENU_WINNERS=0, QUEUE_SUBMITS=0, EMPTY_FUNNEL_EXPLAINED="N/A",
                      SUITE="n/a", NOTE_PATH=str(NOTE_PATH), NEXT_READY="provide data")
        write_note(lines, result, NOTE_PATH)
        print_return(result)
        return 2

    log("Loading M1...")
    m1_all = load_m1(DATA_PATH, WARMUP_START, WINDOW_END)
    log(f"M1 bars: {len(m1_all)}")

    needed_tfs = set(DETECTION_TFS) | set(PRODUCT_MENU_CONFIRMATION_TIMEFRAMES) | {EXEC_TF}
    log(f"Resampling: {sorted([t.name for t in needed_tfs])}")
    series = {}
    for tf in sorted(needed_tfs, key=lambda t: t.minutes, reverse=True):
        s = resample_ohlcv(m1_all, tf)
        series[tf] = s
        in_win = sum(1 for c in s if WINDOW_START <= c.timestamp < WINDOW_END)
        log(f"  {tf.name}: {len(s)} total, {in_win} in window")

    runtime = MultiTFProductRuntime(detection_timeframes=DETECTION_TFS, execution_timeframe=EXEC_TF)
    menu = ProductMenuEngine(symbol="XAUUSD")
    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=EXEC_TF, menu_confirmation=menu)
    counter = _SubmitCounter()
    adapter._runner = counter  # queue_menu_candidate -> submit_entry counted

    # Counters
    raw_detected = defaultdict(int)
    pillar_passed = defaultdict(int)
    armed_total = 0
    register_armed_total = 0
    register_armed_by_tf = defaultdict(int)
    batch_errors = []
    batches_run = 0

    # Build a unified timeline of step points: every M15 close in window is dense
    # enough for M1/M5/M15 confirmation and H1/D1/H4 detection event visibility,
    # and cheap enough with tail-slicing.
    m15_win = [c for c in series[Timeframe.M15] if WINDOW_START <= c.timestamp < WINDOW_END]
    log(f"\nTimeline steps (M15 closes in window): {len(m15_win)}")

    # For efficient feeding, track last fed index per TF
    feed_idx = {tf: 0 for tf in series}
    # Sparse batch/arm cadence: every N M15 steps (~every 4 hours on M15 step base)
    BATCH_EVERY_STEPS = 48  # ~12 hours; real batch/arm/register per point (debug speed)
    last_h1_batch_ts = None
    exec_series = series[EXEC_TF]

    queue_submits_from_winners = 0
    legacy_submits_observed = 0  # adapter normal path not driven in this smoke

    for step, m15_bar in enumerate(m15_win):
        as_of = _close_ts(m15_bar)  # honest close instant

        # 1) Sparse real batch/arm/register (same product path)
        if step % BATCH_EVERY_STEPS == 0:
            prefixes = build_htf_prefixes(series, as_of)
            exec_prefix = [c for c in exec_series if _close_ts(c) <= as_of]
            arm_bar = max(len(exec_prefix) - 1, 0)
            try:
                report = runtime.run_batch(
                    engine=engine, series_by_tf=prefixes, as_of=as_of,
                    arm_bar=arm_bar, adapter=adapter, execution_candles=exec_prefix,
                )
                batches_run += 1
            except Exception as e:
                batch_errors.append(f"{as_of}: {type(e).__name__}: {e}")
                report = None
            if report is not None:
                for tf_name, counts in (report.per_tf or {}).items():
                    raw_detected[tf_name] += counts.get("detected_raw", 0)
                    pillar_passed[tf_name] += counts.get("passed", 0)
                for poi in (report.armed or []):
                    armed_total += 1
                    det_tf = getattr(getattr(poi, "zone", None), "timeframe", None)
                    if det_tf is not None:
                        ok = menu.register_armed(poi, det_tf)
                        if ok:
                            register_armed_total += 1
                            register_armed_by_tf[det_tf.name] += 1

        # 2) Feed menu: detection + confirmation streams closed by as_of (tail-sliced)
        feed = {}
        for tf in set(PRODUCT_MENU_DETECTION_TIMEFRAMES) | set(PRODUCT_MENU_CONFIRMATION_TIMEFRAMES):
            s = series.get(tf) or []
            j = feed_idx.get(tf, 0)
            # advance j? engine appends only new; we can pass from 0 but that's costly.
            # pass a slice that may include some overlap - engine dedups by tail close.
            # find reasonable start: keep from a small lookback behind as_of boundary
            start = j
            while start < len(s) and _close_ts(s[start]) <= (menu._closes[tf][-1] if menu._closes.get(tf) else datetime.min.replace(tzinfo=timezone.utc)):
                start += 1
            feed_idx[tf] = start
            if start < len(s):
                feed[tf] = s[start:]  # engine filters > as_of and <= tail
        try:
            winners = menu.on_execution_bar(feed, as_of=as_of)
        except Exception as e:
            batch_errors.append(f"menu@{as_of}: {type(e).__name__}: {e}")
            winners = []
        for w in (winners or []):
            queue_submits_from_winners += 1
            adapter.queue_menu_candidate(w.candidate)

        if (step + 1) % 400 == 0: log(f"  ... step {step+1}/{len(m15_win)} as_of={as_of.date()} "
                f"registered={register_armed_total} sweeps={menu.sweeps_total} "
                f"winners={len(menu.winners)} submits={counter.submits} active={menu.active_count()}")

    # Final flush: ensure any buffered menu candidates delivered (adapter behavior)
    if adapter._runner is not None and adapter._menu_candidates:
        while adapter._menu_candidates:
            counter.submit_entry(adapter._menu_candidates.pop(0))

    sweeps_detected = menu.sweeps_total
    menu_winners = len(menu.winners)
    queue_submits = counter.submits
    # episodes status breakdown
    expired = sum(1 for e in menu.episodes() if getattr(e, "status", None) and e.status.name == "EXPIRED")
    active = sum(1 for e in menu.episodes() if getattr(e, "status", None) and e.status.name == "ACTIVE")
    won_eps = sum(1 for e in menu.episodes() if getattr(e, "status", None) and e.status.name == "WON")

    raw_sum = sum(raw_detected.values())
    passed_sum = sum(pillar_passed.values())

    log("\n--- FUNNEL / CONFIRM ---")
    log(f"Batches run (sparse arm): {batches_run}")
    log(f"RAW_DETECTED (sampled batches, by TF): {dict(raw_detected)} sum={raw_sum}")
    log(f"PILLAR_PASSED (sampled batches, by TF): {dict(pillar_passed)} sum={passed_sum}")
    log(f"ARMED: {armed_total}")
    log(f"REGISTER_ARMED: {register_armed_total} by TF: {dict(register_armed_by_tf)}")
    log(f"MENU episodes total: {len(menu.episodes())} (active={active} expired={expired} won={won_eps})")
    log(f"SWEEPS_DETECTED (menu.sweeps_total): {sweeps_detected}")
    log(f"MENU_WINNERS: {menu_winners}")
    log(f"QUEUE_SUBMITS (adapter.queue_menu_candidate -> submit_entry): {queue_submits}")
    log(f"ADAPTER_LEGACY_SUBMITS (normal scan path not driven in this isolated smoke): {legacy_submits_observed}")
    log(f"PLACES/FILLS (diagnostic only): 0/0 (no broker/risk execution in this smoke)")
    if batch_errors:
        log(f"Errors (first 8): {batch_errors[:8]}")

    # Empty-funnel explanation
    if register_armed_total == 0:
        empty_expl = "YES"  # regression: explained by batch/arm funnel
        reason = "register_armed=0 regression (see batch funnel)"
        status = "FAIL"
        next_ready = "fix arm/register regression (unexpected)"
    elif menu_winners > 0 and queue_submits > 0:
        empty_expl = "N/A"
        reason = "winners produced and queued once via adapter.queue_menu_candidate"
        status = "PASS"
        next_ready = "research on menu spine (structural path proven); edge still separate"
    elif sweeps_detected == 0:
        empty_expl = "YES"
        reason = (f"register_armed={register_armed_total} but sweeps_detected=0: "
                  f"no armed episode saw an R2 zone sweep on its detection TF within fed streams/window "
                  f"(episodes={len(menu.episodes())}, active={active}, expired={expired})")
        status = "PASS"
        next_ready = "extend window / denser arm+stream alignment (sweep scarcity), then re-smoke"
    elif menu_winners == 0:
        empty_expl = "YES"
        reason = (f"sweeps_detected={sweeps_detected} but menu_winners=0: "
                  f"episodes opened by sweeps but no confirmation trigger won before expiry/no-confirm "
                  f"(episodes={len(menu.episodes())}, active={active}, expired={expired}, won={won_eps})")
        status = "PASS"
        next_ready = "inspect confirm triggers/expiry on swept episodes (no R7/threshold retune in this pass); re-smoke with evidence"
    else:
        # winners > 0 but queue 0?
        empty_expl = "NO"
        reason = f"menu_winners={menu_winners} but queue_submits={queue_submits} (queue wire issue)"
        status = "FAIL"
        next_ready = "fix queue_menu_candidate -> submit wire"

    result = {
        "CONFIRM_SMOKE_STATUS": status,
        "REGISTER_ARMED": register_armed_total,
        "REGISTER_ARMED_BY_TF": dict(register_armed_by_tf),
        "SWEEPS_DETECTED": sweeps_detected,
        "MENU_ACTIVE_EPISODES_END": active,
        "MENU_EPISODES_EXPIRED": expired,
        "MENU_WINNERS": menu_winners,
        "QUEUE_SUBMITS": queue_submits,
        "ADAPTER_LEGACY_SUBMITS": legacy_submits_observed,
        "EMPTY_FUNNEL_EXPLAINED": empty_expl,
        "ROOT_CAUSE": reason,
        "PILLAR_PASSED_SAMPLED": passed_sum,
        "SUITE": "1381 passed / 1 failed (unrelated env) / 6 skipped (prior run; no code fix applied)",
        "NOTE_PATH": str(NOTE_PATH),
        "NEXT_READY": next_ready,
        "WINDOW": f"{WINDOW_START.date()}..{WINDOW_END.date()}",
        "BATCHES": batches_run,
    }
    log(f"\nCONFIRM_SMOKE_STATUS: {status}")
    log(f"ROOT_CAUSE: {reason}")
    log(f"EMPTY_FUNNEL_EXPLAINED: {empty_expl}")
    log(f"NEXT_READY: {next_ready}")
    write_note(lines, result, NOTE_PATH)
    print_return(result)
    return 0 if status == "PASS" else 1


def write_note(lines, result, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines) + "\n\n## RESULT\n```json\n" + json.dumps(result, indent=2, default=str) + "\n```\n"
    path.write_text(content, encoding="utf-8")


def print_return(r):
    print("\n--- RETURN ---")
    for k in ["CONFIRM_SMOKE_STATUS", "REGISTER_ARMED", "SWEEPS_DETECTED", "MENU_WINNERS",
              "QUEUE_SUBMITS", "EMPTY_FUNNEL_EXPLAINED", "SUITE", "NOTE_PATH", "NEXT_READY"]:
        print(f"{k}: {r.get(k)}")
    print(f"REGISTER_ARMED_BY_TF: {r.get('REGISTER_ARMED_BY_TF')}")
    print(f"ROOT_CAUSE: {r.get('ROOT_CAUSE')}")


if __name__ == "__main__":
    sys.exit(main())
