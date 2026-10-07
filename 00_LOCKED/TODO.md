# TODO — SMC BOT Task Board

**Last Updated:** 2026-09-15
**Current Phase:** ✅ V1 COMPLETE — Phase 7 Live Readiness + MQL5 Safety Watchdog. Post-V1 work is governed by **`POST_V1_PLAN_OF_ACTION.md`** (binding order: Phase A Data Acceptance → B fidelity backtest → C 5y baseline → D demo → E V1.1). **Phase A — Data Acceptance: CLOSED 2026-09-09 (PASS; A5 ruled option (a) — baseline WITHOUT Trigger D). Phase B — Short Fidelity Backtest: CLOSED 2026-09-14 (PASS). Phase C — Full 5-Year Baseline: CLOSED 2026-09-19 (Lead Architect sign-off). **ACTIVE PROGRAM: V1.1 RUNTIME BASELINE FROZEN (2026-09-24 — `00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md`); next = Phase D watchdog GUI attach + stale-heartbeat drill or a dated research ruling.** Completed foundation: PRODUCT RUNTIME UNIFICATION (owner "Choice 1", 2026-09-23) — Phase 0 contract + Phase 1/C1 one multi-TF runtime (live = paper = research) + Phase 2 contracts + Phase 3 funnel + Phase 4 frozen backtest, ALL COMPLETE/PASS; Track A residuals COMPLETE; Phase D HTF probe PASS. Track R diagnosis CLOSED; Foundation Fidelity Reset (FR-1→R9) a completed prerequisite; Phase D ops parallel only. Day-to-day checklist: `POST_V1_ACTIVE_TODO.md` (this file tracks the V1 build only — do not duplicate its checkboxes here).**
**Architecture:** Python-First + MQL5 Safety Watchdog (Option A Locked)

---

## High-Level Phases

| Phase | Name | Status |
|-------|------|--------|
| **0** | Foundations / Infrastructure | ✅ COMPLETE (2026-09-06) |
| 1 | Core Detection — Liquidity + Displacement + Swing Gate | ✅ COMPLETE (2026-09-06) |
| 2 | POI Classification — M1–M8 Modular Tags | ✅ COMPLETE (2026-09-06) |
| 3 | 5-Pillar Validation | ✅ COMPLETE (2026-09-07) |
| 4 | LTF Triggers + Python Execution | ✅ COMPLETE (2026-09-07) |
| 5 | Risk Layer — Port v25_DIAG to Python | ✅ COMPLETE (2026-09-07) |
| 6 | Backtesting & Paper Trading | ✅ COMPLETE (2026-09-09) |
| 7 | Live Readiness + MQL5 Safety Watchdog | ✅ COMPLETE (2026-09-09) |

---

## Phase 0: Foundations / Infrastructure

**Goal:** Set up project structure, shared types, configuration loading, data access layer, and direct MT5 API connection.
**Effort:** ~1 day
**Difficulty:** Easy

### Project Structure

- [x] Create `smc/` package root with `__init__.py`
- [x] Create `smc/config/` directory
- [x] Create `smc/core/` directory
- [x] Create `smc/data/` directory
- [x] Create `smc/utils/` directory
- [x] Create `smc/detection/` directory (placeholder package, for Phase 1)
- [x] Create `smc/poi/` directory (placeholder package, for Phase 2)
- [x] Create `smc/validation/` directory (placeholder package, for Phase 3)
- [x] Create `smc/triggers/` directory (placeholder package, for Phase 4)
- [x] Create `smc/execution/` directory (placeholder package, for Phase 4)
- [x] Create `smc/risk/` directory (placeholder package, for Phase 5)
- [x] Create `smc/logging/` directory (placeholder package, for Phase 5)
- [x] Create `smc/backtest/` directory (placeholder package, for Phase 6)
- [x] Create `smc/paper/` directory (placeholder package, for Phase 6)
- [x] Create `smc/live/` directory (placeholder package, for Phase 7)

### Configuration (`smc/config/`)

- [x] Create `locked_constants.py` — All frozen thresholds from LOCKED_DECISIONS.md
  - [x] `EQH_EQL_TOLERANCE = 4.5`
  - [x] `DISPLACEMENT_MIN_ATR = 1.0`
  - [x] `DISPLACEMENT_HARD_FAIL = 0.5`
  - [x] `ZONE_REFINEMENT_ATR = 0.5`
  - [x] `PREMIUM_THRESHOLD = 0.55`
  - [x] `DISCOUNT_THRESHOLD = 0.45`
  - [x] `M5_EXPIRY_BARS = 12`
  - [x] `M1_EXPIRY_BARS = 30`
  - [x] `N_BAR_HTF = 5`
  - [x] `N_BAR_LTF = 3`
  - [x] `TRIGGER_A_EXPIRY = 20`
  - [x] `TRIGGER_B_EXPIRY = 30`
  - [x] `TRIGGER_C_EXPIRY_EXTRA = 3`
  - [x] `TRIGGER_D_EXPIRY = 1`
  - [x] `TRIGGER_E_EXPIRY = 15`
  - [x] `TRIGGER_F_EXPIRY = 1`
- [x] Create `timeframe.py` — Enum: D1, H4, H1, M30, M15, M5, M1
- [x] Create `model_type.py` — Enum: M1–M8 (Trigger A–F lives in `smc/core/enums.py` as `TriggerType`)

### Core Types (`smc/core/`)

- [x] Create `candle.py` — Candle dataclass (OHLCV, timestamp, TF)
- [x] Create `swing.py` — Swing dataclass (high/low, base_candle, is_valid)
- [x] Create `zone.py` — Zone dataclass (top, bottom, direction, tf)
- [x] Create `liquidity_level.py` — LiquidityLevel dataclass (type, level, pool, tf)
- [x] Create `poi.py` — POI dataclass (zone, models[], score, state, freshness)
- [x] Create `event.py` — Event dataclass (type, payload, timestamp, event_id)
- [x] Create `enums.py` — LiquidityType, POIState, Direction, PoolType, TriggerType

### Data Layer (`smc/data/`)

- [x] Create `mt5_connector.py` — REUSE MetaTrader5 Python API wrapper (direct, no HTTP)
  - [x] `copy_rates(symbol, tf, start, count)`
  - [x] `order_send(request)`
  - [x] `account_info()`
  - [x] `positions_get()`
  - [x] `order_check()`
- [x] Create `csv_loader.py` — Load historical OHLCV from CSV for backtesting
- [x] Review `cab_watcher_v16_3-1.py` and extract reusable MT5 connection + order patterns (documented in `mt5_connector.py` docstring)
- [ ] Create `redis_store.py` — OPTIONAL for V1 (in-memory state is acceptable initially). **Deferred** — see Blocked/Waiting. Design decision needed before Phase 3/6.

### Utilities (`smc/utils/`)

- [x] Create `atr.py` — ATR calculation (period configurable)
- [x] Create `timestamps.py` — UTC conversion, session detection (Asia/London/NY)
- [x] Create `pips.py` — Pip conversion for XAUUSD (4.5 pip tolerance)

### Validation

- [x] Unit test: All dataclasses instantiate correctly (`tests/test_core_types.py`)
- [x] Unit test: Enums have correct values (`tests/test_enums.py`)
- [x] Unit test: `locked_constants.py` contains all frozen thresholds (`tests/test_locked_constants.py`)
- [x] Unit test: `mt5_connector.py` wrapper methods exist (mock MT5) (`tests/test_mt5_connector.py`)
- [x] Unit test: `atr.py` computes ATR correctly on synthetic data (`tests/test_atr.py`)

---

## Phase 1: Core Detection ✅ COMPLETE (2026-09-06)

- [x] `smc/detection/liquidity_scanner.py` — Stage 0A orchestrator (session, periodic, EQH/EQL, structural families; POI/D&S/OB types deferred to Phases 2+)
- [x] `smc/detection/session_levels.py` — Asia/London/NY session highs and lows (§2 UTC windows from locked constants)
- [x] `smc/detection/periodic_levels.py` — PDH/PDL, PWH/PWL (most recent completed trading day/week)
- [x] `smc/detection/eqh_eql_detector.py` — Equal Highs / Equal Lows (frozen 4.5-pip tolerance)
- [x] `smc/detection/structural_swing_detector.py` — Structural swing H/L using N-bar + Base Candle gate
- [x] `smc/detection/sweep_detector.py` — Wick-pierce + body-close sweep confirmation
- [x] `smc/detection/displacement_checker.py` — BOS + FVG + displacement magnitude (§3 thresholds)
- [x] `smc/detection/fvg_detector.py` — Fair Value Gap (3-candle imbalance)
- [x] `smc/detection/base_candle.py` — Base Candle identification algorithm (§18 incl. bearish wick rule)
- [x] `smc/detection/swing_validator.py` — Swing validity decision gate (§19)
- [x] 56 Phase 1 unit tests — **92 tests total passing** (`python -m pytest tests` from `04_SRC/`)

## Phase 2: POI Classification ✅ COMPLETE (2026-09-06)

> Path note: per the Phase 2 coding prompt (`01_ARCHITECTURE/SMC_PHASE_2_CODING_PROMPT.md`), the registry lives at `smc/poi/model_registry.py` (not `models/`) and the eight model detectors under `smc/poi/models/`.

- [x] `smc/poi/base_model.py` — Abstract base class (`POIModel`) + shared geometry helpers (zone_for_swing/level/candle, first_close_beyond, atr_up_to, directional-FVG check)
- [x] `smc/poi/model_registry.py` — `ModelRegistry` + `build_registry(timeframe, htf_candles)` registering M1–M8
- [x] `smc/poi/confluence_scorer.py` — Independent-tag count, quality tiers (1/2/3+), M8 +0.10 HTF-overlap bonus, overlap merge
- [x] `smc/poi/deal_range.py` — Dealing range (§6) + Premium/Discount/Equilibrium classification (frozen 0.45/0.55 bands)
- [x] `smc/poi/choch_classifier.py` — CHOCH Rule 1/2/3 (§17/§20), bullish via price inversion
- [x] `smc/poi/models/m1_origin_base.py` — Origin Demand/Supply Base
- [x] `smc/poi/models/m2_rbs_sbr_breaker.py` — RBS/SBR Breaker Flip
- [x] `smc/poi/models/m3_choch_retest.py` — CHOCH Baseline Retest (Rules 1/2/3 share the single M3 tag)
- [x] `smc/poi/models/m4_quasimodo.py` — Quasimodo Level / QML
- [x] `smc/poi/models/m5_extreme_equal_highs.py` — Extreme Equal Highs / Supply Origin (proactive)
- [x] `smc/poi/models/m6_neckline_retest.py` — Neckline / Double Top-Bottom
- [x] `smc/poi/models/m7_equal_resistance.py` — Equal Resistance Shelf (reactive)
- [x] `smc/poi/models/m8_htf_demand_supply.py` — HTF Demand/Supply zones D1/H4 (OB, FVG, §22 zones; §21/§26 overlap flag)
- [x] 42 Phase 2 unit tests (framework + per-model acceptance/decoys + M8 §22 zone / D1-H4-only checks) — **134 tests total passing** (`python -m pytest tests` from `04_SRC/`)

## Phase 3: 5-Pillar Validation ✅ COMPLETE (2026-09-07)

- [x] `smc/validation/pillar.py` — Abstract `Pillar` base + `PillarStatus`/`PillarResult`/`ValidationContext` shared types
- [x] `smc/validation/pillar_1_zone_refinement.py` — §13 unmitigated OB/FVG within ±0.5× ATR of the POI level; naked level = hard FAIL
- [x] `smc/validation/pillar_2_displacement.py` — §3 gate consuming the Phase 1 `check_displacement` result (no blind recompute)
- [x] `smc/validation/pillar_3_premium_discount.py` — §6 gate; SOLE owner of the 45%/55% hard reject (`classify_region` consumer)
- [x] `smc/validation/pillar_4_freshness.py` — §5 strict 1-touch state gate (CREATED/FRESH only)
- [x] `smc/validation/pillar_5_inducement.py` — §7 soft 100%/70% scoring; never rejects
- [x] `smc/validation/validation_pipeline.py` — runs pillars 1→5, short-circuits on first hard (1–4) non-pass, arms POI (CREATED→FRESH) + assigns `score_poi` on PASS
- [x] `smc/validation/state_machine.py` — atomic §5 transitions (`POIStateMachine`), 1-touch TESTED / VIOLATED terminals, §23 unfilled-order expiry (M5=12 / M1=30)
- [x] 7 test files: per-pillar (1–5) + pipeline + state machine — **40 Phase 3 unit tests, 174 total passing** (`python -m pytest tests` from `04_SRC/`)

> Notes: `pillar_3_premium_discount` is the sole owner of the §6 reject — `deal_range.py` only classifies the region. UNAVAILABLE on pillars 1–4 rejects (never a silent pass). Displacement is injected as a Phase 1 `DisplacementResult`; the pipeline auto-computes the dealing range from swings via Phase 2 `compute_dealing_range`.

## Phase 4: LTF Triggers + Python Execution ✅ COMPLETE (2026-09-07)

- [x] `smc/triggers/base_trigger.py` — `Trigger` ABC + `TriggerContext`/`TriggerSignal` (entry limit + stop reference, `data: dict` never None)
- [x] `smc/triggers/trigger_a_choch.py`
- [x] `smc/triggers/trigger_b_leading_diagonal.py`
- [x] `smc/triggers/trigger_c_ending_diagonal.py`
- [x] `smc/triggers/trigger_d_two_bar.py`
- [x] `smc/triggers/trigger_e_rsi_divergence.py`
- [x] `smc/triggers/trigger_f_bos_ob.py`
- [x] `smc/triggers/wave_structure.py` — deterministic V1 5-wave impulse extraction (Triggers B/C)
- [x] `smc/triggers/trigger_router.py` — chronological first-valid routing (§12) + §15 grade tie-break
- [x] `smc/triggers/trigger_expiry.py` — §24 validity windows + §23 order expiry anchors
- [x] `smc/triggers/compatibility_matrix.py` — §15 PREFERRED/STRUCTURAL/UNCOMMON grades
- [x] `smc/execution/order_manager.py` — Order placement, cancel, modify via MT5 API
- [x] `smc/execution/position_manager.py` — Position monitoring, SL/TP adjustment
- [x] `smc/execution/news_guard.py` — §11 CPI/NFP/FOMC blackout
- [x] `smc/execution/session_filter.py` — §2 allowed-session gate
- [x] `smc/execution/lot_sizing.py` — `risk_lots` sizing helper (Phase 5 consumer)
- [x] `smc/orchestration/engine.py` — `PipelineEngine`: merge → validate → arm → per-bar feed → scan_route → execute_route
- [x] 76 Phase 4 unit tests (triggers A–F, router, matrix, expiry, execution, engine, RSI) — **250 tests total passing** (`python -m pytest tests` from `04_SRC/`)

## Phase 5: Risk Layer — Port v25_DIAG ✅ COMPLETE (2026-09-07)

> **Note:** Kalman filter, ADX gate, and ATR floor should only be ported if still required after the core detection stack is proven. ADX (≥ 25.0) and ATR-floor (1.0×) thresholds ARE now locked (§28.8) as conditional gates — the components themselves were NOT ported in V1.

- [x] Risk constants formally locked (LOCKED_DECISIONS §28) — all 17 §28 thresholds written into `locked_constants.py` with an assertion test — **251 tests total passing**
- [x] `smc/risk/lot_sizing.py` — Phase 5 sizing policy: re-exports the single `risk_lots` formula from `smc/execution/lot_sizing.py` (no parallel path) + `clamp_risk_fraction` (RISK_PCT_MIN/MAX band 0.5–1.0%) + `sized_lots` (cap LOT_MAX_SAFETY 0.10)
- [x] `smc/risk/circuit_breaker.py` — 3 consecutive losses → 4h pause (§28.2), win/new-day reset, synthetic injectable state
- [x] `smc/risk/same_level_guard.py` — re-entry block within 0.15× ATR of last closed SL for 4 bars (§28.3; locked at the running v25 default, not the outdated 0.1 comment)
- [x] `smc/risk/friday_eod.py` — once-per-Friday force-close decision at 20:00 UTC (§28.4), latch + reset, pure decision (no broker calls)
- [x] `smc/risk/sweep_guard.py` — per-direction failed-sweep re-entry block: 0.5× ATR zone + 4-bar cooldown (§28.6), v25 `IsFailedSweepBlocked` semantics
- [x] `smc/risk/spread_grading.py` — §28.5 score-tier grading (A+ ≥8 / A ≥5 / B ≥3 / C <3) + multipliers (A+ 1.5 / A 1.0 / B 0.7 / C 0.5) over SPREAD_MAX_ATR (0.15 × ATR)
- [x] `smc/risk/pure_runner.py` — BE at 1.0× ATR from entry + 0.10× ATR buffer (§28.1), one-shot latch, no partials in V1, pure SL decision
- [x] `smc/risk/fvg_invalidation.py` — `FvgContext` contract (valid/low/high/direction) + closed-candle structural-failure exit decision
- [x] `smc/risk/risk_engine.py` — orchestrator composing all components: pre-entry gates (news → session → circuit breaker → same-level → sweep → spread → sizing) + per-bar exits (Friday EOD → FVG invalidation → PureRunner BE) + state updates, all dependency-injected, pure decisions (no MT5)
- [x] 90 Phase 5 unit tests (10 test files: risk constants §28 + lot sizing, circuit breaker, same-level guard, friday eod, sweep guard, spread grading, pure runner, fvg invalidation, risk engine) — **340 tests total passing** (`python -m pytest tests` from `04_SRC/`)
- [x] ~~`smc/risk/kalman_filter.py`~~ — NOT ported (per note above)
- [x] ~~`smc/risk/adx_gate.py`~~ — NOT ported (constants locked as conditional gate only, §28.8)
- [x] ~~`smc/risk/atr_floor.py`~~ — NOT ported (constants locked as conditional gate only, §28.8)

## Phase 6: Backtesting & Paper Trading ✅ COMPLETE (2026-09-09)

> Delivered through six accepted milestones (M1–M6) per the Phase 6
> design (`01_ARCHITECTURE/SMC_PHASE_6_DESIGN.md`) and per-milestone
> design notes (`SMC_PHASE_6_M4/M5/M6_DESIGN_NOTE.md`). The original
> placeholder checklist (backtest_engine/event_bus/state_store/…)
> was superseded by the locked M1–M6 milestone plan.

### M1 — Thin bar loop + data feed
- [x] `smc/backtest/data_feed.py` — `CandleSeries` (multi-TF feed shape, exact-timestamp contract)
- [x] `smc/backtest/clock.py` — deterministic `BarClock` (strictly-advancing injected `now`)
- [x] `smc/backtest/bar_loop.py` — `BarLoop` + `BarHandler` seam (ONE loop, backtest/live shared skeleton)

### M2 — Pending orders + fill model + position store
- [x] `smc/backtest/orders.py` — `PendingOrderBook` (deterministic tickets, §23/§24 expiry)
- [x] `smc/backtest/fill_model.py` — limit fills at LIMIT PRICE, physical SL/TP, same-bar SL-first rule
- [x] `smc/backtest/positions.py` — `PositionStore` (open/close/modify, POI/trigger identity on trades)

### M3 — RiskEngine integration (backtest runner)
- [x] `smc/backtest/runner.py` — `BacktestRunner`: locked per-bar order (reset_day → Friday EOD → hard-cancel → risk exits → fills → entries last), blocked entries place nothing, injected `now` only

### M4 — PipelineEngine integration (real detection in the loop)
- [x] `smc/backtest/pipeline_bridge.py` — `TriggerRoute` → `CandidateEntry` mapping (poi_id / trigger / route_id identity, honest FVG provider)
- [x] `smc/backtest/pipeline_adapter.py` — per-bar engine drive: scan-before-feed, §11 one-shot workflows, §24 expiry, VIOLATED → cancel resting limit
- [x] `smc/orchestration/engine.py` — `scan_route(to_bar=)` no-lookahead cap + `tracked_pois()` arm-order registry

### M5 — Core reports
- [x] `smc/backtest/reports.py` — `TradeRecord`/`CoreMetrics`/`GroupMetrics`/`BacktestReport` (win rate, PF with explicit zero-loss `None`, net P/L, closed-trade max DD, per-trigger + per-POI breakdowns, blocked counts, empty-run defined zeros)
- [x] `smc/backtest/export.py` — deterministic CSV (18-column trade list) + JSON (sorted keys)
- [x] `runner.result()` — `RunnerResult` snapshot (closed trades + blocked log + route_ids)

### M6 — Paper runner + KPI logging
- [x] `smc/paper/runner.py` — `PaperRunner`: same bar order over the LIVE execution layer; implements the M4 adapter seam (submit_entry / on_candidate_accepted / cancel_pending_for_poi); broker-truth fill/close observation; dry-run + refuse-to-start safety posture
- [x] `smc/paper/broker_adapter.py` — thin `OrderManager`/`PositionManager` boundary (raises nothing; TP preserved on SL modify; `on_be_applied` only on confirmed success)
- [x] `smc/paper/kpi_logger.py` — append-only structured KPI records (decision/order_ack/management/fill/trade_closed/missed_bar/hard_cancel/friday_close), injected timestamps, deterministic JSON/JSONL/CSV exports

### Suite
- [x] **496 tests total passing** (`python -m pytest tests` from `04_SRC/`)

### Deferred to V1.1 (recorded, NOT built)
- [ ] Walk-forward analysis
- [ ] Monte Carlo
- [ ] Future Flexibility Clause KPI pass/fail thresholds (metrics logged; thresholds not frozen)

## Phase 7: Live Readiness + MQL5 Safety Watchdog ✅ COMPLETE (2026-09-09)

> Option A locked: Python owns ALL trading logic; MQL5 is ONLY a Safety
> Watchdog (heartbeat monitoring + emergency flatten — no strategy logic).
> Design note: `01_ARCHITECTURE/SMC_PHASE_7_DESIGN_NOTE.md`.

### 7.1 — Live config + heartbeat
- [x] `smc/live/config.py` — `LiveConfig` (demo-first defaults, single-sizing-path risk inputs, heartbeat/watchdog timing) + `live_config_from_dict`
- [x] `smc/live/heartbeat.py` — plain-text heartbeat file (`<unix_secs> <seq>` + `state=`), atomic writes, `HeartbeatPublisher` (interval-bounded, injected clock), `read_heartbeat`/`is_stale` (fail-closed on missing/garbage), `evaluate_watchdog` (the tested spec the EA mirrors)

### 7.2 — Live main loop
- [x] `smc/live/loop.py` — `LiveLoop`: connector poll → rolling-window `DetectionDriver.validate_window` → arm ONLY newly-passed POIs → `PaperRunner.run_one_cycle` (REAL adapter/engine/risk stack) → heartbeat; cold start anchors history (no replay); `start()` refuses when the connector fails; `run_once()` is the deterministic test seam
- [x] `smc/orchestration/detection_driver.py` — `validate_window` (validate WITHOUT arming) so rolling callers never re-arm (arm-bar/one-shot preserved)

### 7.3 — MQL5 Safety Watchdog EA
- [x] `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` — 1 s timer, 5 s stale timeout (`TimeGMT` vs file epoch), emergency close-ALL + delete-ALL (magic/symbol scoped), healthy → no trading actions; NO strategy logic

### 7.4 — Tests + watchdog contract
- [x] `tests/test_live_phase7.py` — 9 tests: heartbeat roundtrip/freshness, fail-closed garbage/missing, sequence + clean-shutdown marker, publisher interval, watchdog decision (healthy → no_action / stale → emergency / missing → emergency), live loop over fake connector (history anchor → new-bar cycle → heartbeat fresh → shutdown marker), start refusal, no re-arming of existing POIs, config coercion
- [x] EA manual validation checklist — `01_ARCHITECTURE/SMC_PHASE_7_DESIGN_NOTE.md` §6

### Suite
- [x] **519 tests total passing** (`python -m pytest tests` from `04_SRC/`)

### Deferred to V1.1 / next cycle (recorded, NOT built)
- [ ] Walk-forward analysis
- [ ] Monte Carlo
- [ ] Future Flexibility Clause KPI pass/fail thresholds (metrics logged; thresholds not frozen)
- [ ] Production alerting (Telegram/email) + M8 HTF provisioning in the live driver + remote/VPS heartbeat transport

---

## Post-V1 — Phases A–E (governed by `POST_V1_PLAN_OF_ACTION.md`)

> **Order is binding:** A → B → C → D → E, one phase per engagement. The plan is the source of truth; every decision gets recorded there with date + rationale.

### Phase A — Data Acceptance ✅ COMPLETE (2026-09-09)
- [x] `06_RESEARCH/scripts/phase_a_data_acceptance.py` — read-only A1–A6 acceptance script (no trading logic touched)
- [x] `06_RESEARCH/DATA_ACCEPTANCE_REPORT.md` — full report; verdict PASS
- [x] A1 schema/Candle round-trip · A2 UTC localization · A3 gap census (1,679 gaps fully classified: weekends + NY-5pm rollover-hour omissions; no unexplained class) · A4 OHLC/units/spike integrity · A6 SHA-256 checksums — all PASS
- [x] **A5 volume ruling — option (a):** dataset accepted as volume-less; Phase B/C baselines run WITHOUT Trigger D as a tradeable path (recorded in plan §3)
- [x] `smc/data/parquet_loader.py` — accepted loader (`load_ohlcv_parquet`, 6 unit tests) — the ONLY sanctioned Phase B/C input path
- [x] Canonical series: `07_DATA/XAUUSD_M1.parquet` (1,768,123 M1 bars, 2021-04-12 11:00 → 2026-04-10 20:59 UTC; SHA-256 in plan §3 A6); `07_DATA/` git-ignored

### Phase B — Short Fidelity Backtest ✅ COMPLETE (CLOSED 2026-09-14 — PASS)
- [x] Window selection — full October 2025 (2025-10-01 → 2025-10-31, 31,619 bars; last bar 20:59 = Friday rollover-hour omission, Phase A-classified) + frozen config recorded verbatim (`06_RESEARCH/PHASE_B_FIDELITY_REPORT.md` §2)
- [x] Pipeline validated at three scales: Oct 1 smoke pair (byte-identical) → Oct 1–3 short pair (`phase_b_oct_short_run1/2`, byte-identical, all invariants OK, 6 trades) → full October
- [x] **Perf fix (2026-09-13):** first full-October attempt aborted at bar ~12.5k — quadratic per-bar cost (O(prefix) swing/RSI/ATR/inversion rebuilds re-run per armed POI per bar, py-spy-diagnosed); three equivalence-preserving patches (`pipeline_adapter.generate_candidates` hoist + scan retirement, `engine.scan_route` resume cursor, `trigger_router.scan` arm-bar anchor preserved) — suite 529→**532**, golden check reproduces the Oct 1–3 pair BYTE-IDENTICALLY (`phase_b_golden_check/`)
- [x] Full-October determinism pair — COMPLETE 2026-09-13 21:40/21:41 (31,619 bars each, ~11.8 h/run, 0.75 bars/s); exports BYTE-IDENTICAL; summary identical ex-runtime
- [x] Kill-funnel counters — every stage non-zero or explained in writing: raw 189,284 → armed 237 → routes 49 → placed 42 → opened 41 (1 × §24 give-up) → closed 41; `positions_still_open = 0` = flat end-of-window book (explained); hard-cancelled_news 0, friday_closes 0
- [x] Frozen-rule invariants verified: §23/§24 expiry, §11 one-shot, §5 one-touch terminal TESTED, BE latch once-per-trade, limit-price fills — all OK × 2 runs; same-bar SL-first verified over **ALL 41 trades** (`phase_b_sl_first_check.py`: every exit price == SL exactly, zero ambiguous bars) — stronger than the requested sample
- [x] Determinism rerun — byte-identical `trades.csv` + `report.json`; `summary.json` identical ex-runtime; machine verdict `phase_b_verdict.json` = **PASS** (two checker defects fixed + disclosed: recursive runtime-strip; `positions_still_open` explanation)
- [x] `PHASE_B_FIDELITY_REPORT.md` fully filled (funnel §3, metrics §4, per-trigger §5: A=2/B=7/F=32/D=0, determinism §6, §7.4 anomalies, §9 overall **PASS**); one-page fidelity note appended to the plan; marker → Phase C

### Phase C — Full 5-Year Baseline (EXECUTED 2026-09-19; CLOSED — Lead Architect sign-off granted 2026-09-19)
- [x] Runtime reality check: as-is ≈ 27 days/run (0.75 bars/s Phase B plateau + O(prefix) trigger costs) → **Option B** (semantics-preserving perf only, per plan)
- [x] Perf patches P1–P3 (detection hoists + incremental `SeriesState` + trigger hints), suite 532 → **551** (19 new equivalence tests)
- [x] Golden equivalence vs Phase B October pair: `trades.csv`/`report.json` **byte-identical**, summary identical ex-runtime (`06_RESEARCH/results/phase_c_golden_replay/`); post-patch plateau **110 ms/bar** → ETA ≈ 54 h/run
- [x] Dual segmented baseline — **COMPLETE 2026-09-19**: 6 calendar-year segments × 2 runs, **1,768,123 bars each** (77.4 h/run after one interruption + supervisor relaunch; manifest resume preserved completed segments byte-identically); `trades.csv`/`report.json` byte-identical, summary identical ex-runtime, invariants all OK, Trigger D = 0; verdict **PASS** re-stamped 2026-09-19 09:55:10 against the final on-disk artifacts (`06_RESEARCH/results/phase_c_verdict.json`)
- [x] Spread sensitivity — **COMPLETE 2026-09-19**: 4-arm constant-spread ladder {0.00, 0.05, 0.15, 0.35} on 2023-02-01 → 2023-04-30 (84,470 bars; window-adequacy + cold-start measurement note in report §8); result: gate removes flow monotonically — 52 → 22 → 2 → **0 trades at 0.35** (all 54 routes spread-blocked at the representative retail spread); invariants OK in every arm; identical pre-spread funnel (510,095 → 407 → 54) isolates the spread attribution (`06_RESEARCH/results/phase_c_spread_sens_sens0p{00,05,15,35}/`)
- [x] `06_RESEARCH/PHASE_C_BASELINE_REPORT.md` — **COMPLETE 2026-09-19** (frozen config + 4 sha256 checksums, coverage, funnel, core + per-year + per-trigger breakdowns, boundary ruling accept+document with 0 warm-up-zone trades verified, spread ladder, anomalies incl. 0.10-lot cap binding 100 % of trades, binding interpretation, exit-criteria table, reproduce commands)
- [x] Governance close-out (plan/handoff/TODO/CHANGELOG) — this update; suite re-verified **565 passed**; `SMC_phase_c_guard` scheduled task + Startup `phase_c_guard_hidden.vbs` removed
- [x] **Lead Architect sign-off on the Phase C package** — GRANTED 2026-09-19: **Phase C CLOSED**; Phase D cleared for ops validation only (no optimization / no redesign / no locked-constant changes)

### ACTIVE: Phase D — Demo/Paper Operational Validation (OPENED 2026-09-19 — session 1 done, market closed)
- [x] Terminal binding + identity gate: EXNESS Copy path verified (dir identity MATCH), **DEMO** 474608655 @ Exness-MT5Trial15, symbol **XAUUSDm** resolved (`06_RESEARCH/scripts/phase_d_identity_check.py` → PHASE_D_IDENTITY: PASS)
- [x] Watchdog EA deployed + compiled (**0 err / 0 warn**) into the terminal's `MQL5\Experts\`; heartbeat contract verified (5 s stale edge, file-format parity with EA parser, terminal `MQL5\Files` sandbox round-trip)
- [x] Idle-session stability: 2 min LiveLoop dry-run — 60 polls, 0 errors, 0 new bars (weekend), heartbeat seq 60 + shutdown marker (`results/phase_d_ops/`)
- [x] Order-path payload validation via `order_check`: BUY_LIMIT 0.10 @ magic **20260919** — retcode 0 (FOK + IOC); NO sends (market closed, Algo Trading OFF in terminal GUI)
- [x] Divergence log started: `06_RESEARCH/PHASE_D_DIVERGENCES.md` — headline: §28.5 gate is ATR-relative ⇒ 2023's all-grades-blocked regime (ATR 0.30–1.06, ceiling 0.02–0.08) vs today's all-grades-pass regime (ATR ≈ 3.75); live spread constant 0.26
- [x] **Operator pack delivered** (Lead Architect instruction 2026-09-19): `run_live.bat` launcher + `config/live_demo.json` (strict whitelist, LOCKED keys rejected loudly, risk_fraction band-checked) + `04_SRC/smc/live/run_operator.py` entrypoint (identity gate → loop → console board → backend logs in gitignored `logs/`) + pure renderer `operator_console.py`; 15 focused tests; suite **580**; live smoke on the EXNESS Copy terminal PASSED (identity, boards, heartbeat, clean shutdown; `trade_allowed=true` observed — Algo Trading is ON)
- [ ] **EA attach via terminal GUI** (InpHeartbeatFile=smc_heartbeat.txt, InpSymbolFilter=XAUUSDm, InpMagicFilter=20260919) + Algo Trading ON — user/GUI step
- [ ] Live bar-cycle session on open market: detect→arm→risk cycles, no crashes, KPI decision/ack latencies
- [ ] Order sends on demo: place limit / cancel / SL-modify-preserves-TP / close (identity-gated, magic 20260919)
- [ ] Stale-heartbeat emergency drill (Python stopped → watchdog closes scoped positions / cancels scoped pendings)
- [ ] Full-trading-day spread distribution + gate/lot-cap observations → divergence log; KPI archive started
- [ ] Phase D exit: ≥ 2 consecutive weeks unattended demo, zero unhandled exceptions, watchdog validated, divergence log maintained
- [ ] Phase E — V1.1 (walk-forward, Monte Carlo, Future Flexibility thresholds) — BLOCKED until Phase D exit criteria met
- [ ] Track V — Visual conviction / chart overlays (locked 2026-09-20; research visualizer V1 near-term, MT5 draw-only overlay V3 later) — pointer only, checklist lives in `POST_V1_ACTIVE_TODO.md` Track V

---

## Blocked / Waiting

| Item | Blocked By | Notes |
|------|-----------|-------|
| Phase 1–7 tasks | Phase 0 completion | Foundation must be solid first |
| `redis_store.py` decision | Redis vs SQLite for backtesting? | **Resolved by design (2026-09-09):** V1 uses in-memory stores (`PendingOrderBook` / `PositionStore` / `POIStateMachine`), documented as the seam for a later Redis CAS — no Redis in V1 |
| Event bus abstraction | Design not yet started | **Resolved by design (2026-09-09):** no bus in V1 — the runners compose components via direct calls in the locked per-bar order; an abstraction would add indirection without a consumer |

---

## Completed

| Date | Task | Phase |
|------|------|-------|
| 2026-09-06 | Project restructuring — new folder structure created | Setup |
| 2026-09-06 | Option A Locked — Python-First + MQL5 Safety Watchdog | Architecture |
| 2026-09-06 | All 3 governance documents created | Governance |
| 2026-09-06 | File audit — 180 files categorized and moved | Setup |
| 2026-09-06 | `smc/` package tree created (config, core, data, utils + 10 placeholder phase packages) | Phase 0 |
| 2026-09-06 | `locked_constants.py` — all frozen thresholds extracted from LOCKED_DECISIONS.md | Phase 0 |
| 2026-09-06 | Core types: Candle, Swing, Zone, LiquidityLevel, POI, Event + enums | Phase 0 |
| 2026-09-06 | Data layer: `mt5_connector.py` (thin MT5 wrapper) + `csv_loader.py` | Phase 0 |
| 2026-09-06 | Utils: `atr.py`, `timestamps.py` (sessions), `pips.py` (XAUUSD) | Phase 0 |
| 2026-09-06 | 5 Phase 0 unit test files — **36 tests passing** | Phase 0 |
| 2026-09-06 | Phase 1 core detection — 10 modules (scanner, sessions, periodic, EQH/EQL, swings, sweeps, FVG, displacement) | Phase 1 |
| 2026-09-06 | 10 Phase 1 test files (56 tests) — **92 tests passing** | Phase 1 |
| 2026-09-06 | Phase 2 POI classification — 12 modules (`smc/poi/` framework + `models/m1–m8`) | Phase 2 |
| 2026-09-06 | 5 Phase 2 test files (registry, CHOCH, deal range, confluence, M1–M8 fixtures) — Phase 2 POI classification delivered | Phase 2 |
| 2026-09-07 | Phase 2 audit PASS + M8 §22/§21 test hardening — **42 Phase 2 tests, 134 total passing**; SESSION_HANDOFF refreshed to Phase 3 | Phase 2 |
| 2026-09-07 | Phase 3 5-Pillar Validation — 8 modules in `smc/validation/` (pillars 1–5, pipeline, state machine, shared types) | Phase 3 |
| 2026-09-07 | 7 Phase 3 test files (40 tests: pillars 1–5, pipeline, state machine) — **174 tests total passing** | Phase 3 |
| 2026-09-07 | Phase 3 audit PASS (11/11, 2 Notes) — integration seams for Phase 4 documented in SESSION_HANDOFF; docs-only, **174 tests total passing** | Phase 3 |
| 2026-09-07 | Phase 4 LTF Triggers + Python Execution — 6 triggers (A–F), wave structure, TriggerRouter, compatibility matrix, expiry, execution layer (OrderManager, PositionManager, NewsGuard, SessionFilter, lot sizing), PipelineEngine | Phase 4 |
| 2026-09-07 | 76 Phase 4 unit tests (16 files: triggers A–F, router, expiry, matrix, order/position manager, news/session, lot sizing, RSI, engine) — **250 tests total passing** | Phase 4 |
| 2026-09-07 | Phase 4 final contract fixes — `ExecutionOutcome.order_result` typed field + Trigger B `TriggerSignal.data` dict contract — suite 245 → **250/250 green** | Phase 4 |
| 2026-09-07 | Phase 5 constant lock — 17 §28 risk thresholds approved by Lead Architect and written into `locked_constants.py` + `LOCKED_DECISIONS.md` §28 — **251 tests total passing** | Phase 5 |
| 2026-09-07 | Phase 5 Milestone 1 — `smc/risk/` lot sizing policy (single sizing path), circuit breaker (3 losses → 4h), same-level guard (0.15× ATR + 4 bars) — **278 tests total passing** | Phase 5 |
| 2026-09-07 | Phase 5 Milestone 2 — friday EOD (once-per-Friday latch at 20:00 UTC), sweep guard (0.5× ATR + 4 bars, per-direction), spread grading (score-tier multipliers) — **304 tests total passing** | Phase 5 |
| 2026-09-07 | Phase 5 Milestone 3 — pure runner (BE at 1.0× ATR + 0.10 buffer, one-shot latch), FVG invalidation (`FvgContext` contract, closed-candle exit) — **320 tests total passing** | Phase 5 |
| 2026-09-07 | Phase 5 Final Milestone — `risk_engine.py` orchestrator (typed Entry/Exit decisions, v25 gate order, DI of all components, pure decisions) — **340 tests total passing** | Phase 5 |
| 2026-09-08 | Phase 0–5 audit fixes — PositionManager SL/TP preserve (C1), `compute_risk_lots` through §28.7 policy (C2), blocked routes keep the POI one-shot (I2), same-bar tie-break A-first (I3), §7 constants imported (I4), injected `now` in `execute_route` (I5), governance docs aligned to post-audit RiskEngine API — **363 tests total passing** | Audit |
| 2026-09-08 | Phase 6 M1 — thin bar loop + data feed (`BarLoop`/`BarHandler`, `BarClock`, `CandleSeries`) + M2 — pending orders, fill model (limit-price fills, SL-first), position store | Phase 6 |
| 2026-09-08 | Phase 6 M3 — `BacktestRunner` RiskEngine integration (locked per-bar order, blocked entries place nothing, injected clock) — **458 tests total passing** (M1–M3 accepted and frozen) | Phase 6 |
| 2026-09-09 | Phase 6 M4 — PipelineEngine integration: pipeline bridge + adapter (scan-before-feed, §11 one-shot workflows, no-lookahead `to_bar` cap), POI/trigger/route identity through fill, honest FVG capture — **467 tests total passing** | Phase 6 |
| 2026-09-09 | Phase 6 M5 — core reports (`reports.py`, `export.py`, `runner.result()`): trade list, PF/win-rate/net P/L, closed-trade max DD, per-trigger + per-POI breakdowns, CSV/JSON export — **481 tests total passing** | Phase 6 |
| 2026-09-09 | Phase 6 M6 — paper runner + broker adapter + KPI logger (same bar order over the live execution layer, broker-truth observation, `on_be_applied` only on confirmed modify, dry-run posture, deterministic KPI records) — **496 tests total passing** | Phase 6 |
| 2026-09-09 | Phase 6 documentation freeze — TODO/CHANGELOG/SESSION_HANDOFF updated to Phase 7 next; Phase 6 design notes referenced; repo committed and pushed | Governance |
| 2026-09-09 | Phase 6 audit fixes — C1 §23/§24 expiry wired into the loop, C2 paper fill linkage (symbol/magic/comment), I1 per-bar ATR/spread, I2 real-adapter auto-attach, I3/I5 rulings recorded — **501 tests total passing** | Phase 6 |
| 2026-09-09 | Pre-Phase-7 coherence patch — CR1 detection driver (candles → validated/armed POIs), I1 single §5 state machine, I2 running equity in backtest sizing, CR2 paper close outcomes feed risk guards, I4 terminal-state retention — **510 tests total passing** | Phase 7 prep |
| 2026-09-09 | Phase 7 — live readiness: `smc/live/` (LiveConfig, heartbeat publisher + watchdog decision spec, `LiveLoop` over the real stack) + `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` (heartbeat + emergency flatten only) — **519 tests total passing** | Phase 7 |
| 2026-09-09 | Post-V1 Phase A — Data Acceptance: acceptance script + report (A1–A6 PASS), A5 ruled option (a) (baseline WITHOUT Trigger D), canonical parquet + SHA-256 recorded, `smc/data/parquet_loader.py` merged (6 tests — **525 tests total passing**), `.gitignore` data protections + `data/` root-anchor fix | Post-V1 Phase A |
| 2026-09-14 | Post-V1 Phase B — Short Fidelity Backtest CLOSED: **PASS** — full-October determinism pair (2025-10-01→31, 31,619 bars × 2, byte-identical exports, summary identical ex-runtime), all 7 plan §4 invariants OK × 2, Trigger D = 0, funnel every stage non-zero-or-explained, same-bar SL-first verified over all 41 trades, `phase_b_verdict.json` = PASS; report fully filled + one-page fidelity note in the plan; metrics (diagnostic): 41 trades, WR 36.59%, net −7.66, PF 0.0501, maxDD 7.66. Fixes en route: §28.1 BE-latch per-trade keying (525→529) + quadratic scan-cost patch with golden-check proof (529→**532**) | Post-V1 Phase B |
| 2026-09-15 | Independent Phase C perf-patch audit CLOSED: **PASS WITH FINDINGS** (`06_RESEARCH/PHASE_C_PERF_AUDIT.md`) — 17 static equivalence claims OK (F1 LOW-latent, F2 INFO), suite 565 independently green, fold-convergence + warm-up-margin probes PASS. Boundary-probe finding: fresh-stack-per-segment loses episode/one-shot state at segment boundaries (CARRY_LOSS = 1, real October) and end-of-boundary open positions are dropped from the merged trade list — 2024→25 + 2025→26 year boundaries exposed (the other three are Friday-pre-flattened); probe's own false PREFIX_IDENTITY (midnight-truncated window) fixed + disclosed — corrected re-run: PREFIX_IDENTITY True (20 vs 20), CARRY_LOSS = 1 reproduced identically. Disposition (accept-and-document vs boundary-overlap trim) DEFERRED TO LEAD ARCHITECT; production pair unaffected in-flight | Post-V1 Phase C |
| 2026-09-15 | Project-wide audit recorded (`06_RESEARCH/PROJECT_WIDE_AUDIT.md`): criticals C1 (boundary carry — pending ruling), C2 (segment-end open positions silently dropped from merge — no end-of-data warning), C3 (paper runner = largest, least-tested heavy module); strengths, clarity items and ranked enhancements E1–E6 catalogued; **re-check §7 scheduled at 5-year baseline completion** | Post-V1 Phase C |
| 2026-09-15 | **LEAD ARCHITECT RULING (pending execution): boundary-carry disposition = OPTION B (boundary-overlap trim)** — to be applied to the Phase C merge AFTER the 5-year pair completes (drop per-segment trades whose `entry_bar < own_start`; bookkeeping-only, does not restore boundary state-carry). Also pending at completion: verify `positions_still_open` on the 2024→25 (Tue Dec 31) and 2025→26 (Wed Dec 31) midweek boundaries, watcher verdict, then work PROJECT_WIDE_AUDIT.md §7 with the user | Post-V1 Phase C |
| 2026-09-17 | Phase C pair interruption (died ~2026-09-16 16:45 local at 2024 bar 196k/358.8k — machine-level; segments 2021–2023 intact and byte-identical) + relaunch: manifest-fingerprint resume skipped completed segments, 2024 restarted, watcher re-armed — ETA ≈ 28 h; checkpoint/resume design verified in production | Post-V1 Phase C |
| 2026-09-17 | Forensics: pair death NOT a reboot/crash/OOM — unlogged session-level suspend/termination (watcher freeze/resume fingerprint: 16.75 h log gap, abort at 09:30 on machine resume). **Auto-relaunch supervisor deployed + live-fire tested** (scheduled task SMC_phase_c_guard /5 min + Startup copy + pythonw daemon; dead components self-heal ≤5 min; cleanup commands in CHANGELOG) | Post-V1 Phase C |
