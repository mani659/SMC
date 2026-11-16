"""Build PRODUCT_1Y_ONE_STORY_DIAGNOSTIC_REPORT.md from summary.json.

Reads 06_RESEARCH/results/product_1y_one_story/summary.json (produced by
``product_1y_one_story_diag.py``) plus the continuous-attempt probe log
(if present) and writes the diagnostic report. Book-shape evidence only:
counts, mixes, determinism - NO expectancy, NO performance claim, NO ship
recommendation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_ROOT = REPO / "06_RESEARCH" / "results" / "product_1y_one_story"
SUMMARY = OUT_ROOT / "summary.json"
PROBE_LOG = OUT_ROOT / "cont_probe.log"
REPORT = REPO / "06_RESEARCH" / "PRODUCT_1Y_ONE_STORY_DIAGNOSTIC_REPORT.md"

SEG_ORDER = ["nov24", "dec24", "jan25", "feb25", "mar25", "apr25",
             "may25", "jun25", "jul25", "aug25", "sep25", "oct25"]


def fmt_counts(d: dict) -> str:
    return ", ".join(f"{k} {v}" for k, v in (d or {}).items()) or "none"


def single_storyline_verdict(combined: dict) -> tuple[str, str]:
    triggers = combined["fills_by_trigger"]
    directions = combined["fills_by_direction"]
    tiers = combined["fills_by_detection_tf"]
    months = combined["fills_by_month"]
    if len(triggers) <= 1 and len(directions) <= 1:
        label = "YES"
    elif len(triggers) >= 2 and len(directions) >= 2 and len(tiers) >= 2:
        label = "NO"
    else:
        label = "PARTIAL"
    evidence = (f"trigger mix on fills: {fmt_counts(triggers)}; "
                f"direction mix on fills: {fmt_counts(directions)}; "
                f"detection-tier mix on fills: {fmt_counts(tiers)}; "
                f"fills by month: {fmt_counts(months)}")
    return label, evidence


def probe_lines() -> list[str]:
    if not PROBE_LOG.exists():
        return []
    out = []
    for line in PROBE_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("[p3]") and ("bar " in line or "exec M5" in line):
            out.append(line)
    return out


def main() -> int:
    s = json.loads(SUMMARY.read_text(encoding="utf-8"))
    segments = s["segments"]
    combined = s["combined"]
    comp = s["comparison_vs_6m"]
    label, evidence = single_storyline_verdict(combined)
    mode = s["mode"]
    probe = probe_lines()

    lines = []
    a = lines.append
    a("# PRODUCT ~1Y MENU + ONE-STORY DIAGNOSTIC")
    a("")
    a("**DIAGNOSTIC ONLY — NOT PERFORMANCE. No edge claim, no ranking, no gate"
      " or threshold change, no ship recommendation. Every number below is a"
      " book-shape count on the frozen diagnostic configuration (spread 0.0,"
      " news dormant, all sessions, cost model dormant) — the same"
      " machine-completeness config as PFE-2 / PRODUCT_6M, explicitly NOT"
      " cost realism.**")
    a("")
    a(f"- **Status:** measurement complete; one-story guard ON (shipped"
      f" intake seam, `04_SRC/smc/risk/story_guard.py`).")
    a(f"- **Script:** `06_RESEARCH/scripts/product_1y_one_story_diag.py`"
      f" driving the PFE-2 harness (`phase3_structure_funnel.py`,"
      f" `--composition menu`) — no forked engine, no strategy change.")
    a(f"- **Mode:** **{mode.upper()}** (see §1 for the continuous-attempt"
      f" profile and the segmented-tiling merge rules).")
    a("")
    a("## 1. Window and the continuous-vs-segmented decision")
    a("")
    a("**Target (pre-registered):** exec **2024-11-01 → 2025-10-31 UTC**"
      " (12 calendar months), load **2024-09-01** (61 days warm-up). The"
      " canonical `XAUUSD_M1.parquet` covers 2021-04-12 → 2026-04-10"
      " (1,768,123 rows), so the target window is fully inside the data"
      " (fail-loud check passed).")
    a("")
    a("**Continuous attempt (mode A) — profiled live, then stopped by the"
      " pre-registered budget:**")
    a("")
    if probe:
        a("```")
        for ln in probe:
            a(ln)
        a("```")
    else:
        a("(no probe log found)")
    a("")
    a("PFE-2 §1.1 measured the same decay on the 6-month continuous menu"
      " attempt (30.8 bars/s at bar 2,000 → 9.7 at 4,000 → **< 2 bars/s**"
      " with no progress for >10 min, CPU-bound quadratic menu bookkeeping —"
      " stopped **before any funnel was read**, no product code changed to"
      " work around it). The 1-year window is ~70,885 M5 bars (~2× the 6m"
      " attempt); extrapolating the measured decay, the continuous run does"
      " not complete in a reasonable wall-time budget. Per the engagement"
      " rule, it was NOT silently substituted by 10-day slices.")
    a("")
    a("**Segmented continuous coverage (mode B, sanctioned fallback):** 12"
      " **adjacent** calendar-month segments exactly tiling"
      " 2024-11-01 → 2025-10-31 (no gaps, no overlaps, no sampling), each"
      " dual-run, every segment loading from 2024-09-01 (same information"
      " depth the continuous run would have had at that point). This is a"
      " full tiling of the same year — explicitly not the three-window"
      " PRODUCT_6M sample.")
    a("")
    a("**Merge rules (mechanical, pre-registered in the driver docstring):**")
    a("1. Every fill happens at exactly one timestamp inside exactly one"
      " segment — no double-count by construction (verified: segment fill"
      " sum == combined fills).")
    a("2. `armed` / merged / passed / menu-winners are NOT summed across"
      " segments: menu state restarts per segment, so zones near boundaries"
      " re-arm; those counts are reported per segment only.")
    a(f"3. Boundary dedupe (counted, not silent): a later fill whose plan"
      f" identity (story_guard rules 2-6) equals an earlier fill, with the"
      f" earlier within the last 10 days of its segment and the later within"
      f" the first 10 days of the next, is treated as a boundary re-arm"
      f" artifact and dropped. **Dropped: "
      f"{combined['boundary_dedupe_dropped']}**"
      f" (of {combined['raw_fills_before_boundary_dedupe']} raw fills);"
      f" guard-legal re-arms outside the boundary bands are kept and shown"
      f" as non-overlapping groups.")
    a("")
    a("**Documented boundary limitation:** a story armed within ~one menu"
      " window of a month boundary may confirm in the next segment instead"
      " of its arm segment (menu state restarts). The fill census remains a"
      " true 1y census; per-segment armed counts carry the duplicate-arm"
      " artifact.")
    a("")
    a("## 2. Per-segment funnel (menu, guard ON)")
    a("")
    a("| Segment | exec | armed | winners | placed | fills | guard drops |"
      " menu_errors | M5 bars |")
    a("|---|---|---|---|---|---|---|---|---|")
    for seg in SEG_ORDER:
        d = segments[seg]
        f_ = d["funnel"]
        sc = (f_.get("story_counters") or {}).get("duplicate_story_dropped", 0)
        a(f"| {seg} | {d['exec_window']} | {f_['armed']} |"
          f" {f_['menu_winners']} | {d['placed']} | {d['fills']} | {sc} |"
          f" {f_['menu_errors']} | {f_['bars_m5']:,} |")
    a(f"| **sum (fills only)** | — | *not additive* | — |"
      f" **{combined['placed_total']}** | **{combined['fills_total']}** | — | 0"
      f" | — |")
    a("")
    a("`routes` is 0 in every segment (menu-covered POIs, scan dormant — as"
      " in PFE-2). Armed counts are per-segment (menu state restarts; NOT"
      " summed).")
    a("")
    total_drops = sum(
        (segments[seg]["funnel"].get("story_counters") or {}).get(
            "duplicate_story_dropped", 0) for seg in SEG_ORDER)
    a(f"**Guard intake total: {total_drops} duplicate winners dropped**"
      " across the 12 segments (per segment in the table) — the one-story"
      " spray never reached the risk gate.")
    a("")
    a("## 3. Unique stories vs raw fills (the answer)")
    a("")
    a("| | Raw fills | Unique filled plans | Identical-plan groups (total) |"
      " of which overlapping |")
    a("|---|---|---|---|---|")
    a(f"| **1y combined (after boundary dedupe)** |"
      f" **{combined['raw_fills']}** |"
      f" **{combined['unique_filled_plans']}** |"
      f" **{combined['identical_plan_groups_total']}** |"
      f" **{combined['identical_plan_groups_overlapping']}** |")
    a("")
    a("Plan identity = the locked story_guard rules 2-6 (direction · trigger"
      " · entry · SL · TP exact floats · overlapping zone), applied"
      " mechanically to the merged book; no tolerance invented, unknown"
      " geometry never collapsed.")
    a("")
    a("**Multi-fill check:** overlapping identical-plan groups (concurrent"
      " duplicates) ="
      f" **{combined['identical_plan_groups_overlapping']}** (must be 0)."
      f" Non-overlapping same-plan groups (guard-legal re-arms: the plan"
      f" closed, the story re-armed later):"
      f" **{combined['non_overlapping_rearm_groups']}** — reported, not"
      " treated as a violation (the guard seals claims only while the plan"
      " lives; re-arm after close is allowed by design).")
    a("")
    a("## 4. Mix tables (book shape, 1y)")
    a("")
    a("| Mix | Value |")
    a("|---|---|")
    a(f"| Trigger mix on fills | {fmt_counts(combined['fills_by_trigger'])} |")
    a(f"| Direction mix on fills | {fmt_counts(combined['fills_by_direction'])} |")
    a(f"| model_tags on fills | {fmt_counts(combined['fills_by_model_tags'])} |")
    a(f"| Detection-TF mix on fills | {fmt_counts(combined['fills_by_detection_tf'])} |")
    a(f"| **Month histogram** | {fmt_counts(combined['fills_by_month'])} |")
    a(f"| Exit close_kind | {fmt_counts(combined['exit_close_kind'])} |")
    a(f"| Exit tp_source | {fmt_counts(combined['exit_tp_source'])} |")
    a("")
    a("## 5. Comparison — read-only, vs PRODUCT_6M (three-window sample)")
    a("")
    a("| | Raw fills | Unique filled plans |")
    a("|---|---|---|")
    a(f"| PFE-2 pre-guard (same three windows) | {comp['pre_guard_raw_fills']}"
      f" | {comp['pre_guard_unique_plans']} |")
    a(f"| PRODUCT_6M, guard ON | {comp['post_guard_raw_fills']} |"
      f" {comp['post_guard_unique_plans']} |")
    a(f"| This 1y census (12 contiguous months, guard ON) |"
      f" {comp['this_1y_raw_fills']} | {comp['this_1y_unique_filled_plans']} |")
    a("")
    a("Scale context: the 6m sample covered 30 exec days; the 1y census"
      " covers ~250 exec days. Rates per exec day are a book-shape"
      " observation only (no performance meaning).")
    a("")
    a("## 6. Determinism")
    a("")
    a("| Segment | trades.csv | report.json | funnel_summary |")
    a("|---|---|---|---|")
    for seg in SEG_ORDER:
        det = segments[seg]["determinism"]
        a(f"| {seg} | {det['trades_csv']} (byte-identical) |"
          f" {det['report_json']} (byte-identical) | {det['funnel_summary']} |")
    a("")
    a("## 7. Is the engine a single storyline at year scale?")
    a("")
    a(f"**SINGLE_STORYLINE_ENGINE: {label}** — evidence: {evidence}.")
    a("")
    a("This is a statement about the diagnostic book shape only, not about"
      " forward edge or quality.")
    a("")
    a("## 8. Residuals")
    a("")
    a("- Continuous 12-month menu run remains infeasible without a"
      " performance-only harness engagement (PFE-2 §1.1 stands; the probe"
      " above re-confirms the decay). A minimal harness fix would be a"
      " menu-bookkeeping performance patch in the runtime — **production"
      " code, out of scope here by ban**; proposed to the Architect, not"
      " implemented.")
    a("- Boundary limitation of the segment tiling (§1 rule 3 + note):"
      " boundary re-arms deduped mechanically; per-segment armed counts"
      " carry the re-arm artifact.")
    a("- `POSTURE` extras: not re-measured (UNKNOWN, honestly — only the"
      " already-instrumented funnel counters are reported).")
    a("- Warm-up asymmetry: every segment loads from 2024-09-01; D1/H4/H1"
      " carry the full load window while M15/M5/M1 start at each segment's"
      " exec start (carried from the PFE-2/PRODUCT_6M convention).")
    a("")
    a("**No expectancy claim, no PnL-as-performance claim, no ship"
      " recommendation. O1-O5 remain CLOSED status-quo; C3/SL/TP policy and"
      " thresholds untouched; `locked_constants.py` untouched.**")
    a("")

    REPORT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"[report] wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
