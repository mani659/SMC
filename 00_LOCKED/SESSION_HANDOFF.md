# SESSION HANDOFF — SMC BOT

**Last Updated:** 2026-10-06 (**PRE-COMMIT HYGIENE + CONTRACT LOCK (unified GLM + Co-pilot audit ruling)** — 4-item directive implemented, no commit/push: (1) `.gitignore` now ignores `06_RESEARCH/results/` (90 MB / 773 files, HEAD tracks zero files there; curated exceptions only via explicit `git add -f`); (2) **product-mode H4+H1 detection enforcement at construction** — `MultiTFProductRuntime.__init__` raises a loud `ValueError` naming every missing timeframe when `allow_single_tf_degraded=False` and the detection set omits H4 or H1 (W1+D1 remain optional context, M5 exec unchanged, degraded opt-in still allowed; caller survey confirmed every non-test construction safe — run_operator/paper default to H4+H1, research funnels use the default); (3) `LOCKED_DECISIONS.md` **§4a amendment (2026-10-06)** — dated supersession of §4/§21/(§27) timeframe-role conflicts: H4+H1 required detection, W1+D1 optional (W1=32769 context tier), M5 execution, pointer to `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` + enforcement location; no numeric threshold or locked constant touched; (4) **F3 guard** `test_f3_asof_trim_guard.py` — pins the as_of trim convention (demonstrates Pillar-1 suffix sensitivity: trimmed PASS vs untrimmed REJECTED; asserts `build_htf_prefixes` and `PaperRunner.arm_multi_tf` never deliver a series whose last bar exceeds as_of). New tests: `test_product_mode_detection_policy.py` (6) + F3 guard (3). Suite **853 → 862**; `locked_constants.py` diff empty. **NEXT READY: commit/push prompt (3-commit split per audit: 04_SRC code+tests / 06_RESEARCH+config / 00_LOCKED governance).**) PREVIOUS: **PAPER/DEMO OPS SESSION PASS (post console fix; dry_run only)** — 20-min bounded session on DEMO 474608655 XAUUSDm with the current stack (W1 provisioned + fixed structure console + structural TP + §5a): identity PASS, 2386 polls / 5 bars, 1 HTF batch (H4 23/11/3 passed, **armed 1**, duplicates 2), **39 structure boards — every one matched detect.armed 1 with ZERO lag** (batch 16:29:01Z → board snapshot same second; the mismatch fix proven in ops), 0 orders / 0 fills / 0 errors, clean shutdown + heartbeat shutdown marker; watchdog EA attach still BLOCKED (GUI-only, honest record, not blocking). Suite 853; `locked_constants.py` diff empty. Note: `06_RESEARCH/PAPER_OPS_SESSION_NOTE.md`; artifacts `06_RESEARCH/results/paper_ops_20261006/`. **NEXT READY: project-wide independent audit → git commit/push (per Architect order).** PREVIOUS: **LIVE CONSOLE vs ARMED MISMATCH — ROOT-CAUSED + FIXED + RECONCILED LIVE (ops bugfix, dry_run only)** — **root cause:** the structure-snapshot rate limit treated the arming event (HTF batch change) like routine per-bar refreshes, so with `console_refresh_s=900` an armed POI stayed off the board up to 15 min while the status counter updated immediately (stale-snapshot window; arm path → engine `_armed_order` → `tracked_pois()` verified sound). **Fix (display wiring only):** batch changes now ALWAYS rebuild the snapshot immediately (bar refreshes stay rate-limited; idle polls no-op) + board header carries an armed counter so `detect: armed N` vs POIS can never silently diverge. 4 regression tests (`test_structure_refresh.py`); suite **849→853**. **Warm-up audit: design already correct** — LiveLoop fetches `htf_window_bars=300` per HTF at start AND for every batch (full window re-scanned, `build_htf_prefixes` trims to as_of): W1 300 bars back to **2021-01-10**, D1 300 (12 mo), H4 300 (9.5 wk), H1 300 (2.5 wk), M5 200; no operator-path override. **Live reconciliation (600 s dry_run, Copy terminal):** batch 15:40Z armed 1 (H4 23/11/3 — same counts as the Architect's pasted session) and the structure board immediately showed the armed H4 zone (LONG demand_supply+fvg+ob 3982.45-4310.83, state=TESTED, sweep-linked 1.20×ATR) — counters and console now agree on the same "armed" definition; clean shutdown, heartbeat shutdown marker. Note: `06_RESEARCH/LIVE_CONSOLE_ARMED_MISMATCH_NOTE.md`. **NEXT READY: paper trading (console trustworthy) | Architect review.** PREVIOUS: **SETUP LEDGER BACKFILL + EXPERT PACK PASS (2026-10-06, research/export only)** — direction backfilled **17/30** (trade_row 3 + EXACT unique geometry join vs 6m structure-ledger poi_raw events 14; 13 DATA_GAP — source artifacts lack those zones' geometry, never guessed); posture UNKNOWN 30/30 (not in any artifact, never price-inferred); arm_ts_utc 30/30 via exec-bar map validated 6/6 against routed trade entry/exit timestamps; human verdict/timing/notes columns STILL BLANK by design; hyp-outcome joins preserved. **Expert pack: `06_RESEARCH/results/setup_identification_ledger/EXPERT_SETUP_REVIEW_PACK.pdf`** (7 pages: cover+rubric, 30-row ledger table, 15 charts = 3 routed + D1 3/H4 6/H1 3 evenly spaced by arm bar) + report `06_RESEARCH/SETUP_IDENTIFICATION_EXPERT_REPORT.md` (rubric: CORRECT/PARTIAL/WRONG/UNCLEAR × EARLY/ON_TIME/LATE/N_A — identification quality, NOT PnL; Architect draft notes on the 3 routed rows in a clearly separated appendix). Scripts `setup_ledger_backfill.py` + `setup_ledger_expert_pack.py` (dual-run deterministic); suite 849 green; `locked_constants.py` diff empty. **NEXT ACTION: expert review of the pack (fill verdict/timing) → then paper trading prompt (paper only after expert scores or an explicit waiver).** PREVIOUS: L2 SETUP IDENTIFICATION LEDGER PASS (2026-10-06, research+export only) — script `06_RESEARCH/scripts/setup_identification_ledger.py` joins the frozen 6m post-TP funnel armed records (30 setups: H4 19/H1 6/D1 5) with hypothesis-outcome trades (run_label 6m_post_tp_run1): 3 routed with full plan (entry+SL+TP), join YES (SL_THEN_TP_PATH 2 / TP_REACHED 1, tp_source atr_fallback 2 / structural_swing 1); human columns verdict/timing/notes BLANK by design (reviewer's step, never pre-filled); honest gaps documented (direction only from trade rows, posture UNKNOWN — not instrumented in the funnel export); double-run byte-identical (setups.csv SHA 5388635e…); paper path documented (same column schema from future operator/KPI exports — no live run required for PASS); no 04_SRC/smc/** edit, `locked_constants.py` diff empty, no expectancy claims. Note: `06_RESEARCH/SETUP_IDENTIFICATION_LEDGER_NOTE.md`; outputs `06_RESEARCH/results/setup_identification_ledger/`. **NEXT READY: Architect review (L2 ledger + W/L1/dry-run chain) | paper ops.** PREVIOUS: **LIVE CONSOLE BOUNDED DRY-RUN PASS (EXNESS Copy, 2026-10-06) — ops validation only** — three bounded sessions on DEMO 474608655 XAUUSDm (150 s/400 s/420 s, dry_run=true, no orders): identity gate PASS, clean shutdowns with heartbeat `state=shutdown`; **W1 enum bug FIXED: 32768 → 32769** (the MetaTrader5 package's TIMEFRAME_W1; 32768 is rejected live by `copy_rates_from_pos` with "Invalid params" — caught by the pre-session probe, contract-restoring fix, suite 849 green with strengthened pin); real product batch fired on the 14:30:00Z M5 close (H4 22 raw→9 merged→0 passed; H1 21→8→0 passed; W1/D1/H4/H1 each fetched live at 300 bars), **7 live structure boards rendered** with honest empties (W1/D1/H4/H1 all `(none)` — zero PASSED POIs in window = Pillar rejection, not cold-start; sweeps none, plan none). Note: `06_RESEARCH/LIVE_CONSOLE_DRYRUN_NOTE.md`. **NEXT READY: L2 setup identification ledger (directive already issued — see POST_V1_ACTIVE_TODO).** PREVIOUS: **WEEKLY (W1) PROVISIONING + LIVE STRUCTURE CONSOLE — MILESTONES W + L1 BOTH PASS (Lead Architect two-sequence engagement 2026-10-06)** — **W:** `Timeframe.W1 = 32768` (MT5 PERIOD_W1, minutes=10080, §27 HTF class N=5 with `N_BAR_HTF` unchanged) wired additively at 5 seams: enum, `resample.py` (Monday-00:00 ISO-week bins — epoch-multiples would align to Thursday, deliberate market-convention exception + guard bypass), M8 `HTF_TIMEFRAMES=(W1,D1,H4)` same frozen scanner with D1×H4 overlap pairing FROZEN (quality scores untouched), `multi_tf.M8_HTF_TIMEFRAMES`, runtime `optional_timeframes=(W1,D1)`; `LiveLoop` product fetch list now `(H4,H1,W1,D1)` with batch cadence still keyed on the new H1 close; W1 role = HTF CONTEXT POI ONLY, execution stays M5; required detection set unchanged (H4,H1, loud-fail intact); suite 829→838 (+9 `test_weekly_provisioning.py`), note `06_RESEARCH/WEEKLY_PROVISIONING_NOTE.md`. **L1:** read-only structure console `smc/live/structure_console.py` (`build_structure_snapshot` + `render_structure_console`, pure ASCII renderers, not MT5 chart objects) with sections POIS / SWEEPS / SEEKING / PLAN — W1 rows are LIVE engine data (not hardcoded demo rows), honest empties pinned; operator wiring refreshes on a new M5 bar and/or HTF batch, rate-limited to `console_refresh_s`; additive display-only seams `MultiTFBatchReport.displacements` + `LiveLoop.sweep_links` + `PipelineAdapter.active_workflows()`; suite 838→849 (+11 `test_structure_console.py`, fake snapshots, no MT5); design `06_RESEARCH/LIVE_STRUCTURE_CONSOLE_DESIGN.md`, note `06_RESEARCH/LIVE_STRUCTURE_CONSOLE_NOTE.md`. Both milestones: `locked_constants.py` diff empty; no pillar/trigger/SL/TP/risk/§5a changes; no expectancy claims. **NEXT READY: L2 setup identification ledger (parked until Architect/user requests setup-count validation) | Architect review of W+L1. Do NOT start L2 without a ruling.** PREVIOUS: STRUCTURAL TP FEED — IMPLEMENTED + MEASURED 2026-10-05 (design accepted; diagnostic only)** — the accepted design lock implemented on the minimal surface: pure selector `structural_tp_target` in `smc/backtest/pipeline_bridge.py` (§19-confirmed swings, `confirmed_index < placement_bar` strictly before the decision bar; LONG nearest valid swing high strictly beyond `entry + STRUCTURAL_TP_MIN_ATR × atr`, SHORT mirrored; recency tie-break; documented age bound = `poi_give_up_bars()` as CPU/age cap, NOT give-up semantics per Architect ruling) fed at the EXISTING adapter `candidate_from_route(structural_target=)` call site on the SAME place-time prefix the scan consumed; `resolve_take_profit` untouched; interim constant `STRUCTURAL_TP_MIN_ATR = 0.25` module-level (Architect-accepted, pinned in tests, pending formal § lock); `tp_source` audit provenance threaded E1-style candidate→order→position (BE-preserving)→TradeRecord→CSV/JSON, audit-only (test-enforced no reads in risk/**). Measurement on the frozen 3m window (dual run, harness `structural_tp_feed_measurement.py`, artifacts `06_RESEARCH/results/structural_tp_feed/`): **placed 2 → structural 1 / fallback 1 (50/50), TP non-null 100%, fills 2, trades 2**; exit mix **take_profit 1 + stop_loss 1 (BE-scratch 1)** vs pre-feed stop_loss 2 — the C trade poi-001022 flipped SL −0.3728 → structural TP **HIT +0.3852** (nearer first-swing target reached before stop); F trade fallback byte-identical to pre-feed (+0.0715 BE scratch); **net +0.4567 diagnostic n=2 — NOT performance, no edge claim; mechanism demonstration only**. **Determinism PASS** (trades.csv + report.json byte-identical, SHA `00ee227e…`). Suite **805 → 829** (24 new `test_structural_tp_feed.py`); 2 pre-existing CSV header-end assertions updated for the appended `tp_source` column (E1 convention — column-order assertions retained); `locked_constants.py` diff empty. Note: `06_RESEARCH/STRUCTURAL_TP_FEED_IMPLEMENTATION_NOTE.md`. **PREVIOUS: STRUCTURAL TP FEED — DESIGN LOCK COMPLETE 2026-10-05 (design only, LOGIC_CHANGED: NO)** — `06_RESEARCH/STRUCTURAL_TP_FEED_DESIGN.md`: first-swing selector REUSES the existing §19 swing machinery (`SeriesState`/`SwingIndex.last_valid`), place-time lookahead-safe (prefix-bounded `before = placement_bar`, confirmed swings only, no fill-time refinement); LONG = most recent §19-valid swing high strictly above entry, SHORT mirror, nearest-in-price with recency tie-break, bounded by the armed POI lifecycle (confirmed ≥ arm_bar or base ≥ arm_bar − `poi_give_up_bars()` — PROPOSED reuse); guard `STRUCTURAL_TP_MIN_ATR = 0.25` PROPOSED (note only, not written); attachment = the EXISTING `candidate_from_route(structural_target=...)` kwarg at the existing adapter call site (~L193) + `tp_source=` provenance string; `resolve_take_profit` and fallback 4×ATR untouched; SL explicitly unchanged (policy B); 30-pip absent (policy C). **PREVIOUS: DOCS-ONLY POLICY SYNC COMPLETE 2026-10-05 — governance aligned with the accepted work (Option B seek/scan redesign, frozen 3m + 6m funnels, expert marked charts archive) and the Lead Architect policy rulings A–E recorded in the "Standing rulings + accepted state (2026-10-05)" section below; no code, no constants, LOGIC_CHANGED: NO.** PREVIOUS: **STAGE 3 LIFECYCLE TIMING AUDIT COMPLETE 2026-10-04 — identification only, distributions not opinions: all 263 Stage 3 completions joined to their parent HTF structures (DATA_GAP 0 / NEVER_ARMED 0) and timed against the product arm / first-touch / scan-close events via the accepted instrumented §5 replay. Buckets: **OPEN_SCAN 2 (0.76% all, 0.98% F)**, CLOSED_TOUCH 199 (75.67%), CLOSED_VIOL 62 (23.57%); 2 routed rows sanity → OPEN_SCAN PASS; median completion−scan_close 10 bars (all) / 10 bars (F); structure findings: arm = close bar for all rows (11 weekend minute-gaps), first_touch == arm for all 199 touch-closed structures (effective seek span [arm, arm+1]), all 62 violations fire at arm (scan never opens); 3 illustrative charts; double-run byte-identical; suite 772→780; report `06_RESEARCH/STAGE3_LIFECYCLE_TIMING_REPORT.md`.** PREVIOUS: **STAGE 3 TRIGGER VISIBILITY + CONVERSION AUDIT COMPLETE 2026-10-04 — identification only: 668 accepted HTF structures scanned at the product horizon [close, close+20 M5]; **263 completed Stage 3 triggers** (A 31 / B 17 / C 4 / D 0 / E 7 / F 204; M5 263 / M1 0), all HTF-linked (0 unlinked by construction, disclosed); conversion 15,350 detector links → 263 completions (1.71%) → 2 product routes; route funnel: 261 completions suppressed by the §5 armed-POI lifecycle (199 first-touch+1 gate, 62 zone violation), 2/2 inside the open scan routed (same 2 as LTF pack); 36 charts (30 trigger panels type-seeded June→Nov + 6 negative examples); double-run byte-identical; suite 762→772; report `06_RESEARCH/STAGE3_TRIGGER_VISIBILITY_REPORT.md`.** PREVIOUS: **LTF CONFIRMATION PACK COMPLETE 2026-10-04 — structure/confirmation identification, identification-only: 668 HTF structures (658 H4 pack raw + 10 D1 subset; ob 177/ds 307/fvg 184), stage0 M15=13,474 / M5=37,015, ledger 15,352 rows; dual=0 per source pack, conflicts=0; activity 624 / silent 44; trigger mix {F:2} pre-pillar routes; sample 13 (7 active + 6 silent) = 39 panels, caps ≤12/≤8/≤40; look-ahead M5=20 (TRIGGER_A_EXPIRY) / M15=7 same rule every structure; double-run byte-identical; suite 754→762; report `06_RESEARCH/LTF_CONFIRMATION_REPORT.md`; note `06_RESEARCH/LTF_CONFIRMATION_NOTE.md`.** PREVIOUS: **H4 POI IDENTIFICATION PACK COMPLETE 2026-10-04 — structure confirmation, identification-only: raw 658 (ob 177/ds 304/fvg 177) / merged 3 / armed 0; dual=0, conflicts=0, origin_tight=0, all rows H4; 55 charts; double-run byte-identical; suite 750→754; report `06_RESEARCH/results/h4_poi_confirmation/H4_POI_CONFIRMATION_REPORT.md`; note `06_RESEARCH/H4_POI_CONFIRMATION_NOTE.md`.** ACTIVE PROGRAM: V1.1 RUNTIME BASELINE FROZEN (docs-only freeze, 2026-09-24 — `00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md`).** The frozen baseline = Choice 1 Product Runtime Unification (Phase 0 contract + C1 multi-TF runtime in live/paper + Phase 2 contracts + Phase 3 funnel + Phase 4 byte-identical frozen 3-month backtest) + Track A (E1 entry_anchor export DONE, C3 UNFED_DESIGN_ONLY, C4 news/sweep DEFERRED + spread WIRED) + Phase D HTF probe PASS on EXNESS Copy DEMO (H4/H1/D1=300 bars, dry_run loop clean). **Expectancy / PF / live profitability are NOT proven and NOT part of the freeze** — the default posture is operate-and-observe under contract, not redesign. **Allowed without a ruling:** Phase D ops (watchdog EA attach + emergency drill, stability logging), contract-restoring bugfixes, docs. **Requires a dated ruling:** locked_constants edits; pillar/trigger/zone/R7/R9 edits; F-timing/Monte Carlo; structural TP invention; treating demo PnL as idea validation; dry_run=false campaigns. **NEXT ACTION = Architect review of hypothesis-outcome study (SL_THEN_TP_PATH 4 / TP_REACHED 2 / MFE_ONLY 0 / REJECTED 0 / DATA_GAP 0 on the 6m post-TP n=3 sample; cross-tabs by trigger/tp_source/close_kind recorded; no strategy logic change).** Next engagement after that review: whatever the Architect rules for Phase D / hypothesis-outcome analytics follow-on. BANS stand: F-survivor/F-timing PAUSED (R6), Monte Carlo PAUSED, demo PnL never idea validation, no locked-constant edits without a dated ruling. PRIOR: TRACK A RESIDUAL ENGINEERING COMPLETE (E1→C3→C4, ordered; per owner prompt). E1 entry_anchor export DONE — first-class field on the full trade path (bridge→order→position→TradeRecord→CSV/JSON, appended + backward compatible; modify_sl preserves it like original_sl; also inside signal_data_json); suite 726→737. C3 structural TP = UNFED_DESIGN_ONLY — design note written BEFORE code (`06_RESEARCH/RESIDUAL_A_E1_C3_C4_NOTE.md` §C3); no trigger emits a structural target, nothing invented, TP stays frozen 4×ATR (FR-2 R4). C4 dispositions — news DEFERRED, spread WIRED (operator input, threaded to §28.5 grading), sweep-guard DEFERRED (no trigger emits sweep_level); formal Silent/deferred table in `PRODUCT_RUNTIME_CONTRACT.md` §8; shipped configs (`news_events=[]`, `spread_price=0.0`) remain diagnostic, NOT "gates proven live". No decision-logic change, no locked-constant edit. PRIOR: PRODUCT RUNTIME UNIFICATION (Phase 0–4, owner "Choice 1") — ALL FOUR PHASES COMPLETE/PASS. Phase 4 frozen 3-month measurement (exec 2025-09-01→11-30): 17 armed / 8 routes (all F) / 1 BE-scratch fill (+0.0715 diagnostic); trades.csv + report.json BYTE-IDENTICAL across run1/run2; paper dry wiring proven. NEXT ACTION = Lead Architect accept Track A, or Phase D HTF probe on EXNESS — NOT silent F-optimization.** Prior: PHASE 0 + PHASE 1 C1 COMPLETE — ONE MULTI-TF PRODUCT RUNTIME: contract `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` + shared seam `smc/orchestration/multi_tf_runtime.py`; live/paper no longer single-TF (H4+H1 detection, D1→M8, batch per new H1 close, start-time HTF probe refuses in product mode); suite 698 green; no threshold/constant edits.** Prior: AS-CODED ARCHITECTURE EXTRACTION COMPLETE (Part 1 of 3 — report + pictures + inventory; comparison vs Rev 5 COMPLETE (Lead Architect Part 2 — verdict gaps C1–C4 recorded in CHANGELOG); 6-month structure ledger NOT started).** Prior: FOUNDATION FIDELITY RESET ACTIVE — fill-regime rulings R7+R8 implemented, then R9 place-on-reentry intent: FIRST COMPLETE CHAIN under frozen rules (armed→re-entry→FILL→BE→close +0.07, M8 poi-014750; suite 681). PAUSED Trigger F survivor optimization as main track.** Prior: FR-3.1 PASS (on-zone entry anchor) · FR-4 + fate ledger + FR-4b + unfilled forensic DONE · Track R CLOSED (R1–R5 PASS) · Export identity/zone patches DONE · Phase C CLOSED, Phase D OPENED session 1 on EXNESS Copy terminal.)
**Purpose:** Everything a new agent needs to continue this project without asking questions.

---

## Standing rulings + accepted state (2026-10-05, docs-only sync)

**Current phase / next task = Architect review of structural TP feed metrics (implementation note `06_RESEARCH/STRUCTURAL_TP_FEED_IMPLEMENTATION_NOTE.md`); then optional wider-window diagnostic.** First swing low|high fed via the existing `structural_else_4ATR` branch (NOW LIVE — was UNFED C3/FR-2 R4); SL unchanged (ATR/structural); the expert "30 pips" statement = review metric only (post-trade MAE yardstick), never a live stop.

**Accepted 2026-10-05 (recorded as done — do not re-litigate):**

- **Option B seek/scan redesign** — implemented, `LOCKED_DECISIONS.md` §5a amended, suite 805.
- **Frozen funnels under the new contract (diagnostic only — NOT performance):** 3m (Sep–Nov 2025): armed 18, routes 9 (F 8 + C 1), fills 2, trades 2; 6m (Jun–Nov 2025): armed 30, routes 10 (F 9 + C 1), fills 3, trades 3.
- **Expert marked charts archive (2026-10-05):** 11 charts → `03_REFERENCE_CODE/expert_marked_charts/`; index `06_RESEARCH/EXPERT_MARKED_CHARTS_INDEX.md`; ledger `06_RESEARCH/results/expert_marked_charts/ledger.csv`; match note `06_RESEARCH/EXPERT_CHART_SYSTEM_MATCH_NOTE.md`; match YES 1 · PARTIAL 9 · NO 3 · time DATA_GAP all; LOGIC_CHANGED: NO.

**Standing rulings (Lead Architect, 2026-10-05):**

- **A. TP:** structural / first swing low|high MAY be fed via the existing `structural_else_4ATR` branch (currently UNFED). Design+implement is the NEXT coding track after this docs sync. Not done yet. **[UPDATE 2026-10-05: design accepted AND implemented — see the Last-Updated chain; `tp_source` shares: structural 50% / fallback 50% at n=2 placed on the 3m frozen window.]**
- **B. SL:** remain current ATR / structural stops. Fixed 30-pip stop is NOT adopted.
- **C. Expert "30 pips below/above LTF entry":** REVIEW METRIC ONLY — post-trade MAE / entry-precision yardstick. Not a live stop rule.
- **D. PARTIAL findings (standing guidance):** WRONG → never trade; CORRECT → full path (existing gates); PARTIAL → allowed in principle, must eventually carry a quality tag; default degradation direction = log + half risk until a dated size rule is locked. Not implemented in code yet — policy posture only.
- **E. Pattern vocabulary gaps** (double top/bottom, Fib golden, W1 OB, etc.) are documented from the match note — research backlog, not silent scope expansion this session.

**Bans unchanged:** no threshold fishing, no F-survivor/F-timing optimization (R6), Monte Carlo PAUSED, demo PnL never idea validation, no locked-constant edits without a dated ruling.

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
| `POST_V1_PLAN_OF_ACTION.md` | `00_LOCKED/` | ACTIVE — binding post-V1 operational plan (Phases A–E). **Start every post-V1 session here.** |

---

## Current Project Structure

```
SMC/
├── 00_LOCKED/           ← Source of Truth (read-only)
├── 01_ARCHITECTURE/     ← Current design docs + v5 flowcharts
├── 02_KNOWLEDGE_BASE/   ← 57 PNG visual references
├── 03_REFERENCE_CODE/   ← GOLD_SMC_v25_DIAG.mq5 + CAB files
├── 04_SRC/              ← Python codebase (Phases 0–7 built: `smc` package + tests)
├── 05_MQL5_SAFETY/      ← Safety Watchdog EA (SMC_Safety_Watchdog.mq5)
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
- **Phase 6:** Backtesting & Paper Trading (4–6 days) — ✅ BUILT (2026-09-09) — M1–M6 accepted, suite **496 passed** (audit fixes → **501**; coherence patch → **510**)
- **Phase 7:** Live Readiness + MQL5 Safety Watchdog (1–2 days) — ✅ BUILT (2026-09-09) — live loop + heartbeat + watchdog EA, suite **519 passed**
- **News Hard-Cancel:** ✅ implemented in Python (`news_guard.py` + §11 hard-cancel in both runners)

**Total estimated effort:** 25–39 working days

---

## Current Phase & Next Task

**Current Phase:** ✅ **V1.1 RUNTIME BASELINE FROZEN (2026-09-24 — `00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md`); next action = Phase D watchdog GUI chart-attach + stale-heartbeat emergency drill (ops), or wait for a dated research ruling. Completed-program record — 🚀 PRODUCT RUNTIME UNIFICATION (Phase 0–4, owner "Choice 1", 2026-09-23)** — the binding program after the Foundation Fidelity Reset restored the research multi-TF path: **research, paper, and live must share ONE multi-TF detection → M5 execution runtime.** **Cold-start reading order:** (1) `LEAD_ARCHITECT_ROLE_AND_PROTOCOL.md` → (2) this section → (3) `POST_V1_ACTIVE_TODO.md` "Product completion path" + §7 marker → (4) `PRODUCT_RUNTIME_CONTRACT.md` (Phase 0, LOCKED) + `06_RESEARCH/C1_MULTI_TF_PRODUCT_PATH_NOTE.md` → (5) `AS_CODED_ARCHITECTURE_FLOWCHART.md` for code truth. **Phase 0 — product contract: DONE** (2026-09-23). **Phase 1 / C1 — one multi-TF runtime: DONE (PASS)** — seam `smc/orchestration/multi_tf_runtime.py`, live + paper wired, loud-fail on missing HTF, suite 698. **Phase 2 — layer/pillar CONTRACT tests: DONE (PASS)** — 28 contracts (detectors + pillars 1–5 + handoffs) with stable reason tokens, suite 726, snapshot `results/phase2_contracts/snapshot.json`, note `PHASE2_LAYER_CONTRACTS_NOTE.md`. **Phase 3 — structure funnel / information-flow audit: DONE (PASS)** — locked October window on the product seam, funnel JSON + sample audit (8/8, 0 gaps) + determinism pair + charts; report `PHASE3_STRUCTURE_FUNNEL_REPORT.md`. **Phase 4 — frozen backtest + paper on the unified machine: DONE (PASS)** — locked 3-month window, byte-level determinism pair, 1 complete R9 fill chain; report `PHASE4_UNIFIED_BACKTEST_REPORT.md`. **CHOICE 1 COMPLETE — program review ACCEPTED; Track A residuals COMPLETE; Phase D HTF probe PASS; V1.1 runtime baseline FROZEN (`00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md`).**
- **QA Pack Delivered (2026-09-21):** `06_RESEARCH/FOUNDATION_RESET_QA_PACK.md` — comprehensive 36-question audit spanning intended cascade, Stage 0/0b liquidity & Base Candle law, POI models M1–M8, Multi-TF/Model 8 silence, 5 quantitative pillars, surgical triggers A–F, stops & hardwired `tp_price=None`, research drift taxonomy, and 10 foundation reset questions with a standardized fidelity scorecard.
- **Core Verdict:** V1 is not trading the Revision 5 architecture. V1 is an M1-only trend-chase engine dominated by Trigger F (86.6%) with sub-ATR stops inside noise (0.82× ATR, 5 pre-touches) and zero take-profit capability (`tp_price=None` hardwired), while the flagship multi-TF Model 8 is completely dormant (`htf_candles={}`).
- **Hard Rule for Future Agents:** **STOP treating Trigger F survivor optimization as the main track.** No threshold tuning, no Monte Carlo, no TP implementation until the Lead Architect reviews the QA Pack and orders the foundation reset sequence.
- **Phase D Operations (in parallel, background only):** EXNESS Copy demo terminal ops validation continues for operations proof only (EA chart-attach + emergency drill pending).
- **BANS while on this path (binding):** F-survivor optimization / F-timing / chase discriminators as main track — PAUSED (R6); Monte Carlo — PAUSED (broken-book confidence intervals are meaningless); Phase D demo P/L is never idea validation; **no long expectancy flagship run before Phase 2**; no locked-constant / threshold / zone-band edits without a dated Lead Architect ruling.

- **STRUCTURE IDENTIFICATION LEDGER + EXPERT VALIDATION PDFs DELIVERED 2026-09-25 (read-only measurement + export + charts + docs; LOGIC_CHANGED: NO).** Six-month identification ledger over the LOCKED window 2025-06-01→2025-11-30 (2 tiled 3-month chunks; 35,725 M5 bars / 2,979 HTF batches / 0 batch errors): **13,247 unique events** (liquidity_level 4,320 · sweep 2,041 · poi_merged 1,745 · pillar_reject 1,669 · poi_raw 1,418 · displacement 1,117 · fvg 802 · pillar_pass 76 · poi_armed 31 · intent 16 · route_ltf 10 · fill 2) from 6,089,850 raw observations; funnel **31 armed / 10 routes / 2 fills**. Artifacts: `06_RESEARCH/results/structure_ledger_6m/` (`events.csv` + `events.jsonl`, `summary.json`, 44 stratified `review_sample/` PNGs, self-contained `review_gallery.html`, `verification_matrix.json` = 44 PASS / 0 failures / 3 documented flags, `REVIEW_INDEX.md`); report `06_RESEARCH/STRUCTURE_IDENTIFICATION_LEDGER_REPORT.md`; tooling `06_RESEARCH/scripts/{structure_identification_ledger,verify_review_pack,build_expert_pdfs}.py`. **Shareable expert PDFs, charts EMBEDDED (reportlab, native 1820×910 image XObjects, no external file dependency, A4, contents verified): `06_RESEARCH/results/structure_ledger_6m/EXPERT_VALIDATION_PACK.pdf` (20 pp, 24 priority charts, blank per-chart verdict lines, documented flags shown not hidden) and `STRUCTURE_LEDGER_FULL_REPORT.pdf` (32 pp, all 44 charts stratified) + text twin `EXPERT_VALIDATION_PACK.md`. NEXT READY = owner/external expert scores CORRECT / PARTIAL / WRONG / UNCLEAR per chart (tally by event_type) — identification is NOT audited until those tallies exist, and a mechanical chart-verifier PASS is not that verdict.** Frozen baseline untouched: no threshold / pillar / trigger / zone-band / R7 / R9 / locked-constant change, no re-tuning, no paper trading, no edge claim; the merge cross-row link repair (48 rows marked `rel_dangling`, all warm-up retain_window cases) and the byte-identical re-run were tooling-only.

- **HUMAN-READABLE FLOWCHART LABELS DELIVERED 2026-09-25 (presentation/export only; LOGIC_CHANGED: NO).** The review surface now speaks **reviewer language instead of engine vocabulary**. Owner feedback was that the first pack read as a code-emission audit, not a flowchart review: internal vocabulary (`poi_raw`, `route_ltf`, `pillar_reject`, `source_module`) instead of human tags, and the post-sweep LTF entry step in a separate section with no set-up story. Fix (presentation only): (1) all 44 charts re-rendered with plain titles (`LIQUIDITY SWEEP`, `ORDER BLOCK (M8 HTF)`, `DEMAND ZONE`, `SUPPLY ZONE`, `FAIR VALUE GAP (FVG)`, `ARMED POI (PASSED VALIDATION)`, `LTF CONFIRMATION (M5 ENTRY, TRIGGER F)`, `ENTRY FILL`) into the NEW folder `06_RESEARCH/results/structure_ledger_6m/review_sample_v2/` (same file names; original `review_sample/` untouched; self-contained `review_gallery_v2.html`; `relabel_manifest.json`); (2) the mandatory **SETUP CHAIN** block on every `route_ltf` / `fill` chart and caption (12 charts) — `FLOWCHART STAGE` → `HTF structure` (armed POI → merged/confluence POI, or the explicit "no sweep / FVG event id is linked in this row") → `LTF confirmation` (M5 trigger letter + detail text) → `Entry` / `Original SL` → "This chart is the lower-timeframe entry step, not the HTF sweep itself."; (3) engine vocabulary DEMOTED, never dropped (one `technical row:` footnote on the chart, a two-line technical record in the PDF caption); (4) new "How to read flowchart tags" page = **expert pack §2** + **full report §1.4**; (5) new `HUMAN_LABELS_NOTE.md`. **One source of truth:** `06_RESEARCH/scripts/flowchart_labels.py` (imported by both `relabel_review_charts.py` and `build_expert_pdfs.py`, so chart and PDF wording cannot drift). **Honesty rule:** a label is emitted only when the row supports it — `kind=ob` → Order block, `kind=demand_supply` + direction → Demand / Supply zone, `kind=fvg` → FVG, else **"unlabeled POI"**; level words from `level_type=`, pool words from `pool=`, trigger letter from `trigger`/`route_id`; no OB / FVG / S&D label and no row-to-row link is ever inferred (8/8 sampled `poi_raw` rows carry a code kind: ob ×4, demand_supply ×4). **Re-verified:** `EXPERT_VALIDATION_PACK.pdf` 34 pp / 2.654 MB / 24 charts; `STRUCTURE_LEDGER_FULL_REPORT.pdf` 56 pp / 4.672 MB / 44 charts; all images 1820×910 native (no downsampling), **0 out-of-frame, 0 overlaps, 0 hyperlinks**, contents stable (24 / 29 entries), A4, image placement + overlap parsed from the content stream (`read_back` in the manifest); the relabelled charts were re-verified by `verify_review_pack.py` itself (new `--png-dir`/`--out` flags keep the canonical matrix intact) — **44/44 PASS, 0 failures, the same 3 documented flags** (`verification_matrix_v2.json`); layout is now **1 chart per page** (the reading + chain blocks need the room — the old 2-per-page code-vocabulary PDFs are superseded, not deleted; `images_per_page` recorded in `pdf_build_manifest.json`). Read-only proof: `events.csv` SHA-256 `903e5a3b401ce30812f5fce69831fc1d9cac7930d3bd0636dec4cc5b89acc063` unchanged, `04_SRC/**` untouched. **NEXT READY = re-share ONLY the expert pack with validators for CORRECT / PARTIAL / WRONG / UNCLEAR tallies (now tallyable by plain tag).**

- **SEEK/SCAN CONTRACT REDESIGN — DESIGN LOCK (Option B) DELIVERED 2026-10-05 (design only; LOGIC_CHANGED: NO).** Per the Lead Architect Option B ruling, the design note `06_RESEARCH/SEEK_SCAN_CONTRACT_REDESIGN_DESIGN.md` was written FIRST, before any production code. It restates the two measured failure modes with exact counts (in-zone-at-close 199/263: first_touch == arm → effective seek span [arm, arm+1]; violation-at-arm 62/263: scan never opens, completions still form inside the locked 20-bar horizon) and locks the new contract as normative rules: arming unchanged + initial-posture classification (`IN_ZONE_AT_ARM` = arm-bar touch is initial presence, not a §5 touch; `VIOLATION_AT_ARM` = REVALIDATION posture, routes only after zone re-entry via the existing `market_reentered_zone` rule; `CLEAN_ARM` = today's behaviour); the scan opens at arm in every posture; the span is the UNCHANGED `[arm, arm+20]` give-up computation; terminators = give-up / violation-after-live-scan (dead-thesis behaviour unchanged) / one-shot route; one-shot/episode identity untouched. Behaviour changes vs §5 one-touch+1 itemised (touch no longer ends the seek; arm-bar violation no longer pre-empts the scan; touch+1 grace subsumed by TRIGGER_D_EXPIRY); every locked constant the contract touches listed as obeyed-unchanged. 4 rejected alternatives recorded. Success metrics M1–M5 for the implementation phase (OPEN_SCAN share 0.76% → target ≥80% with reason split; the 2 routed rows remain routable at the same bars; median(completion−scan_close) ≤ +2; armed-count invariant; one-shot invariant machine-checked; 50% selectivity alarm). Implementation surface: `PipelineEngine` seek-posture + `PipelineAdapter._may_route` replacement; trigger A–F, pillars, risk, fill model, `locked_constants.py` all out of scope. Risks & residuals recorded (incl. required §5 locked-doc amendment at implementation ruling). Self-check vs the 5 measured facts + hard bans recorded in the note (§8). NEXT = implementation + measurement engagement per M1–M5 — NOT STARTED; `04_SRC/smc/**` untouched by this redesign.

- **SEEK/SCAN CONTRACT REDESIGN — IMPLEMENTED + MEASURED 2026-10-05 (Option B; the accepted design lock implemented).** Design R1–R5 implemented with the minimal surface: `PipelineEngine` gains `SeekPosture` (`CLEAN_ARM`/`IN_ZONE_AT_ARM`/`VIOLATION_AT_ARM` classified at `arm_at(..., arm_candle=)`; adverse close wins over touch; no candle → legacy behaviour) and `feed_bar` skips the ARM CANDLE for non-CLEAN postures (the arming candle belongs to the HTF structure — kills both measured failure modes at the root) with REVALIDATION continuation (pre-re-entry adverse close = arm-bar condition continued, dies at give-up; post-re-entry terminal as before); `PipelineAdapter._may_route` replaced — a §5 TESTED state no longer closes the scan (seek runs to the locked give-up deadline; Trigger D preserved by its own expiry), REVALIDATION routes only after zone re-entry via the existing named rule `market_reentered_zone` (R7 band, adapter ATR, fail-closed on warm-up ATR — disclosed deviation from the R7 place-guard dormancy), the re-entry latch moves the scan cursor to the re-entry bar, give-up retirement applies to every posture; one-shot/episode identity untouched. Pre-implementation clarification ruled: `IN_ZONE_AT_ARM` needs no re-entry gate (design R2.2 governs). Measurement on the frozen window (`06_RESEARCH/scripts/seek_scan_impl_measurement.py`; artifacts `06_RESEARCH/results/seek_scan_implementation/`; double-run byte-identical): **M1 OPEN_SCAN share 0.76% → 78.33%** (206/263; F-only 81.86%) — **below the ≥80% target by 5 rows, reported not tuned**, residual 100% attributed (routed_earlier 27 = one-shot success / never_reentered_arm_violation 17 / violation_after_live_seek 13); **M2 PASS** (both previously routed rows route again at the same completion bars); **M3 median(completion − last_scanned) = 0.0 bars** for previously-CLOSED rows (was +10; 204/261 now visible); **M4 PASS** (armed 668=668, 0 arm-bar mismatches; routes 2 → 196 pre-pillar = 29.34% of armed, below the 50% selectivity alarm; mix F159/A21/B8/E6/C4); **M5 PASS** (0 multi-route episodes). Suite **780 → 805** (new `test_seek_scan_contract.py`, 25 tests); `locked_constants.py` diff **empty**; trigger A–F + state-machine diffs **empty**. Note: `06_RESEARCH/SEEK_SCAN_CONTRACT_IMPLEMENTATION_NOTE.md`. **PENDING Architect:** accept implementation + metrics (M1 decision point) and date the `LOCKED_DECISIONS.md` §5 seek-window amendment; no quality filter / F-timing work unlocked by this.

- **§5 LOCKED-DOC AMENDMENT DELIVERED 2026-10-05 (docs-only; LOGIC_CHANGED: NO; implementation ACCEPTED — M1 78.33% residual accepted as fully attributed).** `LOCKED_DECISIONS.md` gains **§5a — Seek/Scan Contract (amended 2026-10-05, Lead Architect Option B)**: records the acceptance with note paths (`SEEK_SCAN_CONTRACT_REDESIGN_DESIGN.md` DESIGN_LOCK PASS; `SEEK_SCAN_CONTRACT_IMPLEMENTATION_NOTE.md` IMPL_STATUS PASS, suite 805, M1–M5 accepted), declares the prior one-touch+1 seek behaviour **superseded**, and states the implemented contract normatively (arming unchanged; `CLEAN_ARM` / `IN_ZONE_AT_ARM` / `VIOLATION_AT_ARM` postures; scan opens at arm in every posture; arm-bar presence = initial presence, NOT a §5 first-touch terminator; REVALIDATION routes only after zone re-entry via `market_reentered_zone`, fail-closed on warm-up ATR; span = `[arm, arm + poi_give_up_bars()]`; terminators = give-up / violation-after-live-scan / one-shot route; one-shot identity unchanged; no numeric threshold or constant changed). The §5 state machine (states, atomic transitions, terminal semantics, §23 unfilled expiry) is explicitly declared UNCHANGED. Cross-references updated: §21 (Model 8 entry rules) and §22 (Demand/Supply freshness rules) now cite §5a. Docs-only: no `04_SRC/smc/**` edit, `locked_constants.py` diff empty, suite 805 unchanged. **NEXT = frozen-window funnel/backtest measurement under the new contract (Architect-directed; same discipline as Phase 3/4, diagnostic only, no optimization).**

- **FROZEN-WINDOW FUNNEL MEASUREMENT UNDER THE NEW SEEK/SCAN CONTRACT COMPLETE 2026-10-05 (diagnostic only; dual-run deterministic).** First full funnel + trade-outcome measurement under the accepted Option B redesign, on the FROZEN Phase 4 window (M1 load 2025-08-01, exec 2025-09-01→11-30, 17,840 M5 bars), via the Phase 3 composition **imported, not forked** — the redesign is measured by running it; zero strategy-code changes. Funnel: 1,488 HTF batches (0 errors) → 20,898 merged → 839 pillar-pass → **18 armed (15 M8)** → 256 scans → **9 routes {F 8, C 1}** — **the C route is the first Trigger C in product history** (C's frozen sweep+3 window was unreachable under the old touch+1 seek; direct product-level fingerprint of the redesign) → 2 placed (TP 2/2 = 100% non-null) + 6 R9 intents (1 placed, 0 expired) → **2 fills → 2 trades**: C stop_loss −0.3728 (anchor absent, honest), F stop_loss +0.0715 BE-scratch (`zone_edge_reanchor`) → **net −0.3013 diagnostic n=2 — NOT performance**. Posture mix on armed: CLEAN 18 / IN_ZONE 0 / VIOLATION 0 — this window's armed population arms clean; the pack-window replay (M1 78.33%) remains the evidence for the other postures. **Determinism PASS:** trades.csv + report.json byte-identical (SHA-256 match); suite **805 passed** unchanged; `locked_constants.py` diff empty. Report: `06_RESEARCH/FROZEN_FUNNEL_NEW_CONTRACT_REPORT.md`; harness `06_RESEARCH/scripts/frozen_funnel_new_contract.py`; artifacts `06_RESEARCH/results/frozen_funnel_new_contract/`. **NEXT = Architect review of funnel results** (honest n=2; nothing authorizes tuning, filters, or paper-trading steps).

- **WIDER FROZEN-WINDOW FUNNEL MEASUREMENT (6 MONTHS) UNDER THE NEW SEEK/SCAN CONTRACT COMPLETE 2026-10-05 (diagnostic only; dual-run deterministic).** Per the Lead Architect wider-diagnostic-window directive: same product path, same discipline, window extended to the frozen 6-month pack window (M1 load 2025-05-01, exec 2025-06-01→11-30, 35,725 M5 bars) — no strategy code, threshold, or constant touched; composition imported, not forked (`frozen_funnel_6m_new_contract.py`, an extension of the 3-month harness). Funnel: 2,979 HTF batches (0 errors) → 43,004 merged (96,015 raw: H4 44,922 + H1 51,093) → 2,021 pillar-pass → **30 armed (28 M8; H4 19/H1 6/D1 5)** → 501 scans → **10 routes {F 9, C 1}** → 4 placed (TP 4/4 = 100% non-null) + 7 R9 intents (3 placed, 0 expired) → **3 fills → 3 trades**: F stop_loss −2.9105, C stop_loss −0.3728 (anchor absent, honest), F stop_loss +0.0715 BE-scratch (`zone_edge_reanchor`) → **net −3.2117 diagnostic n=3 — NOT performance**. Posture mix: CLEAN 30 / IN_ZONE 0 / VIOLATION 0 — the wider window still does NOT exercise the non-CLEAN postures on the product path (pillar-filtered armed population arms clean across all 6 months; suite + pack replay remain the posture evidence); non-F routes stay thin (C n=1, A/B/D/E 0). **Determinism PASS:** trades.csv + report.json byte-identical (SHA-256 match); no `04_SRC/smc/**` edit. Report: `06_RESEARCH/FROZEN_FUNNEL_6M_NEW_CONTRACT_REPORT.md`; artifacts `06_RESEARCH/results/frozen_funnel_6m_new_contract/`. **NEXT = Architect review of 6m funnel results** (honest n=3; nothing authorizes tuning, filters, or paper-trading steps).

- **EXPERT CHART ARCHIVE + SYSTEM MATCH PROBE COMPLETE 2026-10-05 (read-only; LOGIC_CHANGED: NO).** The operator's 11 human-marked example charts (Downloads `1.jfif…11.jfif`, XAUUSD-VIP TradingView-style, no dates readable) archived byte-identical to `03_REFERENCE_CODE/expert_marked_charts/`, inventoried in `06_RESEARCH/EXPERT_MARKED_CHARTS_INDEX.md` + `06_RESEARCH/results/expert_marked_charts/ledger.csv` (flowchart-language tags: W1 OB → D1 structural sweep → H4 sweep / H4 FVG → M5/M1 double top-bottom, CHOCH, Fib golden, ending diagonal → entry; both directions present). Labels rest on RapidOCR + red-pixel geometry (harness-local, pip-only; browser screenshot path broken in this build). Match probe vs the existing frozen structure ledger (13,247 rows, events SHA 903e5a3b… unchanged, read-only, no re-detection): **YES 1** (chart 3 H4 sweep), **PARTIAL 9** (mostly TF-capped M5/M1/W1→H1/D1 or coarse annotation spans — honest-but-weak), **clean NO 3** (charts 5/6 FVG zones miss by ~39.6/46.2 price units; charts 10/11 at route/entry level — 0 of 10 routes near marked entries), **time matching DATA_GAP for every chart** (no dates readable — none invented). Pattern classes the system does not emit (double top/bottom, CHOCH, Fib golden, ending diagonal, W1) disclosed. **Operator TP/SL policy captured docs-only, PENDING Architect ruling, NOT implemented:** (a) TP = first swing low/high; (b) SL = 30 pips below/above small-TF entry — current V1 behaviour unchanged (structural-else-4ATR TP branch UNFED; SL structural ± buffer/ATR, not fixed pips). No `04_SRC/smc/**` edit; `locked_constants.py` diff empty. Note: `06_RESEARCH/EXPERT_CHART_SYSTEM_MATCH_NOTE.md`; probe `06_RESEARCH/scripts/expert_chart_match_probe.py` + `results/expert_marked_charts/match_probe.json`. **NEXT = Architect ruling on the TP/SL policy statements (and on whether any pattern-class vocabulary gap matters before paper/ops).**

**Prior Research Milestones (Frozen Reference):**
- **HONEST-R COMPLETE 2026-09-20: PASS.** 39 unique setups: med MFE_R honest 0.42 (full-SL-only 0.23), 30.8% ≥1R honest vs 38.5% contaminated; showcase flips nailed (10–13R → 0.4–0.8R); stop/ATR honest 0.85; entry-selection diagnosis holds. Report: `06_RESEARCH/PHASE_HONEST_R_RECOMPUTE_REPORT.md`.
- **STRATIFIED SAMPLE COMPLETE 2026-09-20: PASS.** 16 charts + `STRATIFIED_INSPECTOR_NOTES.md`: F entries mostly chase/mid-move (7/9); 10/11 entries sit 1–4 zone-heights outside recorded zones; B is shelf-trading.
- **F-TIMING COMPLETE 2026-09-20: PASS.** Rule v1: 23 late_chase (med MFE 0.03R, 13% ≥1R) / 13 mid_move (1.17R, 61.5%) / 1 pullback. Report: `06_RESEARCH/F_TIMING_DISCRIMINATOR_NOTES.md`.
- **WIDER-VALIDATION COMPLETE 2026-09-20: PASS.** n=64 pooled unique F: mid_move 57.9% ≥1R vs late_chase 26.2%. Report: `06_RESEARCH/F_TIMING_WIDER_VALIDATION.md`.
- **STOP-VS-SHELF COMPLETE 2026-09-20: PASS.** 69 pooled setups: F stops tight (0.82× ATR) in pre-touched levels (5 touches median) with wick-tag majority deaths (35 vs 29); B stops wide (2.65× ATR) in fresh levels with close-through majority. Report: `06_RESEARCH/STOP_VS_STRUCTURE_NOTES.md`.
- **FORMAL MAP COMPLETE 2026-09-20: PASS.** `06_RESEARCH/FLOWCHART_CODE_EVIDENCE_MAP.md`: durable record binding pipeline × modules × evidence.
- **PHASE D OPS PUSH 2026-09-21 (open market, Mon 10:28-10:40 UTC): PASS on executable items.** Identity MATCH, Algo Trading ON, full order path proven live. Log: `PHASE_D_DIVERGENCES.md` §8.
**ROLE PROTOCOL FILE EXISTS — mandatory startup reading:** `00_LOCKED/LEAD_ARCHITECT_ROLE_AND_PROTOCOL.md` (ACTIVE/BINDING 2026-09-21; role boundaries, anti-drift rules, verification protocol, startup order). No session may proceed on chat memory alone.
**FR-0b COMPLETE 2026-09-21: PASS.** Binding plan written: `00_LOCKED/FOUNDATION_RESET_PLAN.md` (ACTIVE; rulings R1–R6 received and recorded verbatim — M8 wired, H4+H1 detection minimum, M5 execution, structural-TP/±0.3ATR-SL recorded for FR-2, F-research gated on FR-4; no FR-1 code started).
**FR-1 COMPLETE 2026-09-21: PASS.** Multi-TF cascade restored as a wired library path: `smc/data/resample.py` (deterministic M1→M5/H1/H4/D1) + `smc/orchestration/multi_tf.py` (per-TF frozen drivers, shared D1/H4 map into M8, per-TF counts, single-TF alarm, loud missing-series failure). Smoke on real data (41,399 M1 bars → H4/H1 detection, M8 emitted 12 POIs, `single_tf_detect_exec=false`). Tests: 11 new, suite **607 passed**, zero regressions, no constant edits. Per-bar loop integration explicitly NOT in FR-1 (residual). Note: `06_RESEARCH/FR1_MULTI_TF_NOTE.md` (+ `results/fr1_smoke/`, `scripts/fr1_multi_tf_smoke.py`).
**FR-2 COMPLETE 2026-09-21: PASS.** Structural SL/TP routing implemented as ruled: shared `structural_sl` helper (0.3×ATR beyond reference, guarded fallback) applied to F/A/D/E raw-edge stops (B/C wave stops exempt with documented FR-3 rationale); `resolve_take_profit` (structural-if-valid else 4×ATR; None only when ATR unknowable); adapter feeds honest-prefix ATR; paper carries TP with zero code change. Interim constants `FR2_SL_BUFFER_ATR`/`FR2_TP_ATR_MULTIPLE` listed for future formal lock. Tests: 10 new + 3 stale assertions updated to buffered expectations; suite **617 passed**. Post-FR-2 books are NOT comparable to Phase C (documented). Note: `06_RESEARCH/FR2_SL_TP_ROUTING_NOTE.md`.
**FR-3 COMPLETE 2026-09-21: PASS.** Zone/entry geometry + M4 fidelity as ruled: shared `entry_within_zone()` enforced in F (entry inside thesis ± frozen 0.5×ATR; far-outside routes rejected, merge untouched by documented choice); M4 head must clear the frozen EQH tolerance (M5/M7-domain split, no new numbers); 4 new tests + marginal-head decoy + 3 fixture updates (zones now meaningful); suite **622 passed**, zero regressions incl. integration. Residuals: A/D/E containment unmeasured, merge envelope exports, flicker structural, post-FR-3 books incomparable to Phase C. Note: `06_RESEARCH/FR3_ZONE_M4_NOTE.md`.
**FR-4 COMPLETE 2026-09-21: PASS (YES_WITH_RESIDUALS).** October M5 month on the post-reset machine (H4+H1 detection, M8 map, FR-2 TP/SL, FR-3 gate): determinism pair byte-identical (trades/report/summary); funnel 9363 detected → 209 passed → 8 armed (4 M8) → 130 scans → 0 routes, explained — FR-3 zone gate is THE binding constraint (diag ablation without gate: 2 F+M8 routes → 2 TP-carrying placements → 2 SL closes, proving the full machine live). M8 armed but unrouted in compliant mode; TP path placed-only in diag; Trigger D 0 (A5). Phase C archived pre-reset, incomparable. Residuals: empty-book limits, no gate-reject counter, one-month loop. Report: `06_RESEARCH/FR4_FIDELITY_BASELINE_REPORT.md` (+ `results/fr4_fidelity/`, diag in `results/fr4_diag_nogate/`).
**FR-4 RESIDUAL CLOSEOUT 2026-09-22: DONE (forensics only).** Armed-POI fate ledger for the October compliant window: 8 armed (4 M8) — 2 same-bar TESTED, 3 tested-after-arm, 3 never touched; **0 built-then-rejected, 0 never-scanned; FR-3 gate rejects = 2** (poi-002480 +43.78 above zone high, poi-005293 +16.50; the diag's 2 no-gate trades originate from exactly these POIs at the same bars). Replay byte-identical to run1 (trades SHA ec885eef…), funnel parity exact (130 scans/0 routes). No strategy/gate/constant changes; logging-only shims. Report: `06_RESEARCH/FR4_ARMED_POI_FATE_REPORT.md` (+ `results/fr4_fidelity/armed_poi_fate.{csv,json → summary.json}`). **FR-3.1 COMPLETE 2026-09-22: PASS (on-zone entry anchor; gate NOT widened).** Trigger F limit anchored into the routed POI zone: shared `zone_anchored_entry` (direction-proximal edge; on-zone passthrough bit-exact; unlocatable geometry passes through so the unchanged FR-3 gate still rejects), stop reference moves to the zone distal edge for re-anchored entries + degenerate zero-SL guard; provenance `entry_anchor` in signal data. October smoke: **0→2 routes, gate rejects 2→0** (poi-002480/005293 now gate-ACCEPT with on-zone buy-limits 3995.775 / 4247.355), 0 fills within expiry (honest; not tuned). 14 new tests (M8 fixtures + bit-identical on-zone regressions), suite **636 passed**. Note: `06_RESEARCH/FR3_1_ON_ZONE_ENTRY_NOTE.md` (+ `results/fr31_smoke/`); FR-4 fate ledger re-verified byte-exact after the smoke run.
**FR-4b COMPLETE 2026-09-22: measurement run (post-FR-3.1, frozen config).** 3-month window (exec 2025-09-01→2025-11-30, 17,840 M5 bars, 1-month warm-up): funnel 27,266 detected → 709 passed → **21 armed (15 M8)** → 274 scans → 6 F signals → **gate 6/0 accept-reject** → **6 routes (4 M8)** → 5 orders placed (TP 5/5) → **0 fills** (§23 12-bar window vs proximal-edge retrace; book flat). Exit mix empty; determinism pair byte-identical (trades/report/summary/fates). M8 chain armed/routed/filled = 15/4/0. Chain answer: routing unblocked end-to-end, blocker now the fill regime — F first-touch timing vs at-zone limit within §24/§23 lifetimes (candidate for Architect expiry/touch design fork; local agent does NOT touch F timing). F-survivor research stays PAUSED (no filled sample). Diagnostic only; no parameter search. Report: `06_RESEARCH/FR4B_WIDER_WINDOW_REPORT.md` (+ `results/fr4b_wider/run{1,2}/`, wrapper `scripts/fr4b_wider_window.py`).
**FR-4b UNFILLED FORENSIC 2026-09-22: DONE (facts only; no strategy change).** All 5 FR-4b orders re-anchored LONGs, all §23-expired at N+11 exactly (0 touched-live anomalies → fill model + lifecycle mutually consistent). Fates: 3 never_touched_in_life (September trend-runaway; closest approach 54.7/141.9/162.8 units) + 2 touched_only_after_expiry (both M8 October: +26 bars / +121 bars after expiry; **ticket-5 near-miss: closest approach 4.43 units in life, touch 26 bars post-expiry**). Median closest approach 54.70; median touch lag 73.5 bars. Recording-book forensic run reproduced run1 bytes. Data: `06_RESEARCH/results/fr4b_wider/unfilled_forensic.{csv,json → summary.json}`. Report: `06_RESEARCH/FR4B_UNFILLED_FORENSIC_REPORT.md`. Ready for the D1/D2/D3 ruling.
**R7+R8 FILL-REGIME POLICY COMPLETE 2026-09-22: PASS (per Architect ruling; gate NOT widened).** Single source `smc/risk/fill_regime_policy.py` imported by backtest + paper. R7 place guard: risk-accepted candidate NOT placed when its market close at place time sits outside the routed POI zone beyond the EXISTING FR-3 band (`ZONE_REFINEMENT_ATR × ATR`); machine-readable `blocked_by=skip_place_far_from_zone`, retryable (one-shot burns only on accepted placement — news/session semantics). R8 HTF resting bars: `rest_bars_for(detection_tf, is_m8)` — H1→36, H4/M8/D1→48, else execution-TF §23 default (12 M5 / 30 M1, never silently shortened); §23 inclusive convention preserved; give-up (20) an independent backstop, never raising rest. Provenance `detection_tf`/`is_m8` threaded bridge → CandidateEntry → PendingOrder → `_TrackedPending`. Smoke (FR-4b window, isolated out-root): funnel identical (21 armed/15 M8, 6 routes/4 M8), **10 R7 skips, 0 places, 0 fills** — independent geometry check: market close at place time +14.65..+165.50 beyond zone vs band 1.73..3.84 (F fires on BOS-continuation bars whose close has already left the zone). R8 separately proven live in the superseded intermediate (limit-ref) run: first filled trade in the chain (zone-high re-anchor 4247.355, BE-stop +0.48 after 5 bars). Residual for D1/D2/D3: market-ref R7 + frozen band annihilates ALL in-window placement incl. the October M8 near-miss class R8 targets — a limit-placement/timing design question, not a threshold issue; nothing tuned. 33-test file, suite **658 passed**. Note: `06_RESEARCH/FR_FILL_REGIME_R7_R8_NOTE.md` (+ `results/fr7r8_smoke/`); policy recorded in `FOUNDATION_RESET_PLAN.md` §8.
**R9 PLACE-ON-REENTRY INTENT COMPLETE 2026-09-22: PASS (per Architect ruling; design locked BEFORE code — `00_LOCKED/R9_PLACE_ON_REENTRY_DESIGN.md`; GATE_WIDENED=NO).** An R7-skipped candidate arms a `PlaceIntent` (full accepted placement frozen: FR-3.1 on-zone limit, FR-2 SL/TP, policy lots) instead of dropping silently; on band re-entry (existing R7 geometry) or limit touch (fill-model rule, cross-checked by test) within an R8-sized clock from signal, the pending order places with the REMAINING bars. Design-locked derivations: §23 clock parity (armed N, dead N+rest); DOA boundary — remaining < 3 bars never fabricates a born-expired order; one intent per route per run, clock never refreshed; candidates-before-intents bar order (a same-bar in-band re-proposal supersedes the intent — my own test caught the double-order defect in the first wiring before any run). One-shot burns ONLY at intent placement (both engines); dead-thesis + portfolio drops mirror the resting-order rules. Modules: `smc/backtest/intents.py` (PlaceIntent/IntentBook), `market_reentered_zone` in the policy module, backtest + paper wiring. Smoke (frozen FR-4b window): funnel identical (6 routes) → **5 intents armed, 4 expired naturally (September runaway class — now counted waits), 1 PLACED on re-entry (bar 9694, 37 bars into the 48-bar M8 clock) → FILLED at the on-zone limit 4247.355 → BE-managed → closed +0.07 after 52 bars** — the first complete arm→reentry→fill→manage→close chain under frozen rules, n=1 (M8). 23-test file, suite **681 passed**. Note: `06_RESEARCH/R9_PLACE_ON_REENTRY_NOTE.md` (+ `results/r9_smoke/run1/`); policy recorded in `FOUNDATION_RESET_PLAN.md` §8.
**AS-CODED ARCHITECTURE EXTRACTION COMPLETE 2026-09-23: DONE (Part 1 of 3 — code → flowchart + pictures; Part 2 comparison COMPLETE by the Lead Architect — see the next paragraph; Part 3 6-month structure ledger NOT started; research-only, zero strategy edits, suite 681 unchanged).** Live `04_SRC/smc/` (118 modules) read level-by-level and extracted AS-CODED: report `06_RESEARCH/AS_CODED_ARCHITECTURE_FLOWCHART.md` (package tree built from AST docstrings, stage map 0A→5 with file/class/function citations, two Mermaid diagrams — end-to-end runtime + state owners, call-graph notes), pictures `06_RESEARCH/results/architecture_audit/as_coded_architecture.png` + `as_coded_bar_loop.png` (matplotlib-only renderer `scripts/render_as_coded_architecture.py`), machine-readable `results/architecture_audit/module_inventory.json` (`scripts/build_module_inventory.py`). Headline as-coded facts: **two drivers for one detection stack** (shipped research chain = `MultiTFDetectionDriver` H4+H1 batch on new-H1-close; live/paper = single-TF `DetectionDriver`); `orchestration/multi_tf.py` imported ONLY by tests + research scripts (no smc runner); 7 locked constants never imported anywhere (ADX_MIN_ENTRY, ATR_FLOOR_MIN_SL, EQUILIBRIUM_MIN/MAX, M8_MIN_RR, M8_SL_MIN/MAX_PIPS); NO trigger emits a sweep level (sweep-guard plumbing dormant); FVG invalidation only for Trigger-F signals (bridge returns None otherwise); `smc/logging/` still a 4-line placeholder; `PipelineEngine.execute_route` superseded — no runner calls it.
**LEAD ARCHITECT AS-CODED COMPARISON COMPLETE 2026-09-23 (Part 2 of 3): verdict recorded (do not re-debate).** Modules largely match the stage list, but **runtime wiring does not fully match** the intended multi-TF live cascade: **C1** live/paper ≠ research multi-TF; **C2** HTF cadence / M8 D1-H4 map still largely caller-owned; **C3** structural TP never fed (4×ATR fallback only); **C4** news / spread / sweep-guard / some constants compiled but silent in shipped configs. Aligned: limit-only fills, R7/R9 research path, pillars, router, models on disk. Post-Phase-0/1 status: **C1 CLOSED** by the one multi-TF runtime; **C2 PARTIAL** (seam now owns live/paper cadence; frozen research scripts still own theirs); **C3/C4 OPEN** (declared V1 non-goals). Full record: `00_LOCKED/CHANGELOG.md`.
**PHASE 0 + PHASE 1 C1 COMPLETE 2026-09-23: PASS (per Lead Architect ruling; ONE multi-TF product runtime; no threshold/constant edits).** Phase 0 contract `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` (canonical runtime H4+H1 detection / M5 execution, one-driver rule, loud-fail policy, non-goals, acceptance tests, residuals) written BEFORE code, then implemented: shared seam `smc/orchestration/multi_tf_runtime.py` — `MultiTFProductRuntime.run_batch` (facade over the frozen `MultiTFDetectionDriver.validate_multi`; no second stack), `build_htf_prefixes` (honest `timestamp <= as_of` prefixes via bisect), shared `ZoneDedup` (the research chain's geometric episode rule — POI ids are uuid4, so identity alone cannot dedup), `MissingHtfSeriesError`. Live: `LiveLoop` now provisions HTF series from the connector (`copy_rates` per TF, bounded `htf_window_bars=300`) and runs **one batch per new H1 close** through the seam; `start()` probes HTF and **refuses to start** in product mode when H1/H4 are unusable; a refused batch records `arm_errors`/`last_arm_error` and arms NOTHING (no silent single-TF fallback); legacy single-TF driver mode retained only for the Phase 7 tests and logged when used. Paper: `PaperRunner.arm_multi_tf(...)` delegates to the same runtime (constructed by default in product mode). Operator: `detection_timeframes` + `allow_single_tf_degraded` config keys (strict whitelist preserved; a config whose detection set collapses onto the execution TF is REJECTED unless degraded is explicit), runtime wired in `run_operator._build_stack`, board/events.log gain a `detect` line (HTF batches / armed / arm-errors at H1 cadence — no spam). Real-data parity smoke on the canonical dataset (exec 2025-10-01→10-15, 2,761 M5 bars, 27 s): 231 H1 batches → H4 3,272/H1 3,503 raw → 8/49 passed → **5 armed**, **52 duplicate zones suppressed by the shared dedup**, 0 batch errors; **parity: live per-TF counts == paper per-TF counts** on the same batch (separate runtime instance); loud-fail probe raised for withheld H4; degraded probe stamped `degraded=True`; LiveLoop dispatch smoke `started=True`, `htf_batches=1` over 60 M5 bars. 17 new tests (`test_multi_tf_product_path.py`), suite **698 green** (681 + 17), zero regressions. Note: `06_RESEARCH/C1_MULTI_TF_PRODUCT_PATH_NOTE.md`; smoke `results/c1_multi_tf_parity/run1/`; script `06_RESEARCH/scripts/c1_multi_tf_parity_smoke.py`.
**NEXT ACTION = human review of the H4 POI pack + re-score of post-F1F2 armed/stratified charts (Architect gate: Armed ≥50% CORRECT on re-score; dual=0; conflicts=0 already proven) — or Phase D watchdog GUI chart-attach + stale-heartbeat emergency drill (ops).** H4 POI identification pack DONE 2026-10-04 (`06_RESEARCH/scripts/h4_poi_confirmation.py`: 658 raw / 3 merged / 0 armed, gates PASS, 55 charts, double-run byte-identical after two script-local fixes — exec-window endpoint filter + geometry-derived event ids since `POI.id` is uuid4; suite 754; armed=0 documented as batch-vs-live-loop limitation, no threshold relaxed). F1/F2 M8 emission fix DONE 2026-10-04 (episode collapse + origin-tight verdict, suite 750; note `06_RESEARCH/F1_F2_M8_EMISSION_FIX_NOTE.md`; re-sample `06_RESEARCH/results/d1_f1f2_resample/`). The V1.1 runtime baseline is FROZEN (`00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md`); restart of any paused track or baseline change requires a dated ruling. **R9 is ACCEPTED** (design + code + smoke chain n=1 — not the main next work). F-survivor / F-timing / Monte Carlo stay PAUSED (R6); Phase D ops background only. Day-to-day checklist: `00_LOCKED/POST_V1_ACTIVE_TODO.md` (subordinate to `POST_V1_PLAN_OF_ACTION.md`). Start every session with `00_LOCKED/LEAD_ARCHITECT_ROLE_AND_PROTOCOL.md`, then this section, then the TODO next-action marker. Pointers: `POST_V1_PLAN_OF_ACTION.md` (binding order) · `POST_V1_ACTIVE_TODO.md` (checklist) · `POST_BASELINE_DIAGNOSIS.md` (Track R verdicts) · `FLOWCHART_MATCH_NOTES.md` (conviction notes) · `PHASE_HONEST_R_RECOMPUTE_REPORT.md` (honest denominators) · `FOUNDATION_RESET_QA_PACK.md` (fidelity evidence).
**Known upcoming work (locked 2026-09-20, not a redesign track):** export patch COMPLETE + Python research visualizer V1 COMPLETE (`scripts/trade_inspector.py`, curated F/B chart set in `results/trade_inspector/curated/`, usage in `TRADE_INSPECTOR_README.md`) → next: structured flowchart/KB matching notes on the dominant F pattern using the curated charts; later → MT5 draw-only overlay for paper (Track V3). See Track V in the TODO + `01_ARCHITECTURE/SMC_VISUALIZATION_ROADMAP.md`.
**Phase B state:** CLOSED — **PASS** (2026-09-14). The relaunched full-October pair completed 2026-09-13 21:40/21:41 (31,619 bars each, ~11.8 h/run, 0.75 bars/s); `trades.csv` + `report.json` BYTE-IDENTICAL between runs, `summary.json` identical ex-runtime. All 7 plan §4 invariants OK × 2; Trigger D = 0; funnel every stage non-zero-or-explained (raw 189,284 → armed 237 → routes 49 → placed 42 → opened 41 via 1 × §24 give-up → closed 41; `positions_still_open = 0` = flat end-of-window book). Same-bar SL-first verified over ALL 41 trades (`06_RESEARCH/scripts/phase_b_sl_first_check.py`: every exit price == SL exactly, zero ambiguous bars). Machine verdict `06_RESEARCH/results/phase_b_verdict.json` = **PASS** — initial FAIL was two checker defects, both fixed + disclosed: the runtime-strip was top-level-only while `runtime_seconds`/`bars_per_second` live nested inside `funnel`, and `positions_still_open` lacked a written explanation. Metrics (diagnostic, per plan §5 interpretation — NOT edge): 41 trades, 15 W / 26 L, WR 36.59%, net P/L −7.66, PF 0.0501, maxDD 7.66; all 41 closes are exact-SL and the 15 wins are exactly the BE-modified positions (be_modifies_applied == n_wins == 15; TP never reached in October). Report fully filled: `06_RESEARCH/PHASE_B_FIDELITY_REPORT.md`; one-page fidelity note + §4 status + marker → Phase C in `POST_V1_PLAN_OF_ACTION.md`.
**ACTIVE NEXT — EXECUTED 2026-09-19:** Phase C pair completed (run1 finished 2026-09-19, run2 01:26/01:30 merged; verdict PASS re-stamped 09:55:10 against the final on-disk bytes — see `06_RESEARCH/results/phase_c_verdict.json`). Closeout executed: verdict re-check ✔ · report `06_RESEARCH/PHASE_C_BASELINE_REPORT.md` ✔ · boundary ruling **option (a) accept + document** recorded in report §7 (2026-09-19; the earlier Option-B warm-up trim closed as MOOT — verified 0 warm-up-zone trades, merge offsets exact, route_id unique 761/761) · spread ladder {0.00, 0.05, 0.15, 0.35} on 2023-02-01→2023-04-30 ✔ (52 → 22 → 2 → **0 trades at 0.35**; the §28.5 gate blocks ALL flow at the representative retail spread in the 2023 regime) · suite **565 passed** ✔ · `SMC_phase_c_guard` task + Startup copy removed ✔. Baseline shape (diagnostic only): 761 trades, WR 25.49 %, net −47.81 raw (−4.78 % of equity; every trade 0.10 lots — the §28.7 cap binds 100 % of trades), PF 0.344, maxDD 49.15; F = 659 of 761. **Phase D remains NOT CLEARED pending Lead Architect sign-off on the report.** — SIGN-OFF GRANTED 2026-09-19: **Phase C CLOSED**; Phase D cleared for **operations validation only** (not profitability proof; no optimization, no redesign, no locked-constant changes). Historical run log follows. Phase C — **IN FLIGHT (2026-09-14 15:45 local)**. Runtime reality check: as-is ≈ 27 days/run → **Option B** invoked (semantics-preserving perf only). Patches P1–P3: (P1) detection hoists — per-window shared ATR/FVG artifacts in `stage0` + `check_displacement(…, atr=, fvgs=)` params + per-window validation cache (`smc/validation/window_cache.py`) + `raw.sweeps` reuse; (P2) incremental `smc/backtest/series_state.py` — `SeriesState` (Wilder ATR fold, dual-space RSI fold, §27 candidates evaluated once with §19 confirms as monotone first-confirm events via threshold heaps, mirrored series, base-sorted swing indexes) replacing ALL O(prefix) adapter recomputations; (P3) `TriggerContext.hints` (ATR/RSI series, inversions, swing indexes) consumed by triggers A/C/E/F + CHOCH classifier. Proof: suite 532→**551** (19 `test_series_state_equivalence.py` — caught + fixed 2 real equivalence bugs: pre-window §19 confirms, valid-at-arrival swings); October golden replay vs preserved Phase B pair: `trades.csv`/`report.json` **byte-identical**, summary identical ex-runtime (`phase_c_golden_replay/`). Post-patch plateau **110 ms/bar** (12×) → **ETA ≈ 54 h/run single-process**. Runner `phase_c_baseline_backtest.py`: calendar-year segments, 2,880-bar warm-up context for interior segments (continuous-run equivalence), checkpoint/resume via manifest fingerprint, deterministic merge (absolute bars, chained equity, frozen reports.py helpers). Dual pair RUNNING (Windows PIDs 10912/11648, watcher 19672): logs `06_RESEARCH/results/phase_c_baseline_run{1,2}.log`, per-segment artifacts under `phase_c_baseline_run{1,2}/segments/`, merged at `/merged/`, verdict auto-written `06_RESEARCH/results/phase_c_verdict.json` (watcher: coverage = full 1,768,123 bars, byte-identity, summary-ex-runtime, invariants, Trigger D = 0). On completion: spread sensitivity (≥3 spreads, representative window + adequacy note), `PHASE_C_BASELINE_REPORT.md`, governance updates, PASS/FAIL package. Interpretation binding per plan §5 — diagnostic baseline, NO edge claim. **2026-09-15 — Independent perf-patch audit: PASS WITH FINDINGS** (`06_RESEARCH/PHASE_C_PERF_AUDIT.md`): 17 static equivalence claims OK (F1 LOW-latent, F2 INFO), suite 551 independently re-verified, fold-convergence + warm-up-margin probes PASS. Boundary-probe finding (with a self-disclosed probe defect fixed — false PREFIX_IDENTITY was a midnight-truncated window; the corrected re-run returns PREFIX_IDENTITY True 20 vs 20 with CARRY_LOSS = 1 reproduced identically): the fresh-stack-per-segment design loses episode/one-shot state across segment boundaries (CARRY_LOSS = 1 on real October data) — 2021→22, 2022→23, 2023→24 are Friday-pre-flattened, but **2024→25 (Tue Dec 31) and 2025→26 (Wed Dec 31) are exposed**: positions open at a segment end are dropped from the merged trade list (no end-of-data close; no `still_open` merge stage). Disposition (accept-and-document vs boundary-overlap trim in the merge) is DEFERRED TO THE LEAD ARCHITECT — options recorded in audit §6. **2026-09-15 — Project-wide audit recorded:** `06_RESEARCH/PROJECT_WIDE_AUDIT.md` — criticals C1–C3 (boundary carry / silent end-of-data position drop / paper-runner test gap), strengths, clarity items, ranked enhancements E1–E6; **§7 re-check checklist to be worked when the 5-year baseline completes**. **2026-09-15 — LEAD ARCHITECT RULING: boundary-carry disposition = OPTION B (boundary-overlap trim in the merge).** HOLD UNTIL PAIR COMPLETION: when the 5-year run finishes, notify the user and implement the trim on the merge (drop per-segment trades whose `entry_bar < own_start`; bookkeeping-only), verify `positions_still_open` on the midweek 2024→25 / 2025→26 boundaries, review the watcher verdict, then work the audit §7 checklist together. User is deliberately holding all other work until then. **2026-09-17 — interruption + relaunch:** pair + watcher died ~2026-09-16 16:45 local (machine-level; completed 2021/2022/2023 segments safe, byte-identical); relaunched same day ~11:50 via the recorded nohup commands — manifest resume skipped the three finished segments, 2024 recomputing from segment start, ETA ≈ 28 h (late Sep 18). Keep the machine awake/on until completion. **2026-09-17 — forensics + supervisor:** death was NOT a reboot (boot Sep 14, no WER, no OOM) — unlogged session-level suspend/termination, proven by the watcher's freeze/resume fingerprint (16.75 h log gap, abort at 09:30 on resume). **Auto-relaunch supervisor deployed + live-fire tested** (`phase_c_supervisor.py` + guard bat: scheduled task `SMC_phase_c_guard` every 5 min, Startup copy, pythonw daemon, single-instance lock, FileTime PID checks, own audit log) — any dead component now self-heals within ≤5 min; cleanup after Phase C: `schtasks /Delete /TN SMC_phase_c_guard /F` + delete Startup `phase_c_guard.bat`.
**PHASE D EXECUTION — SESSION 1 (2026-09-19, Saturday — FX market closed; ops subset completed):** terminal binding proven read-only (`06_RESEARCH/scripts/phase_d_identity_check.py`): `C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe` — terminal-dir identity MATCH, **DEMO** login 474608655 @ Exness-MT5Trial15 (USD, 1:2000), symbol **XAUUSDm** (visible; digits 3, point 0.001, filling FOK+IOC, volume 0.01–200 step 0.01). Watchdog EA deployed to the terminal (`MQL5\Experts\SMC_Safety_Watchdog.ex5`, metaeditor compile **0 errors / 0 warnings**); heartbeat contract verified (`is_stale` flips exactly at the 5 s timeout; file format matches the EA parser; round-trips through the terminal `MQL5\Files` sandbox). Idle LiveLoop session (2 min, dry-run): 60 polls, 0 errors, 0 new bars (weekend), heartbeat seq 60 + shutdown marker. Order paths: payload-validated via `order_check` (BUY_LIMIT 0.10 lots @ magic **20260919** — retcode 0, FOK + IOC); sends deferred (market closed + terminal Algo Trading OFF — GUI step). **Headline divergence:** live spread is CONSTANT **0.26** (32,775 + 5,578 Friday ticks: p10 = p99 = 0.26) and the §28.5 gate is ATR-relative — at every 2023 month-end (M5 ATR 0.30–1.06) the gate ceiling was 0.02–0.08 ⇒ the 0.26 live spread would block ALL grades ALL of 2023 (Phase C's ladder "0 trades at 0.35" is an ATR-regime special case); current regime ATR ≈ 3.75 ⇒ gate passes every grade. Log: `06_RESEARCH/PHASE_D_DIVERGENCES.md`; artifacts `06_RESEARCH/results/phase_d_ops/`. Deferred to next open session: EA attach (GUI) + Algo Trading ON, live bar-cycle session, order send/cancel/SL-modify/close, stale-heartbeat emergency drill, KPI latencies under load.

**PHASE D OPERATOR PACK (2026-09-19, accepted instruction):** controlled demo/live run surface — `run_live.bat` (repo-root launcher: config/python existence checks, window stays open on failure) → `04_SRC/smc/live/run_operator.py` (identity gate → frozen-stack wiring → poll loop → console board → backend logs → heartbeat shutdown marker; `--max-seconds` for bounded windows) with `04_SRC/smc/live/operator_config.py` (STRICT whitelist: unknown keys and LOCKED keys — spread gate, lot cap, BE, breaker, trigger geometry — are rejected loudly; `risk_fraction` validated against the frozen RISK_PCT band 0.5–1.0 %) and `04_SRC/smc/live/operator_console.py` (pure status-board renderer). Config: `config/live_demo.json` (defaults: EXNESS Copy terminal, XAUUSDm, magic 20260919, dry_run TRUE, require_demo TRUE, logs/phase_d). **How to start:** double-click `run_live.bat` (or `python 04_SRC/smc/live/run_operator.py --config config/live_demo.json`); Ctrl+C = clean shutdown. **Mutable:** terminal_path/symbol/magic/dry_run/require_demo/risk_fraction(in band)/timeframe/allowed_sessions/heartbeat/poll/console/log_dir. **Never mutable via config:** anything in `smc.config.locked_constants`. Backend logs (gitignored `logs/`): identity.json, config_effective.json, events.log, console_mirror.log, kpi_records.jsonl, session_summary.json, heartbeat.txt. Live smoke PASSED on the EXNESS Copy terminal (idle Saturday session; `trade_allowed=true` observed — Algo Trading now ON). Tests: 15 new (`test_operator_pack.py`), suite **580**.

**Phase C RESUME COMMANDS (copy-paste after any crash/restart — the runner resumes completed segments and re-merges):**
```
nohup python 06_RESEARCH/scripts/phase_c_baseline_backtest.py --tag run1 --out-root 06_RESEARCH/results/phase_c_baseline_run1 > 06_RESEARCH/results/phase_c_baseline_run1.log 2>&1 &
nohup python 06_RESEARCH/scripts/phase_c_baseline_backtest.py --tag run2 --out-root 06_RESEARCH/results/phase_c_baseline_run2 > 06_RESEARCH/results/phase_c_baseline_run2.log 2>&1 &
nohup python 06_RESEARCH/scripts/phase_c_verdict.py > 06_RESEARCH/results/phase_c_verdict_watcher.log 2>&1 &
```
**Post-V1 sequencing is BINDING and lives in `POST_V1_PLAN_OF_ACTION.md`:** Phase A — Data Acceptance → Phase B — short fidelity backtest → Phase C — full 5-year baseline → Phase D — demo forward → only then Phase E (V1.1). No backtest, tuning, or edge claims before the diagnostic baseline exists.

**Phase A status (full report: `06_RESEARCH/DATA_ACCEPTANCE_REPORT.md`):**
Canonical series designated: `07_DATA/XAUUSD_M1.parquet` (1,768,123 M1 bars, 2021-04-12 11:00 → 2026-04-10 20:59 UTC, SHA-256 `e5d730ea…d17fee9`). All A1–A4/A6 checks passed — 0 duplicate/OHLC/non-finite/spike defects; the 1,679 gaps are fully classified (weekends + NY-5pm rollover-hour omissions; **no unexplained class**). The accepted loader `smc/data/parquet_loader.py` (6 unit tests, suite 525 green) is the only sanctioned Phase B/C input path. `07_DATA/` is git-ignored — never commit market data. **A5 CLOSED — ruled option (a) on 2026-09-09 (plan §3): the dataset is accepted as volume-less; the Phase B/C baselines run WITHOUT Trigger D as a tradeable path (it remains compiled but structurally unfireable — per-trigger breakdowns will show 0). Rationale: volume is 0 on all 1.77M M1 rows AND all 281.5M tick rows, so no re-derivation was possible; triggers A/B/C are unaffected; vendor re-sourcing deferred until Phase C fidelity justifies it.**

Phase 7 delivered live readiness under the locked Option A architecture:
`smc/live/` (LiveConfig, heartbeat publisher + watchdog-decision spec,
`LiveLoop` over the REAL stack) plus `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5`
(heartbeat monitor + emergency flatten ONLY — no strategy logic). The
live loop polls the connector for new closed bars, validates/arms new
POIs through the rolling-window `DetectionDriver` into the SAME engine the
M4 `PipelineAdapter` drives, and runs `PaperRunner.run_one_cycle(bar)` per
bar; the heartbeat file (`<unix_secs> <seq>` + `state=`) is written every
~1 s and the EA fails-closed on any stale/unreadable heartbeat (close ALL
scoped positions + delete ALL scoped pendings). Full suite is **519/519**
(510 pre-Phase-7 + 9 new). Deferred to V1.1: walk-forward, Monte Carlo,
Future Flexibility KPI thresholds, production alerting, M8 HTF
provisioning in the live driver, remote/VPS heartbeat transport. See
`TODO.md` (Phase 7 checklist), `CHANGELOG.md` (2026-09-09 entries) and
`01_ARCHITECTURE/SMC_PHASE_7_DESIGN_NOTE.md` (+ the pre-Phase-7 coherence
patch note) for details.

---

## Phase 7 Implementation Notes (V1 definitions — 2026-09-09)

- **Option A honored:** Python owns ALL trading logic; the MQL5 EA
  (`05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5`) ONLY monitors the heartbeat
  file and emergency-flattens (close scoped positions + delete scoped
  pendings) when the heartbeat is stale or unreadable. Healthy heartbeat
  → the EA does nothing. No POI detection / validation / entries /
  PureRunner-FVG management / session-news-risk policy / sizing in MQL5.
- **Heartbeat transport:** a plain-text file is the V1 transport (Redis
  rejected for V1 — no deployment, and the EA cannot read Redis without a
  third-party socket lib). Format: line 1 `<unix_epoch_seconds>
  <monotonic_sequence>`; optional `state=<running|shutdown>` line for
  operators. Python writes with the injected clock; the EA compares
  against `TimeGMT()` (UTC). Missing/garbage file == stale (fail-closed).
  Defaults (UNFROZEN operational timing): 1 s interval, 5 s stale
  timeout, 1 s EA timer, 0.5 s bar poll, 200-bar detection window.
- **Live loop (`smc/live/loop.py`):** connector poll → rolling window →
  `DetectionDriver.validate_window` (validate WITHOUT arming) → arm ONLY
  newly-passed POIs (an existing episode is never re-armed — §24 arm-bar
  anchor and §11 one-shot stay) → `PaperRunner.run_one_cycle(bar)` with
  the REAL adapter/engine/risk stack → interval-bounded heartbeat.
  `start()` refuses when the connector fails; cold start anchors the
  latest bar timestamp WITHOUT replaying history; `run_once()` is the
  deterministic test seam; `stop()` writes `state=shutdown` — the
  watchdog does NOT distinguish clean stop from death (both stale →
  emergency; fail-closed), the marker is operator diagnostics.
- **Watchdog decision spec:** `smc.live.heartbeat.evaluate_watchdog` is
  the pure-Python, pytest-tested decision the EA mirrors exactly
  (healthy → `no_action`; stale / unreadable → `emergency`). Keep the EA
  and the spec in sync (comments in both files).
- **Pre-Phase-7 coherence patch (folded into this freeze):** CR1
  `DetectionDriver` (candles → validated/armed POIs), I1 single §5 state
  machine across engine+pipeline, I2 backtest running equity from
  realized P/L (units: raw pnl × pip-value-per-lot), CR2 paper close
  outcomes feed risk guards (exact for runner-issued closes; bar-range
  determination for broker closes; ambiguous closes stay unfed), I4
  terminal-state retention (workflow-live + touch-window POIs never
  pruned). See `SMC_PHASE_7_PREP_COHERENCE_PATCH.md`.

---

## Phase 6 Implementation Notes (V1 definitions — 2026-09-09)

- **Shared bar-order contract (backtest AND paper):** both runners
  apply the same locked per-bar order — 1) `reset_day()` on UTC date
  change; 2) `evaluate_friday_close(now)` ONCE (portfolio: close ALL +
  cancel ALL, then skip the bar); 3) §11 `hard_cancel_pending`; 4)
  per-position `evaluate_exit` (FVG invalidation on the CLOSED bar →
  PureRunner BE proposal; `on_be_applied()` ONLY after a successful
  modify); 5) fills (pending-limit fills AT THE LIMIT PRICE + physical
  SL/TP with same-bar SL-FIRST); 6) new entries LAST. In backtest the
  stores simulate; in paper the broker decides and the runner observes.
  A 3b) step applies the frozen §23/§24 unfilled-order expiry each bar
  (backtest: `PendingOrderBook.expired_by_section23` /
  `expired_by_give_up` before fills, affected POIs driven TESTED through
  the state machine; paper: runner-side age cancel of GTC pendings,
  audit C1).
- **Backtest vs paper split:** `BacktestRunner` + M2 stores
  (`PendingOrderBook` / `PositionStore`) are backtest-pure — no MT5
  imports (guarded by tests). `PaperRunner` composes the SAME pure
  components (`PipelineEngine` through the M4 `PipelineAdapter`,
  `RiskEngine`) but applies decisions through the live execution layer
  (`OrderManager` / `PositionManager` / `MT5Connector`) via the thin
  `BrokerAdapter`. The paper runner implements the adapter's runner
  seam (`submit_entry` / `on_candidate_accepted` /
  `cancel_pending_for_poi`), so the identical adapter object drives
  both paths. Fill/close observation is broker truth: fill = a broker
  position whose (symbol, magic, comment) matches a placed pending's
  order identity (MT5 `POSITION_MAGIC` / `POSITION_COMMENT` — the
  position ticket is a DIFFERENT identifier from the order ticket, so
  ticket equality is never used, audit C2); close = a tracked position
  disappears from `positions_get`.
- **Report identity fields (M5):** every candidate/pending/fill/closed
  trade carries `poi_id`, `trigger` (TriggerType) and `route_id`
  ("{poi}:{trigger}@{bar}" §11 event identity, kept in the order
  comment client-side); `runner.result()` → `RunnerResult(closed,
  blocked, route_ids)` feeds `build_report`. Per-trigger + per-POI
  breakdowns group on these; identity-absent trades land in
  `unattributed`. Model tags are NOT on closed positions — no per-model
  section exists (nothing invented). Profit factor zero-loss case is an
  explicit `None` (never inf); max DD is on the closed-trade equity
  curve (V1).
- **KPI metrics logged (M6, NO thresholds):** `decision` (bar-close →
  decision-complete latency, candidates/placed/blocked/rejected),
  `order_ack` (decision → broker ack, success/retcode), `management`
  (modify_sl / close / cancel outcomes + latency), `fill`,
  `trade_closed`, `missed_bar` (feed-gap detection), `hard_cancel`,
  `friday_close`. Every timestamp is injected (bar clock + injected
  `perf` monotonic source); records are append-only with deterministic
  JSON/JSONL/CSV exports. No pass/fail engine — Future Flexibility
  Clause thresholds stay unfrozen until measured evidence exists.
- **Known V1 limitations (documented, not faked):**
  - Live close P/L/kind/price are NOT reconstructed from MT5 history —
    closes whose outcome is ambiguous (the closing bar reaches no SL/TP
    level) carry `win=None` and are NOT fed to the guards; SL/TP-determined
    and runner-issued closes ARE fed (coherence patch CR2). Full
    deal-history reconciliation remains a later candidate.
  - Partial fills are logged at the reported volume (no volume-specific
    partial handling); order rejects are logged with the broker retcode
    (no retry policy in V1).
  - Walk-forward and Monte Carlo are deferred to V1.1.
- **Integration seams Phase 7 must respect:**
  - *Loop reuse:* Phase 7's live main loop should drive
    `PaperRunner.run_one_cycle(bar)` per closed bar (bar-close driven
    V1) rather than inventing a third orchestrator; heartbeat/watchdog
    wraps the PROCESS, not the strategy.
  - *Connector contract:* the paper stack requires
    `initialize()` / `account_info()` / `positions_get(symbol)` /
    `order_send(request)` (+ optional `shutdown()`); the MQL5 watchdog
    must stay outside this contract (MT5-side safety only).
  - *Sizing inputs:* live equity comes from `connector.account_info()`
    each cycle; symbol/magic live on the injected managers — the
    watchdog's emergency protection must not race the Python book.

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
