# SMC BOT — DEVELOPMENT PLAN (REVISED — OPTION A LOCKED)

**Date:** 2026-09-06
**Source of Truth:** `LOCKED_DECISIONS.md` Revision 5 (frozen 2026-09-01)
**Architecture:** Python-First with MQL5 Safety Watchdog
**Status:** OPTION A LOCKED — Python owns ALL trading logic; MQL5 reduced to emergency safety layer only

---

## Architecture: Option A (Locked)

### Permanent Architectural Decision

1. **Python owns ALL trading logic:**
   - Stage 0A: Liquidity Sweep + Displacement + Swing Gate
   - Stage 1–1b: POI Classification (M1–M8) + CHOCH Rules
   - Stage 2: 5-Pillar Validation
   - Stage 3: Trigger Routing
   - Stage 4: Execution (order placement, cancel, modify, news protocol)
   - Stage 5: Trade Management (PureRunner, FVG Invalidation, Circuit Breaker, Same-Level Guard, Friday EOD)

2. **MQL5 role is reduced to Safety Watchdog only:**
   - Heartbeat monitoring of Python process
   - Emergency protection of open positions if Python heartbeat dies
   - No entry logic
   - No normal trade management

3. **Future Flexibility Clause:**
   During paper trading we will log detailed operational KPIs (latency, order success rate, management delay, missed events, etc.). If any specific component later proves problematic in Python, we may selectively port only that component to MQL5 — but only after measured evidence.

### Why This Architecture

- **Unified logic:** One language (Python) for detection, validation, triggers, execution, and risk management. No split-brain.
- **Backtesting fidelity:** Same Python code runs in backtest and live. No `risk_simulator.py` that must replicate MQL5 logic.
- **Research velocity:** Python data science ecosystem (pandas, numpy, scipy) directly available for analysis.
- **MQL5 as safety net:** The MQL5 EA watches the Python process. If Python crashes or hangs, MQL5 emergency-protects open positions. This is the ONLY MQL5 responsibility.
- **Future flexibility:** If Python latency proves problematic for any component, we port only that component back to MQL5 — after measured evidence from paper trading KPIs.

---

## Re-use Inventory

### KEEP from v25_DIAG (Reference Implementation — Logic to Port to Python)

| Component | v25_DIAG Status | Python Status | Notes |
|-----------|----------------|---------------|-------|
| PureRunner + BE at 1× ATR | ✅ PROVEN (MQL5) | 🔨 PORT TO PYTHON | Logic reference in v25_DIAG. Port to `smc/risk/pure_runner.py` |
| FVG Invalidation | ✅ PROVEN (MQL5) | 🔨 PORT TO PYTHON | Logic reference in v25_DIAG. Port to `smc/risk/fvg_invalidation.py` |
| Circuit Breaker (3 losses → 4h) | ✅ PROVEN (MQL5) | 🔨 PORT TO PYTHON | Logic reference in v25_DIAG. Port to `smc/risk/circuit_breaker.py` |
| Same-Level SL Guard | ✅ PROVEN (MQL5) | 🔨 PORT TO PYTHON | Logic reference in v25_DIAG. Port to `smc/risk/same_level_guard.py` |
| Friday EOD | ✅ PROVEN (MQL5) | 🔨 PORT TO PYTHON | Logic reference in v25_DIAG. Port to `smc/risk/friday_eod.py` |
| 41-Column Forensic Logger | ✅ PROVEN (MQL5) | 🔨 PORT TO PYTHON | Logic reference in v25_DIAG. Port to `smc/logging/forensic_logger.py` |
| Dynamic Risk Lot Sizing | ✅ PROVEN (MQL5) | 🔨 PORT TO PYTHON | Logic reference in v25_DIAG. Port to `smc/risk/lot_sizing.py` |
| News Hard-Cancel | ✅ PROVEN (MQL5) | 🔨 PORT TO PYTHON | Logic reference in v25_DIAG. Port to `smc/risk/news_guard.py` |
| Spread Grading (A+/A/B/C) | ✅ PROVEN (MQL5) | 🔨 PORT TO PYTHON | Logic reference in v25_DIAG. Port to `smc/risk/spread_grading.py` |
| ML Feature Logger | ✅ PROVEN (MQL5) | 🔨 PORT TO PYTHON | Logic reference in v25_DIAG. Port to `smc/logging/feature_logger.py` |
| Sweep Re-Entry Guard | ✅ PROVEN (MQL5) | 🔨 PORT TO PYTHON | Logic reference in v25_DIAG. Port to `smc/risk/sweep_guard.py` |
| Session Filtering | ✅ PROVEN (MQL5) | 🔨 PORT TO PYTHON | Logic reference in v25_DIAG. Port to `smc/risk/session_filter.py` |
| Kalman Velocity Filter | ✅ PROVEN (MQL5) | 🔨 PORT TO PYTHON | Logic reference in v25_DIAG. Port to `smc/risk/kalman_filter.py` |
| ADX Trend Gate | ✅ PROVEN (MQL5) | 🔨 PORT TO PYTHON | Logic reference in v25_DIAG. Port to `smc/risk/adx_gate.py` |
| SLD/ATR Floor | ✅ PROVEN (MQL5) | 🔨 PORT TO PYTHON | Logic reference in v25_DIAG. Port to `smc/risk/atr_floor.py` |

### KEEP from CAB Pattern → Becomes MQL5 Safety Watchdog

| Component | CAB Status | New Role | Notes |
|-----------|-----------|----------|-------|
| Heartbeat/keepalive | ✅ EXISTS | **MQL5 Safety Watchdog** | Python sends heartbeat. MQL5 monitors. If heartbeat dies, MQL5 emergency-protects positions. |
| Position monitoring | ✅ EXISTS | **MQL5 Safety Watchdog** | MQL5 watches open positions for emergency protection only. Normal management is Python. |
| Emergency close | ✅ EXISTS | **MQL5 Safety Watchdog** | If Python heartbeat fails, MQL5 closes all positions at market. |

### KEEP from CAB Pattern → Python Direct MT5 API

| Component | CAB Status | New Role | Notes |
|-----------|-----------|----------|-------|
| `MetaTrader5` Python API | ✅ EXISTS | **Python Execution** | `copy_rates()`, `order_send()`, `account_info()` — Python calls directly |
| Order dispatch | ✅ EXISTS | **Python Execution** | Python places orders directly via MT5 API. No HTTP bridge needed. |
| Position monitoring | ✅ EXISTS | **Python Execution** | Python monitors fills, SL/TP, P&L directly. |

### COMPLETELY NEW (Must Be Built from Scratch)

| Component | Phase | Difficulty | Notes |
|-----------|-------|-----------|-------|
| Liquidity Scanner (8 level types) | 1 | Medium | Session H/L, PDH/PDL, PWH/PWL, EQH/EQL, Structural Swing, POI Sweep, D&S/OB Fallback |
| Base Candle Identification | 1 | Easy | Bullish = HIGH is swing high; Bearish = LOW is swing low |
| Swing Validity Gate | 1 | Medium | Break opposite extreme + body close. Two-bar reversal trap. |
| Displacement Checker | 1 | Easy | BOS + FVG + >1× ATR magnitude |
| FVG Detector | 1 | Easy | 3-candle imbalance gap |
| M1–M8 POI Models (8 modules) | 2 | Hard | Each model is an independent pluggable module |
| CHOCH Classifier (3 rules) | 2 | Hard | Standard, Inside Body, Inside Wick — subtle detection rules |
| Quasimodo (QML) | 2 | Hard | Left shoulder anchoring, full wick range |
| M8 HTF Demand/Supply | 2 | Hard | Multi-timeframe: D1/H4 scan → M5 approach → M1 trigger |
| Confluence Scorer | 2 | Easy | Count independent model tags, compute quality score |
| 5-Pillar Validation Pipeline | 3 | Medium | Zone refinement, displacement, P/D, freshness, inducement |
| Freshness State Machine | 3 | Medium | STATE_CREATED→FRESH→TESTED/VIOLATED, Redis Lua CAS for live |
| Trigger A–F (6 modules) | 4 | Hard | Especially B/C (wave counting) |
| Trigger Router | 4 | Medium | Chronological first-valid wins |
| Trigger Expiry Enforcer | 4 | Easy | Per-trigger window enforcement |
| Python Execution Engine | 5 | Medium | Order placement, cancel, modify via MT5 API |
| Python Risk Layer | 5 | Medium | Port v25_DIAG logic to Python |
| MQL5 Safety Watchdog EA | 7 | Easy | Heartbeat monitor + emergency position close |
| Backtest Engine | 6 | Hard | Event-driven bar-by-bar + vectorized modes |
| Walk-Forward / Monte Carlo | 6 | Hard | Statistical validation framework |

---

## What Is ALREADY DONE vs What Must Be Built

```
┌─────────────────────────────────────────────────────────────────┐
│              ALREADY DONE — v25_DIAG (Reference Only)            │
│              Logic lives in MQL5. Port to Python.                │
│                                                                 │
│  📋 PureRunner (BE at 1× ATR, run to TP)                        │
│  📋 FVG Invalidation exit                                        │
│  📋 Circuit Breaker (3 losses → 4h pause)                       │
│  📋 Same-Level SL Guard                                          │
│  📋 Friday EOD force-close                                       │
│  📋 News hard-cancel                                             │
│  📋 41-column forensic logger                                    │
│  📋 Dynamic risk lot sizing                                      │
│  📋 Session filtering (Asia/London/NY)                           │
│  📋 Spread grading                                               │
│  📋 ML feature logger                                            │
│  📋 Sweep re-entry guard                                         │
│  📋 Kalman velocity filter                                       │
│  📋 ADX trend gate                                               │
│  📋 SLD/ATR floor                                                │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│              MUST BE BUILT (Phases 1–4, 6)                       │
│                                                                 │
│  🔨 Stage 0A: Macro Liquidity Scanner (8 level types)           │
│  🔨 Stage 0b: Base Candle + Swing Validity Gate                  │
│  🔨 Stage 0c: Displacement + FVG Detection                       │
│  🔨 Stage 1:  POI Model Classification (M1–M8 tags)             │
│  🔨 Stage 1b: CHOCH Type Classification (Rule 1/2/3)            │
│  🔨 Stage 2:  5-Pillar Validation Pipeline                       │
│  🔨 Stage 3:  Trigger Routing (A–F, chronological)              │
│  🔨 Stage 4:  Python Execution Engine (order/cancel/modify)     │
│  🔨 Stage 5:  Python Risk Layer (port from v25_DIAG)            │
│  🔨 Backtest Engine (event-driven + vectorized)                  │
│  🔨 Walk-Forward + Monte Carlo validation                        │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│              MUST BE BUILT (Phase 7)                              │
│                                                                 │
│  🔨 MQL5 Safety Watchdog EA (heartbeat + emergency close)       │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│              REUSE — Python Direct MT5 API                        │
│                                                                 │
│  ♻️  MetaTrader5 Python package (copy_rates, order_send)         │
│  ♻️  Python → MT5 direct connection (no HTTP bridge)             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Design Principles

1. **Single Responsibility** — Every class does exactly one thing
2. **Dependency Inversion** — High-level modules depend on abstractions, not concretions
3. **Open/Closed** — POI models, triggers, and pillars are open for extension (new models) but closed for modification (locked decisions frozen)
4. **Testability** — Every component can be unit-tested in isolation with synthetic OHLCV data
5. **Immutable Configuration** — All frozen thresholds from LOCKED_DECISIONS.md are injected as constants, never hardcoded in logic
6. **Python-First** — All logic lives in Python. MQL5 is only a safety watchdog.
7. **Reference Implementation** — v25_DIAG is a logic reference for porting, not a runtime component

---

## Phase 0: Foundations / Infrastructure

**Goal:** Set up project structure, shared types, configuration loading, data access layer, and direct MT5 API connection.

### Classes to Build

```
smc/
├── __init__.py
├── config/
│   ├── __init__.py
│   ├── locked_constants.py        # All frozen values from LOCKED_DECISIONS.md
│   ├── timeframe.py               # Enum: D1, H4, H1, M30, M15, M5, M1
│   └── model_type.py              # Enum: M1–M8, Trigger A–F
├── core/
│   ├── __init__.py
│   ├── candle.py                  # Candle dataclass (OHLCV, timestamp, TF)
│   ├── swing.py                   # Swing dataclass (high/low, base_candle, is_valid)
│   ├── zone.py                    # Zone dataclass (top, bottom, direction, tf)
│   ├── liquidity_level.py         # LiquidityLevel dataclass (type, level, pool, tf)
│   ├── poi.py                     # POI dataclass (zone, models[], score, state, freshness)
│   ├── event.py                   # Event dataclass (type, payload, timestamp, event_id)
│   └── enums.py                   # LiquidityType, POIState, Direction, PoolType
├── data/
│   ├── __init__.py
│   ├── mt5_connector.py           # REUSE — MetaTrader5 Python API wrapper (direct, no HTTP)
│   ├── csv_loader.py              # Load historical OHLCV from CSV for backtesting
│   └── redis_store.py             # Redis state store (POI state, cooldowns, orders)
└── utils/
    ├── __init__.py
    ├── atr.py                     # ATR calculation (period configurable)
    ├── timestamps.py              # UTC conversion, session detection (Asia/London/NY)
    └── pips.py                    # Pip conversion for XAUUSD (4.5 pip tolerance)
```

### Key Responsibilities
- `locked_constants.py` — Every frozen threshold in one place: `EQH_EQL_TOLERANCE = 4.5`, `DISPLACEMENT_MIN_ATR = 1.0`, `DISPLACEMENT_HARD_FAIL = 0.5`, `ZONE_REFINEMENT_ATR = 0.5`, `PREMIUM_THRESHOLD = 0.55`, `DISCOUNT_THRESHOLD = 0.45`, `M5_EXPIRY_BARS = 12`, `M1_EXPIRY_BARS = 30`, `N_BAR_HTF = 5`, `N_BAR_LTF = 3`, `TRIGGER_A_EXPIRY = 20`, `TRIGGER_B_EXPIRY = 30`, `TRIGGER_C_EXPIRY_EXTRA = 3`, `TRIGGER_D_EXPIRY = 1`, `TRIGGER_E_EXPIRY = 15`, `TRIGGER_F_EXPIRY = 1`, etc.
- `mt5_connector.py` — **REUSE existing MetaTrader5 Python API.** Thin wrapper around `MetaTrader5` package. Methods: `copy_rates(symbol, tf, start, count)`, `order_send(request)`, `account_info()`, `positions_get()`, `order_check()`. Python connects DIRECTLY to MT5 — no HTTP bridge needed.
- `redis_store.py` — Methods: `set_poi_state(poi_id, state)`, `get_poi_state(poi_id)`, `atomic_freshness_cas(poi_id, expected, new)`, `set_cooldown(level_id, bars)`, `set_breaker(account_id, pause_until)`.
- `csv_loader.py` — For backtesting: `load_ohlcv(filepath) -> List[Candle]`. Also `load_tradelog(filepath) -> List[TradeRecord]`.

### Dependencies
None — this is the foundation layer.

### Difficulty: **Easy**
- Mostly dataclasses, enums, and thin wrappers
- MT5 connector is REUSED from existing MetaTrader5 Python API — no new bridge code needed
- Can be validated with unit tests using synthetic data

### Missing Design Decisions
- **Redis vs SQLite for backtesting?** Redis is specified for live, but backtesting may need a lightweight local store. Decision needed.
- **Event bus for backtesting?** The live system uses Redis Streams. Backtesting needs an in-process event bus (simple callback queue). Design the abstraction now.

---

## Phase 1: Core Detection — Liquidity + Displacement + Swing Gate

**Goal:** Implement Stage 0A (Liquidity Sweep Detection), Stage 0b (Displacement Check), and Stage 0c (Base Candle / Swing Validation Gate). **This is 100% new code — the current MQL5 EA does not have this full pipeline.**

### Classes to Build

```
smc/detection/
├── __init__.py
├── liquidity_scanner.py           # Scans for all 8 liquidity level types
├── session_levels.py              # Asia/London/NY session highs and lows
├── periodic_levels.py             # PDH/PDL, PWH/PWL
├── eqh_eql_detector.py            # Equal Highs / Equal Lows (≤ 4.5 pip tolerance)
├── structural_swing_detector.py   # Structural swing H/L with Base Candle gate
├── sweep_detector.py              # Wick-pierce + body-close sweep confirmation
├── displacement_checker.py        # BOS + FVG + displacement magnitude
├── fvg_detector.py                # Fair Value Gap (3-candle imbalance)
├── base_candle.py                 # Base Candle identification algorithm
└── swing_validator.py             # Swing validity decision gate
```

### Key Responsibilities
- `liquidity_scanner.py` — Orchestrates all sub-detectors. Returns `List[LiquidityLevel]` for a given bar window.
- `session_levels.py` — Computes session H/L for Asia (00:00–07:00), London (07:00–13:00), NY (13:00–20:00 UTC).
- `eqh_eql_detector.py` — Detects double/triple tops/bottoms within ≤ 4.5 pip tolerance. Both top (BSL) and bottom (SSL) tracked concurrently.
- `structural_swing_detector.py` — Identifies swing H/L, then calls `base_candle.py` and `swing_validator.py` to confirm. Uses N-bar confirmation (N=5 HTF, N=3 LTF).
- `sweep_detector.py` — Checks if price wick-pierces a structural level and candle body closes back inside. Tracks BSL/SSL direction.
- `displacement_checker.py` — After sweep, checks: (1) BOS confirmed (close beyond prior swing), (2) FVG created (3-candle imbalance), (3) Displacement > 1× ATR. Hard fail < 0.5× ATR.
- `base_candle.py` — Implements the Base Candle identification: bullish = candle whose HIGH = swing high; bearish = candle whose LOW = swing low (with the bearish exception rule).
- `swing_validator.py` — Decision gate: Did price break Base Candle's OPPOSITE extreme? Did candle CLOSE beyond? Two-bar reversal alone does NOT confirm.

### Dependencies
Phase 0 (core types, config, data access)

### Difficulty: **Medium**
- Each sub-detector is straightforward (deterministic algorithms)
- The orchestration logic in `liquidity_scanner.py` must handle 8 level types with correct priority ordering
- Swing validation gate has subtle edge cases (bearish exception rule, two-bar reversal trap)
- FVG detection requires careful 3-candle window logic
- **Note:** v25_DIAG has basic sweep detection, but it is tightly coupled to MQL5 and does NOT implement the full Stage 0A pipeline (no session levels, no periodic levels, no EQH/EQL detector, no Base Candle gate). This is genuinely new work.

### Missing Design Decisions
- **Bar window size for swing detection?** LOCKED_DECISIONS says N-bar confirmation, but how many bars of history to scan? Need a `lookback_bars` parameter.
- **Session timezone handling?** The spec says UTC, but MT5 may use broker server time. Need a timezone normalization layer.

---

## Phase 2: POI Classification — M1–M8 Modular Tags

**Goal:** Implement Stage 1 (POI Model Classification) and Stage 1b (CHOCH Type Classification). Each model is an independent, pluggable module. **This is 100% new code — the current MQL5 EA does not have modular POI tags.**

### Classes to Build

```
smc/poi/
├── __init__.py
├── base_model.py                  # Abstract base class for all POI models
├── confluence_scorer.py           # Counts independent model tags, computes quality score
├── models/
│   ├── __init__.py
│   ├── m1_origin_base.py          # Origin Demand/Supply Base
│   ├── m2_rbs_sbr_breaker.py      # RBS/SBR Breaker
│   ├── m3_choch_retest.py         # CHOCH Retest (3 sub-variants)
│   ├── m4_quasimodo.py            # Quasimodo (QML)
│   ├── m5_extreme_equal_highs.py  # Extreme Equal Highs / Supply Origin
│   ├── m6_neckline_retest.py      # Neckline / Double Top-Bottom
│   ├── m7_equal_resistance.py     # Equal Resistance Shelf
│   ├── m8_htf_demand_supply.py    # HTF Demand/Supply (D1/H4)
│   └── model_registry.py          # Registry: maps ModelType -> model instance
├── choch_classifier.py            # CHOCH Rule 1/2/3 classification
└── deal_range.py                  # Premium/Discount zone computation
```

### Key Responsibilities
- `base_model.py` — Abstract class: `def detect(self, candles, swings, liquidity_levels) -> List[POI]`. Each model implements this interface.
- `model_registry.py` — Registry pattern: `register(ModelType.M1, M1OriginBase())`. Allows dynamic model registration.
- `confluence_scorer.py` — Given a price level with multiple model tags, computes: 1 tag = base, 2 = elevated, 3+ = institutional-grade. No model is suppressed.
- `m3_choch_retest.py` — Detects CHOCH + retest. Delegates to `choch_classifier.py` for Rule 1/2/3 sub-variant. Entry at broken structural level (not origin OB). SL above/below sweep extreme (Head).
- `m4_quasimodo.py` — Detects QML: Left Shoulder → Head (sweep) → Neckline break → LS free. Entry: full wick range [left_shoulder_low, left_shoulder_high].
- `m5_extreme_equal_highs.py` — Proactive: equal highs/lows formed, then broken. Continuation setup. Distinguished from M7 (reactive shelf).
- `m7_equal_resistance.py` — Reactive: bounce creates resistance shelf, then broken. Equal peaks from shelf formation.
- `m8_htf_demand_supply.py` — Multi-timeframe: scans D1/H4 for OB, FVG, Demand/Supply zones (single last opposing candle). Then monitors M5 approach → M1 trigger. +0.10 quality-score bonus for D1+H4 overlap.
- `choch_classifier.py` — Rule 1: Standard (body close breaks last swing). Rule 2: Inside Body (body close breaks intermediate, last swing NOT broken). Rule 3: Inside Wick (wick only, weakest but KEPT).
- `deal_range.py` — Computes dealing range on detection TF. Bullish POIs must be in Discount (<45%). Bearish in Premium (>55%). 45–55% = REJECT.

### Dependencies
Phase 0 (core types), Phase 1 (detection outputs: swings, liquidity levels, displacement)

### Difficulty: **Hard**
- M3 (CHOCH) has 3 sub-variants with subtle detection rules — the most complex model
- M4 (QML) requires left-shoulder anchoring with full wick range
- M8 is multi-timeframe — requires coordinating D1/H4 scan with M5 approach and M1 trigger
- Confluence scorer must handle overlapping levels correctly
- Each model must be independently testable with synthetic patterns
- **Note:** v25_DIAG has a simple score-based entry filter but does NOT implement the 8-model modular tag system. This is the single biggest architectural upgrade.

### Missing Design Decisions
- **POI zone representation?** Is a POI a price level (line) or a zone (range)? LOCKED_DECISIONS uses both. Need to decide: zone = [top, bottom] with preferred entry in upper/lower 50%.
- **Model 8 timing?** D1/H4 zones are identified on higher TFs. When exactly does the M5 approach phase start? On bar close that enters the zone? On tick?

---

## Phase 3: 5-Pillar Validation

**Goal:** Implement Stage 2 (POI Validation Pipeline). Each pillar is an independent validator. **This is 100% new code — the current MQL5 EA uses a simple score threshold, not the 5-pillar pipeline.**

### Classes to Build

```
smc/validation/
├── __init__.py
├── pillar.py                      # Abstract base class for all pillars
├── pillar_1_zone_refinement.py    # ±0.5× ATR zone refinement
├── pillar_2_displacement.py       # Displacement > 1× ATR
├── pillar_3_premium_discount.py   # Dealing range P/D check
├── pillar_4_freshness.py          # 1-touch state machine
├── pillar_5_inducement.py         # Soft score (100% with, 70% without)
├── validation_pipeline.py         # Orchestrates all 5 pillars
└── state_machine.py               # POI state transitions (CREATED→FRESH→TESTED/VIOLATED)
```

### Key Responsibilities
- `pillar_1_zone_refinement.py` — Checks if unmitigated OB or FVG exists within ±0.5× ATR of POI. Pass/Fail.
- `pillar_2_displacement.py` — Checks BOS + FVG + displacement > 1× ATR. Pass/Fail.
- `pillar_3_premium_discount.py` — Coupled to detection TF. Buys <45%, Sells >55%. 45–55% = REJECT. Pass/Fail.
- `pillar_4_freshness.py` — Strict 1-touch only. STATE_FRESH → STATE_TESTED (terminal). Unfilled order expiry: M5=12 bars, M1=30 bars.
- `pillar_5_inducement.py` — Soft gate. EQH/EQL, trendline, or minor swing in front of POI. Score: 100% with, 70% without. Never hard reject.
- `validation_pipeline.py` — Runs all 5 pillars. All must pass except Inducement (soft). Returns validated POI with score.
- `state_machine.py` — Atomic state transitions. Live: Redis Lua CAS. Backtest: in-memory dict with lock.

### Dependencies
Phase 0 (core types, config), Phase 1 (displacement data), Phase 2 (POI with zone, direction, model tags)

### Difficulty: **Medium**
- Pillars 1–3 are straightforward threshold checks
- Pillar 4 (freshness) requires state management — the state machine must be race-proof in live mode
- Pillar 5 (inducement) requires detecting trendlines and minor swings "in front of" the POI — this is somewhat subjective
- The pipeline orchestrator must handle the soft-gate logic for Pillar 5

### Missing Design Decisions
- **Inducement detection algorithm?** "EQH/EQL, trendline, or minor swing directly in front of POI" — how is "directly in front" defined? Needs a spatial criterion (e.g., within N bars, within X pips).
- **Freshness state persistence?** For backtesting, should state be reset per backtest run? For live, Redis is specified. Need to clarify the abstraction boundary.

---

## Phase 4: LTF Triggers + Python Execution

**Goal:** Implement Stage 3 (Trigger Routing) and Stage 4 (Execution). Python detects the trigger AND places the order directly via MT5 API. **No HTTP bridge — Python owns everything.**

### Classes to Build

```
smc/triggers/
├── __init__.py
├── base_trigger.py                # Abstract base class for all triggers
├── trigger_a_choch.py             # CHOCH Reversal (20 M5 bars expiry)
├── trigger_b_leading_diagonal.py  # Leading Diagonal (30 bars after Wave 5)
├── trigger_c_ending_diagonal.py   # Ending Diagonal (sweep candle + 3 bars)
├── trigger_d_two_bar.py           # Two-Bar Reversal (next bar only)
├── trigger_e_rsi_divergence.py    # RSI Divergence (15 bars after pattern)
├── trigger_f_bos_ob.py            # BOS + OB Continuation (first touch only)
├── trigger_router.py              # Chronological first-valid trigger wins
├── trigger_expiry.py              # Per-trigger expiry enforcement
└── compatibility_matrix.py        # POI × Trigger compatibility (§15 matrix)

smc/execution/
├── __init__.py
├── order_manager.py               # Order placement, cancel, modify via MT5 API
├── position_manager.py            # Position monitoring, SL/TP adjustment
├── news_guard.py                  # Hard cancel 15 min before CPI/NFP/FOMC
└── session_filter.py              # Asia/London/NY session enforcement
```

### Key Responsibilities
- `trigger_a_choch.py` — Detects M1/M5 CHOCH. Entry: limit at broken level. SL: above/below sweep extreme. Expiry: 20 M5 bars.
- `trigger_c_ending_diagonal.py` — 5-wave diagonal into POI → Wave 5 trendline sweep. PREFERRED for Model 8. SL: ultra-tight beyond Wave 5 wick. Expiry: sweep candle + 3 bars.
- `trigger_d_two_bar.py` — Engulfing in POI zone. Limit at 50% of engulfing body (NOT market order). Expiry: bar immediately following only.
- `trigger_router.py` — Drops to M1/M5. Arms compatible triggers per §15 matrix. First valid trigger (chronological) wins. Frozen rule.
- `trigger_expiry.py` — Enforces per-trigger expiry windows. No trigger fires → POI → STATE_TESTED.
- `compatibility_matrix.py` — Hardcoded matrix from LOCKED_DECISIONS §15. Model 8 + Ending Diagonal = preferred (✓★).
- `order_manager.py` — **PYTHON DIRECT.** Methods: `place_limit(direction, entry, sl, tp, lots)`, `place_market(direction, sl, tp, lots)`, `cancel_order(ticket)`, `modify_order(ticket, sl, tp)`. Uses `MetaTrader5.order_send()`.
- `position_manager.py` — **PYTHON DIRECT.** Methods: `get_open_positions()`, `get_position_pnl(ticket)`, `close_position(ticket)`, `modify_sl(ticket, new_sl)`. Uses `MetaTrader5.positions_get()`.
- `news_guard.py` — Cancels all pending limits 15 min before high-impact US events. Re-evaluates 30 min post-release.
- `session_filter.py` — Enforces session windows. Blocks entries outside Asia/London/NY.

### Dependencies
Phase 0 (core types), Phase 2 (validated POIs), Phase 3 (freshness state)

### Difficulty: **Hard**
- Trigger C (Ending Diagonal) requires Elliott Wave counting — the most subjective trigger
- Trigger B (Leading Diagonal) also requires wave counting
- Trigger routing must enforce chronological ordering — timing is critical
- `order_manager.py` must handle MT5 API errors, retries, and slippage gracefully
- **Note:** This is now Python execution, not MQL5. Python places orders directly via MT5 API.

### Missing Design Decisions
- **Wave counting algorithm?** Leading/Ending Diagonals require 5-wave identification. This is notoriously subjective. Need to define a deterministic algorithm or mark these as "manual review recommended."
- **Order retry logic?** What happens if `order_send()` fails? Retry immediately? Retry on next bar? Need a retry policy.
- **Slippage handling?** How does Python handle slippage? Accept any fill? Cancel if slippage > X pips?

---

## Phase 5: Risk Layer — Port v25_DIAG Logic to Python

**Goal:** Port ALL defensive risk components from v25_DIAG (MQL5) to Python. Python becomes the single source of truth for risk management. **v25_DIAG is the reference implementation — logic must match exactly.**

### Classes to Build

```
smc/risk/
├── __init__.py
├── pure_runner.py                 # BE at 1× ATR, zero early partials, run to TP
├── fvg_invalidation.py            # Hard exit if candle closes beyond FVG boundary
├── circuit_breaker.py             # 3 losses → 4h pause, Z-score validated
├── same_level_guard.py            # Blocks re-entry if SL within 0.1× ATR of last SL
├── friday_eod.py                  # Force-close all at 20:00 UTC Friday
├── lot_sizing.py                  # Dynamic risk: Lots = (Equity × Risk%) / (SL × tick_value)
├── spread_grading.py              # Realistic spread classification (A+/A/B/C)
├── sweep_guard.py                 # 4-bar cooldown on same zone
├── kalman_filter.py               # Kalman probability gating
├── adx_gate.py                    # Blocks entries when ADX < 25
├── atr_floor.py                   # Blocks entries when stop distance < 1.0× ATR
└── risk_engine.py                 # Orchestrates all risk components
```

### Key Responsibilities
- `pure_runner.py` — Port from v25_DIAG. Move SL to breakeven at 1.0× ATR. Zero early partials. 100% of trades run to TP.
- `fvg_invalidation.py` — Port from v25_DIAG. If candle body closes beyond FVG boundary, hard exit immediately.
- `circuit_breaker.py` — Port from v25_DIAG. After 3 consecutive losses, pause trading for 4 hours. Z-score validated (-2.27).
- `same_level_guard.py` — Port from v25_DIAG. If new SL is within 0.1× ATR of last SL, block re-entry.
- `friday_eod.py` — Port from v25_DIAG. Force-close all positions at 20:00 UTC Friday.
- `lot_sizing.py` — Port from v25_DIAG. `Lots = (Equity × Risk%) / (SL × tick_value)`. Risk 0.5–1.0%.
- `spread_grading.py` — Port from v25_DIAG. Classify spread as A+ (<15 pts), A (15–25), B (25–40), C (>40).
- `sweep_guard.py` — Port from v25_DIAG. 4-bar cooldown on same liquidity zone.
- `kalman_filter.py` — Port from v25_DIAG. Kalman probability gating for velocity.
- `adx_gate.py` — Port from v25_DIAG. Block entries when ADX < 25.
- `atr_floor.py` — Port from v25_DIAG. Block entries when stop distance < 1.0× ATR.
- `risk_engine.py` — Orchestrates all risk components. Called on every tick/bar. Returns PASS/FAIL + action.

### v25_DIAG Reference Files
- `GOLD_SMC_v25_DIAG.mq5` — Source of truth for all risk logic
- Port each function carefully. Validate with unit tests against MQL5 behavior.

### Dependencies
Phase 0 (core types), Phase 4 (execution layer)

### Difficulty: **Medium**
- Each component is a direct port from v25_DIAG — logic is proven and documented
- Main challenge: ensuring Python port matches MQL5 behavior exactly (floating point precision, timing, edge cases)
- Unit tests must validate parity with v25_DIAG outputs
- **Note:** This is no longer "decisions only" — it is active porting work. Each component must be carefully translated from MQL5 to Python.

### Missing Design Decisions
- **Port fidelity tolerance?** How close must Python match MQL5? Exact bit-for-bit? Or within floating-point tolerance (1e-6)?
- **Port order?** Which components to port first? Start with simplest (Friday EOD) or most critical (PureRunner)?
- **Testing strategy?** How to validate parity? Run both MQL5 and Python on same data and compare outputs?

---

## Phase 6: Backtesting & Paper Trading

**Goal:** Build the backtesting harness and paper trading bridge. **Since Python owns all logic, backtest uses the SAME code as live — no separate risk_simulator.py needed.**

### Classes to Build

```
smc/backtest/
├── __init__.py
├── backtest_engine.py             # Main backtest loop (bar-by-bar or vectorized)
├── event_bus.py                   # In-process event bus (callback queue, no Redis)
├── state_store.py                 # In-memory state store (dict + lock)
├── performance_analyzer.py        # PF, RF, win rate, MFE/MAE, regime analysis
├── walk_forward.py                # Walk-forward OOS validation (3 years)
├── monte_carlo.py                 # Monte Carlo simulation for robustness
└── report_generator.py            # Generate HTML/CSV reports

smc/paper/
├── __init__.py
├── paper_trading_runner.py        # Runs live pipeline on demo account
├── slippage_simulator.py          # Simulates variable spreads (25–50 pts) and latency
└── kpi_logger.py                  # Logs operational KPIs (latency, success rate, etc.)
```

### Key Responsibilities
- `backtest_engine.py` — Two modes: (1) Bar-by-bar simulation using event bus, (2) Vectorized batch processing for speed. Ingests CSV OHLCV, runs full L0-L7 pipeline. **Uses the SAME Python risk layer as live.**
- `event_bus.py` — In-process callback queue. Replaces Redis Streams for backtesting. Same event contracts as live.
- `state_store.py` — In-memory dict with threading lock. Replaces Redis for backtesting. Same key patterns.
- `performance_analyzer.py` — Computes: Profit Factor, Recovery Factor, win rate, average RR, MFE/MAE distribution, regime analysis (trend/range), per-model performance.
- `walk_forward.py` — Splits data into in-sample (2 years) and out-of-sample (1 year). Walk-forward with 6-month windows.
- `paper_trading_runner.py` — Runs the full Python pipeline on a demo account. Logs all operational KPIs for the Future Flexibility Clause.
- `kpi_logger.py` — Logs: latency (bar-close → order ACK), order success rate, management delay, missed events, etc. This data determines if any component needs porting back to MQL5.

### Dependencies
Phases 0–5 (full pipeline must be complete)

### Difficulty: **Hard**
- Backtest engine must faithfully reproduce the live event-driven pipeline
- Vectorized mode requires careful handling of state-dependent logic (freshness, cooldowns)
- Walk-forward and Monte Carlo are statistically complex
- **Advantage:** Same Python code runs in backtest and live — no separate risk_simulator.py needed

### Missing Design Decisions
- **Backtest speed target?** How fast does the backtest need to run? 5 years of M1 data is ~1.3M bars. Vectorized mode may be needed.
- **Walk-forward window size?** LOCKED_DECISIONS doesn't specify. The restart plan says "3 years: 2022, 2023, 2025" but window sizing needs a decision.
- **Paper trading duration?** The restart plan says "30 consecutive trading days." Is this sufficient?
- **KPI thresholds?** What KPI values trigger the Future Flexibility Clause? Latency > X ms? Missed events > Y%?

---

## Phase 7: Live Readiness + MQL5 Safety Watchdog

**Goal:** Deploy to live MT5 demo account. Build the MQL5 Safety Watchdog EA (heartbeat monitor + emergency position close). **The MQL5 EA is now a thin safety layer — no entry logic, no normal trade management.**

### MQL5 Safety Watchdog EA

```
SMC_Safety_Watchdog.mq5
├── OnTimer()
│   ├── Check Python heartbeat (Redis key or file touch)
│   ├── If heartbeat stale (> 5 seconds):
│   │   ├── Log emergency event
│   │   ├── Close ALL open positions at market
│   │   ├── Cancel ALL pending orders
│   │   └── Send alert (email/Telegram)
│   └── If heartbeat alive:
│       └── Do nothing (Python handles everything)
└── OnDeinit()
    └── Log shutdown event
```

**MQL5 Safety Watchdog — Responsibilities:**
1. Monitor Python heartbeat (Redis key `python:heartbeat` updated every 1 second by Python)
2. If heartbeat is stale (> 5 seconds), assume Python is dead
3. Emergency close ALL open positions at market price
4. Emergency cancel ALL pending orders
5. Send alert notification
6. **That's it.** No entry logic. No SL/TP management. No session filtering. No risk management. All of that is Python.

**MQL5 Safety Watchdog — What It Does NOT Do:**
- ❌ No entry logic
- ❌ No SL/TP placement
- ❌ No PureRunner
- ❌ No FVG Invalidation
- ❌ No Circuit Breaker
- ❌ No Same-Level Guard
- ❌ No Friday EOD
- ❌ No news cancel
- ❌ No session filtering
- ❌ No spread grading

### Python Live Components

```
smc/live/
├── __init__.py
├── config_loader.py               # Load production config from YAML/JSON
├── heartbeat.py                   # Update Redis key every 1 second
├── main_loop.py                   # Main event loop (bar-by-bar or tick)
└── integration_test.py            # End-to-end test: Python → MT5 → fill
```

### Key Responsibilities
- `config_loader.py` — Load production config: symbol, timeframes, risk%, news calendar, Redis connection.
- `heartbeat.py` — Updates Redis key `python:heartbeat` every 1 second. MQL5 Safety Watchdog monitors this.
- `main_loop.py` — Main event loop: poll MT5 for new bars, run pipeline, execute trades, manage positions.
- `integration_test.py` — End-to-end test: Python detects POI → validates → triggers → executes → manages → heartbeat alive.

### Dependencies
Phases 0–6 (complete system validated in backtest and paper)

### Difficulty: **Easy**
- MQL5 Safety Watchdog is a thin script (~50 lines of MQL5)
- Python live components are mostly configuration and glue code
- Main work is integration testing and validation
- **Note:** The heavy lifting (risk management, execution) is already done in Phases 4–5

### Missing Design Decisions
- **VPS hosting?** Where will the system run? Latency requirements (≤100ms bar-close→broker ACK) suggest co-location.
- **Monitoring/alerting?** How are alerts delivered? Email? Telegram? Need to decide.
- **Heartbeat interval?** How often does Python update the heartbeat? Every 1 second? Every tick?
- **Heartbeat timeout?** How long before MQL5 declares Python dead? 5 seconds? 10 seconds?

---

## Summary: Difficulty & Effort Matrix

| Phase | Difficulty | Key Challenge | Depends On | Effort | Notes |
|-------|-----------|---------------|------------|--------|-------|
| **0: Foundations** | Easy | Data types + MT5 API wrapper | None | **1 day** | REUSE MetaTrader5 Python API |
| **1: Core Detection** | Medium | 8 liquidity types, swing gate edge cases | Phase 0 | **3–5 days** | 100% new code |
| **2: POI Classification** | Hard | M3 CHOCH (3 variants), M8 multi-TF | Phases 0–1 | **5–8 days** | 100% new code |
| **3: 5-Pillar Validation** | Medium | Freshness state machine, inducement | Phases 0–2 | **3–4 days** | 100% new code |
| **4: LTF Triggers + Execution** | Hard | Wave counting (B/C), Python direct execution | Phases 0–3 | **5–8 days** | Triggers new; execution via MT5 API |
| **5: Risk Layer (Port)** | Medium | Port v25_DIAG logic to Python, ensure parity | Phase 0 | **3–5 days** | Port 15 components from MQL5 |
| **6: Backtesting** | Hard | Faithful simulation, walk-forward, Monte Carlo | Phases 0–5 | **4–6 days** | Same code as live |
| **7: Live + Safety Watchdog** | Easy | MQL5 thin watchdog + integration testing | Phases 0–6 | **1–2 days** | MQL5 ~50 lines; Python glue |
| **TOTAL** | | | | **25–39 days** | 5–8 weeks at full-time |

**Total estimated effort:** 25–39 working days (5–8 weeks at full-time)

---

## What Can Be Built Relatively Easily

1. **Phase 0 (Foundations)** — Pure data types, REUSE MetaTrader5 Python API
2. **Phase 7 (Safety Watchdog)** — Thin MQL5 script (~50 lines) + Python glue
3. **Pillars 1–3** — Threshold checks against ATR and dealing range
4. **Freshness state machine** — Simple state transitions
5. **Confluence scorer** — Count model tags
6. **Trigger expiry enforcer** — Per-trigger window checks
7. **Compatibility matrix** — Hardcoded lookup table
8. **Friday EOD** — Simple time check
9. **Same-Level SL Guard** — Distance check
10. **ADX/ATR gates** — Threshold checks

## What Will Be Technically Difficult

1. **M3 CHOCH (3 variants)** — The detection rules are subtle (standard vs inside body vs inside wick). Requires careful parsing of swing structure.
2. **M4 QML** — Left-shoulder anchoring with full wick range requires precise geometry.
3. **M8 Multi-Timeframe** — Coordinating D1/H4 zone detection with M5 approach and M1 trigger across different data streams.
4. **Trigger B/C Wave Counting** — Leading/Ending Diagonals require 5-wave identification. This is notoriously subjective in real markets.
5. **Port Parity** — Ensuring Python ports of v25_DIAG components match MQL5 behavior exactly (floating point, timing, edge cases).
6. **Freshness CAS in Redis** — The atomic Lua CAS script must be race-proof under concurrent events.
7. **Python Execution Reliability** — Python must handle MT5 API errors, retries, connection drops gracefully.

## Missing Design Decisions That Should Be Resolved Before Coding

| # | Decision | Impact | Current Status |
|---|----------|--------|----------------|
| 1 | **Event bus abstraction for backtest vs live** | Affects every phase | Not designed — need an `EventBus` interface with `InProcessBus` (backtest) and `RedisStreamsBus` (live) implementations |
| 2 | **POI zone representation** | Affects Phases 2–4 | LOCKED_DECISIONS uses both "level" and "zone." Need to decide: `Zone(top, bottom)` with entry at upper/lower 50%? |
| 3 | **Wave counting algorithm** | Affects Phase 4 | No deterministic algorithm exists in the codebase. Either define one or mark B/C triggers as "manual review only" |
| 4 | **Inducement spatial criterion** | Affects Phase 3 | "Directly in front of POI" is undefined. Need: within N bars? Within X pips? |
| 5 | **Port fidelity tolerance** | Affects Phase 5 | How close must Python match MQL5? Exact bit-for-bit? Or within floating-point tolerance (1e-6)? |
| 6 | **Order retry policy** | Affects Phase 4 | What happens if `order_send()` fails? Retry immediately? Retry on next bar? |
| 7 | **Heartbeat interval/timeout** | Affects Phase 7 | How often does Python update heartbeat? How long before MQL5 declares Python dead? |
| 8 | **KPI thresholds for flexibility clause** | Affects Phase 6 | What KPI values trigger porting a component back to MQL5? |

---

## Recommended Build Order

```
Phase 0 (1 day) — Foundations: types, MT5 API wrapper
    ↓
Phase 1 (3-5 days) — Core Detection: Liquidity + Displacement + Swing Gate
    ↓
Phase 2 (5-8 days) — POI Classification: M1–M8 Modular Tags ← HARDEST
    ↓
Phase 3 (3-4 days) — 5-Pillar Validation
    ↓
Phase 4 (5-8 days) — LTF Triggers + Python Execution ← SECOND HARDEST
    ↓
Phase 5 (3-5 days) — Risk Layer: Port v25_DIAG to Python ← THIRD HARDEST
    ↓
Phase 6 (4-6 days) — Backtesting: same code as live
    ↓
Phase 7 (1-2 days) — Live: MQL5 Safety Watchdog + integration test
```

**Total estimated effort:** 25–39 working days (5–8 weeks at full-time)

**Critical path:** Phases 0→1→2→3→4→5 (the core pipeline + risk layer). Phases 6–7 are lightweight once Phase 5 is complete.

**Recommended first milestone:** After Phase 3, run a minimal backtest with M1/M3/M5 models on 1 year of data to validate the pipeline architecture before building triggers and execution.

---

## Changelog

| Date | Change | Reason |
|------|--------|--------|
| 2026-09-06 | Initial plan created | Based on LOCKED_DECISIONS.md Rev 5 + codebase audit |
| 2026-09-06 | Added re-use inventory (v25_DIAG + CAB) | User revision instruction |
| 2026-09-06 | Reduced effort from 28–44 to 22–33 days | Re-use savings |
| 2026-09-06 | **OPTION A LOCKED: Python owns ALL logic** | Lead Architect decision |
| 2026-09-06 | MQL5 reduced to Safety Watchdog only | Lead Architect decision |
| 2026-09-06 | Phase 4: Python execution (no HTTP bridge) | Lead Architect decision |
| 2026-09-06 | Phase 5: Port v25_DIAG to Python (not keep in MQL5) | Lead Architect decision |
| 2026-09-06 | Phase 7: MQL5 Safety Watchdog EA (~50 lines) | Lead Architect decision |
| 2026-09-06 | Added Future Flexibility Clause | Lead Architect decision |
| 2026-09-06 | Revised effort to 25–39 days (port work added) | Accurate estimates |

---

*This plan is based on LOCKED_DECISIONS.md Revision 5, the existing codebase audit, and the permanent architecture decision that Python owns ALL trading logic. MQL5 is reduced to a Safety Watchdog (heartbeat monitor + emergency position close). All frozen rules are respected. v25_DIAG is a reference implementation for porting, not a runtime component.*
