#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TP source attribution on the MENU path (measurement only).

Joins the plan-complement ledger rows (same 5 menu submits, no re-run of the
spine) with a static read of the plan-forming code to answer:

  * was a structural target present on route / signal / candidate at menu
    submit time?
  * how many submits carried a structural TP vs the 4xATR fallback?

Read-only. No TP rule, constant, threshold or tier change. LOGIC_CHANGED: NO.

Diagnostic only — does NOT validate profitability or edge.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER_CSV = ROOT / "06_RESEARCH" / "results" / "plan_complement_ledger" / "plan_complement_ledger.csv"
NOTE_PATH = ROOT / "06_RESEARCH" / "TP_MENU_PATH_ATTRIBUTION_NOTE.md"
SUMMARY_PATH = ROOT / "06_RESEARCH" / "results" / "plan_complement_ledger" / "tp_menu_path_attribution.json"

MENU_SRC = ROOT / "04_SRC" / "smc" / "orchestration" / "product_menu_mtf.py"
BRIDGE_SRC = ROOT / "04_SRC" / "smc" / "backtest" / "pipeline_bridge.py"
ADAPTER_SRC = ROOT / "04_SRC" / "smc" / "backtest" / "pipeline_adapter.py"
TRIGGER_SRC = ROOT / "04_SRC" / "smc" / "triggers" / "base_trigger.py"
RUNNER_SRC = ROOT / "04_SRC" / "smc" / "backtest" / "runner.py"


def _source(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"SOURCE_GAP: missing {path}")
    return path.read_text(encoding="utf-8")


def _slice_between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        return ""
    end = text.find(end_marker, start + len(start_marker))
    return text[start:] if end < 0 else text[start:end]


def main() -> int:
    if not LEDGER_CSV.exists():
        raise SystemExit(f"LEDGER_GAP: missing {LEDGER_CSV} (run plan_complement_ledger.py)")

    with LEDGER_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("LEDGER_GAP: ledger has no rows")

    tp_counts = Counter((r.get("tp_source") or "unknown") for r in rows)
    structural = sum(1 for r in rows if (r.get("tp_source") or "") == "structural_swing")
    atr_fallback = sum(1 for r in rows if (r.get("tp_source") or "") == "atr_fallback")
    n = len(rows)

    # --- Static evidence: where the structural target can enter ---------- #
    menu_src = _source(MENU_SRC)
    adapter_src = _source(ADAPTER_SRC)
    trigger_src = _source(TRIGGER_SRC)
    runner_src = _source(RUNNER_SRC)

    menu_candidate_body = _slice_between(menu_src, "    def _candidate(", "    def _unlocatable_completion")
    signal_body = _slice_between(trigger_src, "class TriggerSignal:", "class Trigger:")
    candidate_body = _slice_between(runner_src, "class CandidateEntry:", "    def fvg_context")

    evidence = {
        "menu_candidate_passes_structural_target": "structural_target" in menu_candidate_body,
        "menu_candidate_calls_candidate_from_route": "candidate_from_route(" in menu_candidate_body,
        "adapter_computes_structural_tp_target": "structural_tp_target(" in adapter_src,
        "trigger_signal_has_structural_target_field": "target" in signal_body,
        "candidate_entry_has_structural_target_field": "structural_target" in candidate_body,
        "candidate_entry_has_tp_source_field": "tp_source" in candidate_body,
    }

    if tp_counts.get("structural_swing"):
        gap_sentence = (
            f"Not always absent: {tp_counts['structural_swing']}/{n} menu submits carried a structural TP."
        )
    else:
        gap_sentence = (
            "Menu path never feeds a structural target: ProductMenuEngine._candidate builds the plan with "
            "candidate_from_route(route, ..., atr=atr) and no structural_target, so resolve_take_profit always "
            "takes the 4xATR fallback; only the adapter-only path (PipelineAdapter.generate_candidates, "
            "pipeline_adapter.py:283) computes structural_tp_target(...) from the route's swing index."
        )

    summary = {
        "TASK": "TP_MENU_PATH_ATTRIBUTION",
        "path": "menu queue_menu_candidate submits only (not adapter-only)",
        "N_EVENTS": n,
        "TP_STRUCTURAL_PRESENT_COUNT": structural,
        "TP_ATR_FALLBACK_COUNT": atr_fallback,
        "TP_SOURCE_COUNTS": dict(tp_counts),
        "TP_FEED_GAP": gap_sentence,
        "STATIC_EVIDENCE": evidence,
        "diagnostic_only": True,
        "logic_changed": "NO",
        "window": {"start": "2024-04-01", "end": "2024-05-01", "warmup_start": "2023-12-01"},
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    table = "\n".join(
        f"| {r['submit_index']} | {r['poi_id']} | {r['detection_tf']}→{r['confirmation_tf']} | "
        f"{r['trigger_type']} | `{r.get('tp_source')}` | {r.get('tp_price')} | "
        f"{'present' if (r.get('tp_source') or '') == 'structural_swing' else 'absent'} |"
        for r in rows
    )

    note = f"""# TP Source Attribution — MENU path (measurement only)

**Diagnostic only — does NOT validate profitability or edge.** Read-only join over the same
{n} plan-complement ledger submits (menu `queue_menu_candidate` → `submit_entry`), window
`2024-04-01..2024-05-01` (warmup `2023-12-01`), `07_DATA/XAUUSD_M1.parquet`. No TP rule,
constant, threshold or tier change (`LOGIC_CHANGED=NO`); no forced structural TP.
Multi-TF tier policy unchanged.

## Counts
- `N_EVENTS` (menu submits): **{n}**
- `TP_STRUCTURAL_PRESENT_COUNT`: **{structural}**
- `TP_ATR_FALLBACK_COUNT`: **{atr_fallback}**
- `tp_source` distribution: `{dict(tp_counts)}`

## Per-submit attribution
| # | poi_id | det→conf | trigger | tp_source | tp_price | structural_target |
|---:|---|---|---|---|---|---|
{table}

## Feed gap (one sentence)
{gap_sentence}

## Static evidence (plan-forming call sites)
- `ProductMenuEngine._candidate` → `candidate_from_route(route, pillar_path=..., atr=atr)`:
  `structural_target` passed = **{evidence['menu_candidate_passes_structural_target']}**
- `PipelineAdapter.generate_candidates` computes `structural_tp_target(...)`:
  **{evidence['adapter_computes_structural_tp_target']}** (adapter-only feed)
- `TriggerSignal` carries a structural target field: **{evidence['trigger_signal_has_structural_target_field']}**
  (fields: trigger, direction, entry_price, stop_reference, completion_index, expiry_bars, detail, data)
- `CandidateEntry` carries `structural_target`: **{evidence['candidate_entry_has_structural_target_field']}**
  (provenance is `tp_source`: {evidence['candidate_entry_has_tp_source_field']})

## Reading
The menu plan's TP provenance is therefore structurally explainable: absent input → `atr_fallback`
by construction, not a rejected structural candidate. Whether the menu path *should* feed
`structural_tp_target(...)` (same selector + lookahead ban as the adapter) is an Architect design
decision, **not** made here and **not** implied by these counts. Small n ({n}), single window.

## Artifacts
- `{LEDGER_CSV}` (input, gitignored results)
- `{SUMMARY_PATH}`
"""
    NOTE_PATH.write_text(note, encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
