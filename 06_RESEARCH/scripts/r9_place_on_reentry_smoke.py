"""R9 smoke — place-on-reentry intents on the frozen FR-4b window.

Logging-only instrumentation over the FR-4 fidelity baseline (the same
pattern the FR-4b/forensic scripts used): ``fr4.BacktestRunner`` is
replaced by a capturing subclass for the duration of ONE frozen run;
the real runner internals are untouched. The capture is restored
unconditionally in ``finally``.

Window (identical to FR-4b, frozen): load 2025-08-01 (1-month M1
warm-up), exec 2025-09-01 → 2025-11-30. Stack state: FR-3.1 anchor +
R7 market-reference guard + R8 HTF resting bars + R9 intents live.

Diagnostic only. NOT edge, promotion, or capital advice. No parameter
search is performed regardless of trade count.

Usage:
  python 06_RESEARCH/scripts/r9_place_on_reentry_smoke.py --tag r9_smoke \
      --out-root 06_RESEARCH/results/r9_smoke/run1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

import fr4_fidelity_baseline as fr4  # noqa: E402

# R9 smoke default window (frozen, = FR-4b): 1-month warm-up + 3-month exec.
DEFAULT_LOAD_FROM = "2025-08-01"
DEFAULT_EXEC_FROM = "2025-09-01"
DEFAULT_EXEC_TO = "2025-11-30"


def run_with_intent_capture(args) -> dict:
    """Run the FR-4 baseline with the runner captured for intent telemetry.

    The subclass changes NO behavior — it only records the instance so
    the intent book (counters + lifecycle events) can be read after the
    run. The original ``fr4.BacktestRunner`` is restored in ``finally``.
    """
    captured: list = []

    class _CapturingRunner(fr4.BacktestRunner):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            captured.append(self)

    original_runner = fr4.BacktestRunner
    fr4.BacktestRunner = _CapturingRunner  # type: ignore[assignment]
    try:
        summary = fr4.run(args)
    finally:
        fr4.BacktestRunner = original_runner  # type: ignore[assignment]

    if len(captured) != 1:
        summary["r9_intent_capture_error"] = (
            f"expected exactly 1 runner instance, captured {len(captured)}")
        return summary
    runner = captured[0]
    counters = runner.intents.counters()
    events = list(runner.intents.events)
    summary["r9_intents"] = counters
    # Event breakdown (machine-readable; occurrence order preserved).
    by_event: dict[str, int] = {}
    for e in events:
        by_event[e["event"]] = by_event.get(e["event"], 0) + 1
    summary["r9_intent_events"] = by_event
    # Per-intent lifecycle table (small — routes were 6 in FR-4b).
    summary["r9_intent_rows"] = [
        {"intent_id": i.intent_id,
         "route_id": getattr(i.candidate, "route_id", None),
         "poi_id": getattr(i.candidate, "poi_id", None),
         "is_m8": bool(getattr(i.candidate, "is_m8", False)),
         "detection_tf": str(getattr(i.candidate, "detection_tf", None)),
         "signal_bar": i.signal_bar, "rest_bars": i.rest_bars,
         "expire_bar": i.expire_bar, "status": i.status,
         "placed_bar": i.placed_bar, "placed_ticket": i.placed_ticket}
        for i in runner.intents._intents
    ]
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--load-from", default=DEFAULT_LOAD_FROM)
    ap.add_argument("--exec-from", default=DEFAULT_EXEC_FROM)
    ap.add_argument("--exec-to", default=DEFAULT_EXEC_TO)
    args = ap.parse_args()
    summary = run_with_intent_capture(args)
    out = REPO_ROOT / args.out_root
    out.mkdir(parents=True, exist_ok=True)
    (out / "r9_smoke_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: v for k, v in summary.items()
                      if k in ("tag", "funnel", "routes_m8", "entries_placed",
                               "placed_with_tp", "trades_closed", "m8_trades",
                               "r9_intents", "r9_intent_events")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
