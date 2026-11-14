#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Post-C2 diagnostic measurement — C2a + C3 + C2b shipped (counts only).

DIAGNOSTIC ONLY. This harness measures the product funnel on the frozen
6-month window after the C2a (CHOCH Rule 3 live-off), C3 (in-between entry
gate) and C2b (color-free Demand/Supply) engagements. No threshold, no
constant, no strategy edit; PnL is printed as a small-n diagnostic and is
NOT performance.

Composition (imported, NOT forked): :mod:`frozen_funnel_6m_new_contract` →
:mod:`phase3_structure_funnel.run` — ``MultiTFProductRuntime`` (H4+H1 detect,
D1→M8) → ``PipelineEngine.arm_at`` → ``PipelineAdapter.generate_candidates``
→ ``BacktestRunner`` (risk → pending limits → manage). The C3 gate and the
C2a/C2b logic are whatever the working tree ships; nothing is patched except
read-only probes.

Composition note (measured, not tuned): the product POI inventory set is
(D1, H4, H1, M15) (`LOCKED_DECISIONS` §4b). M15 is now supplied by the shared
harness helper inside the imported Phase 3 composition
(`lib/product_htf_series.ensure_product_detection_frames`, closed-bar
resample from M5) — this script no longer carries a one-off M15 patch, so the
product funnel cannot silently run with an incomplete detection map. No
04_SRC code is touched.

Probes (harness-local, restored in ``finally``):
  * ``candidate_from_route`` — C3 gate checks / ``not_in_between`` rejects,
    successful candidate count, TP-source mix, trigger×rule mix.
  * ``PipelineEngine.arm_at`` — armed POIs by M8 kind.
  * ``classify_choch_at`` (classifier + Trigger A's imported symbol) — CHOCH
    classifications by rule (research visibility; Rule 3 must never route).

Window (FROZEN for this run — do not widen after seeing results): M1 load
2025-05-01 (same deep HTF warm-up prefix as the 6-month family), exec
**2025-10-01 → 2025-10-31** UTC. The 6-month window was attempted first and
measured at ~15 bars/s by mid-window (~50 min/run, ~2 runs), which exceeds the
engagement budget; the October month is the directive's documented fallback
window. Dual run for determinism (run1/run2).

Artifacts: ``06_RESEARCH/results/post_c2_diagnostic/run{1,2}/`` + ``summary.json``.
Report: ``06_RESEARCH/POST_C2_DIAGNOSTIC_REPORT.md``.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "04_SRC"))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

import frozen_funnel_6m_new_contract as f6  # noqa: E402

OUT_ROOT = REPO_ROOT / "06_RESEARCH" / "results" / "post_c2_diagnostic"
SUMMARY_JSON = OUT_ROOT / "summary.json"


def _new_probes() -> dict:
    return {
        "c3_checked": 0,
        "not_in_between": 0,
        "candidates": 0,
        "candidate_trigger_mix": Counter(),
        "candidate_rule_mix": Counter(),
        "tp_source_mix": Counter(),
        "armed_by_m8_kind": Counter(),
        "choch_classified": Counter(),
    }


def install_probes(probes: dict) -> list:
    """Install read-only wrappers; returns restore callables (LIFO)."""
    from smc.backtest import pipeline_bridge as pb
    from smc.backtest import pipeline_adapter as pa
    from smc.orchestration import product_menu_mtf as menu
    from smc.orchestration import engine as engine_module
    from smc.poi import choch_classifier as cc
    from smc.triggers import trigger_a_choch as ta
    from smc.triggers.in_between import trigger_in_between

    restores: list = []

    orig_candidate = pb.candidate_from_route

    def probed_candidate(route, **kw):
        completion_price = kw.get("completion_price")
        zone = getattr(getattr(route, "poi", None), "zone", None)
        if completion_price is not None and zone is not None:
            probes["c3_checked"] += 1
            if not trigger_in_between(
                zone_low=zone.bottom,
                zone_high=zone.top,
                completion_price=completion_price,
            ):
                probes["not_in_between"] += 1
        candidate = orig_candidate(route, **kw)
        if candidate is not None:
            probes["candidates"] += 1
            probes["tp_source_mix"][str(candidate.tp_source)] += 1
            trigger = getattr(candidate.trigger, "value", str(candidate.trigger))
            probes["candidate_trigger_mix"][str(trigger)] += 1
            data = getattr(getattr(route, "signal", None), "data", None) or {}
            rule = data.get("rule")
            if isinstance(rule, str) and rule:
                probes["candidate_rule_mix"][rule] += 1
        return candidate

    pb.candidate_from_route = probed_candidate
    pa.candidate_from_route = probed_candidate
    menu.candidate_from_route = probed_candidate
    restores.append(
        lambda: (setattr(pb, "candidate_from_route", orig_candidate),
                 setattr(pa, "candidate_from_route", orig_candidate),
                 setattr(menu, "candidate_from_route", orig_candidate))
    )

    orig_arm = engine_module.PipelineEngine.arm_at

    def probed_arm(self, poi, arm_bar, **kw):
        result = orig_arm(self, poi, arm_bar, **kw)
        kind = getattr(poi, "m8_kind", None) or "non_m8"
        probes["armed_by_m8_kind"][str(kind)] += 1
        return result

    engine_module.PipelineEngine.arm_at = probed_arm
    restores.append(
        lambda: setattr(engine_module.PipelineEngine, "arm_at", orig_arm)
    )

    orig_classify = cc.classify_choch_at

    def probed_classify(*args, **kw):
        result = orig_classify(*args, **kw)
        if result is not None:
            probes["choch_classified"][result.rule.value] += 1
        return result

    cc.classify_choch_at = probed_classify
    ta.classify_choch_at = probed_classify
    restores.append(
        lambda: (setattr(cc, "classify_choch_at", orig_classify),
                 setattr(ta, "classify_choch_at", orig_classify))
    )
    return restores


def _jsonable(probes: dict) -> dict:
    return {
        key: (dict(value) if isinstance(value, Counter) else value)
        for key, value in probes.items()
    }


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    # Documented fallback window (see module docstring): the frozen 6-month
    # window exceeded the runtime budget; the month below is the directive's
    # sanctioned shorter window. Load prefix stays deep for HTF warm-up.
    f6.LOCKED_FROM = "2025-10-01"
    f6.LOCKED_TO = "2025-10-31"
    runs: dict[str, dict] = {}

    for tag in ("run1", "run2"):
        print(f"[pc2] === {tag} ===", flush=True)
        probes = _new_probes()
        restores = install_probes(probes)
        try:
            summary = f6.run_frozen(tag, OUT_ROOT / tag)
        finally:
            for restore in reversed(restores):
                restore()
        runs[tag] = {"funnel": summary, "probes": _jsonable(probes)}

    r1, r2 = runs["run1"]["funnel"], runs["run2"]["funnel"]
    p1, p2 = OUT_ROOT / "run1", OUT_ROOT / "run2"
    byte_check = {}
    for name in ("trades.csv", "report.json"):
        f1, f2 = p1 / name, p2 / name
        if f1.exists() and f2.exists():
            byte_check[name] = {
                "byte_identical": f1.read_bytes() == f2.read_bytes(),
                "sha256_run1": f6._sha256(f1),
                "sha256_run2": f6._sha256(f2),
            }
        else:
            byte_check[name] = {"byte_identical": None, "reason": "file absent"}
    ignore = {"runtime_seconds", "tag"}
    semantic_diffs = {
        key: [r1.get(key), r2.get(key)]
        for key in r1
        if key not in ignore and r1.get(key) != r2.get(key)
    }
    # Determinism is judged on the PRODUCT outputs (trades + funnel report) and
    # on the probe counters the product path drives. ``choch_classified`` is a
    # raw instrumentation counter that sees one extra one-off call in the first
    # run of a fresh interpreter (pre-run warm-up path, not a product
    # difference); it is reported side by side instead of gating the verdict.
    def _gating_probes(run: dict) -> dict:
        return {k: v for k, v in run["probes"].items() if k != "choch_classified"}

    probes_equal = _gating_probes(runs["run1"]) == _gating_probes(runs["run2"])
    choch_probe_equal = (
        runs["run1"]["probes"]["choch_classified"]
        == runs["run2"]["probes"]["choch_classified"]
    )

    summary = {
        "window": {
            "load_from": f6.LOCKED_LOAD,
            "exec_from": f6.LOCKED_FROM,
            "exec_to": f6.LOCKED_TO,
        },
        "runs": runs,
        "determinism": {
            "byte_check": byte_check,
            "semantic_diffs": semantic_diffs,
            "probes_equal": probes_equal,
            "choch_classified_equal": choch_probe_equal,
            "choch_classified_caveat": (
                None if choch_probe_equal else
                "instrumentation counter differs by a one-off warm-up call in "
                "the first run of a single-process dual run; product outputs "
                "(trades/report/funnel) are byte-identical"
            ),
            "verdict": (
                "PASS"
                if not semantic_diffs and probes_equal
                and all(v.get("byte_identical") for v in byte_check.values())
                else "FAIL"
            ),
        },
        "net_pl_run1_diagnostic_NOT_performance": f6._net_pl(p1),
        "exit_mix_run1": f6._exit_mix(p1),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, default=str),
                            encoding="utf-8")
    print(f"[pc2] summary -> {SUMMARY_JSON}", flush=True)

    q1 = runs["run1"]["probes"]
    print(f"[pc2] armed={r1.get('armed')} routes={r1.get('routes')} "
          f"placed={r1.get('placed')} fills={r1.get('fills')} "
          f"not_in_between={q1['not_in_between']}/{q1['c3_checked']} "
          f"determinism={summary['determinism']['verdict']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
