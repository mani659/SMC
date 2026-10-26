"""FR-1 multi-TF smoke: resampled H1/H4/D1 + M5 through the wired path.

Loads M1 parquet (accepted loader only), resamples to M5/H1/H4/D1,
validates a MultiTimeframeFeed, runs MultiTFDetectionDriver over H4+H1
(batch, validate-only), and proves M8 emits with the shared HTF map.
Loud fail when M8 emits nothing (silence must be impossible by accident).

Usage:
    python 06_RESEARCH/scripts/fr1_multi_tf_smoke.py [--from YYYY-MM-DD] [--to YYYY-MM-DD]

Artifacts: 06_RESEARCH/results/fr1_smoke/fr1_summary.json
Research-only: no thresholds, no sizing, no orders.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

from smc.backtest.data_feed import CandleSeries, MultiTimeframeFeed  # noqa: E402
from smc.config.model_type import ModelType  # noqa: E402
from smc.config.timeframe import Timeframe  # noqa: E402
from smc.data.resample import resample_multi  # noqa: E402
from smc.orchestration.detection_driver import DetectionDriver  # noqa: E402
from smc.orchestration.multi_tf import MultiTFDetectionDriver  # noqa: E402

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "fr1_smoke"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="from_ts", default="2025-09-20")
    ap.add_argument("--to", dest="to_ts", default="2025-10-31")
    args = ap.parse_args()

    from smc.data.parquet_loader import load_ohlcv_parquet

    start = datetime.strptime(args.from_ts, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = (datetime.strptime(args.to_ts, "%Y-%m-%d").replace(tzinfo=timezone.utc)
           + timedelta(days=1) - timedelta(minutes=1))
    all_candles = load_ohlcv_parquet(REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet")
    candles = [c for c in all_candles if start <= c.timestamp <= end]
    print(f"[fr1] M1 bars loaded: {len(candles)}", flush=True)
    if len(candles) < 1000:
        print("[fr1] FAIL: window too small", flush=True)
        return 1

    multi = resample_multi(candles, [Timeframe.M5, Timeframe.H1,
                                     Timeframe.H4, Timeframe.D1])
    for tf, series in multi.items():
        print(f"[fr1] {tf.name}: {len(series)} bars "
              f"({series[0].timestamp.date()}..{series[-1].timestamp.date()})",
              flush=True)
    feed = MultiTimeframeFeed(
        primary=CandleSeries(multi[Timeframe.M5], Timeframe.M5),
        htf={tf: CandleSeries(multi[tf], tf)
             for tf in (Timeframe.H1, Timeframe.H4, Timeframe.D1)},
    )
    print(f"[fr1] feed OK: primary={feed.primary_timeframe.name} "
          f"htf={[t.name for t in feed.timeframes if t is not feed.primary_timeframe]}",
          flush=True)

    driver = MultiTFDetectionDriver(
        detection_timeframes=(Timeframe.H4, Timeframe.H1),
        execution_timeframe=Timeframe.M5,
    )
    result = driver.validate_multi(
        {Timeframe.H4: multi[Timeframe.H4], Timeframe.H1: multi[Timeframe.H1]})
    print(f"[fr1] counts: {result.counts_by_tf()}", flush=True)
    print(f"[fr1] single_tf_detect_exec={result.single_tf_detect_exec} "
          f"degraded={result.degraded}", flush=True)

    # M8 emission through the wired driver path (shared D1/H4 map).
    probe = DetectionDriver(
        Timeframe.H1,
        htf_candles={Timeframe.H4: multi[Timeframe.H4],
                     Timeframe.D1: multi[Timeframe.D1]},
    )
    _passed, _results, _run, _skipped, detected = probe.validate_window(
        multi[Timeframe.H1])
    m8 = [p for p in detected if ModelType.M8 in p.models]
    print(f"[fr1] M8 POIs emitted: {len(m8)}", flush=True)
    if not m8:
        print("[fr1] FAIL: M8 silent despite fed HTF map", flush=True)
        return 1
    zone_tfs = sorted({p.zone.timeframe.name for p in m8})

    summary = {
        "window": [args.from_ts, args.to_ts],
        "m1_bars": len(candles),
        "series_lengths": {tf.name: len(s) for tf, s in multi.items()},
        "counts_by_tf": {tf.name: c for tf, c in result.counts_by_tf().items()},
        "single_tf_detect_exec": result.single_tf_detect_exec,
        "degraded": result.degraded,
        "m8_pois": len(m8),
        "m8_zone_timeframes": zone_tfs,
        "m8_htf_overlap": sum(1 for p in m8 if p.htf_overlap),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "fr1_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[fr1] PASS — artifacts in {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
