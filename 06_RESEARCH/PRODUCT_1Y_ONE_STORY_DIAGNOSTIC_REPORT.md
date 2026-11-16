# PRODUCT ~1Y MENU + ONE-STORY DIAGNOSTIC

**DIAGNOSTIC ONLY — NOT PERFORMANCE. No edge claim, no ranking, no gate or threshold change, no ship recommendation. Every number below is a book-shape count on the frozen diagnostic configuration (spread 0.0, news dormant, all sessions, cost model dormant) — the same machine-completeness config as PFE-2 / PRODUCT_6M, explicitly NOT cost realism.**

- **Status:** measurement complete; one-story guard ON (shipped intake seam, `04_SRC/smc/risk/story_guard.py`).
- **Script:** `06_RESEARCH/scripts/product_1y_one_story_diag.py` driving the PFE-2 harness (`phase3_structure_funnel.py`, `--composition menu`) — no forked engine, no strategy change.
- **Mode:** **SEGMENTED** (see §1 for the continuous-attempt profile and the segmented-tiling merge rules).

## 1. Window and the continuous-vs-segmented decision

**Target (pre-registered):** exec **2024-11-01 → 2025-10-31 UTC** (12 calendar months), load **2024-09-01** (61 days warm-up). The canonical `XAUUSD_M1.parquet` covers 2021-04-12 → 2026-04-10 (1,768,123 rows), so the target window is fully inside the data (fail-loud check passed).

**Continuous attempt (mode A) — profiled live, then stopped by the pre-registered budget:**

```
[p3] exec M5 70885 bars; H1 6923 H4 1872 D1 365 M15 23630
[p3] bar 2000/70885 26.1 bars/s armed=62 routes=0
[p3] bar 4000/70885 7.1 bars/s armed=206 routes=0
[p3] bar 6000/70885 2.5 bars/s armed=244 routes=0
```

PFE-2 §1.1 measured the same decay on the 6-month continuous menu attempt (30.8 bars/s at bar 2,000 → 9.7 at 4,000 → **< 2 bars/s** with no progress for >10 min, CPU-bound quadratic menu bookkeeping — stopped **before any funnel was read**, no product code changed to work around it). The 1-year window is ~70,885 M5 bars (~2× the 6m attempt); extrapolating the measured decay, the continuous run does not complete in a reasonable wall-time budget. Per the engagement rule, it was NOT silently substituted by 10-day slices.

**Segmented continuous coverage (mode B, sanctioned fallback):** 12 **adjacent** calendar-month segments exactly tiling 2024-11-01 → 2025-10-31 (no gaps, no overlaps, no sampling), each dual-run, every segment loading from 2024-09-01 (same information depth the continuous run would have had at that point). This is a full tiling of the same year — explicitly not the three-window PRODUCT_6M sample.

**Merge rules (mechanical, pre-registered in the driver docstring):**
1. Every fill happens at exactly one timestamp inside exactly one segment — no double-count by construction (verified: segment fill sum == combined fills).
2. `armed` / merged / passed / menu-winners are NOT summed across segments: menu state restarts per segment, so zones near boundaries re-arm; those counts are reported per segment only.
3. Boundary dedupe (counted, not silent): a later fill whose plan identity (story_guard rules 2-6) equals an earlier fill, with the earlier within the last 10 days of its segment and the later within the first 10 days of the next, is treated as a boundary re-arm artifact and dropped. **Dropped: 0** (of 239 raw fills); guard-legal re-arms outside the boundary bands are kept and shown as non-overlapping groups.

**Documented boundary limitation:** a story armed within ~one menu window of a month boundary may confirm in the next segment instead of its arm segment (menu state restarts). The fill census remains a true 1y census; per-segment armed counts carry the duplicate-arm artifact.

## 2. Per-segment funnel (menu, guard ON)

| Segment | exec | armed | winners | placed | fills | guard drops | menu_errors | M5 bars |
|---|---|---|---|---|---|---|---|---|
| nov24 | 2024-11-01 -> 2024-11-30 | 232 | 63 | 21 | 21 | 41 | 0 | 5,715 |
| dec24 | 2024-12-01 -> 2024-12-31 | 193 | 61 | 13 | 12 | 46 | 0 | 5,756 |
| jan25 | 2025-01-01 -> 2025-01-31 | 198 | 25 | 13 | 12 | 11 | 0 | 6,041 |
| feb25 | 2025-02-01 -> 2025-02-28 | 290 | 91 | 24 | 23 | 62 | 0 | 5,490 |
| mar25 | 2025-03-01 -> 2025-03-31 | 394 | 49 | 17 | 14 | 31 | 0 | 5,820 |
| apr25 | 2025-04-01 -> 2025-04-30 | 386 | 65 | 20 | 18 | 43 | 0 | 5,794 |
| may25 | 2025-05-01 -> 2025-05-31 | 320 | 82 | 30 | 30 | 48 | 0 | 6,018 |
| jun25 | 2025-06-01 -> 2025-06-30 | 284 | 101 | 20 | 19 | 79 | 0 | 5,790 |
| jul25 | 2025-07-01 -> 2025-07-31 | 331 | 106 | 28 | 27 | 76 | 0 | 6,300 |
| aug25 | 2025-08-01 -> 2025-08-31 | 198 | 48 | 22 | 22 | 23 | 0 | 5,795 |
| sep25 | 2025-09-01 -> 2025-09-30 | 462 | 55 | 21 | 18 | 32 | 0 | 6,042 |
| oct25 | 2025-10-01 -> 2025-10-31 | 443 | 119 | 23 | 23 | 88 | 0 | 6,324 |
| **sum (fills only)** | — | *not additive* | — | **252** | **239** | — | 0 | — |

`routes` is 0 in every segment (menu-covered POIs, scan dormant — as in PFE-2). Armed counts are per-segment (menu state restarts; NOT summed).

**Guard intake total: 580 duplicate winners dropped** across the 12 segments (per segment in the table) — the one-story spray never reached the risk gate.

## 3. Unique stories vs raw fills (the answer)

| | Raw fills | Unique filled plans | Identical-plan groups (total) | of which overlapping |
|---|---|---|---|---|
| **1y combined (after boundary dedupe)** | **239** | **239** | **0** | **0** |

Plan identity = the locked story_guard rules 2-6 (direction · trigger · entry · SL · TP exact floats · overlapping zone), applied mechanically to the merged book; no tolerance invented, unknown geometry never collapsed.

**Multi-fill check:** overlapping identical-plan groups (concurrent duplicates) = **0** (must be 0). Non-overlapping same-plan groups (guard-legal re-arms: the plan closed, the story re-armed later): **0** — reported, not treated as a violation (the guard seals claims only while the plan lives; re-arm after close is allowed by design).

## 4. Mix tables (book shape, 1y)

| Mix | Value |
|---|---|
| Trigger mix on fills | A 13, F 226 |
| Direction mix on fills | long 135, short 104 |
| model_tags on fills | M1 9, M1+M2+M4+M5+M7+M8 1, M1+M2+M4+M7+M8 2, M1+M2+M4+M8 1, M1+M2+M5+M7+M8 1, M1+M2+M7+M8 2, M1+M4 2, M1+M4+M5 1, M1+M4+M5+M6+M7+M8 2, M1+M4+M5+M7+M8 3, M1+M4+M7 10, M1+M4+M7+M8 6, M1+M4+M8 1, M1+M5+M6+M7 2, M1+M5+M7 1, M1+M5+M7+M8 7, M1+M5+M8 1, M1+M7 10, M1+M7+M8 32, M1+M8 5, M2+M8 3, M4 12, M4+M5 1, M4+M5+M6+M7+M8 1, M4+M5+M7+M8 1, M4+M5+M8 2, M4+M6+M8 1, M4+M7 1, M4+M7+M8 5, M4+M8 12, M5 10, M5+M6 1, M5+M6+M7 1, M5+M6+M7+M8 1, M5+M6+M8 3, M5+M7 1, M5+M7+M8 1, M5+M8 22, M6 6, M6+M7+M8 1, M6+M8 3, M7 6, M7+M8 8, M8 37 |
| Detection-TF mix on fills | D1 6, H1 37, H4 35, M15 161 |
| **Month histogram** | 2024-11 21, 2024-12 12, 2025-01 12, 2025-02 23, 2025-03 14, 2025-04 18, 2025-05 30, 2025-06 19, 2025-07 27, 2025-08 22, 2025-09 18, 2025-10 23 |
| Exit close_kind | stop_loss 174, take_profit 65 |
| Exit tp_source | atr_fallback 84, structural_swing 155 |

## 5. Comparison — read-only, vs PRODUCT_6M (three-window sample)

| | Raw fills | Unique filled plans |
|---|---|---|
| PFE-2 pre-guard (same three windows) | 27 | 8 |
| PRODUCT_6M, guard ON | 9 | 9 |
| This 1y census (12 contiguous months, guard ON) | 239 | 239 |

Scale context: the 6m sample covered 30 exec days; the 1y census covers ~250 exec days. Rates per exec day are a book-shape observation only (no performance meaning).

## 6. Determinism

| Segment | trades.csv | report.json | funnel_summary |
|---|---|---|---|
| nov24 | PASS (byte-identical) | PASS (byte-identical) | PASS |
| dec24 | PASS (byte-identical) | PASS (byte-identical) | PASS |
| jan25 | PASS (byte-identical) | PASS (byte-identical) | PASS |
| feb25 | PASS (byte-identical) | PASS (byte-identical) | PASS |
| mar25 | PASS (byte-identical) | PASS (byte-identical) | PASS |
| apr25 | PASS (byte-identical) | PASS (byte-identical) | PASS |
| may25 | PASS (byte-identical) | PASS (byte-identical) | PASS |
| jun25 | PASS (byte-identical) | PASS (byte-identical) | PASS |
| jul25 | PASS (byte-identical) | PASS (byte-identical) | PASS |
| aug25 | PASS (byte-identical) | PASS (byte-identical) | PASS |
| sep25 | PASS (byte-identical) | PASS (byte-identical) | PASS |
| oct25 | PASS (byte-identical) | PASS (byte-identical) | PASS |

## 7. Is the engine a single storyline at year scale?

**SINGLE_STORYLINE_ENGINE: NO** — evidence: trigger mix on fills: A 13, F 226; direction mix on fills: long 135, short 104; detection-tier mix on fills: D1 6, H1 37, H4 35, M15 161; fills by month: 2024-11 21, 2024-12 12, 2025-01 12, 2025-02 23, 2025-03 14, 2025-04 18, 2025-05 30, 2025-06 19, 2025-07 27, 2025-08 22, 2025-09 18, 2025-10 23.

This is a statement about the diagnostic book shape only, not about forward edge or quality.

## 8. Residuals

- Continuous 12-month menu run remains infeasible without a performance-only harness engagement (PFE-2 §1.1 stands; the probe above re-confirms the decay). A minimal harness fix would be a menu-bookkeeping performance patch in the runtime — **production code, out of scope here by ban**; proposed to the Architect, not implemented.
- Boundary limitation of the segment tiling (§1 rule 3 + note): boundary re-arms deduped mechanically; per-segment armed counts carry the re-arm artifact.
- `POSTURE` extras: not re-measured (UNKNOWN, honestly — only the already-instrumented funnel counters are reported).
- Warm-up asymmetry: every segment loads from 2024-09-01; D1/H4/H1 carry the full load window while M15/M5/M1 start at each segment's exec start (carried from the PFE-2/PRODUCT_6M convention).

**No expectancy claim, no PnL-as-performance claim, no ship recommendation. O1-O5 remain CLOSED status-quo; C3/SL/TP policy and thresholds untouched; `locked_constants.py` untouched.**
