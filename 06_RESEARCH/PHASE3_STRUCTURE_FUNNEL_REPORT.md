# PHASE 3 — STRUCTURE FUNNEL + INFORMATION-FLOW AUDIT REPORT

**Status:** COMPLETE 2026-09-23 (Choice 1 sequence, Phase 3 of 4) — **PASS**.
**Window (locked):** exec 2025-10-01 → 2025-10-31 (full month, M5), M1 loaded from 2025-09-01 (warm-up) — the primary window ran in full; no degradation to the 14-day fallback.
**Scope:** identification + flow audit on the unified product path. NOT expectancy, NOT paper trading, NOT F-timing. No strategy code changed; `locked_constants.py` diff empty; suite still green (726).
**Artifacts:** `06_RESEARCH/results/phase3_structure_funnel/run1/` (+ identical `run2/`), charts `results/phase3_structure_funnel/charts/`.

---

## 1. Window + driver composition (exact modules)

| Element | Module |
|---|---|
| Data | `07_DATA/XAUUSD_M1.parquet` via `smc.data.parquet_loader.load_ohlcv_parquet` + `smc.data.resample.resample_multi` (M5/H1/H4/D1) |
| Detection cadence | one batch per new H1 close (product contract §1) |
| **Detection/arming seam** | **`smc.orchestration.multi_tf_runtime.MultiTFProductRuntime.run_batch`** — the C1 product seam (H4+H1 required, D1 forwarded to M8, honest `<= as_of` prefixes, shared `ZoneDedup`, `MissingHtfSeriesError` loud-fail) |
| Pillar histogram instrumentation | `MultiTFDetectionDriver.validate_multi` wrapped (Phase-2-snapshot composition) to read per-POI `ValidationResult.first_failure` — the seam's report carries counts only by contract §2 design; wrapper restored in `finally` |
| Arm / scan / risk | `PipelineEngine.arm_at` → `PipelineAdapter.generate_candidates` (scan capped at current bar, §5 feed after scan) → `BacktestRunner` risk → `PendingOrderBook` |
| Route context | `adapter.note_route_context(displacement, pillar_path)` — the same identity seam live uses |
| Instrumentation | `engine.scan_route` + adapter-module `candidate_from_route` wrapped for counters (FR-4 pattern, restored in `finally`) |
| Config | equity 10,000 · risk 1% · spread 0.0 · news dormant · all sessions — machine-completeness, NOT cost realism (FR-4 convention) |

---

## 2. Funnel table

| Stage | Count | Notes |
|---|---:|---|
| M5 bars processed | 6,324 | full October month |
| HTF batches | 527 | one per new H1 close; 0 batch errors |
| detected_raw (H4 / H1) | 7,696 / 7,991 | per-TF model output summed over batches |
| merged (H4 / H1) | 3,848 / 3,716 | 7,564 merged POIs total |
| **Pillar first failures** | **P2:fail 6,549 · P3:fail 418 · P1:fail 339** | short-circuit at first hard pillar; PASS 258 |
| passed validation (H4 / H1) | 73 / 185 | 258 total |
| duplicate zones suppressed | 250 | shared `ZoneDedup` (contract §2) |
| **armed (unique)** | **8** | H4 3 · H1 2 · D1(M8 zone tf) 3 — armed_m8 = 5 |
| skipped_tracked | 0 | no double-arm attempts |
| scans executed | 100 | scan calls over armed POIs (§24-bounded) |
| **routes** | **4** | all Trigger F; 4/4 M8 |
| placed | 1 | TP present 1/1 |
| intents (R9) | armed 3 · placed 1 · expired 0 | from the runner's `IntentBook` event log |
| **fills** | **1** | Trigger F, M8 POI poi-008910 |
| trades closed | 1 | see `run1/trades.csv` |

Per-day breakdown: `run1/funnel_by_day.csv`.

**P2 dominance explained (factual, not fixed):** 6,549/7,306 first failures (89.6%) die at Pillar 2 — the displacement gate. Two structural reasons, both by design: (a) the per-POI attribution rule gives a POI no displacement entry unless a same-direction sweep precedes it, and a failed/weak sweep impulse fails the §3 magnitude test; (b) detection runs on H4+H1 where zones far from any sweep impulse are common. This matches the Phase 2 snapshot (84.3% on 14 days) and the Phase 2 note's contract: UNAVAILABLE/FAIL is the honest outcome, never an invented displacement. No tuning is permitted or performed.

## 3. Drop-off interpretation (factual)

- detected → merged: ~49% (per-batch re-detection of the same structures; the geometric dedup then suppresses 250 repeat episodes at arm time).
- merged → passed: 3.4% — dominated by P2 (displacement) as above; P3 (premium/discount) kills 418 (5.7%); P1 (naked level) kills 339 (4.6%).
- passed (258) → armed (8): the seam's dedup counts 250 duplicates — the same zones re-validated on later batches are suppressed, so 258 "passed" events collapse to 8 unique armed POIs. This is the contract's arm-once rule working as designed.
- armed (8) → routes (4): 4 POIs never fired within the §24 give-up window (fates tracked per POI in FR-4-style state feed; 100 scans across 8 armed POIs).
- routes (4) → placed (1): R7 market-reference guard + risk gates filtered the rest; 3 intents armed (place-on-reentry deferred placements) of which 1 placed.
- placed (1) → fills (1): the R9 intent placement filled at the on-zone limit — the same complete chain class R9 proved on the FR-4b window.

## 4. Sample audit findings (handoff gaps only)

`sample_audit.csv` — 8 rows = ALL armed POIs (armed < 12 → the full-armed-set rule; no under-sample note needed since nothing was skipped).

| Check | Result |
|---|---|
| zone bounds present | 8/8 |
| model_tags non-empty | 8/8 |
| pillar_path non-empty (`PASS:1+2+3+4+5;inducement=…`) | 8/8 |
| displacement magnitude present on armed set | 8/8 |
| routed rows carry entry + original_sl (+ TP) | 1/1 (poi-008910: entry 4244.725 = zone-high re-anchor, SL 4245.440, TP 4275.664 = 4×ATR fallback path) |
| **flow_gaps** | **NONE** |

`entry_anchor` is `n/a:not_exported` — the anchor provenance field exists in the trigger's signal data but is not exported as a standalone column on this path; recorded as a gap, not back-filled.

## 5. Zero-trade / low-route honesty

The window produced 1 fill from 8 armed POIs — a thin book, consistent with the FR-4/FR-4b lineage on post-reset frozen rules (FR-4: 0 routes; FR-4b: 0 fills; R9 smoke: 1 complete chain). No retuning, no gate widening, no threshold edits: the funnel's job is to make the drop-offs visible and attributed, which it now does end-to-end on the unified machine. The prior fill-regime context (FR-3.1 anchor → R7 guard → R8 rest bars → R9 intents) is inherited unchanged.

## 6. Phase 3 exit

- Funnel JSON complete with non-null core counts (detected / merged / passed / armed / routes / placed / fills): **YES** (intent counters now real; entry_anchor honestly N/A).
- Determinism: run1 vs run2 — **semantic funnel counts identical** (only `tag` + `runtime_seconds` differ).
- Sample audit with real rows: **YES** (8/8 armed, 0 flow gaps).
- No strategy code changes: **YES** (`git diff` on `04_SRC/smc/` unchanged by this task; wrappers restored in `finally`).
- Suite: **726 passed** re-run.

**PHASE3_STATUS: PASS**

## 7. Residuals for Phase 4

1. **Single-month window** — the funnel is one October month; Phase 4's frozen run may extend the window but must stay diagnostic-first if the funnel remains thin.
2. **Intent counters via event-log counting** — `IntentBook` exposes a lifecycle event list, not aggregate counters; the script counts events by kind. A counter property on the book would be a (production-surface) nicety, not a correctness issue.
3. **entry_anchor not exported** — route-time anchor provenance stays inside `signal_data_json`; a dedicated export column would close the only sample-audit N/A.
4. **No F-trigger-level funnel split inside routes** — all 4 routes are F; per-trigger funnel splits become meaningful only with multi-trigger books (later phases).
5. **Chart set is armed-POI geometry** — the routed POI chart is labeled with entry/SL/TP; nothing here is a fill-quality or timing claim.
