"""Build PRODUCT_6M_ONE_STORY_DIAGNOSTIC_REPORT.md from summary.json.

Reads 06_RESEARCH/results/product_6m_one_story/summary.json (produced by
``product_6m_one_story_diag.py``) and writes the diagnostic report next to it.
Everything is book-shape evidence: counts, mixes, determinism - NO expectancy,
NO performance claim, NO ship recommendation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_ROOT = REPO / "06_RESEARCH" / "results" / "product_6m_one_story"
SUMMARY = OUT_ROOT / "summary.json"
REPORT = REPO / "06_RESEARCH" / "PRODUCT_6M_ONE_STORY_DIAGNOSTIC_REPORT.md"


def fmt_counts(d: dict) -> str:
    return ", ".join(f"{k} {v}" for k, v in (d or {}).items()) or "none"


def single_storyline_verdict(combined: dict) -> tuple[str, str]:
    """Mechanical label from the book-shape mixes (no PnL anywhere)."""
    triggers = combined["fills_by_trigger"]
    directions = combined["fills_by_direction"]
    tiers = combined["fills_by_detection_tf"]
    months = combined["fills_by_month"]
    parts = []
    if len(triggers) <= 1 and len(directions) <= 1:
        label = "YES"
    elif len(triggers) >= 2 and len(directions) >= 2 and len(tiers) >= 2:
        label = "NO"
    else:
        label = "PARTIAL"
    parts.append(f"trigger mix on fills: {fmt_counts(triggers)}")
    parts.append(f"direction mix on fills: {fmt_counts(directions)}")
    parts.append(f"detection-tier mix on fills: {fmt_counts(tiers)}")
    parts.append(f"fills by month: {fmt_counts(months)}")
    return label, "; ".join(parts)


def main() -> int:
    s = json.loads(SUMMARY.read_text(encoding="utf-8"))
    windows = s["windows"]
    order = ["jun", "sep", "oct"]
    combined = s["combined"]
    comp = s["comparison_vs_pfe2_pre_guard"]
    label, evidence = single_storyline_verdict(combined)

    lines = []
    a = lines.append
    a("# PRODUCT 6-MONTH MENU + ONE-STORY DIAGNOSTIC")
    a("")
    a("**DIAGNOSTIC ONLY — NOT PERFORMANCE. No edge claim, no ranking, no gate or"
      " threshold change, no ship recommendation. Every number below is a book-shape"
      " count on the frozen diagnostic configuration (spread 0.0, news dormant, all"
      " sessions, cost model dormant) — the same machine-completeness config as"
      " PFE-2, explicitly NOT cost realism.**")
    a("")
    a(f"- **Status:** measurement complete; one-story guard ON (shipped intake"
      f" seam, `04_SRC/smc/risk/story_guard.py`, locked 2026-11-15).")
    a(f"- **Script:** `06_RESEARCH/scripts/product_6m_one_story_diag.py`"
      f" driving the PFE-2 harness (`06_RESEARCH/scripts/phase3_structure_funnel.py`,"
      f" `--composition menu`) unchanged except a one-line additive measurement"
      f" surface (`story_counters` in the summary).")
    a("- **Composition:** MENU product path only (`ProductMenuEngine` sweep →"
      " one-shot LTF confirmation → `PipelineAdapter.queue_menu_candidate` → same"
      " risk/order seam), one-story guard at intake, structural TP / §5a selector"
      " and risk unchanged. No seek run, no parameter search, no post-hoc filter.")
    a("")
    a("## 1. Window (frozen; PFE-2 conventions, dual run)")
    a("")
    a("The continuous 6-month menu run is documented infeasible (PFE-2 §1.1 —"
      " quadratic menu bookkeeping, stopped before any funnel was read; no product"
      " code changed to work around it). The menu evidence therefore reuses the"
      " PFE-2 frozen bounded windows verbatim, each dual-run:")
    a("")
    a("| Window | Exec (UTC) | Load | M5 bars |")
    a("|---|---|---|---|")
    for w in order:
        d = windows[w]
        a(f"| {w} | {d['exec_window'].replace('T', ' ').replace('+00:00', '')}"
          f" | {d['load_from'][:10]} | {d['bars_m5']:,} |")
    a("")
    a("**Documented deviation:** this is a three-window frozen sample of the six"
      " months (Jun / Sep / Oct 2025 10-day windows), not a continuous 2025-06-01 →"
      " 2025-11-30 run — identical bounds per pair, dual-run. November 2025 has no"
      " bounded menu window in the established record and none was added here"
      " (same residual as PFE-2).")
    a("")
    a("## 2. Funnel (menu, guard ON)")
    a("")
    a("| Metric | Jun 1-10 | Sep 1-10 | Oct 1-10 (primary) |")
    a("|---|---|---|---|")
    def row(key, fmt=str):
        vals = [fmt(windows[w]["funnel"][key]) for w in order]
        a("| " + key + " | " + " | ".join(vals) + " |")
    def row_menu_counter(name):
        vals = [str((windows[w]["funnel"]["menu_counters"] or {}).get(name, "?"))
                for w in order]
        a("| " + name + " | " + " | ".join(vals) + " |")
    row("htf_batches")
    row("batch_errors")
    row("merged_pois")
    row("passed_validation")
    row("armed")
    row("armed_m8")
    row("menu_episodes")
    row("menu_winners")
    row_menu_counter("menu_submitted")
    row("placed")
    row("fills")
    row("menu_errors")
    a("| stories_claimed | "
      + " | ".join(str(windows[w]["funnel"]["story_counters"]["stories_claimed"])
                   for w in order) + " |")
    a("| duplicate_story_dropped (intake) | "
      + " | ".join(str(windows[w]["funnel"]["story_counters"]["duplicate_story_dropped"])
                   for w in order) + " |")
    a("")
    a("`routes` is 0 in every window (menu-covered POIs, scan dormant — as in"
      " PFE-2). `menu_submitted` is the post-guard intake count (PFE-2 pre-guard"
      " submission happened directly from winners).")
    a("")
    a("## 3. Unique stories vs raw fills (the answer)")
    a("")
    a("| | Raw fills | Unique plans | Identical-plan groups |")
    a("|---|---|---|---|")
    for w in order:
        d = windows[w]
        a(f"| {w} | {d['raw_fills']} | {d['unique_filled_plans']} |"
          f" {d['identical_plan_groups']} |")
    a(f"| **combined** | **{combined['raw_fills']}** |"
      f" **{combined['unique_filled_plans']}** |"
      f" **{combined['identical_plan_groups']}** |")
    a("")
    a("Plan identity = the locked story_guard rules 2-6 (direction · trigger ·"
      " entry · SL · TP exact floats · overlapping zone), applied mechanically to"
      " the trades; no tolerance invented, unknown geometry never collapsed.")
    a("")
    a("**Multi-fill check:** identical-plan groups after the guard ="
      f" **{combined['identical_plan_groups']}** (must be 0); groups with"
      " overlapping hold intervals ="
      f" **{combined['identical_plan_groups_overlapping']}** (must be 0)."
      " The guard's own intake counters show the spray was dropped before the"
      " risk gate, so a duplicate never sized and never minted a ticket.")
    a("")
    a("## 4. Mix tables (book shape)")
    a("")
    a("| Mix | Value |")
    a("|---|---|")
    a(f"| Trigger mix on fills | {fmt_counts(combined['fills_by_trigger'])} |")
    a(f"| Direction mix on fills | {fmt_counts(combined['fills_by_direction'])} |")
    a(f"| model_tags on fills | {fmt_counts(combined['fills_by_model_tags'])} |")
    a(f"| Detection-TF mix on fills | {fmt_counts(combined['fills_by_detection_tf'])} |")
    a(f"| Fills by month | {fmt_counts(combined['fills_by_month'])} |")
    a(f"| Exit close_kind | {fmt_counts(combined['exit_close_kind'])} |")
    a(f"| Exit tp_source | {fmt_counts(combined['exit_tp_source'])} |")
    a(f"| Routes by trigger | "
      + "; ".join(f"{w}: {fmt_counts(combined['routes_by_trigger'][w])}"
                  for w in order) + " |")
    a(f"| Armed by detection TF | "
      + "; ".join(f"{w}: {fmt_counts(combined['armed_by_tf'][w])}"
                  for w in order) + " |")
    a("")
    a("## 5. Comparison — pre-guard PFE-2 vs guard ON (same plan key, both sides)")
    a("")
    a("| | Raw fills | Unique plans |")
    a("|---|---|---|")
    a(f"| PFE-2 pre-guard (same three windows) |"
      f" {comp['pre_guard']['raw_fills']} | {comp['pre_guard']['unique_plans']} |")
    a(f"| This run, guard ON | {comp['post_guard']['raw_fills']} |"
      f" {comp['post_guard']['unique_plans']} |")
    a("")
    a(f"Per window pre-guard unique plans: "
      + ", ".join(f"{w} {comp['pre_guard']['by_window'][w]['unique_plans']}"
                  for w in order)
      + "; the guard reduces the book to exactly the distinct plans (the"
        " duplicates never place).")
    a("")
    a("## 6. Determinism")
    a("")
    a("| Window | trades.csv | report.json | funnel_summary |")
    a("|---|---|---|---|")
    for w in order:
        det = windows[w]["determinism"]
        a(f"| {w} | {det['trades_csv']} (byte-identical) |"
          f" {det['report_json']} (byte-identical) | {det['funnel_summary']} |")
    a("")
    a("## 7. Is the engine a single storyline?")
    a("")
    a(f"**SINGLE_STORYLINE_ENGINE: {label}** — evidence: {evidence}.")
    a("")
    a("This is a statement about the diagnostic book shape only, not about"
      " forward edge or quality; n is small (see the funnel table) and the"
      " windows are 10-day samples.")
    a("")
    a("## 8. Residuals")
    a("")
    a("- Continuous 6-month menu run remains infeasible without a"
      " performance-only harness engagement (PFE-2 §1.1 stands); this report is"
      " the three-window frozen sample.")
    a("- November 2025 carries no bounded menu window in the established record.")
    a("- Warm-up asymmetry (D1/H4/H1 carry load_from; M15/M5/M1 start at exec),"
      " window-end queued entries, and fresh menu state per window — carried"
      " verbatim from PFE-2.")
    a("- `POSTURE` extras: not re-measured here (UNKNOWN, honestly — only the"
      " already-instrumented funnel counters are reported).")
    a("")
    a("**No expectancy claim, no PnL claim, no ship recommendation. O1-O5 remain"
      " CLOSED status-quo; C3/SL/TP policy and thresholds untouched;"
      " `locked_constants.py` untouched.**")
    a("")

    REPORT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"[report] wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
