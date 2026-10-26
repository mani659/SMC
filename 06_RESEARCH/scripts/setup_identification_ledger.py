"""L2 — Setup identification ledger (Lead Architect directive 2026-10-06).

RESEARCH + EXPORT ANALYTICS ONLY: emits a human-reviewable ledger of the
setups the frozen engine IDENTIFIED on the frozen 6m window (post-TP-feed
funnel artifacts). This supports identification validation (count +
quality scoring by a human), NOT PnL edge. No trading threshold changes,
no expectancy claims, no `04_SRC/smc/**` edits.

Primary source (offline):
    06_RESEARCH/results/frozen_funnel_6m_post_tp/run1/armed_records.json
    06_RESEARCH/results/frozen_funnel_6m_post_tp/run1/funnel_summary.json
Join (when a setup routed AND filled):
    06_RESEARCH/results/hypothesis_outcome/trades_hypothesis.csv
        (run_label == "6m_post_tp_run1")

Human-scoring columns (blank by design — filled by the reviewer, never by
the script): ``verdict`` (CORRECT/PARTIAL/WRONG/UNCLEAR), ``timing``
(EARLY/ON_TIME/LATE/N_A), ``notes``.

Determinism: same inputs → byte-identical outputs (sorted rows, no wall
clock, input SHA-256 recorded in summary.json for provenance).

Paper path (documented, not required for PASS): a future paper session can
feed the SAME schema by exporting its armed-POI snapshots + routed
candidate fields (poi_id, detection_tf, model_tags, zone bounds, arm bar,
pillar path, displacement, trigger, entry/SL/TP, tp_source) into the same
row shape — e.g. from the operator KPI records / a session export hook.
Nothing here requires a live paper run.

Usage:
    python 06_RESEARCH/scripts/setup_identification_ledger.py \
        [--artifacts-root 06_RESEARCH/results] [--run 6m_post_tp_run1]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

__all__ = ["build_ledger", "main"]

#: hypothesis-outcome run label this ledger joins by default.
DEFAULT_RUN = "6m_post_tp_run1"

HUMAN_COLUMNS = ("verdict", "timing", "notes")

LEDGER_COLUMNS = [
    "setup_index",
    "poi_id",
    "detection_tf",
    "kind",
    "direction",
    "zone_low",
    "zone_high",
    "zone_mid",
    "armed_bar",
    "pillar_path",
    "disp_magnitude_atr",
    "posture",
    "routed",
    "trigger",
    "entry",
    "original_sl",
    "tp",
    "entry_anchor",
    "tp_source",
    # hypothesis-outcome join (filled only when the setup filled a trade)
    "ticket",
    "close_kind",
    "pnl",
    "hypothesis_outcome",
    "mfe_units",
    "mae_units",
    # human scoring (blank by design)
    *HUMAN_COLUMNS,
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_hyp_outcomes(path: Path, run_label: str) -> dict:
    """poi_id → first hypothesis-outcome row for the run (deterministic)."""
    if not path.exists():
        return {}
    out: dict = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("run_label") != run_label:
                continue
            pid = row.get("poi_id") or ""
            if pid and pid not in out:
                out[pid] = row
    return out


def _fmt_float(value) -> str:
    """Compact deterministic float formatting ('' for None/empty)."""
    if value in (None, ""):
        return ""
    try:
        return repr(round(float(value), 6))
    except (TypeError, ValueError):
        return str(value)


def build_ledger(*, artifacts_root: Path, run: str = DEFAULT_RUN) -> dict:
    """Build the ledger; returns {"rows", "summary"} (deterministic)."""
    # The funnel harness writes run artifacts under runN/ while the
    # hypothesis-outcome CSV labels rows with the full run label
    # (6m_post_tp_runN) — map between the two.
    run_dir = run.replace("6m_post_tp_", "") if run.startswith("6m_post_tp_") else run
    funnel_dir = artifacts_root / "frozen_funnel_6m_post_tp" / run_dir
    armed_path = funnel_dir / "armed_records.json"
    summary_path = funnel_dir / "funnel_summary.json"
    hyp_path = artifacts_root / "hypothesis_outcome" / "trades_hypothesis.csv"
    if not armed_path.exists():
        raise SystemExit(f"missing funnel artifact: {armed_path}")
    if not summary_path.exists():
        raise SystemExit(f"missing funnel artifact: {summary_path}")

    armed = json.loads(armed_path.read_text(encoding="utf-8"))
    funnel = json.loads(summary_path.read_text(encoding="utf-8"))
    hyp = _load_hyp_outcomes(hyp_path, run)

    window = funnel.get("window") or {}
    rows: list[dict] = []
    for poi_id, rec in sorted(armed.items()):
        hyp_row = hyp.get(poi_id)
        zone_low = rec.get("zone_low") or ""
        zone_high = rec.get("zone_high") or ""
        try:
            zone_mid = (float(zone_low) + float(zone_high)) / 2.0
        except (TypeError, ValueError):
            zone_mid = None
        rows.append({
            "poi_id": poi_id,
            "detection_tf": rec.get("detection_tf") or "",
            # kind: the model tags the POI carried (m8_kind sub-kind is not
            # exported by the funnel harness — left to a future export).
            "kind": rec.get("model_tags") or "",
            # direction: only known where a trade row carried it (the funnel
            # harness does not export the zone direction) — never inferred.
            "direction": (hyp_row or {}).get("direction", ""),
            "zone_low": _fmt_float(zone_low),
            "zone_high": _fmt_float(zone_high),
            "zone_mid": _fmt_float(zone_mid),
            "armed_bar": rec.get("armed_bar", ""),
            "pillar_path": rec.get("pillar_path") or "",
            "disp_magnitude_atr": _fmt_float(rec.get("disp_magnitude_atr")),
            # Arm posture is not instrumented in the funnel export (the 6m
            # post-TP report records it as UNKNOWN) — honest constant.
            "posture": "UNKNOWN",
            "routed": "YES" if str(rec.get("routed", "")).lower() == "true" else "NO",
            "trigger": rec.get("trigger") or "",
            "entry": _fmt_float(rec.get("entry")),
            "original_sl": _fmt_float(rec.get("original_sl")),
            "tp": _fmt_float(rec.get("tp")),
            "entry_anchor": rec.get("entry_anchor") or "",
            # tp_source exists only at trade level (hypothesis-outcome join).
            "tp_source": (hyp_row or {}).get("tp_source", ""),
            "ticket": (hyp_row or {}).get("ticket", ""),
            "close_kind": (hyp_row or {}).get("close_kind", ""),
            "pnl": _fmt_float((hyp_row or {}).get("pnl")),
            "hypothesis_outcome": (hyp_row or {}).get("hypothesis_outcome", ""),
            "mfe_units": _fmt_float((hyp_row or {}).get("mfe_units")),
            "mae_units": _fmt_float((hyp_row or {}).get("mae_units")),
            # Human scoring — deliberately blank (the script must never
            # pre-fill a verdict; that is the reviewer's judgement).
            "verdict": "",
            "timing": "",
            "notes": "",
        })
    rows.sort(key=lambda r: (r["armed_bar"], r["poi_id"]))
    for index, row in enumerate(rows, start=1):
        row["setup_index"] = index

    by_tf: dict = {}
    for row in rows:
        by_tf[row["detection_tf"]] = by_tf.get(row["detection_tf"], 0) + 1
    routed_rows = [r for r in rows if r["routed"] == "YES"]
    with_plan = [r for r in routed_rows if r["entry"] and r["original_sl"] and r["tp"]]
    joined = [r for r in rows if r["hypothesis_outcome"]]
    hyp_mix: dict = {}
    for row in joined:
        key = row["hypothesis_outcome"]
        hyp_mix[key] = hyp_mix.get(key, 0) + 1

    summary = {
        "ledger": "setup_identification_ledger",
        "purpose": (
            "identification validation (count + human quality scoring) — "
            "NOT PnL edge; no expectancy claim"
        ),
        "source": {
            "funnel_artifacts": str(funnel_dir),
            "funnel_tag": funnel.get("tag"),
            "armed_records_sha256": _sha256(armed_path),
            "funnel_summary_sha256": _sha256(summary_path),
            "hypothesis_outcome_csv": (str(hyp_path) if hyp_path.exists()
                                       else None),
            "run_label": run,
        },
        "window": {
            "start": window.get("start"),
            "end": window.get("end"),
            "exec_tf": window.get("exec_tf"),
            "load_from": window.get("load_from"),
        },
        "setups_n": len(rows),
        "by_tf": dict(sorted(by_tf.items())),
        "routed_n": len(routed_rows),
        "routed_with_full_plan_n": len(with_plan),
        "hyp_outcome_join": ("YES" if joined else "NO") if rows else "NO",
        "hyp_outcome_joined_n": len(joined),
        "hyp_outcome_mix": dict(sorted(hyp_mix.items())),
        "tp_source_mix": dict(sorted(
            (lambda d: d)(
                {r["tp_source"]: sum(1 for x in rows if x["tp_source"] == r["tp_source"])
                 for r in rows if r["tp_source"]}) .items())),
        "human_columns": list(HUMAN_COLUMNS),
        "human_columns_note": (
            "blank by design — filled by the human reviewer; the script "
            "never pre-fills a verdict/timing"
        ),
        "posture_note": (
            "arm posture not instrumented in the funnel export (6m post-TP "
            "report records it as UNKNOWN) — column kept for schema parity "
            "with the future paper export"
        ),
        "determinism": "sorted rows, no wall clock — same inputs → byte-identical outputs",
    }
    return {"rows": rows, "summary": summary}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="L2 setup identification ledger")
    parser.add_argument("--artifacts-root", default="06_RESEARCH/results")
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument(
        "--out-dir", default="06_RESEARCH/results/setup_identification_ledger")
    args = parser.parse_args(argv)

    artifacts_root = Path(args.artifacts_root)
    result = build_ledger(artifacts_root=artifacts_root, run=args.run)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "setups.csv"
    summary_path = out_dir / "summary.json"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=LEDGER_COLUMNS)
        writer.writeheader()
        writer.writerows(result["rows"])
    summary_path.write_text(
        json.dumps(result["summary"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8")

    summary = result["summary"]
    print("setup_identification_ledger")
    print(f"  window        : {summary['window']['start']} .. {summary['window']['end']}"
          f" (exec {summary['window']['exec_tf']})")
    print(f"  setups        : {summary['setups_n']}")
    print(f"  by_tf         : {summary['by_tf']}")
    print(f"  routed        : {summary['routed_n']}"
          f" (with full plan: {summary['routed_with_full_plan_n']})")
    print(f"  hyp join      : {summary['hyp_outcome_join']}"
          f" ({summary['hyp_outcome_joined_n']} rows) {summary['hyp_outcome_mix']}")
    print(f"  outputs       : {csv_path}")
    print(f"                  {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
