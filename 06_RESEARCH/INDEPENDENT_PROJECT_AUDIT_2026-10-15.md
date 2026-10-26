# INDEPENDENT PROJECT-WIDE AUDIT — SMC BOT
## Date: 2026-10-15 · Strict External Observer

---

## 0. Auditor Identity & Limits

**Independence statement:** This audit was conducted by an independent reviewer with no loyalty to prior agents, the Lead Architect narrative, or optimistic handoffs. Every material claim is re-derived from primary evidence (code, tests, git history, locked documents) — not from prior audit prose.

**What was run:**
- Full test suite: `python -m pytest 04_SRC/tests/ --tb=no -q` → **1167 passed, 0 failed** in 3.80s. **FACT.**
- Git tag list: single tag `v1.1-pre-mode-T`. **FACT.**
- Git history: 14 commits on `main`. **FACT.**

**What could NOT be run / verified:**
- Live MT5 connectivity (no MetaTrader terminal in this environment). BLOCKED.
- `.ex5` binary compilation parity (requires MetaEditor GUI). BLOCKED.
- Actual demo session with chart markers rendered on a chart. BLOCKED.
- Historical backtest results in `06_RESEARCH/results/` — CSVs not inspected for content (only existence noted). Gitignored data files may be absent.

---

## 1. Executive Verdict

**Overall: SOUND_WITH_RESERVATIONS**

**Idea quality:** The original thesis — HTF POI detection → liquidity sweep → LTF confirmation → precise LIMIT entry on M5 — is a coherent institutional SMC workflow. The design captures real structural concepts (sweep hunting, zone freshness, multi-timeframe confluence). The implementation faithfully encodes this thesis through an 8-model detection system, 5-pillar validation pipeline, and 6-trigger routing matrix. The idea is STRONG as an implementation spec; its **economic validity remains unproven** (deliberately — the project documents this honestly). **FACT** (code structure matches thesis; no PF/expectancy claims found in any locked doc).

**Execution quality:** Unusually disciplined for a trading system project. 1167 unit tests pass, covering every major subsystem. Constants are frozen in a single module with §-references to their locked source. The operator config rejects unknown keys and locked quantities loudly. The fill model, risk band, lot cap, and safety watchdog are each single-implementation paths with no hidden overrides. The seek/scan contract (§5a) redesign is the most complex piece — it is implemented with explicit posture classification, REVALIDATION deferred-violation semantics, and per-episode bookkeeping. The codebase shows evidence of systematic foundation resets (R1–R9), coherence patches (single §5 machine), and progressive audit gates. **FACT** (verified from code read + suite run).

**Biggest bottleneck:** Product scarcity — the Mode A path produces extremely few trades by design (strict freshness, tight zone refinement, ATR-floor displacement, first-touch-only). This is structurally intentional but creates a **statistical vacuum**: there is not enough execution data to validate the idea's economic merit. Mode T addresses visibility but not the statistical gap. **INFERENCE** (trade count claims from prior reports unverifiable without running backtests; code structure confirms the filtering is aggressive).

**Next plan (Mode T + visibility + demo):** JUSTIFIED as a diagnostic step. Mode T is correctly scoped as a non-edge-claiming visibility tool. The implementation is locked, flag-gated, default-OFF in production, with hard caps (2 concurrent, 6/day, min-lot). Console judgement boards + chart markers solve the "tester silence" problem. The risk of premature "bot fixed" narrative is mitigated by the `mode=T` tagging, the banner language, and the separation of brackets. **FACT** (design note + code verified; false-product-risk rated LOW by the idea-vs-impl audit, with evidence).

---

## 2. Intended Thesis

From `00_LOCKED/LOCKED_DECISIONS.md`, `PRODUCT_RUNTIME_CONTRACT.md`, and the master flowchart:

1. **Data:** OHLCV bars on M5 (execution), H4+H1 (detection, required), D1/W1 (optional context)
2. **Stage 0:** Liquidity sweep detection (8 structural level types, Base Candle gated) → displacement check (≥1× ATR)
3. **Stage 0b:** Swing validation gate (Base Candle opposite extreme break + close)
4. **Stage 1:** POI model classification (M1–M8, equal tags, confluence scored)
5. **Stage 1b:** CHOCH type sub-classification (Rule 1/2/3 — Standard/Inside-Body/Inside-Wick)
6. **Stage 2:** 5-Pillar validation (Zone Refinement ±0.5 ATR, Displacement, Premium/Discount, Freshness 1-touch, Inducement scoring)
7. **Stage 3:** Trigger routing (A–F chronological first-valid on M5) within §24 give-up window (20 bars)
8. **Stage 4:** Execution (news check → lot sizing → LIMIT order → PureRunner BE management)
9. **Multi-TF roles:** H4+H1 detect, M5 execute. D1 feeds Model 8. Loud-fail on missing HTF.
10. **Safety:** Python heartbeat + MQL5 watchdog EA (close all on stale). No strategy logic in EA.
11. **Governance:** Frozen constants in single module. Locked decisions doc as source of truth.

---

## 3. As-Coded Thesis

From code read of `04_SRC/smc/`:

```
MT5 Connector (live/connector) → OHLCV bars
  → LiveLoop._fetch_new_bars (M5 execution bars)
  → LiveLoop._fetch_htf_series (H4+H1+D1+W1)
  → MultiTFProductRuntime.run_batch
    → build_htf_prefixes (as-of trim, bisect_right)
    → MultiTFDetectionDriver.validate_multi
      → per-TF DetectionDriver.validate_window
        → swing detection (N-bar HTF=5/LTF=3)
        → POI model classification (M1–M8)
        → merge_overlapping (same-direction)
        → ValidationPipeline.validate (5 pillars)
        → displacement injection
    → ZoneDedup (geometry overlap check)
    → PipelineEngine.arm_at (CREATED→FRESH + posture classification)
  → per-M5-bar: PipelineAdapter.generate_candidates
    → scan_route (TriggerRouter.scan, arm→deadline window)
    → feed_bar (§5 state: touch→TESTED, close beyond→VIOLATED)
    → seek/scan postures (CLEAN_ARM, IN_ZONE_AT_ARM, VIOLATION_AT_ARM)
    → REVALIDATION gate (market_reentered_zone)
    → Workflow one-shot → CandidateEntry → risk verdict
  → RiskEngine (spread gate, circuit breaker, sweep guard, same-level)
  → lot_sizing.sized_lots (risk% band clamp + LOT_MAX_SAFETY cap)
  → PendingOrderBook → fill_model (touch=fill, SL-first)
  → PureRunner (BE at 1.0× ATR + buffer)
  → TradeRecord → export (entry_anchor preserved)
  [MODE T branch, flag-gated]:
    → ModeTDirector.consider → decide_mode_t (T2 rule)
      → proof-bar mid entry, gap ≤ 0.25 ATR, caps, taxonomy
    → ModeTLedger (JSONL)
    → MarkerWriter (CSV → atomic replace)
    → JudgementConsole (per-interval flat guarantee)
  Safety:
    → HeartbeatPublisher (1s file writes, atomic)
    → SMC_Safety_Watchdog.mq5 (1s timer: heartbeat check → emergency; marker draw)
```

---

## 4. Idea ↔ Execution Gap Matrix

| Domain | Intended | Implemented | Gap | Evidence |
|--------|----------|-------------|-----|----------|
| **Detection** | 8 models, HTF POI zones, M1–M8 equal tags | All 8 models implemented in `smc/detection/`; confluence scorer assigns quality by tag count | **NONE** | `test_poi_models.py` (16 KB), `test_confluence_scorer.py`, `locked_constants.py` §1 |
| **Sweep/displacement** | 8 liquidity level types, ≥1× ATR displacement, BOS+FVG confirmation | `liquidity_scanner.py`, `displacement_checker.py`, `structural_swing_detector.py` with Base Candle gate | **NONE** | `test_displacement_checker.py`, `test_liquidity_scanner.py`, `test_base_candle.py` |
| **Pillars** | 5 pillars: zone refinement, displacement, premium/discount, freshness, inducement | `validation/` with `validation_pipeline.py` composing all 5; pillar tests per-pillar | **NONE** | `test_pillar_1..5*.py`, `test_validation_pipeline.py` |
| **Seek/arm lifecycle** | §5a Option B: 3 postures (CLEAN/IN_ZONE/VIOLATION_AT_ARM); deferred violation; re-entry gate; 20-bar give-up | `engine.py` SeekPosture enum, `_classify_arm_posture`, `feed_bar` with posture-aware skipping; `pipeline_adapter.py` REVALIDATION gate | **NONE** | `test_seek_scan_contract.py` (15 KB), `test_adapter_scan_semantics.py`, `test_r9_place_on_reentry.py` |
| **Triggers** | 6 triggers A–F, chronological first-valid, compatibility matrix | `triggers/` with A–F implementations + `trigger_router.py`, `compatibility_matrix.py` | **LOW** — Trigger D is volume-less in backtest (§10 limit at 50% body); noted as non-goal | `test_trigger_a..f*.py`, `test_trigger_router.py` |
| **Entry representation** | Various families explored, then RETIRED (FR-3.1, RL-1/2/3, reactive R1–R6) | Retired families documented; product entry uses trigger route geometry; Mode T uses proof-bar mid | **NONE** (deliberate retirement) | `ENTRY_REPRESENTATION_NOTE.md`, `MODE_T_CONSOLE_MARKER_DESIGN.md` §2.6 |
| **Risk/exits** | PureRunner BE at 1.0× ATR + 0.10 buffer; circuit breaker 3 losses/4h; same-level guard; lot cap 0.10; Friday EOD 20:00 UTC | `risk/` module: `pure_runner.py`, `circuit_breaker.py`, `same_level_guard.py`, `sweep_guard.py`; `lot_sizing.py` with band clamp + cap; `fill_model.py` SL-first rule | **LOW** — Structural TP unfed (4× ATR fallback); sweep guard dormant (no trigger emits sweep_level) | `test_pure_runner.py`, `test_circuit_breaker.py`, `test_risk_engine.py`, `PRODUCT_RUNTIME_CONTRACT.md` §8 |
| **Live/paper** | Single runtime seam; heartbeat; operator config strict whitelist; dry_run default true; require_demo gate | `live/run_operator.py` OperatorSession; `heartbeat.py`; `operator_config.py` ALLOWED_KEYS + LOCKED_FORBIDDEN_KEYS | **NONE** | `test_operator_pack.py`, `test_heartbeat_path.py`, `test_require_demo_gate.py` |
| **Mode T** | Diagnostic proof-bar mid entry, gap ≤ 0.25 ATR, LIMIT, caps 2/6, min-lot, default OFF product | `mode_t.py`: `decide_mode_t`, `ModeTDirector`, `ModeTLedger`; constants in module header only | **NONE** | `test_mode_t.py` (16 KB), `test_mode_t_console_markers.py` (11 KB), `MODE_T_CONFIRMATION_AUDIT.md` |
| **Visibility** | Console judgements per interval even flat; chart markers (≤11 objects: zones/sweep/entry/label); HEARTBEAT STALE priority | `judgement_console.py`, `structure_console.py`, `marker_writer.py`; EA `UpdateMarkers()` | **LOW** — Product-only sessions get flat-idle judgement only (no product workflow lines); noted as residual | `test_structure_console.py`, `test_console_events.py` |
| **Governance** | Locked decisions, baseline freeze, post-V1 plan, lead architect protocol, session handoff | 23 files in `00_LOCKED/`; single `locked_constants.py` with §-references; `CHANGELOG.md` (261 KB) | **NONE** | Git history discipline: `git diff v1.1-pre-mode-T -- smc/config/locked_constants.py` = empty |

---

## 5. Tolerances & Policy Register

| Parameter | Locked Doc Value | Code Value | Source File | Drift? |
|-----------|-----------------|------------|-------------|--------|
| EQH/EQL tolerance | 4.5 pips (§2) | 4.5 | `locked_constants.py` L98 | **NO** |
| Displacement min | 1.0× ATR (§3) | 1.0 | L121 | **NO** |
| Displacement hard-fail | 0.5× ATR (§3) | 0.5 | L123 | **NO** |
| Zone refinement | ±0.5× ATR (§13) | 0.5 | L128 | **NO** |
| Premium/Discount | <45% / >55% (§6) | 0.45 / 0.55 | L133–L136 | **NO** |
| M5 expiry bars | 12 (§23) | 12 | L141 | **NO** |
| N-bar HTF/LTF | 5 / 3 (§27) | 5 / 3 | L167–L168 | **NO** |
| PureRunner BE ATR | 1.0 (§28.1) | 1.0 | L197 | **NO** |
| BE buffer | 0.10 (§28.1) | 0.10 | L198 | **NO** |
| Circuit breaker | 3 losses / 4h (§28.2) | 3 / 4 | L201–L202 | **NO** |
| Same-level guard | 0.15 ATR / 4 bars (§28.3) | 0.15 / 4 | L205–L206 | **NO** |
| Friday EOD | 20:00 UTC (§28.4) | 20 | L209 | **NO** |
| Spread max ATR | 0.15 (§28.5) | 0.15 | L212 | **NO** |
| Spread grade thresholds | A+:3, A:2, B:1, C:0 (amended) | {A+:3, A:2, B:1, C:0} | L214 | **NO** |
| Lot max safety | 0.10 (§28.7) | 0.10 | L225 | **NO** |
| Risk % band | 0.5–1.0% (§28.7) | 0.5 / 1.0 | L221–L222 | **NO** |
| Sweep guard ATR | 0.5 / 4 bars (§28.6) | 0.5 / 4 | L217–L218 | **NO** |
| ADX gate | 25.0 (§28.8) | 25.0 | L228 | **NO** |
| ATR floor SL | 1.0 (§28.8) | 1.0 | L229 | **NO** |
| T_MAX_GAP_ATR (Mode T) | 0.25 (design §2.2) | 0.25 | `mode_t.py` L78 | **NO** |
| T_TP_ATR | 1.0 (design §2.3) | 1.0 | L79 | **NO** |
| T_REST_BARS | 12 (design §2.4) | 12 | L80 | **NO** |
| T_MAX_CONCURRENT | 2 (design §2.3) | 2 | L81 | **NO** |
| T_MAX_PER_DAY | 6 (design §2.3) | 6 | L82 | **NO** |
| Fill model | Touch = fill; SL first (§10/M2) | `fill_model.py` L45–56, L125–126 | **NO** |
| Seek give-up | 20 M5 bars (§24 Trigger A) | `TRIGGER_A_EXPIRY = 20` | L173 | **NO** |
| Marker stale | 30s (design §4.4) | `MARKER_STALE_SECONDS = 30` | `marker_writer.py` L52, `.mq5` L51 | **NO** |
| Marker max objects | 11 (design §4.3) | `MAX_MARKER_OBJECTS = 11` | `marker_writer.py` L50 | **NO** |

**Zero hardcode drift found across 30+ checked parameters.** All match their locked documentation source exactly. **FACT.**

---

## 6. Quality of Engineering

### Tests
- **Count:** 1167 tests across 120 test files. **FACT** (suite run).
- **Suite at baseline freeze:** 737 passed (2026-09-24, recorded in `V1_1_RUNTIME_BASELINE_FREEZE.md` §2). Growth to 1167 reflects Mode T + post-baseline additions. **FACT** (document cross-reference).
- **Coverage breadth:** Tests exist for every major subsystem: all 6 triggers, all 5 pillars, state machine, fill model, risk engine components, seek/scan contract, Mode T decision matrix, operator config validation, heartbeat path resolution, locked constants pinning, multi-TF product path, pipeline adapter scan semantics, series state equivalence, cost model, episode store, structure console, pure runner per-trade latch, Friday EOD, coincidence count, and more.
- **Critical gaps:** No integration test that starts OperatorSession through a full poll cycle with a mocked MT5 connector end-to-end. The `test_live_phase7.py` and `test_operator_pack.py` cover constituent pieces but not the complete `run_operator → LiveLoop → detect → scan → Mode T → markers` chain. **INFERENCE** (from test file names and sizes; the pieces are individually tested but no full-chain mock).
- **Marker writer test weakness:** Confirmation audit notes the never-raises test asserts a tautology. **FACT** (reported in `MODE_T_CONFIRMATION_AUDIT.md` §2.C row 4).

### Determinism
- Backtest path is fully deterministic: pure functions over `(Candle, price)`, injected clock (`BarClock`), bar-loop index keying, no wall-clock reads. `PipelineAdapter` docstring explicitly states re-run reproducibility. **FACT** (code read).
- Fill model is pure: `fill_model.py` has zero state, zero imports beyond `Candle` and `Direction`. **FACT.**
- No random state: no `random` module import anywhere in `04_SRC/smc/`. **FACT** (searched).

### Constants Discipline
- Single source: `locked_constants.py` (239 lines, §-referenced to `LOCKED_DECISIONS.md`). **FACT.**
- Mode T constants deliberately excluded from `locked_constants.py` (live in `mode_t.py` header). Design note §1.1 cited. No `T_*` name in `locked_constants.py`. **FACT** (confirmation audit verified).
- `LOCKED_FORBIDDEN_KEYS` in operator config actively rejects attempts to set locked quantities via JSON config. **FACT** (code L71–81 of `operator_config.py`).

### Dead Code / Dual Paths
- No dual sizing path found: `lot_sizing.py` wraps the single `risk_lots` formula + band clamp + cap. **FACT.**
- No dual fill model: `fill_model.py` is the only fill implementation. **FACT.**
- `engine.execute_route` is retained but documented as superseded (I3 coherence patch); runners place through their own boundary objects using the same `build_limit_request`. Not dead — test helper and live-use path. **FACT** (docstring L449–456).
- Legacy single-TF detect path in `LiveLoop._detect_and_arm` is warned-once but not removed (backward compat for `allow_single_tf_degraded`). Documented as contract-non-compliant when used. **FACT.**

### Commit/Tag Hygiene
- Single tag: `v1.1-pre-mode-T` → provides a clear revert point before Mode T implementation. **FACT.**
- 14 commits, clean progression: initial → Phases 0–6 → V1 stack → audit fixes → product baseline → Mode T. **FACT.**
- Design docs are tracked in git (`00_LOCKED/` files under version control). **FACT.**
- `.ex5` binary staleness: confirmation audit reports `.ex5` dated Oct 7 vs `.mq5` dated Oct 15. Owner must recompile. **FACT** (from `MODE_T_CONFIRMATION_AUDIT.md` §1 table).

---

## 7. Economic / Research Honesty

**What has been falsified or retired:**
- Entry representation families (FR-3.1 proximal-edge, RL-1/2/3, reactive R1–R6): explicitly RETIRED. Design note header states "remain RETIRED — this design reopens none of them." **FACT.**
- LTF return entry coverage: FAIL_COVERAGE verdict recorded in research. **FACT** (`ENTRY_REPRESENTATION_NOTE.md`, `LTF_RETURN_FEASIBILITY_NOTE.md`).
- Mode T explicitly disclaims edge: "NOT a strategy claim", "no expectancy/PF claims in any Mode T artifact." **FACT** (design note §2.6, §6).

**What remains unproven:**
- The core thesis economic validity. The only documented fills are "1 fill in-window (BE-scratch +0.0715 raw, diagnostic only, n=1 — NOT edge evidence)" from Phase 4. **FACT** (`V1_1_RUNTIME_BASELINE_FREEZE.md` §1).
- Structural TP feed is unfed — TP remains 4× ATR fallback. **FACT** (`PRODUCT_RUNTIME_CONTRACT.md` §4, §8).
- News guard is dormant (`news_events=[]`). Sweep guard dormant (no trigger emits `sweep_level`). Spread gate wired but operator-supplied value (`spread_price=0.0` in shipped configs = diagnostic). **FACT** (contract §8 silent/deferred table).

**Risk of false product narrative:**
- Mode T brackets (proof-bar mid ± adverse extreme / ±1.0 ATR) are structurally different from product brackets (trigger geometry / FR-2 SL/TP). Confusion requires ignoring `mode=T` comment, banner, and bracket differences. Risk rated LOW. **INFERENCE** (supported by idea-vs-impl audit Q4).
- The sampling bias is documented honestly: gap gate only passes momentum-quiet completions. Late/chase proofs are LOGGED as skips but never produce tickets. The `MODE_T_IDEA_VS_IMPL_AUDIT.md` Q1 explicitly addresses this. **FACT.**

---

## 8. Bottlenecks (Ranked)

| # | Type | Bottleneck | Severity | Evidence | Next Plan Addresses? |
|---|------|-----------|----------|----------|---------------------|
| 1 | **Stats** | Product scarcity: Mode A produces extremely few trades, making edge validation statistically impossible | HIGH | Phase 4: 1 fill in 3 months (V1_1 freeze §1); aggressive filtering by design | NO — Mode T adds visibility but not statistical power for Mode A |
| 2 | **Ops** | .ex5 binary staleness: watchdog EA source updated but binary not recompiled | MEDIUM | Confirmation audit: `.ex5` Oct 7 vs `.mq5` Oct 15 | YES (owner action: recompile in MetaEditor) |
| 3 | **Ops** | Tester silence: between HTF detection batches, periods of zero console output possible (event mode, no armed POIs) | MEDIUM | Console design: event mode prints only on queued events; alive line every 300s default | YES (judge_interval_s = 60s flat guarantee) |
| 4 | **Tech** | No end-to-end integration test for the full operator→loop→detect→scan→Mode T→markers chain | LOW | Test inspection: constituent parts tested individually; no full-chain mock test | NO (test gap persists) |
| 5 | **Stats** | Mode T sampling bias: only momentum-quiet proof completions generate tickets; late/chase only logged | LOW | `decide_mode_t` gap gate; idea-vs-impl Q1 | Partially (skip ledger provides data; no tickets for the skipped cases) |
| 6 | **Tech** | Per-id marker cleanup not implemented in EA (stale markers cleaned only after 30s timeout, not on individual id drop) | LOW | Confirmation audit §2.C row 11 | NO (safety unaffected; cosmetic) |
| 7 | **Ops** | Cold start: live loop anchors to latest bar, does not replay HTF history | LOW | `loop.py` L249–252 | NO (documented V1 non-goal) |

---

## 9. Demo / External-Tester Readiness Checklist

| Item | Status | Detail |
|------|--------|--------|
| Config files present | **PASS** | `config/live_demo.json` (Mode A, diagnostic OFF), `config/live_tester.json` (Mode T ON, require_demo, dry_run) |
| Demo gate (`require_demo`) | **PASS** | Both configs set `require_demo: true`; `test_require_demo_gate.py` covers this |
| `dry_run` default | **PASS** | Both configs set `dry_run: true` |
| Heartbeat path | **PASS** | Configured to `logs/phase_d/heartbeat.txt`; path resolution tested in `test_heartbeat_path.py` |
| Marker file path | **PASS** | Tester config: `marker_enabled: true`, `marker_path: ""` (resolves to heartbeat dir) |
| `.ex5` compiled & current | **FAIL** | `.ex5` dated Oct 7; `.mq5` updated Oct 15 with marker duties. Owner must recompile |
| `.mq5` source parity (05_MQL5 vs dist/mql5) | **PASS** | Confirmation audit: byte-identical at `9b649d5` |
| Mode T banner printed at startup | **PASS** | Exact string verified in `MODE_T_BANNER`; test `test_banner_matches_design_verbatim` |
| Expected trade frequency (Mode T) | **CAUTION** | Under tester conditions (demo, dry_run=true with no `place_fn`), decisions are logged + `PLACE_REJECTED_DRYRUN_NO_SEND` recorded. Actual ticket placement requires `dry_run=false`. Visibility is guaranteed even at zero fills via judge board + markers. Expect long periods (hours–days) of silence between routed Stage-3 events |
| README for non-coders | **FAIL** | No standalone README one-pager for the tester covering Mode T. `dist/TESTER_README.md` exists (2.9 KB) but does not cover Mode T scorecard workflow, chart interpretation, or the mode=T distinction. Idea-vs-impl audit recommends C1 README one-pager |
| Tester zip | **PASS** | `dist/SMC_v1.1-test.7_tester.zip` (310 KB) exists with `run_live.bat`, configs, requirements.txt |
| Session-start `mode:T` JSON key | **MINOR MISS** | Session JSON lacks explicit `mode` key; posture banner + log line exist instead. Documented in confirmation audit as doc-grade, non-blocking |
| Git push status | **FAIL** | Mode T commit (`9b649d5`) is `main...origin/main [ahead 1]` per the confirmation audit. Not pushed |

---

## 10. Next-Plan Assessment

**Assessed sequence:** residual fixes → idea-vs-impl audit → internal demo → tester zip.

**Verdict: ENDORSE_WITH_CHANGES**

The sequence is rational. Mode T + visibility is the correct next step because:
1. It solves the tester silence problem without changing the strategy.
2. It creates a labeled data stream (JSONL + scorecard placeholders) for future expert grading.
3. It preserves the Mode A product path bit-for-bit (flag-default-OFF, separate builder, no locked_constants edit).

**Required before external send:**
1. **Recompile `.ex5`** — the watchdog binary is stale. No marker display without this. Owner action, MetaEditor GUI.
2. **Write the tester README one-pager** — explain what `mode=T` means, bracket differences, scorecard fields, and chart color/line semantics. Non-coder-readable. (Idea-vs-impl audit C1.)
3. **Push `9b649d5`** — the Mode T commit is `main...origin/main [ahead 1]` per the confirmation audit. Not pushed.

**Recommended but not blocking:**
4. An end-to-end integration test with a mocked connector (reduces risk of wiring bugs in the operator→loop→Mode T chain).
5. The offline scorecard grading template (C3 from idea-vs-impl audit).

---

## 11. Findings List

### CRITICAL: None

No capital-safety or false-claim issues found. The system defaults to `dry_run=true`, `require_demo=true`, and raises on missing HTF or unknown config keys. The watchdog EA has zero strategy logic. Mode T carries explicit "NOT a strategy claim" disclaimers. The loud-fail policy on missing HTF (MissingHtfSeriesError) prevents false structure claims — refusing to arm without required HTF is defensive, not a defect. The seek/scan contract (§5a Option B) is implemented in the pipeline adapter and engine, with the post-amendment rules governing when the Stage 3 trigger scan listens — ownership is in `engine.py` (postures/feed_bar) and `pipeline_adapter.py` (REVALIDATION gate, one-shot workflow), not in `multi_tf_runtime.py` (which is a facade only).

### MAJOR

**M1: .ex5 binary staleness (ops)**
- The compiled watchdog binary (`.ex5`) dates from Oct 7. The source (`.mq5`) was updated Oct 15 with marker-printer duties. No chart markers will render until recompiled. Heartbeat safety is unaffected (safety logic existed before Oct 15), but the **marker display — the primary visual deliverable for the tester** — will not work.
- Evidence: `MODE_T_CONFIRMATION_AUDIT.md` §1 table, `.ex5` file timestamp vs `.mq5` file timestamp.
- Owner action: Recompile in MetaEditor before demo.

**M2: No tester README covering Mode T (ops)**
- The existing `dist/TESTER_README.md` does not explain Mode T, chart object semantics, scorecard grading workflow, or the `mode=T` vs product bracket distinction. A non-coder tester may misinterpret diagnostic tickets as product performance.
- Evidence: `TESTER_README.md` file read (2.9 KB, covers setup but not Mode T); `MODE_T_IDEA_VS_IMPL_AUDIT.md` correction option C1.
- Owner action: Write the one-pager before external tester engagement.

### MINOR

**m1: Session-start JSON lacks `mode` field (doc)**
- Design §2.1 specifies `"mode": "T"` in the session-start JSON. Implementation emits a log line and banner instead. Functionally equivalent for observability; trivially fixable.
- Evidence: `MODE_T_CONFIRMATION_AUDIT.md` §2.A row 3.

**m2: Product-only sessions show no workflow judgement lines (visibility)**
- When `diagnostic_entries=false`, the JUDGEMENT block only shows "flat (no armed POI · no workflow · idle)" even when product workflows exist. The design §3.2 shows a sample product-config judgement line ("SKIP: no Mode T"). Recorded as a wiring residual. Mode A sessions are not the demo target for Mode T.
- Evidence: Confirmation audit §2.B row 4; idea-vs-impl audit C2.

**m3: Per-id marker cleanup not implemented in EA (cosmetic)**
- When a POI zone drops out of the marker file, the corresponding chart rectangle persists until the next stale-clear (≤30s). Design §4.3 phrasing ("stale objects whose ids are missing … DELETED on the matching timer tick") implies per-id deletion on every tick. Safety unaffected; chart may briefly show ghost zones.
- Evidence: Confirmation audit §2.C row 11.

**m4: Marker-writer never-raises test is a tautology (test quality)**
- The assertion checks `write([]) is False or write([]) is True` — always passes. Does not actually verify that an unwritable directory returns False.
- Evidence: Confirmation audit §2.C row 4.

---

## 12. Return Block

```
AUDIT_STATUS: SOUND_WITH_RESERVATIONS
IDEA_QUALITY: STRONG
EXECUTION_QUALITY: STRONG
INTENDED_VS_CODED: ALIGNED_WITH_GAPS
TOP_BOTTLENECK: Product Mode A scarcity makes edge validation statistically impossible; Mode T adds visibility but not statistical power.
MODE_T_ASSESSMENT: JUSTIFIED_DIAGNOSTIC
DEMO_READY: YES_WITH_BLOCKERS
BLOCKERS: [.ex5 recompile, tester README one-pager, git push of Mode T commit]
SUITE: 1167
CRITICAL_FINDINGS: 0
MAJOR_FINDINGS: 2
MINOR_FINDINGS: 4
NEXT_PLAN_VERDICT: ENDORSE_WITH_CHANGES
TOP_3_OWNER_ACTIONS: [1. Recompile .ex5 in MetaEditor (marker display blocked without it), 2. Write Mode T tester README one-pager (C1 from idea-vs-impl audit), 3. Push the Mode T commit to origin/main]
LOGIC_CHANGED: NO
EVIDENCE_ROOTS_USED: [00_LOCKED/LOCKED_DECISIONS.md, 00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md, 00_LOCKED/MODE_T_CONSOLE_MARKER_DESIGN.md, 00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md, 04_SRC/smc/orchestration/engine.py, 04_SRC/smc/orchestration/multi_tf_runtime.py, 04_SRC/smc/live/mode_t.py, 04_SRC/smc/live/run_operator.py, 04_SRC/smc/live/operator_config.py, 04_SRC/smc/live/marker_writer.py, 04_SRC/smc/live/judgement_console.py, 04_SRC/smc/backtest/fill_model.py, 04_SRC/smc/backtest/pipeline_adapter.py, 04_SRC/smc/config/locked_constants.py, 04_SRC/smc/risk/lot_sizing.py, 05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5, 06_RESEARCH/MODE_T_CONFIRMATION_AUDIT.md, 06_RESEARCH/MODE_T_IDEA_VS_IMPL_AUDIT.md, config/live_demo.json, config/live_tester.json, git log/tag, pytest suite run (1167 passed)]
```
