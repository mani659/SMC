# TODO — SMC BOT Task Board

**Last Updated:** 2026-09-09
**Current Phase:** Phase 7 — Live Readiness + MQL5 Safety Watchdog (next)
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
| 7 | Live Readiness + MQL5 Safety Watchdog | Pending |

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

## Phase 7: Live + Safety Watchdog (Pending)

- [ ] `smc/live/config_loader.py`
- [ ] `smc/live/heartbeat.py`
- [ ] `smc/live/main_loop.py`
- [ ] `smc/live/integration_test.py`
- [ ] `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5`

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
