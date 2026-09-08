# SESSION HANDOFF — SMC BOT

**Last Updated:** 2026-09-07
**Purpose:** Everything a new agent needs to continue this project without asking questions.

---

## Project Goal

Build a modular SMC (Smart Money Concepts) trading bot for XAUUSD on MT5 using a **Python-First architecture with MQL5 Safety Watchdog**. Python owns ALL trading logic. MQL5 is only a safety net.

---

## Current Architecture Decision (LOCKED)

**Option A — Python-First + MQL5 Safety Watchdog**

1. Python owns ALL trading logic:
   - Stage 0A: Liquidity Sweep + Displacement + Swing Gate
   - Stage 1–1b: POI Classification (M1–M8) + CHOCH Rules
   - Stage 2: 5-Pillar Validation
   - Stage 3: Trigger Routing
   - Stage 4: Execution (order placement, cancel, modify)
   - Stage 5: Trade Management (PureRunner, FVG Invalidation, Circuit Breaker, Same-Level Guard, Friday EOD)

2. MQL5 role reduced to Safety Watchdog only:
   - Heartbeat monitoring of Python process
   - Emergency protection of open positions if Python heartbeat dies
   - No entry logic, no normal trade management

3. Future Flexibility Clause: If any Python component proves problematic during paper trading, we may selectively port it back to MQL5 — but only after measured evidence.

---

## Source of Truth Files

| File | Location | Status |
|------|----------|--------|
| `LOCKED_DECISIONS.md` | `00_LOCKED/` | FROZEN Rev 5 (2026-09-01). Do not modify. |
| `DEVELOPMENT_PLAN.md` | `00_LOCKED/` | Option A Locked. Master build plan. |
| `CHOCH_TYPES_AND_SWING_VALIDITY.md` | `00_LOCKED/` | CHOCH detection rules (3 variants). |
| `MODEL_8_HTF_DEMAND_SUPPLY.md` | `00_LOCKED/` | Model 8 specification. |
| `SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md` | `00_LOCKED/` | 1061-line formal specs for all 8 models. |
| `TODO.md` | `00_LOCKED/` | Living task board. |
| `CHANGELOG.md` | `00_LOCKED/` | Every change recorded here. |

---

## Current Project Structure

```
SMC/
├── 00_LOCKED/           ← Source of Truth (read-only)
├── 01_ARCHITECTURE/     ← Current design docs + v5 flowcharts
├── 02_KNOWLEDGE_BASE/   ← 57 PNG visual references
├── 03_REFERENCE_CODE/   ← GOLD_SMC_v25_DIAG.mq5 + CAB files
├── 04_SRC/              ← Python codebase (Phases 0–5 built: `smc` package + tests)
├── 05_MQL5_SAFETY/      ← Future Safety Watchdog EA
├── 06_RESEARCH/         ← Active research scripts + experiments
└── ARCHIVE/             ← All historical files by era
```

**Note on CAB files:** CAB files are temporary reference only. Archive them after the Python MT5 connector is complete.

---

## What is Locked (DO NOT CHANGE)

- All 8 POI models (M1–M8) — detection, validation, trigger routing
- 5-Pillar Validation Pipeline
- 6 Trigger types (A–F) and compatibility matrix
- All frozen thresholds (ATR multipliers, expiry bars, pip tolerances)
- Confluence scoring rule (1 tag = base, 2 = elevated, 3+ = institutional)
- Trigger routing order (chronological first-valid wins)
- Option A architecture decision (Python-First + MQL5 Safety Watchdog)

---

## What is Already Built vs What Must Be Built

### Already Built (v25_DIAG — Reference Only)
- PureRunner (BE at 1× ATR)
- FVG Invalidation
- Circuit Breaker (3 losses → 4h)
- Same-Level SL Guard
- Friday EOD
- 41-Column Forensic Logger
- Dynamic Risk Lot Sizing
- Session Filtering
- Spread Grading
- ML Feature Logger
- CAB bridge pattern

### Must Be Built
- **Phase 0:** Project structure, types, MT5 connector (1 day) — ✅ BUILT (2026-09-06)
- **Phase 1:** Core Detection — Liquidity Scanner, Swing Gate, Displacement (3–5 days) — ✅ BUILT (2026-09-06)
- **Phase 2:** POI Classification — M1–M8 Modular Tags (5–8 days) — ✅ BUILT (2026-09-06)
- **Phase 3:** 5-Pillar Validation Pipeline (3–4 days) — ✅ BUILT (2026-09-07)
- **Phase 4:** LTF Triggers + Python Execution (5–8 days) — ✅ BUILT (2026-09-07)
- **Phase 5:** Port v25_DIAG Risk Layer to Python (3–5 days) — ✅ BUILT (2026-09-07)
- **Phase 6:** Backtesting & Paper Trading (4–6 days) — NEXT
- **Phase 7:** MQL5 Safety Watchdog + Live Integration (1–2 days)
- **News Hard-Cancel:** Must be implemented in Python (not yet ported)

**Total estimated effort:** 25–39 working days

---

## Current Phase & Next Task

**Current Phase:** Phase 5 — Risk Layer (v25_DIAG Port) ✅ COMPLETE (2026-09-07)
**Next Phase:** Phase 6 — Backtesting & Paper Trading
(backtest engine, event bus, state store, performance analyzer,
walk-forward, Monte Carlo, report generator; paper trading runner,
slippage simulator, KPI logger)

Phase 5 locked the risk constants (§28 in `locked_constants.py` +
`LOCKED_DECISIONS.md` §28.1–28.9) and delivered `smc/risk/` (Stage 5: lot
sizing policy, circuit breaker, same-level guard, Friday EOD, sweep guard,
spread grading, PureRunner, FVG invalidation and the `RiskEngine`
orchestrator) with 90 tests; full suite is **340/340** (36 Phase 0 +
56 Phase 1 + 42 Phase 2 + 40 Phase 3 + 76 Phase 4 + 90 Phase 5). See
`TODO.md` (Phase 6 checklist) and `CHANGELOG.md` for details.

---

## Phase 5 Implementation Notes (V1 definitions — 2026-09-07)

- **Risk constants are LOCKED (§28):** `locked_constants.py` now carries the
  §28 group (PureRunner BE 1.0× ATR + 0.10 buffer; circuit breaker 3 losses →
  4h; same-level guard 0.15× ATR + 4-bar cooldown; Friday EOD 20:00 UTC;
  spread max 0.15× ATR + score-tier grade maps; sweep guard 0.5× ATR + 4
  bars; risk band 0.5–1.0%; LOT_MAX_SAFETY 0.10; optional gates ADX ≥ 25.0
  and ATR floor 1.0). `LOCKED_DECISIONS.md` §28 is the authoritative record —
  Same-Level = 0.15 (running default, supersedes the outdated 0.1 comment);
  spread grading = score-tier multipliers over SPREAD_MAX_ATR, not the point
  bands once written in DEVELOPMENT_PLAN.
- **Stage 5 lives in `smc/risk/`:** `lot_sizing.py` (policy layer over the
  single Phase 4 formula — re-export, no parallel path), `circuit_breaker.py`,
  `same_level_guard.py`, `friday_eod.py`, `sweep_guard.py`,
  `spread_grading.py`, `pure_runner.py`, `fvg_invalidation.py`,
  `risk_engine.py`. Every component is a pure decision maker with an
  injectable state dataclass — NO MT5 calls anywhere in the layer; the
  Phase 6/7 runner applies decisions.
- **`RiskEngine` public API (the Phase 6 integration seam):**
  - `evaluate_entry(EntryRequest) -> EntryDecision` — gates in v25 pipeline
    order: news (§11) → session (§2) → circuit breaker (§28.2) → same-level
    guard (§28.3) → sweep guard (§28.6) → spread grading (§28.5, soft/hard
    toggle via `spread_gate_enabled`) → risk-band clamp + `sized_lots`
    (§28.7). First block wins; `blocked_by` is a machine-readable reason;
    undersized lots also block. Pass → `RiskAction.ENTER` + `lots`.
  - `evaluate_exit(PositionState, *, now, fvg_context) -> ExitDecision` —
    per-position priority: FVG invalidation (closed-bar close only) →
    PureRunner BE move (§28.1, one-shot latch). `MOVE_SL` carries `new_sl`.
    Friday EOD is NOT evaluated here — it is portfolio-level:
    `evaluate_friday_close(now) -> bool` (call ONCE per bar, BEFORE any
    per-position `evaluate_exit`; True ⇒ close ALL positions + cancel
    pending orders).
  - `evaluate_friday_close(now) -> bool` — portfolio-level Friday EOD
    (§28.4) with the once-per-Friday latch owned by the engine so a
    multi-position book cannot have it consumed by one position.
  - `hard_cancel_pending(now, news_events) -> bool` — §11 hard-cancel:
    True when ALL pending limit orders must be cancelled (pre-news
    blackout); the runner performs cancellations via `OrderManager`.
  - `on_trade_opened()` / `on_be_applied()` — lifecycle hooks:
    `on_trade_opened` re-arms the per-trade PureRunner BE latch on every
    new position; `on_be_applied` sets the one-shot latch ONLY after the
    broker accepted the BE modify (v25 sets `g_beMoved` inside the
    successful `PositionModify` branch).
  - `EntryRequest.current_spread_price` — spread in PRICE units (e.g. 0.35
    on gold), NOT MT5 points; compared against
    `SPREAD_MAX_ATR × ATR × grade multiplier` (also price units). Convert
    `SYMBOL_SPREAD` points at the data boundary.
  - Closed-bar FVG contract: `PositionState.closed_close` is the CLOSE of
    the just-closed bar (v25 `iClose(..., 1)`); FVG structural invalidation
    consumes ONLY this field (never the live price); `None` skips the
    check. `PositionState.bar_index` is runner bookkeeping only.
  - State updates: `record_result(win, at)` (breaker), `record_sl_close(...)`
    (same-level), `record_failed_sweep(...)` (sweep guard), `reset_day()`
    (breaker + sweep + same-level daily rollover).
  - Types: `RiskAction` (HOLD/ENTER/MOVE_SL/EXIT), `EntryRequest`,
    `EntryDecision`, `PositionState`, `ExitDecision`.
- **Deferred / not ported (per the Risk Constants Lock):** Immediate Trail,
  fixed-dollar risk mode, fixed-lot fallback, dynamic SL buffers, PureRunner
  TP RR, Kalman filter. ADX gate + ATR floor are locked (§28.8) but
  conditionally ported — Phase 6 decides whether the core stack needs them.
- **Integration seams Phase 6 must respect:**
  - *FVG context capture:* `evaluate_exit` needs the `FvgContext` snapshotted
    at trade open — the trigger layer does not persist FVG boundaries yet, so
    the Phase 6 runner must capture it from the entry signal's `data` dict.
  - *Exit cadence:* v25 evaluates exits on closed bars only (bar index 1);
    the runner must define per-bar vs per-tick invocation of `evaluate_exit`.
  - *Daily rollover:* `reset_day()` must fire on UTC date change — the
    runner owns that clock edge (no MT5 in the risk layer).
  - *Slippage policy:* v25's `InpSlippage` (20) was deferred at constant-lock
    time — Phase 6 execution/backtest must decide acceptance bounds (the
    paper runner's slippage simulator is the natural home).
  - *News hard-cancel:* still not ported (listed under Must Be Built) —
    decide whether it lands in the Phase 6 runner or the risk engine.
  - *§7 inducement literals:* the value-identical constant refactor
    (`pillar_5_inducement.py` 1.0/0.7) remains open — Phase 6 hygiene
    candidate.

---

## Phase 4 Implementation Notes (V1 definitions — 2026-09-07)

- **Stage 3 lives in `smc/triggers/`:** `base_trigger.py` (`Trigger` ABC +
  `TriggerContext`/`TriggerSignal`), `trigger_a_choch` … `trigger_f_bos_ob`
  (the six triggers), `wave_structure.py` (deterministic V1 5-wave impulse
  extraction for B/C), `trigger_router.py`, `trigger_expiry.py` (§24 windows
  + §23 expiry anchors + POI give-up), `compatibility_matrix.py` (§15 grades).
- **Every trigger is a LIMIT entry** (Trigger D frozen at 50% of the
  engulfing body, §10) — no trigger emits a market order. `TriggerSignal`
  carries entry price, stop reference, completion index, expiry bars, and a
  `data` dict that is ALWAYS a real dict (never None) — consumers can rely on
  e.g. `signal.data["wave5_index"]`.
- **Routing is chronological first-valid (§12), frozen** — the router scans
  bar-by-bar from the POI's arm bar within the §24 give-up window (Trigger
  A's 20 M5 bars, V1). Same-bar tie-break (pinned post-audit): §15
  compatibility grade (PREFERRED > STRUCTURAL > UNCOMMON), then trigger
  letter with the EARLIER letter winning (A before F) — aligned across
  `TriggerRouter.evaluate_at` and `CompatibilityMatrix.eligible_triggers`;
  no frozen matrix cell is forbidden.
- **Stage 4 lives in `smc/execution/`:** `order_manager.py` (limit/market/
  cancel/modify via a connector; `OrderRequest`/`OrderResult`),
  `position_manager.py` (SL/TP modifies RE-SEND the current opposite
  protective price — post-audit, the cab_watcher `_modify_sl` pattern; a
  modify never zeroes the other field and unknown tickets raise),
  `news_guard.py` (§11 CPI/NFP/FOMC blackout), `session_filter.py` (§2
  gate), `lot_sizing.py` (`risk_lots` — internal formula behind the
  `sized_lots` policy; not a public sizing path).
- **`smc/orchestration/engine.py` — `PipelineEngine` is the Phase 4
  integration seam:** `merge` (Phase 2 overlap merge BEFORE validate),
  `validate` (Pillar 2 displacement injection; arm bar recorded per POI),
  `feed_bar` (per-bar §5 touch/violation events), `scan_route`
  (give-up-bounded chronological scan), `execute_route` (news + session
  gates → LIMIT order → `ExecutionOutcome`). `ExecutionOutcome` carries the
  typed `order_result: Optional[OrderResult]`.
- **Integration seams Phase 5 must respect:**
  - *Risk lot sizing:* `PipelineEngine.compute_risk_lots` goes through the
    Phase 5 policy layer (`smc.risk.lot_sizing.sized_lots` — §28.7 band
    clamp + `LOT_MAX_SAFETY` cap). There is NO public sizing path outside
    the band/cap; the raw `risk_lots` formula is an internal building block
    only (consumed by `sized_lots`).
  - *§23 order expiry:* unfilled-order expiry (M5=12 / M1=30) is owned by
    `POIStateMachine.expire_unfilled` (Phase 3) and the engine's arm-bar
    bookkeeping anchors the §24 give-up window — do not add a second expiry
    regime in the risk layer.
  - *News/session gates:* entry blocking (news + session) already lives in
    `execute_route`; risk-layer gates (sweep guard, spread grading, Friday
    EOD) should compose with, not bypass, those. A blocked outcome does NOT
    consume the POI's one-shot event identity — only an ACCEPTED execution
    attempt marks it fired (post-audit ruling), so a blocked route may be
    re-attempted once the gate clears.
  - *Injected clock:* `execute_route(..., now=...)` requires the caller to
    inject `now` (required keyword, no `datetime.now()` default) so
    backtests stay deterministic; `POI.created_at` is the only remaining
    wall-clock default (creation metadata, not a trading decision).
  - *v25_DIAG thresholds:* — **resolved in Phase 5:** formally locked as §28
    on 2026-09-07 (Same-Level = 0.15× ATR running default, not the outdated
    0.1 comment; ADX/ATR floor locked as optional gates). See
    `LOCKED_DECISIONS.md` §28 and `locked_constants.py`.
  - *Kalman/ADX/ATR-floor:* port only if still required after the core
    detection stack is proven (TODO Phase 5 note).
  - *§7 inducement literals:* **resolved (post-audit):**
    `pillar_5_inducement.py` and `validation_pipeline.py` now import and
    use `INDUCEMENT_WITH_SCORE` / `INDUCEMENT_WITHOUT_SCORE` from
    `locked_constants` — no bare 1.0/0.7 modifiers remain.

---

## Phase 3 Implementation Notes (V1 definitions — audit 2026-09-07)

- **Stage 2 lives in `smc/validation/`:** `pillar.py` (abstract `Pillar` +
  `PillarStatus` PASS/FAIL/UNAVAILABLE + `PillarResult` + `ValidationContext`),
  `pillar_1_zone_refinement` … `pillar_5_inducement`, `validation_pipeline.py`
  and `state_machine.py`. Pillars run 1→5; 1–4 are HARD gates, 5 (inducement)
  is SOFT (1.0/0.7 modifier, never rejects).
- **Pillar 3 is the SOLE owner of the §6 45%/55% hard reject** — it consumes
  `deal_range.classify_region`; `deal_range.py` only classifies regions.
- **UNAVAILABLE (pillars 1–4) rejects** — fail-fast, no silent accept; it is
  logged distinctly from FAIL via `PillarStatus`.
- **Pillar 2 input contract:** the caller injects the Phase 1
  `check_displacement` result (BOS + FVG + ≥1× ATR) for the POI's own sweep;
  absent ⇒ UNAVAILABLE. The detector→pipeline glue (Phase 4+ orchestration)
  must supply it — Phase 2 detectors do not yet persist sweep/BOS indices.
- **Pipeline effects on PASS:** POI armed CREATED→FRESH via `POIStateMachine`
  and §1 confluence `score_poi` assigned when `poi.score == 0.0`.
- **Pillar 4 is state-based at validation time**; per-bar first-touch
  (FRESH→TESTED), violation (FRESH→VIOLATED) and §23 unfilled-order expiry
  (M5=12 / M1=30 bars) run through `POIStateMachine` — atomic, terminal
  states immutable, `can_trade` = FRESH only.
- **No frozen numbers invented:** inducement uses only zone/price geometry
  (approach-side interval, strict); expiry reuses frozen M5=12/M1=30.
- **Integration seams Phase 4 must respect (Phase 3 independent audit
  2026-09-07):**
  - *Displacement injection (Pillar 2):* Phase 4 orchestration glue must
    persist each POI's sweep candle + prior-swing BOS level and inject the
    Phase 1 `check_displacement(...)` result per POI — otherwise Pillar 2 is
    UNAVAILABLE and the POI is rejected (no generic derivation inside the
    pillar; deliberate).
  - *Merge before validate:* run Phase 2 `merge_overlapping` on
    same-direction overlapping POIs BEFORE validation so Pillar 1's
    refinement scan and the §1 confluence score see every tag on the merged
    zone.
  - *Score assignment timing:* the pipeline assigns `score_poi` only on PASS
    and only when `poi.score == 0.0` (never overwrites a Phase 2 pre-score).
    Phase 4 must pick one scoring owner per POI lifecycle.
  - *M8 freshness:* M8 zones are NOT assumed fresh — the same §5 machine
    applies (armed on validation PASS like every model; first touch →
    TESTED). Do not special-case M8 in the trigger layer.
  - *Pillar 4 is state-based:* per-bar first-touch / violation / §23 expiry
    must be fed to `POIStateMachine` from the POI's creation bar onward.
    `POI` stores no creation-bar index (Phase 2) — add one if a
    pre-creation touch scan is required.
  - *§7 inducement literals:* `pillar_5_inducement.py` and the pipeline use
    literal modifiers 1.0 / 0.7 — values IDENTICAL to the frozen
    `INDUCEMENT_WITH_SCORE` / `INDUCEMENT_WITHOUT_SCORE` but not imported
    from `locked_constants`. A value-identical constant refactor is a
    candidate at Phase 4 kickoff (per the no-hardcoded-thresholds standard).
  - *Indicator defaults:* `atr_period=14` threaded through
    `ValidationContext` / `validate()` is an indicator parameter inherited
    from `smc.utils.atr` (not a frozen decision value).

---

## Phase 2 Implementation Notes (V1 definitions — audit 2026-09-07)

- **Stage 1 / 1b live in `smc/poi/`:** `base_model.py` (abstract `POIModel`
  + pure geometry helpers), `model_registry.py` (`build_registry(timeframe,
  htf_candles)` → M1–M8), `confluence_scorer.py`, `choch_classifier.py`,
  `deal_range.py`, and the 8 detectors under `smc/poi/models/m1–m8`.
  All 8 models are EQUAL tags (§1); overlapping same-direction POIs are
  merged by `confluence_scorer.merge_overlapping` (tag union, widest zone,
  earliest id) — no model suppresses another.
- **Quality score = independent tag count** (1 base / 2 elevated / 3+
  institutional) + M8 `+0.10` when `htf_overlap=True` (§26) — score-only,
  never position size.
- **CHOCH (Stage 1b):** Rule 1 = body close beyond the last §19-valid swing
  (highest), Rule 2 = body close beyond an intermediate (unconfirmed) level
  while the last swing holds (medium), Rule 3 = wick-only pierce (lowest —
  KEPT, no extra confluence gate). Entry level = broken level per rule
  (§9/§20). Bullish is classified via price inversion of the same bearish
  code path.
- **Dealing range:** most recent §19-valid swing high/low (window-extreme
  fallback). Region classification on frozen 0.45/0.55 bands. **Ownership
  boundary (audit 2026-09-07):** `deal_range.py` only CLASSIFIES the region
  (`DealRangeRegion` via `classify_region`); Phase 3 **Pillar 3 is the SOLE
  owner of the §6 45%/55% hard reject** (buy must be < 45% discount, sell
  > 55% premium, 45–55% = REJECT). Do not add a PASS/FAIL buy/sell gate to
  `deal_range.py` — enforce it in Pillar 3.
- **M8:** D1/H4 ONLY; emits OB (candle before first FVG candle), FVG, and
  §22 Demand/Supply zones = the single last opposing candle's FULL high-low
  range before a ≥1×ATR impulse. `htf_overlap=True` marks same-direction
  D1∩H4 price overlap. Step 1 (zone ID) only — no M5-approach/M1-trigger
  logic yet (later phases).
- **No frozen numbers invented:** bare-level ±0.5×ATR bands and the M5
  cluster full-wick zone are documented UNFROZEN V1 geometry choices (see
  CHANGELOG); do not treat as locked without authorization.
- **V1 simplifications / edge cases Phase 3 must be aware of (audit
  2026-09-07):**
  - **M4** evaluates three CONSECUTIVE swings (LS→neck→head must be adjacent
    in the swing list); a QML with intermediate minor swings between the
    left shoulder and the neck is not yet detected.
  - **M8** keeps only the MOST RECENT zone per (direction, kind) per
    timeframe, and its Demand/Supply scan is forward-looking (any opposing
    candle whose next `N_BAR_LTF` bars move ≥ 1×ATR) — equivalent to §22's
    backward-from-impulse rule for a single impulse.
  - **`merge_overlapping` is single-pass:** chain-overlapping zones
    (A∩B, B∩C but not A∩C) can still leave touching POIs in the output.
  - **CHOCH Rule 3** (wick-only) can reference the last main-trend swing OR
    an intermediate level (whichever the wick pierces without a body close),
    while §17's ranking table lists "intermediate level" — revisit only if
    Trigger A research logging disagrees.
  - **M5 may also tag reactive M7-style fixtures** when the two extremes
    fall within the frozen 4.5-pip tolerance — co-tagging is by design
    (§1 equal tags → confluence), not a defect.
  - **M3's Rule 1/2/3 sub-variants share a single equal M3 tag**; per-rule
    strength is exposed only via `ChochBreak.rule` for research logging.

---

## Phase 1 Implementation Notes (V1 definitions — audit 2026-09-06)

- **Displacement measurement (V1):** displacement is measured from the
  sweep extreme → BOS close, compared against the PRE-SWEEP Wilder ATR
  (bars strictly before the sweep candle, so the impulse never inflates
  its own reference). Thresholds themselves remain the frozen §3 values
  (min 1× ATR, hard fail < 0.5× ATR, preferred > 1.5× ATR).
- **Multi-label readiness:** the scanner intentionally returns multiple
  overlapping `LiquidityLevel` objects on the same price region (session
  high + EQH + structural swing can all sit at 104.10). Per §1 all models
  are equal tags — deduplication/confluence belongs to the Phase 2 POI
  layer, not the scanner. Confirmed by `test_liquidity_scanner.py`.
- **PDH/PDL semantics:** most recent completed *trading* day/week (calendar
  days with no candles — weekends — are skipped).
- **Swing validity is retroactive (§19):** a swing is structural only after
  a body close beyond its Base Candle's opposite extreme; unconfirmed
  candidates are returned with `is_valid=False`.

---

## Coding Standards

- Python 3.10+
- Type hints on all functions
- Dataclasses for all data structures
- Abstract base classes for extensible components (models, triggers, pillars)
- Single Responsibility: one class = one job
- Dependency Inversion: depend on abstractions, not concretions
- No hardcoded thresholds — all values from `locked_constants.py`
- Unit tests for every component (synthetic OHLCV data)
- Docstrings on all public methods

---

## How to Use TODO + CHANGELOG

### TODO.md
- Living task board
- Check off tasks as you complete them
- Update "Current Phase" at the top when moving to a new phase
- Add blocked items to "Blocked / Waiting" section
- Record completed tasks with date in "Completed" section

### CHANGELOG.md
- Every change to the project goes here
- Format: `[YYYY-MM-DD] - Session Title`
- Sections: Added, Changed, Fixed, Architecture Decisions
- Update `Last Updated` at the top

### SESSION_HANDOFF.md (this file)
- Update at the end of every session
- Ensure any new agent can pick up where you left off
- Keep it concise but complete

---

## Important Warnings / Do-Not-Repeat

| Warning | Source |
|---------|--------|
| Do NOT modify `LOCKED_DECISIONS.md` without explicit authorization | Frozen Rev 5 |
| Do NOT rebuild what v25_DIAG already does well — port it to Python | Re-use inventory |
| Do NOT create an HTTP bridge — Python connects directly to MT5 | Option A architecture |
| Do NOT hardcode thresholds in logic — always import from `locked_constants.py` | Design principles |
| Do NOT skip unit tests — every component must be testable with synthetic data | Design principles |
| Do NOT use market orders for Trigger D — limit at 50% of engulfing body only | LOCKED_DECISIONS §22 |
| Do NOT suppress any POI model — all 8 are equal tags, confluence adds quality | LOCKED_DECISIONS §1 |
| Do NOT change trigger routing order — chronological first-valid wins, frozen | LOCKED_DECISIONS §22 |
| Do NOT create separate `risk_simulator.py` — same Python code runs in backtest and live | Option A architecture |
| Do NOT port components back to MQL5 without measured evidence from paper trading KPIs | Future Flexibility Clause |

---

## Key Experiments & Results

| Experiment | Result | Implication |
|-----------|--------|-------------|
| SMC-R4 (BOS+OB) | Positive expectancy (1.01 gross bps) | BOS+OB has edge but needs refinement |
| SMC-R6 (M4 Qualification) | M4 FAILED | Quasimodo model not validated at economic level |
| SMC-R9 (CHOCH) | M3 FAILED (0.89 gross bps, -17.03 net bps) | CHOCH model not validated at economic level |
| SMC-R7 (Frequency Compression) | BOS+OB CLOSED | Frequency compression invalidates BOS+OB |
| SMC-R11 (Rare Events) | Framework established | Rare-event module governance in place |

**Key insight:** The programme is PAUSED. No automatic next experiment. Restart requires new scientific primitives governed by the qualification framework (R10) and rare-event framework (R11). These mixed/failed results are the reason we are now building the full modular system under frozen locked decisions instead of continuing isolated experiments.
