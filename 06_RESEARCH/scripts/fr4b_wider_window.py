"""FR-4b — wider fidelity window (post-FR-3.1 machine), measurement only.

Thin wrapper around the FR-4 fidelity baseline (`fr4_fidelity_baseline.py`)
that widens the execution window and adds the two counters FR-4b must
report that FR-4 did not export:

* FR-3 gate accept/reject events — a pass-through recorder on the same
  module-attribute seam the FR-4 diag/fate scripts used (production code
  untouched, counter restored in ``finally``);
* exit mix and entry-anchor provenance (`ob_proximal` vs
  `zone_edge_reanchor`) computed from the written report artifacts.

Frozen intent unchanged from FR-4: equity 10k, risk 0.01, spread 0.0
(gates off — machine completeness, not cost realism), news dormant, all
sessions, Friday EOD on, M5 execution, H4+H1 detection, FR-2 TP/SL +
FR-3 zone gate live (NOT widened), FR-3.1 on-zone anchor live (library
state as of 2026-09-22).

Default window (documented per instruction): load 2025-08-01 (one month
of M1 detection warm-up before the execution start, matching FR-4's
one-month ratio), execute 2025-09-01 → 2025-11-30 (3 months).

Diagnostic only. NOT edge, promotion, or capital advice. No parameter
search is performed regardless of trade count.

Usage:
  python 06_RESEARCH/scripts/fr4b_wider_window.py --tag run1 --out-root 06_RESEARCH/results/fr4b_wider/run1
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
import smc.triggers.trigger_f_bos_ob as fmod  # noqa: E402

# FR-4b default window (documented): 1-month M1 warm-up + 3-month exec.
DEFAULT_LOAD_FROM = "2025-08-01"
DEFAULT_EXEC_FROM = "2025-09-01"
DEFAULT_EXEC_TO = "2025-11-30"


def run_with_gate_counter(args) -> dict:
    """Run the FR-4 baseline with a gate-event counter wrapped around it.

    The recorder is a pass-through: the real (frozen) ``entry_within_zone``
    decides, the wrapper only counts. Restored unconditionally.
    """
    original_gate = fmod.entry_within_zone
    counts = {"accept": 0, "reject": 0}

    def counting_gate(entry, zone, atr, *a, **k):
        result = original_gate(entry, zone, atr, *a, **k)
        counts["accept" if result else "reject"] += 1
        return result

    fmod.entry_within_zone = counting_gate  # type: ignore[assignment]
    try:
        summary = fr4.run(args)
    finally:
        fmod.entry_within_zone = original_gate  # type: ignore[assignment]

    summary["fr3_gate_events"] = counts

    # Exit mix + entry-anchor provenance from the written trade book
    # (trades.csv — authoritative header; report.json rows are the same
    # records but the header guarantees the key names we read).
    import csv

    trades_path = REPO_ROOT / args.out_root / "trades.csv"
    exit_mix: dict[str, int] = {}
    anchor_mix: dict[str, int] = {}
    trades_n = 0
    try:
        with open(trades_path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        trades_n = len(rows)
        for row in rows:
            kind = row.get("close_kind") or "unknown"
            exit_mix[kind] = exit_mix.get(kind, 0) + 1
            raw = row.get("signal_data_json")
            if raw:
                try:
                    payload = json.loads(raw)
                    anchor = payload.get("entry_anchor") if isinstance(payload, dict) else None
                    if anchor:
                        anchor_mix[anchor] = anchor_mix.get(anchor, 0) + 1
                except (TypeError, ValueError):
                    pass
    except OSError as exc:
        exit_mix["__trades_read_error__"] = str(exc)

    summary["exit_mix"] = exit_mix
    summary["entry_anchor_mix"] = anchor_mix
    summary["report_trades"] = trades_n
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--load-from", default=DEFAULT_LOAD_FROM)
    ap.add_argument("--exec-from", default=DEFAULT_EXEC_FROM)
    ap.add_argument("--exec-to", default=DEFAULT_EXEC_TO)
    ap.add_argument("--diag-no-zone-gate", action="store_true",
                    help="DIAGNOSTIC ONLY: inherited from the FR-4 baseline. "
                         "Never for evidence runs.")
    args = ap.parse_args()
    summary = run_with_gate_counter(args)
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
