"""LEG 5b — ZoneDedup lifecycle implementation measurement (frozen 6m).

Drives the SAME frozen composition LEG 4 drove (``phase3_structure_funnel.run``,
imported, not forked — exec M5 2025-06-01 → 2025-11-30, M1 load from 2025-05-01)
with the retirement wiring live, and reports the pre-registered acceptance
gates of ``06_RESEARCH/ZONE_DEDUP_LIFECYCLE_DESIGN.md``:

* **Gate A** integrity: htf_batches / merged / passed_validation vs the frozen
  baseline (2,979 / 43,004 / 2,021) — retirement is downstream of validation,
  so those three MUST match exactly.
* **Gate B** the mechanism engaged: ``retired_total >= 1`` (zero = INVALID run).
* **Gate C** disposition: armed / SKIP_DEDUP deltas vs the LEG 4 baseline
  (30 armed / 1,991 dedup), PASS→arm rate, live_keys, retire_misses.
* **Gate D** determinism: run this script twice (different ``--run-id``) and
  byte-compare the dumped ``summary.json``.

Logging-only seams, restored in ``finally`` (same pattern as LEG 3/4):
``MultiTFProductRuntime.__init__`` (to keep a handle on the session registry
and read its counters after the run) and ``PipelineAdapter._retire_dead_keys``
(one record per per-bar retirement sweep: bar, engine-pruned ids that were
sent). Nothing is re-decided; the seams only observe.

Usage:
  python zone_dedup_lifecycle_measure.py --run-id run1
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # for the composition import

OUT_DIR = REPO_ROOT / "06_RESEARCH" / "results" / "zone_dedup_lifecycle"

#: LEG 4 frozen baseline (published, pre-registered in the design note).
BASELINE = {
    "htf_batches": 2979,
    "merged_pois": 43004,
    "passed_validation": 2021,
    "armed": 30,
    "duplicates_suppressed": 1991,
    "skipped_tracked": 0,
    "routes": 10,
    "placed": 4,
    "fills": 3,
    "trades": 3,
}

# ---------------------------------------------------------------------- #
# logging-only observation seams (restored in finally)
# ---------------------------------------------------------------------- #

_RUNTIMES: list = []
_SWEEPS: list[dict] = []
_ORIG: dict = {}


def _reset_seams() -> None:
    _RUNTIMES.clear()
    _SWEEPS.clear()
    _ORIG.clear()
    for module in list(sys.modules):
        if module.endswith("zone_dedup_lifecycle_measure"):
            continue


def install_seams() -> list:
    """Wrap MultiTFProductRuntime.__init__ + adapter._retire_dead_keys."""
    def restore_all():
        for module, name, original in _ORIG.values():
            setattr(module, name, original)

    def wrap(module, name, wrapper):
        original = getattr(module, name)
        _ORIG[(id(module), name)] = (module, name, original)
        setattr(module, name, wrapper)
        return original

    import smc.orchestration.multi_tf_runtime as rt
    import smc.backtest.pipeline_adapter as pa

    def observing_init(self, *args, **kwargs):
        original = _ORIG[(id(rt), "MultiTFProductRuntime")][2]
        original(self, *args, **kwargs)
        _RUNTIMES.append(self)

    wrap(rt, "MultiTFProductRuntime", observing_init)

    original_retire = pa.PipelineAdapter._retire_dead_keys

    def observing_retire(self, pruned_ids, retain, bar_index):
        before = None
        dedup = self._dedup_registry
        if dedup is not None:
            before = (dedup.retired_total, len(dedup._zones))
        original_retire(self, pruned_ids, retain, bar_index)
        if dedup is not None and before is not None:
            after = (dedup.retired_total, len(dedup._zones))
            if after != before:
                _SWEEPS.append({
                    "bar_index": bar_index,
                    "engine_pruned_sent": list(pruned_ids),
                    "retired_total_after": after[0],
                    "live_keys_after": after[1],
                })

    wrap(pa.PipelineAdapter, "_retire_dead_keys", observing_retire)
    return restore_all


# ---------------------------------------------------------------------- #
# driver
# ---------------------------------------------------------------------- #

def run_capture(run_id: str) -> dict:
    import phase3_structure_funnel as funnel

    out_root = OUT_DIR / run_id / "_funnel_capture"
    out_root.parent.mkdir(parents=True, exist_ok=True)
    _reset_seams()
    restore = install_seams()
    args = argparse.Namespace(
        tag=run_id,
        out_root=str(out_root),
        load_from="2025-05-01",
        exec_from="2025-06-01",
        exec_to="2025-11-30",
        cost_config=None,
        episode_store=None,
    )
    t0 = time.perf_counter()
    try:
        summary = funnel.run(args)
    finally:
        restore()
    elapsed = round(time.perf_counter() - t0, 1)

    runtime = _RUNTIMES[-1] if _RUNTIMES else None
    dedup = runtime.dedup if runtime is not None else None
    retire = {
        "retired_total": dedup.retired_total if dedup else None,
        "retire_misses": dedup.retire_misses if dedup else None,
        "live_keys": dedup.live_keys if dedup else None,
        "n_sweeps_with_retirement": len(_SWEEPS),
        "sweep_head": _SWEEPS[:5],
        "sweep_tail": _SWEEPS[-5:],
        "registry_bound": (runtime is not None),
    }

    # The composition's summary is FLAT (htf_batches / merged_pois /
    # passed_validation / armed / duplicates_suppressed / ...); parse
    # the pre-registered gate values directly off it.
    parsed = {
        "banner": "DIAGNOSTIC — NOT EDGE. LEG 5b implementation measurement.",
        "design": "06_RESEARCH/ZONE_DEDUP_LIFECYCLE_DESIGN.md (R1–R8, ACCEPT 2026-10-20)",
        "run_id": run_id,
        "runtime_seconds": elapsed,
        "funnel": summary,
        "retirement": retire,
        "baseline": BASELINE,
        "gate_a": {
            "htf_batches_match": summary.get("htf_batches") == BASELINE["htf_batches"],
            "merged_match": summary.get("merged_pois") == BASELINE["merged_pois"],
            "passed_match": summary.get("passed_validation") == BASELINE["passed_validation"],
        },
        "gate_b": {"retired_total_ge_1": bool(retire["retired_total"] and retire["retired_total"] >= 1)},
        "gate_c": {
            "armed_after": summary.get("armed"),
            "armed_baseline": BASELINE["armed"],
            "armed_delta": (summary.get("armed") - BASELINE["armed"]
                            if isinstance(summary.get("armed"), int) else None),
            "skip_dedup_after": summary.get("duplicates_suppressed"),
            "skip_dedup_delta": (summary.get("duplicates_suppressed") - BASELINE["duplicates_suppressed"]
                                 if isinstance(summary.get("duplicates_suppressed"), int) else None),
            "pass_to_arm_pct": (round(100.0 * summary.get("armed", 0) / summary.get("passed_validation", 0), 2)
                                if summary.get("passed_validation") else None),
            "skipped_tracked": summary.get("skipped_tracked"),
        },
    }
    out = OUT_DIR / run_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(
        json.dumps(parsed, indent=2, default=str), encoding="utf-8")
    with gzip.open(out / "retire_sweeps.jsonl.gz", "wt", encoding="utf-8") as fh:
        for sweep in _SWEEPS:
            fh.write(json.dumps(sweep, default=str) + "\n")
    print(json.dumps({
        "run": run_id, "elapsed_s": elapsed,
        "funnel": {k: parsed["funnel"].get(k) for k in
                   ("htf_batches", "merged_pois", "passed_validation", "armed",
                    "duplicates_suppressed", "skipped_tracked", "routes",
                    "placed", "fills", "trades")},
        "retirement": {k: retire[k] for k in
                       ("retired_total", "retire_misses", "live_keys",
                        "n_sweeps_with_retirement")},
        "gate_a": parsed["gate_a"],
    }, indent=2, default=str), flush=True)
    return parsed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default="run1")
    args = ap.parse_args()
    run_capture(args.run_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
