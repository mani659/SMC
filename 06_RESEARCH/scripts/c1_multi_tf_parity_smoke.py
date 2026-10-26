"""C1 parity smoke — the shared multi-TF product seam on REAL data.

Proves, on the canonical dataset, that the runtime live/paper now use is
the same function research uses, and that the live cadence (one batch per
new H1 close) plus the loud-fail policy behave on real bars:

    07_DATA/XAUUSD_M1.parquet
      → resample M5 (exec) + H1 / H4 / D1
      → M5 bar loop: on each new H1 close, build honest prefixes
        (bars <= bar timestamp) and call
        ``MultiTFProductRuntime.run_batch`` exactly as LiveLoop does
      → parity: a second, independent engine+adapter run of the SAME batch
        through ``PaperRunner.arm_multi_tf`` must produce identical per-TF
        counts (the paper seam delegates to the same runtime)
      → loud-fail probe: ``run_batch`` with HTF withheld must raise
        ``MissingHtfSeriesError``; degraded mode must report degraded=True

No strategy code, no threshold tuning, no trading — measurement only.
Artifacts: 06_RESEARCH/results/c1_multi_tf_parity/<tag>/summary.json

Usage:
    python 06_RESEARCH/scripts/c1_multi_tf_parity_smoke.py [--days 14]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

from smc.backtest.pipeline_adapter import PipelineAdapter  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402
from smc.core.candle import Candle  # noqa: E402
from smc.live.loop import LiveLoop  # noqa: E402
from smc.orchestration.engine import PipelineEngine  # noqa: E402
from smc.orchestration.multi_tf_runtime import (  # noqa: E402
    MissingHtfSeriesError,
    MultiTFProductRuntime,
    build_htf_prefixes,
    missing_required_series,
)
from smc.paper.runner import PaperRunner  # noqa: E402
from smc.risk.risk_engine import RiskEngine  # noqa: E402

TF = Timeframe.M5
EXEC_START = datetime(2025, 10, 1, tzinfo=timezone.utc)
EXEC_END = datetime(2025, 10, 15, tzinfo=timezone.utc)
LOAD_FROM = EXEC_START - timedelta(days=45)   # HTF warm-up context


class _NullHeartbeat:
    def maybe_publish(self) -> bool:
        return False

    def publish_shutdown(self) -> None:
        return None


class _NullConnector:
    """Loop-shaped connector that never fetches (parity drives bars directly)."""

    def connect(self) -> bool:
        return True

    def copy_rates(self, symbol, tf, start, count):
        return None


def _summary(counters: dict, *, batches: int, bars: int, seconds: float,
             parity: dict | None, loud_fail: dict, degraded: dict) -> dict:
    return {
        "tag": "c1_parity",
        "window": [EXEC_START.isoformat(), EXEC_END.isoformat()],
        "bars_processed": bars,
        "htf_batches": batches,
        "seconds": round(seconds, 2),
        "funnel": counters,
        "parity": parity or {},
        "loud_fail": loud_fail,
        "degraded": degraded,
        "note": ("C1 seam parity: live cadence + paper delegation + loud-fail "
                 "on real bars; no strategy change, no tuning"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="run1")
    ap.add_argument("--days", type=float, default=14.0)
    args = ap.parse_args()

    from smc.data.parquet_loader import load_ohlcv_parquet
    from smc.data.resample import resample_multi

    t0 = time.perf_counter()
    exec_end = EXEC_START + timedelta(days=args.days)
    m1 = load_ohlcv_parquet(REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet")
    m1 = [c for c in m1 if LOAD_FROM <= c.timestamp <= exec_end + timedelta(days=1)]
    multi = resample_multi(m1, [TF, Timeframe.H1, Timeframe.H4, Timeframe.D1])
    m5 = [c for c in multi[TF] if EXEC_START <= c.timestamp <= exec_end]
    h1, h4, d1 = (multi[Timeframe.H1], multi[Timeframe.H4], multi[Timeframe.D1])
    print(f"[c1] M1 {len(m1)} → M5 {len(m5)} | H1 {len(h1)} H4 {len(h4)} D1 {len(d1)}",
          flush=True)

    h1_ts = [c.timestamp for c in h1]
    h4_ts = [c.timestamp for c in h4]
    d1_ts = [c.timestamp for c in d1]

    engine = PipelineEngine()
    adapter = PipelineAdapter(engine, timeframe=TF)
    adapter.set_candles(m5)
    runtime = MultiTFProductRuntime()

    counters = {"armed": 0, "duplicates": 0, "skipped_tracked": 0,
                "batches": 0, "per_tf_passed": {}, "per_tf_detected": {},
                "arm_errors": 0}
    parity: dict = {}
    last_h1: datetime | None = None

    # ---- Live-cadence loop through the SHARED seam ------------------- #
    for index, bar in enumerate(m5):
        cut = bisect_right(h1_ts, bar.timestamp) - 1
        if cut < 0:
            continue
        current_h1 = h1[cut].timestamp
        if current_h1 == last_h1:
            continue
        last_h1 = current_h1
        series = {
            Timeframe.H1: h1[: cut + 1],
            Timeframe.H4: h4[: bisect_right(h4_ts, bar.timestamp)],
            Timeframe.D1: d1[: bisect_right(d1_ts, bar.timestamp)],
        }
        try:
            report = runtime.run_batch(
                engine=engine, series_by_tf=series, as_of=bar.timestamp,
                arm_bar=index, adapter=adapter,
            )
        except MissingHtfSeriesError as exc:                # pragma: no cover
            counters["arm_errors"] += 1
            print(f"[c1] loud fail at bar {index}: {exc}", flush=True)
            continue
        counters["batches"] += 1
        counters["armed"] += report.armed_count
        counters["duplicates"] += len(report.duplicates)
        counters["skipped_tracked"] += len(report.skipped_tracked)
        for name, counts in report.per_tf.items():
            counters["per_tf_passed"][name] = (
                counters["per_tf_passed"].get(name, 0) + counts["passed"])
            counters["per_tf_detected"][name] = (
                counters["per_tf_detected"].get(name, 0) + counts["detected_raw"])

        # ---- Parity check on the first batch: paper delegation --------- #
        if not parity:
            paper_engine = PipelineEngine()
            paper_adapter = PipelineAdapter(paper_engine, timeframe=TF)
            paper_runner = PaperRunner(
                connector=_NullConnector(), risk_engine=RiskEngine(),
                pipeline=paper_adapter, order_manager=None,
                position_manager=None,
            )
            paper_report = paper_runner.arm_multi_tf(
                series, as_of=bar.timestamp, arm_bar=index)
            parity = {
                "batch_index": index,
                "live_per_tf": report.per_tf,
                "paper_per_tf": paper_report.per_tf,
                "per_tf_equal": report.per_tf == paper_report.per_tf,
                "live_armed": report.armed_count,
                "paper_armed": paper_report.armed_count,
                "armed_equal": report.armed_count == paper_report.armed_count,
                "degraded_flags": [report.degraded, paper_report.degraded],
                "paper_runtime_is_shared_class": (
                    type(paper_runner.runtime) is MultiTFProductRuntime
                    and paper_runner.runtime is not runtime),
            }
            print(f"[c1] parity: {json.dumps(parity, default=str)}", flush=True)

    # ---- Loud-fail + degraded policy probes on real series ----------- #
    loud_fail = {"raised": False}
    try:
        runtime.run_batch(engine=PipelineEngine(),
                          series_by_tf={Timeframe.H1: h1, Timeframe.H4: []},
                          as_of=h1[-1].timestamp, arm_bar=0)
    except MissingHtfSeriesError as exc:
        loud_fail = {"raised": True, "missing": [tf.name for tf in
                                                 missing_required_series(
                                                     {Timeframe.H1: h1,
                                                      Timeframe.H4: []})],
                     "message": str(exc)[:160]}
    degraded_runtime = MultiTFProductRuntime(allow_single_tf_degraded=True)
    degraded_report = degraded_runtime.run_batch(
        engine=PipelineEngine(), series_by_tf={}, as_of=m5[-1].timestamp,
        arm_bar=len(m5) - 1, execution_candles=m5,
    )
    degraded = {
        "degraded": degraded_report.degraded,
        "reason": degraded_report.degraded_reason,
        "per_tf": degraded_report.per_tf,
    }

    # ---- LiveLoop smoke (dispatch + cadence) without a real terminal -- #
    live = {"started": None, "batches": None}
    try:
        loop_engine = PipelineEngine()
        loop_adapter = PipelineAdapter(loop_engine, timeframe=TF)
        loop_runner = PaperRunner(
            connector=_NullConnector(), risk_engine=RiskEngine(),
            pipeline=loop_adapter, order_manager=None, position_manager=None,
        )
        loop = LiveLoop(connector=_NullConnector(), runner=loop_runner,
                        heartbeat=_NullHeartbeat(), timeframe=TF,
                        runtime=MultiTFProductRuntime(),
                        htf_fetch=lambda tf, count: {
                            Timeframe.H1: h1, Timeframe.H4: h4,
                            Timeframe.D1: d1}.get(tf, []))
        live["started"] = loop.start()
        loop._window.extend(m5[:3])                    # simulated window
        live["batches"] = 0
        for bar in m5[:60]:
            loop._detect_and_arm(bar)
        live["batches"] = loop.htf_batches
        live["arm_errors"] = loop.arm_errors
    except Exception as exc:                          # noqa: BLE001
        live["error"] = f"{type(exc).__name__}: {exc}"

    seconds = time.perf_counter() - t0
    out = REPO_ROOT / "06_RESEARCH" / "results" / "c1_multi_tf_parity" / args.tag
    out.mkdir(parents=True, exist_ok=True)
    summary = _summary(counters, batches=counters["batches"], bars=len(m5),
                       seconds=seconds, parity=parity, loud_fail=loud_fail,
                       degraded=degraded)
    summary["live_loop"] = live
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str),
                                      encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))
    print(f"[c1] wrote {out / 'summary.json'} in {seconds:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
