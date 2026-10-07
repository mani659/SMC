#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Frozen-window funnel measurement — NEW seek/scan contract (Option B).

Lead Architect directive (2026-10-05): the first full funnel + trade
outcome measurement under the accepted seek/scan redesign on the FROZEN
Phase 4 window. MEASUREMENT ONLY — no production logic changes, no
threshold fishing, no window shopping, no expectancy/edge claims
(all PnL labelled diagnostic, n=trades).

Composition (imported, NOT forked): ``phase3_structure_funnel.run`` —
``MultiTFProductRuntime.run_batch`` (H4+H1 detection, D1→M8) →
``PipelineEngine.arm_at`` (NEW posture classification) →
``PipelineAdapter.generate_candidates`` (post-redesign ``_may_route``:
touch no longer terminates the seek; REVALIDATION gate via
``market_reentered_zone``) → ``BacktestRunner`` (risk → pending limits →
R9 intents → manage). Because the composition imports the production
modules, the redesign is measured by simply running it — no patching.

Window (FROZEN, identical to Phase 4): M1 load 2025-08-01, exec
2025-09-01 → 2025-11-30 (3 months M5). Missing data fails loudly.

Extra instrumentation (harness-local, restored in ``finally``):
  * posture mix on armed POIs (``SeekPosture`` from the engine episode);
  * exit mix (full SL / BE scratch / TP / friday_eod / other) from the
    trade report;
  * TP non-null rate on PLACED orders (order book);
  * entry_anchor distribution (adapter context, honest-absent allowed).

Artifacts: ``results/frozen_funnel_new_contract/run{1,2}/`` (the Phase 3
composition's own artifacts) + ``summary.json`` (this wrapper: funnel,
posture mix, exit mix, TP rate, determinism byte-check, comparison
anchors). Report:
``06_RESEARCH/FROZEN_FUNNEL_NEW_CONTRACT_REPORT.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

LOCKED_LOAD = "2025-08-01"
LOCKED_FROM = "2025-09-01"
LOCKED_TO = "2025-11-30"

OUT_ROOT = REPO_ROOT / "06_RESEARCH" / "results" / "frozen_funnel_new_contract"
SUMMARY_JSON = OUT_ROOT / "summary.json"
REPORT_MD = REPO_ROOT / "06_RESEARCH" / "FROZEN_FUNNEL_NEW_CONTRACT_REPORT.md"

ANCHORS = {
    "phase4_pre_redesign": {
        "window": "exec 2025-09-01 → 2025-11-30 (same window)",
        "armed": 17, "routes": 8, "fills": 1, "trades": 1,
        "note": "BE-scratch fill +0.0715 diagnostic; pre-redesign contract",
    },
    "stage3_lifecycle_pack": {
        "window": "exec 2025-06-01 → 2025-11-30 (pack window, 6 months)",
        "open_scan_share_pct": 78.33, "routes_replay": 196,
        "note": "pre-pillar replay visibility, not the full product path",
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _exit_mix(run_root: Path) -> dict:
    """Exit mix from report.json: ``close_kind`` counts + BE-scratch note.

    The trade record's exit field is ``close_kind`` (stop_loss /
    take_profit / friday_eod / ...). BE scratch (the break-even latch) is
    the |pnl| < 0.15 stop_loss class — Phase 4's +0.0715 signature — and
    is counted separately for readability (it is a SUBSET of stop_loss,
    not an additive kind).
    """
    report_path = run_root / "report.json"
    mix: dict = {}
    if not report_path.exists():
        return mix
    data = json.loads(report_path.read_text())
    for row in data.get("trades", []):
        kind = str(row.get("close_kind") or row.get("kind") or "other")
        mix[kind] = mix.get(kind, 0) + 1
        try:
            pnl = float(row.get("pnl"))
        except (TypeError, ValueError):
            continue
        if kind == "stop_loss" and abs(pnl) < 0.15:
            mix["be_scratch_subset"] = mix.get("be_scratch_subset", 0) + 1
    return mix


def _net_pl(run_root: Path) -> float:
    report_path = run_root / "report.json"
    if not report_path.exists():
        return 0.0
    data = json.loads(report_path.read_text())
    total = 0.0
    for row in data.get("trades", []):
        try:
            total += float(row.get("pnl"))
        except (TypeError, ValueError):
            pass
    return round(total, 4)


def _tp_rate_and_entry_anchors(run_root: Path) -> dict:
    """TP non-null rate on PLACED orders + entry_anchor distribution.

    Reads placed-order provenance from the funnel summary (``placed``/
    ``placed_with_tp`` counters) and the entry-anchor mix from the
    trades' ``entry_anchor`` field (routed trades carry it; "absent" =
    the POI's anchor was not set — honest absence, never invented).
    """
    fs_path = run_root / "funnel_summary.json"
    out = {"placed": None, "placed_with_tp": None,
           "tp_non_null_rate_pct": None, "entry_anchor_distribution": {}}
    if fs_path.exists():
        fs = json.loads(fs_path.read_text())
        placed = fs.get("placed")
        with_tp = fs.get("placed_with_tp")
        out["placed"] = placed
        out["placed_with_tp"] = with_tp
        if placed:
            out["tp_non_null_rate_pct"] = round(100.0 * (with_tp or 0) / placed, 1)
    report_path = run_root / "report.json"
    anchors: dict[str, int] = {}
    if report_path.exists():
        data = json.loads(report_path.read_text())
        for row in data.get("trades", []):
            anchor = row.get("entry_anchor") or "absent"
            anchors[str(anchor)] = anchors.get(str(anchor), 0) + 1
    out["entry_anchor_distribution"] = anchors
    return out


def run_frozen(tag: str, out_root: Path) -> dict:
    """One frozen run via the Phase 3 composition (imported, not forked)."""
    out_root.mkdir(parents=True, exist_ok=True)
    import phase3_structure_funnel as p3
    args = argparse.Namespace(
        tag=tag, out_root=str(out_root),
        load_from=LOCKED_LOAD, exec_from=LOCKED_FROM, exec_to=LOCKED_TO,
    )
    return p3.run(args)


def posture_summary(run_root: Path, summary: dict) -> dict:
    """Posture mix on armed POIs — read from the harness-local posture log
    the wrapper writes during run() (see instrument_postures)."""
    log_path = run_root / "posture_log.json"
    if not log_path.exists():
        return {"available": False,
                "note": "posture log absent — instrument_postures not wired"}
    log = json.loads(log_path.read_text())
    counts: dict[str, int] = {}
    for posture in log.values():
        counts[posture] = counts.get(posture, 0) + 1
    return {"available": True, "armed_logged": len(log), "counts": counts}


def instrument_postures(out_root: Path) -> object:
    """Wrap ``PipelineEngine.arm_at`` to log each armed POI's posture.

    Harness-local instrumentation (FR-4 pattern): wraps, never replaces —
    the original runs unchanged; the wrapper reads the episode AFTER the
    original call and restores in ``finally`` by the caller.
    """
    from smc.orchestration import engine as engine_module

    log: dict[str, str] = {}
    original_arm = engine_module.PipelineEngine.arm_at

    def logging_arm_at(self, poi, arm_bar, **kw):
        original_arm(self, poi, arm_bar, **kw)
        episode = self._episodes.get(poi.id)
        if episode is not None:
            log[poi.id] = episode.posture.value
        return None

    engine_module.PipelineEngine.arm_at = logging_arm_at
    return type("PostureInstrument", (), {
        "log": log,
        "restore": staticmethod(
            lambda: setattr(engine_module.PipelineEngine, "arm_at",
                            original_arm)),
    })()


def write_posture_log(instr, run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "posture_log.json").write_text(
        json.dumps(instr.log, indent=2), encoding="utf-8")
    instr.restore()


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    summaries: dict[str, dict] = {}
    for tag in ("run1", "run2"):
        print(f"[fn] === frozen run {tag} ===", flush=True)
        instr = instrument_postures(OUT_ROOT / tag)
        try:
            summaries[tag] = run_frozen(tag, OUT_ROOT / tag)
        finally:
            write_posture_log(instr, OUT_ROOT / tag)

    r1, r2 = summaries["run1"], summaries["run2"]
    p1, p2 = OUT_ROOT / "run1", OUT_ROOT / "run2"

    # ---- Determinism: byte-identical trades.csv + report.json ---------- #
    byte_check: dict = {}
    for name in ("trades.csv", "report.json"):
        f1, f2 = p1 / name, p2 / name
        if f1.exists() and f2.exists():
            same = f1.read_bytes() == f2.read_bytes()
            byte_check[name] = {
                "byte_identical": same,
                "sha256_run1": _sha256(f1),
                "sha256_run2": _sha256(f2),
            }
        else:
            byte_check[name] = {"byte_identical": None, "reason": "file absent"}

    ignore = {"runtime_seconds", "tag"}
    semantic_diffs = {
        key: [r1.get(key), r2.get(key)]
        for key in r1
        if key not in ignore and r1.get(key) != r2.get(key)
    }
    determinism = {
        "byte_check": byte_check,
        "semantic_diffs": semantic_diffs,
        "semantic_equal": not semantic_diffs,
        "verdict": ("PASS" if not semantic_diffs
                    and all(v.get("byte_identical") for v in byte_check.values())
                    else "FAIL"),
    }

    post1 = posture_summary(p1, r1)
    exit1 = _exit_mix(p1)
    tp1 = _tp_rate_and_entry_anchors(p1)
    net1 = _net_pl(p1)

    summary = {
        "directive": "frozen-window funnel measurement — NEW seek/scan contract",
        "diagnostic_only": "NOT performance — no expectancy/edge claims; PnL diagnostic n=trades",
        "window": {"load_from": LOCKED_LOAD, "exec_from": LOCKED_FROM,
                   "exec_to": LOCKED_TO, "exec_tf": "M5", "frozen": True},
        "composition": ("phase3_structure_funnel.run imported — the product "
                        "path with the accepted seek/scan redesign; no "
                        "strategy code patched"),
        "funnel_run1": {
            "bars_m5": r1.get("bars_m5"),
            "htf_batches": r1.get("htf_batches"),
            "batch_errors": r1.get("batch_errors"),
            "detected_raw": r1.get("detected_raw_by_tf"),
            "detected_raw_total": (r1.get("detected_raw") if
                                   isinstance(r1.get("detected_raw"), int)
                                   else None),
            "merged_pois": r1.get("merged_pois"),
            "passed_validation": r1.get("passed_validation"),
            "pillar_first_failure": r1.get("pillar_first_failure"),
            "armed": r1.get("armed"),
            "armed_m8": r1.get("armed_m8"),
            "scans": r1.get("scanned_pois"),
            "routes": r1.get("routes"),
            "routes_by_trigger": r1.get("routes_by_trigger"),
            "placed": r1.get("placed"),
            "intents": {k: r1.get(k) for k in
                        ("intents_armed", "intents_placed", "intents_expired")},
            "fills": r1.get("fills"),
            "trades": r1.get("trades"),
        },
        "posture_mix_run1": post1,
        "exit_mix_run1": exit1,
        "tp_and_entry_anchor_run1": tp1,
        "net_pl_diagnostic_run1": net1,
        "determinism": determinism,
        "comparison_anchors": ANCHORS,
        "run2_mirror": {
            "armed": r2.get("armed"), "routes": r2.get("routes"),
            "fills": r2.get("fills"), "trades": r2.get("trades"),
            "runtime_seconds": r2.get("runtime_seconds"),
        },
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, default=str),
                            encoding="utf-8")

    print(json.dumps({
        "window": summary["window"],
        "armed": r1.get("armed"), "routes": r1.get("routes"),
        "routes_by_trigger": r1.get("routes_by_trigger"),
        "placed": r1.get("placed"), "fills": r1.get("fills"),
        "trades": r1.get("trades"),
        "posture_mix": post1.get("counts"),
        "exit_mix": exit1, "tp_rate": tp1.get("tp_non_null_rate_pct"),
        "net_pl_diagnostic": net1,
        "determinism": determinism["verdict"],
    }, indent=2, default=str))
    print(f"[fn] wrote {SUMMARY_JSON}")
    return 0 if determinism["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
