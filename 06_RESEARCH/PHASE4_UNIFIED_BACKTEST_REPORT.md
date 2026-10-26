# PHASE 4 — FROZEN BACKTEST (+ PAPER DRY PATH) ON THE UNIFIED MACHINE

**Status:** COMPLETE 2026-09-23 (Choice 1 sequence, Phase 4 of 4) — **PASS**.
**Window (locked):** M1 warm-up from 2025-08-01; exec **2025-09-01 → 2025-11-30** (3 months, M5, 17,840 bars) — the primary window ran in full (~189 s/run ×2).
**Scope:** final Choice-1 measurement gate. Frozen config, deterministic dual run, funnel + trade outcomes reported separately. NOT edge, NOT a retuning gate, NOT a Phase D live session.
**Artifacts:** `06_RESEARCH/results/phase4_unified/` — `summary.json`, `run1/`, `run2/` (funnel_summary.json, trades.csv, report.json, sample_audit.csv, armed_records.json, funnel_by_day.csv), `paper_dry_note.json`.

---

## 1. Window + exact driver/module graph

| Element | Value |
|---|---|
| Data | `07_DATA/XAUUSD_M1.parquet` → `load_ohlcv_parquet` → `resample_multi` (M5/H1/H4/D1) |
| Detection | **`smc.orchestration.multi_tf_runtime.MultiTFProductRuntime.run_batch`** (C1 product seam) — H4+H1 required, D1 forwarded to M8, honest `<= as_of` prefixes, shared `ZoneDedup`, loud-fail `MissingHtfSeriesError` |
| Cadence | one batch per new H1 close (contract §1) |
| Arm → scan → risk | `PipelineEngine.arm_at` → `PipelineAdapter.generate_candidates` (§24-capped scan, §5 feed after scan) → `BacktestRunner` (risk gate → pending limits → R9 intents → manage) |
| Composition source | `phase3_structure_funnel.run` **imported, not forked** (same file, different locked window) |
| Instrumentation | FR-4 pattern wrappers (scan_route / candidate_from_route / validate_multi histogram), all restored in `finally` |

**Frozen config (documented fields):** equity 10,000 · risk_fraction 0.01 · spread_price 0.0 · news_events [] · sessions ASIA/LONDON/NEW_YORK · detection H4+H1 · M8 HTF = D1 when available · execution M5 · **no diag flags** — FR-3 zone gate, R7 place guard, R8 rest bars, R9 intents all live. No locked constant, pillar, trigger, zone-band, or R7/R9 number touched (`locked_constants.py` diff empty).

## 2. Funnel table (run1 = run2 semantically)

| Stage | Count |
|---|---:|
| M5 bars processed | 17,840 |
| HTF batches | 1,488 (0 errors) |
| detected_raw (H4 / H1) | 22,472 / 22,650 |
| merged POIs | 20,654 |
| first failures | **P2:fail 18,050 (86.9%)** · P3:fail 1,084 · P1:fail 755 |
| passed validation | 765 |
| duplicates suppressed | 748 |
| **armed (unique)** | **17** (14 M8; H4 5 / H1 8 / D1 4) |
| scans | 208 (per summary) |
| **routes** | **8** — all Trigger F, 7/8 M8 |
| placed | 1 (TP 1/1) |
| R9 intents | armed 6 · placed 1 · expired 0 |
| **fills / trades** | **1 / 1** |

## 3. Trade summary (diagnostic only — n=1 proves wiring, nothing else)

| Field | Value |
|---|---|
| Ticket | 1 — LONG, Trigger F, POI poi-024417 (M8, D1 zone 4179.355–4244.725) |
| Entry / Exit | limit 4244.725 (zone-high re-anchor; signal_data `entry_anchor=zone_edge_reanchor`) → SL close 4245.440 |
| original_sl | 4177.035 (BE-modified per PureRunner; placement stop preserved in export) |
| Exit kind | stop_loss (BE +0.0715 raw) after 52 bars (2025-10-20 05:50 → 10:10 UTC) |
| Net PnL (diagnostic) | **+0.0715 raw** (0.10 lots) — the same complete-chain class the R9 smoke produced |
| Exit mix | 1 SL(BE) / 0 TP / 0 Friday |

**Not proven:** any edge, robustness, regime stability, live-cost viability. One BE-scratch trade over 3 months is a *wiring* result, not a performance result. No optimization is authorized or performed on these numbers.

## 4. Determinism proof

| Check | Result |
|---|---|
| `trades.csv` byte-identical | **YES** — SHA-256 `7b3e8659…552719` both runs |
| `report.json` byte-identical | **YES** — SHA-256 `37f0568b…cd2bfbe` both runs |
| Semantic funnel fields | **equal** (only `tag` + `runtime_seconds` differ) |
| Verdict | **PASS** |

## 5. Comparison to the Phase 3 October slice (reference, not equality)

| Metric | Phase 3 (Oct-only) | Phase 4 (3-month, October inside) |
|---|---:|---:|
| armed | 8 | 17 |
| routes | 4 | 8 |
| fills | 1 | 1 (same BE-scratch class) |

The 3-month run is a superset measurement (more warm-up, longer batch history, different prefix shapes); the October sub-slice is not expected to equal the October-only run and is recorded as a reference row only. Directionally consistent: same funnel shape, same P2 dominance, same thin route/fill tail.

## 6. Honesty section

- **Sample size:** 1 trade. Nothing about expectancy, WR, PF, or drawdown is measurable at n=1; the trade table exists to prove the unified machine's completeness, not its profitability.
- **All-F routes (8/8):** the frozen trigger geometry + M8-heavy armed set routes only F under the locked rules. This is the as-coded behavior, documented — not a defect patched here.
- **P2 drop-off (86.9%):** attribution honesty (no same-direction sweep ⇒ no displacement ⇒ fail), consistent across Phase 2 (84.3%), Phase 3 (89.6%), and this run. Not tuned.
- **Placed(1) vs routes(8):** R7 market-reference guard + risk gates stop 7 of 8 candidates at place time; 6 arm R9 intents (place-on-reentry deferral), of which 1 eventually placed and filled. The September trend-runaway class (FR-4b forensic) remains counted waits.
- **Demo PnL is never edge** (paper dry check below is wiring-only).

## 7. Paper dry-run wiring note

`paper_dry_note.json`: **DONE, no MT5 required.** A real-data slice (2025-09-20→26) drove `PaperRunner.arm_multi_tf` with a null connector: 1 batch, degraded=False, armed=0 on that quiet slice, **0 dry-run orders sent**; `runner.runtime is MultiTFProductRuntime` (the shared C1 seam) confirmed by type check. Wiring-only — Phase D ops remains the separate terminal-validation track.

## 8. Residuals

1. **entry_anchor not exported** as a standalone column (visible inside `signal_data_json` on the trade row) — export-gap item for the residual-engineering fork.
2. **HTF depth** — 300-bar live fetch / prefix-based research windows; deep-history warm-up remains unprovisioned (contract residual).
3. **Paper R9 depth** — the paper dry smoke proves delegation + dry-run recording; a paper-side intent lifecycle drill on a filled window remains a Phase D/exness-ops item.
4. **Intent counters** — counted from the `IntentBook` event log (aggregate-counter property would be a nicety).
5. **Single 3-month window** — regime coverage limited; any broader measurement is a NEW dated ruling, not a silent extension.

## 9. Verdict

**PHASE4_STATUS: PASS** — dual-run determinism proven at byte level, funnel + trade artifacts complete, zero logic changes, suite green (726). The Choice-1 machine (Phase 0 contract → C1 runtime → Phase 2 contracts → Phase 3 funnel → this frozen measurement) is **complete and measured**.
