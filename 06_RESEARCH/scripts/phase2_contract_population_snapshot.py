"""Phase 2 population snapshot — pillar first-failure histogram on real bars.

READ-ONLY counts over a short multi-TF window through the EXISTING multi-TF
research path: per-TF ``DetectionDriver.validate_window`` (the frozen driver
behind the C1 seam) on honest H4/H1 prefixes at each new H1 close — the same
detection windows the product runtime sees. Rates only, NO PnL, NO trades,
NO tuning. This is the OPTIONAL Phase 2 population snapshot; Phase 2's PASS
does not depend on it.

Why not through ``MultiTFProductRuntime.run_batch``: the seam's batch report
is deliberately machine-readable COUNTS only (no POI objects — contract §2),
so per-POI pillar results are not exposed there. The per-TF driver path
returns the ``ValidationResult`` list without touching any production code.

Contract relevance: the histogram documents that the machine-checkable
contracts in ``tests/test_phase2_layer_contracts.py`` describe what the
layers actually do on real bars (e.g. which hard pillar dominates first
failures in the population).

Output: 06_RESEARCH/results/phase2_contracts/snapshot.json
Usage:  python 06_RESEARCH/scripts/phase2_contract_population_snapshot.py [--days 14]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from bisect import bisect_right
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))

from smc.config.timeframe import Timeframe  # noqa: E402
from smc.orchestration.detection_driver import DetectionDriver  # noqa: E402

TF = Timeframe.M5
EXEC_START = datetime(2025, 10, 1, tzinfo=timezone.utc)
DETECTION_TFS = (Timeframe.H4, Timeframe.H1)  # the canonical detect set (contract §1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="snapshot")
    ap.add_argument("--days", type=float, default=14.0)
    args = ap.parse_args()

    from smc.data.parquet_loader import load_ohlcv_parquet
    from smc.data.resample import resample_multi

    t0 = time.perf_counter()
    exec_end = EXEC_START + timedelta(days=args.days)
    data_path = REPO_ROOT / "07_DATA" / "XAUUSD_M1.parquet"
    if not data_path.exists():
        print(f"[p2] SKIP: canonical dataset missing at {data_path}")
        return 0
    try:
        m1 = load_ohlcv_parquet(data_path)
    except Exception as exc:  # noqa: BLE001 — snapshot is optional, fail soft
        print(f"[p2] SKIP: dataset unreadable ({type(exc).__name__}: {exc})")
        return 0
    m1 = [
        c for c in m1
        if EXEC_START - timedelta(days=45) <= c.timestamp <= exec_end + timedelta(days=1)
    ]
    if not m1:
        print("[p2] SKIP: no bars in the requested window")
        return 0
    multi = resample_multi(m1, list(DETECTION_TFS))
    series = {tf: multi[tf] for tf in DETECTION_TFS}
    print("[p2] " + " | ".join(
        f"{tf.name} {len(series[tf])}" for tf in DETECTION_TFS
    ) + f" (M1 {len(m1)})", flush=True)

    drivers = {tf: DetectionDriver(tf) for tf in DETECTION_TFS}
    ts = {tf: [c.timestamp for c in series[tf]] for tf in DETECTION_TFS}

    detected = 0
    merged = 0
    passed = 0
    batches = 0
    first_fail: Counter[str] = Counter()
    pillar_status: Counter[str] = Counter()
    decision: Counter[str] = Counter()

    # One snapshot step per new H4 close (the coarser detection cadence —
    # every H1 window is a strict prefix of the next H4 boundary's view, so
    # this samples the population without double-counting every H1 bar).
    h4 = series[Timeframe.H4]
    for index in range(len(h4)):
        prefix = {Timeframe.H4: h4[: index + 1]}
        for tf in DETECTION_TFS:
            prefix[tf] = series[tf][: bisect_right(ts[tf], h4[index].timestamp)]
        batches += 1
        for tf in DETECTION_TFS:
            try:
                _passed, results, _run, _skipped, pois = drivers[tf].validate_window(
                    prefix[tf]
                )
            except (IndexError, ValueError) as exc:
                # Snapshot must not die on a degenerate synthetic-free window.
                print(f"[p2] window {tf.name}@{index} skipped: "
                      f"{type(exc).__name__}: {exc}", flush=True)
                continue
            detected += len(pois)
            merged += len(results)
            passed += len(_passed)
            for result in results:
                failure = result.first_failure
                if failure is not None:
                    first_fail[f"P{failure.pillar}:{failure.status.value}"] += 1
                    for ran in result.pillar_results:
                        pillar_status[f"P{ran.pillar}:{ran.status.value}"] += 1
                else:
                    decision["PASS"] += 1
                    for ran in result.pillar_results:
                        pillar_status[f"P{ran.pillar}:{ran.status.value}"] += 1

    seconds = time.perf_counter() - t0
    snapshot = {
        "tag": f"phase2_contracts_{args.tag}",
        "window": [EXEC_START.isoformat(), exec_end.isoformat()],
        "detection_tfs": [tf.name for tf in DETECTION_TFS],
        "snapshot_steps": batches,
        "seconds": round(seconds, 2),
        "counts": {
            "detected_raw": detected,
            "merged": merged,
            "passed": passed,
        },
        "pillar_first_failure_histogram": dict(sorted(first_fail.items())),
        "pillar_status_histogram": dict(sorted(pillar_status.items())),
        "note": (
            "Phase 2 population snapshot — READ-ONLY counts through the "
            "existing per-TF DetectionDriver.validate_window research path "
            "(the frozen driver behind the C1 seam); rates only, no PnL, no "
            "trades, no tuning. Phase 2 PASS rests on the unit contracts, "
            "not this file."
        ),
    }
    out = REPO_ROOT / "06_RESEARCH" / "results" / "phase2_contracts"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.tag}.json").write_text(
        json.dumps(snapshot, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(snapshot, indent=2, default=str))
    print(f"[p2] wrote {out / (args.tag + '.json')} in {seconds:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
