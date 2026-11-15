# COUPLED FULL-MENU 443-FILL HYPOTHESIS STUDY — R / MFE / MAE (CAPTURED LEGS)

**Date:** 2026-11-01 · **Authority:** Lead Architect "INSTRUMENTED FILL-LEG CAPTURE (SINGLE PASS) + RE-RUN HYPOTHESIS STUDY" (GO 2026-11-01)
**Status:** CAPTURE PASS · STUDY PASS — **coverage 100.0% (443/443), DATA_GAP 0**

> **banner: DIAGNOSTIC ONLY — NOT PERFORMANCE / NOT EDGE.**
> Every table and statement in this report is diagnostic. MFE is peak
> excursion, not realized outcome; nothing here is edge evidence; no
> threshold tuning, no Mode A == M15 promotion. LOGIC_CHANGED: NO.

---

## 1. Capture provenance (single instrumented pass, logging only)

Source of truth for this report: `06_RESEARCH/results/coupled_mtf_fill_leg_capture/run1/fill_legs.jsonl`
(1,579 legs: 693 `placed` + 443 `fill` + 443 `exit`), written by
`06_RESEARCH/scripts/coupled_mtf_fill_leg_capture.py` as a logging-only
subclass of the production diagnostic's own `CountingBook`/`CountingPositions`
seam (window/bar reads, funnel, strategy, sizing, SL/TP policy untouched).

| Capture fact | Value |
|---|---|
| git sha | `513af0ca0145bc093924dbc43b82e070ebf42f17` |
| window | LOAD 2025-05-01 -> EXEC 2025-06-01T00:00Z -> 2025-11-30T23:59 (M5, exclusive 2025-12-01) |
| execution bars | 35,725 processed of 35,725 frozen |
| mode | `fresh` single pass, started 2026-11-01T08:19:46Z |
| runtime | 6.33 h (22,773 s, ~1.6 bars/s incl. warmup) |
| placed counter | **693** (reference 693) |
| fills counter | **443** (reference 443) — **drift ZERO** |
| exits written | 443 (100% fill->exit pairing, fsync per event) |
| prior diag DONE trees | untouched (`coupled_mtf_full_menu_diag/**` untouched) |
| `04_SRC` edits | none (`strategy_changed: false`) |
| candidates.json (capture tree) | written by same harness; used for identity join |

Identity join: `route_id` (order comment = `episode.identity_tag`) joined to
candidate `identity` on the RAW encoded string; join was smoke-verified and
lands 100% (tier/trigger/confirm_tf/level_family resolved for all 443).

## 2. Definitions and labels (pre-registered; mapping documented)

- **1R** = `|entry - sl_original|` — the ORIGINAL placement SL distance.
  BE-modified SL is ignored (never used as 1R).
- **mfe_r / mae_r** = per-bar extreme favorable/adverse price excursion
  (entry-bar through closing bar inclusive, closing bar folded) divided by 1R.
  Direction-aware: LONG favorable = max price, SHORT favorable = min price.
- Labels resolve mechanically from the persisted `close_kind` (enum value
  normalized, verbatim repr kept for audit) and geometry only — nothing
  invented:
  - `take_profit` -> **TP_REACHED** (31 / 443 = 7.0%)
  - `stop_loss`  -> **REJECTED** (412 / 443 = 93.0%)
  - unrecognized kind (none occurred; only `'friday_eod'` possible)
    -> geometry sub-classification: `exit == entry` -> BE_SCRATCH else MFE_ONLY
  - **SL_THEN_TP_PATH** is reserved for an explicitly recorded re-entry chain;
    the single-close capture cannot establish it, so it stays unused (and
    such fills honestly label **REJECTED** — no fabrication).
- Labels resolved: **443 / 443** — DATA_GAP count: **0**.

Honest shares implied by labels alone: the placed-TP was reached on 7.0% of
fills; 93.0% of fills hit the original stop within the frozen window
(meaning the placed SL was touched before the placed TP — the *path* detail
beyond that single fact is not captured).

## 3. Pre-registered read order (executed in order; NOT reordered)

### Read 1 — F-book: median MFE_R vs MAE_R and %MFE>=1R

| n | median MFE_R | median MAE_R | %MFE>=1R | %MFE>=2R | MFE-MAE median asymmetry |
|---|---|---|---|---|---|
| 380 | **4.3625** | **3.1550** | **80.3%** | 73.9% | +1.2075 |

F-book excursion map: favorable peaks typically far beyond 1R (73.9% of F
fills visited >= 2R before resolution), while adverse medians are ~0.73R
below the favorable median. Excursion reading only — not performance.

### Read 2 — M15 vs H4/H1 separation on %MFE>=1R (detection tier of the episode)

| tier | n | median MFE_R | median MAE_R | %MFE>=1R | %MFE>=2R | flag |
|---|---|---|---|---|---|---|
| M15 | 351 | 3.9619 | 2.8800 | **75.5%** | 66.4% | n large |
| H1 | 65 | 3.5394 | 2.4196 | **75.4%** | 63.1% | n moderate |
| H4 | 27 | 2.1913 | 1.3662 | **66.7%** | 51.9% | **n small** |

Separation: M15 and H1 are indistinguishable (75.5% vs 75.4%). H4 reads lower
(66.7%) but carries a small-n flag; the count is stated, not massaged. No
separation claim is made.

### Read 3 — A vs F (with n flags)

| trigger | n | median MFE_R | median MAE_R | %MFE>=1R | %MFE>=2R | flag |
|---|---|---|---|---|---|---|
| F | 380 | 4.3625 | 3.1550 | 80.3% | 73.9% | n large |
| A | 63 | **0.6457** | **1.0960** | **42.9%** | 11.1% | **n flagged (63)** |

A-trigger legs are adverse-dominant by median (MAE_R 1.10 > MFE_R 0.65), the
only split where the favorable median sits below 1R. Stated with its n flag;
classification is the architect's call, not this report's.

### Read 4 — D note

**D = 0 fills.** No D-trigger leg exists in the captured 443 (no `D` cell in
`by_trigger`), consistent with the frozen diagnostic (winners D 0 / Def-B 0 /
DAY 0). Nothing to aggregate; noted per the pre-registered read.

## 4. Overall and remaining splits

Overall bucket (n = 443, all R-resolved):

| n | median MFE_R | median MAE_R | %MFE>=1R | %MFE>=2R | asymmetry |
|---|---|---|---|---|---|
| 443 | 3.7152 | 2.7419 | 74.9% | 65.0% | +0.9733 |

By confirm_tf (%MFE>=1R: M1 74.9% n=399 / M5 75.0% n=44; trigger mix per
cell not separated here — see `summary.json` `by_confirm_tf`). By
`level_family`: swing-only spread across tiers (poi/swing fields join from
candidates; see `summary.json` `by_level_family`).

## 5. Honest caveats (binding on every consumer of this report)

1. **MFE is opportunity, not outcome.** Median MFE 3.7R with 93% SL hits means
   favorable peaks are abundantly visited but the placed bracket does not
   monetize them; any redesign implication is a STRATEGY decision, out of
   scope here (Part 1 bans: no policy change in the capture, no tuning now).
2. **Label granularity**: single-close capture cannot see SL-then-re-entry
   paths; REJECTED is the honest label for all 412 SL-kind exits.
3. **Small-n cells are flagged, never hidden** (H4 n=27; A n=63).
4. **Single-pass capture**: dual-run determinism was proven for the funnel on
   the reference trees; this capture re-derives the identical funnel counters
   (693/443, zero drift) but excursions/pnl come from one pass by design.
5. `pnl_raw`/`win` are persisted on every exit leg and available in
   `fills_hypothesis.csv`; no aggregate P&L is claimed or computed here.

## 6. Artifacts and governance

| Artifact | Path |
|---|---|
| Capture legs (source of truth) | `06_RESEARCH/results/coupled_mtf_fill_leg_capture/run1/fill_legs.jsonl` |
| Capture meta | `06_RESEARCH/results/coupled_mtf_fill_leg_capture/run1/capture_meta.json` |
| Capture runner | `06_RESEARCH/scripts/coupled_mtf_fill_leg_capture.py` |
| Capture launcher (detached) | `06_RESEARCH/scripts/launch_fill_leg_capture.ps1` |
| Study script | `06_RESEARCH/scripts/coupled_mtf_fill_hypothesis_study.py` (visibility: `--legs`) |
| Per-fill rows | `06_RESEARCH/results/coupled_mtf_fill_hypothesis/fills_hypothesis.csv` |
| Aggregates JSON | `06_RESEARCH/results/coupled_mtf_fill_hypothesis/summary.json` |
| Reference context | `06_RESEARCH/FULL_MENU_DIAG_RESULTS_BRIEF.md`, `06_RESEARCH/results/coupled_mtf_full_menu_diag/summary.json` (READ-ONLY) |

Prior state of this report (coverage 0% PARTIAL finding) is superseded by this
document; the DATA_GAP explanation it recorded remains historically correct
and is preserved in the 2026-11-01 governance ledgers.
