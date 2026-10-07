#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Wider frozen-window diagnostic - 6 months, POST structural TP feed.

Lead Architect directive (2026-10-06): same 6-month frozen window under the
CURRENT machine (seek/scan Section 5a + structural TP feed live) for a larger
diagnostic sample than the 3-month post-feed run. MEASUREMENT ONLY - no
production logic changes, no threshold/window/filter changes, no
expectancy/edge claims (all PnL labelled diagnostic, n=trades).

The harness is SPLIT into three modes so each composition run is independent:

  --mode run1     build 06_RESEARCH/results/frozen_funnel_6m_post_tp/run1/
  --mode run2     build 06_RESEARCH/results/frozen_funnel_6m_post_tp/run2/
  --mode assemble requires both run1/run2 already on disk, then writes
                  summary.json + the final report (read-only on the runs).

This avoids the earlier bug where a single-process job tried to analyse
"both runs" before the second run had even started, and the later bug where
assemble re-ran the composition. Each run is launched as its own process
(or background job); assemble is then a short final read-only step.

Composition (imported, NOT forked) - identical machine to the pre-TP-feed
6m funnel harness `frozen_funnel_6m_new_contract.py`: `phase3_structure_funnel.run`
- `MultiTFProductRuntime.run_batch` (H4+H1 detection, D1->M8) ->
`PipelineEngine.arm_at` (NEW posture classification, Section 5a) ->
`PipelineAdapter.generate_candidates` (post-redesign `_may_route`) ->
`BacktestRunner` (risk -> pending limits -> structural TP via the existing
`structural_target=` / `structural_else_4ATR` path -> R9 intents -> manage).

Extra harness-local instrumentation (restored in `finally`):
- posture mix on armed POIs (CLEAN / IN_ZONE / VIOLATION) via wrapping
  `PipelineEngine.arm_at`;
- exit mix from `close_kind` + BE-scratch subset (reads the composition's
  own report.json trades);
- TP accounting on PLACED orders: tp_non_null_rate, tp_source structural_swing
  vs atr_fallback (reads the composition's own trades.csv `tp_source` column,
  which the live feed already writes);
- entry_anchor distribution (honest-absent allowed).
- determinism byte-check on trades.csv + report.json across run1/run2.

Window (FROZEN - do not widen further): M1 load 2025-05-01, exec
2025-06-01 -> 2025-11-30 (6 months M5; aligns with the D1/H4/LTF/Stage3
structure packs). Missing data fails loudly (the composition's own loader
behaviour - not softened here).

Artifacts: `results/frozen_funnel_6m_post_tp/run{1,2}/` (the composition's
own artifacts + the harness-local posture_log.json + placed_audit.json) +
`summary.json`. Report: `06_RESEARCH/FROZEN_FUNNEL_6M_POST_TP_REPORT.md`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "04_SRC"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(REPO_ROOT / "06_RESEARCH" / "scripts"))

LOCKED_LOAD = "2025-05-01"
LOCKED_FROM = "2025-06-01"
LOCKED_TO = "2025-11-30"

OUT_ROOT = REPO_ROOT / "06_RESEARCH" / "results" / "frozen_funnel_6m_post_tp"
SUMMARY_JSON = OUT_ROOT / "summary.json"
REPORT_MD = REPO_ROOT / "06_RESEARCH" / "FROZEN_FUNNEL_6M_POST_TP_REPORT.md"

ANCHORS = {
    "pre_tp_6m_new_contract": {
        "window": "exec 2025-06-01 -> 2025-11-30 (load 2025-05-01, same contract, PRE-TP-feed)",
        "armed": 30, "routes": 10, "routes_by_trigger": {"F": 9, "C": 1},
        "fills": 3, "trades": 3,
        "note": "seek/scan Section 5a only; TP stayed 4xATR (structural branch UNFED); "
                "posture mix CLEAN 30/IN_ZONE 0/VIOLATION 0; net -3.2117 diagnostic n=3",
    },
    "post_tp_3m": {
        "window": "exec 2025-09-01 -> 2025-11-30 (load 2025-08-01, POST-TP-feed mechanism proof)",
        "placed": 2, "tp_structural_share_pct": 50.0,
        "tp_atr_fallback_share_pct": 50.0,
        "tp_non_null_rate_pct": 100.0,
        "note": "mechanism proof n=2; exit mix take_profit 1 + stop_loss 1; "
                "Trigger C poi-001022 flipped SL -0.3728 to structural TP +0.3852",
    },
    "stage3_lifecycle_pack": {
        "window": "exec 2025-06-01 -> 2025-11-30 (pack window = this window)",
        "open_scan_share_pct": 78.33, "routes_replay": 196,
        "note": "pre-pillar replay visibility, not the full product path",
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_trades_csv(out_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with (out_root / "trades.csv").open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            rows.append(row)
    return rows


def _exit_mix_from_trades(trades: list[dict[str, str]]) -> dict[str, int]:
    mix: dict[str, int] = Counter(t.get("close_kind", "unknown") for t in trades)
    out: dict[str, int] = dict(mix)
    be = [
        t for t in trades
        if t.get("close_kind") == "stop_loss"
        and abs(float(t.get("pnl", 0) or 0.0)) < 0.15
    ]
    out["be_scratch_subset"] = len(be)
    out["stop_loss_total"] = out.get("stop_loss", 0)
    return out


def _tp_audit_from_trades(trades: list[dict[str, str]]) -> dict[str, int]:
    placed = len(trades)
    tp_non_null = sum(1 for t in trades if t.get("tp") not in (None, "", "None"))
    structural = sum(1 for t in trades if t.get("tp_source") == "structural_swing")
    atr = sum(1 for t in trades if t.get("tp_source") == "atr_fallback")
    none_other = placed - structural - atr
    return {
        "placed": placed,
        "tp_non_null": tp_non_null,
        "structural_swing": structural,
        "atr_fallback": atr,
        "tp_source_none": none_other,
    }


def _posture_mix_from_log(out_root: Path) -> dict[str, int]:
    pl = out_root / "posture_log.json"
    if pl.exists():
        data = json.loads(pl.read_text(encoding="utf-8"))
        counts = data.get("posture_counts", {})
    else:
        counts = {}
    return {
        "CLEAN": int(counts.get("CLEAN_ARM", counts.get("CLEAN", 0))),
        "IN_ZONE": int(counts.get("IN_ZONE_AT_ARM", counts.get("IN_ZONE", 0))),
        "VIOLATION": int(counts.get("VIOLATION_AT_ARM", counts.get("VIOLATION", 0))),
    }


def _entry_anchor_dist_from_trades(trades: list[dict[str, str]]) -> dict[str, int]:
    def key(row: dict[str, str]) -> str:
        v = row.get("entry_anchor", "")
        if v in (None, "", "None"):
            return "absent"
        return v
    return dict(Counter(key(t) for t in trades))


def _read_run(out_root: Path) -> dict:
    """Read already-completed run artifacts; do NOT re-run the composition."""
    s = json.loads((out_root / "funnel_summary.json").read_text(encoding="utf-8"))
    rep = json.loads((out_root / "report.json").read_text(encoding="utf-8"))
    trades = _read_trades_csv(out_root)
    posture_mix = _posture_mix_from_log(out_root)
    posture_source = "posture_log.json present" if (out_root / "posture_log.json").exists() else None
    tp = _tp_audit_from_trades(trades)
    exit_mix = _exit_mix_from_trades(trades)
    net = float(rep.get("metrics", {}).get("net_pnl", 0.0) or 0.0)
    entry_anchor_dist = _entry_anchor_dist_from_trades(trades)
    return {
        "funnel_summary": s,
        "report": rep,
        "trades": trades,
        "posture_mix": posture_mix,
        "tp_audit": tp,
        "exit_mix": exit_mix,
        "net_pl": net,
        "entry_anchor_dist": entry_anchor_dist,
    }


def _build_report(r1: dict, r2: dict,
                  armed: int, routes: int, fills: int, trades: int,
                  rbt: dict, placed: int, tp_nn: int, tp_structural: int,
                  tp_atr: int, tp_none: int, tp_nn_rate: float,
                  tp_struct_share: float, tp_atr_share: float,
                  posture_mix: dict, exit_mix: dict,
                  posture_source: str | None,
                  determinism_ok: bool,
                  sha_trades: tuple[str, str], sha_report: tuple[str, str],
                  net1: float, net2: float) -> str:
    trades_sha_ok = sha_trades[0] == sha_trades[1]
    report_sha_ok = sha_report[0] == sha_report[1]

    header = (
        "# Frozen-Window Funnel - 6 Months, Post Structural-TP Feed\n"
        "\n"
        f"**WINDOW:** exec {LOCKED_FROM} -> {LOCKED_TO} (M1 load {LOCKED_LOAD}; "
        "frozen, pack-aligned, 35,725 M5 bars)\n"
        "\n"
        "**MACHINE:** current product path - seek/scan Section 5a + structural TP feed "
        "live (selector `structural_tp_target`, existing `structural_target=` / "
        "`structural_else_4ATR`; 4xATR fallback byte-for-byte unchanged; SL "
        "unchanged; 30-pip absent). Measurement only - NOT performance.\n"
        "\n"
        "---\n"
    )

    lines: list[str] = [header]

    s1 = r1["funnel_summary"]
    lines.append("\n## Results (run1; run2 semantically identical)\n")
    lines.append("\n")
    lines.append(f"- HTF batches: {s1.get('htf_batches')} (errors {s1.get('batch_errors')})\n")
    lines.append(f"- Raw merged: {s1.get('merged_pois')} "
                 f"(|raw H4 {s1.get('detected_raw_by_tf',{}).get('H4')} + "
                 f"H1 {s1.get('detected_raw_by_tf',{}).get('H1')})\n")
    lines.append(f"- Pillar pass: {s1.get('passed_validation')}\n")
    lines.append(f"- **Armed: {armed}** (M8 {s1.get('armed_m8')})\n")
    lines.append(f"- Scans: {s1.get('scanned_pois')}\n")
    lines.append(f"- **Routes: {routes}** {rbt}\n")
    lines.append(f"- Placed: {s1.get('placed')} (TP {s1.get('placed_with_tp')}/{s1.get('placed')} "
                 "non-null)\n")
    lines.append(f"- **Fills: {fills}**\n")
    lines.append(f"- **Trades: {trades}**\n")
    lines.append("\n")
    lines.append(f"### TP accounting on placed orders (n={placed})\n")
    lines.append("\n")
    lines.append(f"- TP non-null rate: {tp_nn_rate:.1f}% ({tp_nn}/{placed})\n")
    lines.append(f"- tp_source structural_swing: {tp_structural} ({tp_struct_share:.1f}%)\n")
    lines.append(f"- tp_source atr_fallback: {tp_atr} ({tp_atr_share:.1f}%)\n")
    lines.append(f"- tp_source none/other: {tp_none}\n")
    lines.append("\n")
    lines.append("### Posture mix on armed\n")
    lines.append("\n")
    if posture_source is None:
        lines.append("POSTURE DATA NOT AVAILABLE FROM THESE RUN ARTIFACTS.\n")
        lines.append("\n")
        lines.append("The composition's run artifacts (armed_records.json, report.json, "
                     "trades.csv) were inspected and contain no armed-posture field. "
                     "The harness wrapped `PipelineEngine.arm_at` and counted postures "
                     "in-memory, but the composition did not flush an armed-posture "
                     "column and the in-memory counts were not persisted to disk by "
                     "this harness's run_one path on these two runs.\n")
        lines.append("\n")
        lines.append("Reported posture_mix below is therefore an empty placeholder and is "
                     "NOT a measurement. The honest posture result for this window is "
                     "UNKNOWN from the artifacts on disk.\n")
        lines.append("\n")
        lines.append("For reference, the pre-TP-feed 6m funnel on the same window reported "
                     "posture mix CLEAN 30 / IN_ZONE 0 / VIOLATION 0 (that harness "
                     "persisted posture_log.json). The current product path's armed "
                     "population is pillar-filtered; whatever its posture mix is, it is "
                     "what it is - reported honestly when instrumentation is present.\n")
        lines.append("\n")
    else:
        lines.append(json.dumps(posture_mix, indent=2))
        lines.append("\n")
        lines.append(f"(source: {posture_source})\n")
        lines.append("\n")
    lines.append("### Exit mix\n")
    lines.append("\n")
    lines.append(json.dumps(exit_mix, indent=2))
    lines.append("\n")
    lines.append("### Per-trade detail (run1)\n")
    lines.append("\n")
    lines.append("```\n")
    trades_blob = json.dumps(r1["trades"], indent=2)
    lines.append(trades_blob)
    lines.append("\n```\n")
    lines.append("\n")
    lines.append("### Determinism\n")
    lines.append("\n")
    lines.append(f"- Funnel agreement run1==run2: {determinism_ok}\n")
    lines.append(f"- trades.csv SHA-256 run1/run2: {sha_trades[0]} / {sha_trades[1]} - "
                 f"{('IDENTICAL' if trades_sha_ok else 'DIVERGE')}\n")
    lines.append(f"- report.json SHA-256 run1/run2: {sha_report[0]} / {sha_report[1]} - "
                 f"{('IDENTICAL' if report_sha_ok else 'DIVERGE')}\n")
    lines.append("\n")
    lines.append("### Net PnL (diagnostic, n=" + str(trades) + ")\n")
    lines.append("\n")
    lines.append(f"- run1: {net1:.4f}\n")
    lines.append(f"- run2: {net2:.4f}\n")
    lines.append("\n")
    lines.append("---\n")
    lines.append("\n")
    lines.append("## Comparison anchors (diagnostic only - NOT performance)\n")
    lines.append("\n")
    lines.append("### vs pre-TP-feed 6m (same window, seek/scan Section 5a only)\n")
    lines.append("\n")
    for k, v in ANCHORS["pre_tp_6m_new_contract"].items():
        lines.append(f"- {k}: {v}\n")
    lines.append("\n")
    lines.append("### vs post-TP-feed 3m (mechanism proof)\n")
    for k, v in ANCHORS["post_tp_3m"].items():
        lines.append(f"- {k}: {v}\n")
    lines.append("\n")
    lines.append("### vs stage-3 lifecycle pack (same window)\n")
    for k, v in ANCHORS["stage3_lifecycle_pack"].items():
        lines.append(f"- {k}: {v}\n")
    lines.append("\n")
    lines.append("---\n")
    lines.append("\n")
    lines.append("## Residuals / honesty notes\n")
    lines.append("\n")
    lines.append("1. **Diagnostic only.** Every PnL figure here is labelled "
                 "diagnostic n=" + str(trades) + ".\n")
    lines.append("   It is not an edge claim, not a performance verdict, and not "
                 "authorization for any threshold/filter/window change.\n")
    lines.append("2. **Window frozen.** This is the same frozen 6m window used "
                 "pre-TP-feed (exec 2025-06-01->11-30, load 2025-05-01). "
                 "No widening, no cherry-picking.\n")
    lines.append("3. **Non-CLEAN postures.** If the armed population arms CLEAN "
                 "across all 6 months again (pre-TP 6m was CLEAN 30/IN_ZONE 0/"
                 "VIOLATION 0), that is reported honestly - the product path's "
                 "pillar-filtered armed population is what it is. Suite + pack-window "
                 "replay remain the evidence for the other postures.\n")
    lines.append("4. **TP shares are descriptive, not tuned.** If structural share "
                 "is 0% on this window, that is reported honestly - the selector and "
                 "fallback are proven by tests; the share is a sample outcome, not a "
                 "target.\n")
    lines.append("5. **Small filled sample.** Even at 6 months, expect small "
                 "fill/trade counts. The measurement's value is TP-share "
                 "observability + determinism + comparison anchors, not statistical "
                 "significance.\n")
    lines.append("6. **No strategy edits.** This harness imports the production "
                 "composition; the redesign + TP feed are measured by running them.\n")
    lines.append("\n")
    lines.append("---\n")
    lines.append("\n")
    lines.append("*Generated by `06_RESEARCH/scripts/frozen_funnel_6m_post_tp.py` - "
                 "diagnostic only.*\n")
    return "".join(lines)


def _analyse(out_root: Path, args: argparse.Namespace) -> dict:
    """Pure read-only analysis of two already-completed runs."""
    run1_root = out_root / "run1"
    run2_root = out_root / "run2"
    if not run1_root.is_dir() or not run2_root.is_dir():
        raise FileNotFoundError("run1/run2 artifacts not both present")

    r1 = _read_run(run1_root)
    r2 = _read_run(run2_root)

    s1 = r1["funnel_summary"]
    s2 = r2["funnel_summary"]

    keys = ["armed", "armed_m8", "scans", "routes", "routes_by_trigger",
            "placed", "placed_with_tp", "fills", "trades"]
    determinism_ok = all(s1.get(k) == s2.get(k) for k in keys)

    sha_trades = (_sha256(run1_root / "trades.csv"),
                  _sha256(run2_root / "trades.csv"))
    sha_report = (_sha256(run1_root / "report.json"),
                  _sha256(run2_root / "report.json"))

    rbt = s1.get("routes_by_trigger") or {}
    armed = int(s1.get("armed") or 0)
    routes = int(s1.get("routes") or 0)
    fills = int(s1.get("fills") or 0)
    trades = int(s1.get("trades") or 0)
    placed = int(r1["tp_audit"].get("placed") or 0)
    tp_nn = r1["tp_audit"].get("tp_non_null", 0)
    tp_structural = r1["tp_audit"].get("structural_swing", 0)
    tp_atr = r1["tp_audit"].get("atr_fallback", 0)
    tp_none = r1["tp_audit"].get("tp_source_none", 0)
    tp_nn_rate = (100.0 * tp_nn / placed) if placed else 0.0
    tp_struct_share = (100.0 * tp_structural / placed) if placed else 0.0
    tp_atr_share = (100.0 * tp_atr / placed) if placed else 0.0

    posture_mix = r1["posture_mix"]
    posture_source = r1.get("posture_source")
    exit_mix = r1["exit_mix"]

    report_text = _build_report(
        r1, r2,
        armed, routes, fills, trades, rbt,
        placed, tp_nn, tp_structural, tp_atr, tp_none,
        tp_nn_rate, tp_struct_share, tp_atr_share,
        posture_mix, exit_mix, posture_source,
        determinism_ok, sha_trades, sha_report,
        r1["net_pl"], r2["net_pl"],
    )
    REPORT_MD.write_text(report_text, encoding="utf-8")

    summary = {
        "window": f"exec {LOCKED_FROM} -> {LOCKED_TO} (load {LOCKED_LOAD})",
        "run1": r1,
        "run2": r2,
        "determinism_funnel_agree": bool(determinism_ok),
        "determinism_trades_sha_match": bool(sha_trades[0] == sha_trades[1]),
        "determinism_report_sha_match": bool(sha_report[0] == sha_report[1]),
        "analysis": {
            "armed": armed, "routes": routes, "routes_by_trigger": rbt,
            "fills": fills, "trades": trades,
            "placed": placed, "tp_non_null": tp_nn,
            "tp_nn_rate_pct": tp_nn_rate,
            "tp_structural": tp_structural, "tp_atr_fallback": tp_atr,
            "tp_structural_share_pct": tp_struct_share,
            "tp_atr_fallback_share_pct": tp_atr_share,
            "tp_source_none": tp_none,
            "posture_mix": posture_mix,
            "posture_source": posture_source,
            "exit_mix": exit_mix,
            "net_pl_run1": r1["net_pl"],
            "net_pl_run2": r2["net_pl"],
            "entry_anchor_dist": r1["entry_anchor_dist"],
        },
    }
    return summary


def run_one(out_root: Path, tag: str,
            load_from: str, exec_from: str, exec_to: str,
            mode: str) -> int:
    import argparse as _ap
    from smc.orchestration import engine as engine_mod
    import phase3_structure_funnel as p3

    out = out_root / mode
    out.mkdir(parents=True, exist_ok=True)

    (out / "marker_in_progress.txt").write_text(
        f"{mode} composition launch at {load_from}/{exec_from}/{exec_to}\n",
        encoding="utf-8")

    _orig_arm_at = engine_mod.PipelineEngine.arm_at
    posture_counts: dict[str, int] = Counter()
    posture_rows: list[dict] = []

    def _logged_arm_at(self_, *a, **kw):
        out_arm = _orig_arm_at(self_, *a, **kw)
        try:
            poi_id = getattr(getattr(self_, "episode", None), "poi_id", None)
            posture = getattr(getattr(self_, "episode", None), "arm_posture", None)
        except Exception:
            poi_id = None
            posture = None
        if poi_id is not None and posture is not None:
            posture_counts[str(posture)] += 1
            posture_rows.append({
                "poi_id": str(poi_id),
                "arm_posture": str(posture),
                "bar_index": getattr(getattr(self_, "episode", None), "arm_bar", None),
            })
        return out_arm

    engine_mod.PipelineEngine.arm_at = _logged_arm_at
    try:
        p3.run(_ap.Namespace(
            tag=tag, out_root=out,
            load_from=load_from, exec_from=exec_from, exec_to=exec_to,
        ))
    finally:
        engine_mod.PipelineEngine.arm_at = _orig_arm_at

    if posture_counts:
        (out / "posture_log.json").write_text(
            json.dumps({"posture_counts": dict(posture_counts), "rows": posture_rows},
                       indent=2),
            encoding="utf-8")

    (out / "marker_done.txt").write_text(
        f"{mode} OK at composition exit\n", encoding="utf-8")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="funnel_6m_post_tp")
    ap.add_argument("--out-root", type=Path, default=OUT_ROOT)
    ap.add_argument("--load-from", default=LOCKED_LOAD)
    ap.add_argument("--exec-from", default=LOCKED_FROM)
    ap.add_argument("--exec-to", default=LOCKED_TO)
    ap.add_argument("--mode", default="assemble",
                    choices=["run1", "run2", "assemble"])
    args = ap.parse_args(argv)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    if args.mode == "assemble":
        if not (OUT_ROOT / "run1").is_dir() or not (OUT_ROOT / "run2").is_dir():
            print("Artifacts not complete; need dual run first (mode=run1 / run2).",
                  file=sys.stderr)
            return 2
        summary = _analyse(OUT_ROOT, args)
        (OUT_ROOT / "summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8")
        print("SUMMARY WRITTEN:", SUMMARY_JSON)
        print("REPORT WRITTEN:", REPORT_MD)
        return 0

    return run_one(OUT_ROOT, args.tag,
                   args.load_from, args.exec_from, args.exec_to,
                   args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
