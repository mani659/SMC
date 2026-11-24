# REPO HYGIENE CANDIDATES — 2026-11-16 (REVIEW ONLY)

**Status:** analysis only. **No file was deleted, moved, renamed or committed.**
**Scope:** whole tree at `D:\Gold Scripts\MQL5\SMC`, branch `main`, HEAD `3f2582c`.
**Method:** `du -sh` per directory, file counts, git tracking (`git ls-files`), `.gitignore`
coverage, import grep for residual-code claims, and byte-hash (md5) duplicate detection on
files > 1 MB. No bulk opening of binary artifacts.
**Baseline for reference:** `04_SRC` suite green at 1523 passed / 7 skipped (commit `3f2582c`);
this report does not change code and does not re-run the suite.

---

## A. Executive summary

| Rank | Path | Size | Share of repo |
|---|---|---|---|
| 1 | `07_DATA/` | 134 MB | 33 % |
| 2 | `06_RESEARCH/` | 125 MB | 31 % |
| 3 | `04_SRC/` | 11 MB | 2.7 % |
| 4 | `dist/` | 2.0 MB | 0.5 % |
| 5 | `00_LOCKED/` | 1.5 MB | 0.4 % |
| 6 | `01_ARCHITECTURE/` | 520 KB | 0.1 % |
| 7 | `ARCHIVE/` | 322 KB | 0.1 % |
| 8 | `02_KNOWLEDGE_BASE/` | 236 KB | <0.1 % |
| 9 | `logs/` | 144 KB | <0.1 % |
| 10 | `05_MQL5_SAFETY/` | 92 KB | <0.1 % |
| — | `docs/` 48 KB · `config/` 4 KB | 52 KB | <0.1 % |
| | **Total (excl. `.git`)** | **405 MB** | |

Key observations:

1. **Only two trees carry almost all the weight.** `07_DATA` + `06_RESEARCH` = 259 MB of
   405 MB (64 %), and **both are already fully gitignored**. Nothing here affects clone size
   or CI; the pressure is purely local disk.
2. **`06_RESEARCH/results/` is the single largest churn area**: 118 MB / 887 files / 39
   top-level run directories, **0 files tracked** (`06_RESEARCH/results/` is ignored).
3. **`poi_kpi_pack/` alone is 65 MB (55 % of results/)**, and `run1/poi_rows.json` and
   `run2/poi_rows.json` are **byte-identical 25,352,853-byte duplicates** (md5-verified).
4. **Interpretation artifacts dominate `06_RESEARCH`**: 220 top-level `*.md` (2.4 MB) plus
   485 tracked `*.md` across the tree, versus 150 research scripts (3.0 MB excluding caches).
5. **Python bytecode caches total 9.4 MB across 22 `__pycache__/` directories** (6.1 MB of
   that under `04_SRC/tests/`), plus a 143 KB `.pytest_cache/`. All gitignored; pure junk.
6. **`dist/` is untracked** (`dist/` is gitignored, 0 files tracked) and holds exactly one
   tester pack (`SMC_v1.1-test.8_tester.zip`, 442 KB) plus a 1.5 MB copy of `04_SRC` that
   `AUTO_BUILD_RELEASE.py` regenerates. No older zip versions exist anywhere in the tree.
7. **Genuine residual-code flags are small but real**: `04_SRC/smc/logging/` (a 143-byte
   package with **zero importers**) and two real programs parked inside the gitignored
   runtime log directory (`logs/gov_ops.py`, `logs/patch_release.py`).
8. **Tracked file count is modest (817)**, so no tracked-history bloat was found; the cleanup
   opportunity is local-disk and local-hygiene, not repository size.

---

## B. Classification tables

Legend — **KEEP_RUNTIME**, **KEEP_GOVERNANCE**, **KEEP_RELEASE**, **RESEARCH_ACTIVE**,
**RESEARCH_HISTORICAL**, **RESEARCH_EPHEMERAL**, **GENERATED**, **RESIDUAL_CODE**,
**UNRELATED**, **UNKNOWN**.
`git` column = tracked? (`ignored` = covered by `.gitignore`).

### B1 — Top level

| Path | ~Size | git | Classification | Recommendation | Reason | Risk if wrong |
|---|---|---|---|---|---|---|
| `00_LOCKED/` | 1.5 MB | tracked | KEEP_GOVERNANCE | **KEEP** | 33 sources of truth (handoff, TODO, locked decisions, contracts) | **HIGH** |
| `.github/workflows/pytest.yml` | <4 KB | tracked | KEEP_RUNTIME | **KEEP** | CI definition; currently green | HIGH |
| `01_ARCHITECTURE/` | 520 KB | tracked | RESEARCH_HISTORICAL | **KEEP** (archive only per architect) | Phase 2–7 design notes + Flowcharts; still cited as design rationale | MED |
| `02_KNOWLEDGE_BASE/` | 236 KB | ignored | KEEP_RUNTIME (reference) | **KEEP** | ~11 MB chart reference material by policy (current size small) | MED |
| `04_SRC/smc/` | 3.3 MB | tracked | KEEP_RUNTIME | **KEEP** | Product path + tests | **HIGH** |
| `04_SRC/tests/` | 7.5 MB (6.1 MB = `__pycache__`) | tracked | KEEP_RUNTIME | **KEEP** (see C for caches) | 1523-test suite | **HIGH** |
| `04_SRC/logs/` | 0 B | ignored | RESEARCH_EPHEMERAL | **DELETE** (caches only) | Empty dir + `_test_refresh/events.log` from a test run | LOW |
| `05_MQL5_SAFETY/` | 92 KB | tracked | KEEP_RUNTIME | **KEEP** | EA sources (watchdog, structure draw) + shipping note | **HIGH** |
| `06_RESEARCH/` | 125 MB | mixed | see B2 | see B2/C/D | Research program | — |
| `07_DATA/` | 134 MB | ignored | KEEP_RUNTIME (data) | **KEEP** | Canonical `XAUUSD_M1.parquet` (34 MB) used by loaders/scripts; `XAUUSD_M1.csv` (100 MB) is the legacy export (see D) | MED |
| `ARCHIVE/` | 322 KB | ignored | RESEARCH_HISTORICAL | **KEEP as archive** | Already the archive target (`RECOVERY_FRAGMENTS_2026-11-08` 306 KB, `MQL5_HISTORY` 8 KB) | MED |
| `config/` | 4 KB | tracked | KEEP_RUNTIME | **KEEP** | Operator configs used by `run_live.bat` / tests | HIGH |
| `dist/` | 2.0 MB | ignored | KEEP_RELEASE | **KEEP** (latest only) | Current tester payload; regenerable via `AUTO_BUILD_RELEASE.py` | MED |
| `docs/` | 48 KB | tracked (1 spec) | UNKNOWN | **KEEP** | `BUILT_ENGINE_VS_FLOWCHART_VALIDATION.md` + `docs/superpowers/` spec | LOW |
| `logs/` | 144 KB | ignored | RESEARCH_EPHEMERAL + **RESIDUAL_CODE** | **DELETE logs**, **ESCALATE 2 `.py` files** | Runtime log dir contains two real programs (see B4) | MED |
| `.pytest_cache/`, `__pycache__/` ×22 | 9.5 MB | ignored | RESEARCH_EPHEMERAL | **DELETE** | Bytecode/test caches | LOW |
| `.superpowers/` | 4 KB | **tracked** (5 files) | UNKNOWN | **KEEP, FLAG** | Agent-tool brainstorm state is committed; owner may want it ignored | LOW |
| `.freebuff/` | — | ignored | KEEP_RUNTIME (tooling) | **KEEP** | Agent workspace metadata | LOW |
| `AUTO_BUILD_RELEASE.py` | 23 KB | tracked | KEEP_RUNTIME (ops) | **KEEP** | Builds `dist/` tester pack | MED |
| `AUTO_RELEASE_VERIFY.py` | 5.5 KB | tracked | KEEP_RUNTIME (ops) | **KEEP** | Verifies release payload | MED |
| `run_live.bat` | 1.7 KB | tracked | KEEP_RUNTIME | **KEEP** | Operator entrypoint | HIGH |
| `README.md` | 6.1 KB | tracked | KEEP_GOVERNANCE | **KEEP** (update content separately) | Project overview (known to lag current state) | LOW |

### B2 — `06_RESEARCH/` tree

| Path | ~Size | git | Classification | Recommendation | Reason | Risk if wrong |
|---|---|---|---|---|---|---|
| `results/` | **118 MB** / 887 files | ignored (0 tracked) | RESEARCH_EPHEMERAL + GENERATED | **ARCHIVE bulk, DELETE dups/caches** | Run artifacts; conclusions live in tracked `.md` notes | LOW–MED |
| `scripts/` | 4.7 MB (3.0 MB excl. cache) | 156 tracked | RESEARCH_ACTIVE + HISTORICAL | **KEEP all, ARCHIVE a stale subset** | Entrypoints for the current program are here | MED |
| `scripts/__pycache__/` | 1.7 MB | ignored | RESEARCH_EPHEMERAL | **DELETE** | Bytecode | LOW |
| `*.md` (top level) | 220 files / 2.4 MB | tracked (485 md total incl. subdirs) | RESEARCH_ACTIVE + HISTORICAL | **KEEP** (archive old phases per D) | The audit trail for every study | MED |
| `validation/` | 173 KB | md tracked, csv ignored | RESEARCH_HISTORICAL | **KEEP** | Methodology evidence | MED |
| `methodology/` | 144 KB | tracked | KEEP_GOVERNANCE (research) | **KEEP** | How studies are measured | MED |
| `experiments/` | 44 KB | md tracked, csv ignored | RESEARCH_HISTORICAL | **KEEP** | Experiment definitions | LOW |
| `architecture/` | 40 KB | tracked | KEEP_GOVERNANCE (research) | **KEEP** | Architecture notes feeding `00_LOCKED` | MED |
| `releases/TESTER_README.md` | 4 KB | tracked | KEEP_RELEASE (copy) | **KEEP** | Source for the tester README in `dist/` | LOW |
| `MENU_CONFIRM_STREAM_SMOKE_RUN.log` | 3.6 KB | tracked | UNRELATED | **DELETE (after confirm)** | Smoke-run console capture committed next to its note | LOW |
| `MENU_FUNNEL_DEBUG_RUN.log` | 1.8 KB | tracked | UNRELATED | **DELETE (after confirm)** | Same pattern | LOW |
| `R0_TRIGGER_ADMISSION_MAP.md` | 13 KB | **untracked** | RESEARCH_ACTIVE | **KEEP / commit when ready** | Today's trigger-admission work | LOW |
| `scripts/r1_pure_tag_books.py` | 27 KB | **untracked** | RESEARCH_ACTIVE | **KEEP / commit when ready** | Today's R1 script | LOW |

### B3 — `06_RESEARCH/results/` (39 run dirs, 118 MB, 0 tracked)

Grouped, largest first. All entries are **RESEARCH_EPHEMERAL / GENERATED** regenerable by their
scripts; the value is in re-running, not in the bytes.

| Dir | ~Size | Program / phase | Recommendation | Reason | Risk if wrong |
|---|---|---|---|---|---|
| `poi_kpi_pack/` | **65 MB** | POI KPI study (`poi_kpi_pack`, pre-Nov) | **ARCHIVE 1 run, DELETE `run2` dup + `_smoke_month`** | `run1`/`run2` `poi_rows.json` md5-identical (24 MB wasted); smoke month is a partial run | LOW |
| `pfe3_expert_pack/` | 13 MB | PFE-3 expert validation pack | **ARCHIVE** | 7.4 MB PDF regenerable by `pfe3_expert_pack.py`; superseded by later expert review | LOW |
| `product_1y_one_story/` | 5.8 MB | product_1y one-story (Nov 15–16) | **KEEP** | Current program output | LOW |
| `p1_visual_levels/` | 4.5 MB | P1 visual liquidity levels (Nov 10) | **KEEP (active O1–O5)** | Feeds open decisions O1–O5 | MED |
| `track_a_sweep_ledger/` | 4.0 MB | Track A sweep ledger | **KEEP** | 3.8 MB `events_sweep.csv` is the ledger of record for Track A | MED |
| `scan1a_ltf_no_poi/` | 3.3 MB | Scan-1A (Nov 16) | **KEEP** | Current program | LOW |
| `pfe2_6m/` | 3.2 MB | PFE-2 six-month product backtest | **ARCHIVE** | Superseded by product_1y / product_6m runs | LOW |
| `p1_wrong_extreme_audit/` | 3.1 MB | P1 wrong-extreme audit | **KEEP (active)** | Feeds the same O1–O5 package | MED |
| `scan1b_ltf_with_poi/` | 2.2 MB | Scan-1B (Nov 16) | **KEEP** | Current program | LOW |
| `l1_h4_stage0a_enriched/` | 2.2 MB | L1 H4 stage 0A (Nov 10) | **KEEP** | Recent layer-fidelity evidence | LOW |
| `ungated_event_ledger_p1/` | 2.1 MB | P1 ungated event ledger | **KEEP** | Ledger of record | MED |
| `l1_h4_sweep_fidelity/` | 2.1 MB | L1 H4 sweep fidelity | **KEEP** | Recent evidence | LOW |
| `product_9_fills_decode/` | 1.7 MB | product_9 fills decode | **KEEP** | Recent product decode | LOW |
| `p1_rescore_pack/` | 1.5 MB | P1 re-score pack | **KEEP** | Active P1 chain | LOW |
| `menu_trade_charts_1m/` | 1.0 MB | menu trade charts (1M) | **ARCHIVE (if not regenerated soon)** | Chart dump; note is tracked | LOW |
| `baseline_pre_fix/` | 764 KB | pre-fix baseline | **ARCHIVE** | Historical comparison point; `00_LOCKED/BASELINE_…` is the governed record | LOW |
| `open_decisions/` | 754 KB | O1–O5 open decisions | **KEEP** | Live decision package | MED |
| `plan_complement_charts/` | 748 KB | plan-complement charts | **ARCHIVE** | Chart-only pack, note tracked | LOW |
| `post_c2_diagnostic/` | 530 KB | post-C2 diagnostic | **ARCHIVE** | Superseded by C2A/C2B/C3 notes | LOW |
| `product_6m_one_story/` | 506 KB | product_6m one-story | **KEEP** | Current program sibling | LOW |
| `p2a_pool_inventory/` + `p2b_sweep_attribution/` | 370 KB | P2 liquidity pools | **KEEP** | Pool registry evidence | LOW |
| `pfe15_smoke/` | 143 KB | PFE-1.5 composition smoke | **ARCHIVE** | Smoke only | LOW |
| `bce_starvation/` | 121 KB | BCE starvation probe (Nov 16) | **KEEP** | Today's analysis | LOW |
| `one_story_oct/`, `one_story_oct_b/` | 170 KB | one-story October pilot | **ARCHIVE** | Superseded pilots, notes tracked | LOW |
| `confirm_vs_zone_opt4_wider/` | 52 KB | OPT-4 wider window | **ARCHIVE** | Note `OPT4_WIDER_JOIN_NOTE.md` is the record | LOW |
| `p1_independent_verify/`, `plan_complement_ledger_post_f5f7/`, `s2_menu_confirm_lag/` | 57 KB | small verifications | **KEEP** | Cheap and cited | LOW |
| `**/run.log` | 27 files | run consoles | **DELETE** | Console noise duplicated into notes | LOW |

### B4 — Root, residual code and unrelated items

| Path | ~Size | git | Classification | Recommendation | Reason | Risk if wrong |
|---|---|---|---|---|---|---|
| `04_SRC/smc/logging/` (only `__init__.py`) | 143 B | tracked | **RESIDUAL_CODE** | **FLAG ONLY — do not delete this turn** | `grep -r "smc.logging"` over the whole tree returns **0 importers**; package is dead. Removal needs an architect decision because it is a public module name | MED |
| `04_SRC/smc/essence/` | 56 KB | tracked | KEEP_RUNTIME (research contract) | **KEEP** | 0 product-path importers, **but** imported by `06_RESEARCH/scripts/essence_v1_slice_capture.py` and governed by `00_LOCKED/ESSENCE_CONTRACT_V1.md` — **not residual** | HIGH |
| `logs/gov_ops.py` | 8 KB | **ignored** | **RESIDUAL_CODE / MIGRATE** | **ESCALATE** (would be lost by log cleanup) | Real governance-ops program sitting in a gitignored log dir | **HIGH** |
| `logs/patch_release.py` | 8 KB | **ignored** | **RESIDUAL_CODE / MIGRATE** | **ESCALATE** (would be lost by log cleanup) | Release-patch tool in the same gitignored dir | **HIGH** |
| `logs/ops_smoke/` | 56 KB | ignored | RESEARCH_EPHEMERAL | **DELETE** | Smoke run output | LOW |
| `logs/*.log` (`o1_c3`, `o2_htf_sweep`, `o4`, `one_story_oct`, …, 8 files) | ~22 KB | ignored | RESEARCH_EPHEMERAL | **DELETE** | Console captures already summarized in notes | LOW |
| `logs/_test_refresh/` | 4 KB | ignored | RESEARCH_EPHEMERAL | **DELETE** | Test-run leftovers | LOW |
| `.superpowers/brainstorm/**` | 4 KB | **tracked** (5 files) | UNKNOWN | **KEEP, FLAG** | Tool state committed to the repo; owner preference needed | LOW |
| `dist/04_SRC/` | 1.5 MB | ignored | GENERATED | **KEEP** | Release payload copy; regenerated by `AUTO_BUILD_RELEASE.py` | LOW |
| `07_DATA/XAUUSD_M1.csv` | **100 MB** | ignored | GENERATED / legacy | **ARCHIVE** (keep locally, delete only after owner confirms) | `parquet_loader.py` calls the **parquet** canonical; the 100 MB CSV is the raw export behind it | MED |
| `07_DATA/XAUUSD_M1.parquet` | 34 MB | ignored | KEEP_RUNTIME (data) | **KEEP** | Canonical backtest series named in `parquet_loader.py` | **HIGH** |
| `ARCHIVE/RECOVERY_FRAGMENTS_2026-11-08/` | 306 KB | ignored | RESEARCH_HISTORICAL | **KEEP** (already archived) | Recovery evidence | MED |

### B5 — `06_RESEARCH/scripts/` (156 tracked, 150 `.py`, 3.0 MB real)

Not a delete candidate set — every script is a reproducibility artifact. The split that matters:

| Group | Examples | Classification | Recommendation |
|---|---|---|---|
| Current program (Nov 14–16) | `r1_pure_tag_books.py`*, `bce_starvation_probe.py`, `scan1a_ltf_no_poi.py`, `scan1b_ltf_with_poi.py`, `product_1y_one_story_diag.py`, `product_1y_one_story_report.py`, `product_6m_one_story_*.py`, `product_9_fills_decode.py`, `stage3_trigger_visibility.py`, `phase3_structure_funnel.py`, `pfe3_expert_pack.py`, `frozen_funnel_6m_post_tp.py` | RESEARCH_ACTIVE | **KEEP** (near the top of the tree) |
| Nov 8–13 active layer/console work | `l1_h4_*`, `c1_multi_tf_parity_smoke.py`, `menu_*`, `post_c2_*`, `pfe15_composition_smoke.py`, `essence_v1_*` | RESEARCH_ACTIVE → HISTORICAL | **KEEP**; archive only if the program closes |
| Nov 8 bulk "phase" studies | `phase*_`, `fr*_`, `f_*`, `fill_takeability_study.py`, `entry_representation_*.py`, `ltf_*`, `coupled_mtf_*`, `coincidence_count.py`, `hypothesis_outcome_study.py`, `d1_f1f2_resample.py`, `a4_identity_chart_checklist.py`, `build_expert_pdfs.py` | RESEARCH_HISTORICAL | **KEEP tracked** (audit trail); no archive needed while they are 3 MB total |
| Launchers | `launch_detached.ps1`, `launch_fill_leg_capture.ps1`, `lib/` | KEEP_RUNTIME (research) | **KEEP** |

`*` = currently untracked.

**Duplicate-script candidates:** several "report + diag" pairs share a prefix
(`product_6m_one_story_diag`/`_report`, `product_1y_one_story_diag`/`_report`,
`fr4_fidelity_baseline`/`fr4_armed_poi_fate`, `confirm_vs_zone_opt1_smoke`/`opt4_smoke`,
`f_timing_labels`/`_followon`/`_wider`). By md5 they are **not** identical (no false-merge
risk), but they are candidates for a human "keep one entrypoint" review — **no action proposed
this turn**.

---

## C. Safe DELETE list (LOW risk only)

Every item below is **gitignored or byte-duplicated**, regenerable, and touches no product,
governance or research-record file.

| # | Path | ~Size | Why it is safe |
|---|---|---|---|
| 1 | `**/__pycache__/` (22 dirs) | 9.4 MB | Python bytecode; gitignored; rebuilt on import |
| 2 | `.pytest_cache/` | 143 KB | pytest cache; gitignored |
| 3 | `06_RESEARCH/scripts/__pycache__/` | 1.7 MB | (already counted in #1 — listed for locality) |
| 4 | `logs/*.log` (8 files) | ~22 KB | Console captures; conclusions already in tracked notes |
| 5 | `logs/_test_refresh/` | 4 KB | Test-run leftovers |
| 6 | `logs/ops_smoke/` | 56 KB | Smoke-run output |
| 7 | `04_SRC/logs/_test_refresh/` | 4 KB | Test-run leftovers (dir otherwise empty) |
| 8 | `06_RESEARCH/results/**/run.log` (27 files) | ~120 KB | Run consoles duplicated into notes/results |
| 9 | `06_RESEARCH/results/poi_kpi_pack/run2/poi_rows.json` | **24 MB** | md5-identical to `run1/poi_rows.json` |
| 10 | `06_RESEARCH/results/poi_kpi_pack/_smoke_month/` | 4.8 MB | Partial "smoke" month run, not a study result |
| 11 | `06_RESEARCH/MENU_CONFIRM_STREAM_SMOKE_RUN.log` | 3.6 KB | **tracked** smoke console; delete only with a commit + architect nod |
| 12 | `06_RESEARCH/MENU_FUNNEL_DEBUG_RUN.log` | 1.8 KB | **tracked** smoke console; same condition |

**Safe-delete total: 12 entries, ≈ 38.5 MB** (≈ 9.6 MB excluding the duplicate JSON + pycache
would still be the low-risk floor).

> Items 11–12 are the only *tracked* entries; they need a normal commit, so they are listed as
> "delete after architect confirmation", not as local junk.

---

## D. ARCHIVE list (propose path, do not move)

Proposed destinations: `06_RESEARCH/_archive/results/` for run artifacts (keeps them out of the
active results tree but on disk), `06_RESEARCH/_archive/scripts/` for superseded entrypoints,
`ARCHIVE/research_phases/` for closed-phase reports (the existing `ARCHIVE/` root is already
gitignored, which is where historical material belongs).

| # | Path | ~Size | Proposed destination | Reason |
|---|---|---|---|---|
| 1 | `06_RESEARCH/results/poi_kpi_pack/` (keep `run1`) | 65 MB → ~37 MB after dup delete | `06_RESEARCH/_archive/results/poi_kpi_pack/` | Pre-Nov KPI study, superseded; conclusions in `POI_KPI_REPORT.md` |
| 2 | `06_RESEARCH/results/pfe3_expert_pack/` | 13 MB | `_archive/results/` | Expert PDF regenerable by `pfe3_expert_pack.py` |
| 3 | `06_RESEARCH/results/pfe2_6m/` | 3.2 MB | `_archive/results/` | Superseded by product_1y/6m runs |
| 4 | `06_RESEARCH/results/baseline_pre_fix/` | 764 KB | `_archive/results/` | Historical comparison point |
| 5 | `06_RESEARCH/results/post_c2_diagnostic/` | 530 KB | `_archive/results/` | Superseded by C2A/C2B/C3 notes |
| 6 | `06_RESEARCH/results/plan_complement_charts/` | 748 KB | `_archive/results/` | Chart-only pack |
| 7 | `06_RESEARCH/results/menu_trade_charts_1m/` | 1.0 MB | `_archive/results/` | Chart-only pack |
| 8 | `06_RESEARCH/results/pfe15_smoke/` | 143 KB | `_archive/results/` | Smoke only |
| 9 | `06_RESEARCH/results/one_story_oct/`, `one_story_oct_b/` | 170 KB | `_archive/results/` | Superseded October pilots |
| 10 | `06_RESEARCH/results/confirm_vs_zone_opt4_wider/` | 52 KB | `_archive/results/` | Note is the record |
| 11 | `07_DATA/XAUUSD_M1.csv` | **100 MB** | `07_DATA/_archive/` (or delete after owner confirm) | Canonical loader uses the parquet; raw CSV is the only redundant giant |
| 12 | Historical phase reports: `PHASE_B_FIDELITY_REPORT.md`, `PHASE_C_BASELINE_REPORT.md`, `PHASE_C_PERF_AUDIT.md`, `PHASE_D_DIVERGENCES.md`, `PHASE_R1/R2/R3/R4_*`, `PHASE01_INFORMATION_SET_NOTE.md`, `PHASE0_EVENT_SCORE_SHEET.md`, `PHASE2_LAYER_CONTRACTS_NOTE.md`, `PHASE_0_1_2_COMBINED_AUDIT.md`, `DAILY_CHANGE_REPORT_2026-10-25.md`, `INDEPENDENT_*_AUDIT_2026-10-1*.md`, `PROJECT_WIDE_AUDIT_2026-10-06.md`, `QUANT_AUDIT_2026-10-08.md`, `PERM_HARDENING_AUDIT_2026-10-08.md` | ~400 KB | `ARCHIVE/research_phases/` | Closed phases; kept for audit trail only if architect wants the tree leaner |
| 13 | Nov-8 bulk study scripts (see B5 group 3) | ~1.5 MB | **NOT recommended** | They are the reproducibility record and cost almost nothing; listed only as the option |
| 14 | `dist/` older packs | 0 MB | n/a | **No older zips exist** — exactly one pack (`v1.1-test.8`). Archive criterion satisfied already |

**Archive candidates: 13 substantive entries** (item 13 explicitly *not* recommended; item 14 is a
no-op confirmation). Realistic reclaim if 1–11 are moved off the active tree: **≈ 85–185 MB**
(185 MB only if the 100 MB CSV also leaves `07_DATA`).

---

## E. DO NOT TOUCH

| Path | Why |
|---|---|
| `00_LOCKED/**` (33 files, incl. `SESSION_HANDOFF.md`, `POST_V1_ACTIVE_TODO.md`, `LOCKED_DECISIONS.md`, `CHANGELOG.md`, contracts) | Governance sources of truth. **REQUIRES_ARCHITECT** for any change; default **KEEP** |
| `04_SRC/smc/**` (runtime, strategy, risk, triggers, config) | Product path; out of scope for hygiene |
| `04_SRC/tests/**` | 1523-test suite; deleting a test is never hygiene |
| `.github/workflows/pytest.yml` | CI source of truth, currently green |
| `config/live_demo.json`, `config/live_tester.json`, `config/live_console_dryrun.json`, `run_live.bat`, `AUTO_BUILD_RELEASE.py`, `AUTO_RELEASE_VERIFY.py` | Operator + release path |
| `dist/SMC_v1.1-test.8_tester.zip` + `dist/TESTER_README.md` + `dist/VERSION.txt` | The current (only) tester pack |
| `07_DATA/XAUUSD_M1.parquet` | Canonical backtest dataset referenced by `parquet_loader.py` |
| `05_MQL5_SAFETY/*.mq5` | Shipped EA sources |
| `06_RESEARCH/scripts/` referenced by `SESSION_HANDOFF` / `POST_V1_ACTIVE_TODO` / today's work (`r1_pure_tag_books.py`, `bce_starvation_probe.py`, `scan1a/1b`, `product_*`, `stage3_trigger_visibility.py`, `phase3_structure_funnel.py`, `pfe3_expert_pack.py`) | Active program entrypoints |
| `06_RESEARCH/*.md` for open decisions `OPEN_DECISION_O1…O5`, `R0_TRIGGER_ADMISSION_MAP.md`, `BCE_STARVATION_PROBE_REPORT.md`, `SCAN1_*`, `RESEARCH_PROOF_REGISTER_2026-10.md` | Current research record |
| `logs/gov_ops.py`, `logs/patch_release.py` | **Do not delete with log cleanup** — they are code, not logs; escalate for relocation first |

---

## F. Explicit statement

**NO ACTIONS TAKEN.** This report is the only file created. No deletion, move, rename, `git rm`,
commit or push was performed; no strategy/risk/threshold/locked-constant/CI file was edited.
`04_SRC` was not modified. Awaiting **Lead Architect + owner** review of the lists above.

Suggested order of approval, when the architect is ready:

1. Approve section **C** items 1–10 (local junk, 38 MB, zero product/governance impact).
2. Confirm whether `logs/gov_ops.py` and `logs/patch_release.py` should move into a tracked
   tooling path **before** any `logs/` cleanup.
3. Decide section **D** items 1–10 (research archive tree) and whether the 100 MB
   `XAUUSD_M1.csv` is truly redundant.
4. Decide `04_SRC/smc/logging/` (dead package) — separate, explicit architect call.
5. Optional: decide whether `.superpowers/` tool state should be gitignored.
