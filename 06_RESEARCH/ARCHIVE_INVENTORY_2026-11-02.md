# ARCHIVE INVENTORY — 2026-11-02 (Part 0, read-only survey)

**Authority:** Lead Architect "ARCHIVE PASS — LOGS + OBSOLETE ARTIFACTS
(PRODUCT V1 BASE)". No moves were made before this inventory. Product
baseline = `product_v1` (multi-TF).

**Existing archive tree:** the repo already has a top-level `ARCHIVE/`
(gitignored by policy: "Historical archives: old reports, logs, MQL5
history, superseded docs") holding `MQL5_History/`, `Old_Flowcharts/`,
`Old_Reports_Logs/`, `Research_Archive/`, `Superseded_Docs/`,
`TradingView_Era/`. This pass adds to it (Windows paths are
case-insensitive, so `archive/` == `ARCHIVE/`; we reuse the existing tree).

**Live-session lock:** a live operator (PID 18484,
`python 04_SRC\smc\live\run_operator.py --config config\live_demo.json`,
started 13:05:06) holds `logs/phase_d` open → that directory is
**SKIPPED_LOCKED** and is NOT touched.

---

## A) LOGS / RUNTIME candidates

| path | size / files | last write | verdict |
|---|---|---|---|
| `logs/phase_d/` | 28.4 MB (mirror 28.2 MB) | live (1:12 PM) | **SKIPPED_LOCKED** — live operator output dir; rotate only after the session stops |
| `logs/live_console_dryrun/` | 0.14 MB, 6 files | 2026-10-06 | ARCHIVE (pre-Phase-D dry-run console era) |
| `logs/ops_density/` | 0.14 MB, 6 files | 2026-10-20 | ARCHIVE (one-off ops-density probe) |
| `logs/research/` | ~0 MB, 2 files | 2026-10-20 | ARCHIVE |
| `logs/_test_console_v2/` | ~0 MB, 1 file | 2026-11-02 | ARCHIVE (test temp output; tests recreate on demand) |
| `logs/_test_refresh/` | ~0 MB, 1 file | 2026-10-13 | ARCHIVE (test temp output) |

Cutoff note: the current product era begins with the Console V2 +
product_v1 naming work (2026-11-02); everything in `logs/` outside the
LIVE `phase_d` dir is older-era or test-temp.

## B) RESEARCH RESULTS (bulk) — KEEP, documented decision

`06_RESEARCH/results/` ≈ **~180 MB, 115 run dirs** (largest:
`structure_ledger_6m` 46.3 MB, `compute_htf_sweep_census` 24.1 MB — local
only, gitignored by documented policy). **Decision: KEEP in place, do not
move/zip.** Reason: tracked methodology notes record exact artifact paths
(e.g. "artifacts: `06_RESEARCH/results/coupled_mtf_gave_back/`") — moving
breaks every documented reference for zero disk gain (already excluded from
git). Revisit only if the Architect wants a results snapshot zip as a
separate engagement.

## C) STALE RELEASE / DIST

| path | size | last write | verdict |
|---|---|---|---|
| `dist/` (whole pack incl. `SMC_v1.1-test.7_tester.zip`, `run_live.bat` 2026-10-08) | 1.1 MB, 132 files | 2026-10-08 | **ARCHIVE → `ARCHIVE/dist_stale/`** — superseded (pre-multi-TF, pre-naming). A tester pack must be REBUILT from product_v1 before any future dist use. Repo-root `run_live.bat` never referenced it (verified in the bat-wire probe). |

## D) CODE — default DO NOT MOVE honoured

* `04_SRC/smc/dumb/*` package and all internal `DumbMtf*` symbols: **REMAIN**
  (explicit ruling — rename is a dedicated engagement; product_v1 renders no
  legacy token).
* `04_SRC/**` product path (`run_operator`, `operator_config`,
  `loop`, `multi_tf_runtime`, …): untouched this pass.
* Quarantine candidates screen: nothing qualifies (no dead duplicate files;
  tight/archive feeds are loaded via `run_operator` import branches).
* One-off probe scripts FOUND and moved (not code the product imports):
  * root `tests/test_gn.py` — sqlite FTS5 smoke probe (untracked; grep
    proves no reference in any code/test) → `ARCHIVE/research_scripts_stale/`.

## E) UNTOUCHED (per bans)

`04_SRC/smc/config/locked_constants.py` (no edit, diff empty), `00_LOCKED/**`
(covers a CHANGELOG/handoff line only), `.git/`, `07_DATA/**`,
`config/live_demo.json` product_v1 content, `.venv`, `.pytest_cache`,
`__pycache__` (gitignored regenerable caches — documented, left as-is).
