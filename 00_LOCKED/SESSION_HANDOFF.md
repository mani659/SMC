# SESSION HANDOFF — SMC BOT

## 2026-10-20 (5) — OPS DENSITY SMOKE, live/paper operator path (M-2 gate) — MEASURED (`OPS_DENSITY_STATUS: PASS`)

**Status: COMPLETE — OPS ONLY, NO EDGE/PnL CLAIM. `LOGIC_CHANGED: NO` (no `04_SRC` edit; suite NOT_RUN). Authority: Architect disposition 2026-10-20 (LIVE_PROMOTION blocked until density soak under ~20× arm class). Note: `06_RESEARCH/OPS_DENSITY_SMOKE_NOTE.md`; artifacts `06_RESEARCH/results/ops_density_smoke_session/` (gitignored).**

- **Session 1** (25 min, `--max-seconds 1500`, clean stop): identity gate PASS in-session (DEMO 474608655 @ Exness-MT5Trial15, exact EXNESS-Copy dir, XAUUSDm, dry_run=true, require_demo=true); post-LEG-5b tree (`zone_dedup_retire=true`, product H4+H1, degraded=false). 1 HTF batch (startup, arm_bar 0): H4 20→6→3 / H1 22→8→3 → **armed 3 / duplicates 3** / skipped_tracked 0 / `errors: {}`; board ↔ detect armed matched **60/60 snapshots**; heartbeat healthy (seq 180→720+, age ≤0.5 s, path via terminal_data_path); **errors 0, orders 0**, BOOK empty (product + mode=T), missed bars 0.
- **Session 2 restart residual** (5 min, DONE): **F-7 cold dedup confirmed** — identical funnel reproduced on cold spawn (armed 3 / dup 3), no persistent dedup residue, no double-arm; two spawn→shutdown→respawn cycles clean. Ops quirk documented: `MT5.initialize(path)` leaves its spawned terminal alive + ~60 s respawn cooldown can trip `IPC initialize failed`.
- **Honesty record:** no second H1 boundary fell inside the window (batch cadence observed once); on-window retire churn N/A (< give-up clock) — carried by tests + LEG 5b/6; EA-panel consumption BLOCKED for owner-side observation (not a gate failure per brief); `events.log` wall-clock labels are local time mislabeled "Z" (cosmetic); live concurrent armed max 3 (small-class qualifier — session proves operator-path mechanics under the arming class, not a wider live soak).
- **Next Ready:** Architect live-promotion residual ruling — whether a longer multi-boundary soak is required before LIVE_PROMOTION or the evidenced mechanics + backtest provenance suffice; commit split (operator/config/diagnostic vs the 130-dirty-path tree, git 9b649d5).
## 2026-10-20 (4) — LEG 6 Post-dedup new-arm quality sample — MEASURED (`NEW_ARM_QUALITY_STATUS: PASS`)

**Status: COMPLETE — DIAGNOSTIC, NOT EDGE. `LOGIC_CHANGED: NO` (read-only; logging-only class seams restored in `finally`; the sole `04_SRC` fact: two research capture runs). `locked_constants.py` diff EMPTY; suite NOT_RUN (nothing shipped changed). Authority: Architect ACCEPT of LEG 5b; prior HOLDs untouched. Note: `06_RESEARCH/POST_DEDUP_NEW_ARM_QUALITY_REPORT.md`; script `06_RESEARCH/scripts/post_dedup_new_arm_quality.py`; results `06_RESEARCH/results/post_dedup_new_arm_quality/` (gitignored).**

- **Setup:** one logging-only re-capture of the funnel on the frozen 6m window — **byte-identical to LEG 5b run1** (`trades.csv` `8eecd3b9…`; 606 arms / 606 registers / 219 routes / 65 places / 606 retires) plus an **append-only counterfactual capture** (identical composition, only the retirement seam no-op'd — `PipelineAdapter._retire_dead_keys` is the sole retirement path): funnel **30→10→4→3 fills (F2/C1)**, retires 0, and **armed ids set-equal to LEG 4's 30** — today's composition reproduces the legacy append-only baseline exactly.
- **Cohorts (direct membership, no proxy):** **A = 30** (lifecycle arms matched 1:1 to a counterfactual arm: exact poi-id+bar+zone pass 1, earliest-overlap pass 2), **B = 576** (each verified: 573 via the pre-registered first-match blocker-retire join, 3 via a recorded displacement proof — cf-blocked space AND full give-up chain retired < arm bar: poi-006662/033642/054982; two false gaps poi-047069/059079 were exact-id arms in BOTH runs). Join gaps 0; double-arm live 0; fate gaps 0; cf spaces without a lifecycle heir 0.
- **Funnel (measured in the lifecycle run):** routed A **33.33%** (10/30) vs B **36.28%** (209/576); filled A **6.67%** (2) vs B **9.72%** (56); expired B 7 (1.22%), cancelled 0, resting-at-end 0. Δ **+2.95 pp route / +3.05 pp fill** → INTERPRETATION pre-registered bands: **`NEW_ARMS_SIMILAR_TO_LEGACY`** (conversion only — **no PnL/edge/expectancy claim**).
- **Mixes:** triggers (routes) A F9/C1 · B F188/A9/B8/C1/E3 (F-dominated both ~90%). Exits: A TP1/SL1 · B **TP29/SL27**. Medians: width/ATR 10.6 vs 14.4, disp 2.13 vs 1.87 ATR, arm→route 10.5 vs 12 bars, arm→fill 33.5 (n=2) vs 14 bars.
- **Honesty record:** the pre-registered LEG-4-frozen A-gate FIRED (append-only replay over the lifecycle stream: n_A=25, streams not commensurate) and was replaced by the counterfactual anchor; both amendment evidence trails are in the report §2.3/§2.5 and `results/summary.json`.
- **Next Ready:** Architect ruling on the new-arm class (ops soak / hold density / further research — e.g. per-displacement-ATR breakdown, ops-soak counterfactuals, or hold as-is). No silent implement.

## 2026-10-20 (3) — LEG 5b ZoneDedup lifecycle retirement — IMPLEMENTED (dual-run measured)

**Status: COMPLETE — IMPL_STATUS: PASS. Authority: Architect ACCEPT 2026-10-20 of the LEG 5 design (R1–R8) — implement authorized. `LOGIC_CHANGED: YES` (dedup lifecycle only): `multi_tf_runtime.py` (owned keys, idempotent `retire(owner_id)`, counters; `seen` unchanged), `pipeline_adapter.py` (retire sweep in `prune_terminal_pois`, engine first / registry second; `bind_dedup_registry`), `backtest/runner.py` + `paper/runner.py` (alive-intent obligations), `episode_store.py` (register-signature compatibility, resolution bit-identical). `locked_constants.py` diff EMPTY; no pillar/trigger/fill/expiry change; engine retention untouched. Note: `06_RESEARCH/ZONE_DEDUP_LIFECYCLE_IMPLEMENTATION_NOTE.md`.**

- **Frozen 6m dual run (same window as LEG 4):** Gate A integrity **exact** (2,979 batches / 43,004 merged / **2,021 passed** / SKIP_TRACKED 0, both runs). Gate B: `retired_total` **606** both runs (448 sweeps each, 11 engine-prune releases, `retire_misses` 0, max `live_keys` 5, ends 0). Gate C: **armed 30 → 606 (+576)** · PASS→arm **1.48% → 29.99%** · **dedup 1,991 → 1,415 (−576, exact bucket conservation)** · routes 10 → 219 (F197/A9/B8/E3/C2) · placed 4 → 65 · fills 3 → 58 · intents armed 7 → 152 / placed 26 / expired 0. **No double-arm of a live episode** (≤1 concurrent arm per live key, invariant test-pinned).
- **Determinism:** `trades.csv` (`8eecd3b9…`) / `report.json` (`5145d54e…`) **byte-identical** across run1/run2; 963.7 / 933.3 s (LEG 4 capture: 883.8 s; sweeps ≈ +6–9%).
- **Tests:** 16 new in `test_zone_dedup_lifecycle.py`; suite **1,220 → 1,236 passed (EXIT=0)**; `locked_constants.py` diff empty.
- **Disclosures:** `summary.json` retirement counters `null` (composition imported the runtime class before the seam wrapped it) — authoritative counters are the `retire_sweeps.jsonl.gz` final record; the optional LEG 4-capture offline counterfactual was skipped (blocker obligations are not in that capture) and superseded by the dual run; live restart resets the in-memory registry (F-7); edge-touch + TF-blind keys remain designed residuals; research scripts `d1_f1f2_resample` / `h4_poi_confirmation` still use the old `register(zone)` signature (not run here).
- **Next Ready:** Architect review of the post-implement funnel — whether the armed delta and the 70% dedup remainder are accepted; any further change (per-TF keys, edge-touch, engine retention) arrives as its own dated ruling. No silent expansion.

## 2026-10-20 (2) — LEG 5 ZoneDedup ↔ episode lifecycle — DESIGN LOCK (no code)

**Status: COMPLETE — DESIGN_LOCK_STATUS: PASS; implementation NOT started. Authority Architect ruling R-ARM 2026-10-20 (`ARM_FILTER_IS_BOTTLENECK` — intentional dedup; lifetime too long). Design only: no `04_SRC` edit, no test change, `locked_constants.py` diff EMPTY, `LOGIC_CHANGED: NO`. Note: `06_RESEARCH/ZONE_DEDUP_LIFECYCLE_DESIGN.md`.**

- **Problem, measured (LEG 4):** 2,021 PASS events → **30 ARMED**; `SKIP_DEDUP_EPISODE` **1,991 (98.52%)**; `SKIP_TRACKED` **0**; 29 distinct blockers; blocker age median **29.5 d**, **49.8% ≥ 30 d**, 227 ≥ 90 d, max **140.3 d**; median coverage **0.461**; identical 6 dp bounds 11.5%; **11** zero-area edge-touch suppressions. The key never dies, not the identity rule.
- **Code surface (cited line-level in the note):** `ZoneDedup` = `__init__`/`seen`/`register`/`__len__` only (`multi_tf_runtime.py:135-169`), registry on the runtime (`:272`), one `seen` at `:464`, one `register` at `:493`; `engine.episode`/`arm_at` (`engine.py:250-314`); engine prune `engine.py:510-535`; adapter prune `pipeline_adapter.py:344-373`; give-up scan closure `:150-164`.
- **New code fact (corrects LEG 4's wording):** the adapter retains every POI that `_may_route(..., bar=None)` accepts, and that legacy contract returns True for **all FRESH and TESTED** POIs (`pipeline_adapter.py:362-366, 442-445`) — so `prune_terminal` releases **VIOLATED only**. Verified read-only (armed at bar 0, give-up 20, `prune_terminal_pois` returns `[]` at bars 25 / 500 / 5000, still tracked). "Retire when prune removes it" would fix only a minority of the suppression mass.
- **Design (R1–R7 + R8 residual):** **R1** `register` stores the owner `poi.id` beside the unchanged 6 dp geometry (owner is an attribute, never sameness); **R2** `seen` unchanged, retired keys removed (not flagged); **R3** ONE id-based `retire(owner_id)` at the first per-bar prune step where the episode has **no live obligation** — no resting order, no open position, **no alive R9 intent** (`intents.py:92,140`), no in-flight workflow — **and** (`VIOLATED` **or** `bar_index > arm_bar + poi_give_up_bars()`); called from `PipelineAdapter.prune_terminal_pois`, before the scan and after that bar's arm batch (composition ordering: batch → `runner.on_bar` prune, `phase3_structure_funnel.py:245-306`), so the first affected arm is the next H1 close; **R4** no float re-derivation, no new tolerance; **R5** keys stay **shared** across detection TFs (no per-TF split); **R6** `retire` idempotent, misses counted not raised, no clear-all, counters `retired_total`/`retire_misses`/`live_keys`; **R7** non-goals (no P2/FVG/fill/expiry/trigger/Mode T/engine-retention change, no cap, no score, no "arm everything"); **R8** edge-touch = **residual**.
- **Acceptance gates pre-registered for the implement leg:** A integrity exact (2,979 / 43,004 / 2,021 / one bucket per PASS / 0 batch errors); B `retired_total ≥ 1` (zero = invalid run); C `SKIP_DEDUP` falls, `ARMED > 30` as a **delta not a target**, ≤ 1 concurrent arm per live key (arm→kill→re-arm invariant), blocker-age collapse reported; D byte-identical dual run + auditable `retired` events; E suite green, `locked_constants.py` empty, **`LOGIC_CHANGED: YES` declared**; F control run reproduces the three prior labels with retirement off.
- **Residuals disclosed (§7):** edge touch · TF-blind keys · `seen` never rounds its query · TESTED engine retention (F-1) · in-memory keys reset on restart · legacy degraded live path has no dedup (`live/loop.py:415-441`) · frequency rises as the intended effect · the 20-bar give-up clock now bounds identity memory (a longer memory would be a new rule).
- **Next Ready:** Architect acceptance of the design → implement prompt. Authorised edit surface for that leg: `ZoneDedup` + its two `register` sites + the adapter prune step + one registry bind. No silent implement.

## 2026-10-20 (1) — LEG 4 passed → armed attribution — MEASUREMENT ONLY

**Status: COMPLETE — PASSED_ARMED_STATUS: PASS, LABEL `ARM_FILTER_IS_BOTTLENECK`, `WIRING_BUG: NO`. Authority `00_LOCKED/TECHNICAL_OWNER_PLAN_POST_PROBE.md` LEG 4. No arm-policy, pillar, trigger, expiry or zone-band change; `locked_constants.py` diff EMPTY; no multi-symbol; `LOGIC_CHANGED: NO`. Report: `06_RESEARCH/PASSED_TO_ARMED_ATTRIBUTION_REPORT.md`.**

- **Capture:** `06_RESEARCH/scripts/passed_to_armed_study.py` imports the frozen composition (`phase3_structure_funnel.run`, not forked) and wraps only logging seams (`MultiTFProductRuntime.run_batch`, `MultiTFDetectionDriver.validate_multi`, `ZoneDedup.seen`/`.register`, `PipelineEngine.episode`/`.arm_at`), restored in `finally`. Funnel reproduced **exactly** (2,979 batches / 43,004 merged / **2,021 passed / 30 armed** / 10 routes / 4 placed / 3 fills, 883.8 s). `--analyze-only` reproduced `summary.json` + `pass_disposition.csv` **byte-identically**.
- **Every PASS, one bucket:** `SKIP_DEDUP_EPISODE` **1,991 (98.52%)** · `ARMED` **30 (1.48%)** · `SKIP_TRACKED` **0** · the seven gates with no code path (`freshness`, `posture`, `give-up/expiry`, `one-shot`, `registry/cap`, `TF policy`, `merge order`) **0** · `SKIP_OTHER` 0 · `DATA_GAP` 0. Pass/armed/dedup/tracked **id sets** equal the composition's own batch reports; `bucket_sum = passes = 2,021`.
- **Episode view:** 2,021 events → **30** episodes (product's own dedup rule), each armed exactly **once** (0 never armed, 0 double-armed); median 30.5 events/episode, max **539**; top five episodes = 62.9% of passes; 12 episodes span both detection TFs. Exact-geometry census: **166** geometries (median re-emission 8×, max **252×**), 30 armed / 136 never — the two counts bracket distinct-structure truth, neither is asserted as it.
- **Dedup geometry (the label's evidence):** median coverage of the PASS zone by its blocker **0.461** (p10 0.128 / p90 1.000); identical 6 dp bounds **11.5%**; 22.8% fully covered; **36.0%** at 25–50% coverage and **18.4%** below 25%; **11** events suppressed on a **zero-area edge touch** (the predicate is inclusive on both edges). 1,989/1,991 cross-batch; blocker age median **29.5 d**, **49.8% ≥ 30 d**, 227 ≥ 90 d, max **140.3 d**; 29 distinct blockers.
- **Mechanism (from code):** the arm loop has exactly three gates (`engine.episode` → `dedup.seen` → `engine.arm_at`). `PipelineAdapter.prune_terminal_pois` → `PipelineEngine.prune_terminal` retires TESTED/VIOLATED episodes **every bar**, while `ZoneDedup` exposes only `seen`/`register`/`__len__` — **no removal API**. A zone armed in June therefore suppresses overlapping same-direction zones in November long after the engine forgot the episode. `SKIP_TRACKED = 0` next to `SKIP_DEDUP = 1,991` is that asymmetry in the counts.
- **Reading:** `ARM_FILTER_IS_BOTTLENECK` (pre-registered: dedup ≥ 50% with median coverage < 0.50). Not a wiring hole — every pass reached a gate, none raised, 30 episodes → 30 arms — but the filter is **not doing identity-only work**: 54.4% of suppressions overlap the blocker by less than half the PASS zone, half come from zones ≥ 30 days old, and the extreme case shares a single boundary with zero area. No counterfactual "what would have armed" is computed (that would be a policy proposal).
- **Window coverage:** primary 6m only for the geometry. The 18m secondary was **not re-captured** (identical composition cost 15,313 s / 4.25 h in LEG 3); LEG 3's own 18m secondary funnel (**6,626 passed / 81 armed / 6,545 dedup = 98.78%**) independently corroborates the event-level shape, not the geometry.
- **Artifacts:** report + `06_RESEARCH/results/passed_to_armed/{summary.json,pass_disposition.csv,pass_events.jsonl.gz,_funnel_capture/*}` (results tree gitignored by convention); 25 new tests. Suite **1,220 passed (EXIT=0)**.
- **Next Ready:** Architect ruling on the arm filter — hold as written, design-lock episode retirement, or design-lock an explicit sameness rule (coverage/age). Each needs its own dated ruling, its own pre-registered measure and its own proof register entry. No silent implement; this leg proposes none.

## 2026-10-19 (4) — LEG 3 fill / takeability study — MEASUREMENT ONLY

**Status: COMPLETE — FILL_TAKEABILITY_STATUS: PASS, LABEL `FILL_PATH_HEALTHY` (basis: secondary 18m). Authority `00_LOCKED/TECHNICAL_OWNER_PLAN_POST_PROBE.md` LEG 3. No product decision path, fill model, lifetime or gate touched; `locked_constants.py` diff EMPTY; no multi-symbol; `LOGIC_CHANGED: NO`. Report: `06_RESEARCH/FILL_TAKEABILITY_REPORT.md`.**

- **Capture:** `06_RESEARCH/scripts/fill_takeability_study.py` imports the frozen composition (`phase3_structure_funnel.run`, not forked) and wraps only logging seams (`BacktestRunner.__init__`, `PendingOrderBook.place`, the book's `on_bar`/`_apply_fills`/`_expire_orders`/`cancel_pending_for_poi`/`_cancel_all_pending`/`set_atr` + Friday/news gate reads), restored in `finally`. **Primary 6m reproduces byte-identically** (`trades.csv` `2cd4e4f1…`, `report.json` `b9516af7…`; a second full capture reproduced both).
- **Primary (2025-06-01 → 2025-11-30, 35,725 bars, 899.5 s):** 30 armed / 10 routes / **4 placed / 3 filled / 1 §23 expiry**. The only miss (`poi-034151`, 32 eligible bars) came within **0.744 = 0.156×ATR on the first eligible bar**, then returned at **+289 bars**; `+12/+24/+48` bars of extra rest recover **0/1**. `n = 4 < 10` → this window cannot carry the label by the pre-registered rule.
- **Secondary (2023-12-01 → 2025-05-31, 105,864 bars, 15,312.6 s):** 81 armed / 31 routes / **14 placed / 14 filled**; fates `{FILLED: 14}`, 0 expiries, 0 cancels, integrity clean (14/14 terminal, no anomaly). Medians: eligible **46** bars, **bars to fill 1** (12/14 at the first eligible bar; exceptions at 5 and 24), TP **1.311R**. **LABEL `FILL_PATH_HEALTHY`** (`F = 1.00`, `X = 0.00`, `n = 14`).
- **Reading:** PLACE → FILL is the least lossy stage (3/4 primary, 14/14 secondary); the funnel loses volume upstream — merged → validation survival **4.7–4.8%**, passed → armed **1.2–1.5%**, armed → routed 33–38%, routed → placed 40–45%. Exits after the 14 secondary fills: **8 SL / 6 TP** (gross path, NOT edge — `FILL_PATH_HEALTHY` is a conversion statement, not a quality one).
- **Disclosures:** (1) 4 of the 14 secondary orders share one placement bar (`poi-000452/454/458/461 @193`) → effective ~11 independent episodes; the rule counts orders, so the label stands as defined. (2) The secondary was **re-pinned from 24 months to 18 months before any secondary result existed** after the 24m run decayed to ~6 bars/s and projected to ~8 h (stopped at bar 62,000/141,403 with no summary; `secondary_24m_ABORTED.log`; report §2.1). (3) `route_level_unplaced` is primary-only (null on the secondary).
- **Artifacts:** report + `06_RESEARCH/results/fill_takeability/{summary.json,orders_fate.csv,summary_all.json (basis=secondary),capture_meta.json,events.jsonl.gz,primary_rerun/,secondary_18m/{…},secondary_18m.log,secondary_24m_ABORTED.log}` (results tree gitignored by convention); 21 new tests. Suite **1195 passed (EXIT=0)**.
- **Next Ready:** Architect ruling only. This leg proposes no gate, lifetime, fill-model, or representation change and authorizes none.

## 2026-10-19 (3) — LEG 1 near-miss counterfactual (P2 FVG / BOS) — MEASUREMENT ONLY

**Status: COMPLETE — LEG1_STATUS: PASS, INTERPRETATION: HOLD_P2_FVG. Authority `00_LOCKED/TECHNICAL_OWNER_PLAN_POST_PROBE.md` LEG 1 (placed in `00_LOCKED/` from the owner's posted plan text; no source copy existed in the tree). No pillar/trigger/Mode T/live decision change; `locked_constants.py` diff EMPTY; no threshold search; no multi-symbol; `LOGIC_CHANGED: NO`. Report: `06_RESEARCH/NEAR_MISS_P2_FVG_COUNTERFACTUAL_REPORT.md`.**

- **Capture:** `06_RESEARCH/scripts/near_miss_p2_fvg_study.py --capture` imports the frozen composition (`phase3_structure_funnel.run`, not forked) over the frozen 6m window and wraps only `MultiTFProductRuntime.run_batch` + `DetectionDriver.validate_window` (restored in `finally`). **Funnel reproduced exactly:** 2,979 batches / 43,004 merged / 2,021 passed / 30 armed / 10 routes / 3 fills; P2 37,745 fails (87.77%). 43,004 validation events, ~888 s.
- **Populations (episode clusters via the product's own `ZoneDedup` overlap rule, per detection TF; anchored at the first event defining the population; R = 1× Wilder ATR(14) at the anchor; horizons H20/H50/H100):** **A** strict pass **54** · **B** FVG-absent near-miss (BOS + ≥1× ATR) **88** · **C** wick-only-BOS near-miss **7** (separate, not pooled).
- **Result:** A ≥ B on every favourable cell at every horizon (H50 median MFE 4.04R vs 2.85R; %MFE ≥ 1R 92.6% vs 81.8%; H100 5.97R vs 4.94R) and B has the larger typical adverse excursion at H20/H50 (1.40R vs 0.96R; 2.20R vs 1.59R). C is the weakest population on the favourable side. The pre-registered rule (written before the run, in the report §7) lands in the HOLD branch at both H50 and H100.
- **Reading:** the FVG gate is not shown to be cutting a *better* class of paths on this window; the class it removes travels less favourably from its own first-fail anchor. This is path geometry only — no entry, fill, stop, BE, or cost model was simulated; no expectancy/edge claim exists anywhere in the note.
- **Artifacts:** report + `06_RESEARCH/results/near_miss_p2_fvg/{summary.json,candidates.csv,events.jsonl.gz,capture_meta.json,capture.log,_funnel_capture/}` (results tree gitignored by convention); suite **1174 passed (EXIT=0)**.
- **Next Ready:** LEG 2 Architect ruling only. LEG 1 authorizes no pillar/FVG/BOS/threshold change and proposes none.

## 2026-10-19 — Live / Session Product Funnel Probe (Why armed = 0; Read-Only Diagnostic)

**Status: COMPLETE — Lead Architect dated ruling 2026-10-19 executed. Read-only diagnostic investigation into why `armed = 0` on live session. `locked_constants.py` diff EMPTY, no strategy/trigger/Mode T change, `LOGIC_CHANGED: NO`. Report: `06_RESEARCH/LIVE_PRODUCT_FUNNEL_PROBE_NOTE.md`.**

- **Part 0 (Live Clock & Session):** PID 5040 active on `XAUUSDm` demo; 12 HTF batches run today (01:00 UTC → 12:00 UTC). Triples `H4 a/b/c` and `H1 a/b/c` confirmed from code: `a = detected_raw`, `b = merged`, `c = passed`. With `c = 0`, `_arm_passed()` receives an empty list.
- **Part 1 & 2 (Instrumentation & Autopsy):** Replayed 12 live batches across broker rates (n=126 merged candidates). **Pillar 2 (Displacement) is the overwhelming killer: 111 / 126 (88.10%) rejected at P2** (91 missing directional FVG, 20 missing BOS body-close). Pillar 1 killed 12 (9.52%, naked level), Pillar 3 killed 3 (2.38%, wrong discount/premium region). Autopsy dataset saved to `06_RESEARCH/results/sample_failures.csv`.
- **Part 3 (Research Comparison & Wiring):** Verified against 6-month research baseline (`06_RESEARCH/FROZEN_FUNNEL_6M_NEW_CONTRACT_REPORT.md`). Baseline P2 failure rate was **87.77%** (live is **88.10%** — exact match). Baseline generated only **30 armed POIs across 2,979 batches (~1 every 99.3 hours / batches)**. The probability of 0 armed POIs in 12 batches is **88.58%**. Zero wire bugs found (series valid, trim valid, arm path valid, console accurate, symbol accurate).
- **Deliverables:** `06_RESEARCH/LIVE_PRODUCT_FUNNEL_PROBE_NOTE.md`, `06_RESEARCH/results/live_funnel_replay_summary.json`, `06_RESEARCH/results/sample_failures.csv`.
- **Next Ready:** Architect ruling on scarcity track (relaxing FVG/BOS requires dated design ruling; or enable Mode T for diagnostic order flow).

## 2026-10-19 — Stop Nuisance Heartbeat Unreadable Alerts (EA Debounce + Rate-Limit + Python Logging Hardening; suite 1174)

**Status: COMPLETE — Lead Architect dated ruling 2026-10-19 implemented. Live-ops only: `locked_constants.py` diff EMPTY, no strategy/trigger/Mode T change, watchdog safety NOT disabled, dead-Python protection preserved, `LOGIC_CHANGED: NO`. Edits UNCOMMITTED (base `9b649d5`); commit gate not granted.**

- **Part 0 (Verification):** Live operator process (PID 5332, started 10-17 10:31 UTC) ran post-Fix-A code continuously up to seq 173,975 (~48h runtime, errors 0). Every single unreadable alert recovered on the very next second tick. `FIX_A_IN_PROCESS: YES`.
- **Part 1 (Root Cause):** H3 (sharing violation / transient read-write lock collision under Windows returning `INVALID_HANDLE`) combined with H5 (EA single-tick fail-closed with zero debounce, triggering `Alert()` flood and `Emergency()` position close).
- **Part 2 (Implementation):**
  - **Python (`04_SRC/smc/live/heartbeat.py`):** Rate-limited and signature-deduplicated in-place fallback write warnings (`_replace_blocked_signatures`); clean tmp unlink error suppression; added debounce parameters to pure Python spec `evaluate_watchdog`.
  - **EA Debounce (`05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5`):** Debounce `N=3` consecutive bad ticks (`UNREADABLE_DEBOUNCE_TICKS = 3`) at 1s timer (~3s) before triggering `Emergency("unreadable")`. Bad ticks log to Experts journal (`PrintFormat`), but do not sound alarms. Single-tick recoveries clear the counter immediately.
  - **Alert Hygiene & Flood Limit:** Stale timeout stays fast fail-closed on old timestamps, but Alert flood is gated by `ALERT_FLOOD_INTERVAL_SEC = 300` (at most once every 5 minutes while emergency remains active). Double text `"heartbeat heartbeat"` eliminated.
- **Part 3 (Tests & Diff):** +1 test (`test_watchdog_decision_unreadable_debounce`), suite **1173 → 1174 passed (EXIT=0)**. `locked_constants.py` diff: EMPTY.
- **Owner Action:** Recompile `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` → `.ex5` in MetaEditor; restart operator (`run_live.bat`); observe for 1h.

## 2026-10-17 — Heartbeat Fix A (non-truncating in-place write) + operator resilience B1–B4 (suite 1173)

**Status: COMPLETE — Lead Architect dated ruling 2026-10-17 implemented. Fix A closes the in-place truncate→rewrite window that produced nuisance EA `heartbeat unreadable` alerts (each one runs the EA `Emergency()` close-all); B1–B4 make the operator self-healing (independent heartbeat thread, capped-backoff MT5 reconnect with a loud give-up, structured/rate-limited console, startup banner). Live-ops only: `locked_constants.py` diff EMPTY, no strategy/trigger/Mode T change, watchdog safety not disabled, no `.mq5` change, `LOGIC_CHANGED: NO`. Edits UNCOMMITTED (base `9b649d5`); commit gate not granted.**

- **Root cause (10-15..17):** the in-place fallback used `Path.open("w")` → truncated the file to 0 bytes *before* writing; a 1 Hz EA read in that window saw an EMPTY file → fail-closed "unreadable", self-healing in ~1 s. One continuous session (PID 18456, ~40 h, seq ~145.7k) proves the writer never stopped; 22 of the 10-15 alerts were genuinely stale (a real 16:07–16:31 gap before the session started).
- **Fix A:** `_write_in_place` now `O_RDWR|O_CREAT|O_BINARY` → `lseek(0)` → full write → `fsync` → `ftruncate(len)` (no empty window, no stale tail; **O_BINARY mandatory** — Windows CRT text mode rewrites `\n`→`\r\n`). Atomic replace path + payload format unchanged; **zero EA change**.
- **B1:** `HeartbeatPublisher` lock-guarded + new `HeartbeatRunner` daemon thread (~interval/2 s, file-only, never MT5); started after `LiveLoop.start()`, stopped first in `_shutdown()` so the single `shutdown` marker survives. **B2:** `MT5Connector.is_alive()`/`reconnect()`; poll failures → backoff (1,2,5) s, max 10, gate re-checked, non-zero exit `MAJOR: giving up reconnect …`. **B3:** structured `[poll-error]/[poll-recovered]/[reconnect]` stdout lines, 30 s rate-limit on unchanged signatures. **B4:** banner shows resolved heartbeat path + `HB independent: YES` + `auto-reconnect: YES`.
- **Tests:** +6; suite **1167 → 1173 passed (EXIT=0)**; `locked_constants.py` diff EMPTY. Note `06_RESEARCH/HEARTBEAT_FIX_A_RECONNECT_NOTE.md` (incl. a 15-min no-MT5 soak checklist).
- **Owner actions:** run `run_live.bat` / `--config config/live_demo.json` and watch today's EA log for ≥15 min (expect no empty-window "unreadable"); commit/push decision for the working tree. **Deferred:** POI/STRUCTURE scarcity + Mode T enablement (out of scope here).

## 2026-10-15 — Part 1 residual fixes (R1–R3; suite 1167) + Part 2 idea-vs-impl audit (ALIGNED_WITH_GAPS)

**Status: COMPLETE — Part 1 fixed the confirmation audit's three thin residuals; Part 2 is the read-only philosophy-vs-implementation review requiring owner decisions before anything wider is touched. Base commit stays `9b649d5` (Part 1 edits are UB — working-tree changes left for the owner; commit gate not granted in this engagement). `locked_constants.py` diff vs `v1.1-pre-mode-T`: EMPTY (re-verified post-edit). LOGIC_CHANGED: YES Part 1 (observability wiring only); NO Part 2 (docs-only).**

- **Part 1 (RESIDUAL_FIX_STATUS: PASS):** R1 — entry_t marker LIVE (`ModeTDirector.latest_entry_marker()` read-only accessor → `run_operator._maybe_markers` as `mode_t_poi`; booked `Mode T LIMIT <price>` / `(filled)` / `(dry-run, not sent)`; rejected/cancelled/expired/invalidated → no row — no phantom); the marker signature includes the entry line so dry-run decisions refresh the snapshot and fill/cancel/expiry drop/update it. R2 — session-start JSON `"mode": "T"|"A"` (§2.1) via `_session_start_payload()`, sourced from the CONFIG FLAG (≡ director posture; director is only built inside `_build_stack`). R3 — the tautological writer test now triggers a real OSError path and asserts exactly `False`.
- **Part 1 tests:** +4 R1 tests + 1 R2 test, 1 rewritten; suite **1162 → 1167 passed (EXIT=0)**; nothing weakened; note `06_RESEARCH/MODE_T_RESIDUAL_FIXES_NOTE.md`.
- **Part 2 (IDEA_IMPL_STATUS: ALIGNED_WITH_GAPS):** `06_RESEARCH/MODE_T_IDEA_VS_IMPL_AUDIT.md`. T2_SAMPLES_WHAT: routed Stage-3 survivors of an armed H4/H1 POI whose proof-bar close is within 0.25 ATR of the proof mid (late/chase proofs are logged as skips, never ticked — design-frozen, not drift). Q-answers: visibility OK post-R1; false-product risk LOW (T2 brackets ≠ product geometry; product configs can't enable; README still recommended); scorecard placeholders reach the JSONL durably.
- **Owner decisions pending (correction options — none coded):** C1 ship the tester README one-pager (recommended, rides the demo zip); C3 offline scorecard-grading template (recommended); C4 gap/workflow widening = a DATED design amendment only (deferred); C2 product judgement lines (deferred, separate enhancement); C5 optional dry-run-line toggle (config-only, owner rule).
- **Owner actions:** recompile `.ex5` · demo on `config/live_tester.json` · commit/push decision for the Part 1 working tree (staged summary left in the note) · pick corrections from Part 2 C-table.

## 2026-10-15 — MODE T CONFIRMATION AUDIT executed (read-only; PASS_WITH_RESIDUALS)

**Status: COMPLETE — the audited deliverable set was re-derived from the binding design `00_LOCKED/MODE_T_CONSOLE_MARKER_DESIGN.md`, not commit lore. Read-only audit: no T2/threshold/product-path/locked_constants/MQL5 change; suite re-run green (1162 passed, EXIT=0); `locked_constants.py` diff vs `v1.1-pre-mode-T` = 0 lines; `.mq5` copies byte-identical. Report: `06_RESEARCH/MODE_T_CONFIRMATION_AUDIT.md`.**

- **Critical set ALL MATCH:** T2 mid-entry geometry + ≤0.25 gap gate + LIMIT-only (no market path), flag defaults (product OFF / tester ON + require_demo), product path flag-off unchanged, EA safety-first order with zero trading logic, mode=T ledger §2.5-verbatim (incl. `anomaly_ts_iso` + blank expert placeholders), one-shot per (poi, proof), 11-entry taxonomy + `PLACE_REJECTED_<retcode>` tail, dry_run logs decisions and sends nothing.
- **Findings (non-blocking):** session-start JSON lacks §2.1's `"mode":"T"` key (separate posture log line exists — doc-grade, fix needs owner sign-off); EA cleans dropped marker ids only at the 30 s stale-clear; live-day JUDGEMENT block sources Mode T ledger only (pure-product sessions print the flat idle line); `entry_t` marker not populated on live wiring (`mode_t_poi=None` — writer capability proven in tests only); never-raises writer test is tautological (code independently verified safe).
- **Doc integrity:** no tracked reference to the obsolete `MODE_T_VOLUME_BASED_ENTRY_DESIGN.md` name; commit body cites the correct design file.
- **Owner actions pending:** `.ex5` recompile (MetaEditor; current `.ex5` = Oct 7 binary), internal demo on `config/live_tester.json`, push decision for `9b649d5` (branch ahead 1, unpushed). NEXT READY: idea-vs-impl correction audit | demo | push.

## 2026-10-15 — MODE T + CONSOLE JUDGEMENTS + CHART MARKERS implemented (three seams; suite 1162; LOGIC_CHANGED YES-seams-only)

**Status: COMPLETE — the locked design `00_LOCKED/MODE_T_CONSOLE_MARKER_DESIGN.md` implemented end-to-end. Baseline tag `v1.1-pre-mode-T` still the revert point. Product strategy path untouched; `locked_constants.py` diff EMPTY (Mode T numbers live in `04_SRC/smc/live/mode_t.py`, test-pinned). Entry-rep families remain RETIRED; Mode T stays DIAGNOSTIC (mode=T on every decision/ticket).**

- **(A) Mode T shipped:** `smc/live/mode_t.py` (constants T_MAX_GAP_ATR=0.25 / T_TP_ATR=1.0 / T_REST_BARS=12 / T_MAX_CONCURRENT=2 / T_MAX_PER_DAY=6; banner §2.1 verbatim; pure `decide_mode_t` rule T2 frozen order duplicate→session→spread→product-tie→NO_ATR→GAP_TOO_WIDE→caps→volume→PLACE; exhaustive 11-entry skip taxonomy) · `operator_config` new keys (`diagnostic_entries` default false, `judge_interval_s` 60, `marker_enabled` true, `marker_path` "") with the geometry keys still loud-rejected · `ModeTDirector` (one-shot per (poi,proof), caps, 12-bar rest expiry, §5-invalidation + Friday-EOD §28.4 cancels, `PLACE_REJECTED_<retcode>` tail, clean-stop resting cancels) · `run_operator._mode_t_on_poll` at the candidate/limit seam (adapter routed-not-accepted workflows; product wins ties via broker-truth comment-prefix scan; LIMIT-only through `PaperRunner.broker.place_limit`; **dry_run logs every decision, sends nothing**) · ledger `logs/…/mode_t_events.jsonl` note-verbatim §2.5 fields (incl. `anomaly_ts_iso`) + blank scorecard placeholders · `config/live_tester.json` created per §5 (diag ON + require_demo + dry_run); `live_demo.json` untouched (flag absent → OFF).
- **(B) Console judgements shipped:** `smc/live/judgement_console.py` (blocks MODE/POIS/SWEEPS/SEEKING/JUDGEMENT/BOOK/HEARTBEAT; honest empties incl. `JUDGEMENT: flat … idle`; ASCII pure renderer) + `run_operator._maybe_judge` — ≥1 full board per `judge_interval_s` even flat (0 disables); lines from ledger tail only; no tracebacks-as-status, no fill-only printing.
- **(C) Markers shipped:** `smc/live/marker_writer.py` (`smc_markers.csv` header exact; ≤11 objects; sweep line only when the linked armed POI's zone edge prices it — honest skip otherwise; atomic write-temp+rename w/ in-place fallback; OSError → logged False never raises) at `_publish_console`/`_on_poll`; `SMC_Safety_Watchdog.mq5` + `dist/mql5/` copy — `InpMarkerFile` input; timer order FROZEN (heartbeat safety first, markers second); draws/deletes only `SMC_*` OBJ_RECTANGLE/HLINE/LABEL; >30 s stale file → clears markers; heartbeat stale → `HEARTBEAT STALE` red corner label; zero trading logic; **user must recompile the .ex5 locally** (shipped .ex5 is the old binary).
- **Tests:** +35 (`test_mode_t.py`, `test_mode_t_console_markers.py`); suite **1127 → 1162 passed** (exit status preserved via PIPESTATUS). Two `test_perm_hardening` live-poll tests transiently broke when the hook was mis-anchored inside `_on_poll`; root cause fixed by re-anchoring after the spread/ATR/book block — no skipped checks. Flat board smoke OK; config smoke both jsons OK.
- **Note:** `06_RESEARCH/MODE_T_IMPLEMENTATION_NOTE.md` (paths, disclosed limits, note-verbatim appendix). **NEXT: owner internal demo on the tester config → rebuild the tester zip (not automatic ship).**

## 2026-10-15 — MODE T + CONSOLE JUDGEMENTS + CHART-MARKER CONTRACT design locked (docs-only)

**Status: COMPLETE — Lead Architect design lock for the next release's three seams, per the mode-T/console-marker design task. Baseline = tag `v1.1-pre-mode-T` (revert point). Docs only: `00_LOCKED/MODE_T_CONSOLE_MARKER_DESIGN.md`; no `04_SRC` edit, no MQL5 edit, `locked_constants.py` diff empty, `LOGIC_CHANGED: NO`. Entry-rep families stay RETIRED; Mode T is DIAGNOSTIC — visible activity + labelable tickets, never an edge or representation claim.**

- **(A) Mode T (frozen values):** config `diagnostic_entries` bool default false (product configs leave it absent; tester config ON + require_demo true); exact banner string in the note. ONE primary rule **T2** — preconditions (flag, armed H4/H1 POI, Stage-3 proof closed, session, §28.5 gate, no same-episode product candidate) then ONE LIMIT at proof-bar mid `(high+low)/2` in thesis direction IFF `gap = abs(entry−close(proof))/ATR <= T_MAX_GAP_ATR (0.25)`, else skip via the frozen taxonomy. SL = proof-bar adverse extreme; TP = `entry ± T_TP_ATR (1.0) × ATR` — Mode T's OWN diagnostic brackets, never inherited product geometry; min-lot volume; caps `T_MAX_CONCURRENT=2` / `T_MAX_PER_DAY=6`; resting lifetime `T_REST_BARS=12`; cancel on §5 invalidation / Friday 20:00 UTC; no separate news cancel (no news feed on the live path — disclosed). Per-decision ledger `logs/phase_d/mode_t_events.jsonl` with mode=T + poi_id/tf/entry/sl/tp/gap_atr/skip_reason + scorecard placeholders `level_ok/sweep_ok/confirm_ok/timing/would_take` (V1 blank). Constants home = future `mode_t.py`, never locked_constants.
- **(B) Console judgements:** new knob `judge_interval_s` (default 60 s, 0=off) guarantees ≥1 full board per interval EVEN WHEN FLAT (event-mode silence superseded for the board; alive ping unchanged); fixed blocks MODE / POIS / SWEEPS / SEEKING / JUDGEMENT / BOOK / HEARTBEAT in plain language from the read-only snapshot + Mode T ledger only; forbidden: fill-only printing, tracebacks-as-status, invented desirability text.
- **(C) Chart markers:** `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` gains ONE marker duty on the existing 1 s timer — CheckHeartbeat first, markers second, marker failure never disables safety. Python writes `smc_markers.csv` (keys `marker_path` default EA-readable dir, `marker_enabled` default true) with the SAME candidate-list/write-probe/atomic-replace discipline as the heartbeat. CSV schema + object caps frozen: ≤8 `OBJ_RECTANGLE` POI zones + 1 sweep `OBJ_HLINE` + 1 Mode T entry `OBJ_HLINE` + 1 corner `OBJ_TEXT` (`SMC Mode A` | `SMC Mode T` | `HEARTBEAT STALE`); file stale >30 s → EA deletes all `SMC_*` objects; safety behavior unchanged (stale heartbeat still closes/deletes scoped).
- **Config matrix:** exact keys frozen in the note for a new `config/live_tester.json` vs `config/live_demo.json` (demo: `diagnostic_entries` absent, `dry_run` stays true). Next tester zip duties: Mode T ON + marker path aligned to terminal + README one-pager (levels + early/late scorecard).
- **NEXT ACTION: implementation prompt — Mode T flag/builder at the candidate/limit seam + console judgement blocks + Python marker writer + EA marker reader (`LOGIC_CHANGED` becomes YES there; revert via tag `v1.1-pre-mode-T`).**

## 2026-10-14 — Mode A LTF-return selection-breadth amendment locked (docs-only; pending Architect acceptance)

**Status: COMPLETE — the ONE permitted amendment before one final offline feasibility measure, per the amendment directive. Docs only: `00_LOCKED/MODE_A_LTF_RETURN_SELECTION_BREADTH_AMENDMENT.md`; no `04_SRC/smc` edit, no test change, no `locked_constants.py` edit, no frozen artifact touched, product wiring NOT started, `LOGIC_CHANGED: NO`. The prior measure's INCONCLUSIVE verdict is NOT reinterpreted.**

- **What it changes (design only):** the singular-nearest §4b/§4c selection rule is replaced by ONE deterministic broadened representation: **candidate set → filter → rank → exactly ONE selection**. Candidate set = ALL M5 FVGs of the product's own detector (validity verbatim, no new maturity rule/constant), direction-matched, formation completed by the true proof close, wholly inside the FIXED [proof−48, proof] window (no wider span exists). Filter = the chosen near edge strictly protected-side of the true proof-bar close (existing semantics). Rank = R1 smallest completed-formation bar distance → R2 smallest |near edge − close(proof)| → R3 more recent formation end → R4 stable detector/source order. If no candidate survives → `STRUCT_UNAVAILABLE`. At most one concurrent candidate/order/ticket per episode.
- **Origin OB unchanged in role:** clearly separated, REPORT-ONLY alternate under the product's own R1 §3.1 pairing applied to the SELECTED FVG; never a fallback limit, never stacked/blended, never in any verdict or kill computation.
- **Verdict redesign (frozen numeric gates, BEFORE any script):** the old generic `STRUCT_UNAVAILABLE` path is split — TRUE data/provenance gap (`DATA_GAP_PROVENANCE`) vs representation-coverage failure (`NO_STRUCTURE_SELECTED`, named terminal reasons a–e). First-fired gates: control-evaluability < 3 → INCONCLUSIVE; true-gap rate > 0.10 → INCONCLUSIVE; coverage < 0.70 → FAIL_COVERAGE; near-mass (≤ 1.0 ATR over full P1) < 0.50 → FAIL_NO_NEAR_MASS; structured median > 2.0 ATR → FAIL_STILL_FAR; retention 0 with 3 evaluable → FAIL_BASELINE; paper-expires > 0.85 at n ≥ 20 → FAIL_UNFILLABLE; else PASS_FEASIBILITY (Architect discussion only, never a ship decision). A failure retires active Mode A LTF-return representation work ONLY — Mode A, SMC detection, POI/sweep/proof evidence and the project are NOT declared invalid.
- **Frozen non-changes + recorded impurity:** HTF context label-only (no HTF-edge limit input), FR-2 distal stop, engine §5, rest lifetime, FR-3/R7/session/§28, trigger/pillar/POI/routing, no market orders; the possible coexistence of the selected M5 limit with FR-2/HTF-oriented stop geometry is recorded as a measure impurity — entry-representation assessment only, no stop redesign authorized.
- **Prohibitions (binding, §7):** no 48-bar widening, no sequential fallback, no post-hoc threshold tuning, no HTF-edge limit under a new name, no multi-candidate per episode, no hybrid FVG/OB, no stop-logic change in this measure, no product/live/paper wiring from pass OR fail. Self-audit (§8): one bounded final selection-breadth experiment, not a new strategy family.
- **NEXT ACTION: Architect acceptance → ONE final offline feasibility measure per this amendment (its own dated read-only task; NO further amendment before that measure runs as-is; re-frozen kills are in the amendment, not a future decision).**

## 2026-10-14 — LTF-return feasibility measure executed (frozen verdict: INCONCLUSIVE; read-only research)

**Status: COMPLETE — the accepted design's §6 gate run as instructed (PRIMARY = M5 displacement-FVG singular-nearest; OB = report-only alternate, no hybrid; strict protected-side rule or STRUCT_UNAVAILABLE; no HTF-edge input; intersection LABEL only; FR-2/§5/rest-lifetime reused exactly). Read-only; 8 new tests; full suite green; dual-run byte-identical; `locked_constants.py` diff = only the pre-existing dated spread-grade amendment; no production file changed; `LOGIC_CHANGED: NO`; no post-hoc parameter change.**

- **Method (frozen per design + acceptance):** base rows reused row-for-row from the entry-rep artifacts (true frame +6018 asserted); structure detection via the product's OWN FVG detector (`smc.detection.fvg_detector.detect_fvgs`, locked §3 semantics) + the product's R1 §3.1 origin-OB pairing, imported read-only; selection = THE singular nearest-the-proof direction-matched FVG inside the reused [proof−48, proof] window, limit = near edge IFF strictly on the protected side of the true proof close, else the same-formation OB report-only, else STRUCT_UNAVAILABLE (fail-closed, never inferred); retest = product rest lifetime, touch-only paper (SL/TP never invented); HTF-zone intersection = label column only (114 True / 33 False on the found rows; no filter).
- **Build-time defect caught by tests before final artifacts:** the first draft fell through to the NEXT-nearest FVG when the nearest failed strict side — the frozen design fixes the primary as the SINGULAR nearest formation; corrected (implementation fixed, tests passed 8/8) before the finalists were written; two corrected runs byte-identical.
- **Results (frozen first-fired order):** STRUCT_FOUND 147/268 (54.9%: FVG 119 + OB-alt 28); **STRUCT_UNAVAILABLE 121 (45.1%)** → `data_gap_rate_p1` 0.451 → **kill 1 (INCONCLUSIVE) FIRED** — the verdict denominator is the full frozen P1 population and 45.1% of it has no honest geometry under the frozen selection rule; kill 3 also fires in the record (≤1.0 ATR over all P1 = 34.7% < 50%). On the readable subset the story works: median gap **0.638 ATR** at proof (63.3% ≤ 1.0 over the 147 found rows), the OB-alternate subset even tighter (median 0.26), and the retired control baseline reproduced (median 8.275, 4.1% ≤ 1) — an order-of-magnitude representation improvement ON THE READABLE SUBSET, honestly unreadable on the full population. Gap at the arm bar deepens again (median 15.62 ATR — waiting loses the structure, consistent with prior studies). Paper (touch-only): 126 FILLED_NO_RESOLVE / 21 EXPIRED (14.3% of 147 path rows) / 121 DATA_GAP. **Fills: 1/2 evaluable retained (poi-014146 via OB-alternate, gap 0.39); poi-073511 FVG expired; poi-047805 (C-trigger ending-diagonal leg) STRUCT_UNAVAILABLE — kill 4's 3-evaluable gate unsatisfiable → the kill is UNPROVABLE on this window, disclosed rather than forced.**
- **Verdict (exact first-fired): INCONCLUSIVE** (`[INCONCLUSIVE (0.451 > 0.30), FAIL_NO_NEAR_MASS (0.347 < 0.50)]`) — NOT PASS_FEASIBILITY and NOT a family kill: the near-market representation demonstrably works where geometry is honestly readable; the §4b singular-selection rule cannot read 45.1% of rows, and neither substituting geometry nor widening the window was permitted by the acceptance.
- **Artifacts:** `06_RESEARCH/scripts/ltf_return_feasibility_measure.py` · note `06_RESEARCH/LTF_RETURN_FEASIBILITY_NOTE.md` · data `06_RESEARCH/results/ltf_return_feasibility/{rows.csv, summary.json}` (278 rows; + `_run2` determinism mirror) · tests `04_SRC/tests/test_ltf_return_feasibility_measure.py`.
- **NEXT ACTION: Architect review of the feasibility result** — re-rating §4b selection breadth / re-pinning the window / stopping are ALL design-amendment decisions for a dated follow-up with re-frozen kills; none proposed or authorized by this measure.

## 2026-10-14 — OWNER RULING + Mode A LTF-return entry design locked (docs-only; pending Architect acceptance)

**Status: COMPLETE — owner ruling (binding) + one dated design lock per the tightened directive. Docs only: `00_LOCKED/MODE_A_LTF_RETURN_ENTRY_DESIGN.md`; no `04_SRC/smc` edit, `locked_constants.py` untouched, product wiring NOT started, `LOGIC_CHANGED: NO`.**

- **Owner ruling recorded:** Mode A entry identity = **HTF (H4/H1) thesis + location CONTEXT → M5 LTF proof (TIMING) → entry from a deliberately defined LTF RETURN STRUCTURE** — NOT a price derived from the HTF zone proximal edge. **Proximal-edge family RETIRED from active experimentation** (FR-3.1 edge limits, RL-1/2/3, prior reactive-admission R1–R6) — control-evidence only; no parameter retune of any retired family.
- **Design lock (one family, not a menu):** PRIMARY structure = the nearest **M5 displacement FVG of the proof leg** (3-candle gap, all bars within the reused H_PROOF=48 lookback, nearest-the-proof formation); clearly-secondary ALTERNATE = the leg's origin OB (product's own Trigger-F shape, read-only import). **Limit rule (one line): limit = the near edge of the chosen M5 return structure, iff strictly on the protected side of the true proof-bar close; else `STRUCT_UNAVAILABLE` (fail-closed, no market-order fallback).** Stop = structure's far edge via the unchanged FR-2 `structural_sl` path; invalidation = engine §5 semantics; retest window = the product's own rest lifetime (reused, no new constant); expiry = no touch in-window. Episode identity/one-shot: attributes only, one candidate per first proof, the one-shot consumes at first placement; episode store stays observability-only.
- **Pre-registered feasibility measure (frozen now, §6):** same P1(268)/P0(10)/P2 + verified frame; metrics = structure mass, near-market presentation (gap_atr vs proof/arm; ≤1.0/≤2.0 report bands), FVG/OB strata, DATA_GAP, fill overlap, optional touch-only paper EXPIRED; CONTROL proximal-edge column scored identically. **Frozen kills (first-fired):** DATA_GAP>30% → INCONCLUSIVE; median gap_atr>2.0 → FAIL_STILL_FAR; share≤1.0<50% → FAIL_NO_NEAR_MASS; 0/3 fill-retained (evaluable) → FAIL_BASELINE; paper EXPIRED>85% at n≥20 → FAIL_UNFILLABLE; else PASS_FEASIBILITY (discussion unlock only).
- **Compatibility:** FR-3 zone gate / R7 / session / §28 unchanged — NOT quietly carved: if ever wired, the zone-membership gate carve-out for HTF-context is an explicit Architect ruling (§8 Q1). Retired family appears only as the frozen control baseline.
- **Open questions (5):** gate/R7 carve-out scope; FVG-first vs OB-first precedence; FVG maturity rule (mitigation test or not); M5-only confirmation; rest-lifetime coupling.
- **NEXT ACTION: Architect acceptance → the offline LTF-return feasibility measure (its own dated read-only task, kill criteria frozen above; no ship on PASS alone).**

## 2026-10-14 — Entry-representation offline measure executed (verdicts: RL-1/RL-3 FAIL_STILL_FAR, RL-2 FAIL_NO_NEAR_MASS; research only)

**Status: COMPLETE — the accepted design's §5 measurement gate run as instructed (PRIMARY under test: RL-1 pullback_shelf; RL-2/RL-3 side-by-side; no stacking; TP/SL unchanged — limit only). Read-only counterfactual limits on the frozen 6m populations; 8 new tests; full suite green; dual-run byte-identical; `locked_constants.py` diff = only the pre-existing dated spread-grade amendment; `LOGIC_CHANGED: NO` (no `04_SRC/smc` decision-path edit — the only `04_SRC` addition is the test file; **no rule earns PASS_MEASURE — no implement discussion unlocked**).**

- **Method (frozen per design §5 + measure pins):** reused the true-frame entry-rep artifacts (P1 = 268; P0 = 10) + the reactive module's grid/ATR/edge helpers (never forked); per row × rule {CONTROL, RL-1, RL-2, RL-3}: counterfactual limit, gap_atr vs true proof close (primary) + arm close (secondary), ≤1.0/≤2.0 reporting bands (never gate), RL-3 present-condition (NAMED `market_reentered_zone` + ≤1.0-ATR proximity within the R8 lifetime), paper paths (P0 recorded SL/TP via near-miss semantics; P1 touch-only, SL/TP never invented). k=1.0, the 50% transform, the 96-bar leg lookback, and all kill thresholds frozen in the script header BEFORE the run and test-pinned; no post-hoc tuning.
- **Results:** CONTROL baseline reproduced (median 8.27, 4.1% ≤ 1 ATR, 2/3 fills retained, 13.1% expired). **RL-1: FAIL_STILL_FAR (median 7.73; 12.3% ≤ 1 ATR)** — its own guard rails bind: 235/268 fallback to the CONTROL edge (194 × guard3 proof-extreme overflow, 41 × guard2 tunneling), so the frozen rule barely moves the geometry. **RL-2: FAIL_NO_NEAR_MASS (FIRST-FIRED; 3.4% ≤ 1 ATR)** — but the evaluation is INCONCLUSIVE-grade: **73.5% DATA_GAP** (197/268 rows have no proximal-edge touch inside the 96-bar lookback — the displacement leg is unmeasurable at the frozen pin; the ≤ 1-ATR share is computed over the full population); the usable subset (n=71: median 4.77, P0 0.75) is suggestive, not readable as a verdict; nothing was widened to rescue it. **RL-3: FAIL_STILL_FAR** (limit unchanged → CONTROL-identical gap stats; its own mechanism shows 81/268 presented, median 12 bars to presentation, 187 expire un-presented, 98.8% of the presented fill within their remaining lifetime — presentation is the bottleneck, mirroring the closed measure's R3 finding).
- **Fill overlap:** 2/3 retained under EVERY rule — nothing destroys the baseline geometry; the fail is "still far", not "baseline broken". (Disclosure: lifetimes re-anchored at the proof/first-presentation bar, not the near-miss placed-bar ledger — 1/3 control fill reads EXPIRED here that read SL_HIT there; stated plainly in the note.)
- **Artifacts:** `06_RESEARCH/scripts/entry_representation_measure.py` · note `06_RESEARCH/ENTRY_REPRESENTATION_MEASURE_NOTE.md` · data `06_RESEARCH/results/entry_representation_measure/{rows.csv, summary.json}` (1,112 rows = 278 × 4; + `_run2` determinism mirror) · tests `04_SRC/tests/test_entry_representation_measure.py`.
- **NEXT ACTION: Architect review of the representation measure.** All three accepted candidates fail as frozen; any follow-up (amending RL-1's guard rails, widening RL-2's leg span, or stopping on the fill-retention result) must arrive as its own dated design amendment — none proposed or authorized by this measure.

## 2026-10-14 — Entry-representation design locked (docs-only; DESIGN_LOCKED pending acceptance)

**Status: COMPLETE — Lead Architect directive after the entry-representation study PASS. Docs only: design note `00_LOCKED/ENTRY_REPRESENTATION_DESIGN.md`; no `04_SRC/smc` edit, `locked_constants.py` untouched, product limit change NOT started, `LOGIC_CHANGED: NO`.**

- **Purpose:** propose exactly 3 alternative limit-construction rules confronting the measured gap (P1 median ~8.27 ATR at proof; 86.6% zone-edge & >1 ATR away; waiting to arm deepens the gap), each offline-measurable with pre-registered kill criteria BEFORE any implement. Policy paper, not a limit change.
- **Rules:** RL-1 `pullback_shelf` (PRIMARY rec; limit = true-proof-bar close ± 1.0×ATR with three guard rails, own replacement gate, fail-closed fallback to the FR-3.1 edge) — mechanical; RL-2 `retrace_mid` (parameter-free 50% retracement of the measured displacement leg from the proximal edge toward the leg extreme) — mechanical; RL-3 `edge_plus_wait` (FR-3.1 limit VERBATIM, no new formula; presentation deferred to the first bar inside the R8 lifetime where the NAMED `market_reentered_zone` rule AND a ≤1.0-ATR proximity guard hold; R9 machinery unchanged) — lifecycle/placement.
- **Measure pre-registered (section 5, frozen):** same P0/P1/P2 populations + verified frame; per-rule median gap_atr at proof (primary) + arm (secondary), ≤1.0/≤2.0 reporting bands (bands never gate), fill overlap with the 3 control fills, paper EXPIRED under frozen near-miss semantics, fallback counts. **Frozen kills (first-fired): median ≥ 6.0 → FAIL_STILL_FAR; share ≤ 1.0 < 10% → FAIL_NO_NEAR_MASS; 0 fill overlap (evaluable) → FAIL_BASELINE; paper EXPIRED > 90% at n ≥ 20 → FAIL_UNFILLABLE; DATA_GAP > 20% → INCONCLUSIVE; else PASS_MEASURE.** k=1.0 and the 50% transform are frozen NOW; no post-run tuning.
- **Stance:** representation first, then admission (recommended; the R4 proximity guard evaluated the very input this design reworks). The FAIL_TIGHT admission measure stays CLOSED; RL-3 does not reopen it.
- **Non-goals held:** no mid-zone fishing (all limits are fixed transforms of measured structure), no market-order shape (RL-1's protected-side guard), no Mode B/ML, no proactive pre-sweep limits, no expectancy claims.
- **Open questions (5):** primary rule ratification; structural TP coupling under moved limits; OB distal vs zone distal stop reference; rule layering/exclusivity; sequencing of the H4 frame-residual re-run decision feeding presentation-time metrics.
- **NEXT ACTION: Architect acceptance → the offline representation measure (its own dated read-only task) for the chosen primary rule.**

## 2026-10-14 — Entry-representation study executed (VERDICT_FAMILY: BOTH; research only)

**Status: COMPLETE — Lead Architect tightened directive 2026-10-14 (admission measure CLOSED, not re-run/retouched). Read-only diagnostics: why do entry limits sit far from the post-impulse market? 14 new tests, suite green; dual-run byte-identical; `locked_constants.py` diff = only the pre-existing dated spread-grade amendment; `LOGIC_CHANGED: NO` (no `04_SRC/smc` decision-path edit — the only `04_SRC` addition is the test file; no rule softened; no implement).**

- **Question:** classify the limit-vs-market gap as MECHANICAL / LIFECYCLE / BOTH / INCONCLUSIVE, distributions + stratified counts + max-5 hypotheses (each "NOT implemented in this task").
- **Populations (frozen):** P0 = the 10 frozen product routes; P1 = 268 armed+coincident rows of the frozen admission artifacts, reused row-for-row; P2 (report-only) = the 138 rows that failed the admission's R4 only — exactly the published count.
- **Frame ruling (the critical method fact):** all artifact bar columns (reactive `proof_bar`/`armed_bar`, candidates `first_present_bar`) are EXEC-frame; true grid = exec + 6018 (the parent measure's own asserted offset, ts-verified on every P0 route and sampled P1 episodes). All gap math here is true-frame; the closed measure's own presentation columns are NOT reused.
- **RESULTS (primary reference = true proof-bar close):** median gap P1 = **8.27 ATR** (21.76 units; p25 4.50 / p75 14.02) vs P0 routes 5.80; only **4.1%** of P1 rows ≤ 1.0 ATR; gap deepens by the arm bar (median 13.8 ATR) — nothing recovers toward the zone-edge limit; **VERDICT_FAMILY: BOTH** — mech 86.6% (232/268 zone-edge limit > 1 ATR away at proof; the on-edge anchored shape dominates), life 23.9% (64/268 armed-after-proof, exact published-count cross-check). Strata: routed entries (market-relative) median 3.24 ATR / 22% ≤ 1 vs 8.61 / 2% for the zone-edge fallback; trigger F farthest (8.70); zone width does NOT separate the strata (H5 not supported here).
- **Control fills (n=3):** all three sit at gap_atr_proof 1.28 / 1.68 / 2.25 — the geometry tail that fills.
- **Instrument residual disclosed (measure stays CLOSED):** the closed admission measure's market geometry (presentation columns, `atr_at_proof`) evaluated at grid index `first_coinc_bar − 6018` — 6018 slots earlier than its own published timestamps (verified by exact ts comparison). Quantified by disclosure columns: 18/268 rows change side of the 1-ATR line between frames (≤1 ATR: 4.1% true vs 2.6% shifted). No verdict/rule/threshold re-derived; re-running the closed measure on the verified frame = its own dated Architect decision.
- **Artifacts:** `06_RESEARCH/scripts/entry_representation_study.py` · note `06_RESEARCH/ENTRY_REPRESENTATION_NOTE.md` · data `06_RESEARCH/results/entry_representation/{rows.csv, summary.json}` (+ `entry_representation_run2` determinism mirror) · tests `04_SRC/tests/test_entry_representation_study.py`.
- **NEXT ACTION: Architect review of entry representation only** — any representation redesign arrives as its own dated design + pre-registered rules before code; the H4 frame residual is recorded for a separate decision.

## 2026-10-13 — Offline reactive-admission measure executed (FAIL_TIGHT; research only)

**Status: COMPLETE — owner plan binding step 4's §5 measurement gate. Read-only counterfactual: R1–R6 applied as a fail-closed classifier on the frozen 6m artifacts; 35 new tests, suite **1097 passed**; dual-run byte-identical; `locked_constants.py` diff = only the pre-existing dated spread-grade amendment; `LOGIC_CHANGED: NO` (no `04_SRC/smc` decision-path edit — the only `04_SRC` addition is the test file; no gate loosened; no M15; no ML). Nothing authorizes live wiring.**

- **Question:** does the accepted reactive rule set admit enough armed+coincident candidates to justify an implement prompt, without destroying the product's baseline paths? Killed-or-carry per the design's own §5.3 thresholds.
- **Method (frozen in the script header):** the coincidence study's own 585 rows re-used row-for-row (one would-be candidate per episode at its FIRST proof); populations asserted 268 (armed+coincident) / 208 (validated-in-packs) / 109 (other); R1 arm-at-or-before-proof; R2 aligned completion; R3 return-to-zone within 20 bars of proof INCLUDING the proof bar; R4 presentation = first bar satisfying the NAMED rule `market_reentered_zone` (imported) + 1.0-ATR proximity; R5 chase 1.5×ATR + product sessions + engine-true touch-first violation semantics; R6 one-shot consumed only by a route presented strictly before the presentation bar; armed-record refined bounds everywhere (`zone_source=armed_record` on all 268); ATR = SMA(TR,14) measure convention; paper fill via the near-miss frozen helpers (imported, control-reproduced there); missing field → FAIL-CLOSED + DATA_GAP (never invented).
- **Funnel (Pop 1 = 268):** 204 armed at proof (64 armed AFTER proof → proactive mass) → 146 return in window (58 no return) → 8 pass proximity (138 `limit_far_from_market` = the near-miss representation gap in rule form) → 5 exclusions (zone_violated 4, session+violated 1) → **N_would_admit = 3**; first-fail sums reconcile exactly (64+58+138+5+3 = 268), DATA_GAP rate 0.00.
- **Overlap:** 0/16 routes, 0/3 control fills; all 3 fill rows analytically evaluable → the rule replaces the baseline path rather than generalizing it (their proofs predate their arms — nothing proactive is licensed at those moments; one fill also fails the proximity guard at its own presentation).
- **Verdict (frozen order): FAIL_TIGHT** — `kill1_under_selective` (3 < 8) + `kill3_zero_control_overlap`, both recorded. Per the design the reactive-admission path AS WRITTEN is killed; any redesign must come as its own dated proposal with pre-registered rules. The one live seam worth carrying to that design: 8 of 146 returned theses survive the proximity funnel.
- **Secondary (tiny n, disclosed):** the 3 admits all touched their would-be limit inside the product rest lifetime (FILLED_NO_RESOLVE — SL/TP never invented); EXPIRED rate 0.0 (n=3) — nothing inferable. Pop-2/3 phase-2 report columns (R2–R6 only): 11/208 and 3/109 — REAL mass, same shape, no decision taken.
- **Integrity:** populations asserted exactly; warm-up offset 6018 asserted against the loaded grid (42,296 M5 bars); dual-run `rows.csv` + `summary.json` byte-identical (no wall-clock in the summary); kill-criterion evaluator branch-tested completely.
- **Two build-time defects caught and fixed before the final artifacts (tests caught them, not luck):** the named rule compares direction by ENUM identity so a string silently disabled its limit-touch path (and the intermediate enum conversion then leaked into our own string-comparing helpers, flipping LONG→SHORT on the violation walk — fixed by keeping strings everywhere except the single rule call site); artifact writing bypassed the `--out-dir` argument, exposed by the dual-run determinism check.
- **Artifacts:** `06_RESEARCH/scripts/reactive_admission_measure.py` · note `06_RESEARCH/REACTIVE_ADMISSION_MEASURE_NOTE.md` · data `06_RESEARCH/results/reactive_admission_measure/{rows.csv, summary.json}` (+ `_run2` determinism mirror) · tests `04_SRC/tests/test_reactive_admission_measure.py`.
- **NEXT ACTION: Architect review of the measure only** (no redesign, no implement prompt, no threshold discussion until the Architect rules). Measurement threads otherwise unchanged (entry representation; episode store).

## 2026-10-13 — Reactive Admission Design Lock (docs-only; DESIGN_LOCKED pending Architect acceptance)

**Status: DESIGN_LOCKED (owner plan binding step 4). Docs-only: no `04_SRC` code, no tests, `locked_constants.py` diff empty, `LOGIC_CHANGED: NO`. Implementation deliberately NOT started — design and pre-registered measure required before any code.**

- **Design:** `00_LOCKED/REACTIVE_ADMISSION_DESIGN.md` (sections 1–9 + return block).
- **Purpose:** Solves the conversion gap exposed by the coincidence study (585/1093 coincidences @ H=48, but only 16 routes and 3 fills on armed geometry; 74% on un-armed geometry) while respecting the near-miss finding (`PLACEMENT_NOT_PRIMARY`: placement gates are not destructive, candidate limits are too far from market).
- **Mechanism:** Chosen Primary Mechanism = Option C (phased: scan continuation under §5a for Phase 1; parallel candidate minting into shadow logs for Phase 2).
- **Rule set (R1–R6):**
  - $R_{\text{thesis}}$: HTF episode state (`ARMED`/`SEEKING` in Phase 1; unviolated `VALIDATED` in Phase 2).
  - $R_{\text{proof}}$: Directional LTF proof (directional sweep of SSL/BSL or Stage-3 trigger A–F completion).
  - $R_{\text{timing}}$: Proof within $H_{\text{proof}}=48$ M5 bars of thesis anchor; return within $H_{\text{return}}=20$ M5 bars of proof.
  - $R_{\text{location}}$: Return-to-structure geometry (`market_reentered_zone` within refined bounds; limit within $1.0\times\text{ATR}$ of market).
  - $R_{\text{exclusion}}$: Invalidation filters (no chase $>1.5\times\text{ATR}$, allowed sessions, no adverse HTF close).
  - $R_{\text{one\_shot}}$: Episode-level one-shot invariant (§11: 1 episode $\rightarrow$ 1 route $\rightarrow$ 1 execution).
- **Pre-registered kill criteria:** (1) $N_{\text{would\_admit}} < 8$ on armed-coincident; (2) $N_{\text{would\_admit}} \ge 25$ but counterfactual $\text{EXPIRED\_NO\_FILL} > 85\%$; (3) 0 control overlap; (4) $N_{\text{would\_admit}} > 150$ (indiscriminate flood).
- **Bans upheld:** No gate loosening, no Mode B, no ML, no automatic route of all 585, no proactive placement in V1 admission, no Redis.
- **NEXT ACTION: Architect acceptance → offline admission measurement script (counterfactual admits over 6m) | store hook completion.**

## 2026-10-13 — Episode Store V1 Observability Implementation (PASS)

**Status: COMPLETE — owner plan step 3 implementation. V1 observability-only store shipped: `04_SRC/smc/orchestration/episode_store.py`, unit + integration tests in `04_SRC/tests/test_episode_store_v1.py` (11 tests, suite **1062 passed**), short parity verified (trades.csv byte-identical, report.json semantically identical), `locked_constants.py` untouched, `LOGIC_CHANGED: NO` (decision paths untouched).**

- **Module:** `smc/orchestration/episode_store.py` providing `EpisodeStore`, `EpisodeRecord`, `EpisodeEvent`, `EpisodeIdentityKey`, `EpisodeState`, `EpisodeEventKind`.
- **Identity rulings satisfied (§9a):** Canonical geometric identity `(direction, detection_tf, m8_kind_class, [zone_low, zone_high] under ZoneDedup overlap-equivalence, 6dp bounds)`; `poi_id` and `route_id` are attributes and lookup keys; H4 vs M8←H4 separated; refinement adopts tighter armed bounds with mandatory parent link; `ZoneDedup` sole merge authority; `EXPIRED_UNARMED` first-class terminal state; append-only events, no-lookahead assertions.
- **Integration hooks:** Optional sidecar in `MultiTFProductRuntime` and `PipelineEngine` (`episode_store=None` default OFF); exception-guarded so store failures never disrupt decision paths. Parity tested via `phase3_structure_funnel`.
- **Docs:** `06_RESEARCH/EPISODE_STORE_V1_IMPLEMENTATION_NOTE.md`.
- **NEXT ACTION: Architect review / Reactive-admission design.**

## 2026-10-13 — Episode store design lock (docs-only; pending Architect acceptance)

**Status: DESIGN_LOCKED (owner plan binding step 3). Docs-only: no `04_SRC` code, no tests, no suite re-run, `locked_constants.py` diff empty, `LOGIC_CHANGED: NO`. Implementation deliberately NOT started — the design requires acceptance before any code.**
- **Effectiveness-audit gate (this session):** `06_RESEARCH/scripts/effectiveness_audit_gate.py` added; safety/ban check passed; zero tool call anomaly observed; artefact path for this gate recorded as `06_RESEARCH/scripts/effectiveness_audit_gate.py`.

- **Design:** `00_LOCKED/EPISODE_STORE_DESIGN.md` (sections 1-10 + return block). Purpose: one addressable **episode** with an append-only history so measurement stops re-deriving joins and the product keeps its own memory (register F-08; six fragmented stores; the logged `expired 0` counter defect; no per-POI validation/arm log anywhere; A4 identity contested).
- **Identity (proposed, normative):** `(direction, detection_tf, m8_kind_class, [zone_low, zone_high] under overlap-equivalence)` — sameness is the shipped `ZoneDedup` rule (same direction + overlapping span, 6 dp); bounds canonicalised at 6 dp with a `bounds_history`; an armed tighter box inside a census parent is **REFINEMENT of the same episode** (adopted bounds, parent link, no fork); `poi.id` (uuid4) and `route_id` are attributes, never identity; `ZoneDedup` remains the sole merge authority.
- **Lifecycle:** DETECTED → REJECTED_PILLAR | VALIDATED → SUPPRESSED_DEDUP | EXPIRED_UNARMED | ARMED(posture) → SEEKING → ROUTED | SCAN_CLOSED | VIOLATED (REVALIDATION sub-state per Option B R2.3) → PLACED | INTENT_* (R9 verbatim) | BLOCKED_* → FILLED / ORDER_EXPIRED → CLOSED_* | OPEN_UNRESOLVED. §4.3 table states which transitions exist today vs which are **bookkeeping only**.
- **Event log:** append-only, one vocabulary, no future bars, counters derived from events (kills the counter-vocabulary class of bug), read API for the studies (`state_at`, `funnel`, `fate`, `coincidence_hits`, `blueprint`).
- **V1 scope:** in-memory per run + CSV/JSON export, **observability-only** (no decision path reads the store); byte-identity parity gate for the frozen 6m run (funnel 30 armed / 10 routes / 4 placed / 3 fills; trades.csv + report.json identical); migration phases 1-3 (write-only → read-only consumers with 0-mismatch cross-checks against the census chain, the 474 taxonomy and COINCIDENCE_COUNT → decision reads only if separately ruled).
- **Acceptance tests listed (10):** identity stability under refinement; dedup authority; no-lookahead property test; one-shot invariant; coincidence-query reproducibility (585/713, 490 strict anchor); funnel reconciliation; derived counters (assert 4 expired, not 0); observability-only byte parity; export determinism; loud-fail discipline.
- **Open questions (5, for the Architect):** cross-TF identity collision (H4 vs M8-H4); refinement parent link mandatory or optional; EXPIRED_UNARMED first-class or derived; live persistence across restarts; route key compatibility (`poi:trigger@bar` vs episode-keyed).
- **NEXT ACTION (after acceptance): implement the observability-only episode store with the parity gate**, or take the reactive-admission design (owner plan step 4) first — Architect pick. No routing, gate, threshold or constant change is proposed here.

## 2026-10-13 — Coincidence count (PASS; COINCIDENCE_MASS_PRESENT)

**Status: COMPLETE — owner plan binding step 2 / proof-register BACKUP_NEXT. Read-only measurement: 12 new tests, suite **1051 passed**; Step-3 reconciliation exact (946 / 490 / 605, 0 mismatches); `locked_constants.py` diff empty; `LOGIC_CHANGED: NO` (no `04_SRC/smc` decision path touched, no gate loosened, no routing change, no episode store).**

- **Question:** how often does an LTF proof (Stage-3 completion A-F) coincide, in a short frozen window, with an HTF zone thesis — including theses the product never armed and never routed? (Prices the sequential-order constraint with counts only.)
- **Method (frozen before the run):** all **1,093** unique Step-1 episodes from Step-2's `sweeps_per_episode.csv`; completions evaluated in **Step 3's imported evaluation mode** (one `SeriesState(M5)` per bar, matrix-eligible triggers, episode POI = Step-3's verbatim construction); anchor = `first_sweep_ts` (946 swept) or **day-close PROXY** for the 147 unswept (conservative, no look-ahead); window `ref < bar <= ref+H` (Step-3's link rule), primary **H=48**, sensitivity H in {20,38,58} windowed from one pass; pairs unique by (bar, letter).
- **Integrity:** sweep-anchored reconciliation **exact** — 946 swept / 490 confirmed / 605 completions (raw = dedup) / **0** per-episode flag mismatches; smoke subset (92 episodes) 0 mismatches; exec-index cross-check 3/3 against the frozen run's trade `entry_bar`s; the coincident lifecycle-joined 134 decompose exactly into Step-4's `scanned-no-route` 102 + `routed-before-sweep` 32.
- **Counts:** **585/1,093 episodes** (713 pairs) at H=48 — 490 at the strict sweep anchor (= Step 3) + 95 PROXY; H=20 346 / H=38 522 / H=58 642; swing **0.205** <= 0.25 (sweep subset 0.231) → stable. First coincidence median **19 M5 bars** (p25 10 / p75 28.25); first-proof mix F 477 / A 56 / B 46 / E 5 / C 1.
- **By fate (coincident/n):** filled 3/3 · routed 13/13 · armed_never_routed 134/134 · zone-only 118/363 · never_armed 317/580.
- **Verdict (pre-registered rule): COINCIDENCE_MASS_PRESENT.** The mass is real and window-stable, but **conversion is the finding**: of 268 coincidences on armed geometry only **16 route (6.0%)** / **3 fill (1.1%)**, and **435/585 (74%)** coincide on theses the product never armed. Composes with PLACEMENT_NOT_PRIMARY (gates removed nothing takeable) and Stage-3 visibility (261/263 completions after the armed scan closed): the order constraint does not bind on proof availability — it binds on when the product will look and on what the coincidence is. Per the register the verdict earns a *dated coincidence-routing design proposal*; this study recommends carrying it as owner-plan steps 3-4 (episode store → explicit reactive admission), not as a wider window. No gate ruling requested; none authorized.
- **Disclosures:** PROXY anchor is day-close (95 of 585, quoted as its own stratum); `armed_never_routed_zone_only` is a direction-free band probe (8/30 armed records carry no direction) and 90 of Step-4's 340 `no-product-POI` rows disagree with its Tier-C "none" under it; episodes outside the 490 confirmed rows are never labelled routed/filled; single window/feed, counts not rates.
- **Artifacts:** `06_RESEARCH/scripts/coincidence_count.py` · note `06_RESEARCH/COINCIDENCE_COUNT_NOTE.md` · data `06_RESEARCH/results/coincidence_count/{episode_coincidence.csv, pair_events.csv, summary.json}` · tests `04_SRC/tests/test_coincidence_count.py`.
- **NEXT ACTION: carry the coincidence/admission design (owner-plan steps 3-4: episode-store design lock, then explicit reactive admission with a pre-registered measure before code)** — or Architect review. The entry-representation thread stays the open strategy question.

## 2026-10-13 — Near-miss / counterfactual study (PASS; PLACEMENT_NOT_PRIMARY)

**Status: COMPLETE — the owner plan / proof-register primary next. Read-only measurement: 27 new tests, suite **1039 passed**; capture byte-identical to the frozen 6m run; `locked_constants.py` diff empty; `LOGIC_CHANGED: NO` (no `04_SRC/smc` decision path touched, no gate loosened).**

- **Question:** did placement / session / R7 (and peers) kill paths that *would have been good* under the frozen fill semantics, or paths that were already bad? Method: the frozen `phase3_structure_funnel.run` composition re-run on the frozen 6m window (exec 2025-06-01 -> 11-30, 35,725 M5 bars; M1 warm-up 2025-05-01) under logging-only class wraps (`BacktestRunner.__init__`, `_process_entries` candidate geometry + `blocked_log` delta, `PendingOrderBook.place`), then a pure paper engine mirroring `fill_model` (touch = fill at the limit; SL before TP same bar; placement bar never fill-eligible; eligible = `present+1 .. present+rest_bars-2` with the route's OWN R8/§23 lifetime — one rule, all rows).
- **Integrity (seam changed nothing):** `trades.csv` + `report.json` byte-identical to `results/product_6m_refresh_track_b/run1` (SHA-256 `05a848120b6feeae…`); routes captured 10/10; placements 4/4; blocked log 18 events = `session 4` + R7-far 14 (exact match to the frozen `blocked_by_reason`); **control fills reproduced 3/3** (engine fill bar == actual `entry_bar` on every control row).
- **Book:** 10 routes → control 3 | placed_unfilled 1 | blocked_session 2 | blocked_r7_far 4. Untaken outcome mix **{EXPIRED_NO_FILL: 7}** — resolved untaken paths **0**; 6/7 never touch their own limit even at a disclosed 100-bar horizon; median closest approach while live **26.59** units; the single exception (`poi-022254`) missed by 2.82 units and first touched **42 bars after** its 48-bar clock (TP-able only with a longer rest -> a lifetime question, not a gate question, n=1). Control raw mix TP 2 / SL 1 vs actual TP 1 / SL 2 — one BE-stop divergence, disclosed, so raw `TP_HIT` is an upper bound.
- **Verdict (pre-registered rule): PLACEMENT_NOT_PRIMARY** — every untaken route never touched its own limit inside the lifetime it would have been granted; the gates cut off no takeable path. Per the registered kill criteria: **stop attributing scarcity to placement gates; pivot weight to the entry-timing / entry-representation program.** No gate change is proposed or authorized by this task.
- **Documented research-instrument defect (NOT fixed here):** the composition's `intents_expired` counter reads **0** while the run's own `IntentBook` recorded **4** real `intent_expired_no_reentry` transitions (`by_kind.get("EXPIRED")` vs the actual event name; same class of mismatch for `dropped_portfolio_{friday,news}`). Every published "intents armed 7 / placed 3 / expired 0" line under-reports the terminal lifetime facts. Research instrumentation only; the fix belongs in its own dated change with regenerated artifacts. Residual logged in `POST_V1_ACTIVE_TODO.md`.
- **Artifacts:** `06_RESEARCH/scripts/near_miss_counterfactual.py` · note `06_RESEARCH/NEAR_MISS_COUNTERFACTUAL_NOTE.md` · data `06_RESEARCH/results/near_miss_counterfactual/{candidates.csv, outcomes.csv, summary.json, events.json, capture/}` · tests `04_SRC/tests/test_near_miss_counterfactual.py`.
- **NEXT ACTION: coincidence count** (owner plan step 2 / proof-register backup) OR Architect review of this verdict. No gate ruling requested.

## 2026-10-13 — Owner plan registered: multi-TF translation spine (docs-only)

**Status: ACTIVE — resume anchor. Owner plan registered; single NEXT ACTION = near-miss/counterfactual study.**

- **Owner plan:** `00_LOCKED/OWNER_PLAN_MULTI_TF_TRANSLATION_2026-10-13.md` — Lead Architect owner plan (binding until superseded by a dated ruling). Freezes product identity (Mode A = strict subset of expert multi-TF process; exec M5, detect H4+H1, no M15 product decision TF), defines reactive vs proactive (near-term target = deliberate reactive, expert-long style), sets the operational success target (60–80% of a *written checklist space* armed+proposed within pre-registered delay with pre-registered false-propose bounds — not expert P&L, not human parity), and locks the **binding ordered work sequence**: (1) near-miss/counterfactual → (2) coincidence count → (3) unified episode store → (4) explicit reactive admission rule → (5) optional light ranking ML. Kill criteria copied from the proof register + the new representation-gap kill rule. Explicit non-goals restated (no gate loosening for n, no Mode B as next task, no chart ML brain, no demo P/L as edge, no immediate 5y rerun).
- **This file + the owner plan are the joint resume anchor** for any later session.
- **NEXT ACTION: near-miss / counterfactual study** (primary; kill criteria registered). Backup: coincidence count. Implementation prompt is issued by the Architect — not started in this task.

## 2026-10-13 — Heartbeat publish: retry the in-place fallback (live abort fix)

**Status: COMPLETE. Live abort diagnosed (transient external lock on both write strategies), fix shipped in `04_SRC/smc/live/heartbeat.py` (in-place fallback now retries, full publish retries across cycles), regression test added, suite 1012 green. No trading-threshold, gate, or decision-logic change (`LOGIC_CHANGED: NO`).**

- **Incident:** live session (PID 2572, started 11:14) aborted at 12:32:42Z — `ABORT: heartbeat publication failed ... replace_error=PermissionError(13, 'Access is denied') inplace_error=PermissionError(13, 'Permission denied')`, exit code 3. Watchdog EA then alerted "Python heartbeat stale" — expected consequence of Python death (fresh `state=shutdown` ages past 5s), not a second bug.
- **Root cause (confirmed on disk + forensics):** a transient **external** lock (AV/indexer/file-preview, ~sub-second to 2s — not the EA, whose reads are ms once/sec) blocked `os.replace` **and** the in-place fallback. `write_heartbeat` retried the replace 5×/20ms backoff but the in-place path was **single-shot** — one failed open raised immediately. The clean-shutdown write succeeded 1–2s later, proving the lock was transient and a retry-absorbing design should have survived it.
- **Fix (`04_SRC/smc/live/heartbeat.py`):** in-place overwrite now retries with the same budget/backoff as replace; the whole publish (replace-set → in-place-set) retries `HEARTBEAT_PUBLISH_CYCLES` (new constant, operational timing only) with a pause between cycles. Fail-closed still holds when both strategies are denied the full budget. Docstring updated.
- **Tests (`04_SRC/tests/test_perm_hardening.py`):** +1 regression (`test_heartbeat_transient_inplace_lock_recovers_via_retry` — the exact 2026-10-13 shape: replace denied + first in-place denied → retry recovers, no abort); total-failure test updated for the cycle budget (in-place called replace_attempts × publish_cycles times, message now includes "publish cycles"). Suite **1011 → 1012 passed**.
- **Governance:** `locked_constants.py` diff = only the accepted spread-grade amendment (8/5/3 → 3/2/1, dated 2026-10-11 Architect ruling) — no new trading-threshold touch. No commit made (working tree holds a large cross-cutting uncommitted body; partial commit would be incoherent). CHANGELOG entry added under `## [Unreleased]`.
- **NEXT unchanged: near-miss/counterfactual study (backup: coincidence count), awaiting Architect acceptance.**

## 2026-10-11 — End-of-day governance lock: proof register + critical review (docs-only)

**Status: research proofs registered (F-01..F-09 with PROVEN/TEXTURE_ONLY/SUPERSEDED statuses); critical review delivered with dissent; no code, no constants, no runs.**

- **Register:** `06_RESEARCH/RESEARCH_PROOF_REGISTER_2026-10.md` — 9 rows (A4 identity, post-sweep catalog, funnel, latency, regime texture, M8 consistency, entry/economics, amnesia diagnosis, superseded baselines) + lookahead-clean + suite 1011 statements. Every row carries evidence paths and a no-edge implication.
- **Critical review (inside the register):** solid (determinism, frozen packs, funnel shape, cost arithmetic, structural negatives) vs starved (all n≤30 economics, A4 single-pass, single-window catalogs, A3-other gap) vs EV-judged next steps (near-miss HIGH first; coincidence HIGH/cheapest second; episode-store valuable-but-third; regime-on-routes premature; CHOCH-measurement medium; loosening REJECTED).
- **Dissent recorded:** Architect order was near-miss → episode-store → coincidence; this review recommends near-miss → coincidence → episode-store (cost, decision value, identity-grain risk — defended in §B4).
- **NEXT ACTION: run the near-miss/counterfactual study on unplaced routes + blocked candidates (backup: coincidence count); kill criteria and non-goals registered.**

## 2026-10-11 — Post-sweep behavior catalog (PASS, read-only research)

**Status: PASS. 174 swept episodes mapped for post-sweep structure: triggers/displacement/FVG ubiquitous, discrete CHOCH scarce (15.5%), zones touched 93% / violated 90%, routes attach to none of these rows. No thresholds, no code, no gates.**

- **Population:** 41 A4-contained (armed bounds) + 133 A2/A3 gap rows (census bounds); 97 partials held out (identity contested). Frozen horizons: triggers +48 (Step-3 established), everything else +100 M5.
- **Behaviors (n=174):** trigger completion 174 (100%, med 17; mix F161/A32/B18/C2/E2) / displacement 136 (78%, med 8) / BOS 136 / CHOCH 27 (15.5%, med 27) / FVG formed 152 (87%) all mitigated-by-touch (med 8) / zone touched 162 (93%, med 2) / violated 156 (90%, med 0). Unaligned LTF rows 2,235 (side count). Routes/fills joined: **0/174** — all 16 routes + 3 fills sit outside (partials/B rows).
- **Cross-checks:** (b)-row firsts reproduce Step-3 exactly (0 mismatches); rerun byte-identical. MSS absent in code (stated); charts skipped by design.
- **Alignment read:** every flowchart ingredient except discrete breaks and product admission is abundant post-sweep — abundance ≠ tradeability, absence of fills ≠ evidence against fragments.
- **Verified:** 6 new tests (alignment, overlap, touch runs, violation strictness, mitigation, parsing, frozen sets); mid-build they caught two real defects (aliased detector lists; first-touch stuck at 0) — fixed, rerun. Suite 1011; `locked_constants.py` diff empty; no `04_SRC/smc` change.
- Script `06_RESEARCH/scripts/post_sweep_behavior_catalog.py` (new); artifacts local-only `results/post_sweep_behavior_catalog/` (174-row CSV + summary); note `06_RESEARCH/POST_SWEEP_BEHAVIOR_CATALOG_NOTE.md`.

**NEXT READY: Architect review of post-sweep map.**

## 2026-10-11 — A4 identity chart checklist (PASS, research UX)

**Status: PASS. 56-panel human review pack for scoring A4 overlap candidates; no auto-scoring anywhere by design; no code, no constants, no thresholds.**

- **Pack:** 41 contained + 15 earliest-sweep partials (deterministic order; all 5 note examples verified inside); per panel: census zone (blue) vs armed zone (orange dashed), sweep bar (red), arm bar (purple, when in ±90-bar window); `index.csv` with bounds/timestamps + blank `human_verdict`/`notes`; `summary.json` with rules + verdict values.
- **Rubric in note:** SAME_FOOTPRINT / REFINEMENT_ONLY / DIFFERENT / UNCLEAR with one-line criteria each + fill-and-tally instructions; NEXT = post-sweep behavior catalog (SAME/REFINEMENT mapping decided by Architect, not here).
- **Verified:** 56/56 rendered, 0 skipped; 1 chart read in-session (partial overlap legible, caption/footer correct); 3 new tests (selection priorities/dedupe/order, window clamps — one real robustness fix: dedupe within contained); rerun-stable. Suite 1005; `locked_constants.py` diff empty; no `04_SRC/smc` change.
- Script `06_RESEARCH/scripts/a4_identity_chart_checklist.py` (new); artifacts local-only `results/a4_identity_chart_checklist/`; note `06_RESEARCH/A4_IDENTITY_CHART_CHECKLIST_NOTE.md`.

**NEXT READY: Human scoring → post-sweep behavior catalog** (send tallies or marked charts; then Prompt 2).

## 2026-10-11 — Arming forensics, bucket A (PASS, read-only)

**Status: PASS. 271 validated-elsewhere episodes split by direct batch evidence: A4 138 / A3 82 / A2 51 / A1 0 / A5 0. No code, no constants, no thresholds.**

- **Method:** frozen p3 composition driven verbatim with call-through recorders (raw detections + validated PASS/fail via details-carried POIs + arm events; true originals restored). **Fidelity PASS** (byte-identical trades.csv/report.json + funnel equality; M5 grid proven identical). Priority frozen: identity > pass > fail > absence > gaps.
- **Breakdown:** A4 armed-other-identity 138 (50.9%; exact 0 / contained-armed-in-census 41 / partial 97; arm gaps median 8d — overlap is cheap evidence, chart check required, examples listed) / A3 passed-not-armed 82 (dedup-loser 47 exact-rule replications / other 35 genuinely unexplained — no cap/score/freshness filter exists; dedup-possible 0) / A2 failed-pillars 51 (P2-dominated fail events 20,029) / A1 0 (every episode validated somewhere) / A5 0.
- **Dominant paragraph:** A4 leads but is weakest-evidence; mechanically firm buckets are A2 + A3-dedup. Code defects found: none. Policy order: give-up horizon, pillar bands, arm-selection, one-shot — instrumentation (arming logs, per-scan posture) needed before selection rulings. 5 examples per top reason with bounds+timestamps in note.
- **Verified:** 5 new tests (overlap predicate, A priority, day diff, hashing, frozen params); population reconciles exactly. Suite 1002; `locked_constants.py` diff empty; no `04_SRC/smc` change.
- Script `06_RESEARCH/scripts/arming_forensics_bucket_a.py` (new; + replay_run1 fidelity artifacts); results local-only `results/arming_forensics_bucket_a/` (271-row CSV + summary); note `06_RESEARCH/ARMING_FORENSICS_BUCKET_A_NOTE.md`.

**NEXT READY: Architect ruling on arming miss · then broader post-sweep behavior catalog (non-F geometries) as separate task.**

## 2026-10-11 — 474 never-routed decomposition (PASS, read-only)

**Status: PASS. Exclusive taxonomy reconciling exactly (340+32+102+0); dominant = A-validated-elsewhere (271); no code, no constants, no thresholds.**

- **Top table:** A no-product-POI 340 (71.7%, med 25 bars) / B routed-before-sweep 32 (6.8%) / C scanned-no-route 102 (21.5%) / D 0. A splits validated-elsewhere 271 vs never-validated 69 — the dominant gap is accepted geometry never armed (batch/dedup/arming dynamics; needs per-POI arming logs first), not pillar rejection of unknowns.
- **C sub-break (frozen priority):** C1 expired-give-up 72 (horizon policy; deadline behaved as designed) / C2 scan-late 25 (arm timing) / C3 matrix 0 (validates the router docstring empirically) / C4 unspecified 5 (instrumentation). B is working-as-designed (§11 one-shot; not a gap).
- **Dominant paragraph (code vs policy):** code defects found: none. Policy order for Architect: give-up horizon, pillar bands, arm-selection, one-shot — with instrumentation (arming logs, per-scan posture/cursor/signal) needed before selection rulings.
- **Verified:** 3 new tests (C priority, fix-class map, letter shapes); population reconciles exactly. Suite 997; `locked_constants.py` diff empty; no `04_SRC/smc` change.
- Script `06_RESEARCH/scripts/confirm_never_routed_474.py` (new); artifacts local-only `results/confirm_never_routed_474/` (474-row CSV + summary); note `06_RESEARCH/CONFIRM_NEVER_ROUTED_474_NOTE.md`.

**NEXT READY: Architect ruling on dominant reason only** (instrument first or rule on horizon/pillars/selection — still no threshold fishing).

## 2026-10-11 — Step 4 entry path on confirmed swept POIs (PASS, read-only)

**Status: PASS. 490 confirmed → 16 routed → 4 placed → 3 filled, measured through the product's own code path with byte-identical fidelity. The chain is closed: idea geometry vs product admission, quantified.**

- **Method:** frozen p3 composition driven verbatim with call-through recorders (scan/route/place/close + stashed blocked log), true originals restored after. **Fidelity PASS:** replay trades.csv + report.json byte-identical to the 6m refresh, funnel equal on every count (the gate caught a real zero-cost config slip mid-build — fixed via single-source PILOT_COSTS). M5 mapping proven (35,725 bars, Sunday-open start).
- **Lifecycle:** 340/490 (69%) never had a product POI (never validated/armed); 150 joined (7 exact + 143 containment); 32 routed pre-sweep (one-shot consumed); 102 scanned-never-routed (silent by construction; never-scanned = 0); **16 routed post-sweep (3.3%, all F)** → **4 placed (25%)** → **3 filled (75%)**. Blocked post-sweep: session 7, R7 9 (per-event). @20 secondary: same shape (12/282 routed).
- **C trade answered:** its structure shows zero completions in the frozen +48 post-sweep (route came ~100+ M5 bars later under arm-anchored seek) — bounds Step-3's horizon, not a contradiction. Both F fills join cleanly.
- **Verified:** 4 new tests (join tiers, gap taxonomy); no `04_SRC/smc` change; suite 994; `locked_constants.py` diff empty.
- Script `06_RESEARCH/scripts/poi_confirm_entry_path.py` (new; + replay_run1 fidelity artifacts); results local-only `results/poi_confirm_entry_path/` (490-row CSV + summary); note `06_RESEARCH/POI_CONFIRM_ENTRY_PATH_NOTE.md`.

**NEXT READY: Architect flowchart synthesis** — measured chain complete: 1,093 → 946 → 490 → 16 → 4 → 3.

## 2026-10-11 — LTF confirmation on swept POIs, Step 3 (PASS, read-only)

**Status: PASS. 490/946 swept episodes confirm within 48 M5 bars; rates by horizon/trigger/group recorded; no thresholds, no code, no gates.**

- **Method:** visibility-pack scan mode re-anchored (SeriesState M5, TriggerRouter eligible triggers, episode POI + from_bar=first-sweep, EVERY completion ungated; single +48 pass, nested horizons derived). Link frozen: sweep < completion ≤ sweep+H, H in {5,12,20,48} (20 = locked give-up scale); M15 skipped by design (product is M5-only).
- **Rates:** H5 6.9% (65) / H12 15.8% / H20 29.8% / H48 **51.8%** (490); 605 completions, median 19 M5 bars to first confirm. First-confirm mix F 393 / A 47 / B 44 / E 5 / C 1 (F 80%). By group @48: H4 39% / H1 53% / M8-H4 52% / M8-D1 58% / M8-W1 44% — none dominates. By kind flat 41–58% (kind does not separate).
- **Reading:** the 490-vs-single-digit-routes gap is the router + placement chain (chronology, §24 windows, R7, sessions, one-shot), not missing geometry. 147 unswept never in any denominator.
- **Verified:** 5 new tests (edges, nesting, letters, order + tie-break, POI models); rerun byte-identical. Suite 990; `locked_constants.py` diff empty; no `04_SRC/smc` change.
- Script `06_RESEARCH/scripts/poi_swept_ltf_confirm.py` (new); artifacts local-only `results/poi_swept_ltf_confirm/` (946-row CSV + summary); note `06_RESEARCH/POI_SWEPT_LTF_CONFIRM_NOTE.md`.

**NEXT READY: Step 4 entry path on confirmed swept POIs** — of confirmed episodes, what route→place→fill admits (then outcome only).

## 2026-10-11 — POI-linked sweep rate, flowchart Step 2 (PASS, read-only)

**Status: PASS. Of 1,093 POI episodes, 946 are swept on their directional edge in-window — the idea does NOT die at Step 2. No thresholds, no code, no gates.**

- **Method:** product `detect_sweep` (first + re-fires) on the directional edge as `POI_LEVEL` (LONG→SSL-on-low, SHORT→BSL-on-high); search strictly after first-seen through 2025-11-30; primary = own TF bars, M5 secondary same rule.
- **Rates:** H4 m1m7 56/75 (74.7%, med 21.5 bars) / H1 163/196 (83.2%, med 17) / M8-H4 605/659 (91.8%, med 3) / M8-D1 106/137 (77.4%) / M8-W1 16/26 (61.5%). Unswept remainder 147 episodes. M5 secondary 975 (89.2%, side column).
- **Honesty notes:** zones form at price so early sweeps partly measure mechanical proximity (interaction, not foresight — and interaction is what Step 3 needs); opposite-side sweeps out of scope; a string/enum normalization bug that would have mis-sided SHORT POIs was caught and fixed mid-build (recorded in note). Re-sweeps heavy (M8-H4 5,888).
- **Verified:** 6 new tests (mapping, bounds, ordering, SHORT mirror, frozen window); rerun reproduced 946/975 exactly. Suite 985; `locked_constants.py` diff empty; no `04_SRC/smc` change.
- Script `06_RESEARCH/scripts/poi_linked_sweep_rate.py` (new); artifacts local-only `results/poi_linked_sweep_rate/` (1,093-row CSV + summary); note `06_RESEARCH/POI_LINKED_SWEEP_RATE_NOTE.md`.

**NEXT READY: Step 3 LTF confirmation on swept POIs** — of swept POIs, how often does LTF confirmation appear (then entry/outcome only).

## 2026-10-11 — HTF POI census, flowchart Step 1 (PASS, read-only)

**Status: PASS. 1,093 unique POI episodes by TF and kind with the real product detection path — the re-anchor the audit ordered. No arm, no pillars, no sweeps required.**

- **Method (reuse-or-redetect disclosed):** review packs NOT reused (M8-only construction) — re-detected: registry M1–M7 per daily prefix on H4/H1 (no HTF feed, M8 silent, zero skips); M8 per HTF input (H4/D1/W1-deep-from-2021) via `_zones` + `collapse_episodes`; merge per group; episode = same side+geometry (first-seen dated).
- **Counts:** H4 m1m7 raw 889 → 75 episodes → merged 25 (tags M1 31/M2 24/M4 11/M7 8/M3 1; M5/M6 ride along, never first); H1 889 → 196 → 67; M8-H4 659 (ob 177/ds 305/fvg 177) → merged 98; M8-D1 137 → 35; M8-W1 26 → 10. Kind language honest: model tags for M1–M7 (no tag→kind map exists), facets for M8.
- **Cross-check:** census M8-H4 ⊃ pack raw by exactly 1 zone (LONG 4204.348–4230.349 ds, window-edge — disclosed); pack-merged 3 (validated) vs census-merged 98 (geometric) — different operations, gap now visible as a number. Dominant tag signature M1+M7 (89 episodes).
- **Verified:** zero model skips, zero M8 in registry runs, 15 thin prefixes skipped by frozen floor; +4 tests. Suite 985; `locked_constants.py` diff empty; no `04_SRC/smc` change.
- Script `06_RESEARCH/scripts/htf_poi_census.py` (new); artifacts local-only `results/htf_poi_census/` (1,093-row CSV + summary); note `06_RESEARCH/HTF_POI_CENSUS_NOTE.md`.

**NEXT READY: POI-linked sweep rate (Step 2)** — of these POIs, how many are swept (not how many sweeps exist).

## 2026-10-11 — HTF post-sweep path analysis (PASS, read-only measurement)

**Status: PASS. First-sweep follow-through measured on frozen short horizons; continuation common AND failure common, both growing with horizon; no edge claimed, nothing shipped.**

- **Sample:** unique level + first sweep only (H4 759 / H1 783; re-fires 8,380/22,699 as side counts); stratified TF × family; BSL→downside/SSL→upside reporting only.
- **Horizons frozen:** {1,3,5,10} TF bars exclusive of sweep + M5 secondary (H4→20/H1→5, sub-native lens); level-referenced ATR(14) metrics, no R/stops; reclaim_fail precisely defined; strict truncation (35 M5sec reads on weekend-grid H4 bars — grid cause documented, native reads complete).
- **Texture (not a finding):** h1 +1ATR ~35–45% with adverse <10%, median extremes in 1 bar; by h10 +1ATR ~70–86% but adverse ~40–50%, reclaim >60%, median MAE ~1 ATR — fast small continuation then return-through-level more often than not. Structural vs session: H4 modestly favorable on all axes at n=37 (overlapping CIs — texture only), H1 none, equal n tiny → no consistent edge demonstrated.
- **Verified:** rerun byte-identical; +6 tests (mapping, exclusive indexing, both-side signs, reclaim defs, frozen sets). Suite 975; `locked_constants.py` diff empty; no `04_SRC/smc` change.
- Script `06_RESEARCH/scripts/htf_post_sweep_path.py` (new); artifacts local-only `results/htf_post_sweep_path/` (1,542-row CSV + summary); report `06_RESEARCH/HTF_POST_SWEEP_PATH_REPORT.md`.

**NEXT READY: Architect review.**

## 2026-10-11 — HTF sweep census H4+H1 (PASS, read-only count)

**Status: PASS. First-class HTF sweep inventory exists: H4 9,139 (unique 759) / H1 23,482 (unique 783), real detector path, byte-identical rerun. No thresholds, no code, no gates.**

- **Method:** `liquidity_scanner.scan()` levels per TF + `sweep_detector.detect_sweep()` every sweep per level (first + re-fires, formed_at respected); exec 2025-06-01→11-30, M1 warm-up 2025-05-01. Pools BSL-only/SSL-only; bias SHORT/LONG is reporting convention.
- **Mix:** session levels dominate swept events (H4 91% / H1 68% — constructional, daily levels near price); structural 772/6,867; equal 45/639; periodic formed-but-never-swept.
- **Zone joins (descriptive):** linkage 100% both TFs — disclosed as vacuous (658 overlapping zones blanket 99.9% of span); within ±20 M5 of first-touch 70.3%/56.2% — disclosed as near base rate (≤69% ceiling). First-touch-only undercount documented.
- **Clarified for the record:** decomposed 5,553 = LTF-linked rows (not HTF sweeps); H4 pack 658 = zones (not sweeps); start the HTF story from 9,139 / 23,482.
- **Verified:** predicate spot-check 821/821; formation ≤ sweep bar; window-contained; determinism byte-identical; +7 tests. Suite 969; `locked_constants.py` diff empty.
- Script `06_RESEARCH/scripts/htf_sweep_census.py` (new); artifacts local-only `results/htf_sweep_census/`; note `06_RESEARCH/HTF_SWEEP_CENSUS_NOTE.md`.

**NEXT READY: Architect review** (HTF story restarts from a real sweep count).

## 2026-10-11 — Decomposed 6M event ledger + combination tests (PASS, research only)

**Status: PASS. 16,281 flowchart events inventoried without requiring the product chain; combination tested with frozen rules; falsifications published; no code/constant/threshold touched.**

- **Ledger (concepts 1–4; concept 5 = 3 fills listed):** 668 htf-zones + 5,553 sweeps + 5,553 displacements + 4,244 FVGs + 263 trigger completions (204F/31A/7E/4C/17B) — accepted packs/ledgers reused verbatim (SHAs in summary); post-event reads frozen (H_ZONE=20 zone fate, H_PATH=100 excursion in ATR units, prefix-only, strict truncation with 0 gaps/truncations).
- **Zone fates:** TOUCHED 376 / VIOLATED 292 / UNTOUCHED 0 — every accepted zone interacts within 20 bars; 43.7% violate (descriptive, not a rule).
- **Combination (inside-vs-far +1ATR Wilson CIs, n≥30 cells):** sweep does_not_separate (94.4% vs 95.2%, overlapping); displacement/fvg/trigger insufficient_n (structural cell emptiness from source-ledger relation vocabulary — documented); **overall does_not_separate**. Key texture (described, not verdict-shopped): the +1ATR-over-100 metric saturates (~90–98% everywhere — both directions travel several ATR), while the adverse side differs by context (sweep inside MAE 5.43/inv 87% vs far 3.91/80%) — named follow-on with pre-registered rules, not a new verdict.
- **Falsification:** (i) answered by the verdict above; (ii) routed 2/2 vs unrouted 253/261 → insufficient_n (values published; unrouted median higher at n=2 is meaningless — stated); (iii) 3 fills tabled (all M8, PASS pillars, mixed tp_source) → insufficient_n; Phase C analogue untestable (no columns — stated).
- **Binding gates requoted** (never recomputed): pillars kill 95.3% (P2 87.8% of merged); 98.0% scans unrouted; 60% routes unplaced; costs $2.78.
- Script `06_RESEARCH/scripts/decomposed_6m_ledger.py` (new; imports pack loaders + Track-B ATR, forks nothing); artifacts local-only `results/decomposed_6m_ledger/` (16,281-row CSV + summary); report `06_RESEARCH/DECOMPOSED_6M_LEDGER_REPORT.md`; +7 tests. Suite 962; `locked_constants.py` diff empty.

**NEXT READY: Architect review of combination tests** (then: which single Tier-2 fork, if any, deserves a dated ruling).

## 2026-10-11 — Independent audit: idea / funnel / decomposed flowchart (PASS, review only)

**Status: PASS. Primary diagnosis (b) over-strict AND-chain; decomposed-ledger study specified ready to implement; no code, no constants, no thresholds touched.**

- **Verdict:** 96k raw detections → 43k merged → 30 unique armed episodes → 10 routes → 3 fills in 6mo, mass dying inside named gates — not absent events. Primary (b) AND-chain over-strict; secondary (c) specific handoff frictions + (d) volume/spread data gaps; not (a) — n=3 supports no rarity claim, and ~5 episodes/mo would be normal institutional cadence with a frictionless downstream.
- **Binding gates named:** P2 FVG-absence (37,745/43,004 merged); scan→route 10/501; route→fill 3/10 (R7 defers + §24 expiry); ~30 unique zones/6mo cadence ceiling.
- **Scores:** idea 8 / fidelity 7 / implementation 9 / measurability 6 / economics 2 / ops 4 / overall 4.
- **Decomposed study (ready YES):** read-only event ledger schemas for 5 concepts on the 6m window (HTF zones, sweeps, displacement/FVG, LTF triggers, entries) with frozen H_ZONE=20 / H_PATH=100 M5, ATR numeraires, prefix-only no-look-ahead rules — reusing the three existing packs + one post-event module; HTF-context stratification + three falsification checks specified; ablation from logged reason codes only (no loosening reruns — still banned).
- **Next:** Tier 1 build decomposed ledger + binding-gate report (fix placed-vs-intent accounting ambiguity inside it); Tier 2 forks need rulings (5y state carry, commission schedule, tick spreads, volume feed, M8 attribution, any loosening); explicit non-goals held.
- Report: `06_RESEARCH/INDEPENDENT_FUNNEL_IDEA_AUDIT_2026-10-11.md` (Parts A–E + artifact appendix). Suite N/A (nothing added/changed in code or tests).

**NEXT READY: implement the decomposed event ledger** (read-only) on the 6m window — not another product-only refresh.

## 2026-10-11 — Product 6M refresh: costs on + Track-B columns (PASS, diagnostic only)

**Status: PASS. Refreshed stack (mapped spread thresholds + harness columns) measures identically to its predecessor; columns populated; metrics reported, never read.**

- **Window:** exec 2025-06-01 → 2025-11-30 (35,725 M5 bars; warm-up 2025-05-01). Same frozen composition + ruled CostConfig; script window-parameterized.
- **Determinism PASS:** byte-identical pair, semantic funnel equal, no tolerance needed (~880–990 s/run).
- **Book (n = 3, NOT edge):** funnel 30 armed (M8 28) → 10 routes (9F+1C) → 4 placed → 3 fills → 3 trades; WR 0.667, PF 0.157 gross, gross −2.4537; costs **$2.78**; **net −2.7317**. Mixes F:2/C:1, atr_fallback 2/structural_swing 1.
- **Track-B tables (from artifacts):** by_timing {structured_pullback 2, unknown 1}; by_post_exit {REJECTED 1, SL_THEN_TP_PATH 1, TP_REACHED 1} — row-level match to the Track-B study (t1 pullback/REJECTED, t2 C/TP_REACHED, t3 pullback/SL_THEN_TP_PATH). **late_chase is NOT filtered** — nothing reads the columns (structural).
- **Prior-6m comparison: identical everything** (same tickets/economics/funnel; legacy metric keys byte-equal). **SPREAD_GRADE_EFFECT: none** — gate off at `spread_price=0.0`, so re-tiering cannot change admission (confirmed empirically); artifact deltas are purely additive (2 columns + 2 group sections).
- Artifacts local-only `results/product_6m_refresh_track_b/` + `summary.json`; report: `06_RESEARCH/PRODUCT_6M_REFRESH_TRACK_B_REPORT.md`. Suite 955; `locked_constants.py` diff empty (no edit this task).

**NEXT READY: Architect review.**

## 2026-10-11 — Spread-grade scale MAP fix (dated, PASS)

**Status: PASS. First sanctioned locked-constant change in the chain: thresholds recalibrated to the tag-count scale. Nothing else moved.**

- **Map (ruled, implemented exactly):** A+ ≥3 / A ≥2 / B ≥1 / C <1 (tag-count scale), superseding A+ ≥8 / A ≥5 / B ≥3 / C <3 (0–10 style that made A/A+ unreachable). Dict order + highest-tier-first evaluation preserved; `grade_for_score` loop and all callers logic-untouched (data-only fix).
- **Files (4):** `locked_constants.py` (one constant + supersession comment), `spread_grading.py` (docstrings only), `LOCKED_DECISIONS.md` §28.5 (amended row with dated ruling + old map recorded so it is never restored), pinning tests (`test_locked_constants` exact map; `test_spread_grading` boundaries 3→A+/2→A/1→B/0→C against the real function).
- **Behavioral note (stated, not validated):** gate is looser-or-equal on every score — restores designed tolerance; no backtest run for this note, none claimed. No new scorer, no `SPREAD_MAX_ATR` change, no entry/trigger/pillar/risk change.
- Suite **955 passed** (no count change); no collateral — no other test asserted mid-score gate behavior. Note: `06_RESEARCH/SPREAD_GRADE_SCALE_MAP_NOTE.md`.

**NEXT_READY: Architect review → next product window or 5y plan.**

## 2026-10-11 — Track-B harness: annotations locked into product outputs (PASS)

**Status: PASS. Every future product backtest row/summary carries frozen timing labels + post-exit classes. Research measurement wiring only — NOT filters, NOT gates.**

- **Seam (single, after close):** `reports.build_report(result, annotations=...)` + `TradeRecord.from_closed` kwargs + `BacktestReport.by_timing_label` / `by_post_exit_class` groups + export columns/keys (all appended, additive). smc carries data only — zero Track-B logic in product code (dependency stays research-imports-product).
- **Rules imported, not re-tuned:** `f_selectivity_post_exit.annotate_product_trades` (new entry point reusing its frozen Rule-v1 pieces + H=100 taxonomy incl. TP-absent restriction) + `hypothesis_outcome_study.classify` via it. Composition (`phase3_structure_funnel.run`) annotates `result.closed` over its own series, then builds the report. Unresolvable → "unknown"/DATA_GAP, never invented.
- **Columns:** `f_timing_label` (F-only; empty else by design) + `post_exit_class` (all triggers) on rows; two group sections in JSON. Annotated-vs-plain reports identical except the fields/groups (test-locked).
- **Verified:** 9 new tests (synthetic F end-to-end, enum normalization, empty-series DATA_GAP, unknown buckets, pnl/metric identity, non-F behavior, kwargs, banner, legacy shape); 4 export-tail assertions extended (same justified evolution); composition smoke on 2025-09-01→05 (1,326 bars, 17.9 s → 1 C trade with TP_REACHED populated, economics identical). Suite **946 → 955**; `locked_constants.py` diff empty; no trigger/risk/pillar/sizing/fill change.
- Note: `06_RESEARCH/TRACK_B_HARNESS_NOTE.md` (frozen sources, columns, load discipline, null semantics, smoke, bans).

**NEXT_READY: spread-grade scale (A)** (or Architect-ordered window).

## 2026-10-11 — Track B: F selectivity + post-exit path (PASS, research only)

**Status: PASS. Frozen Rule-v1 labels + frozen H=100 M5 post-exit scan over deduped unique trades; separation reproduced, candidate-only verdict with caveats; no decision-logic change.**

- **Samples:** 1,103 book rows → **72 unique trades** (270 byte-identical re-recordings dropped with record: pilot 2 + posttp 6 of product-6m; w0 76 internal; w1 186 of which 115 re-find w0's set). Verify pool **69 unique (64 F + 5 B)**; product-6m 3 (F 2); Phase C 761 = side counts + field-gap statement only (no original_sl, no tp → honest R and TP-paths uncomputable, nothing faked).
- **Labels (verify F, frozen Rule v1 on M1):** late_chase 42 (med MFE_R 0.23, 26.2% ≥1R) / mid_move 19 (med 1.05, 57.9%) / pullback 3 / chop 0 / unclear 0 — reproduces prior wider-study numbers exactly on the deduped set. Zone: all 64 verify entries outside zones (26 below / 38 above); both product F rows INSIDE (listed, never pooled).
- **Post-exit (H=100 strict, DATA_GAP 0):** F outcomes REJECTED 20 (19 verify + product t1) / SL_THEN_TP_PATH 1 (product t3, BE-stop then TP touch) / MFE_ONLY 45; TP_REACHED 1 (product C). TP paths exist only where TP levels exist (3 product rows); 39/64 verify exits take the frozen BE-scratch default before any R evaluation (cross-checked vs prior taxonomy: partial agreement, rule kept frozen).
- **Fidelity (port validation):** labels 37/37 exact vs prior f_timing artifact; honest R 37/37 to 4dp vs honest_r table (a bar-close-vs-fill reference error was found and fixed mid-build — recorded in report §5); zone 64/64 F vs stop_vs_structure.
- **Verdict:** SEPARATION YES (reproduced, stark) with single-regime caveats → GATE_RECOMMENDED CANDIDATE_ONLY: late_chase-vs-rest as the measurement axis for the next re-run (which fields to preserve), NOT a live rule.
- Script `06_RESEARCH/scripts/f_selectivity_post_exit.py` (new; imports hypothesis_outcome classifiers, forks nothing); artifacts local-only `results/f_selectivity_post_exit/` (72-row CSV + summary with SHAs); report `06_RESEARCH/F_SELECTIVITY_POST_EXIT_REPORT.md`; +8 tests. Suite 946; `locked_constants.py` diff empty.

**NEXT READY: Architect review → later backtest re-run questions** (same frozen labels + H=100 scan on the next TP-bearing book with n; BE-default share outside this regime; M8-attributed F once fills exist; second regime before hardening).

## 2026-10-11 — Product baseline 6M extension, costs-on (PASS, diagnostic only)

**Status: PASS. Longer-window costs-on measurement; seams hold, determinism holds; n = 3 book reported, never read.**

- **Window:** exec 2025-06-01 → 2025-11-30 (35,725 M5 bars; M1 warm-up from 2025-05-01). Same frozen composition + ruled CostConfig as the pilot (script window-parameterized; defaults reproduce the pilot exactly).
- **Determinism PASS:** trades.csv + report.json byte-identical across run1/run2, semantic funnel equal, no tolerance needed. Runtimes 881.8 s / 896.0 s (~40 bars/s sustained — project 5y from the long-window rate, not the pilot's ~100).
- **Funnel:** 2,979 HTF batches (0 errors) → 43,004 merged → 2,021 passed (P2:fail dominates) → **30 armed (M8 28)** → 501 scanned → **10 routes (F 9, C 1; M8 10)** → 4 placed → 7 R9 intents → **3 fills → 3 trades**. Blocked: session 4, far-from-zone 14.
- **Book (n = 3, NOT edge in either direction):** WR 0.667, PF 0.157 gross, gross −2.4537 / DD 2.9105; costs **$2.78** (spread 0.78 + slippage 2.00 + commission 0.00 + swap 0.00); **net after cost −2.7317** ledger. Mixes: F:2 (net −3.0909) / C:1 (net +0.3592); structural_swing 1 / atr_fallback 2. M8-as-trade-engine still not established (arms/routes yes, fills almost none — stated, not proven).
- **Consistency observation (not proof):** the 6m run re-found the pilot's exact 2 Sep–Nov trades (identical timestamps/economics) despite the different load window, plus one new June F loss.
- Artifacts local-only `06_RESEARCH/results/product_baseline_6m/` + root `summary.json`; report: `06_RESEARCH/PRODUCT_BASELINE_6M_COSTS_ON_REPORT.md`. Suite 938; `locked_constants.py` diff empty.

**NEXT READY: Architect review (full 5y only if ordered)** — alternatives on the table: authorize full 5y product baseline, or open spread-grade / F-selectivity research. Still no threshold fishing.

## 2026-10-11 — Staged product baseline PILOT, costs-on (PASS, diagnostic only)

**Status: PASS. First costs-on measurement on the product stack; seams + determinism proven; metrics reported, never read.**

- **Window:** exec 2025-09-01 → 2025-11-30 (17,840 M5 bars; M1 warm-up from 2025-08-01; the Phase 4 window). Composition: frozen `phase3_structure_funnel.run` imported, not forked (H4+H1 detect + D1→M8, M5 exec, structural TP feed, current §5a seek) + explicit `CostConfig` only addition (6-line optional hook; absent = legacy path).
- **Costs ON explicit** (ruled values): commission 0.0 (no schedule, never invented), slippage 1.0 pt (all exits except TP), half-spread on, fallback 0.26 (all legs fell back — runner spread unknown), swap deferred with `bars_held` logged.
- **Determinism PASS:** trades.csv + report.json byte-identical across run1/run2 (SHAs in summary), semantic funnel equal; ~184 s per run; cost floats needed no tolerance.
- **Funnel:** 1,488 HTF batches (0 errors) → 20,898 merged → 839 passed (P2:fail dominates) → **18 armed (M8 15)** → 256 scanned → **9 routes (F 8, C 1; M8 8)** → 2 placed → 6 R9 intents → **2 fills → 2 trades**. Blocked: session 4, far-from-zone 12.
- **Book (n = 2, NOT edge):** WR 1.0, PF null (zero-loss → None by design), gross +0.4567 / DD 0.0; costs **$1.52** (spread 0.52 + slippage 1.00 + commission 0.00 + swap 0.00); **net after cost +0.3047** ledger. Mixes: C:1 TP exit (`structural_swing`, net +0.3592) / F:1 SL exit (`atr_fallback`, net −0.0545).
- **Reference vs Phase 4** (same window, zero-cost, pre-§5a/structural-TP): 17 armed / 8 all-F routes / 1 fill then vs 18 / 9 (8F+1C) / 2 now — drift attributed to post-September stack changes, documented as reference only.
- Scripts: `06_RESEARCH/scripts/product_baseline_pilot.py` (new); artifacts local-only `06_RESEARCH/results/product_baseline_pilot/` + root `summary.json`; report: `06_RESEARCH/PRODUCT_BASELINE_PILOT_REPORT.md`. Suite 938; `locked_constants.py` diff empty.

**NEXT READY: Architect review of pilot** (extend window, fix a seam, or only then plan the long product baseline — full 5y only after accept).

## 2026-10-11 — V1 cost model IMPLEMENTED (post-acceptance; Tier-1)

**Status: PASS. Pure additive cost ledger wired fill-only; prices, entries, SL/TP, lot formula, and locked constants untouched.**

- **New:** `smc/backtest/cost_model.py` (`CostConfig` on runner config — NOT a locked constant — + bound `CostModel` + `CostBreakdown` + pure helpers; stdlib-only). Defaults preserve legacy numerics exactly (`apply_costs=True`, commission 0.0 ruled, slippage 0.0, half-spread off, fallback 0.26 inert unless enabled).
- **Seams:** `positions.py` (entry-spread capture incl. BE-modify preservation; close pricing both legs; `bars_held`; unbound store = legacy zero path) → `runner.py` (spread threading on fills/SL+TP/risk/Friday/breaker closes; equity moves by net ledger) → `reports.py` (7 trade fields; 6 metric totals; group nets incl. per-trigger) → `export.py` (appended CSV columns + JSON keys, append-only contract kept).
- **Rules locked in code:** commission both legs; half-spread per leg with fallback on unknown; slippage on every exit except take-profit; swap always 0.0 (deferred, backfillable via `bars_held`); units defined once (`cost_usd / pip_value_per_lot`, test-locked identity).
- **One flagged deviation (no code change either way):** specified research defaults (1.0 pt slippage, half-spread on) are NOT constructor defaults — they would rewrite frozen test economics without a ruling; research runs set them explicitly (one line each). Architect to confirm zero-preserving defaults (recommended) or rule otherwise. Paper runner untouched (allowed follow-on).
- **Tests:** 21 new (`test_cost_model.py`, arithmetic/determinism only, no MT5, no expectancy assertions); 3 existing files extended only at export tails/fakes (no expectation re-valued). Suite **917 → 938 passed**; `locked_constants.py` diff empty.
- Note: `06_RESEARCH/COST_MODEL_IMPLEMENTATION_NOTE.md`.

**NEXT READY: staged product baseline pilot** (short window, costs on, determinism pair — not full 5y yet).

## 2026-10-11 — Tier-1 design lock: cost model + product baseline V2 plan (DOCS-ONLY)

**Status: two dated design notes proposed, awaiting Architect acceptance. No code written, no constant touched, no threshold changed.**

- **`06_RESEARCH/COST_MODEL_DESIGN.md` (PROPOSED):** locks HOW the product will be measured fairly — zero-cost problem statement (spread gate ≠ fill cost; Phase C `spread_price=0.0`); components (commission per-lot-per-side BLOCKING placeholder + account-type declaration; slippage fixed-points on SL/forced exits, ATR-fraction/none ruled out with reasons; half-spread per leg from tick reconstruction with 0.26 fallback candidate; swap DEFERRED with `bars_held` backfill logging); fill-only seams (`_close` net + `_record_close` equity + appended export columns; fill prices never move); ledger-units conversion rule (`cost_usd / pip_value_per_lot`, test-locked identity); conservative V1 defaults (costs-on headline, costs-off upper-bound attribution); NOT-changed list (entries, SL/TP, lot formula, fills, locked constants — cost params live in runner config, never `locked_constants.py`); unit-test plan (arithmetic/determinism only, no expectancy assertions); 8 open questions for ruling.
- **`06_RESEARCH/PRODUCT_BASELINE_V2_PLAN.md` (PROPOSED):** exact product config snapshot (M5 exec, H4+H1 required detection, M8 provisioned, structural TP feed as-wired with `tp_source` split, lot path + cap-binds note, sessions/EOD, `dry_run` N/A for backtest, Trigger D 0 by ruling); window options (A staged pilot RECOMMENDED first, B full-5y segmented, C continuous explicitly NOT proposed); runtime anchored to Phase C (77.4 compute-h @ 6.3 bars/s M1; M5 ≈353.6k bars + ≈43.8k H1 batches; C1 smoke 102 bars/s upper bound; calibration run required before committing to full 5y); determinism-pair requirements (byte-identical trades.csv/report.json + 4 more gates); metrics (count/WR/PF/net/DD, per-trigger, per-tp_source, costs-on vs costs-off, funnel + blocked-by histogram); explicit diagnostic-until-Phase-E statement; strict launch order (cost model merged FIRST — zero-cost V2 prohibited); out-of-scope list (Phase E, state carry, Tier-2 research, live capital). Appendix S records the two spread-grade ruling options only (remap thresholds vs true 0–10 scorer), no code change, independent track.
- Suite **917 collected** (verified); `locked_constants.py` diff empty; working tree otherwise untouched (only pre-existing `M config/live_demo.json` + untracked PNG remain).

**NEXT READY: Architect accepts (or amends) the two design notes → implement cost model after acceptance.**

## 2026-10-08 — PermissionError(13) operator investigation

**Status: instrumentation and fail-closed hardening applied; live root call is not yet proven.** The tester report supplied no traceback or operation name, so the exact historical PermissionError cannot be attributed conclusively. Ranked evidence:

1. **Most plausible for a working session with repeated poll errors:** execution or HTF `copy_rates_from_pos` through `LiveLoop` → `MT5Connector.copy_rates`. Previously, the generic poll catch appended the same error on every retry without naming the API operation. This matches repeated poll errors while most polls continue and the heartbeat is usually fresh.
2. **Confirmed operator code defects, but not proof they caused this tester's report:** `_on_poll` called `symbol_info_tick` and `positions_get` once outside their intended wrappers (then again inside); the MT5 error logger referenced an undefined `mt5`; and `read_heartbeat`/startup write probes swallowed path errors without contextual logging. An exception from the unwrapped display reads could terminate the session.
3. **Possible, not evidenced:** heartbeat temp-file write/replace ACL or sharing denial. The live heartbeat path already prefers `<terminal_info().data_path>\\MQL5\\Files\\smc_heartbeat.txt`; the tester's heartbeat age near zero is evidence against a persistent path denial, not against an intermittent replace failure.
4. **Unlikely for a session already running:** `initialize`/identity failures are startup-breaking and should prevent the session from becoming live.

**Fixes:** actual MT5 calls now carry operation, terminal executable path, PID, last-error context, and a traceback on first failure; identical errors are rate-limited and successful recovery is logged. Poll-time tick/position reads execute once and failed display values become unknown rather than stale/zero. One connector is reused after identity validation, avoiding a second `initialize` from `LiveLoop.start`. Poll-level rates errors are counted once and the run loop continues on recovery. Heartbeat write errors include target/temp path and operation; no writable startup candidate aborts startup, and a runtime write failure terminates rather than counting a stale heartbeat as successful. Heartbeat fallback outside the confirmed terminal data sandbox is explicitly marked as not confirmed EA-readable. Operator file operations report operation and path on failure.

**Concurrency:** startup events and `identity.json` include configured terminal path and Python PID. Use one active Python owner per terminal as operational guidance; the official [MetaQuotes `initialize()` documentation](https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py) describes connection setup and optional terminal launch but does not document a formal process-exclusivity rule. A separate unrelated terminal is not evidence of contention with the configured Exness Copy terminal.

**Severity:** initialize/identity and heartbeat publication failures are breaking/fail-closed. A transient execution-rates error skips that poll's fetch and retries; a missing required HTF series follows the existing batch refusal policy; tick/position display errors are non-fatal but shown as unknown. No strategy threshold or `locked_constants.py` change is in scope.

**Verification / ship note:** fake tests exercise call attribution, duplicate suppression, recovery, one-call-per-poll, startup identity, heartbeat read/write context, and fail-closed runtime behavior. Focused operator tests: **74 passed**; full suite: **914 passed**. A live MT5 PermissionError has not been reproduced here; run a bounded tester session with the updated build and inspect `events.log` for the exact operation before declaring the original event fully root-caused. Tester/demo shipment is reasonable with that live-attribution residual risk disclosed.

**HEARTBEAT WinError 5 FIXED + SHIP PACK v1.1-test.7 (2026-10-08):** `dist/SMC_v1.1-test.7_tester.zip` rebuilt from the CURRENT tree so the shipped `04_SRC/smc` NOW includes the permission-hardening (`_mt5_call` instrumentation, hardened `smc/data` connector, `heartbeat_path`) — the previous shipped tree predated it. Shipped `config/live_tester.json`: `dry_run=false` (demo orders MAY place; losses possible on demo), `require_demo=true` (real accounts blocked), `console_mode=event`, `detection_timeframes=["H4","H1"]`; `requirements.txt` includes `MetaTrader5>=5.0.45`; `mql5/SMC_Safety_Watchdog.mq5` + compiled `.ex5`. Zip byte-check PASS (config values, hardened modules, watchdog, requirements; no `results/`/`.git`/`__pycache__`). Clean-extract proof PASS: bat → venv → pip → entrypoint, `session exited with code 3` on the placeholder terminal path (matches `ABORT: mt5.initialize failed`; no flash-close). Full suite **917 passed**; `locked_constants.py` diff empty. **HEARTBEAT WinError 5 (root cause confirmed):** the watchdog EA opens/reads/closes the heartbeat each 1 s tick; a read overlapping Python's atomic rename blocks `os.replace` (target held without delete-sharing), and one such collision aborted the session (code 3). Fix in `smc.live.heartbeat.write_heartbeat`: retry `os.replace` 5× / 20 ms, then fall back to an in-place overwrite (write-sharing only, coexists with the EA); only a persistent total failure (temp + all renames + in-place) raises `HeartbeatWriteError` and fails closed. EA already open/read/close per tick — unchanged. +3 tests. **Operational note — ONE active Python owner per terminal:** a leftover operator process (or a bat-test venv) writing the heartbeat keeps the watchdog quiet, and competing IPC clients produce spurious `PermissionError(13)`; kill stray operators before a session. **Audit residual (carried):** the original PermissionError root call remains unproven (no traceback) — inspect `events.log` on the next tester run. **Durability:** the hardening still lives in the working tree — `04_SRC/smc/data/`, `04_SRC/smc/live/heartbeat_path.py`, and the permission tests are untracked (audit MAJOR-1); no commit made (the working tree holds a large cross-cutting uncommitted body).

**Last Updated:** 2026-10-07 (**EVENT-DRIVEN OPERATOR CONSOLE (pack v1.1-test.5)** — console no longer full-repaints every console_refresh_s. `console_mode` (`"event"` DEFAULT in live_demo.json + shipped tester config | `"board"` legacy kept) + `alive_interval_s` (default 300, 0=off). Event mode prints the full board ONLY on major events: session start / new bar / HTF batch (immediate structure rebuild + print preserved) / flow-KPI counter delta (place, cancel, reject, fill, close, hard-cancel, friday) / new error / clean shutdown; pure-timer no-change polls print NOTHING; at most one short `[alive] utc hb_seq processed armed errors` line per interval (never a board). Heartbeat cadence untouched; display-only (`_maybe_print_console`/`_maybe_alive`, reason header `>>> event: <reason>` mirrored). +10 tests (`test_console_events.py`), suite **902**; locked_constants diff empty. Pack v1.1-test.5 rebuilt + zip-verified (console_mode=event shipped; README/PDF one-liner; bat hardening from test.4 intact). Clean-extract LIVE proof: 90 s real-terminal session → **2 full boards in 90 s vs 18 under the old cadence**, one combined bar+batch event print (mirror-log ground truth).) PREV: **2026-10-07 (**PACK v1.1-test.4: ONE-CLICK LAUNCH HARDENING + CLEAN-EXTRACT RE-PROOF** — bat template hard-wired: pip via `.venv\Scripts\python.exe -m pip` (never pip.exe by path), pip failure = hard stop + pause (never continue), no paren-in-if echoes, version bumped to v1.1-test.4 throughout. **Proven twice from fresh extractions:** placeholder path → venv+pip(incl. MetaTrader5) exit 0 → clear `ABORT: mt5.initialize failed` + pause (no flash-close); real terminal (dry_run=true override in extracted copy only) → identity PASS on DEMO 474608655, boards every 5 s, heartbeat seq 26 age 0.0s in the EA's data-folder sandbox. Shipped-zip bytes verified (python -m pip, MetaTrader5 in requirements, dry_run=false/require_demo=true untouched, _console_force present). Leftover zombie from the prior session's bat test (Temp venv operator + child, cmd 18144) killed; watchdog EA correctly re-alerts stale while no bot runs. Pack-tests 41 green; no smc source change; locked_constants diff empty.) PREV: **2026-10-07 (**PRE-SHIP PACK FIXES: BAT PAREN BUG + MISSING MetaTrader5 DEP + CONSOLE REPAINT** — pack v1.1-test.3 rebuilt. (1) run_live.bat was broken for testers ("no window opens"): unescaped parens in echo lines inside if-blocks aborted the batch at parse time — latent since test.1 because verification never executed the bat; fixed. (2) shipped requirements.txt lacked the MetaTrader5 package (main machine's global install masked it; lazy import hid it from --help smoke tests) — added `MetaTrader5>=5.0.45`. (3) "no KPI/POI printing": the 2026-10-06 mismatch fix rebuilt the snapshot on batch change but printing stayed bound to console_refresh_s (900 s in live config) — armed POIs invisible up to 15 min; fixed display-only: board now repaints within one poll of any batch change (`_console_force`), live config cadence 900→30 s. **VERIFIED END-TO-END from a clean zip extraction:** bat → venv → pip → session → identity PASS → status board `armed 2, H4 23/7/3` AND structure console with live POIs rendered. +2 tests; suite **892**; `locked_constants.py` diff empty.) PREV: **2026-10-07 (**HEARTBEAT ROOT CAUSE #2: EA SANDBOX = TERMINAL DATA FOLDER (pack v1.1-test.3)** — after the install-dir derivation still produced stale alerts, proven on disk: the installed (non-portable) MT5 EA's FileOpen sandbox is the terminal DATA folder (`%APPDATA%\MetaQuotes\Terminal\<hash>\MQL5\Files`), where a Sep-19 heartbeat file matched the alert's stale age exactly; the 12:32 session also died mkdir-ing Program Files. **Fix:** heartbeat policy now `live mt5.terminal_info().data_path (authoritative, in identity facts) → install-dir derivation (portable) → config path → logs (loud)` via new `data_folder_heartbeat_path()`; **verified LIVE** with a 75 s bounded EXNESS Copy DEMO session — heartbeat written into the EA's real sandbox file (seq 76, fresh timestamp). +6 tests, suite **886**; `locked_constants.py` diff empty. Repack `dist/SMC_v1.1-test.3_tester.zip` (includes operator-compiled `.ex5`; test.2 removed). PREV: **2026-10-07 (TESTER PACK v1.1-test.2 + HEARTBEAT PATH FIX (Architect rulings implemented)** — (1) heartbeat ruling B: when `terminal_path` is set the operator writes the heartbeat to `<terminal_dir>/MQL5/Files/smc_heartbeat.txt` (dir created if missing) so the EA sees it with default `InpHeartbeatFile`; empty/unparseable terminal_path falls back to config `heartbeat_path` or `logs/phase_d/` with a LOUD warning; new `04_SRC/smc/live/heartbeat_path.py` wired in `run_operator._build_stack`; (2) tester config `dry_run=false` (demo orders CAN place; losses possible on demo) with `require_demo=true` still blocking real accounts (fake-MT5 gate test added); (3) README/PDF/bat simplified (one paste: terminal_path; EA heartbeat input stays default) + operator note to compile `.ex5` into `mql5/` before shipping; (4) repack `dist/SMC_v1.1-test.2_tester.zip` verified (130 entries, no results/.git/secrets, mq5 only — operator adds compiled ex5). Tests `test_heartbeat_path.py` (11) + `test_require_demo_gate.py` (5); suite 875→880; `locked_constants.py` diff empty; no strategy/threshold change.) PREV: **2026-10-06 (**PRE-COMMIT HYGIENE + CONTRACT LOCK (unified GLM + Co-pilot audit ruling)** — 4-item directive implemented, no commit/push: (1) `.gitignore` now ignores `06_RESEARCH/results/` (90 MB / 773 files, HEAD tracks zero files there; curated exceptions only via explicit `git add -f`); (2) **product-mode H4+H1 detection enforcement at construction** — `MultiTFProductRuntime.__init__` raises a loud `ValueError` naming every missing timeframe when `allow_single_tf_degraded=False` and the detection set omits H4 or H1 (W1+D1 remain optional context, M5 exec unchanged, degraded opt-in still allowed; caller survey confirmed every non-test construction safe — run_operator/paper default to H4+H1, research funnels use the default); (3) `LOCKED_DECISIONS.md` **§4a amendment (2026-10-06)** — dated supersession of §4/§21/(§27) timeframe-role conflicts: H4+H1 required detection, W1+D1 optional (W1=32769 context tier), M5 execution, pointer to `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` + enforcement location; no numeric threshold or locked constant touched; (4) **F3 guard** `test_f3_asof_trim_guard.py` — pins the as_of trim convention (demonstrates Pillar-1 suffix sensitivity: trimmed PASS vs untrimmed REJECTED; asserts `build_htf_prefixes` and `PaperRunner.arm_multi_tf` never deliver a series whose last bar exceeds as_of). New tests: `test_product_mode_detection_policy.py` (6) + F3 guard (3). Suite **853 → 862**; `locked_constants.py` diff empty. **NEXT READY: commit/push prompt (3-commit split per audit: 04_SRC code+tests / 06_RESEARCH+config / 00_LOCKED governance).**) PREVIOUS: **PAPER/DEMO OPS SESSION PASS (post console fix; dry_run only)** — 20-min bounded session on DEMO 474608655 XAUUSDm with the current stack (W1 provisioned + fixed structure console + structural TP + §5a): identity PASS, 2386 polls / 5 bars, 1 HTF batch (H4 23/11/3 passed, **armed 1**, duplicates 2), **39 structure boards — every one matched detect.armed 1 with ZERO lag** (batch 16:29:01Z → board snapshot same second; the mismatch fix proven in ops), 0 orders / 0 fills / 0 errors, clean shutdown + heartbeat shutdown marker; watchdog EA attach still BLOCKED (GUI-only, honest record, not blocking). Suite 853; `locked_constants.py` diff empty. Note: `06_RESEARCH/PAPER_OPS_SESSION_NOTE.md`; artifacts `06_RESEARCH/results/paper_ops_20261006/`. **NEXT READY: project-wide independent audit → git commit/push (per Architect order).** PREVIOUS: **LIVE CONSOLE vs ARMED MISMATCH — ROOT-CAUSED + FIXED + RECONCILED LIVE (ops bugfix, dry_run only)** — **root cause:** the structure-snapshot rate limit treated the arming event (HTF batch change) like routine per-bar refreshes, so with `console_refresh_s=900` an armed POI stayed off the board up to 15 min while the status counter updated immediately (stale-snapshot window; arm path → engine `_armed_order` → `tracked_pois()` verified sound). **Fix (display wiring only):** batch changes now ALWAYS rebuild the snapshot immediately (bar refreshes stay rate-limited; idle polls no-op) + board header carries an armed counter so `detect: armed N` vs POIS can never silently diverge. 4 regression tests (`test_structure_refresh.py`); suite **849→853**. **Warm-up audit: design already correct** — LiveLoop fetches `htf_window_bars=300` per HTF at start AND for every batch (full window re-scanned, `build_htf_prefixes` trims to as_of): W1 300 bars back to **2021-01-10**, D1 300 (12 mo), H4 300 (9.5 wk), H1 300 (2.5 wk), M5 200; no operator-path override. **Live reconciliation (600 s dry_run, Copy terminal):** batch 15:40Z armed 1 (H4 23/11/3 — same counts as the Architect's pasted session) and the structure board immediately showed the armed H4 zone (LONG demand_supply+fvg+ob 3982.45-4310.83, state=TESTED, sweep-linked 1.20×ATR) — counters and console now agree on the same "armed" definition; clean shutdown, heartbeat shutdown marker. Note: `06_RESEARCH/LIVE_CONSOLE_ARMED_MISMATCH_NOTE.md`. **NEXT READY: paper trading (console trustworthy) | Architect review.** PREVIOUS: **SETUP LEDGER BACKFILL + EXPERT PACK PASS (2026-10-06, research/export only)** — direction backfilled **17/30** (trade_row 3 + EXACT unique geometry join vs 6m structure-ledger poi_raw events 14; 13 DATA_GAP — source artifacts lack those zones' geometry, never guessed); posture UNKNOWN 30/30 (not in any artifact, never price-inferred); arm_ts_utc 30/30 via exec-bar map validated 6/6 against routed trade entry/exit timestamps; human verdict/timing/notes columns STILL BLANK by design; hyp-outcome joins preserved. **Expert pack: `06_RESEARCH/results/setup_identification_ledger/EXPERT_SETUP_REVIEW_PACK.pdf`** (7 pages: cover+rubric, 30-row ledger table, 15 charts = 3 routed + D1 3/H4 6/H1 3 evenly spaced by arm bar) + report `06_RESEARCH/SETUP_IDENTIFICATION_EXPERT_REPORT.md` (rubric: CORRECT/PARTIAL/WRONG/UNCLEAR × EARLY/ON_TIME/LATE/N_A — identification quality, NOT PnL; Architect draft notes on the 3 routed rows in a clearly separated appendix). Scripts `setup_ledger_backfill.py` + `setup_ledger_expert_pack.py` (dual-run deterministic); suite 849 green; `locked_constants.py` diff empty. **NEXT ACTION: expert review of the pack (fill verdict/timing) → then paper trading prompt (paper only after expert scores or an explicit waiver).** PREVIOUS: L2 SETUP IDENTIFICATION LEDGER PASS (2026-10-06, research+export only) — script `06_RESEARCH/scripts/setup_identification_ledger.py` joins the frozen 6m post-TP funnel armed records (30 setups: H4 19/H1 6/D1 5) with hypothesis-outcome trades (run_label 6m_post_tp_run1): 3 routed with full plan (entry+SL+TP), join YES (SL_THEN_TP_PATH 2 / TP_REACHED 1, tp_source atr_fallback 2 / structural_swing 1); human columns verdict/timing/notes BLANK by design (reviewer's step, never pre-filled); honest gaps documented (direction only from trade rows, posture UNKNOWN — not instrumented in the funnel export); double-run byte-identical (setups.csv SHA 5388635e…); paper path documented (same column schema from future operator/KPI exports — no live run required for PASS); no 04_SRC/smc/** edit, `locked_constants.py` diff empty, no expectancy claims. Note: `06_RESEARCH/SETUP_IDENTIFICATION_LEDGER_NOTE.md`; outputs `06_RESEARCH/results/setup_identification_ledger/`. **NEXT READY: Architect review (L2 ledger + W/L1/dry-run chain) | paper ops.** PREVIOUS: **LIVE CONSOLE BOUNDED DRY-RUN PASS (EXNESS Copy, 2026-10-06) — ops validation only** — three bounded sessions on DEMO 474608655 XAUUSDm (150 s/400 s/420 s, dry_run=true, no orders): identity gate PASS, clean shutdowns with heartbeat `state=shutdown`; **W1 enum bug FIXED: 32768 → 32769** (the MetaTrader5 package's TIMEFRAME_W1; 32768 is rejected live by `copy_rates_from_pos` with "Invalid params" — caught by the pre-session probe, contract-restoring fix, suite 849 green with strengthened pin); real product batch fired on the 14:30:00Z M5 close (H4 22 raw→9 merged→0 passed; H1 21→8→0 passed; W1/D1/H4/H1 each fetched live at 300 bars), **7 live structure boards rendered** with honest empties (W1/D1/H4/H1 all `(none)` — zero PASSED POIs in window = Pillar rejection, not cold-start; sweeps none, plan none). Note: `06_RESEARCH/LIVE_CONSOLE_DRYRUN_NOTE.md`. **NEXT READY: L2 setup identification ledger (directive already issued — see POST_V1_ACTIVE_TODO).** PREVIOUS: **WEEKLY (W1) PROVISIONING + LIVE STRUCTURE CONSOLE — MILESTONES W + L1 BOTH PASS (Lead Architect two-sequence engagement 2026-10-06)** — **W:** `Timeframe.W1 = 32768` (MT5 PERIOD_W1, minutes=10080, §27 HTF class N=5 with `N_BAR_HTF` unchanged) wired additively at 5 seams: enum, `resample.py` (Monday-00:00 ISO-week bins — epoch-multiples would align to Thursday, deliberate market-convention exception + guard bypass), M8 `HTF_TIMEFRAMES=(W1,D1,H4)` same frozen scanner with D1×H4 overlap pairing FROZEN (quality scores untouched), `multi_tf.M8_HTF_TIMEFRAMES`, runtime `optional_timeframes=(W1,D1)`; `LiveLoop` product fetch list now `(H4,H1,W1,D1)` with batch cadence still keyed on the new H1 close; W1 role = HTF CONTEXT POI ONLY, execution stays M5; required detection set unchanged (H4,H1, loud-fail intact); suite 829→838 (+9 `test_weekly_provisioning.py`), note `06_RESEARCH/WEEKLY_PROVISIONING_NOTE.md`. **L1:** read-only structure console `smc/live/structure_console.py` (`build_structure_snapshot` + `render_structure_console`, pure ASCII renderers, not MT5 chart objects) with sections POIS / SWEEPS / SEEKING / PLAN — W1 rows are LIVE engine data (not hardcoded demo rows), honest empties pinned; operator wiring refreshes on a new M5 bar and/or HTF batch, rate-limited to `console_refresh_s`; additive display-only seams `MultiTFBatchReport.displacements` + `LiveLoop.sweep_links` + `PipelineAdapter.active_workflows()`; suite 838→849 (+11 `test_structure_console.py`, fake snapshots, no MT5); design `06_RESEARCH/LIVE_STRUCTURE_CONSOLE_DESIGN.md`, note `06_RESEARCH/LIVE_STRUCTURE_CONSOLE_NOTE.md`. Both milestones: `locked_constants.py` diff empty; no pillar/trigger/SL/TP/risk/§5a changes; no expectancy claims. **NEXT READY: L2 setup identification ledger (parked until Architect/user requests setup-count validation) | Architect review of W+L1. Do NOT start L2 without a ruling.** PREVIOUS: STRUCTURAL TP FEED — IMPLEMENTED + MEASURED 2026-10-05 (design accepted; diagnostic only)** — the accepted design lock implemented on the minimal surface: pure selector `structural_tp_target` in `smc/backtest/pipeline_bridge.py` (§19-confirmed swings, `confirmed_index < placement_bar` strictly before the decision bar; LONG nearest valid swing high strictly beyond `entry + STRUCTURAL_TP_MIN_ATR × atr`, SHORT mirrored; recency tie-break; documented age bound = `poi_give_up_bars()` as CPU/age cap, NOT give-up semantics per Architect ruling) fed at the EXISTING adapter `candidate_from_route(structural_target=)` call site on the SAME place-time prefix the scan consumed; `resolve_take_profit` untouched; interim constant `STRUCTURAL_TP_MIN_ATR = 0.25` module-level (Architect-accepted, pinned in tests, pending formal § lock); `tp_source` audit provenance threaded E1-style candidate→order→position (BE-preserving)→TradeRecord→CSV/JSON, audit-only (test-enforced no reads in risk/**). Measurement on the frozen 3m window (dual run, harness `structural_tp_feed_measurement.py`, artifacts `06_RESEARCH/results/structural_tp_feed/`): **placed 2 → structural 1 / fallback 1 (50/50), TP non-null 100%, fills 2, trades 2**; exit mix **take_profit 1 + stop_loss 1 (BE-scratch 1)** vs pre-feed stop_loss 2 — the C trade poi-001022 flipped SL −0.3728 → structural TP **HIT +0.3852** (nearer first-swing target reached before stop); F trade fallback byte-identical to pre-feed (+0.0715 BE scratch); **net +0.4567 diagnostic n=2 — NOT performance, no edge claim; mechanism demonstration only**. **Determinism PASS** (trades.csv + report.json byte-identical, SHA `00ee227e…`). Suite **805 → 829** (24 new `test_structural_tp_feed.py`); 2 pre-existing CSV header-end assertions updated for the appended `tp_source` column (E1 convention — column-order assertions retained); `locked_constants.py` diff empty. Note: `06_RESEARCH/STRUCTURAL_TP_FEED_IMPLEMENTATION_NOTE.md`. **PREVIOUS: STRUCTURAL TP FEED — DESIGN LOCK COMPLETE 2026-10-05 (design only, LOGIC_CHANGED: NO)** — `06_RESEARCH/STRUCTURAL_TP_FEED_DESIGN.md`: first-swing selector REUSES the existing §19 swing machinery (`SeriesState`/`SwingIndex.last_valid`), place-time lookahead-safe (prefix-bounded `before = placement_bar`, confirmed swings only, no fill-time refinement); LONG = most recent §19-valid swing high strictly above entry, SHORT mirror, nearest-in-price with recency tie-break, bounded by the armed POI lifecycle (confirmed ≥ arm_bar or base ≥ arm_bar − `poi_give_up_bars()` — PROPOSED reuse); guard `STRUCTURAL_TP_MIN_ATR = 0.25` PROPOSED (note only, not written); attachment = the EXISTING `candidate_from_route(structural_target=...)` kwarg at the existing adapter call site (~L193) + `tp_source=` provenance string; `resolve_take_profit` and fallback 4×ATR untouched; SL explicitly unchanged (policy B); 30-pip absent (policy C). **PREVIOUS: DOCS-ONLY POLICY SYNC COMPLETE 2026-10-05 — governance aligned with the accepted work (Option B seek/scan redesign, frozen 3m + 6m funnels, expert marked charts archive) and the Lead Architect policy rulings A–E recorded in the "Standing rulings + accepted state (2026-10-05)" section below; no code, no constants, LOGIC_CHANGED: NO.** PREVIOUS: **STAGE 3 LIFECYCLE TIMING AUDIT COMPLETE 2026-10-04 — identification only, distributions not opinions: all 263 Stage 3 completions joined to their parent HTF structures (DATA_GAP 0 / NEVER_ARMED 0) and timed against the product arm / first-touch / scan-close events via the accepted instrumented §5 replay. Buckets: **OPEN_SCAN 2 (0.76% all, 0.98% F)**, CLOSED_TOUCH 199 (75.67%), CLOSED_VIOL 62 (23.57%); 2 routed rows sanity → OPEN_SCAN PASS; median completion−scan_close 10 bars (all) / 10 bars (F); structure findings: arm = close bar for all rows (11 weekend minute-gaps), first_touch == arm for all 199 touch-closed structures (effective seek span [arm, arm+1]), all 62 violations fire at arm (scan never opens); 3 illustrative charts; double-run byte-identical; suite 772→780; report `06_RESEARCH/STAGE3_LIFECYCLE_TIMING_REPORT.md`.** PREVIOUS: **STAGE 3 TRIGGER VISIBILITY + CONVERSION AUDIT COMPLETE 2026-10-04 — identification only: 668 accepted HTF structures scanned at the product horizon [close, close+20 M5]; **263 completed Stage 3 triggers** (A 31 / B 17 / C 4 / D 0 / E 7 / F 204; M5 263 / M1 0), all HTF-linked (0 unlinked by construction, disclosed); conversion 15,350 detector links → 263 completions (1.71%) → 2 product routes; route funnel: 261 completions suppressed by the §5 armed-POI lifecycle (199 first-touch+1 gate, 62 zone violation), 2/2 inside the open scan routed (same 2 as LTF pack); 36 charts (30 trigger panels type-seeded June→Nov + 6 negative examples); double-run byte-identical; suite 762→772; report `06_RESEARCH/STAGE3_TRIGGER_VISIBILITY_REPORT.md`.** PREVIOUS: **LTF CONFIRMATION PACK COMPLETE 2026-10-04 — structure/confirmation identification, identification-only: 668 HTF structures (658 H4 pack raw + 10 D1 subset; ob 177/ds 307/fvg 184), stage0 M15=13,474 / M5=37,015, ledger 15,352 rows; dual=0 per source pack, conflicts=0; activity 624 / silent 44; trigger mix {F:2} pre-pillar routes; sample 13 (7 active + 6 silent) = 39 panels, caps ≤12/≤8/≤40; look-ahead M5=20 (TRIGGER_A_EXPIRY) / M15=7 same rule every structure; double-run byte-identical; suite 754→762; report `06_RESEARCH/LTF_CONFIRMATION_REPORT.md`; note `06_RESEARCH/LTF_CONFIRMATION_NOTE.md`.** PREVIOUS: **H4 POI IDENTIFICATION PACK COMPLETE 2026-10-04 — structure confirmation, identification-only: raw 658 (ob 177/ds 304/fvg 177) / merged 3 / armed 0; dual=0, conflicts=0, origin_tight=0, all rows H4; 55 charts; double-run byte-identical; suite 750→754; report `06_RESEARCH/results/h4_poi_confirmation/H4_POI_CONFIRMATION_REPORT.md`; note `06_RESEARCH/H4_POI_CONFIRMATION_NOTE.md`.** ACTIVE PROGRAM: V1.1 RUNTIME BASELINE FROZEN (docs-only freeze, 2026-09-24 — `00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md`).** The frozen baseline = Choice 1 Product Runtime Unification (Phase 0 contract + C1 multi-TF runtime in live/paper + Phase 2 contracts + Phase 3 funnel + Phase 4 byte-identical frozen 3-month backtest) + Track A (E1 entry_anchor export DONE, C3 UNFED_DESIGN_ONLY, C4 news/sweep DEFERRED + spread WIRED) + Phase D HTF probe PASS on EXNESS Copy DEMO (H4/H1/D1=300 bars, dry_run loop clean). **Expectancy / PF / live profitability are NOT proven and NOT part of the freeze** — the default posture is operate-and-observe under contract, not redesign. **Allowed without a ruling:** Phase D ops (watchdog EA attach + emergency drill, stability logging), contract-restoring bugfixes, docs. **Requires a dated ruling:** locked_constants edits; pillar/trigger/zone/R7/R9 edits; F-timing/Monte Carlo; structural TP invention; treating demo PnL as idea validation; dry_run=false campaigns. **NEXT ACTION = Architect review of hypothesis-outcome study (SL_THEN_TP_PATH 4 / TP_REACHED 2 / MFE_ONLY 0 / REJECTED 0 / DATA_GAP 0 on the 6m post-TP n=3 sample; cross-tabs by trigger/tp_source/close_kind recorded; no strategy logic change).** Next engagement after that review: whatever the Architect rules for Phase D / hypothesis-outcome analytics follow-on. BANS stand: F-survivor/F-timing PAUSED (R6), Monte Carlo PAUSED, demo PnL never idea validation, no locked-constant edits without a dated ruling.

**Future product mode (docs-only, registered, not started):** **Mode B — Mid-TF structure / scalp path (M15/M30)** is registered as a future track in `06_RESEARCH/MODE_B_MID_TF_SCALPING_STUB.md`. Contrast: Mode A (current frozen product) = H4+H1 required structure, W1+D1 optional context, M5 execution; Mode B (future) = M30 and/or M15 may emit POI (OB/FVG/demand-supply) → zone sweep → lower-TF confirm (M5/M1) → plan. Implement only on a dated ruling after the Mode A identification/ops track is stable; not started; **frozen product remains Mode A**.

PRIOR: TRACK A RESIDUAL ENGINEERING COMPLETE (E1→C3→C4, ordered; per owner prompt). E1 entry_anchor export DONE — first-class field on the full trade path (bridge→order→position→TradeRecord→CSV/JSON, appended + backward compatible; modify_sl preserves it like original_sl; also inside signal_data_json); suite 726→737. C3 structural TP = UNFED_DESIGN_ONLY — design note written BEFORE code (`06_RESEARCH/RESIDUAL_A_E1_C3_C4_NOTE.md` §C3); no trigger emits a structural target, nothing invented, TP stays frozen 4×ATR (FR-2 R4). C4 dispositions — news DEFERRED, spread WIRED (operator input, threaded to §28.5 grading), sweep-guard DEFERRED (no trigger emits sweep_level); formal Silent/deferred table in `PRODUCT_RUNTIME_CONTRACT.md` §8; shipped configs (`news_events=[]`, `spread_price=0.0`) remain diagnostic, NOT "gates proven live". No decision-logic change, no locked-constant edit. PRIOR: PRODUCT RUNTIME UNIFICATION (Phase 0–4, owner "Choice 1") — ALL FOUR PHASES COMPLETE/PASS. Phase 4 frozen 3-month measurement (exec 2025-09-01→11-30): 17 armed / 8 routes (all F) / 1 BE-scratch fill (+0.0715 diagnostic); trades.csv + report.json BYTE-IDENTICAL across run1/run2; paper dry wiring proven. NEXT ACTION = Lead Architect accept Track A, or Phase D HTF probe on EXNESS — NOT silent F-optimization.** Prior: PHASE 0 + PHASE 1 C1 COMPLETE — ONE MULTI-TF PRODUCT RUNTIME: contract `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` + shared seam `smc/orchestration/multi_tf_runtime.py`; live/paper no longer single-TF (H4+H1 detection, D1→M8, batch per new H1 close, start-time HTF probe refuses in product mode); suite 698 green; no threshold/constant edits.** Prior: AS-CODED ARCHITECTURE EXTRACTION COMPLETE (Part 1 of 3 — report + pictures + inventory; comparison vs Rev 5 COMPLETE (Lead Architect Part 2 — verdict gaps C1–C4 recorded in CHANGELOG); 6-month structure ledger NOT started).** Prior: FOUNDATION FIDELITY RESET ACTIVE — fill-regime rulings R7+R8 implemented, then R9 place-on-reentry intent: FIRST COMPLETE CHAIN under frozen rules (armed→re-entry→FILL→BE→close +0.07, M8 poi-014750; suite 681). PAUSED Trigger F survivor optimization as main track.** Prior: FR-3.1 PASS (on-zone entry anchor) · FR-4 + fate ledger + FR-4b + unfilled forensic DONE · Track R CLOSED (R1–R5 PASS) · Export identity/zone patches DONE · Phase C CLOSED, Phase D OPENED session 1 on EXNESS Copy terminal.)
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

**Tester release pack built (v1.1-test.1):** tester run surface assembled and verified in `dist/` + `06_RESEARCH/releases/`: `dist/SMC_v1.1-test.1_tester.zip`, `dist/TESTER_SETUP_GUIDE.pdf`, `dist/TESTER_README.md`, `06_RESEARCH/releases/TESTER_README.md`, `dist/VERSION.txt`, `dist/run_live.bat`, `dist/config/live_tester.json`, `dist/SUPPORT.txt`, `dist/mql5/SMC_Safety_Watchdog.mq5`, plus the shipped `04_SRC/smc` package. Verified end-to-end: zip contains all required artifacts, no forbidden artifacts, PDF parses and mentions the required steps/rules, and `cd extracted_folder && python 04_SRC/smc/live/run_operator.py --help` succeeds from the extracted tree. Config verified: dry_run=true, require_demo=true, detection_timeframes [H4,H1], placeholder terminal_path, symbol XAUUSDm, magic 20260919. No 04_SRC changes, no locked_constants edits, no strategy/threshold changes; results/ untouched; no test suite shipped as runnable tests. Governance docs updated; not committed unless asked.

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
