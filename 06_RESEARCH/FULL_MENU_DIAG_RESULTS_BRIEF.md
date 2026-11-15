# FULL-MENU DIAGNOSTIC RESULTS BRIEF — coupled_mtf (dual-run COMPLETE)

**Check/extract time:** 2026-11-01T07:15Z
**Classification:** **COMPLETE** — `exit_reason.json`: `ALL_DONE_PASS`, exit_code 0; run1 DONE 2026-10-31T15:48:15Z, run2 DONE 2026-10-31T21:54:22Z (errors: none); assemble step ran (`[assemble] status=PASS determinism=PASS`); `chain_stderr.log` EMPTY; no `ALERT_FAILURE.txt`.

> **OBSERVATION / DIAGNOSTIC ONLY.** Every number below is a frozen-window replay artifact of the
> coupled_mtf full-menu measurement harness (banner: `DIAGNOSTIC ONLY - NOT PERFORMANCE / NOT EDGE`).> Nothing here is expectancy, a hit rate, or promotion evidence; funnel counts are context-pipeline
> diagnostics (summary.json residuals, restated verbatim in §E).

---

## A. Run identity

| Field | Value |
|---|---|
| Mode | `COUPLED_MTF` (approved addon, opt-in; docs: `06_RESEARCH/COUPLED_MTF_IMPLEMENTATION_NOTE.md`) |
| Execution window (frozen) | **2025-06-01 → 2025-11-30** (exclusive end `2025-12-01T00:00Z`); load start 2025-05-01; exec TF **M5** |
| Data source | `07_DATA/XAUUSD_M1.parquet` |
| Frozen execution bars | **35,725 M5 bars** — both runs processed **35,725 / 35,725** (run_completion: `complete=true`, "The complete frozen execution interval was processed and finalized.") |
| Loaded bars (warm-up) | M1 208,693 · M15 13,916 · H1 3,482 · H4 942 · D1 184 |
| Resume vs full | Both runs were **resumed from mid-way checkpoints** (run1 from bar 15,500; run2 from bar 5,000) after the 2026-10-31 09:48 UTC detached relaunch; deterministic replay-to-checkpoint precedes new-bar commits (design contract; no double-count — events stayed frozen during replay). |
| git sha at record time | `513af0ca…` (checkpoint/run files) |
| Wall time | run1 ~6.1 h · run2 ~6.1 h · total 12.1 h (chain_progress) |

## B. Funnel / counts (from canonical `summary.json` — assembled by the chain)

Total funnel over the frozen window:

| Stage | DAY | H1 | H4 | M15 | **Total** |
|---|---|---|---|---|---|
| eligible levels seen | — | — | — | — | swing **2,702** / tracked_poi **844** |
| sweeps_detected | 14 | 216 | 76 | 1,595 | **1,901** (= episodes_opened) |
| episodes_violated | 10 | 37 | 13 | 665 | **725** |
| episodes_expired | 4 | 0 | 0 | 119 | **123** |
| episodes_routed (= candidates_emitted) | 0 | 179 | 63 | 810 | **1,052** |
| orders placed | 0 | 103 | 45 | 545 | **693** |
| orders filled | 0 | 65 | 27 | 351 | **443** |
| still_open_at_window_end | 0 | 0 | 0 | 1 | **1** |

Mark reads (per summary.json's own accounting; zero-stage explained-zeros in the file):
- **D trigger: 0 winners in every cell** (18/18 cells; status `ZERO_WINNERS_RAW_EVALUATOR_MATCHES_UNINSTRUMENTED` — raw no-match telemetry is NOT instrumented, so D could occur as non-winner; only first-valid winners are counted).
- **DAY tier: 0 candidates** — every DAY-tier cell zero-winners; the D1→H1 tier is sparse by construction (14 D1 sweeps in the whole 6m window), so zero DAY candidates is a population fact, not a failure signal.
- **Def-B: 0 candidates** (raw and product) — the "never arm raw Def-B" contract held as designed.
- Winner triggers: **F 955 / A 97 / D 0** — F dominates (90.8%) since confirm TFs are M1/M5 where every eligible ladder passes through F's BOS+OB family.
- confirm_tf mix: M1 949 · M5 103; tier mix: M15 810 · H1 179 · H4 63 · DAY 0; level_family mix: swing 1,015 · poi 37.
- Orders: 693 placed / **443 filled** (63.9% fill ratio as constructed by the paper limit-idle model in this diagnostic — a fill-model behavior, not a trade quality metric).

## C. Completeness + determinism

- **Both runs COMPLETE over the identical frozen window; all DONE flags present; assemble PASS.**
- **Determinism PASS (assemble gate + independent hash check):**
  - `run1/candidates.json` and `run2/candidates.json` are **byte-identical** (both 276,102 B; SHA-256 `31d4a736cdd4f4e8…` — independently re-hashed 2026-11-01).
  - `run1/checkpoint_events.jsonl` and `run2/checkpoint_events.jsonl` are also **byte-identical** (both 753,545 B; independently re-hashed).
  - `run.json` semantic identity True (runtime/run-name/resume bookkeeping fields excluded by the checker; every measured field compared equal).
- Events written: run1 **2,953**, run2 **2,953** (both runs' full event journals byte-identical).
- Diagnostic candidate identity cells available in `summary.json.candidate_events` (1,052 × `{tier, trigger, level_family, confirm_tf, identity, sweep_close}`).

## D. Anomalies / caveats

1. `chain_stderr.log` **EMPTY**; exit_code 0; no fatal traces. Non-empty only in `chain_stdout.log`: pre-crash first-attempt lines + appended mojibake from the earlier terminated foreground attempt (pre-existing artifact).
2. Resume history: the original 2026-10-29 chain died at 2026-10-31 ~09:47 UTC (IDE-reload teardown of the Job-Object-bound process tree), directly relaunched 09:48 UTC detached (SESSION_HANDOFF 2026-10-31 (2)). Both runs consumed **resumed** checkpoints; nothing was wiped or force-rerun.
3. run2 late-stage processing rate decayed 1.0 → 0.7 bars/s (progress monitors) — CPU load from concurrent EA compile work earlier, no stall (heartbeat stayed fresh, run completed in plan time).
4. Summary.json residual (verbatim class): the production trigger evaluator returns only winning first-valid candidates — **per-cell no-match/loss telemetry is NOT instrumented**; D's 0 winners is a winner-count fact, not a rule deadness measurement.
5. Still_open_at_window_end = 1 (one M15 episode's paper order open at the exclusive window end — structural consequence of the hard window cut).

## E. Paths for Architect analysis (canonical first)

| Path | What it is |
|---|---|
| `06_RESEARCH/results/coupled_mtf_full_menu_diag/summary.json` | **Primary**: chain-assembled combine — funnel, trigger cells, determinism block, zero-stage accounting, residuals (313 KB) |
| `06_RESEARCH/results/coupled_mtf_full_menu_diag/run1/run.json` | run1 full run record (306,898 B; DONE 2026-10-31T15:48:15Z) |
| `06_RESEARCH/results/coupled_mtf_full_menu_diag/run2/run.json` | run2 full run record (306,896 B; DONE 2026-10-31T21:54:21Z) |
| `06_RESEARCH/results/coupled_mtf_full_menu_diag/run1/candidates.json` | run1 candidates (byte-identical to run2) |
| `06_RESEARCH/results/coupled_mtf_full_menu_diag/run2/candidates.json` | run2 candidates (byte-identical) |
| `06_RESEARCH/results/coupled_mtf_full_menu_diag/run1/checkpoint_events.jsonl` | full event journal (byte-identical to run2) |
| `06_RESEARCH/results/coupled_mtf_full_menu_diag/exit_reason.json` | `ALL_DONE_PASS` · exit_code 0 |
| `06_RESEARCH/results/coupled_mtf_full_menu_diag/ALERT_COMPLETION.txt` | "ALL DONE — PASS · Total 12.1 h · Determinism: PASS" |
| `06_RESEARCH/results/coupled_mtf_full_menu_diag/chain_progress.log` | per-bar chain telemetry + assemble step lines |
| `06_RESEARCH/results/coupled_mtf_full_menu_diag/estimated_completion.json` | chain ETA record |
| `06_RESEARCH/results/coupled_mtf_full_menu_diag/run1/progress.log`, `run2/progress.log` | per-bar per-run progress (rate history) |

Residual statements copied verbatim from `summary.json.residuals`:
> 1. Production trigger evaluator API returns only winning first-valid candidates, not per-episode per-cell evaluation telemetry. Non-winners cannot be classified as a trigger-cell no-match without logic instrumentation.
> 2. `MultiTFProductRuntime` still requires H4/H1; D1/M15 source tiers are coupled swing discovery and available product POIs, not additional product-runtime required series.
> 3. Counts of candidates/orders are context-pipeline diagnostics only, not promotion or edge evidence.

```text
DIAG_STATUS: COMPLETE
PID: NONE
RUN1: DONE=Y bars=35725/35725
RUN2: DONE=Y bars=35725/35725
ASSEMBLE: YES (determinism=PASS, candidates byte-identical; independent SHA re-check PASS)
STDERR_EMPTY: YES
BRIEF_PATH: 06_RESEARCH/FULL_MENU_DIAG_RESULTS_BRIEF.md
KEY_ARTIFACTS: [06_RESEARCH/results/coupled_mtf_full_menu_diag/summary.json, run1/run.json, run2/run.json, run1/candidates.json, run2/candidates.json, run1/checkpoint_events.jsonl, exit_reason.json, ALERT_COMPLETION.txt]
DETERMINISM: PASS
LOGIC_CHANGED: NO
NEXT_READY: Architect analysis
```
