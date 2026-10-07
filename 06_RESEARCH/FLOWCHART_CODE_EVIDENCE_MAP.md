# FLOWCHART ↔ IMPLEMENTATION CODE EVIDENCE MAP

**Status:** FINAL 2026-09-20 · documentation + code-path tracing only. No strategy changes, no locked-constant edits, no live gates promoted.
**Intended process:** `LOCKED_DECISIONS.md` §16 (5-stage master flowchart) + §2 (Stage 0A) + R1 model/trigger specs (`SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md`).
**Code base:** `04_SRC/smc/` tree verified on disk this session (module lists below are observed, not recalled).
**Evidence:** Phase C baseline (761 trades) + Track R (R1–R5) + export patches + V1 inspector + match/stratified/timing/stop-structure notes + Phase D ops.

---

## 1. End-to-end intended pipeline (locked §16)

levels → sweep → displacement → POI/models → pillars → triggers → risk → management, staged as: **0** Liquidity Sweep + Displacement → **0b** Swing Validation Gate (Base Candle) → **1** POI Models M1–M8 (equal tags, confluence) → **1b** CHOCH Rules 1/2/3 → **2** five Pillars → **3** Trigger routing (chronological first-valid, M1/M5) → **4** Execution (news → sizing → limit → PureRunner) + trade management (BE, FVG invalidation, breaker, guards, Friday EOD).

## 2. Code map table

| Flowchart/KB node | Code module(s) | Impl? | Evidence in trades/kills | Notes |
|---|---|---|---|---|
| Session/periodic/EQH levels | `detection/{session_levels,periodic_levels,eqh_eql_detector,liquidity_scanner}.py` | YES | Sweeps fire; session gating verified (0 off-session entries) | — |
| Sweep detection | `detection/sweep_detector.py` | YES | Wick-sweep confirmed on charts (L1, B-shelf cases) | — |
| Displacement (BOS+FVG+1×ATR) | `detection/{displacement_checker,fvg_detector}.py` | YES | R4: magnitudes recorded; FVG absence kills 91% of P2 kills; BOS present in 78% | FVG is the binding sub-constraint |
| Base Candle + swing gate | `detection/{base_candle,structural_swing_detector,swing_validator}.py` | YES | Structural swings gated; two-bar-reversal trap honored | — |
| POI models M1–M8 | `poi/models/m1–m8_*.py` + `base_model` + `model_registry` | YES | All 8 emit (R4 kill tags; Phase B armed mix) | M8 registers but emits nothing without HTF feed (see §4) |
| Confluence scoring | `poi/confluence_scorer.py` | YES | Tag-count scores flow to spread gate + exports | Score scale vs spread-grade thresholds is an audited bug (open ruling §4) |
| Dealing range | `poi/deal_range.py` | YES | P/D pillar enforces 45/55 bands | — |
| CHOCH Rules 1/2/3 | `poi/choch_classifier.py` + `m3_choch_retest` | YES | Rule variants classified; M3-pattern flow thin end-to-end (R4 kills M3=1) | Distinct from Trigger A (CHOCH *trigger* fired 29× in Phase C) |
| Pillars 1–5 + state machine | `validation/{validation_pipeline,pillar_1–5,state_machine}.py` (+ `window_cache` perf) | YES | P2 dominates kills (76% per-bar / 74% batch); pass 15–17% both modes | Freshness/expiry/invalidation paths verified in Phase B invariants |
| Trigger router (chronological) | `triggers/{trigger_router,compatibility_matrix,trigger_expiry}.py` | YES | First-valid wins per design; §15 matrix as tie-break only | Same-bar tie-break A-first is a pinned post-audit rule |
| Triggers A/B/C/E/F | `trigger_{a,b,c,e,f}_*.py` + `wave_structure.py` | YES | F 659 / B 70 / A 29 / E 2 / C 1 (Phase C) | B/C wave extraction is deterministic-V1 code for a discretionary concept |
| Trigger D (two-bar + volume) | `trigger_d_two_bar.py` | PARTIAL | 0 fires — compiled but structurally unfireable on volume-less data (A5 ruling) | Code complete; data absent |
| Risk engine + gates | `risk/{risk_engine,circuit_breaker,same_level_guard,friday_eod,sweep_guard,spread_grading,lot_sizing}.py` | YES | Breaker blocks (266 Phase C); Friday closes 7; spread gate regime law measured live | News gate dormant (empty calendar); ADX/Kalman/ATR-floor gates ABSENT by deferred decision (no such modules) |
| PureRunner BE + FVG invalidation | `risk/{pure_runner,fvg_invalidation}.py` | YES | 187 BE scratches banked as designed; FVG exits on closed-bar rule | BE latch per-trade fix (Phase B) proven |
| Execution (orders/positions) | `execution/` + `backtest/{runner,orders,positions,fill_model}` | YES | Limit fills at price; SL-first same-bar; deterministic dual-run byte-identity | Conservative fill model understates volatile-bar outcomes by design |
| Orchestration (detect→arm→route) | `orchestration/{detection_driver,engine}.py` + `backtest/{pipeline_adapter,pipeline_bridge}` | YES | R4 replayed the batch path; adapter scan-cursor + SeriesState perf patches proven byte-identical | — |
| Paper/live seams | `paper/runner.py` + `live/{loop,heartbeat,run_operator}.py` + `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` | YES | Live loop clean (714 polls, 1 bar, 1 decision, 0 errors); full order path proven on demo (limit/cancel/modify-preserves-TP/close, flat); watchdog compiles, attach GUI-pending | Paper runner is the least unit-tested heavy module (project-wide audit C3) |

## 3. Dominant live path (what the bot mostly actually does)

M1 session/periodic sweep → displacement check (FVG-present minority passes Pillar 2) → M1/M5/M7-ish tags → five pillars → **Trigger F continuation** → limit at proximal/mid → **sub-ATR stop (0.82–0.89×)** in a pre-touched level → wick-tag stop-out (35/64) or BE scratch — with an 87%-of-flow F book, a 70-trade B sidecar (wide stops, shelf levels, BE-or-break outcomes), and statistical ghosts elsewhere.

## 4. Absent / silent paths

- **M8 HTF confluence** (the spec's preferred setup): registered, never fed — zero representation in every artifact. Unmeasurable until D1/H4 provisioning.
- **Trigger D**: dead on volume-less data (binding A5 ruling; needs vendor volume or price-only redefinition — open ruling).
- **Triggers C/E**: n=1/2 in 5 years — no inference licensed.
- **M3-pattern flow**: nearly absent from kills and book alike (distinct from Trigger-A fires).
- **ADX / Kalman / ATR-floor gates**: no modules exist — deferred, not forgotten (TODO Phase 5 note).
- **News gate**: coded, dormant (empty calendar in all runs).
- **Armed-never-traded registry / never-routed pillar paths / FVG context at open**: not persisted (export-patch backlog).

## 5. Mismatches (with dispositions)

1. **Tags vs geometry (OPEN):** identical zones re-detect with different tag sets (M1+M7→M4→M5); M4 tags sit on continuation flow with no visible reversal structure. Tags are detection-path-dependent, not geometry-intrinsic.
2. **Killed vs traded vocabulary (OPEN):** R4 kills are M5/M4/M6-pattern zones; admitted flow is F-trigger continuations. The funnel's pattern language and the trigger's pattern language barely overlap.
3. **BE-contaminated metrics (CLOSED as a finding, bounded):** exported `sl` was post-BE — all R-multiples on 187 trades inflated (showcase: 10–13R → 0.4–0.8R honest). Decontaminated splits published; `original_sl` now exported; rule henceforth: original_sl only.
4. **Zone-entry divergence (OPEN, hypothesis only):** 10/11 entries sit 1–4 zone-heights outside recorded zones; merge-widest-zone retention is the untested hypothesis.
5. **R1 MFE windows are BE-protected lifetimes (CLOSED as a finding):** R1's B 6.12R median corrected by R2 chronology (SL-first 70/70) — excursion-within-protection, not reachable-before-stop.
6. **Verify-window over-arming (CLOSED as methodology):** research scripts arm per-bar uuids without ZoneRegistry dedup → duplicate rows; all counts since deduplicated post-hoc; Phase C book unaffected.
7. **Ticket restart per merged segment (CLOSED as tooling):** inspector now refuses ambiguous tickets; route_id is the stable key (unique 761/761).
8. **Segment-boundary state carry (ACCEPTED + documented):** CARRY_LOSS=1 probe; ±14-day stress unchanged; no continuous-run identity claimed.
9. **Spread-grade scale bug (OPEN ruling):** tag-count scores vs 0–10 thresholds — A/A+ unreachable as coded.

## 6. Conviction summary

**Can discuss with confidence:** the stack executes the frozen spec deterministically (byte-identity, invariants, 596 tests); Pillar 2 (FVG-absence first) is the funnel; F continuation on sub-ATR pre-touched stops is the traded book and it bleeds by wick-tag; BE banks dust exactly as designed; fixed-R TP cannot rescue (best arm 30× below baseline); timing position separates honest excursion ~10× (mid 61.5% vs chase 13% ≥1R, frozen rules, wider-validated); B dies on stop-timing not harvestable TP; Friday luck (+22.93) masks ~half the book loss.
**Cannot claim yet:** per-model pattern validity (flicker); any entry at a documented geometric point (no zone/wave exports in the 5y book); any per-family expectancy (small-n, single-regime, no walk-forward); M8/Trigger-D/C/E anything; that demo P/L (once flowing) validates ideas.

## 7. Recommended next work (ordered)

- **Instrumentation leftovers (small, logging-only):** ORIGINAL sl at placement (DONE); zone bounds (DONE); still open — armed-never-traded registry, never-routed pillar paths, FVG context at open, M8 HTF feed, Phase C re-export with identity fields for 5y-scale charting.
- **Research only:** pullback-v3 (swing-anchored) + chop-outcome study; F-timing × session at larger n; stop-band observation (pre-touch exclusion as pure measurement); FVG-absence predictive split once admitted-FVG rates are measurable.
- **Ops only:** watchdog EA attach (GUI) → emergency drill → 2-week stability → divergence log; spread distribution across full trading days.
- **Explicitly deferred redesign (no prompt without a gate ruling):** any TP family, any threshold move, MQL5 strategy logic, M8 provisioning, capital scaling, live money.

---

*End of map. Evidence paths: `06_RESEARCH/PHASE_C_BASELINE_REPORT.md`, `POST_BASELINE_DIAGNOSIS.md`, R1–R4 + follow-on/wider/honest-R/r3/r4 notes, match/stratified/timing/stop-structure notes, `PHASE_D_DIVERGENCES.md` §8, `04_SRC/smc/` tree as observed 2026-09-20.*
