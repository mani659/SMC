# POST-V1 ACTIVE TODO

**Status:** ACTIVE — day-to-day checklist for the post-baseline period.
**Last updated:** 2026-10-06 (**PRE-COMMIT HYGIENE + CONTRACT LOCK (unified GLM + Co-pilot audit ruling)** — `.gitignore` covers `06_RESEARCH/results/` (90 MB, policy: local-only, curated `git add -f` exceptions); product-mode H4+H1 detection enforced at construction (`MultiTFProductRuntime.__init__` loud fail naming missing TFs; degraded opt-in only bypass); `LOCKED_DECISIONS.md` §4a dated supersession (H4+H1 required detection, W1+D1 optional context, M5 exec, pointer to product contract); F3 as_of-trim guard test suite added; suite **853 → 862**; `locked_constants.py` diff empty. **NEXT READY: git commit/push (3-commit split per audit).**)
**PREVIOUS:** 2026-10-06 (**PAPER/DEMO OPS SESSION PASS (dry_run)** — 20 min on DEMO XAUUSDm: armed 1 appeared on the structure console from the first board with zero lag (fix proven in ops), 39 boards all matched, 0 orders/fills/errors, clean shutdown; watchdog attach BLOCKED (honest). Note `06_RESEARCH/PAPER_OPS_SESSION_NOTE.md`. **NEXT READY: project-wide independent audit → git commit/push.**)
**PREVIOUS:** 2026-10-06 (**LIVE CONSOLE vs ARMED MISMATCH FIXED + RECONCILED LIVE** — root cause: snapshot rate limit treated the arming event like bar refreshes (900 s stale window); fix: batch changes rebuild immediately + board header armed counter; warm-up audit confirms design (300 bars/HTF, W1 back to 2021, full-window re-scan every batch); live 600 s dry_run reconciliation: batch armed 1 → board showed the H4 zone immediately; suite 853; `locked_constants.py` diff empty. Note `06_RESEARCH/LIVE_CONSOLE_ARMED_MISMATCH_NOTE.md`. **NEXT READY: paper trading (console trustworthy) | Architect review.**)
**PREVIOUS:** 2026-10-06 (**SETUP LEDGER BACKFILL + EXPERT PACK PASS** — direction 17/30 backfilled deterministically (trade_row 3 + exact-geometry join 14; 13 DATA_GAP documented), posture UNKNOWN (not in artifacts), arm_ts 30/30 (bar map validated 6/6); human columns still blank; **expert pack: `EXPERT_SETUP_REVIEW_PACK.pdf` (15 charts incl. all 3 routed) + `SETUP_IDENTIFICATION_EXPERT_REPORT.md` with rubric**; dual-run deterministic; suite 849; `locked_constants.py` diff empty. **NEXT ACTION = expert review of the pack → then paper trading prompt (paper only after expert scores or an explicit waiver).**)
**PREVIOUS:** 2026-10-06 (**L2 SETUP IDENTIFICATION LEDGER PASS** — 30 setups from the frozen 6m post-TP funnel (H4 19/H1 6/D1 5), 3 routed with full plan, hyp-outcome join YES (SL_THEN_TP_PATH 2 / TP_REACHED 1); human columns verdict/timing/notes blank by design; double-run byte-identical; paper path documented; research+export only, `locked_constants.py` diff empty. Note `06_RESEARCH/SETUP_IDENTIFICATION_LEDGER_NOTE.md`. **NEXT READY: Architect review | paper ops.**)
**PREVIOUS:** 2026-10-06 (**LIVE CONSOLE DRY-RUN PASS** — three bounded DEMO sessions on XAUUSDm; W1 enum fixed 32768→32769 (MT5 TIMEFRAME_W1; 32768 rejected live by copy_rates_from_pos — contract-restoring fix); real HTF batch + 7 live structure boards, honest empties (zero passed POIs = Pillar rejection, not cold-start); clean shutdowns + heartbeat shutdown markers; suite 849; `locked_constants.py` diff empty. Note `06_RESEARCH/LIVE_CONSOLE_DRYRUN_NOTE.md`. **NEXT = L2 setup identification ledger (directive issued).**)
**PREVIOUS:** 2026-10-06 (**WEEKLY (W1) PROVISIONING + LIVE STRUCTURE CONSOLE — MILESTONES W + L1 BOTH PASS** — W1 is now a first-class HTF context TF (enum `W1=32769`, Monday-aligned resample, M8 scan, runtime optional set, live fetch) with execution unchanged at M5; the operator console renders POIS / SWEEPS / SEEKING / PLAN from LIVE snapshots (W1 rows real, not hardcoded); suite 849; `locked_constants.py` diff empty.)
**PREVIOUS last updated:** 2026-10-05 (**DOCS-ONLY POLICY SYNC** — accepted work (seek/scan redesign §5a, frozen 3m+6m funnels, expert marked charts archive) recorded as done; Architect policy rulings A–E recorded; **NEXT ACTION = Structural TP feed — design lock then implement (first swing → existing structural_else_4ATR; SL unchanged; 30-pip = MAE yardstick only)**)
**Authority:** Subordinate to `00_LOCKED/POST_V1_PLAN_OF_ACTION.md` (binding phase order A→B→C→D→E). This file is the working checklist; the plan is the law. Option A locked. No locked-constant edits without a dated Lead Architect ruling recorded in the plan.

---

## Product completion path (Choice 1 — owner-accepted 2026-09-23)

Binding owner-agreed sequence — **do not reorder in docs**. Phase 0 and Phase 1/C1 are DONE; Phase 2 is the single next action.

- [x] **Phase 0 — `PRODUCT_RUNTIME_CONTRACT.md` locked** (2026-09-23) — canonical runtime, one-driver rule, loud-fail policy, non-goals, acceptance-test list, residuals (`00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md`).
- [x] **Phase 1 / C1 — MultiTF live + paper + shared seam + loud HTF fail + tests** (2026-09-23, **PASS**) — shared seam `smc/orchestration/multi_tf_runtime.py` (`MultiTFProductRuntime.run_batch` / `build_htf_prefixes` / shared `ZoneDedup` / `MissingHtfSeriesError`); `LiveLoop` batches per new H1 close and **refuses to start** in product mode without usable H4/H1; `PaperRunner.arm_multi_tf` uses the same runtime; operator config gains `detection_timeframes` + `allow_single_tf_degraded`; 17 new tests, suite **698**; parity smoke `06_RESEARCH/results/c1_multi_tf_parity/`.
- [x] **Phase 2 — Layer/pillar CONTRACT tests** (COMPLETE 2026-09-23, **PASS**) — 28 machine-checkable contracts in `04_SRC/tests/test_phase2_layer_contracts.py` (Stage 0c detectors D-SWEEP/D-FVG/D-DISP; Pillars 1–5 hard/soft/UNAVAILABLE semantics with stable reason tokens; handoffs H-MERGE / H-ATTR / H-ROUTER). Suite **726 passed** (698 + 28), zero production-logic changes, locked constants untouched. Optional population snapshot RUN: `06_RESEARCH/results/phase2_contracts/snapshot.json` (14-day multi-TF window, read-only counts — P2:fail 84.3% of merged POIs dominates first failures; no PnL). Note: `06_RESEARCH/PHASE2_LAYER_CONTRACTS_NOTE.md`.
- [x] **Phase 3 — Short structure funnel + information-flow audit** (COMPLETE 2026-09-23, **PASS**) — locked window 2025-10-01→10-31 (full month) on the PRODUCT seam (`MultiTFProductRuntime.run_batch` → `PipelineEngine` arm → adapter scans → runner risk): 527 HTF batches → 7,564 merged → P2:fail 6,549 / P3:fail 418 / P1:fail 339 → 258 passed → **8 armed (5 M8)** → 4 routes (all F) → 1 placed + 3 R9 intents → **1 fill** (M8 poi-008910). Sample audit 8/8 with **zero flow gaps**; determinism pair semantic-identical; 6 geometry charts. Artifacts: `06_RESEARCH/results/phase3_structure_funnel/run{1,2}/` + `charts/`; report: `06_RESEARCH/PHASE3_STRUCTURE_FUNNEL_REPORT.md`.
- [x] **Phase 4 — Frozen backtest + paper ONLY on the unified machine** (COMPLETE 2026-09-23, **PASS**) — locked 3-month window (exec 2025-09-01→11-30, 17,840 M5 bars) via the imported Phase 3 composition (product seam → arm → scan → risk → R9 intents): 1,488 batches → 20,654 merged (P2:fail 86.9%) → 765 passed → **17 armed (14 M8)** → **8 routes (all F)** → 1 placed + 6 intents → **1 fill (BE-scratch +0.0715 diagnostic only)**. **Determinism: trades.csv + report.json byte-identical across run1/run2 (SHA-256 match)**; funnel semantic-equal. Paper dry-run wiring smoke DONE (no MT5 needed; delegates to the shared runtime; 0 sends). Report: `06_RESEARCH/PHASE4_UNIFIED_BACKTEST_REPORT.md`; artifacts `06_RESEARCH/results/phase4_unified/`.

**CHOICE 1 PROGRAM COMPLETE (Phase 0→4 all PASS, 2026-09-23).** Next-action authority returns to the Lead Architect: rational forks are residual engineering (C3 structural TP feed, entry_anchor export), Phase D HTF probe on EXNESS, or a dated research ruling — **not silent F-optimization**.

## Residual engineering Track A (E1 → C3 → C4 — COMPLETE 2026-09-24)

Ordered residual work per the owner's Track A prompt; record: `06_RESEARCH/RESIDUAL_A_E1_C3_C4_NOTE.md`.

- [x] **E1 — entry_anchor export (DONE)** — first-class `entry_anchor` on the full trade path: `candidate_from_route` extracts `signal.data["entry_anchor"]` (string-only; absent → None, never invented) → CandidateEntry → PendingOrder → BacktestPosition → TradeRecord → CSV (appended column, backward compatible) + JSON key; also inside `signal_data_json`; `modify_sl` preserves it (original_sl pattern, enforced by test); paper `_TrackedPending`→`_TrackedPosition` carry it. 11 new tests (`test_residual_a_e1_entry_anchor.py`); 2 `test_identity_patch.py` assertions updated for the appended column. Logging/audit only — zero decision change.
- [x] **C3 — structural TP: UNFED_DESIGN_ONLY** — design ruling written BEFORE code (note §C3): valid V1 structural TP = trigger-emitted under an explicit frozen key, finite + strictly favorable, derivable from route-carried objects. Survey: no trigger emits a structural target (`TriggerSignal.data` carries no target price; liquidity levels never attached to routes) → no feed implemented; `resolve_take_profit` structural branch stays wired/tested/dormant; TP remains frozen 4×ATR (FR-2 R4). No new constants, no invented selectors.
- [x] **C4 — news / spread / sweep-guard dispositions** — formal Silent/deferred table appended to `PRODUCT_RUNTIME_CONTRACT.md` §8: News §11 **DEFERRED** (no calendar ingestion; synthetic calendar banned); Spread §28.5 **WIRED (operator input)** — `spread_price` threaded end-to-end to `effective_max_spread` grading; Sweep guard **DEFERRED** (no trigger emits `sweep_level`; plumbing dormant, none invented). Standing statement: shipped configs with `news_events=[]` / `spread_price=0.0` remain **diagnostic**, not "gates proven live".

**Track A COMPLETE (2026-09-24).** Suite **726 → 737**; no decision-logic change; `locked_constants.py` diff empty.

- [x] **Phase D HTF product-runtime probe (COMPLETE 2026-09-24, ops PASS)** — EXNESS Copy terminal ONLY, dry_run true, magic 20260919: identity MATCH (DEMO 474608655, XAUUSDm, trade_allowed=True); product-mode HTF probe **H4=300 / H1=300 / D1=300** bars (`missing_series=[]`), `LiveLoop.start()` compliant with contract §3.4; degraded smoke stamped loud (`degraded=True` + reason, never silent); 60 s dry_run loop 120 polls / 0 unhandled errors / clean shutdown. Script `06_RESEARCH/scripts/phase_d_htf_probe.py`; artifacts `06_RESEARCH/results/phase_d_htf_probe/`; report `PHASE_D_DIVERGENCES.md` §9. Infrastructure proof only — NOT strategy validation. Watchdog EA chart-attach still BLOCKED (GUI-only; stale-heartbeat drill pending).

## V1.1 freeze

- [x] **V1.1 RUNTIME BASELINE FROZEN (COMPLETE 2026-09-24, docs-only)** — frozen implementation baseline recorded in `00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md`: Choice 1 (Phase 0→4) + Track A (E1/C3/C4) + Phase D HTF probe. Expectancy/PF/live profitability NOT proven and NOT part of the freeze. Allowed without a ruling: Phase D ops, contract-restoring bugfixes, docs. Requires a dated ruling: locked_constants / pillar / trigger / zone / R7/R9 edits, F-timing, Monte Carlo, structural TP invention, demo-PnL-as-edge, dry_run=false campaigns. Suite **737**; no code change in the freeze.

**NEXT ACTION = Project-wide independent audit (per Architect order; may include the F3 prefix guard as optional item — ruling: approve cheap hardening, implement after paper or as small pre-commit fix) → then git commit/push.** (Paper ops PASS 2026-10-06; expert pack scoring runs in parallel, not a blocker. The completed chain — W1 provisioning → console → dry-run → L2 ledger → backfill+pack → armed-mismatch fix → look-ahead audit accepted → paper ops — is recorded; no strategy logic change.) The hypothesis-outcome study review (SL_THEN_TP_PATH 4 / TP_REACHED 2 / MFE_ONLY 0 / REJECTED 0 / DATA_GAP 0 on the 6m post-TP n=3 sample) remains recorded and accepted; no strategy logic change. (Supersedes the former 6m-post-TP-diagnostic-next marker; that measurement is complete — see[FROZEN_FUNNEL_6M_POST_TP_REPORT.md](06_RESEARCH/FROZEN_FUNNEL_6M_POST_TP_REPORT.md) — and the hypothesis-outcome study is complete — see[HYPOTHESIS_OUTCOME_REPORT.md](06_RESEARCH/HYPOTHESIS_OUTCOME_REPORT.md). Next engagement after that review: whatever the Architect rules for Phase D / hypothesis-outcome analytics follow-on.)

**Bans while on this path:** F-survivor / F-timing / chase discriminators as main track — PAUSED (R6); Monte Carlo — PAUSED (broken-book CIs are meaningless); Phase D demo P/L is never idea validation; **no long expectancy flagship run before Phase 2**; no locked-constant / threshold / zone-band edits without a dated Lead Architect ruling.

---

## Paper/demo ops session (COMPLETE 2026-10-06, ops PASS, dry_run)

Directive 2026-10-06 (ops validation post console fix; DEMO only).

- [x] **Session (DONE)** — 20 min bounded, DEMO 474608655 XAUUSDm, dry_run=true: identity PASS, 2386 polls / 5 bars, 1 HTF batch (H4 23/11/3, **armed 1**, duplicates 2), 0 orders / 0 fills / 0 errors, clean shutdown + heartbeat `state=shutdown`.
- [x] **Console consistency (DONE — the fix proven in ops)** — 39 structure boards rendered; **every board matched `detect.armed 1`**; snapshot stamped the same second as the batch (zero lag); header armed counter carried on all boards.
- [x] **Watchdog (RECORDED)** — EA chart-attach still BLOCKED (GUI-only); heartbeat publisher ran the full session and wrote the shutdown marker. Honest record, not blocking.
- [x] **Bans honored (DONE)** — no locked_constants edits, single symbol, no optimization, no expectancy claims; suite 853 (read-only session).
- Note: `06_RESEARCH/PAPER_OPS_SESSION_NOTE.md`; artifacts `06_RESEARCH/results/paper_ops_20261006/`.

---

## Live console vs armed mismatch + warm-up audit (COMPLETE 2026-10-06, ops PASS)

Directive 2026-10-06 (ops bugfix + audit; dry_run only).

- [x] **Root cause (DONE)** — snapshot rate limit treated the arming event (batch change) like routine bar refreshes: with `console_refresh_s=900` an armed POI stayed off the structure board up to 15 min while `detect: armed 1` updated immediately. Arm path → engine `_armed_order` → `tracked_pois()` → snapshot builder verified sound; stale-snapshot window, not missing POIs.
- [x] **Fix (DONE, display wiring only)** — batch changes always rebuild the snapshot immediately (bar refreshes stay rate-limited, idle no-op); board header carries an armed counter. Regression tests `test_structure_refresh.py` (4); suite **849 → 853**.
- [x] **Warm-up audit (DONE, no fix needed)** — historical-window design confirmed: 300 bars per HTF fetched at start and re-fetched in full for every batch (prefix-trimmed to as_of); live: W1→2021-01-10, D1→2025-10-21, H4→2026-07-30, H1→2026-09-17; no operator-path override.
- [x] **Live reconciliation (DONE)** — 600 s dry_run on the Copy terminal: batch armed 1 (H4 23/11/3, same counts as the Architect's session) and the structure board immediately showed the armed H4 zone + sweep link; 21 boards rendered; clean shutdown + heartbeat marker.
- [x] **Bans honored (DONE)** — no threshold tuning, `locked_constants.py` diff empty, dry_run only, no second detection stack. Note: `06_RESEARCH/LIVE_CONSOLE_ARMED_MISMATCH_NOTE.md`.

---

## Setup ledger backfill + expert chart report (COMPLETE 2026-10-06, research PASS)

Directive 2026-10-06 (research/export only; two steps in one engagement).

- [x] **Step 1 — backfill (DONE)** — `06_RESEARCH/scripts/setup_ledger_backfill.py`: direction **17/30** (trade_row 3 + EXACT unique geometry join vs 6m structure ledger poi_raw events 14; tolerance probes 0.01/0.05/0.2 add zero unique fills → strict exact rule kept; 13 DATA_GAP — never guessed); `direction_source` provenance column added; posture **UNKNOWN 30/30** (not in any artifact; never price-inferred); `arm_ts_utc` **30/30** (exec-bar map, validated **6/6** vs routed trade entry/exit timestamps); human columns blank; joins preserved; dual-run byte-identical (SHA 3766d6d0…); summary.json `backfill` block.
- [x] **Step 2 — expert pack (DONE)** — `06_RESEARCH/scripts/setup_ledger_expert_pack.py`: **EXPERT_SETUP_REVIEW_PACK.pdf** (7 pages: cover+rubric, 30-row table, 15 charts) + **SETUP_IDENTIFICATION_EXPERT_REPORT.md** (rubric + return-by instructions) + `charts/` 15 PNGs (3 routed mandatory + D1 3/H4 6/H1 3 evenly spaced by arm bar — documented). House chart language; routed rows carry entry/SL/TP/exit marks + tp_source + hyp-outcome; DATA_GAP rows labeled honestly. Architect draft notes ONLY in a separated report appendix ("not expert verdict").
- [x] **Bans honored (DONE)** — no strategy/threshold edits; `locked_constants.py` diff empty; no expectancy claims; suite **849** green.
- Note: `06_RESEARCH/SETUP_IDENTIFICATION_EXPERT_REPORT.md`; outputs `06_RESEARCH/results/setup_identification_ledger/`.

---

## L2 — Setup identification ledger (COMPLETE 2026-10-06, research PASS)

Task 2 of the 2026-10-06 directive (research + export analytics; no threshold changes).

- [x] **Script + schema (DONE)** — `06_RESEARCH/scripts/setup_identification_ledger.py`: one row per armed setup from the frozen 6m post-TP funnel `armed_records.json` (30 rows), identity columns (TF, POI id, kind, zone, arm bar, pillar path, displacement, routed, trigger, entry/SL/TP, entry_anchor, tp_source) + human columns `verdict/timing/notes` **blank by design** + hyp-outcome join columns (ticket, close_kind, pnl, hypothesis_outcome, MFE/MAE).
- [x] **Run + determinism (DONE)** — 30 setups (H4 19/H1 6/D1 5), routed 3 (all with full plan), hyp join YES 3 rows (SL_THEN_TP_PATH 2 / TP_REACHED 1; tp_source atr_fallback 2 / structural_swing 1); double-run byte-identical (setups.csv SHA-256 5388635e…); input SHA-256s recorded in summary.json.
- [x] **Honest gaps (DONE)** — direction only from trade-level rows (funnel harness does not export zone direction; never inferred); posture UNKNOWN (not instrumented in the export); kind = model tags (m8_kind not exported).
- [x] **Paper path (DONE, documented)** — same column schema exportable from a future paper session (engine book / active_workflows / batch displacements / trade records); no live run required for PASS.
- [x] **Bans honored (DONE)** — no SL/TP/pillar/trigger changes, no expectancy claims, no 04_SRC/smc/** edit; `locked_constants.py` diff empty; suite 849 green.
- Note: `06_RESEARCH/SETUP_IDENTIFICATION_LEDGER_NOTE.md`; outputs `06_RESEARCH/results/setup_identification_ledger/` (setups.csv + summary.json).

---

## Live console bounded dry-run (COMPLETE 2026-10-06, ops PASS)

Task 1 of the 2026-10-06 directive (ops validation only; Task 2 = L2 ledger).

- [x] **Identity gate (PASS)** — EXNESS Copy terminal path family match; DEMO 474608655 @ Exness-MT5Trial15; symbol **XAUUSDm from config** (engine requests the configured symbol via MT5 API — the open chart does not retarget the bot); dry_run=true throughout, no orders.
- [x] **W1 enum fix (DONE, contract-restoring)** — pre-session probe: `copy_rates_from_pos(XAUUSDm, 32768, …)` → "Invalid params"; the MetaTrader5 package's `TIMEFRAME_W1` is **32769**. `Timeframe.W1 = 32769` + strengthened pin; after the fix W1 fetches 300 bars (~5.8 y). Suite 849 green.
- [x] **Sessions (DONE)** — 150 s (299 polls, cold-start anchor, 0 bars in window) / 400 s (797 polls, 1 bar, real HTF batch 14:20:00Z: H4 22→9→0, H1 21→8→0) / 420 s with 30 s console cadence (837 polls, batch 14:30:00Z, **7 structure boards**). All clean shutdowns, heartbeat `state=shutdown`.
- [x] **Console verdict (DONE)** — board renders live from the real engine: POIS W1/D1/H4/H1 all `(none)`, SWEEPS none, SEEKING none, PLAN none — **honest empty, not FAIL**: zero *passed* POIs (Pillar rejection on the 9-merged window), while provisioning itself is proven (W1 300 bars ≈ 5.8 y, D1 300 ≈ 12 mo).
- [x] **Bans honored (DONE)** — no locked_constants edits, no multi-symbol work, no strategy changes. Note: `06_RESEARCH/LIVE_CONSOLE_DRYRUN_NOTE.md`.

---

## Weekly (W1) provisioning + live structure console (COMPLETE 2026-10-06)

Dated Lead Architect two-sequence engagement (Milestone W then Milestone L1, both PASS). Operator must-have: Weekly/Daily/H4 POI ranges visible in the terminal for human second-validation — so Weekly was provisioned FIRST (no placeholder board).

- [x] **Milestone W — WEEKLY (W1) PROVISIONING (PASS)** — `Timeframe.W1 = 32768` (MT5 `PERIOD_W1`), `minutes=10080`, `is_htf()` includes W1 (§27 N=5 class; `N_BAR_HTF` unchanged); `resample_ohlcv` W1 support with **Monday-00:00 ISO-week bins** (deliberate market-convention exception — epoch-multiples of 10080 min align to Thursday) + documented guard bypass; M8 `HTF_TIMEFRAMES=(W1,D1,H4)` (same frozen scanner, same constants) with the **D1×H4 overlap pairing left frozen** so §26 quality scores are untouched; `multi_tf.M8_HTF_TIMEFRAMES=(W1,D1,H4)`; `MultiTFProductRuntime.optional_timeframes=(W1,D1)` (required detection set unchanged H4+H1, loud `MissingHtfSeriesError` intact; operator config may promote W1 to required); `LiveLoop` product fetch list `(H4,H1,W1,D1)` via `int(tf)` → `PERIOD_W1` with **cadence still one batch per new H1 close**; W1 documented as HTF **context** POI only — execution stays M5.
- [x] **W tests + note (DONE)** — `test_weekly_provisioning.py` (9): Monday-bin alignment, honest OHLCV aggregation, no invented weekend bars, determinism + guard bypass + `resample_multi`, M8-on-W1 deterministic impulse fixture (≥1 weekly zone, silent when unsupplied), W1-in-detection-set batch (`per_tf["W1"]`), W1-optional → M8 map, live fetch + cadence + legacy unchanged; `test_enums.py` pins strengthened (E1 convention). Suite **829 → 838**. Note `06_RESEARCH/WEEKLY_PROVISIONING_NOTE.md` (residuals: sparse W1 bars / cold-start depth / forming-bar dedup).
- [x] **Milestone L1 — LIVE STRUCTURE CONSOLE (PASS)** — new `smc/live/structure_console.py`: `build_structure_snapshot()` (read-only; engine `tracked_pois`/`episode`/§5 state + adapter `active_workflows()` + loop sweep links) and `render_structure_console()` (pure ASCII). Sections **POIS** (W1/D1/H4/H1 order: direction, kind, zone_low-high, armed, state, short id) / **SWEEPS** (linked POI + TF + side or `none`) / **SEEKING** (state, arm posture, targeted trigger letter) / **PLAN** (direction, entry, SL, TP, `tp_source`, trigger, poi_id — else `PLAN: none`). W1 rows are LIVE data; empty TFs print honestly.
- [x] **L1 wiring (DONE)** — `OperatorSession` refreshes the snapshot on a new M5 bar and/or HTF batch, rate-limited to `console_refresh_s` (min 1 s), and appends the board to the console + `console_mirror.log`. Additive display-only seams: `MultiTFBatchReport.displacements`, `LiveLoop.sweep_links`, `PipelineAdapter.active_workflows()`. Not an MT5 chart dashboard; read-only — zero decision impact.
- [x] **L1 tests + docs (DONE)** — `test_structure_console.py` (11, real engine + synthetic POIs, no MT5; includes live W1 zone numbers on the board, honest empties, sweep links, plan line, ASCII-only, adapter copy semantics, report→loop sweep-link retention). Suite **838 → 849**. Design `06_RESEARCH/LIVE_STRUCTURE_CONSOLE_DESIGN.md`; note `06_RESEARCH/LIVE_STRUCTURE_CONSOLE_NOTE.md`.
- [x] **Bans honored (DONE)** — no pillar/trigger/SL/TP/risk changes, no §5a seek/scan changes, no second detection stack (existing seams extended only), no expectancy claims; `locked_constants.py` diff **empty**; L2 NOT started.

---

## M8 emission fix F1/F2 (COMPLETE 2026-10-04)

Dated Lead Architect prompt (F1 + F2: M8 POI Emission Fix). Identification-only; no thresholds, no trading decisions, no expectancy claims.

- [x] **F1 — episode uniqueness (DONE)** — one geometric episode → one POI: collapse inside `M8HtfDemandSupply._zones` (shared-bounds key, winner by kind priority ob > demand_supply > fvg, then LONG-first, then earliest origin; chronological yield); new `POI.m8_kind` winner-kind field (logging/identity only) propagated through `merge_overlapping`; models stays `[M8]` (no new tags).
- [x] **F2 — zone construction verdict: already origin-tight, no cap (DONE)** — measured D1 Mar–Dec 2025: ob/demand_supply zones equal origin-candle ranges exactly (bit-stable); FVG gaps definitional; width cap rejected as invented selection (would violate §22 full-range rule). Origin-invariant regression tests added instead.
- [x] **D1 re-sample + gates (DONE)** — same window/warm-up/seam as audit pack (`d1_f1f2_resample.py`): 137 raw rows (ob 43 / ds 50 / fvg 44), 2 merged, 0 armed (batch re-validation rejects on Pillar 1 — documented, not hidden); **dual_exact_bounds_count = 0, direction_conflict_count = 0, origin_tight_violations = 0**; 20 charts (ts-spread stratified raw; zero armed rows exist to chart). Armed-quality re-score proceeds on the audit's original 6 armed charts.
- [x] **Tests + suite (DONE)** — `test_m8_episode_uniqueness.py` (8) + `test_m8_zone_width.py` (5); full suite **737 → 750 passed**, zero regressions; pre-existing M8/merge tests unweakened. `locked_constants.py` diff empty.
- Note: `06_RESEARCH/F1_F2_M8_EMISSION_FIX_NOTE.md`. Results: `06_RESEARCH/results/d1_f1f2_resample/`.

---

## H4 POI Identification Pack (COMPLETE 2026-10-04)

Dated Lead Architect prompt (H4 structure confirmation; identification-only — not trades). Same window as the D1 pack (exec 2025-06-01 → 2025-11-30 UTC, warm-up 2025-03-01), post-F1F2 emission path, no thresholds touched.

- [x] **Pack script + run (DONE)** — `06_RESEARCH/scripts/h4_poi_confirmation.py` (mirrors `d1_f1f2_resample.py`; H4 series from M1 parquet → `resample_multi`): 1203 H4 bars; raw **658** (ob 177 / demand_supply 304 / fvg 177), merged **3**, armed **0**; **dual_exact_bounds_count = 0, direction_conflict_count = 0, origin_tight_violations = 0**, all rows detection_tf/chart_tf = H4. Plain tags exactly `ORDER BLOCK (H4)` / `DEMAND ZONE (H4)` / `SUPPLY ZONE (H4)` / `FAIR VALUE GAP (H4)` / `MERGED POI (H4)` / `ARMED POI (H4)`.
- [x] **Charts (DONE)** — 55 PNGs (0 armed + stratified raw 15 OB + 15 demand + 15 supply + 10 FVG, ts-spread; cap 60 not reached), `render_d1_chart` visual language, `001…` ts-ordered.
- [x] **Script-local fixes (DONE)** — (1) rolling-window endpoints filtered to ≥ EXEC_START (pre-exec first-seen anchoring had emptied the merged layer); (2) merged/armed `event_id`s geometry-derived — `POI.id` is `uuid4()` (run-random), double-run now **byte-identical CSV + summary**.
- [x] **Tests + suite (DONE)** — `test_h4_poi_pack.py` (4: H4 synthetic origin-tight/no-duals, plain-tag no-D1-leakage, geometry-stable ids, exec-window filter); full suite **750 → 754 passed**, zero regressions. `locked_constants.py` diff empty.
- Armed = 0 documented (all 3 merged rows failed Pillar 1 zone_refinement "naked level"; batch re-validation ≠ formation-time arming — same limitation as D1, no threshold relaxed). Human CORRECT scoring not run (Architect/user step).
- Report: `06_RESEARCH/results/h4_poi_confirmation/H4_POI_CONFIRMATION_REPORT.md`. Note: `06_RESEARCH/H4_POI_CONFIRMATION_NOTE.md`. Results: `06_RESEARCH/results/h4_poi_confirmation/`.

---

## LTF Confirmation Pack (COMPLETE 2026-10-04)

Dated Lead Architect prompt (LTF confirmation; identification-only — what the current machine sees on M15/M5 after an accepted H4/D1 structure exists; not trades). Same window as the H4 pack (exec 2025-06-01 → 2025-11-30 UTC, warm-up 2025-03-01), accepted packs as HTF source, no thresholds touched.

- [x] **Pack script + run (DONE)** — `06_RESEARCH/scripts/ltf_confirmation_pack.py`: HTF source = `events_h4_poi.csv` raw **658** + D1 subset **10** = **668** structures (ob 177 / ds 307 / fvg 184); stage0 M15=13,474 / M5=37,015 events; per-bar router replay (pre-pillar, `generate_candidates` mirror) on close-anchored windows; ledger `events_ltf_confirmation.csv` **15,352 rows** (exact 15 columns) + `summary.json` (activity/silent, trigger mix, window, look-ahead, chart count, gate status).
- [x] **Gates (DONE)** — **dual=0 per source pack, direction_conflicts=0** (cross-TF tie `evt-6a8455eea149`≡`evt-bbf35c6dc170` disclosed — each pack individually dual=0); **activity 624 / silent 44**; **trigger mix `{"F": 2}`** (both relation=inside; `{}` was spec-allowed, replay honestly found 2); status **PASS**.
- [x] **Script-local fixes (DONE, four defects found while building)** — per-source dual gate; close-anchor (H4 +4h / D1 +24h) for arm + link windows (open-anchor self-linked forming sub-bars → 668/0); activity = zone-interaction (`retest`/`inside`) or own trigger; interleaved active/silent selection under the panel cap.
- [x] **Charts (DONE)** — **39 panels / 13 structures (7 active + 6 silent)**, caps ≤12/≤8/≤40 honored; plain tags TF-suffixed only (SWEEP/DISPLACEMENT + BOS/FAIR VALUE GAP/TRIGGER F …), no module paths; per-panel true detection_tf/chart_tf subtitles (incl. render-only fix in `generate_d1_poi_pack.py:171`, H4 CSV byte-identical after re-render); footer "structure / confirmation identification — NOT a trade claim".
- [x] **Tests + suite (DONE)** — `test_ltf_confirmation_pack.py` (8: selection determinism/caps/interleaved/full-panel-set, plain-tag contract + NONE rows, look-ahead consistency `M5=20`=TRIGGER_A_EXPIRY / `M15=7` same rule every structure, pinned strategy constants); full suite **754 → 762 passed**, zero regressions. `locked_constants.py` diff empty. Double-run CSV byte-identical, summary identical.
- Look-ahead disclosure: M5=20 (`poi_give_up_bars()`=TRIGGER_A_EXPIRY LOCKED §24), M15=7 (`ceil(20×5/15)`); anchor + activity + pre-pillar router + replay-vs-product (0 timestamp overlap with product's 10 `route_ltf` rows) all disclosed in report/note.
- Report: `06_RESEARCH/LTF_CONFIRMATION_REPORT.md`. Note: `06_RESEARCH/LTF_CONFIRMATION_NOTE.md`. Results: `06_RESEARCH/results/ltf_confirmation/`.

---

## Stage 3 Trigger Visibility + Conversion Audit (COMPLETE 2026-10-04)

Dated Lead Architect prompt (Stage 3 trigger visibility; identification/visibility only — count completed Stage 3 triggers A–F in the frozen window, link each to its HTF POI, measure detector-activity → Stage 3 conversion, render panels a human can read; not optimization, not threshold tuning). Same window as prior packs (exec 2025-06-01 → 2025-11-30 UTC, warm-up 2025-03-01), accepted packs as source, all locked rules untouched.

- [x] **Pack script + run (DONE)** — `06_RESEARCH/scripts/stage3_trigger_visibility.py`: Pass 1 = instrumented copy of the accepted §5-mirrored pre-pillar replay (verified same 2 routes as LTF pack) recording per-structure scan-lifecycle gate stats; Pass 2 = visibility inventory — one `SeriesState(M5)` per bar, ALL matrix-eligible triggers evaluated directly in each structure's `[close, close + poi_give_up_bars()=20]` window, **every completion recorded ungated**. Ledger `events_stage3_triggers.csv` **263 rows × 14 columns** + `summary.json` (incl. `route_funnel`).
- [x] **Counts (DONE)** — **263 completions: {A:31, B:17, C:4, D:0, E:7, F:204}**; counts_by_tf {M5:263, M1:0} (triggers never read timeframe; product wires them to M5 only — M1 not wired, honest zero); with-htf-link 263 / without 0 (scan universe = accepted packs, by construction, disclosed); 232/668 structures ≥1 completion; route_would_form = 2 (both F: `evt-ec41701aca47` 2025-07-13 22:10, `evt-499a786ac28b` 2025-10-26 22:10 — same 2 as LTF pack, 0 discrepancies).
- [x] **Conversion funnel (DONE)** — 15,350 detector links → 263 completions (1.71%) → 2 routes; route funnel: 261 completions suppressed after the §5 scan closed (**199 first-touch +1 gate, 62 zone violation**), **2/2 inside the open scan routed**, `scanned_not_routed = 0`, `suppressed_other = 0`, `not_probed = 0` (zero anomalies).
- [x] **Charts (DONE)** — 36 panels = 30 trigger (type-seeded earliest-of-each-type + even-in-time spread; all 5 present types, June→November) + 6 negatives (top detector activity, zero completions); plain title `TRIGGER F — BOS + OB CONTINUATION | M5 | … | LONG` style, detection_tf/chart_tf subtitle, trigger-specific geometry from `signal.data` (BOS/OB, peaks, diagonal terminal, wave/Fib band), footer `Stage 3 trigger visibility — NOT a trade claim`; visually verified.
- [x] **Tests + suite (DONE)** — `test_stage3_visibility_pack.py` (10: ledger schema, trigger_id determinism, detector_context, chart_plan caps, trigger sample coverage, negatives ranking/exclusion, route-funnel buckets, pinned constants + footer wording); full suite **762 → 772 passed**, zero regressions. `locked_constants.py` diff empty. Double-run CSV + summary byte-identical.
- Honest zeros: **D = 0** (frozen rule `engulfer.volume < engulfed.volume` vs all-zero volume column, A5 ruling — structurally unreachable); **M1 = 0** (not wired). Both documented in report §5.
- Report: `06_RESEARCH/STAGE3_TRIGGER_VISIBILITY_REPORT.md`. Results: `06_RESEARCH/results/stage3_trigger_visibility/`.

---

## Stage 3 Lifecycle Timing Audit (COMPLETE 2026-10-04)

Dated Lead Architect directive (lifecycle timing; identification / measurement only — position every recorded Stage 3 completion in the product lifecycle vs arm / first-touch / scan-close; distributions not opinions; inputs reused from disk, never regenerated).

- [x] **Audit script + run (DONE)** — `06_RESEARCH/scripts/stage3_lifecycle_timing.py`: joins the 263-row Stage 3 ledger to the accepted H4/D1 packs (same loader rules), recovers lifecycle events with the accepted instrumented §5 replay (`stage3_trigger_visibility.observe_routes_instrumented` — no invention), writes `events_lifecycle.csv` (263 × 23: all timestamps, 4 bar deltas, 4 minute deltas, bucket) + `summary.json` (bucket counts, type×bucket, distributions, sanity, limitations).
- [x] **Buckets (DONE)** — **OPEN_SCAN 2 (0.76% all / 0.98% F)**, CLOSED_TOUCH 199, CLOSED_VIOL 62, NEVER_ARMED 0, DATA_GAP 0, unclassified 0; **2 routed rows → OPEN_SCAN sanity PASS**; bucket counts reproduce the accepted pack's funnel (199/62) via an independent path; inventory recomputed = 263.
- [x] **Distributions (DONE)** — OTHERS: completion−scan_close p25 4.5 / median **10** / p75 13.5 bars, completion−first_touch median 11 (n_used 199, n_null 62); OPEN_SCAN: both rows complete exactly on the last open scan bar (delta 0); median completion−scan_close **10 (all) / 10 (F)**; all completions 2–20 bars after structure close (locked 20-bar horizon, nothing widened).
- [x] **Structural findings (DONE)** — arm = close bar for all 263 rows (11 weekend minute-gaps to first tradable bar); `first_touch == arm` for 199/199 touch-closed structures (effective seek span `[arm, arm+1]`); all 62 violations fire on the arm bar (scan never opens, nulls by rule, never invented); 0 completions missed while a scan was open.
- [x] **Charts (DONE, optional ≤12)** — 3 illustrative panels (one per populated bucket: `001` OPEN_SCAN / `002` CLOSED_TOUCH / `003` CLOSED_VIOL), existing Stage 3 render helper, lifecycle facts in caption, same footer language.
- [x] **Tests + suite (DONE)** — `test_stage3_lifecycle_timing.py` (8: bucket-assignment cases incl. residual→UNCLASSIFIED, percentile determinism, join non-null structure_close for pack-present ids, routed rows OPEN_SCAN, bucket sums = 263, causal order ≥0, locked windows 20/30/1/12); full suite **772 → 780 passed**, zero regressions. `locked_constants.py` diff empty. Double-run CSV + summary byte-identical.
- Report: `06_RESEARCH/STAGE3_LIFECYCLE_TIMING_REPORT.md` (method / join rules / aggregate tables / three decision inputs stated as observations only — keep contract, redesign seek, further F filter). Results: `06_RESEARCH/results/stage3_lifecycle_timing/`.

---

## Seek/Scan Contract Redesign — DESIGN LOCK (Option B, design only — NOT STARTED as code)

Dated Lead Architect directive (Option B DESIGN LOCK: the arming + one-touch seek contract is defective for the measured data; write the design note FIRST, no production code until reviewed).

- [x] **Design note (DONE 2026-10-05)** — `06_RESEARCH/SEEK_SCAN_CONTRACT_REDESIGN_DESIGN.md`, all 7 required sections in order (problem statement w/ exact counts; design principles; normative rules R1–R5: arming + initial-presence classification `IN_ZONE_AT_ARM`/`VIOLATION_AT_ARM`/`CLEAN_ARM`, scan-open for every posture, revalidation-gated routing via the existing `market_reentered_zone` rule, scan span = unchanged `[arm, arm+20]` give-up computation, terminators incl. violation-after-live-scan, one-shot/episode identity; explicit locked-constants obeyed table + itemised behaviour changes vs §5 one-touch+1; 4 rejected alternatives; success metrics M1–M5 incl. OPEN_SCAN share target 0.76% → ≥80%, no-regression on the 2 routed rows, median(completion−scan_close) ≤ +2, armed-count invariant + one-shot invariant + 50% selectivity alarm; implementation surface = engine seek-posture + adapter `_may_route` replacement, trigger A–F untouched; risks & residuals incl. §5 documentation drift) + §8 recorded self-check vs the 5 measured facts and the hard bans.
- [x] **Implementation + measurement phase (COMPLETE 2026-10-05, per Architect implementation directive)** — design R1–R5 implemented: `PipelineEngine` `SeekPosture` + arm-candle classification + `feed_bar` arm-bar skip (initial presence / deferred violation) + REVALIDATION continuation; `PipelineAdapter._may_route` replacement (touch no longer terminates the seek; REVALIDATION gated on zone re-entry via the existing `market_reentered_zone`, R7 band + adapter ATR, fail-closed on warm-up ATR; re-entry latch moves the scan cursor; give-up retirement per posture); one-shot untouched. Clarification ruled: `IN_ZONE_AT_ARM` needs no re-entry gate (design R2.2). Measurement on the frozen window (`seek_scan_impl_measurement.py`, artifacts `06_RESEARCH/results/seek_scan_implementation/`, double-run byte-identical): **M1 78.33%** (was 0.76%; below the 80% target by 5 rows — fully attributed: routed_earlier 27 / never_reentered 17 / violation_after_live_seek 13 — reported not tuned), **M2 PASS** (both routed rows, same bars), **M3 0.0 bars** (was +10), **M4 PASS** (armed 668=668, routes 2→196, 29.34% < 50% alarm), **M5 PASS** (0 double-routes). Suite **780 → 805**; `locked_constants.py` diff empty; trigger A–F + state-machine diffs empty. Note: `06_RESEARCH/SEEK_SCAN_CONTRACT_IMPLEMENTATION_NOTE.md`.
- [x] **§5 locked-doc amendment (COMPLETE 2026-10-05, docs-only per Architect directive; implementation ACCEPTED — M1 78.33% residual accepted)** — `LOCKED_DECISIONS.md` gains §5a "Seek/Scan Contract (amended 2026-10-05)": records the acceptance + note paths, declares the one-touch+1 seek behaviour superseded, states the implemented contract normatively (arming unchanged; three postures; scan opens at arm; arm-bar presence = initial presence not a §5 touch terminator; REVALIDATION gated on `market_reentered_zone` re-entry; span `[arm, arm+20]`; terminators give-up/violation-after-live-scan/one-shot; one-shot identity unchanged; no constant changed); the §5 state machine explicitly unchanged. Cross-refs updated: §21 + §22 freshness lines now point to §5a. Docs only — no `04_SRC/smc/**` edit, locked-constants diff empty, suite 805 unchanged, `LOGIC_CHANGED: NO`.
- [x] **Frozen-window funnel measurement under the new contract (COMPLETE 2026-10-05, diagnostic only)** — `frozen_funnel_new_contract.py` dual-run on the frozen Phase 4 window (load 2025-08-01, exec 2025-09-01→11-30): **armed 18 (15 M8)** → scans 256 → **routes 9 {F 8, C 1}** — the C route is the first Trigger C in product history, direct evidence of the redesign at product level — → placed 2 (TP 2/2 = 100%) + 6 R9 intents (1 placed) → **fills 2 → trades 2**; exit mix stop_loss 2 (BE-scratch 1); net −0.3013 diagnostic n=2 NOT performance; posture mix CLEAN 18/IN_ZONE 0/VIOLATION 0 (this window's armed population arms clean — pack-window replay remains the evidence for the other postures); **determinism PASS** (byte-identical). Suite 805; locked-constants diff empty; no production edit. Report: `06_RESEARCH/FROZEN_FUNNEL_NEW_CONTRACT_REPORT.md`; artifacts `06_RESEARCH/results/frozen_funnel_new_contract/`.
- [x] **Wider frozen-window funnel measurement, 6 months (COMPLETE 2026-10-05, diagnostic only)** — `frozen_funnel_6m_new_contract.py` dual-run on the frozen 6-month pack window (M1 load 2025-05-01, exec 2025-06-01→11-30, 35,725 M5 bars; fail-loud on missing data): **armed 30 (28 M8)** → scans 501 → **routes 10 {F 9, C 1}** → placed 4 (TP 4/4 = 100%) + 7 R9 intents (3 placed, 0 expired) → **fills 3 → trades 3**; exit mix stop_loss 3 (BE-scratch 1); net −3.2117 diagnostic n=3 NOT performance; posture mix CLEAN 30/IN_ZONE 0/VIOLATION 0 — the 6-month product-path armed population still arms clean, so the non-CLEAN postures remain exercised only by the suite + pack replay; non-F routes thin (C n=1, A/B/D/E 0). **Determinism PASS** (trades.csv + report.json byte-identical); no `04_SRC/smc/**` edit; locked-constants diff empty. Report: `06_RESEARCH/FROZEN_FUNNEL_6M_NEW_CONTRACT_REPORT.md`; artifacts `06_RESEARCH/results/frozen_funnel_6m_new_contract/`.
- [x] **Expert chart archive + system match probe (COMPLETE 2026-10-05, read-only)** — operator's 11 marked example charts archived to `03_REFERENCE_CODE/expert_marked_charts/`, inventoried (`EXPERT_MARKED_CHARTS_INDEX.md`, `results/expert_marked_charts/ledger.csv`), probed against the frozen structure ledger with no re-detection (`EXPERT_CHART_SYSTEM_MATCH_NOTE.md`): match YES 1 / PARTIAL 9 (TF-capped or coarse) / clean NO 3; **time matching DATA_GAP on every chart** (no dates readable, none invented); system does not emit double top/bottom / CHOCH / Fib golden / ending diagonal / W1 classes — disclosed. **Operator TP/SL policy captured docs-only, PENDING Architect ruling:** TP = first swing low/high; SL = 30 pips below/above small-TF entry — NOT implemented; current V1 TP/SL behaviour unchanged. LOGIC_CHANGED: NO; `locked_constants.py` diff empty.
- [x] **Policy record — Architect rulings A–E (COMPLETE 2026-10-05, docs-only sync)** — rulings recorded in `SESSION_HANDOFF.md` ("Standing rulings + accepted state (2026-10-05)") + `06_RESEARCH/POLICY_TP_SL_PARTIAL_2026-10-05.md`: (A) structural/first-swing TP MAY be fed via the existing `structural_else_4ATR` branch (UNFED) — design+implement is the next coding track; (B) SL stays ATR/structural — fixed 30-pip stop NOT adopted; (C) expert "30 pips" = review metric only (post-trade MAE yardstick); (D) PARTIAL standing guidance = WRONG never trade / CORRECT full path / PARTIAL quality tag + default degradation direction log + half risk until a dated size rule is locked (policy posture, not code); (E) pattern vocabulary gaps = research backlog. LOGIC_CHANGED: NO.
- [x] **Structural TP feed — design lock (ACCEPTED 2026-10-05)** — `06_RESEARCH/STRUCTURAL_TP_FEED_DESIGN.md` (with the Architect's two constant rulings in its addendum: `STRUCTURAL_TP_MIN_ATR = 0.25` accepted as interim, pinned in tests, pending formal § lock; `poi_give_up_bars()` reuse accepted ONLY as a documented CPU/age bound, never give-up semantics).
- [x] **Structural TP feed — IMPLEMENTED + MEASURED (COMPLETE 2026-10-05, diagnostic only)** — selector `structural_tp_target` in `pipeline_bridge.py` fed at the existing adapter `candidate_from_route(structural_target=)` site; `resolve_take_profit` untouched; SL unchanged; `tp_source` audit provenance threaded E1-style to CSV/JSON (audit-only, test-enforced). Measurement (frozen 3m window, dual run, `06_RESEARCH/results/structural_tp_feed/`): **placed 2 → structural 1 / fallback 1, TP non-null 100%**; exit mix **take_profit 1 + stop_loss 1** vs pre-feed stop_loss 2 — C trade poi-001022 flipped SL −0.3728 → structural TP **hit +0.3852**; F fallback trade byte-identical to pre-feed; net +0.4567 **diagnostic n=2 — NOT performance**. Determinism PASS (byte-identical). Suite **805 → 829** (24 new tests); `locked_constants.py` diff empty. Note: `06_RESEARCH/STRUCTURAL_TP_FEED_IMPLEMENTATION_NOTE.md`. **NEXT = Architect review of TP feed metrics.**
- **Status:** IMPL_STATUS: PASS · DESIGN_LOCK_STATUS: PASS (design note unchanged) · LOGIC_CHANGED: YES (the accepted redesign itself; everything else read-only).

---

## 1. Current posture

- **Frozen:** `LOCKED_DECISIONS.md` Rev 5 incl. §28 risk constants; trigger geometry + §15 matrix; §5 one-touch; §11 one-shot; §23/§24 expiry; fill model (limit-price fills, SL-first same-bar, fill-before-entry); single sizing path (§28.7 band + `LOT_MAX_SAFETY`).
- **Phase C proved:** the frozen V1 stack runs deterministically over 1,768,123 bars (dual-run byte-identical, all invariants OK); the diagnostic baseline is 761 trades, WR 25.49%, PF 0.344, net −4.78% equity, 0 TP exits.
- **Phase C did NOT prove:** anything about edge, robustness, regime stability, live costs, or any trigger family with n<30. A losing baseline authorizes diagnosis, nothing else.
- **Primary diagnostic finding (triple-audit agreement):** the trade system is incomplete — no TP path exists (`tp_price=None` hardwired in the bridge; 754 SL + 7 Friday-EOD closes). Every metric currently measures the missing exit, not the entries.
- **Parallel tracks:** Track R (research diagnosis — measurement CLOSED 2026-09-19) + Track D (Phase D ops validation) + Track V (visual conviction, NEW — research charts first, MT5 overlay later). Neither blocks the others.

---

## 2. Track R — Research diagnosis (PRIORITY)

Read-only on frozen strategy code. All studies run offline on stored artifacts.

- [x] **R1 — MFE/MAE study on all 761 Phase C trades (COMPLETE 2026-09-19)** — med MFE 0.55R / MAE 1.73R; 37.5% ≥1R; B outlier (med 6.12R) vs F/A weak. Report + `results/r1_mfe_mae/`.
  - Inputs: `06_RESEARCH/results/phase_c_baseline_run1/merged/trades.csv` (761 rows; entry_price, sl, entry_bar/exit_bar, direction, trigger) + canonical `07_DATA/XAUUSD_M1.parquet` (M1 bars for excursion measurement).
  - Outputs: `06_RESEARCH/PHASE_R1_MFE_MAE_REPORT.md` + per-trade table `06_RESEARCH/results/r1_mfe_mae/trades_mfe_mae.csv` (columns: route_id, trigger, direction, entry_price, sl, risk_distance, MFE_price, MAE_price, MFE_R, MAE_R).
  - Method: for each trade, walk M1 bars from entry_bar to exit_bar; record max favorable / max adverse excursion in price and R-multiples (risk_distance = |entry − sl|).
  - Decision-gate note: feeds §6 gates directly. No pass/fail — this is measurement.

- [x] **R1b — Time-to-MFE / R-multiple at MFE (COMPLETE 2026-09-19, folded into R1)** — med bars_to_mfe 1.0 (F: 0, B: 6.5); 29.3% never favorable.
  - Inputs: same as R1.
  - Outputs: appended to `06_RESEARCH/PHASE_R1_MFE_MAE_REPORT.md` §Time-to-MFE + columns `bars_to_mfe`, `mfe_r` in `trades_mfe_mae.csv`.
  - Method: bars from entry to first MFE touch; distribution by trigger family.
  - Decision-gate note: distinguishes "stops too tight" (fast adverse) from "no follow-through" (MFE reached, then faded — exit-model failure).

- [x] **R2 — Synthetic TP counterfactuals at 1.5R / 2R / 3R (COMPLETE 2026-09-19)** — PF 0.011/0.0032/0.0006, all wins F-only; TOUCH≠REACHABLE (84.5% of touches die to SL-first); Gate 6.1 dead, 6.2 confirmed. Report + `results/r2_tp_counterfactual/`.
  - Inputs: R1 per-trade table + same M1 parquet. Frozen entries/SL untouched.
  - Outputs: `06_RESEARCH/PHASE_R2_TP_COUNTERFACTUAL_REPORT.md` + `06_RESEARCH/results/r2_tp_counterfactual/summary_by_policy.csv` (rows: BE-only control, 1.5R, 2R, 3R; columns: trades, WR, net, PF, maxDD, per-trigger splits).
  - Method: offline replay — same entry/SL, close at first TP touch else SL (same-bar SL-first tie-break preserved). BE-only book is the control arm.
  - Decision-gate note: if any policy turns PF>1 with trigger-level consistency → exit model is primary (Gate §6.1). If all policies stay negative → entry/selection is primary (Gate §6.2).

- [x] **R3 — Baseline attribution + rule identity (COMPLETE 2026-09-19; rescoped per R2 gate update)**
  - Inputs: trades.csv + R1 table + R2 control + parquet (session/ATR context). Model tags NOT on any artifact → recorded unknown.
  - Outputs: `06_RESEARCH/PHASE_R3_BASELINE_ATTRIBUTION.md` + `results/r3_attribution/` (trades_identity.csv, summary_by_trigger.csv, summary_by_failure_mode.csv, r3_summary.json).
  - Findings: exit mix full-SL 567 / BE-scratch 187 (+2.14) / Friday 7 (+22.93 calendar luck); F=86.6% of book with sub-ATR stops (0.72×); failure modes instant_stop 223 + no_follow_through 253 = 62.5% of trades, ~140% of net loss; no subset viable (F-only PF 0.397 least-bad); R4 (Pillar-2 kill-sample on F routes) justified as next probe.

- [x] **R4 — Full entry-selectivity / Pillar-2 diagnosis (COMPLETE 2026-09-19; upgraded from sample to full population)** — 131 windows, 335 P2 kills; overfilter INDETERMINATE (structured); FVG-absence is the binding kill driver (91%); magnitude tiers don't separate outcomes; funnel quality MIXED. Report + `results/r4_entry_selectivity/`.
  - Inputs: Phase C first-failure histogram (pillar_2_fail dominant) + armed-POI records.
  - Outputs: short note appended to R5 conclusions, or `06_RESEARCH/PHASE_R4_PILLAR2_SAMPLE.md` if run.
  - Method: hand-review a fixed sample (e.g. 50) of Pillar-2-killed POIs against locked §3 — misfire rate only.
  - Decision-gate note: do NOT run unless R1/R2 point at entry/selection (weak MFE). Skip otherwise.

- [x] **R5 — Document conclusions + Lead Architect decision gates (COMPLETE 2026-09-19)** — `06_RESEARCH/POST_BASELINE_DIAGNOSIS.md`: 10 proved/rejected verdicts; exit-model work NO; entry-selectivity + F-KB dive + export patch YES; 30-day plan with Phase D in background. Track R measurement CLOSED; awaiting §7 gate rulings.
  - Inputs: R1–R4 outputs.
  - Outputs: `06_RESEARCH/POST_BASELINE_DIAGNOSIS.md` (one page per gate in §6) + dated rulings recorded in `POST_V1_PLAN_OF_ACTION.md`.
  - Decision-gate note: no finding enters the locked system without meeting the §6 promotion bar. This checkbox closes Track R.

- [x] **EXPORT — Logging-only identity enrichment (COMPLETE 2026-09-20)** — persist `model_tags` + `pillar_path` + `disp_magnitude_atr` on candidates → orders → positions → trades → CSV/JSON exports (appended columns/keys, backward compatible); adapter `note_route_context` seam fed by live loop + research scripts; paper tracked objects carry the same fields. Verified: 2025-10-01..08 window, 115/115 trades non-empty on all three fields. Suite 591 green. Note: `06_RESEARCH/EXPORT_IDENTITY_PATCH_NOTE.md`. No decision, threshold, or fill/risk logic changed.

- [x] **HONEST-R — Recompute with original_sl (COMPLETE 2026-09-20)** — 39 unique setups (verify_w0 deduped): med MFE honest 0.42R (full-SL-only 0.23R), 30.8% ≥1R honest vs 38.5% contaminated; 3 showcase flips exposed (10–13R → <1R, all BE-scratches); stop/ATR honest 0.85; entry-selection diagnosis holds and strengthens. Report: `06_RESEARCH/PHASE_HONEST_R_RECOMPUTE_REPORT.md` + `results/honest_r_recompute/`. Rule henceforth: original_sl only, never working sl.

- [x] **EXPORT-2 — Original SL + zone geometry (COMPLETE 2026-09-20)** — persist `original_sl` (= placement SL, BE never overwrites — tested) + `zone_low`/`zone_high` (POI bounds) + `signal_data_json` (trigger geometric refs, e.g. F bos/ob indices) across bridge → orders → positions (modify_sl copies verbatim) → TradeRecord → CSV/JSON (appended, backward compatible) + paper tracked objects. Verified: same window re-run, 115/115 non-empty on all four new fields, zone invariant holds. Suite 596 green. Note: `06_RESEARCH/EXPORT_ORIGINAL_SL_ZONE_PATCH_NOTE.md`. Flowchart-match follow-on items (honest-R recompute, zone drawing in inspector) now unblocked.

- [x] **STOP-VS-SHELF — Original-stop structure study (COMPLETE 2026-09-20)** — 69 pooled unique setups (64 F + 5 B), original_sl only: F stops tight (0.82×ATR) in pre-touched levels (5 touches median) dying mostly by wick-tag (35 vs 29 break) = stop-inside-noise; B stops wide (2.65×ATR) in fresh levels (1 touch) dying mostly by close-through break (3 vs 2) = genuine level breaks; F entries 0/64 inside zones; B SLs 3/5 inside their zones (zone-rectangle charts). Script: `06_RESEARCH/scripts/stop_vs_structure.py`. Report: `06_RESEARCH/STOP_VS_STRUCTURE_NOTES.md` + `results/stop_vs_structure/`. No rules, no thresholds, no live gates.

---

## 3. Track D — Phase D ops (ops proof only, never idea validation)

Terminal constraint: ONLY `C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe` (DEMO 474608655, symbol XAUUSDm, magic 20260919). Operator pack: `run_live.bat` → `config/live_demo.json` (dry_run default TRUE).

- [ ] Watchdog EA attached on EXNESS Copy terminal (XAUUSDm chart; InpHeartbeatFile=smc_heartbeat.txt, InpSymbolFilter=XAUUSDm, InpMagicFilter=20260919) — files deployed 9/19, attach still GUI-unconfirmed; drill blocked on this
- [ ] Stale-heartbeat emergency drill (kill heartbeat → EA closes ALL + deletes ALL → log evidence) — BLOCKED on GUI attach
- [x] Live bar-cycle session via operator pack (COMPLETE 2026-09-21, open market) — 714 polls, 1 new M5 bar, 1 KPI decision, 0 errors, clean shutdown; startup banner verified on console
- [x] Order path on demo (COMPLETE 2026-09-21, live sends) — limit place→visible→cancel OK; market 0.01 fill @4350.394; SL/TP bracket; SL-modify with TP preserved (4354.394); close OK; flat. Script: `06_RESEARCH/scripts/phase_d_order_drill.py`. Fills at requested price, zero rejects (IOC).
- [ ] Live spread × ATR × gate decision logging (feed the ATR-regime law, not a constant)
- [ ] Divergence log updates (`06_RESEARCH/PHASE_D_DIVERGENCES.md` — every fill/slippage/reject recorded)
- [ ] 2-week unattended stability target (zero unhandled exceptions, KPI archive complete)

---

## Track V — Visual conviction / chart overlays (locked 2026-09-20)

Visualization / conviction support ONLY — not an edge-validation track, not an MQL5 logic expansion, never ahead of the export identity patch. Design note: `01_ARCHITECTURE/SMC_VISUALIZATION_ROADMAP.md`. Option A preserved throughout (Python owns all logic; MQL5 stays display-only).

- [x] **V0 — Export identity dependency (COMPLETE 2026-09-20)** — `model_tags` + `pillar_path` + `disp_magnitude_atr` persist on every admitted trade (backtest/paper/live). Was the binding prerequisite; now cleared. Note: `06_RESEARCH/EXPORT_IDENTITY_PATCH_NOTE.md`.
- [x] **V1 — Python research visualizer (COMPLETE 2026-09-20, tightened to chart spec)** — `06_RESEARCH/scripts/trade_inspector.py` (list/show/batch CLI + notebook functions): candlestick window + entry/SL/exit overlays + identity panel (trigger, models, pillar, disp, direction, MFE/MAE + failure_mode via R3-join-or-live-compute, prices, bars, P/L) + PNG + JSON sidecar (timestamp range, hold_bars, notes placeholder) under `results/trade_inspector/`. Curated set rendered: 5 F non-loss + 5 F loss + all 3 B (`curated/`, every chart fully identified). Usage: `06_RESEARCH/TRADE_INSPECTOR_README.md`. POI zone labeled "zone geometry unavailable" (not exported — never invented). No strategy code touched.
- [ ] **V2 — Drawable event schema** — frozen event shapes for level/sweep/poi/fvg/entry/state transitions feeding both V1 and V3 from the same identity fields.
- [ ] **V3 — MT5 display-only overlay for the paper terminal (LATER, paper support only)** — draws V2 events; no strategy logic in MQL5; requires V1+V2 first.
- [ ] **V4 — Clean-chart rules validated** — shared object prefix, ownership by poi_id/route_id, delete on TESTED/VIOLATED/expiry, layer toggles (Levels/Sweeps/POIs/FVGs/Entries), history cap against clutter.

---

## 4. Open Lead Architect rulings still pending

True open decisions only — nothing here is decided until dated in the plan:

1. TP model family to test after R1/R2 (fixed-R vs structure-based vs trail; Gate 1).
2. Spread-grade score semantics — tag-count scale vs true 0–10 quality score (audited bug: A/A+ unreachable as coded).
3. Trigger D long-term disposition — keep dead, resource volume data, or redefine price-only (A5 deferred).
4. M8 HTF provision (D1/H4 data path) vs formal scope-out of V1 claims.
5. Whether research metrics should be reported in R-multiples (recommended — lot-cap binds 100%, raw units are nominal).

---

## 5. Explicit non-goals

- No parameter fishing (no tuning loops against the baseline).
- No strategy redesign before R1/R2 complete.
- No treating demo P/L as idea validation (demo has no TP path either — it replicates the shape by construction).
- No locked-constant edits without a dated ruling in `POST_V1_PLAN_OF_ACTION.md`.
- No new POI models, triggers, ML overlays, capital scaling, or live-money decisions.

---

## 6. Decision gates (provisional — Lead Architect confirms thresholds)

- **Gate 6.1 — strong MFE + synthetic TP helps → exit model primary.** Authorize a V1.1 exit-model research track (TP policy family, per-trigger variants). Promotion bar (proposal): improves per-trigger expectancy with bootstrap CI excluding zero at n≥100 per family, holds in ≥2 ATR regimes, survives a walk-forward split.
- **Gate 6.2 — weak MFE → entry/selection primary.** Run R4, then revisit detection/validation premises. No exit-model work until entries show excursion to harvest.
- **Gate 6.3 — mixed by trigger → family-level diagnosis.** Promote, modify, or quarantine per family. Quarantine = keep code, disable in routing config; never delete history. Kill bar (proposal): family negative under every exit policy and every regime bucket.

---

## 7. Next action marker

- [x] **FLOWCHART↔CODE MAP (COMPLETE 2026-09-20)** — `06_RESEARCH/FLOWCHART_CODE_EVIDENCE_MAP.md`: intended §16 pipeline × verified `04_SRC` module tree × evidence per stage; dominant live path (F continuation on sub-ATR pre-touched stops); 9 absences/mismatches dispositioned (M8/D/C/E silent; tag flicker; killed-vs-traded vocabulary; BE-contamination closed; zone divergence open; spread-grade bug open). Conviction can/cannot lists + ordered next work (instrumentation leftovers / research-only / ops-only / deferred redesign). No strategy changes, no locked edits, no live gates.
- [x] **Lead Architect role & verification protocol documented (COMPLETE 2026-09-21)** — `00_LOCKED/LEAD_ARCHITECT_ROLE_AND_PROTOCOL.md` (ACTIVE/BINDING; roles, source-of-truth order, anti-drift rules with CODED|WIRED|OBSERVED|DRIFTED|SILENT|DEFERRED taxonomy, verification protocol, report contract, startup order, cloud note). Foundation Fidelity Reset restated as active program; F-survivor work PAUSED. Docs-only, no code touched.
- [x] **FR-0b Foundation Reset plan written (COMPLETE 2026-09-21)** — `00_LOCKED/FOUNDATION_RESET_PLAN.md` (ACTIVE; rulings R1–R6 recorded verbatim; FR-0→FR-4 phases; FR-1 hard exit criteria incl. M1-only alarm; role protocol §4 plan pointer updated). Docs-only; no FR-1 code started.

- [x] **FR-1 multi-TF cascade (COMPLETE 2026-09-21)** — resample.py + multi_tf.py + 11 tests + smoke script; H4+H1 detection wired, M8 emits (12 POIs on real window), single-TF alarm live; suite 607 green; per-bar loop integration explicitly residual. Note: `06_RESEARCH/FR1_MULTI_TF_NOTE.md`.

- [x] **FR-2 structural SL/TP routing (COMPLETE 2026-09-21)** — shared helper + F/A/D/E buffered stops (B/C exempt, documented); structural-else-4×ATR TP routing; interim constants listed for lock; 10 new tests + 3 updated assertions; suite 617 green. Note: `06_RESEARCH/FR2_SL_TP_ROUTING_NOTE.md`.

- [x] **FR-3 zone/entry geometry + M4 fidelity (COMPLETE 2026-09-21)** — entry↔zone containment in F (± frozen 0.5×ATR, merge untouched by choice); M4 head clears frozen EQH tolerance (M5-domain split); 4 new tests + marginal decoy + 3 fixture updates; suite 622 green. Note: `06_RESEARCH/FR3_ZONE_M4_NOTE.md`.

- [x] **FR-4 fidelity re-baseline (COMPLETE 2026-09-21)** — October M5 month on post-reset machine; determinism pair byte-identical; funnel 9363→209→8 armed (4 M8)→130 scans→0 routes explained (zone gate binding per diag ablation: 2 F+M8 routes → 2 TP placements → 2 SL closes); M8/TP paths proven in diag; one additive `return_details` hook (suite 622 green). 2-month stretch skipped with rationale. Report: `06_RESEARCH/FR4_FIDELITY_BASELINE_REPORT.md`.

- [x] **FR-4 ARMED-POI FATE LEDGER (residual closeout, COMPLETE 2026-09-22)** — forensics only: 8 armed (4 M8) classified — 2 same-bar TESTED / 3 tested-after-arm / 3 never touched; 0 built-then-rejected, 0 never-scanned; FR-3 gate rejects = 2 (both M8; diag counterfactual maps 1:1 to the same POIs/bars). Replay byte-identical to run1 (SHA ec885eef…), funnel parity 130/130; logging-only shims; no strategy/gate/constant changes. Report: `06_RESEARCH/FR4_ARMED_POI_FATE_REPORT.md` (+ `results/fr4_fidelity/armed_poi_fate.csv` + `..._summary.json`).

- [x] **FR-3.1 on-zone entry anchor (COMPLETE 2026-09-22)** — F resting limit re-anchored into the routed POI zone via shared `zone_anchored_entry` (direction-proximal edge; on-zone behavior bit-identical; gate + ZONE_REFINEMENT_ATR untouched); stop reference follows the anchor (zone distal edge on re-anchor) + degenerate zero-SL guard; October smoke: 0→2 routes, gate rejects 2→0, 0 fills within expiry (recorded, not tuned); 14 new tests, suite **636 green**. Note: `06_RESEARCH/FR3_1_ON_ZONE_ENTRY_NOTE.md`.

- [x] **FR-4b wider window (COMPLETE 2026-09-22, measurement only)** — 3 months post-FR-3.1 frozen run (exec 2025-09-01→11-30): 21 armed (15 M8) → 6 F routes (gate 6/0, no silent rejects) → 5 placed with TP 5/5 → **0 fills** (§23 12-bar window vs proximal-edge retrace; flat book); determinism pair byte-identical; M8 chain 15/4/0. Blocker relocated to the fill regime (Architect design fork on expiry/touch; not local-agent work). Diagnostic only, no parameter search. Report: `06_RESEARCH/FR4B_WIDER_WINDOW_REPORT.md`.

- [x] **FR-4b unfilled-order forensic (COMPLETE 2026-09-22, facts only)** — all 5 orders re-anchored LONGs, all §23-expired exactly at N+11, 0 touch anomalies; fates 3 never-touched (Sept trend-runaway) + 2 touched-after-expiry (both M8 October: +26/+121 bars post-expiry; ticket-5 closest approach 4.43 units in life); forensic run byte-reproduced run1; no strategy change. Ready for D1/D2/D3 ruling. Report: `06_RESEARCH/FR4B_UNFILLED_FORENSIC_REPORT.md`.
- [x] **R7+R8 fill-regime policy (COMPLETE 2026-09-22, per Architect ruling)** — single source `smc/risk/fill_regime_policy.py` (backtest + paper import): R7 place guard skips placement when the market close sits outside the routed POI zone beyond the existing FR-3 band (machine-readable `skip_place_far_from_zone`, retryable — one-shot semantics preserved); R8 HTF resting bars `rest_bars_for` (H1→36, H4/M8/D1→48, else execution-TF §23 default) with give-up (20) as independent backstop; detection_tf/is_m8 provenance threaded bridge→order→paper. Smoke on the FR-4b window: funnel identical, **10 skips / 0 places / 0 fills** (market close at place time +14.65..+165.50 beyond zone vs 1.73..3.84 band); R8 proven live in the superseded limit-ref intermediate run (first filled trade in the chain: zone-high re-anchor, BE-stop +0.48). Residual recorded for the D1/D2/D3 ruling; nothing tuned, GATE_WIDENED=NO. 33-test file, suite **658 green**. Note: `06_RESEARCH/FR_FILL_REGIME_R7_R8_NOTE.md`; policy in `FOUNDATION_RESET_PLAN.md` §8.
- [x] **R9 place-on-reentry intent (COMPLETE 2026-09-22, per Architect ruling; design locked before code)** — R7 skip now ARMS a `PlaceIntent` (full accepted placement frozen at signal) instead of dropping; on band re-entry or limit touch within an R8-sized clock the pending places with remaining bars. Design-locked: §23 clock parity, DOA boundary (remaining<3 never placed), one intent per route (clock never refreshed), candidates-before-intents bar order (double-order defect caught by own test pre-run). Smoke (frozen FR-4b window): 5 armed / 4 expired naturally / **1 placed on re-entry → filled at on-zone limit 4247.355 → BE-managed → closed +0.07** — first complete chain under frozen rules (n=1, M8). One-shot burns only at intent placement; paper mirrors incl. dry-run. 23 tests, suite **681 green**. Design: `00_LOCKED/R9_PLACE_ON_REENTRY_DESIGN.md`; note: `06_RESEARCH/R9_PLACE_ON_REENTRY_NOTE.md`; smoke `results/r9_smoke/run1/`.

- [x] **PHASE 0 + PHASE 1 C1 — one multi-TF product runtime (COMPLETE 2026-09-23, per Lead Architect ruling)** — contract `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` (canonical runtime, one-driver rule, loud-fail policy, non-goals, acceptance tests) + shared seam `smc/orchestration/multi_tf_runtime.py` (`MultiTFProductRuntime.run_batch`, `build_htf_prefixes`, shared `ZoneDedup`, `MissingHtfSeriesError`). Live/paper wired: `LiveLoop` batches on each new H1 close from connector-fetched H4/H1/D1 with a start-time HTF probe that REFUSES to start in product mode; `PaperRunner.arm_multi_tf` delegates to the same runtime; operator config gains `detection_timeframes` + `allow_single_tf_degraded` (detect==exec rejected unless degraded). Real-data parity smoke: live per-TF counts == paper per-TF counts on the same batch; 231 H1 batches → 5 armed, **52 duplicate zones suppressed by the shared dedup**; loud-fail probe raised; degraded probe stamped. 17 new tests, suite **698 green**; no threshold/constant changes. Contract: `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md`; note: `06_RESEARCH/C1_MULTI_TF_PRODUCT_PATH_NOTE.md`; smoke `results/c1_multi_tf_parity/run1/`.

**HISTORICAL MARKER (superseded by the V1.1 freeze — kept for the record):** Choice-1 program review COMPLETE; Track A COMPLETE; Phase D HTF probe PASS; the frozen baseline is recorded in `00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md`. **R9 is ACCEPTED** (design + code + smoke chain n=1: armed→re-entry→fill→BE→close +0.07). F-survivor / F-timing / Monte Carlo stay PAUSED (R6). Resume via `00_LOCKED/LEAD_ARCHITECT_ROLE_AND_PROTOCOL.md` first, then handoff, then `V1_1_RUNTIME_BASELINE_FREEZE.md`, then this marker.
