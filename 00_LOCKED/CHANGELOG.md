# CHANGELOG

**Last Updated:** 2026-10-06
**Rules:** Every change to the project is recorded here. Format: date, session title, what was added/changed/fixed.

---

## [Unreleased]

### 2026-10-06 — Pre-commit hygiene + product contract lock (unified GLM + Co-pilot audit ruling)
- **Repo hygiene:** `.gitignore` now ignores `06_RESEARCH/results/` — bulk run artifacts (≈90 MB / 773 files as of the audit; HEAD tracks zero files there). Policy: local-only by default; curated exceptions (e.g. `setups.csv` / `summary.json`) require an explicit `git add -f`. Untracked inventory drops the whole results tree from `git status`.
- **Product-mode detection policy enforced at construction:** `MultiTFProductRuntime.__init__` (in `04_SRC/smc/orchestration/multi_tf_runtime.py`) now raises a loud `ValueError` naming **every missing timeframe** when `allow_single_tf_degraded=False` and `detection_timeframes` omits H4 or H1 (e.g. `missing: H1`). W1+D1 stay optional context; M5 execution unchanged; the explicit `allow_single_tf_degraded=True` opt-in (tests/legacy) skips the check and remains the only path below the H4+H1 minimum. Caller survey confirmed every non-test construction is compliant (operator config defaults to H4+H1; paper runner and research funnels use the default). New tests: `04_SRC/tests/test_product_mode_detection_policy.py` (6 — reject missing H1, reject missing H4, reject context-only W1+D1, accept H4+H1 and extended sets, default construction compliant, degraded opt-in still allowed).
- **Contract lock:** `00_LOCKED/LOCKED_DECISIONS.md` gains **§4a (amended 2026-10-06)** — a dated amendment record (same format as §5a) superseding §4/§21/(§27) timeframe-role conflicts: **H4+H1 required detection minimum**, **W1+D1 optional context** (W1 = `Timeframe.W1` 32769 context tier; D1 forwarded to M8 when present), **M5 execution**, degraded single-TF detection opt-in only. Cites the enforcement site, the tests, and `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md`. **No numeric threshold or locked constant changed** (`locked_constants.py` diff empty).
- **F3 look-ahead guard (no behavior change):** new `04_SRC/tests/test_f3_asof_trim_guard.py` (3 tests) pins the as_of trim convention that makes Pillar 1's `candles[active_index+1:]` mitigation suffix look-ahead-safe: (1) it demonstrates the suffix sensitivity — the same POI PASSes on the as_of-trimmed series and is REJECTED (`naked level`) when a post-as_of mitigating close is present; (2) `build_htf_prefixes` never returns a bar after `as_of` on any timeframe (inclusive bar-at-as_of semantics); (3) `PaperRunner.arm_multi_tf` (the live loop's dispatch target) delivers exactly the trimmed prefixes to the runtime. No production code changed by F3.
- **Verification:** suite **853 → 862 passed** (0 skipped); `04_SRC/smc/config/locked_constants.py` diff empty; `git check-ignore 06_RESEARCH/results/` matches and zero results entries appear in `git status`. No commit/push performed (per directive). LOGIC_CHANGED: NO (enforcement only rejects invalid construction; no threshold, pillar, trigger, SL/TP, risk, or §5a change).

### 2026-10-06 — Project-wide independent audit (findings only; commit readiness YES_WITH_CAVEATS)
- **Added** `06_RESEARCH/PROJECT_WIDE_AUDIT_2026-10-06.md` (Lead Architect pre-commit audit). Verdict: decision path sound/conservative/honestly documented; architecture fidelity high (one frozen composition, no second stack); look-ahead **CONFIRMED CLEAN** (existing note re-verified, nothing new); console↔armed proven in ops; research honesty held (diagnostic-only labeling, blank human columns); suite 853/0 skipped; `locked_constants.py` diff empty; no secrets in tree; W1=32769 verified. **Findings:** 0 Critical, 1 Major (repo hygiene: `06_RESEARCH/results/` = 90 MB untracked AND unignored — HEAD tracks zero results files; policy decision required before commit: recommended = gitignore the tree + curated summaries exception), 4 Minor (F3 prefix convention → include test-level guard pre-commit per pre-approved ruling; interim STRUCTURAL_TP_MIN_ATR lock pending ruling; gate-mirror literals display-only; shared heartbeat path), 5 Info. **Commit plan:** 3 commits (src+tests / research+config / governance), never commit 07_DATA/logs/03_REFERENCE_CODE. `04_SRC/smc/**` untouched by the audit; LOGIC_CHANGED: NO.

### 2026-10-06 — Paper/demo ops session PASS (post console fix; dry_run only)
- **Session:** 20-min bounded run on the EXNESS Copy terminal (DEMO 474608655, XAUUSDm from config, dry_run=true — zero orders by design): identity gate PASS; 2386 polls / 5 new M5 bars; 1 HTF batch at session start (H4 23 raw/11 merged/**3 passed**, H1 22/7/0, **armed 1**, duplicates 2 — batch re-scanned the full 300-bar warm-up window per TF). **Console consistency proven in ops:** 39 structure boards rendered, every one matched `detect.armed 1` with ZERO lag (batch logged 16:29:01Z, board snapshot stamped 13:29:01 UTC — same second); header armed counter on all boards. Clean shutdown, heartbeat `state=shutdown`. Watchdog EA attach still BLOCKED (GUI-only; honest record, not blocking). 0 errors. Suite 853 (read-only session); `locked_constants.py` diff empty. Note: `06_RESEARCH/PAPER_OPS_SESSION_NOTE.md`; artifacts `06_RESEARCH/results/paper_ops_20261006/`. NEXT READY: project-wide independent audit → git commit/push (per Architect order).

### 2026-10-06 — Look-ahead / next-bar / statistical-bias audit (findings only, no code change)
- **Added** `06_RESEARCH/LOOKAHEAD_BIAS_AUDIT_NOTE.md` (Lead Architect request: independent audit, findings for review, no implementation). Verdict: **no look-ahead found in the frozen decision path** (bar-ordered loop, expiry→fills→scan→placement ordering with bar-B placement cannot fill on B, touch=fill at limit price, SL-first same-bar rule, prefix-bounded scans/folds, as_of-trimmed batches verified at every call site). **Next-bar semantics correct** (limit rests ≥ 1 bar); two documented near-boundary items flagged: arm-bar posture uses same-bar range (live-consistent, §5a design) and Pillar-1 mitigation suffix is prefix-safe only by upstream trimming convention (recommendation: explicit guard). **Statistical bias: none in product code** (no ML/calibration imports); the operator command prompt identified as the plausible bias channel (findings-led iteration on n=3 studies, prompt-originated numbers) — existing bans reaffirmed (findings = diagnostic only, prompt numbers = review metrics, locked-constant edits need dated rulings, n<30 = classification never rule). Recommendations listed for review; none implemented. `04_SRC/smc/**` untouched.

### 2026-10-06 — Live console vs armed mismatch: root cause + fix + warm-up audit (ops bugfix, dry_run only; PASS)
- **Root cause:** the structure-console snapshot rate limit (`_maybe_refresh_structure` in `run_operator.py`) treated an HTF batch change — the arming event — like routine per-bar refreshes, gated by `console_refresh_s` (900 s on the live config): a POI armed just after a rebuild stayed invisible on the board up to 15 min while `detect: armed 1` updated immediately. Arm path verified sound (engine `_armed_order` → `tracked_pois()` → snapshot builder); it was a stale-snapshot window, not missing POIs.
- **Fix (display wiring only):** batch changes now ALWAYS rebuild the snapshot immediately; new-bar refreshes stay rate-limited; idle polls remain no-ops. Board header now carries an armed counter (`… (read-only snapshot; armed N)`) so the status counter and POIS sections can never silently diverge. 4 regression tests in `test_structure_refresh.py`; suite **849 → 853**; `locked_constants.py` diff empty.
- **Warm-up audit (design confirmed):** HTF POIs come from a historical window, not session birth — `LiveLoop` fetches `htf_window_bars=300` per W1/D1/H4/H1 at start AND re-fetches the full window for every H1-close batch (prefix-trimmed to `as_of`); live proof on the Copy terminal: W1 300 bars (oldest 2021-01-10), D1 300 (2025-10-21), H4 300 (2026-07-30), H1 300 (2026-09-17), M5 200; no operator-path override.
- **Live reconciliation (600 s dry_run, DEMO, no orders):** batch at 15:40Z armed 1 (H4 23 raw/11 merged/3 passed — same counts as the Architect's pasted session); structure boards (21 rendered) immediately showed the armed H4 zone (LONG demand_supply+fvg+ob 3982.45-4310.83, state=TESTED, sweep link 1.20×ATR) — counters and console agree on the same "armed" definition; clean shutdown + heartbeat shutdown marker. Note: `06_RESEARCH/LIVE_CONSOLE_ARMED_MISMATCH_NOTE.md`.

### 2026-10-06 — Setup ledger backfill + expert review pack (research/export only; PASS)
- **Backfill (direction 17/30):** new `06_RESEARCH/scripts/setup_ledger_backfill.py` fills `direction` deterministically from existing artifacts only — trade_row first (3 routed), then EXACT unique (detection_tf, zone_low, zone_high) geometry match against 6m structure-ledger `poi_raw` events (14); tolerance probing (0.01/0.05/0.2) adds zero unique fills and only ambiguity, so the strict rule stands; 13 rows = DATA_GAP (source artifacts lack those zones' geometry+direction — left blank, never guessed). `direction_source` column added; `posture` stays UNKNOWN 30/30 (not in any artifact — armed_records/funnel_summary/report.json checked; never inferred from price); `arm_ts_utc` filled 30/30 from the exec M5 bar-index map (exec bar 0 = window start) **validated 6/6** by reproducing the routed trades' recorded entry/exit timestamps; human verdict/timing/notes columns remain BLANK (rule untouched); hyp-outcome joins preserved. setups.csv re-emitted dual-run byte-identical (SHA 3766d6d0…); summary.json gains `backfill` block.
- **Expert pack:** new `06_RESEARCH/scripts/setup_ledger_expert_pack.py` → **`06_RESEARCH/results/setup_identification_ledger/EXPERT_SETUP_REVIEW_PACK.pdf`** (7 pages: cover + scoring rubric, 30-row ledger table, 15 charts at 3/page) + **`06_RESEARCH/SETUP_IDENTIFICATION_EXPERT_REPORT.md`** (rubric CORRECT/PARTIAL/WRONG/UNCLEAR × EARLY/ON_TIME/LATE/N_A — identification quality, NOT PnL/edge; return-by instructions) + `charts/` 15 PNGs in the frozen house visual language (candles on detection TF, zone band, arm-bar marker, routed entry/SL/TP/exit marks, honest DATA_GAP labels). Sampling rule documented: all 3 routed + stratified non-routed D1 ≤4 / H4 ≤6 / H1 ≤3 evenly spaced by arm bar. Architect draft notes on the 3 routed rows appear ONLY in a clearly separated report appendix ("not expert verdict"). Chart pages verified non-blank (pixel variance) and PDF paginated (7 pages).
- **Governance:** bans honored (no strategy/threshold edits; `locked_constants.py` diff empty; no expectancy claims); suite 849 green. **NEXT ACTION = expert review of the pack (fill verdict/timing) → then paper trading prompt (paper only after expert scores or an explicit waiver).**

### 2026-10-06 — L2 setup identification ledger (research + export analytics; PASS)
- **Added** `06_RESEARCH/scripts/setup_identification_ledger.py` + outputs `06_RESEARCH/results/setup_identification_ledger/` (setups.csv + summary.json): one row per armed setup from the frozen 6m post-TP funnel artifacts — **30 setups** (H4 19 / H1 6 / D1 5) with full identity (TF, poi_id, kind, zone bounds/mid, arm bar, pillar path, disp ×ATR, routed, trigger, entry/SL/TP, entry_anchor, tp_source) + human-scoring columns **verdict / timing / notes left BLANK by design** (the reviewer's judgement; the script never pre-fills) + hypothesis-outcome join (3 routed setups with full plan: SL_THEN_TP_PATH 2 / TP_REACHED 1; tp_source atr_fallback 2 / structural_swing 1). Honest gaps documented: direction only where the trade row carries it, posture UNKNOWN (not instrumented in the funnel export), kind = model tags. **Double-run byte-identical** (setups.csv SHA-256 5388635e…); input file SHA-256s recorded for provenance. Paper path documented (same column schema from future operator/KPI exports; no live run required). Research + export only: no `04_SRC/smc/**` edit, `locked_constants.py` diff empty, no expectancy claims, no threshold changes. Note: `06_RESEARCH/SETUP_IDENTIFICATION_LEDGER_NOTE.md`.

### 2026-10-06 — Live console bounded dry-run PASS + W1 enum contract fix (ops validation only)
- **W1 enum bug fixed (contract-restoring data-boundary fix):** the weekly-provisioning enum used W1=32768, but the MetaTrader5 package's `TIMEFRAME_W1` is **32769** (0x8001); live probe on the EXNESS Copy terminal showed `copy_rates_from_pos("XAUUSDm", 32768, …)` fails with "Invalid params" while 32769 returns 300 weekly bars. `Timeframe.W1 = 32769` in `smc/config/timeframe.py` (docstring documents the trap) + `test_enums.py` pin strengthened; suite **849 passed** after the fix; `locked_constants.py` diff empty. Both W/L1 notes corrected.
- **Dry-run PASS (three bounded sessions, DEMO 474608655, XAUUSDm, dry_run=true, no orders):** 150 s (299 polls, cold-start anchor), 400 s (797 polls, **1 bar → real HTF batch at 14:20:00Z**: H4 22 raw→9 merged→0 passed, H1 21→8→0 passed), 420 s (837 polls, batch at 14:30:00Z, **7 live structure boards** rendered, all honest empties — zero passed POIs is Pillar rejection on the 9-merged window, NOT cold-start: W1=300 bars ≈ 5.8 y and D1=300 ≈ 12 mo are provisioned). Clean shutdowns with heartbeat `state=shutdown` on all three. Identity gate PASS (path-family match, DEMO refused nothing — require_demo=true). Artifacts: `06_RESEARCH/LIVE_CONSOLE_DRYRUN_NOTE.md`, `06_RESEARCH/results/live_console_dryrun_console.txt`, `logs/live_console_dryrun/`, `config/live_console_dryrun.json` (ops-only cadence/log-dir config). NEXT READY: L2 setup identification ledger.

### 2026-10-06 — Weekly (W1) provisioning + live structure console (Lead Architect two-sequence engagement: Milestones W + L1, both PASS)
- **Milestone W — WEEKLY (W1) PROVISIONING (suite 829 → 838).** `Timeframe.W1 = 32768` added (MT5 `PERIOD_W1`, minutes=10080, `is_htf()` includes W1 — §27 N=5 class with `N_BAR_HTF` unchanged); W1 is HTF **context** POI only, execution stays M5. Seams extended (no second detection stack): `resample.py` Monday-00:00 ISO-week bins (deliberate market-convention exception — epoch-multiples of 10080 min would align to Thursday) + 1440-modulo guard bypass; M8 `HTF_TIMEFRAMES=(W1,D1,H4)` — same frozen scanner, same constants, **D1×H4 overlap pairing left frozen** so §26 quality scores are untouched; `multi_tf.M8_HTF_TIMEFRAMES`; `MultiTFProductRuntime.optional_timeframes=(W1,D1)` (required set H4+H1 unchanged, loud-fail intact); `LiveLoop` product fetch list `(H4,H1,W1,D1)` via the existing `int(tf)` → `PERIOD_W1` cast, batch cadence still keyed on the new H1 close. Tests: `test_weekly_provisioning.py` (9 — Monday alignment, honest OHLCV, no invented weekend bars, determinism, M8-on-W1 impulse, W1 required + optional runtime paths, live fetch + cadence + legacy unchanged) + `test_enums.py` pins strengthened (E1 convention). Note: `06_RESEARCH/WEEKLY_PROVISIONING_NOTE.md`.
- **Milestone L1 — LIVE STRUCTURE CONSOLE (suite 838 → 849).** New `smc/live/structure_console.py`: read-only snapshot builder + pure ASCII renderer with sections **POIS / SWEEPS / SEEKING / PLAN** (W1 rows are LIVE engine data — not hardcoded demo rows; honest empties `(none)` / `SWEEPS: none` / `SEEKING: none` / `PLAN: none`). Operator wiring (`run_operator.py`): snapshot refreshed on a new M5 bar and/or HTF batch, rate-limited to `console_refresh_s`; board appended under the status board + mirrored. Additive display-only seams: `MultiTFBatchReport.displacements`, `LiveLoop.sweep_links`, `PipelineAdapter.active_workflows()` (public copy). Not an MT5 chart dashboard; zero decision impact. Tests: `test_structure_console.py` (11 — real engine + synthetic POIs, no MT5). Design `06_RESEARCH/LIVE_STRUCTURE_CONSOLE_DESIGN.md`; note `06_RESEARCH/LIVE_STRUCTURE_CONSOLE_NOTE.md`.
- **Governance:** `SESSION_HANDOFF.md` + `POST_V1_ACTIVE_TODO.md` updated. NEXT READY: L2 setup identification ledger (parked — needs a dated ruling) | Architect review. Bans honored: no pillar/trigger/SL/TP/risk/§5a changes, no expectancy claims; `locked_constants.py` diff **empty**; LOGIC_CHANGED: NO.

### 2026-10-05 — Structural TP feed IMPLEMENTED + MEASURED (diagnostic only; design accepted; Architect-accepted 2026-10-06)
- **Architect-accepted (2026-10-06):** the structural TP feed is now accepted live V1 logic. Ruling A status: IMPLEMENTED (structural first-swing feed live via `structural_target=` / `structural_else_4ATR`); ruling B (SL stays ATR/structural) and ruling C (30-pip = MAE yardstick only) unchanged.
- **2026-10-06 — Wider frozen-window diagnostic under structural TP feed (6m, diagnostic only; dual-run deterministic).** Same frozen 6m window (exec 2025-06-01→11-30, M1 load 2025-05-01) under the CURRENT machine (seek/scan §5a + structural TP feed live), via imported composition `frozen_funnel_6m_post_tp.py`. Outcome (run1; run2 semantically identical): armed 30 (M8 28; H4 19/H1 6/D1 5), scans 501, **routes 10 {F 9, C 1}**, placed 4 (TP 4/4 non-null = 100%), **fills 3, trades 3**, placed-level TP source **structural_swing 1 (25% of placed) / atr_fallback 2 (50%) / none 1 (25%)**, trades-level TP source **structural_swing 1 / atr_fallback 2**, exit mix **take_profit 1 + stop_loss 2 (BE-scratch 1)**; net **−2.4537 diagnostic n=3** (vs pre-TP-feed 6m net −3.2117; the structural TP hit +0.3852 is the C trade poi-047805, vs that trade's pre-feed SL −0.3728 — same C trade, structural target now hit). **Determinism PASS** (funnel agree + trades.csv + report.json byte-identical). Honest residual: armed-posture mix NOT instrumented on these run artifacts (report states UNKNOWN; pre-TP 6m = CLEAN 30/IN_ZONE 0/VIOLATION 0 for reference). **No `04_SRC/smc/**` edit** (only the measurement harness `06_RESEARCH/scripts/frozen_funnel_6m_post_tp.py`, which reads the composition's own artifacts); `locked_constants.py` diff empty. Report: `06_RESEARCH/FROZEN_FUNNEL_6M_POST_TP_REPORT.md`. **NEXT = Architect review of 6m post-TP diagnostic.
- **2026-10-06 — Hypothesis-outcome analytics (research/logging only; taxonomy locked; no strategy logic change).** For each closed trade in the 6m post-TP diagnostic, classify whether the entry hypothesis was directionally supported by later price, independent of whether the managed trade won. Script `06_RESEARCH/scripts/hypothesis_outcome_study.py` (reads the composition's own 6m run artifacts + M5 exec OHLC from `07_DATA/XAUUSD_M1.parquet` — no strategy edit); outputs `06_RESEARCH/results/hypothesis_outcome/trades_hypothesis.csv` + `summary.json`; report `06_RESEARCH/HYPOTHESIS_OUTCOME_REPORT.md`. Outcome (run1==run2; n=6 rows = 3 unique trades x 2 runs): **SL_THEN_TP_PATH 4, TP_REACHED 2, MFE_ONLY 0, REJECTED 0, DATA_GAP 0**. Cross-tabs: by trigger {F: SL_THEN_TP_PATH 4, C: TP_REACHED 2}; by tp_source {atr_fallback: SL_THEN_TP_PATH 4, structural_swing: TP_REACHED 2}; by close_kind {stop_loss: SL_THEN_TP_PATH 4, take_profit: TP_REACHED 2}. Narrative: on THIS n=3 sample, 2 of 3 unique trades had the same TP level later touched after a stop-first exit (the F trades poi-014146 and poi-073511) — that is the clearest 'confirmations enough but timing/management cost' class; the C trade (poi-047805) realized the carried structural TP via live take_profit. MFE/|original_sl| was a tiny fraction of the stop for the stopped trades (MFE ~3.5 on the short F, ~20.4 on the long F vs their much larger original_sl), so by the documented 0.25R analytics divider those stopped F trades would still read as 'weak favorable excursion vs stop' even though the TP level was later touched — i.e. the later-touched-TP signal and the small-vs-stop signal are NOT the same thing on this sample. 3m post-TP structural_tp_feed `trades.csv` absent on disk, so the study is 6m-only this run (n=3 unique trades) — still PASS because the taxonomy is correctly applied and documented. **Honest residual:** MFE/MAE and after-exit TP touch are computed from the M5 exec series indexed by the trade's entry_bar/exit_bar; if exit_bar lands beyond the exec series or on a timestamp not present in the M5 slice, the affected MFE/MAE/Touch flags would be understated — this sample's exit bars were all within the series and the results are internally consistent (TP_REACHED trades show MFE<=MAE<=distance-to-TP consistent with a live TP hit; SL_THEN_TP_PATH trades show tp_touched_after_entry=True AND tp_touched strictly after exit=True). **Bans honored:** no edits under 04_SRC/smc/ strategy paths; logging-only script; locked_constants.py diff empty; no stop widening / TP retune / expectancy claims; taxonomy labels NOT promoted into live filters. **NEXT = Architect review of hypothesis-outcome study.**
- **Implemented** the accepted structural TP design (`STRUCTURAL_TP_FEED_DESIGN.md`, addendum records the Architect's two constant rulings): pure selector `structural_tp_target` added to `smc/backtest/pipeline_bridge.py` (§19-confirmed swings with `confirmed_index < placement_bar` — strictly before the decision bar; LONG nearest valid swing high strictly beyond `entry + STRUCTURAL_TP_MIN_ATR × atr`, SHORT mirrored; recency tie-break; documented `max_age_bars` CPU/age bound) fed at the existing `PipelineAdapter` → `candidate_from_route(structural_target=...)` call site on the same place-time prefix the trigger scan consumed; `resolve_take_profit` untouched (sidedness/finiteness re-validation unchanged); 4×ATR fallback byte-for-byte unchanged; interim constant `STRUCTURAL_TP_MIN_ATR = 0.25` module-level (Architect-accepted, pinned in tests, pending formal § lock).
- **Provenance:** new audit-only `tp_source` field ("structural_swing" | "atr_fallback", None = legacy) threaded E1-style CandidateEntry → PendingOrder → BacktestPosition (preserved verbatim on BE `modify_sl`) → TradeRecord → `trades.csv` appended column (after `entry_anchor`) + `report.json` key; never read by risk/fill/BE logic (test-enforced). Two pre-existing CSV header-end assertions updated for the appended column (E1 convention; column-order assertions retained).
- **Measured (frozen 3-month window, dual run; `structural_tp_feed_measurement.py`, artifacts `06_RESEARCH/results/structural_tp_feed/`):** placed 2 → **structural 1 / fallback 1 (50/50 at n=2 placed), TP non-null 100%**; exit mix **take_profit 1 + stop_loss 1 (BE-scratch 1)** vs pre-feed stop_loss 2 — the Trigger C trade poi-001022 flipped pre-feed SL −0.3728 to a structural first-swing TP **hit +0.3852** (nearer 3486.405 target reached before the stop); the fallback F trade stayed byte-identical to pre-feed (+0.0715); routes 9 {F 8, C 1}, fills 2, trades 2 unchanged; net +0.4567 **diagnostic n=2 — NOT performance, no edge claim**. **Determinism PASS:** trades.csv + report.json byte-identical across run1/run2 (trades.csv SHA-256 `00ee227e…`). Suite **805 → 829** (24 new tests); `locked_constants.py` diff empty; SL policy unchanged. Note: `06_RESEARCH/STRUCTURAL_TP_FEED_IMPLEMENTATION_NOTE.md`.

### 2026-10-05 — Structural TP feed DESIGN LOCK (design only, no code)
- **Added** `06_RESEARCH/STRUCTURAL_TP_FEED_DESIGN.md` — normative design for feeding the existing dormant `structural_else_4ATR` branch (FR-2 R4 / C3 UNFED) with a first-swing take-profit: selector reuses the existing §19 swing machinery (`SeriesState`/`SwingIndex.last_valid` — no new detector); LONG = most recent §19-valid swing high strictly above the entry limit (SHORT mirrored), nearest-in-price with recency tie-break; search is place-time and prefix-bounded (`before = placement_bar`, confirmed swings only — lookahead-safe, no fill-time refinement); bounded to the armed POI's lifecycle (PROPOSED reuse of `poi_give_up_bars()` as pre-arm tolerance); minimum-distance guard `STRUCTURAL_TP_MIN_ATR = 0.25` (PROPOSED — named in the note only, not written to `locked_constants.py`); attachment via the EXISTING `candidate_from_route(structural_target=...)` kwarg at the existing adapter call site + `tp_source=` audit provenance; fallback (absent/invalid swing → 4×ATR) byte-for-byte unchanged; SL/BE/PureRunner/FVG-invalidation/trigger bodies explicitly untouched.
- **Design only:** no production code, no tests written, no constant written; `locked_constants.py` diff empty; LOGIC_CHANGED: NO. Success metrics for the implementation phase predeclared in the note (TP non-null 100% invariant, structural-vs-fallback share reported, dual-run byte determinism, SL paths unchanged, MFE-vs-TP-distance diagnostic only).

### 2026-10-05 — Documentation sync: post expert-charts + policy lock (docs only)
- **Synced** `SESSION_HANDOFF.md` + `POST_V1_ACTIVE_TODO.md` to the accepted state: Option B seek/scan redesign (implemented, §5a amended, suite 805); frozen funnels under the new contract — 3m (Sep–Nov 2025) armed 18 / routes 9 {F 8, C 1} / fills 2 / trades 2, 6m (Jun–Nov 2025) armed 30 / routes 10 {F 9, C 1} / fills 3 / trades 3, both diagnostic only; expert marked charts archive (11 charts, index/ledger/match note, match YES 1 · PARTIAL 9 · NO 3 · time DATA_GAP all).
- **Recorded** Lead Architect policy rulings A–E (also consolidated in `06_RESEARCH/POLICY_TP_SL_PARTIAL_2026-10-05.md`): (A) structural/first-swing TP MAY be fed via the existing `structural_else_4ATR` branch (currently UNFED) — the NEXT coding track is its design lock then implement; (B) SL remains ATR/structural — fixed 30-pip stop NOT adopted; (C) expert "30 pips" = review metric only (post-trade MAE / entry-precision yardstick); (D) PARTIAL standing guidance — WRONG never trade, CORRECT full path, PARTIAL allowed in principle with a quality tag and default degradation direction log + half risk until a dated size rule is locked (policy posture, not code); (E) pattern vocabulary gaps = research backlog.
- **Replaced** stale next markers (arming/scan contract decision, Phase D watchdog, funnel/seek follow-ups) with the single **NEXT ACTION = Structural TP feed — design lock then implement (first swing → existing structural_else_4ATR; SL unchanged; 30-pip = MAE yardstick only)**.
- **Docs only:** no `04_SRC/smc/**` edit, `locked_constants.py` diff empty, LOGIC_CHANGED: NO.

### 2026-10-05 — Expert chart archive + system match probe (read-only, diagnostic)
- **Added** `03_REFERENCE_CODE/expert_marked_charts/` (11 byte-identical copies of the operator's marked XAUUSD-VIP example charts from Downloads; originals untouched), `06_RESEARCH/EXPERT_MARKED_CHARTS_INDEX.md`, `06_RESEARCH/results/expert_marked_charts/ledger.csv` (flowchart-language inventory: W1 OB → D1 structural sweep → H4 sweep / H4 FVG → M5/M1 double top/bottom, CHOCH, Fib golden, ending diagonal → entry), and the read-only probe `06_RESEARCH/scripts/expert_chart_match_probe.py` (RapidOCR text extraction + red-marking pixel geometry; price calibration from OCR'd axis ticks).
- **Match probe vs the existing frozen structure ledger (no re-detection, nothing recomputed):** YES 1 (H4 sweep), PARTIAL 9 (TF-capped M5/M1/W1→nearest-TF or coarse annotation spans), clean NO 3 (charts 5/6 FVG zones miss by ~39.6/46.2 price units; charts 10/11 at route/entry level); **time matching DATA_GAP on every chart** — no dates readable on any image, none invented. Pattern classes the system does not emit (double top/bottom, CHOCH, Fib golden, ending diagonal, W1) disclosed as-is in `06_RESEARCH/EXPERT_CHART_SYSTEM_MATCH_NOTE.md`.
- **Policy capture (docs only, PENDING Architect ruling):** operator statements (a) TP = first swing low/high and (b) SL = 30 pips below/above small-TF entry are recorded verbatim and NOT implemented — current V1 behaviour (structural-else-4ATR TP branch UNFED; structural ± buffer/ATR SL) unchanged. No `04_SRC/smc/**` edit; `locked_constants.py` diff empty; LOGIC_CHANGED: NO.

### 2026-10-05 — Wider frozen-window funnel measurement (6 months) under the NEW seek/scan contract (diagnostic only)
- **Added** `06_RESEARCH/scripts/frozen_funnel_6m_new_contract.py` — extension of the 3-month funnel harness (same import composition, no fork) for the Lead Architect's wider diagnostic window: M1 load 2025-05-01, exec 2025-06-01→11-30 (35,725 M5 bars; the D1/H4/LTF/Stage3 pack window), fail-loud on missing data. Same harness instrumentation (posture log on `arm_at`, FR-4 wrap restored in `finally`), same determinism byte-check + comparison anchors.
- **Results (run1; run2 semantically identical):** funnel 2,979 HTF batches (0 errors) → 43,004 merged (96,015 raw) → 2,021 pillar-pass → **30 armed (28 M8; H4 19/H1 6/D1 5)** → 501 scans → **10 routes {F 9, C 1}** → 4 placed (all TP-carrying) + 7 R9 intents (3 placed, 0 expired) → **3 fills → 3 trades**. **Posture mix: CLEAN_ARM 30 / IN_ZONE 0 / VIOLATION 0** — the pillar-filtered armed population arms clean across all 6 months; the non-CLEAN posture branches remain exercised only by the suite (25 tests) and the pack-window replay. **Exit mix: stop_loss 3 (BE-scratch subset 1)**; TP non-null 100% (4/4 placed); entry anchors: `zone_edge_reanchor` 2 / `absent` 1 (the C fill — honest). **Net P/L diagnostic −3.2117, n=3 — NOT performance.**
- **Determinism PASS:** `trades.csv` + `report.json` **byte-identical** across run1/run2 (SHA-256 match); semantic funnel equal. No `04_SRC/smc/**` edit; `locked_constants.py` diff empty. Report: `06_RESEARCH/FROZEN_FUNNEL_6M_NEW_CONTRACT_REPORT.md`; artifacts `06_RESEARCH/results/frozen_funnel_6m_new_contract/`.

### 2026-10-05 — Frozen-window funnel measurement under the NEW seek/scan contract (diagnostic only)
- **Added** `06_RESEARCH/scripts/frozen_funnel_new_contract.py` — dual-run funnel + trade-outcome measurement on the FROZEN Phase 4 window (M1 load 2025-08-01, exec 2025-09-01→11-30, 17,840 M5 bars) via the Phase 3 composition **imported, not forked** (the redesign is measured by running it — no strategy code patched). Harness instrumentation (FR-4 wrap pattern, restored in `finally`): posture log on `arm_at`, route/trigger counters, pillar first-failure histogram. Extra artifacts per run: `posture_log.json`; wrapper `summary.json` with determinism byte-check + comparison anchors.
- **Results (run1; run2 semantically identical):** funnel 1,488 HTF batches (0 errors) → 20,898 merged → 839 pillar-pass → **18 armed (15 M8; Phase 4 baseline 17/14)** → 256 scans → **9 routes {F 8, C 1}** (baseline 8, all F — **the +1 is a Trigger C route, the first in product history**, reachable only because the seek now runs to the give-up deadline) → 2 placed (both TP-carrying) + 6 R9 intents (1 placed) → **2 fills → 2 trades**. **Posture mix: CLEAN_ARM 18 / IN_ZONE 0 / VIOLATION 0** — the product-path armed population on this window arms clean; the posture machinery is live and logged (pack-window replay remains the evidence for the other postures, M1 78.33%). **Exit mix: stop_loss 2 (BE-scratch subset 1)**; TP non-null rate 100% (2/2 placed); entry anchors: `zone_edge_reanchor` 1 / `absent` 1 (honest). **Net P/L diagnostic −0.3013, n=2 — NOT performance.**
- **Determinism PASS:** `trades.csv` + `report.json` **byte-identical** across run1/run2 (SHA-256 match); semantic funnel equal. Suite **805 passed** (unchanged); `locked_constants.py` diff **empty**; no `04_SRC/smc/**` edit. Report: `06_RESEARCH/FROZEN_FUNNEL_NEW_CONTRACT_REPORT.md`; artifacts `06_RESEARCH/results/frozen_funnel_new_contract/`.

### 2026-10-05 — §5 locked-doc amendment: seek/scan contract (docs only)
- **Amended** `LOCKED_DECISIONS.md` §5: new subsection **§5a — Seek/Scan Contract (amended 2026-10-05, Lead Architect Option B)** records the acceptance (design note + implementation note paths, suite 805, M1–M5 accepted incl. the M1 78.33% residual), declares the prior **one-touch +1** seek behaviour **superseded**, and states the implemented contract normatively: arming unchanged; three postures (`CLEAN_ARM` / `IN_ZONE_AT_ARM` / `VIOLATION_AT_ARM`); scan opens at arm for every posture; arm-bar presence is initial presence, NOT a §5 first-touch terminator; REVALIDATION routes only after zone re-entry via `market_reentered_zone` (fail-closed on warm-up ATR); span stays `[arm, arm + poi_give_up_bars()]`; terminators = give-up / violation-after-live-scan / one-shot route; one-shot identity unchanged; **no numeric threshold or constant changed**. The §5 state machine (states, atomic transitions, terminal semantics, §23 unfilled expiry) is explicitly declared UNCHANGED. Cross-references updated: §21 (Model 8 entry rules) and §22 (Demand/Supply freshness rules) now point to §5a.
- **Docs-only:** no `04_SRC/smc/**` edit, `locked_constants.py` diff empty, suite unchanged (**805 passed** — docs cannot affect tests, verified once), `LOGIC_CHANGED: NO`.

### 2026-10-05 — Seek/scan contract redesign IMPLEMENTED + MEASURED (Option B) (`06_RESEARCH/SEEK_SCAN_CONTRACT_REDESIGN_DESIGN.md`, rules R1–R5): `smc/orchestration/engine.py` gains `SeekPosture` (`CLEAN_ARM`/`IN_ZONE_AT_ARM`/`VIOLATION_AT_ARM` classified at `arm_at(..., arm_candle=)`) and `feed_bar` now skips the ARM CANDLE for non-CLEAN postures (initial presence / deferred violation — the arming candle belongs to the HTF structure) with a REVALIDATION continuation rule (pre-re-entry adverse close = arm-bar condition continued, dies at give-up; post-re-entry adverse close terminal as before); `smc/backtest/pipeline_adapter.py` `_may_route` replaced — a §5 TESTED state no longer closes the scan (seek runs to the give-up deadline; Trigger D preserved by its own expiry), REVALIDATION routes only after zone re-entry via the existing named rule `market_reentered_zone` (R7 band, adapter ATR, **fail-closed on warm-up ATR** — disclosed deviation from the R7 place-guard's dormancy, a route gate must not be vacuously satisfiable), re-entry latch moves the scan cursor to the re-entry bar, give-up retirement applied to every posture; one-shot identity untouched. Clarification ruled pre-implementation: `IN_ZONE_AT_ARM` needs NO re-entry gate (design R2.2 governs; only `VIOLATION_AT_ARM` is gated). One existing test assertion updated to the design (touched POI no longer pruned on the touch+1-window basis); no assertion weakened.
- **Measured (M1–M5, same frozen window/inputs as the accepted packs; `06_RESEARCH/scripts/seek_scan_impl_measurement.py`, artifacts `06_RESEARCH/results/seek_scan_implementation/`, double-run byte-identical):** **M1** OPEN_SCAN share 0.76% → **78.33%** (206/263; F-only 81.86%) — **below the ≥80% target by 5 rows, reported not tuned**; residual 100% attributed (`routed_earlier` 27 = one-shot success, `never_reentered_arm_violation` 17, `violation_after_live_seek` 13); **M2** PASS — both previously routed rows route again at the same bars; **M3** PASS — median(completion − last_scanned) for previously-CLOSED rows **0.0 bars** (was +10), 204/261 now visible; **M4** PASS — armed 668=668 with 0 arm-bar mismatches, routes 2 → 196 pre-pillar (29.34% of armed, below the 50% selectivity alarm), route mix F159/A21/B8/E6/C4; **M5** PASS — 0 multi-route episodes. Postures: IN_ZONE_AT_ARM 484 / VIOLATION_AT_ARM 182 / CLEAN_ARM 2.
- **Tests:** new `test_seek_scan_contract.py` (25: postures, arm-bar skip, touch-not-terminator incl. give-up boundary, REVALIDATION block/allow/latch/fail-closed-ATR/dead-episode, one-shot, locked constants); full suite **780 → 805 passed**, zero regressions. `locked_constants.py` diff **empty**; trigger A–F + state-machine diffs **empty**.
- **Follow-up required (recorded, not acted on):** Architect decision on M1 = 78.33% vs the 80% target (design's own rule: decision point, not a tuning trigger); `LOCKED_DECISIONS.md` §5 amendment (seek-window clause) must accompany acceptance. No expectancy/PnL/edge claims (pre-pillar visibility only).

### 2026-10-05 — Seek/scan contract redesign DESIGN LOCK (Option B — design only, no code)
- **Added** `06_RESEARCH/SEEK_SCAN_CONTRACT_REDESIGN_DESIGN.md` — the Lead Architect Option B DESIGN LOCK note, written BEFORE any production code. Restates the two measured failure modes with exact counts (in-zone-at-close: 199/263, first_touch == arm, effective seek span [arm, arm+1]; violation-at-arm: 62/263, scan never opens) and defines the redesign as normative rules R1–R5: arming unchanged + three-posture initial classification (`IN_ZONE_AT_ARM` / `VIOLATION_AT_ARM` / `CLEAN_ARM`); scan opens at arm in every posture; REVALIDATION posture routes only after zone re-entry via the existing `market_reentered_zone` named rule; scan span = the unchanged `[arm, arm+20]` give-up computation; terminators = give-up / violation-after-live-scan (terminal, unchanged dead-thesis behaviour) / one-shot route; §5 one-touch becomes seek-bookkeeping (touch no longer ends the seek; one-shot identity, §23/§24 expiry semantics untouched); 4 rejected alternatives (fixed N-bar extension, gate removal, horizon raise — banned, spray entries); success metrics M1–M5 for the later implementation phase (OPEN_SCAN share 0.76% → target ≥80% with reason split for every still-hidden row, the 2 routed rows remain routable at the same bars, median(completion−scan_close) ≤ +2, armed-count invariant, one-shot invariant machine-checked, 50% selectivity alarm as review trigger); implementation surface preview (engine seek-posture field + adapter `_may_route` replacement + REVALIDATION gate; detectors/pillars/triggers A–F/risk/fill/TP-SL/locked_constants all out of scope); risks & residuals (stale-zone visibility accepted, ghost-route mitigations already frozen, §5 locked-doc amendment required at implementation ruling).
- **Design-only engagement:** no `04_SRC/smc/**` edit (production code changed: NO), `locked_constants.py` diff empty, suite untouched by this engagement (780 baseline stands), no expectancy/PnL/edge claims. `LOGIC_CHANGED: NO`.

### 2026-10-04 — Stage 3 lifecycle timing audit (arm / first-touch / scan-close vs completions, identification only)
- **Added** `06_RESEARCH/scripts/stage3_lifecycle_timing.py` — joins all 263 Stage 3 completions to their parent HTF structures (accepted H4/D1 packs, same loader rules as the Stage 3 pack) and recovers `structure_close / arm / first_touch / scan_close (last open bar + pop/retire event) / completion` timestamps from the accepted instrumented §5 replay (the accepted pack's route replay + gate bookkeeping — no invention). Ledger `events_lifecycle.csv` (263 rows × 23 columns: timestamps, 4 bar deltas, 4 minute deltas, bucket) + `summary.json` (bucket counts, type×bucket, null-safe distributions, sanity, limitations) + 3 illustrative charts (one per populated bucket, existing Stage 3 render helper, lifecycle facts in caption).
- **Buckets:** **OPEN_SCAN 2 (0.76% of all / 0.98% of F)** · CLOSED_TOUCH 199 · CLOSED_VIOL 62 · NEVER_ARMED 0 · DATA_GAP 0 · unclassified 0 · causal-order violations 0. The 2 `route_would_form=yes` rows land in OPEN_SCAN (sanity PASS); counts reproduce the accepted funnel (199 first-touch+1 / 62 violation) via an independent classification path; recomputed inventory = 263.
- **Distributions (M5 bars):** OTHERS completion−scan_close p25 4.5 / median **10** / p75 13.5 (n_used 199, n_null 62); completion−first_touch median 11.0; OPEN_SCAN rows complete exactly on the last open scan bar (delta 0); **median completion−scan_close = 10 (all) / 10 (F)**; every completion 2–20 bars after structure close (locked `poi_give_up_bars()=20` horizon).
- **Structural observations:** arm coincides with structure close in bar terms for all 263 rows (11 weekend rows arm at the first tradable bar); `first_touch == arm` for 199/199 touch-closed structures (effective seek span `[arm, arm+1]`); all 62 violations fire on the arm bar (scan never opens — nulls by rule); no completion occurred while a scan was open beyond the 2 routed rows.
- **Verified:** new `test_stage3_lifecycle_timing.py` (8 tests: bucket assignment incl. UNCLASSIFIED residual, percentile determinism, join completeness, routed→OPEN_SCAN, sums=263, causal order, locked windows); full suite **772 → 780 passed**, zero regressions; double-run CSV **byte-identical**, summary identical; `locked_constants.py` diff empty.
- **Read-only wrt decisions:** no `04_SRC/smc/**` edit, no §5/§23/§24 widening, no new thresholds/filters, no what-if reruns, no expectancy/PnL/edge claims; report decision inputs (keep contract / redesign seek / further F filter) stated as observations only. `LOGIC_CHANGED: NO`. Report: `06_RESEARCH/STAGE3_LIFECYCLE_TIMING_REPORT.md`; results: `06_RESEARCH/results/stage3_lifecycle_timing/`.

### 2026-10-04 — Stage 3 trigger visibility + conversion audit (identification only)
- **Added** `06_RESEARCH/scripts/stage3_trigger_visibility.py` — two-pass Stage 3 inventory over the frozen window (exec 2025-06-01 → 2025-11-30 UTC, warm-up 2025-03-01): Pass 1 = instrumented copy of the accepted §5-mirrored pre-pillar replay (verified to reproduce the LTF pack's same 2 routes) with per-structure scan-lifecycle gate stats; Pass 2 = one `SeriesState(M5)` per bar, **all matrix-eligible triggers evaluated directly** in each accepted structure's `[close, close + poi_give_up_bars()=20]` window, **every completion recorded ungated** (visibility, not routing). Ledger `events_stage3_triggers.csv` (263 rows, exact 14-column schema) + `summary.json` (incl. `route_funnel`) + 36 chart panels.
- **Counts:** **263 completions {A:31, B:17, C:4, D:0, E:7, F:204}**; counts_by_tf {M5:263, M1:0}; with-htf-link 263 / without 0 (scan universe = accepted packs, by construction, disclosed); 232/668 structures ≥1 completion; detector links 15,350 → 263 (**1.71%**) → 2 routes (**0.08%** of links); route funnel 261 suppressed after scan close (**199 first-touch +1 gate, 62 zone violation**) + **2/2 in-scan routed**, zero anomalies (`scanned_not_routed=0`, `suppressed_other=0`, `not_probed=0`).
- **Honest zeros:** D = 0 (frozen `engulfer.volume < engulfed.volume` vs all-zero volume column — A5 ruling, structurally unreachable); M1 = 0 (triggers never read timeframe; product wires them to M5 only).
- **Charts** 36 panels (30 trigger: type-seeded earliest-of-each-type + even-in-time spread, all 5 present types June→November, entry/stop/completion/BOS/OB/peak/diagonal-terminal/wave-Fib geometry, plain-title + subtitle + `Stage 3 trigger visibility — NOT a trade claim` footer; 6 negative examples = top detector activity with zero completions): `06_RESEARCH/results/stage3_trigger_visibility/charts/`.
- **Verified:** new `test_stage3_visibility_pack.py` (10 tests, incl. pure `classify_route_funnel` bucketing); full suite **762 → 772 passed**, zero regressions; double-run CSV **byte-identical**, summary identical; `locked_constants.py` diff empty.
- **Read-only wrt decisions:** no locked_constants/pillar/trigger/risk/TP-SL edits, no trigger count tuning, no new thresholds/filters; existing triggers reused in evaluation/scan mode only; `LOGIC_CHANGED: NO` (no `04_SRC/smc/**` edit). Report: `06_RESEARCH/STAGE3_TRIGGER_VISIBILITY_REPORT.md`; results: `06_RESEARCH/results/stage3_trigger_visibility/`.

### 2026-10-04 — LTF confirmation pack (structure / confirmation identification, identification only)
- **Added** `06_RESEARCH/scripts/ltf_confirmation_pack.py` — accepted H4 pack (658 raw) + D1 subset (10) as HTF source; stage-0 (`DetectionDriver.stage0`) on M15 (17,788) and M5 (53,358) bars over the same exec window (2025-06-01 → 2025-11-30 UTC, warm-up 2025-03-01); per-bar router replay mirroring `PipelineAdapter.generate_candidates` (`arm_at`/`feed_bar`/`scan_route`, **pre-pillar** — `route_would_form` disclosed as pre-pillar observation); ledger `events_ltf_confirmation.csv` (15,352 rows, exact 15-column schema) + `summary.json` + 39 chart panels.
- **Counts:** 668 structures (ob 177 / ds 307 / fvg 184) · stage0 M15=13,474 M5=37,015 · links retest 6,889 / inside 3,083 / below 2,700 / above 2,680 · **activity 624 / silent 44** · **trigger mix `{"F": 2}`** (both relation=inside) · 1 structure cross-referenced to an actual product route (outside the 100-min window, honestly noted) · sample **13 = 7 active + 6 silent, 39 panels** (interleaved selection, caps ≤12/≤8/≤40 honored).
- **Fixed (script-local, four defects found while building)** — (1) dual/conflict gates computed **per source pack** (cross-TF geometric tie H4 `evt-6a8455eea149` ≡ D1 `evt-bbf35c6dc170` is not a dual emission of either pack; first run failed dual=1 on it); (2) look-ahead + arm anchored at origin bar **CLOSE** (H4 +4h / D1 +24h, clamped to series and exec end) — the open-anchored window self-linked forming sub-bars (active=668/silent=0); (3) activity = zone-interacting link (`retest`/`inside`) or own trigger — above/below links recorded but not counted; (4) selection interleaves active/silent classes so both appear under the 40-panel cap.
- **Verified:** look-ahead M5=20 (`poi_give_up_bars()`=TRIGGER_A_EXPIRY, LOCKED §24) / M15=7 (`ceil(20×5/15)`), same rule every structure; new `test_ltf_confirmation_pack.py` (8: selection determinism/caps/interleave, plain-tag contract, look-ahead consistency, pinned constants); full suite **754 → 762 passed**; double-run CSV **byte-identical**, summary identical; `locked_constants.py` diff empty.
- **Changed (render only)** — `06_RESEARCH/scripts/generate_d1_poi_pack.py:171` subtitle now reads the row's real `detection_tf`/`chart_tf` (was hardcoded `D1 | D1`); H4 pack re-run: charts corrected, CSV **byte-identical**.
- **Read-only wrt decisions:** no locked_constants/pillar/trigger/risk/TP-SL edits, no new selection thresholds or quality filters, no PnL/expectancy/win-rate/edge claims, no F-timing/Monte Carlo; `LOGIC_CHANGED: NO` (no `04_SRC/smc/**` edit). Report: `06_RESEARCH/LTF_CONFIRMATION_REPORT.md`; note: `06_RESEARCH/LTF_CONFIRMATION_NOTE.md`; results: `06_RESEARCH/results/ltf_confirmation/`.

### 2026-10-04 — H4 POI identification pack (structure confirmation, identification only)
- **Added** `06_RESEARCH/scripts/h4_poi_confirmation.py` — mirrors the D1 pack on H4 (exec 2025-06-01 → 2025-11-30 UTC, warm-up 2025-03-01, M1 parquet → `resample_multi`): raw **658** collapsed `_zones` rows (ob 177 / demand_supply 304 / fvg 177), merged **3**, armed **0**; **dual_exact_bounds_count = 0, direction_conflict_count = 0, origin_tight_violations = 0**; every row detection_tf/chart_tf = H4. Plain tags `ORDER BLOCK (H4)` / `DEMAND ZONE (H4)` / `SUPPLY ZONE (H4)` / `FAIR VALUE GAP (H4)` / `MERGED POI (H4)` / `ARMED POI (H4)`.
- **Charts** 55 PNGs (0 armed + stratified raw ≤15 OB + 15 demand + 15 supply + 10 FVG, ts-spread, cap 60 not reached), `render_d1_chart` visual language, `001…` ts-ordered: `06_RESEARCH/results/h4_poi_confirmation/charts/`.
- **Fixed (script-local, two defects found while building)** — (1) rolling validation windows now require end ≥ EXEC_START (pre-exec first-seen anchoring of deduped geometries had emptied the merged layer despite live M8 results); (2) merged/armed `event_id`s derive from geometry instead of `POI.id` (`uuid4()`, run-random — smc/core/poi.py:32) → double-run **byte-identical CSV + summary**.
- **Verified:** new `test_h4_poi_pack.py` (4 tests); full suite **750 → 754 passed**, zero regressions; `locked_constants.py` diff empty. Armed = 0 documented: all 3 merged rows failed Pillar 1 zone_refinement ("naked level") — batch re-validation cannot reproduce formation-time arming (same as D1; no threshold relaxed).
- **Read-only wrt decisions:** no pillar/trigger/RiskEngine/TP-SL/lot/spread/threshold edits; no new models or tags; no expectancy claims; human CORRECT scoring not run. Report: `06_RESEARCH/results/h4_poi_confirmation/H4_POI_CONFIRMATION_REPORT.md`; note: `06_RESEARCH/H4_POI_CONFIRMATION_NOTE.md`.

### 2026-10-04 — F1/F2 M8 emission fix: episode uniqueness + origin-tight verdict (identification only)
- **Added** episode collapse in `M8HtfDemandSupply._zones` (shared-bounds key; winner by kind priority ob > demand_supply > fvg, then LONG-first, then earliest origin; chronological yield) + `M8_KIND_PRIORITY` / `collapse_episodes` exports; new `POI.m8_kind` winner-kind field (logging/identity only) propagated through `merge_overlapping`.
- **Measured, not changed, for F2:** ob/demand_supply zones equal origin-candle ranges exactly (bit-stable); FVG gaps definitional; width cap rejected as invented selection (would violate §22 full-range rule). Origin-invariant regression tests added instead.
- **Verified:** 13 new tests (`test_m8_episode_uniqueness.py`, `test_m8_zone_width.py`); full suite **737 → 750 passed**, zero regressions; pre-existing M8/merge tests unweakened. `locked_constants.py` diff empty.
- **D1 re-sample** (`06_RESEARCH/scripts/d1_f1f2_resample.py`, same window/warm-up/seam as audit pack): 137 raw rows, 2 merged, 0 armed (batch re-validation rejects on Pillar 1 — documented, not hidden); **dual_exact_bounds_count = 0, direction_conflict_count = 0, origin_tight_violations = 0**; 20 charts. Note: `06_RESEARCH/F1_F2_M8_EMISSION_FIX_NOTE.md`; results: `06_RESEARCH/results/d1_f1f2_resample/`.
- **Read-only wrt decisions:** no pillar/trigger/RiskEngine/TP-SL/lot/spread/threshold edits; no new models or tags; no expectancy claims. Armed-quality re-score proceeds on the audit's original 6 armed charts.

### 2026-09-25 — Human-readable flowchart labels on the review charts and both PDFs (presentation/export only)
- **Changed (presentation only)** — the review surface now speaks **reviewer language instead of engine vocabulary**. The 44 charts were re-rendered with plain titles (`LIQUIDITY SWEEP | H1 | 2025-06-01 22:00 UTC | LONG`, `ORDER BLOCK (M8 HTF)`, `DEMAND ZONE (M8 HTF)`, `SUPPLY ZONE (M8 HTF)`, `FAIR VALUE GAP (FVG)`, `ARMED POI (PASSED VALIDATION)`, `LTF CONFIRMATION (M5 ENTRY, TRIGGER F)`, `ENTRY FILL`) into the NEW folder `06_RESEARCH/results/structure_ledger_6m/review_sample_v2/` (same file names, original `review_sample/` left byte-untouched, self-contained `review_gallery_v2.html`, run record `relabel_manifest.json`), and both PDFs were rebuilt so every chart title, caption, index column, tally table and per-event rubric row leads with the plain tag. Tooling: `06_RESEARCH/scripts/flowchart_labels.py` (**the shared one-source-of-truth label map, imported by both the chart renderer and the PDF builder so the two cannot drift**), `relabel_review_charts.py` (new), `build_expert_pdfs.py` (updated).
- **Added** the mandatory **SETUP CHAIN** block on every `route_ltf` / `fill` chart and caption (12 charts): `FLOWCHART STAGE` → `HTF structure` (armed POI → merged/confluence POI with model tags + zone TF, **or the explicit line that no sweep / FVG event id is linked in the row**) → `LTF confirmation` (M5 trigger letter + time + the runner's own detail text, e.g. `BOS at bar 3425; first touch of origin OB at bar 3427`, plus the route row when the fill's route is in the pack) → `Entry` / `Original SL` (+ anchor) → "This chart is the lower-timeframe entry step, not the HTF sweep itself." Engine vocabulary is **demoted, never dropped**: one small `technical row:` footnote on the chart, a two-line technical record in the PDF caption.
- **Added** `06_RESEARCH/results/structure_ledger_6m/HUMAN_LABELS_NOTE.md` (label map, honesty rule with measured counts, the set-up-chain contract with a worked example, where the charts live, how to verify presentation-only) and a new **"How to read flowchart tags"** page as **§2 of the expert pack** plus **§1.4 of the full report**. The expert pack's per-event rubric, tally table and chart index are all keyed to the plain tag (the engine word kept in a second column for traceability).
- **Honesty rule (binding on this surface):** a label is emitted only when the row itself supports it — `kind=ob` → Order block, `kind=demand_supply` + direction → Demand / Supply zone, `kind=fvg` → Fair value gap, anything else → **"unlabeled POI"**; level words come from `level_type=`, pool words from `pool=`, trigger letter from `trigger` / `route_id`. **No OB / FVG / supply-demand label and no row-to-row link is ever inferred from geometry, price action or proximity.** In the sampled pack 8/8 `poi_raw` rows carry a code kind (ob ×4, demand_supply ×4), so 0 rows needed the unlabeled fallback here.
- **Re-verified after the rebuild:** 24 charts embedded in `EXPERT_VALIDATION_PACK.pdf` (34 pp, 2.654 MB) and 44 in `STRUCTURE_LEDGER_FULL_REPORT.pdf` (56 pp, 4.672 MB); all images **1820×910 native resolution (no downsampling)**; **0 out-of-frame placements, 0 overlaps, 0 hyperlinks** (image placement + pairwise-overlap now parsed from each page's content stream and recorded in the manifest's `read_back`), A4 portrait, contents page numbers stable (24 / 29 entries via the two-pass self-check).
- **Independently re-verified:** the relabelled charts were re-checked by `verify_review_pack.py` itself (new `--png-dir` / `--out` options keep the canonical matrix intact) against the same locked rules + pixel-presence checks — **44/44 PASS, 0 failures, the same 3 documented flags** (`verification_matrix_v2.json`; flags byte-equal to the canonical set: `evt-687f151bf74a` retain_window drop, `evt-58f48dec66f2` + `evt-06e8f6501c55` zone-entry divergence). The chart *pixel classes* changed only in magnitude (the axes box is shorter), never in which classes are present — the verifier's presence thresholds are met with wide margin. Layout is now **1 chart per page** — the plain reading block plus the mandatory chain block need the room — so the earlier 2-per-page code-vocabulary PDFs are superseded (not deleted); the measured `images_per_page` distribution is recorded in `pdf_build_manifest.json`.
- **Read-only:** no threshold / pillar / trigger / zone-band / R7 / R9 / locked-constant change, no detection re-tuning, no paper trading, no edge language. `events.csv` is byte-identical (SHA-256 `903e5a3b401ce30812f5fce69831fc1d9cac7930d3bd0636dec4cc5b89acc063`) and `04_SRC/**` untouched. **LOGIC_CHANGED: NO.** Next: re-share **only the expert pack** with validators for CORRECT / PARTIAL / WRONG / UNCLEAR tallies.

### 2026-09-25 — Structure identification ledger + expert validation PDFs (research artifacts; docs/measurement only)
- **Added** the 6-month structure identification ledger over the LOCKED window 2025-06-01→2025-11-30 (2 tiled 3-month chunks, 35,725 M5 bars, 0 batch errors, **13,247 unique events**; funnel 31 armed / 10 routes / 2 fills): `06_RESEARCH/results/structure_ledger_6m/` (`events.csv` + `events.jsonl`, `summary.json`, 44 stratified `review_sample/` PNGs, self-contained `review_gallery.html`, `verification_matrix.json` = 44 PASS / 0 failures / 3 documented flags, `REVIEW_INDEX.md`), report `06_RESEARCH/STRUCTURE_IDENTIFICATION_LEDGER_REPORT.md`, tooling `06_RESEARCH/scripts/{structure_identification_ledger,verify_review_pack,build_expert_pdfs}.py`.
- **Added** shareable expert PDFs with the charts **embedded** (reportlab, native-resolution image XObjects, zero external file links): `06_RESEARCH/results/structure_ledger_6m/EXPERT_VALIDATION_PACK.pdf` (20 pp, 24 priority charts, blank verdict lines) and `STRUCTURE_LEDGER_FULL_REPORT.pdf` (32 pp, all 44 charts), plus `EXPERT_VALIDATION_PACK.md` text twin. **Status = awaiting external CORRECT / PARTIAL / WRONG / UNCLEAR scoring.**
- **Read-only:** no threshold / pillar / trigger / zone-band / R7 / R9 / locked-constant change, no detection re-tuning, no paper trading, no edge language (**LOGIC_CHANGED: NO**). The merge cross-row link repair (48 rows marked `rel_dangling`, all warm-up cases) and the byte-identical re-run were tooling-only; strategy code untouched.

### 2026-09-24 — V1.1 RUNTIME BASELINE FREEZE (docs-only)
- **Added** `00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md` — frozen implementation baseline: Choice 1 Product Runtime Unification (Phase 0 contract, C1 MultiTFProductRuntime in live+paper, Phase 2 layer contracts, Phase 3 structure funnel, Phase 4 byte-identical frozen 3-month backtest) + Track A (E1 entry_anchor export DONE, C3 UNFED_DESIGN_ONLY, C4 news/sweep DEFERRED + spread WIRED) + Phase D HTF probe PASS (EXNESS Copy DEMO, H4/H1/D1=300 bars, dry_run loop clean). **NOT part of the freeze as edge:** expectancy, PF, live profitability, trigger mix beyond observed F-heavy routes, structural TP feed, news calendar, sweep_level feed.
- **Freeze semantics:** allowed without a new ruling = Phase D ops (watchdog EA attach + emergency drill, stability logging), contract-restoring bugfixes, docs. Requires a dated ruling = locked_constants changes, pillar/trigger/zone/R7/R9 edits, F-timing/Monte Carlo, structural TP invention, treating demo PnL as idea validation, dry_run=false campaigns.
- **Docs-only:** `SESSION_HANDOFF.md` (phase = V1.1 RUNTIME BASELINE FROZEN; next = watchdog attach + drill or dated ruling), `POST_V1_ACTIVE_TODO.md` (V1.1 freeze checked; next marker = watchdog GUI attach + stale-heartbeat drill), pointer line in `PRODUCT_RUNTIME_CONTRACT.md`; stale next-action markers (Choice-1 review / Track A accept / HTF probe) marked superseded. **No 04_SRC change; suite 737 read-only verified; locked_constants diff empty.** Default posture after freeze: operate and observe under contract.

### 2026-09-24 — Phase D: HTF product-runtime probe on the EXNESS Copy terminal (ops PASS)
- **Added** `06_RESEARCH/scripts/phase_d_htf_probe.py` — bounded ops probe on the ONLY permitted terminal (identity gate → product HTF probe → optional degraded smoke → 60 s dry_run loop → artifacts). Operator config `config/live_demo.json`, magic 20260919, `dry_run=true` throughout; **zero strategy change, zero smc/ source change** (suite 737 unchanged).
- **Result: PASS.** Identity MATCH (DEMO 474608655 @ Exness-MT5Trial15, XAUUSDm, Algo Trading ON); product-mode HTF probe: **H4=300 / H1=300 / D1=300 bars** via the same `copy_rates` path the live batches use, `missing_series=[]`, `LiveLoop.start()` compliant with contract §3.4; degraded smoke stamped `degraded=True` + reason (never silent); dry_run loop 60 s / 120 polls / 0 unhandled errors / clean shutdown.
- **Probe-script fix disclosed:** `copy_rates` returns a numpy record array — `raw or []` raises 'truth value of an array is ambiguous'; probe now uses `list(raw) if raw is not None else []`. Probe-script-only.
- **Watchdog EA attach remains BLOCKED** (GUI-only; stale-heartbeat drill still pending).
- **Added** `PHASE_D_DIVERGENCES.md` §9 (HTF product probe) + artifacts `06_RESEARCH/results/phase_d_htf_probe/` (`identity.json`, `probe_summary.json`, `events.log`, heartbeat). Infrastructure proof only — NOT strategy validation, NOT edge evidence.

### 2026-09-24 — Track A residual engineering: E1 entry_anchor export + C3 design ruling + C4 silent/deferred dispositions
- **E1 DONE (export completeness, logging-only):** `entry_anchor` is now a first-class field end-to-end on the trade path — `candidate_from_route` extracts `signal.data["entry_anchor"]` (string-only; absent/None stays unknown, never invented) → `CandidateEntry.entry_anchor` → `PendingOrder` → `BacktestPosition` → `TradeRecord` → `export.to_csv` **appended column** (backward compatible, old order untouched) + `to_json` key. Also remains inside `signal_data_json` (inspector ease). `modify_sl` copies it verbatim (same placement-geometry invariant as `original_sl`, enforced by test). Paper `_TrackedPending`/`_TrackedPosition` carry it pending → position. Modules touched: `smc/backtest/{pipeline_bridge,runner,orders,positions,reports,export}.py`, `smc/paper/runner.py` — identity/export plumbing only, zero decision change.
- **C3 UNFED_DESIGN_ONLY (design note written BEFORE any code):** `06_RESEARCH/RESIDUAL_A_E1_C3_C4_NOTE.md` §C3 locks the V1 ruling — a valid structural TP must be (a) emitted by a trigger under an explicit frozen key, (b) finite + strictly favorable, (c) derivable from objects the route already carries. Survey confirmed NO trigger emits a structural target (`TriggerSignal.data` = fvg/bos_index/ob_index/entry_anchor/wave5/rsi only; liquidity levels never attached to routes); feeding one would require inventing target-selection logic (banned). `resolve_take_profit` structural branch stays wired, tested, dormant; TP remains the frozen 4×ATR fallback (FR-2 R4). No new constants.
- **C4 dispositions (contract table appended):** `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` §8 Silent/deferred policy table — News §11 **DEFERRED** (no calendar ingestion; `news_events=[]` diagnostic), Spread §28.5 **WIRED (operator input)** — `spread_price` threaded end-to-end into `effective_max_spread` grading; value is operator-supplied, Sweep guard **DEFERRED** (guard + plumbing dormant; no trigger emits a sweep level — none invented), Structural TP **DESIGNED/UNFED**, entry_anchor **EXPORTED**. Standing statement recorded: shipped configs with `news_events=[]` / `spread_price=0.0` remain diagnostic, NOT "gates proven live".
- **Added** tests `04_SRC/tests/test_residual_a_e1_entry_anchor.py` (11: bridge extraction incl. non-string guard + decision-identity invariance, order→position flow, modify_sl preservation, from_closed carry, CSV/JSON export) and `06_RESEARCH/RESIDUAL_A_E1_C3_C4_NOTE.md` (E1 record + C3 design + C4 table). 2 assertions in `test_identity_patch.py` updated for the appended CSV column (append-only contract).
- Suite **726 → 737 passed**; **no decision-logic change, no locked-constant edit** (`locked_constants.py` diff empty).

### 2026-09-23 — Phase 4: frozen backtest + paper dry path on the unified machine (Choice 1 COMPLETE)
- **Added** `06_RESEARCH/scripts/phase4_unified_backtest.py` — dual frozen run over the LOCKED 3-month window (exec 2025-09-01→11-30, M1 warm-up 2025-08-01) via the **imported Phase 3 composition** (product seam `MultiTFProductRuntime.run_batch` → `PipelineEngine` arm → `PipelineAdapter` scans → `BacktestRunner` risk/R9 intents; no diag flags; no forked code).
- **Frozen measurement (run1 = run2 semantically):** 1,488 HTF batches (0 errors) → 45,122 raw → 20,654 merged → first failures P2:fail 18,050 (86.9%) / P3:fail 1,084 / P1:fail 755 → 765 passed → 748 duplicates suppressed → **17 armed (14 M8)** → 208 scans → **8 routes (all Trigger F, 7/8 M8)** → 1 placed (TP 1/1) + 6 R9 intents armed (1 placed) → **1 fill: BE-scratch +0.0715 raw (diagnostic only, n=1 — a wiring result, not a performance result)**.
- **Determinism: `trades.csv` + `report.json` BYTE-IDENTICAL across run1/run2** (SHA-256 7b3e8659… / 37f0568b…); funnel semantic-equal. Machine-verdict inside `results/phase4_unified/summary.json`.
- **Paper dry-run wiring smoke DONE (no MT5 dependency):** `PaperRunner.arm_multi_tf` on a real-data slice — 1 batch, degraded=False, 0 dry-run sends, runtime is the shared `MultiTFProductRuntime` (`paper_dry_note.json`).
- **Added** `06_RESEARCH/PHASE4_UNIFIED_BACKTEST_REPORT.md` (module graph, funnel table, n=1 honesty section, October reference row, residuals: entry_anchor export, HTF depth, paper R9 depth, single-window scope).
- **CHOICE 1 PROGRAM COMPLETE (Phase 0→4 all PASS).** Suite **726 passed** unchanged; **no production-logic change, no locked-constant edit**. Next-action authority returns to the Lead Architect.

### 2026-09-23 — Phase 3: structure funnel + information-flow audit (Choice 1 sequence)
- **Added** `06_RESEARCH/scripts/phase3_structure_funnel.py` — locked-window funnel on the PRODUCT multi-TF path: `MultiTFProductRuntime.run_batch` (C1 seam) at new-H1-close cadence → `PipelineEngine` arm → `PipelineAdapter` scans → `BacktestRunner` risk/placement (FR-4 wiring). Pillar histogram via a `validate_multi` wrapper (Phase-2 composition, restored in `finally`); scan/bridge counters via the FR-4 instrumentation pattern; R9 intent telemetry from the runner's `IntentBook` event log.
- **Funnel (locked window 2025-10-01→10-31, full month, 6,324 M5 bars, 527 HTF batches, 0 errors):** detected 15,687 raw (H4 7,696 / H1 7,991) → 7,564 merged → first failures P2:fail 6,549 / P3:fail 418 / P1:fail 339 → 258 passed → 250 duplicates suppressed → **8 armed (5 M8)** → 100 scans → **4 routes (all Trigger F, 4/4 M8)** → 1 placed (TP present) + 3 R9 intents armed (1 placed) → **1 fill** (M8 poi-008910, zone-high re-anchor 4244.725).
- **Sample audit:** `sample_audit.csv` 8/8 armed POIs (full armed set), ZERO flow gaps — zone bounds / model_tags / pillar_path / displacement present on every armed row; routed row carries entry + original_sl + TP. `entry_anchor` honestly `n/a:not_exported`.
- **Determinism:** run1 vs run2 semantic funnel counts IDENTICAL (only tag + runtime seconds differ).
- **Added** chart helper `phase3_funnel_charts.py` → 6 armed-POI geometry charts (`results/phase3_structure_funnel/charts/`; routed POI labeled with entry/SL/TP; others labeled NO FILL).
- **Added** `06_RESEARCH/PHASE3_STRUCTURE_FUNNEL_REPORT.md` (composition, funnel table, P2-dominance explanation, sample findings, low-route honesty, Phase 4 residuals).
- Suite **726 passed** unchanged; **no production-logic change, no locked-constant edit**.

### 2026-09-23 — Phase 2: layer/pillar contract tests (Choice 1 sequence)
- **Added** `04_SRC/tests/test_phase2_layer_contracts.py` — 28 machine-checkable contracts: Stage 0c detectors (D-SWEEP-1/0 wick-pierce + close-back; D-FVG-1/0 classic 3-candle imbalance; D-DISP-1/0 BOS + directional FVG + magnitude vs hard-fail), Pillars 1–5 semantics (P1 naked-level FAIL; P2 UNAVAILABLE→reject fail-fast + FAIL tokens incl. `missing BOS` / `missing directional FVG` / `displacement < 0.5`; P3 §6 sole-ownership gate; P4 strict 1-touch; P5 SOFT — 70% modifier never rejects), and cross-layer handoffs (H-MERGE tag-union/widest-zone/earliest-id; H-ATTR latest-same-direction-wins + omitted-key honesty end-to-end to Pillar 2 rejection; H-ROUTER single-route chronological smoke + determinism).
- **Added** population snapshot `06_RESEARCH/scripts/phase2_contract_population_snapshot.py` → `06_RESEARCH/results/phase2_contracts/snapshot.json` (14-day multi-TF window via per-TF `DetectionDriver.validate_window`; READ-ONLY counts, no PnL): detected 1,294 → merged 946 → **82 passed**; first-failure histogram **P2:fail 797 (84.3%)** · P1:fail 37 · P3:fail 30.
- **Added** `06_RESEARCH/PHASE2_LAYER_CONTRACTS_NOTE.md` (contract-ID → node-id map, stable reason tokens, snapshot analysis, 5 documented gaps NOT fixed).
- Suite **726 passed** (698 + 28), zero regressions; **no production-logic change, no locked-constant edit** (`locked_constants.py` diff empty).

### 2026-09-23 — Architect as-coded comparison (Part 2 verdict) + owner "Choice 1" program (docs decision record)
- **Recorded** the Lead Architect's as-coded-vs-Rev-5 comparison verdict (Part 2 of the architecture extraction — **do not re-debate**): modules largely match the stage list, but **runtime wiring does not fully match** the intended multi-TF live cascade.
  - **Gap C1** — live/paper ≠ research multi-TF (two drivers over one detection stack).
  - **Gap C2** — HTF cadence / M8 D1-H4 map still largely caller-owned.
  - **Gap C3** — structural TP never fed (4×ATR fallback only).
  - **Gap C4** — news / spread / sweep-guard / some constants compiled but silent in shipped configs.
  - **Aligned:** limit-only fills, R7/R9 research path, pillars, router, models on disk.
- **Recorded** the owner-accepted program sequence **"Choice 1"** (BINDING order — do not reorder): Phase 0 `PRODUCT_RUNTIME_CONTRACT.md` → Phase 1 / C1 (MultiTF into live + paper + shared HTF seam + loud HTF fail) → Phase 2 layer/pillar CONTRACT tests → Phase 3 short structure funnel / information-flow audit (1–3-month multi-TF research path) → Phase 4 frozen backtest + paper on the unified machine.
- **Status of the gaps after Phase 0/1 (2026-09-23):** **C1 CLOSED** by the one multi-TF runtime (live/paper now call the shared seam — see the entry below); **C2 PARTIAL** (the seam now owns cadence for live/paper; the frozen research scripts still own theirs); **C3 OPEN**, **C4 OPEN** (both declared V1 non-goals).
- **Docs-only** — no file under `04_SRC/` touched; suite unchanged (698).

### 2026-09-23 — Phase 0 + Phase 1 C1: one multi-TF product runtime (live = paper = research)
- **Added** `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` (Phase 0) — canonical runtime (H4+H1 detection required, M5 execution, one batch per new H1 close), the **one-driver rule** (all three paths call the same seam), loud-fail policy (missing HTF raises; no silent single-TF in product mode; explicit test-only `allow_single_tf_degraded`), non-goals (no ADX/ATR-floor, Trigger D, structural TP, Redis, locked-constant edits) and the acceptance-test list.
- **Added** `smc/orchestration/multi_tf_runtime.py` — the shared seam: `MultiTFProductRuntime` (`run_batch`, `build_htf_prefixes`, `missing_series`), `ZoneDedup` (the research chain's geometric episode rule, now shared — POI ids are uuid4 so identity alone cannot dedup), `MissingHtfSeriesError`, `MultiTFBatchReport`. Facade only: delegates to the frozen `MultiTFDetectionDriver.validate_multi`; forwards D1+H4 into M8's map when supplied (declared superset of the frozen research auto-share).
- **Changed** `smc/live/loop.py` — LiveLoop now provisions HTF series from the connector (bounded `htf_window_bars`, injectable `htf_fetch`) and dispatches **one batch per new H1 close** through the seam; `start()` performs an HTF probe and refuses to start in product mode without usable H1/H4; refused batches record `arm_errors`/`last_arm_error` and arm nothing (no fallback); the pre-C1 single-TF path survives only as logged legacy mode for the Phase 7 tests.
- **Changed** `smc/paper/runner.py` — `PaperRunner.arm_multi_tf(...)` delegates to the same runtime (auto-constructed in product mode); explicit `runtime=` injection supported.
- **Changed** `smc/live/operator_config.py` / `run_operator.py` / `operator_console.py` — operator config gains `detection_timeframes` + `allow_single_tf_degraded` (whitelist intact; detect==exec is rejected unless degraded is explicit); the session builds the runtime; board + events.log report HTF batches/armed/arm-errors at H1 cadence.
- **Added** 17 tests `04_SRC/tests/test_multi_tf_product_path.py` (loud-fail, degraded stamping, prefix/disorder, dedup rule, structure+arming on synthetic HTF, arm-once/dedupe, D1→M8 forwarding, live cadence + start gate + degraded start, paper delegation, operator-config validation). Suite **698 passed** (681 + 17), zero regressions; **no locked constant, pillar, trigger, R7/R8/R9 or zone-band change**.
- **Added** parity smoke `06_RESEARCH/scripts/c1_multi_tf_parity_smoke.py` → `06_RESEARCH/results/c1_multi_tf_parity/run1/summary.json`: exec 2025-10-01→10-15 (2,761 M5 bars, 27 s), 231 H1 batches → 8/49 passed → **5 armed**, **52 duplicate zones suppressed**, 0 errors; live-vs-paper per-TF counts identical; loud-fail + degraded probes pass; LiveLoop dispatch `1` batch over 60 bars; the smoke ran twice (`run1`/`run2`) with IDENTICAL funnel/parity/loud-fail/degraded/dispatch fields.
- **Added** `06_RESEARCH/C1_MULTI_TF_PRODUCT_PATH_NOTE.md` (before/after call graph, public API, HTF provisioning per path, smoke numbers, test map, 7 residuals).

### 2026-09-23 — As-coded architecture extraction (Part 1 of 3; research-only)
- **Added** `06_RESEARCH/AS_CODED_ARCHITECTURE_FLOWCHART.md` — the architecture THE CODE ACTUALLY IMPLEMENTS: package tree from AST docstrings (118 modules), stage map 0A→5 with file/class/function citations, end-to-end Mermaid runtime + state-owner Mermaid, call-graph notes, config defaults that shape behavior, and the compiled-but-silent/optional evidence table (14 rows). Explicitly separated §G "NOT INFERRED FROM DOCS"; comparison vs Rev 5 and the 6-month ledger are NOT started.
- **Added** `06_RESEARCH/scripts/render_as_coded_architecture.py` (matplotlib only, headless) → `06_RESEARCH/results/architecture_audit/as_coded_architecture.png` + `as_coded_bar_loop.png`.
- **Added** `06_RESEARCH/scripts/build_module_inventory.py` (AST scan) → `06_RESEARCH/results/architecture_audit/module_inventory.json` (classes, public functions, `locked_constants` imports per module, import-reference classes: 112 smc-referenced / 5 tests-only / 1 unreferenced).
- **Evidence highlights (code-only):** research chain drives `MultiTFDetectionDriver` (H4+H1 on new-H1-close batches) while `smc/live/loop.py` drives single-TF `DetectionDriver`; `multi_tf.py` has NO smc-module importer; 7 locked constants are never imported anywhere (ADX_MIN_ENTRY, ATR_FLOOR_MIN_SL, EQUILIBRIUM_MIN/MAX, M8_MIN_RR, M8_SL_MIN/MAX_PIPS); no trigger emits a `sweep_level`; FVG invalidation applies to Trigger-F trades only; `smc/logging/` is a placeholder; `PipelineEngine.execute_route` is not called by any runner.
- **No strategy change:** no file under `04_SRC/smc/` edited; suite **681 passed** (unchanged).

### 2026-09-22 — R9 place-on-reentry intent (Lead Architect ruling; design locked before code)
- **Added** `00_LOCKED/R9_PLACE_ON_REENTRY_DESIGN.md` — locked semantics BEFORE implementation: §23 clock parity, DOA boundary (remaining < 3 bars never fabricated), one intent per route with immutable clock, candidates-before-intents bar order, one-shot burns only at intent placement.
- **Added** `smc/backtest/intents.py` — `PlaceIntent` + insertion-ordered `IntentBook` (deterministic lifecycle ARMED→PLACED|EXPIRED|REPLACED|DROPPED_POI|DROPPED_PORTFOLIO; machine-readable event log + counters).
- **Added** `market_reentered_zone` in `smc/risk/fill_regime_policy.py` — band re-entry via the existing R7 guard OR limit touch mirroring the locked fill-model rule (cross-checked against `limit_filled` by test).
- **Changed** backtest runner + paper runner — R7 skip arms an intent (retryable, one-shot unburned); shared single placement path `_place_accepted` (immediate + intent placements byte-identical); re-entry step after the candidate step (same-bar re-proposal supersedes — never two orders for one route; own test caught the double-order defect in the first wiring pre-run); Friday/news/POI-violation drops mirrored; paper dry-run records but never sends.
- **Added** 23 tests (`test_r9_place_on_reentry.py`: immediate place / arm-not-place / band + touch-only re-entry / natural expiry / DOA boundary / dedupe + clock immutability / REPLACED + one-shot burn once / R8 + `ZONE_REFINEMENT_ATR` unchanged / paper mirrors). Suite **681 passed** (658 + 23).
- **Added** smoke `results/r9_smoke/run1/` (frozen FR-4b window, capturing-runner patch restored in `finally`): funnel identical (6 routes) → 5 intents armed, 4 expired naturally (September runaway class — now counted waits), **1 placed on re-entry → FILLED at the on-zone limit 4247.355 → BE-managed → closed +0.07** — first complete arm→reentry→fill→manage→close chain under frozen rules (n=1, M8).
- **Added** `06_RESEARCH/R9_PLACE_ON_REENTRY_NOTE.md` + `FOUNDATION_RESET_PLAN.md` §8 R9 entry. Governance updated (SESSION_HANDOFF, POST_V1_ACTIVE_TODO, CHANGELOG).

### 2026-09-22 — R7+R8 fill-regime policy (Lead Architect ruling implemented)
- **Added** `smc/risk/fill_regime_policy.py` — single source for both rulings: `zone_place_allowed` (R7: existing FR-3 band only; fail-safe defaults), `rest_bars_for` (R8: H1→36, H4/M8/D1→48, else execution-TF §23 default), give-up backstop helper.
- **Changed** backtest runner + paper runner — R7 guard before place (machine-readable `skip_place_far_from_zone`, retryable: one-shot burns only on accepted placement); R8 per-order rest_bars on PendingOrder/_TrackedPending under the §23 inclusive convention; give-up (20) an independent backstop that never shortens HTF rest; `detection_tf`/`is_m8` provenance threaded bridge → orders → paper.
- **Added** 33 tests (`test_fill_regime_r7_r8.py`: R7 geometry/retryability/dormant/fail-closed, R8 table + inclusive expiry + give-up independence, paper mirror, `ZONE_REFINEMENT_ATR`-unchanged assertion). Suite **658 passed** (636 + 22 net).
- **Added** smoke `results/fr7r8_smoke/` (FR-4b window, frozen config): funnel identical, 10 R7 skips / 0 places / 0 fills; independent geometry verification (market close at place time +14.65..+165.50 beyond zone vs band 1.73..3.84); R8 proven live in the superseded intermediate (limit-ref) run — first filled trade in the chain. Residual for the D1/D2/D3 ruling documented; nothing tuned; GATE_WIDENED=NO.
- **Added** `06_RESEARCH/FR_FILL_REGIME_R7_R8_NOTE.md` + `FOUNDATION_RESET_PLAN.md` §8 policy record. Governance updated (SESSION_HANDOFF, POST_V1_ACTIVE_TODO, CHANGELOG).

### 2026-09-22 — FR-4b unfilled-order forensic (facts only, no strategy change)
- **Added** `06_RESEARCH/scripts/fr4b_unfilled_forensic.py` — logging-only recording order book (byte-identity cross-check vs run1), §23-exact live-window touch analysis mirroring fill_model semantics, post-expiry horizon scan.
- **Added** `06_RESEARCH/results/fr4b_wider/unfilled_forensic.{csv,_summary.json}` + `06_RESEARCH/FR4B_UNFILLED_FORENSIC_REPORT.md` — fates 3 never-touched-in-life / 2 touched-only-after-expiry (both M8: +26/+121 bars; ticket-5 closest approach 4.43 units) / 0 anomalies; all orders re-anchored LONGs expired at N+11 exactly.
- **Updated** governance: SESSION_HANDOFF, POST_V1_ACTIVE_TODO, CHANGELOG.

### 2026-09-22 — FR-4b: wider fidelity window (post-FR-3.1, measurement only)
- **Added** `06_RESEARCH/scripts/fr4b_wider_window.py` — thin wrapper over the FR-4 baseline (window args, pass-through FR-3 gate recorder, exit/anchor-mix post-processing from trades.csv).
- **Added** `06_RESEARCH/results/fr4b_wider/run{1,2}/` + `06_RESEARCH/FR4B_WIDER_WINDOW_REPORT.md` — 3-month frozen run (2025-09→11): 21 armed (15 M8) → 6 F routes (gate 6/0) → 5 placed (TP 5/5) → 0 fills (§23 window vs proximal-edge retrace, flat book); determinism pair byte-identical; M8 chain 15/4/0; no parameter search.
- **Updated** governance: SESSION_HANDOFF, POST_V1_ACTIVE_TODO, CHANGELOG.

### 2026-09-22 — FR-3.1: on-zone entry anchor for Trigger F (gate untouched)
- **Changed** `smc/triggers/trigger_f_bos_ob.py` — resting limit anchored into the routed POI zone via the new shared helper (`zone_anchored_entry`, direction-proximal edge; on-zone behavior bit-identical); stop reference follows the anchor (zone distal edge on re-anchor); degenerate zero-SL-distance guard; `entry_anchor` provenance in signal data.
- **Added** `smc/triggers/base_trigger.py::zone_anchored_entry` (pure; no tolerance widening) + 14 tests (`test_fr31_zone_anchored_entry.py` incl. M8 fixtures); `test_fr3_zone_m4.py` off-zone-reject test superseded with documented policy change. Suite **636 passed**.
- **Added** `06_RESEARCH/FR3_1_ON_ZONE_ENTRY_NOTE.md` (old/new rule table, re-anchor-vs-clamp rationale, smoke: October 0→2 routes, gate rejects 2→0, 0 fills within expiry) + `results/fr31_smoke/` artifacts; FR-4 fate ledger re-verified byte-exact.
- **Updated** governance: SESSION_HANDOFF, POST_V1_ACTIVE_TODO, CHANGELOG.

### 2026-09-22 — FR-4 residual closeout: armed-POI fate ledger (forensics only)
- **Added** `06_RESEARCH/scripts/fr4_armed_poi_fate.py` — read-only replay of the frozen FR-4 October window with logging-only observation shims (scan counter, trigger evaluate wrappers, FR-3 gate pass-through recorder); byte-identity + funnel-parity gates vs run1.
- **Added** `06_RESEARCH/results/fr4_fidelity/armed_poi_fate.csv` + `armed_poi_fate_summary.json` — all 8 armed POIs classified: 2 same-bar TESTED, 3 tested-after-arm, 3 never touched; 0 built-then-rejected; FR-3 gate rejects = 2 (poi-002480, poi-005293 — entry +43.78 / +16.50 above zone high; diag no-gate trades map 1:1 to these POIs/bars).
- **Added** `06_RESEARCH/FR4_ARMED_POI_FATE_REPORT.md` — ledger table, fate/TF pivots, M8 subsection, built-vs-scanned answer; no parameter changes.
- **Updated** governance: SESSION_HANDOFF, POST_V1_ACTIVE_TODO, CHANGELOG.

_No pending changes._

---

## [2026-09-21] — FR-4 fidelity re-baseline (post-reset October month)

### Added
- **`06_RESEARCH/scripts/fr4_fidelity_baseline.py`** (new): M1→M5/H1/H4/D1 resample, M5 bar loop, HTF batch detection per H1 close, ZoneRegistry dedup, deterministic POI ids, scan/route/TP/M8 counters, armed-fate tracking, `--diag-no-zone-gate` ablation flag (diagnostic-only).
- **Library (additive):** `MultiTFDetectionDriver.validate_multi(..., return_details=True)` for arm/feed callers; per-TF passed/results/displacement maps without re-deriving.
- **Report:** `06_RESEARCH/FR4_FIDELITY_BASELINE_REPORT.md` (+ `results/fr4_fidelity/run1|run2/`, diag in `results/fr4_diag_nogate/`).

### Measured
- Determinism pair byte-identical (trades/report/summary ex-runtime); funnel 9363 detected → 209 passed → 8 armed (4 M8) → 130 scans → 0 routes, explained (zone gate binding per ablation: 2 F+M8 routes → 2 TP placements → 2 SL closes); M8 armed, TP path placed-only in diag; Trigger D 0; flat book.
- Verdict YES_WITH_RESIDUALS; Phase C archived pre-reset and incomparable.

### Fixed (script-side, found by the work)
- Counting bridge wrapper dropped new `candidate_from_route` kwargs — would have crashed the first routed run; fixed before any evidence run depended on it.

### Notes
- No thresholds, displacement, pillars, lot caps, or Monte Carlo touched; suite **622 passed**; 2–3 month stretch skipped with documented rationale.

---

## [2026-09-21] — FR-3 zone/entry geometry + M4 fidelity

### Added
- **Entry↔zone containment** `entry_within_zone()` in `triggers/base_trigger.py`, enforced in `BosObContinuationTrigger` (± frozen 0.5×ATR; far-outside routes rejected, merge untouched by documented choice).
- **M4/M5 domain split** in `m4_quasimodo.py`: head must clear the frozen EQH tolerance (equal-peak structures stay M5/M7 domain).
- **Tests:** 4 new (`test_fr3_zone_m4.py`) + marginal-head decoy; 3 fixture updates (zones now meaningful); suite **622 passed**.

### Notes
- No thresholds invented (frozen §13/§2 only); B/C untouched; A/D/E containment unmeasured (residual); post-FR-3 books NOT comparable to Phase C (FR-4 measures).

---

## [2026-09-21] — FR-2 structural SL/TP routing (R4/R5 implementation)

### Added
- **Shared SL helper** `structural_sl()` + `context_atr()` in `triggers/base_trigger.py` with interim `FR2_SL_BUFFER_ATR=0.3` / `FR2_TP_ATR_MULTIPLE=4.0` (marked pending formal § lock, pinned by test).
- **Buffered stops** on F/A/D/E raw-edge references (B/C wave stops exempt with documented FR-3 rationale).
- **TP routing** `resolve_take_profit()` in `pipeline_bridge.py` (structural-if-valid else 4×ATR); adapter feeds honest-prefix ATR; paper carries TP unchanged.
- **Tests:** 10 new (`test_fr2_sl_tp_routing.py`); 3 stale raw-edge assertions updated to buffered expectations.

### Notes
- No thresholds, displacement, pillars, lot caps, or Monte Carlo touched; suite **617 passed**; F-timing/M4 untouched (FR-3); post-FR-2 books NOT comparable to Phase C (documented — full measurement is FR-4).

---

## [2026-09-21] — FR-1 multi-TF cascade restoration

### Added
- **`smc/data/resample.py`** (new): deterministic M1→M5/H1/H4/D1 aggregation (UTC bins, present-bars-only gaps, loud disorder).
- **`smc/orchestration/multi_tf.py`** (new): per-TF frozen drivers (H4+H1), shared D1/H4 M8 map, per-TF counts, `single_tf_detect_exec` flag, loud missing-series failure with explicit degraded opt-in.
- **`tests/test_multi_tf_cascade.py`** (new, 11 tests): resample exactness, feed shape, spy-proven non-M1 detection, M8 wired emission, alarm both ways, arm-bars wiring.
- **`06_RESEARCH/scripts/fr1_multi_tf_smoke.py`** (new): real-data wired path with M8 loud-fail gate; smoke PASS (41k M1 bars, M8 × 12).

### Notes
- No thresholds, trigger geometry, risk logic, or constants touched; suite **607 passed**; per-bar loop integration explicitly residual (documented, not hidden).

---

## [2026-09-21] — FR-0b Foundation Reset plan (docs-only)

### Added
- **`00_LOCKED/FOUNDATION_RESET_PLAN.md`** (ACTIVE): problem statement from QA pack; immediate stops; rulings R1–R6 verbatim (M8 wired, H4+H1 detection, M5 execution, structural-TP/±0.3ATR-SL for FR-2, F-research gated on FR-4); FR-0→FR-4 phases; FR-1 hard exit criteria incl. M1-only alarm; non-goals; derived success definition (labeled as derivation); next = FR-1 prompt after acceptance.
- Handoff/TODO/roles synced: FR-0b status, next action = FR-1 prompt (plan acceptance pending), role protocol §4 plan pointer now points at the new file.

### Notes
- Docs-only — no strategy code, thresholds, scripts, or backtest logic touched; no pytest delta claimed; no FR-1 code started; no rulings invented.

---

## [2026-09-21] — Lead Architect role protocol added (docs-only)

### Added
- **`00_LOCKED/LEAD_ARCHITECT_ROLE_AND_PROTOCOL.md`** (ACTIVE/BINDING): role boundaries (Lead Architect / local agent / owner), binding source-of-truth order, anti-drift rules with CODED|WIRED|OBSERVED|DRIFTED|SILENT|DEFERRED taxonomy, 5-step verification protocol, report contract, startup order, cloud-mirror note. Foundation Fidelity Reset restated as active program.
- Handoff/TODO/roles synced: role-protocol pointer + FR-0→R1–R3-rulings next action; short card marked superseded-for-detail; TODO checkbox closed.

### Notes
- Docs-only — no strategy code, thresholds, or backtest logic touched; no pytest delta claimed.

---

## [2026-09-20] — Operator console: startup banner + quiet cadence

### Changed
- **Startup banner** `04_SRC/smc/live/operator_console.py` (`render_startup_banner`, ASCII-only): one-shot ASCII-art "SMC BOT" header with identity facts, printed once after identity PASS and mirrored to `console_mirror.log`.
- **Identity line shortened** `04_SRC/smc/live/run_operator.py`: console shows one human line (mode/login/server/symbol/magic/dry_run); full JSON stays in `identity.json` + `events.log`.
- **Quiet cadence** `config/live_demo.json`: `console_refresh_s` 5.0 → **900.0** (first board prints immediately at session start, then every 15 min; adjustable via the same key — heartbeat 1 s, poll 0.5 s, and all backend logs unchanged).
- **Tests:** 2 new banner tests in `tests/test_operator_pack.py`; full suite **582 passed**.

### Notes
- Ops tooling only — no strategy changes, no threshold tuning, no locked constant touched.

---

## [2026-09-19] — Phase D operator pack (run surface for controlled demo/live testing)

### Completed
- **Launcher** `run_live.bat` (repo root): cd to project root, config + entrypoint + python existence checks with clear failure messages, passes `config/live_demo.json` explicitly, window stays open on failure; no venv exists (documented — system Python 3.11.9).
- **Mutable operator config** `config/live_demo.json`: terminal_path (EXNESS Copy), symbol XAUUSDm, magic 20260919, **dry_run true**, require_demo true, risk_fraction 0.01 (validated against the LOCKED RISK_PCT band 0.5–1.0 %), M5, heartbeat 1 s, poll 0.5 s, console 5 s, log_dir `logs/phase_d`.
- **Strict config loader** `04_SRC/smc/live/operator_config.py`: whitelist-only keys; unknown keys rejected (typo protection); **LOCKED keys (spread gate, lot cap, BE, breaker, trigger geometry, freshness/expiry, …) rejected loudly** with the offending names; risk_fraction band-checked; terminal-dir normalization (`normalize_terminal_dir`) for identity comparisons. Tests for all rejections + band edges.
- **Operator entrypoint** `04_SRC/smc/live/run_operator.py`: load config → validate → `mt5.initialize(path=...)` → **prove identity before the loop** (dir match; abort on mismatch or non-DEMO when require_demo) → stack wiring exactly per Phase 7 tests (PipelineEngine/Adapter + RiskEngine + Order/PositionManagers + LiveLoop + HeartbeatPublisher, dry_run honored) → poll loop with per-poll state hook → console boards every `console_refresh_s` → backend logs → Ctrl+C/`--max-seconds` clean shutdown with heartbeat `shutdown` marker. Board fields: time, terminal/server/account/demo, symbol, dry_run, heartbeat seq/age/state, last bar, spread, ATR, gate pass + per-grade ceilings (display only — the RiskEngine enforces the real gate), candidates/blocked/placed/cancelled/rejects, open positions, KPI counters, error tail.
- **Pure console renderer** `04_SRC/smc/live/operator_console.py` (n/a-degrading, unit-tested without a terminal).
- **Backend logging** in gitignored `logs/phase_d/`: `identity.json`, `config_effective.json` (raw config archived), `events.log` (append-only), `console_mirror.log`, `kpi_records.jsonl`, `session_summary.json`, `heartbeat.txt`. No secrets anywhere. `.gitignore` += `logs/`.
- **Tests:** `04_SRC/tests/test_operator_pack.py` — 15 focused tests (config load/rejections, normalization, renderer with fake state, logger artifacts); **no live terminal required**; full suite **580 passed**.
- **Live smoke test on the ONLY permitted terminal (market closed, idle session):** identity PASS (DEMO 474608655 @ Exness-MT5Trial15), 3 boards rendered, heartbeat seq 1→11 + clean shutdown marker, spread 0.260 sampled, 0 errors; artifacts verified on disk. Note: `trade_allowed=true` — Algo Trading has been enabled on this terminal since session 1.

### Notes
- Ops tooling only — no strategy changes, no threshold tuning, no locked constant touched. Config may tune ONLY the whitelisted operational fields; `smc.config.locked_constants` remains the single source of truth for every risk/strategy quantity.

---

## [2026-09-19] — Phase D opened: demo/paper ops-validation session 1 (EXNESS Copy terminal only)

### Completed
- **Terminal binding + identity gate:** read-only probe `06_RESEARCH/scripts/phase_d_identity_check.py` binds to the ONLY permitted terminal `C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe` (dir-identity MATCH, abort on mismatch/REAL): **DEMO** login 474608655 @ Exness-MT5Trial15 (USD, 1:2000), symbol resolved **XAUUSDm** (visible; digits 3, point 0.001, filling FOK+IOC, volume 0.01–200 step 0.01). PHASE_D_IDENTITY: **PASS**.
- **Watchdog EA deployed + compiled:** `SMC_Safety_Watchdog.mq5` copied into the terminal's `MQL5\Experts\` and compiled via metaeditor64 — **0 errors / 0 warnings** (`SMC_Safety_Watchdog.ex5`, 13,402 bytes). Heartbeat contract verified: file format matches the EA parser (line 1 `<unix> <seq>`), `is_stale` flips exactly at the 5 s timeout (4 s fresh / 6 s stale), file round-trips through the terminal `MQL5\Files` sandbox. EA attach + Algo Trading ON remain GUI steps.
- **Ops session driver** `06_RESEARCH/scripts/phase_d_ops_session.py` (identity gate → idle LiveLoop session → tick-history spread distribution → order-path checks): 2-min idle dry-run **60 polls, 0 errors, 0 new bars** (Saturday), heartbeat seq 60 + clean shutdown marker; KPI logger live-writable.
- **Order paths (payload-validated only — no sends):** BUY_LIMIT 0.10 lots @ bid−5.0, SL/TP bracketed, magic **20260919** → `order_check` retcode 0 ("Done") under FOK AND IOC; sends deferred to the open market with Algo Trading enabled.
- **Divergence log opened** `06_RESEARCH/PHASE_D_DIVERGENCES.md` — headline finding: the §28.5 spread gate is **ATR-relative**, so its bite is an ATR-regime property: live spread is CONSTANT **0.26** (Friday tick history p10=p99=max across 32,775 + 5,578 ticks), current M5 ATR ≈ 3.75 ⇒ gate passes every grade today; at every 2023 month-end (M5 ATR 0.30–1.06) the gate ceiling was 0.02–0.08 ⇒ even the live 0.26 would block ALL grades ALL of 2023 — Phase C's ladder "0 trades at 0.35" is an ATR-regime special case (`results/phase_d_ops/phase_d_gate_regime_check.json`). New scripts: `phase_d_gate_regime_check.py`, `phase_d_ops_session.py`, `phase_d_identity_check.py`.
- **Governance:** SESSION_HANDOFF / TODO / POST_V1_PLAN_OF_ACTION updated — Phase C marked CLOSED (sign-off granted), Phase D ACTIVE with deferred-to-open-market checklist.

### Deferred (market closed / GUI)
- EA attach on an XAUUSDm chart (InpHeartbeatFile=smc_heartbeat.txt, InpSymbolFilter=XAUUSDm, InpMagicFilter=20260919) + terminal Algo Trading toggle.
- Live bar-cycle validation (detect→arm→risk), demo order sends (place/cancel/SL-modify-preserves-TP/close), stale-heartbeat emergency drill, KPI decision/ack latencies under load, full-trading-day spread distribution.

---

## [2026-09-19] — Phase C executed: full 5-year baseline closeout (**CLOSED** — Lead Architect sign-off granted 2026-09-19)

### Completed
- **Dual segmented baseline COMPLETE:** run1 + run2 × 6 calendar-year segments = **1,768,123 bars each** (2021-04-12 → 2026-04-10, 77.4 h/run); `trades.csv`/`report.json` **byte-identical**, `summary.json` identical ex-runtime, all invariants OK, Trigger D = 0. Baseline (diagnostic only): 761 trades, WR 25.49 %, net −47.81 raw ≈ −4.78 % of equity, PF 0.344, maxDD 49.15; per-trigger F = 659 / B = 70 / A = 29 / E = 2 / C = 1 / D = 0.
- **Verdict re-stamp:** `phase_c_verdict.json` re-run at **09:55:10 against the final merged artifacts** (the 01:01 stamp predated the last deterministic re-merge) — criteria unchanged, **PASS**.
- **Boundary ruling implemented (option a — accept + document):** quantification added to report §7 (`phase_c_boundary_quant.py` → `phase_c_boundary_quant.json`): 0 dropped/force-closed positions at any boundary (`positions_opened` = trades exported = 761 per segment, `positions_still_open` = 0 everywhere), ±14-day boundary-window stress: 664 trades, net −39.83, PF 0.383 (shape unchanged); **0 warm-up-zone trades** in every segment (first entry past own start by +71…+2,014 bars; merge offset = own_start − 2,880 verified for all 761 trades; `route_id` unique 761/761) — the 2026-09-15 Option-B warm-up trim closed as **moot**; boundary-overlap re-merge retained as documented contingency only. No continuous-run identity claimed.
- **Spread sensitivity (SENSITIVITY-CHECK, plan §5):** 4-arm constant-spread ladder **{0.00, 0.05, 0.15, 0.35}** on 2023-02-01 → 2023-04-30 (84,470 bars, ATR-calibrated window — closest to full-series ATR p50 0.568; adequacy + cold-start note in report §8). Result: 52 → 22 → 2 → **0 trades at 0.35** (all 54 routes spread-blocked, 219 blocks); invariants OK in every arm; identical pre-spread funnel (510,095 raw → 407 armed → 54 routes) isolates spread attribution. New scripts: `phase_c_spread_calibration.py`, `phase_c_spread_sens_launch.ps1` (manifest resume); artifacts `phase_c_spread_sens_sens0p{00,05,15,35}/`.
- **`06_RESEARCH/PHASE_C_BASELINE_REPORT.md` written:** frozen config + 4 sha256 checksums, execution design, coverage/determinism/invariants, kill funnel, core + per-year + per-trigger + per-direction breakdowns, boundary ruling (§7), spread ladder (§8), runtime/equivalence (§9), anomalies (§10 — incl. LOT_MAX_SAFETY 0.10 binding 100 % of trades making risk_fraction inert, structural no-TP exit model, ATR-relative vs absolute spread regime dependence), binding interpretation (§11), exit-criteria table (§12), reproduce commands (§13).
- **Ops cleanup:** `SMC_phase_c_guard` scheduled task deleted (earlier), Startup `phase_c_guard_hidden.vbs` removed (2026-09-19); no `*SMC*`/`*phase_c*` tasks, no python processes remain. Suite re-verified: **565 passed** (from `04_SRC`).
- **Governance:** `POST_V1_PLAN_OF_ACTION.md` (§5 status line, rules 7–8), `SESSION_HANDOFF.md`, `TODO.md` updated. **Phase D remains NOT CLEARED — pending Lead Architect sign-off on the report.**

---

## [2026-09-17] — Phase C pair interruption + relaunch (checkpoint/resume verified in production)

### Verified
- **Incident:** the in-flight Phase C pair + verdict watcher died ~2026-09-16 16:45–16:47 local (logs frozen at 2024 bar 196,000/358,773). **Forensic conclusion (2026-09-17): NOT a reboot** (last boot Sep 14, single continuous session) and NOT a crash (zero WER records, no traceback) — session-level suspend/termination unlogged by Windows, proven objectively by the watcher's freeze/resume fingerprint: its log wrote [wait] ticks until 16:45, then NOTHING for ~16.75 h, then a single [abort] at 09:30 Sep 17 the instant the machine resumed — a live watcher would have aborted at ~17:45 per its 60-min stale rule. Runs did not survive the resumption; completed 2021/2022/2023 segments unaffected (manifests + artifacts on disk, byte-identical as verified 2026-09-15).
- **Relaunch (2026-09-17 ~11:50):** runner's manifest-fingerprint resume worked exactly as designed — `[resume] 2_2023 complete — loading artifacts` in both logs, then 2024 restarted at segment granularity (no intra-segment checkpoint) with correct 2,880-bar warm-up context. Watcher re-armed after one expected stale-log abort.
- **Supervisor deployed (2026-09-17, post-incident hardening):** `06_RESEARCH/scripts/phase_c_supervisor.py` + `phase_c_guard.bat` — verifies run1/run2/watcher every 5 min (PID + Windows start-time FileTime anti-PID-reuse check), relaunches dead components detached (manifest resume makes restarts cheap), force-restarts logs-silent-2 h wedges, completion-aware, single-instance lock, own audit log `phase_c_supervisor.log`. Defense in depth: scheduled task `SMC_phase_c_guard` (every 5 min) + Startup-folder copy (logon cover) + persistent pythonw daemon. **Live-fire tested: watcher killed manually → detected and relaunched within one cycle (12:38:25 [DEAD] → 12:38:28 [RELAUNCH]); scheduled task fired on time; lock held.** Cleanup after Phase C closes: `schtasks /Delete /TN SMC_phase_c_guard /F` + remove Startup copy.
- **ETA revision:** ≈ 29 h from relaunch (2024 + 2025 recompute in full) → pair completion ≈ late 2026-09-18 local. LEAD ARCHITECT OPTION B (boundary-overlap trim) ruling unchanged and still queued for completion.

---

## [2026-09-15] — Project-Wide Audit recorded (`PROJECT_WIDE_AUDIT.md`)

### Added
- `06_RESEARCH/PROJECT_WIDE_AUDIT.md` — full project-wide audit (production 13,503 LOC / 15 submodules, 69 test files / 10,401 LOC, 16 research scripts, governance layer). Critical findings C1–C3: C1 midweek year-boundary carry exposure (2024→25 + 2025→26; disposition pending Lead Architect — same finding as the perf audit), C2 segment-end open positions silently dropped from the merged trade list (no end-of-data warning anywhere), C3 paper runner = largest (681 LOC) + least-tested heavy module (~2 test files vs 8+ for backtest). Verified strengths: constants governance with test-enforced frozen values, engineered determinism, exact-equivalence Phase C perf patch, pure typed DI risk engine, explicit backtest causality guards, strict data validation, near-zero hygiene debt (0 TODO/FIXME, 0 bare asserts, 1 type: ignore, 3 justified broad excepts). Clarity items: boundary semantics lack a first-class API, stale `logging/` placeholder pointer, no coverage baseline, deferred v25 gates without decision deadline, no test→§N mapping. Ranked enhancements E1–E6: runner `finalize(end_of_data)` contract, boundary-overlap trim, paper-runner test battery, CI determinism gate, coverage baseline, stale-pointer sweep. **RE-CHECK: §7 checklist scheduled for when the 5-year Phase C baseline completes.**

---

## [2026-09-15] — Independent Phase C Perf-Patch Audit (PASS WITH FINDINGS; boundary carry documented, disposition deferred)

### Added
- `06_RESEARCH/PHASE_C_PERF_AUDIT.md` — independent read-only audit of everything after the Phase B PASS: perf patches P1–P3, the segmented 5-year runner, and the verdict machinery. 17 static equivalence claims re-derived and OK (adapter scan cursor, §24 retirement, `SeriesState` folds, inverted-space RSI, §27/§19 heap events, `SwingIndex` queries, mirror artifacts, stage0 hoists, `raw.sweeps` reuse, `WindowCache` suffix arrays, trigger/CHOCH hints, runner warm-up, deterministic merge, verdict watcher). Findings: F1 LOW-latent (`PipelineAdapter.current_atr` on a negative `bar_index` — no production caller), F2 INFO (merged ticket numbers restart per segment — POI/route ids are segment-unique). Dynamic evidence: independent suite rerun **551 passed**; 14-test fresh-seed battery (`test_phase_c_audit_equivalence.py`); Wilder fold warm-up convergence on real data (ATR bit-identical from warm-bar 510, RSI 465 — 5.6× budget headroom); year-boundary warm-up margins 5,514–6,898 bars vs 2,880 required.
- `06_RESEARCH/scripts/audit_boundary_probe.py` — standalone 3-check boundary probe (fold convergence; segment-split vs continuous on real October data; warm-up margins).

### Fixed
- `audit_boundary_probe.py` seg1 window construction — `load_frame("2025-10-06", "2025-10-14")` bounds at midnight, silently truncating seg1 at Oct 14 00:00 (1,379 bars shed) and producing a FALSE PREFIX_IDENTITY mismatch (17 vs 20 trades). Probe now uses inclusive full-day bounds (`2025-10-14 23:59`); fix disclosed in the audit. The genuine finding (CARRY_LOSS) is unaffected — it was computed on correctly built seg2/continuous windows.

### Verified
- **Boundary probe (real Oct 6–17 split at Oct 15 00:00):** CARRY_LOSS = 1 (`LONG 2025-10-15 05:32 UTC, −0.098, stop_loss`) — one continuous trade whose episode/one-shot state crossed the boundary is not taken by the second segment (the documented fresh-stack-per-segment design; REARM_DUP = 0, no phantom re-arm trades, both books flat at segment ends). Corrected re-run (`audit_boundary_probe_v2.log`): PREFIX_IDENTITY **True (20 vs 20)** with the same CARRY_LOSS = 1 reproduced identically — the false PREFIX_IDENTITY (17 vs 20) was Run 1's midnight-truncated seg1 window, and the funnel delta (placed 21+5 = 26 vs cont 27) reconciles exactly with the one missing route. **Materiality scoping:** 2021→22, 2022→23, 2023→24 year boundaries are pre-flattened by the Friday-EOD latch (2021 segment evidence: `positions_still_open=0`, `friday_eod=1`); **2024→25 (Tue Dec 31) and 2025→26 (Wed Dec 31) are midweek and exposed** — positions open at a segment end are dropped from the merged trade list (no end-of-data close; no `still_open` merge stage).
- **Audit verdict: PASS WITH FINDINGS** (self-downgraded per §5's pre-stated rule) — the downgrading finding is the documented segmentation design boundary-carry gap, NOT a patch regression; production pair verified healthy and byte-tracking throughout.
- **Production pair unaffected in-flight** (2021 segment complete and byte-identical across runs; 2022 running in lockstep). Disposition of the boundary-carry finding (accept-and-document vs boundary-overlap trim at merge) is DEFERRED TO THE LEAD ARCHITECT — options recorded in `PHASE_C_PERF_AUDIT.md` §6.

---

## [2026-09-14] — Phase B CLOSED: PASS (full-October determinism verified; report filled; marker → Phase C)

### Fixed
- `06_RESEARCH/scripts/phase_b_verdict.py` — the two checker defects behind the initial FAIL verdict: (1) the runtime-strip was top-level-only while `runtime_seconds`/`bars_per_second` live nested inside `funnel` (false summary-identity FAIL) — now strips recursively; (2) `positions_still_open = 0` (flat book at window end — an end-state, not a throughput stage) lacked a written explanation — added to the explained-zeros list. Re-run verdict: **PASS**. No stack change; both fixes disclosed in the report.

### Added
- `06_RESEARCH/scripts/phase_b_sl_first_check.py` — same-bar SL-first check (plan §4): over **ALL 41** full-October trades (stronger than the requested sample), every stop-loss exit price equals the SL exactly, zero ambiguous same-bar SL/TP bars, all exit bars present in the canonical parquet — PASS.

### Verified
- **Full-October determinism pair COMPLETE:** `phase_b_run1/` + `phase_b_run2/` (2025-10-01 → 2025-10-31, 31,619 bars each; 42,393 / 42,321 s ≈ 11.8 h per run, 0.75 bars/s): `trades.csv` + `report.json` BYTE-IDENTICAL; `summary.json` identical on every semantic field (runtime fields only differ).
- **All 7 plan §4 invariants OK in both runs** (bars non-zero, §23/§24 no-fill-after-expiry, §11 one-shot, §5 one-touch, BE once-per-trade, limit-price fills, Trigger D = 0). Machine verdict `06_RESEARCH/results/phase_b_verdict.json` = **PASS**.
- Funnel (every stage non-zero or explained): raw detections 189,284 → armed 237 → routes 49 → placed 42 → opened 41 (1 × §24 give-up expiry) → closed 41; violated_pulls 0; hard_cancelled_news 0; friday_closes 0; `positions_still_open = 0` (flat end-of-window book, explained).
- Metrics (diagnostic per plan §5 — NOT edge): 41 trades, 15 W / 26 L, WR 36.59%, net P/L −7.66, PF 0.0501, maxDD 7.66; per-trigger A=2 / B=7 / F=32 / D=0; all 41 closes are exact-SL and the 15 wins are exactly the BE-modified positions (be_modifies_applied == n_wins == 15; TP never reached in October).
- Full suite still **532 passed** after all changes.

### Changed
- `06_RESEARCH/PHASE_B_FIDELITY_REPORT.md` — all PENDING_RUN sections filled (funnel §3, metrics §4, per-trigger §5, determinism §6, §7.4 anomalies CLOSED, §9 overall **PASS — Phase B CLOSED**).
- `00_LOCKED/POST_V1_PLAN_OF_ACTION.md` — ACTIVE marker → **Phase C**; one-page fidelity note appended under §4 (BE-latch bug, quadratic scan fix with golden-check proof, fidelity signals, Phase C baseline warning); execution pointer updated.
- `00_LOCKED/TODO.md` + `00_LOCKED/SESSION_HANDOFF.md` — Phase B checklist closed with evidence; current phase → Phase C (AUTHORIZED).

---

## [2026-09-13] — Phase B perf fix: quadratic adapter scan cost found and patched; full-October pair relaunched

### Fixed
- **Quadratic per-bar scan cost (found on the live full-October run, bar ~12.5k):** `PipelineAdapter.generate_candidates` re-ran O(prefix) work for EVERY armed POI on EVERY bar — full-prefix swing detection, candle/swing inversions, RSI series, ATR series, FVG scan — so per-bar cost grew with bar index (~2.5 s/bar at bar 12.5k; first attempt projected ~2–3 days instead of ~10 h; logs stalled >45 min while burning 100% CPU; first attempt aborted, logs preserved as `06_RESEARCH/results/phase_b_oct_full_aborted{1,2}.log`). Diagnosis via py-spy on the live processes (dominant frames: `_invert_candles`/`_invert_swings`, `detect_fvgs`, `atr_series`). Fix, equivalence-preserving by construction (every trigger evaluation is a pure function of the candle prefix up to the evaluated bar; each in-window bar evaluated exactly once):
  - `smc/backtest/pipeline_adapter.py` — per-bar prefix computation hoisted out of the per-POI loop; deadline-exhausted POIs (past §24 give-up window) stop triggering scan attempts; their §5 feed continues unconditionally.
  - `smc/orchestration/engine.py` — `scan_route(..., scan_from=...)` resume parameter; the §24 deadline stays anchored to `arm_bar` (arm + 20), never shifted by the cursor.
  - `smc/triggers/trigger_router.py` — `scan` now separates the SCAN START (cursor) from the CONTEXT ANCHOR (`from_bar=arm_bar`); the cursor must never orphan a pattern from its own episode (first implementation passed the cursor as `from_bar` and Trigger A/D/E anchor checks failed — caught by the integration tests before any run was trusted).
- `06_RESEARCH/scripts/phase_b_verdict.py` — stall threshold corrected 20→45 min (20 min was under one 500-bar progress interval at the observed pre-patch rate → spurious aborts).

### Added
- `04_SRC/tests/test_adapter_scan_semantics.py` — 3 regression tests pinning the guarded-exhaustion / lockstep-cursor / arm-bar-anchor scan semantics (suite 529 → **532**, all green).
- `06_RESEARCH/scripts/phase_b_cost_probe.py` — per-window detection-cost probe across October (disproved a detection-side degradation hypothesis: `validate_window` flat ~1.35–1.62 s at every probe point).

### Verified
- **Golden check (semantics preservation):** patched code reproduces the preserved Oct 1–3 pair byte-identically — `06_RESEARCH/results/phase_b_golden_check/` vs `phase_b_oct_short_run1/`: `trades.csv` and `report.json` IDENTICAL; `summary.json` matches on every semantic field (only runtime fields differ; also ~10% faster at 4,020 bars, gain grows with bar index).

### Changed
- Full-October determinism pair (2025-10-01→31, 31,619 bars) relaunched 2026-09-13 ~09:55 local on the patched code (detached, PIDs in `phase_b_run{1,2}.pid`); verdict watcher re-armed → `phase_b_verdict.json` on completion. ETA ~7 h.

---

## [2026-09-12] — Post-V1 Phase A Complete: Data Acceptance (PASS; A5 ruled option (a))

### Added
- **Phase A artifacts (executed 2026-09-09):**
  - `06_RESEARCH/scripts/phase_a_data_acceptance.py` — read-only A1–A6 acceptance script for `07_DATA/` against the `smc.core.candle.Candle` contract (no trading logic touched).
  - `06_RESEARCH/DATA_ACCEPTANCE_REPORT.md` — full Phase A report; verdict PASS (all A1–A4/A6 checks; 1,679 gaps fully classified: weekends + NY-5pm rollover-hour omissions, no unexplained class).
  - `smc/data/parquet_loader.py` — `load_ohlcv_parquet`: the ONLY sanctioned Phase B/C input path for the canonical dataset (UTC localize-never-convert per A2, chronology enforcement, non-finite/non-positive rejection) + 6 unit tests (`tests/test_parquet_loader.py`, synthetic frames only).
- **`00_LOCKED/POST_V1_PLAN_OF_ACTION.md`** — binding post-V1 operational plan (Phases A–E). Validation executed and the A5 ruling recorded 2026-09-09; Phase A CLOSED, Phase B (Short Fidelity Backtest) ACTIVE.

### Decisions
- **A5 — option (a), recorded in plan §3 (2026-09-09):** the canonical dataset is accepted as volume-less; the Phase B/C baselines run WITHOUT Trigger D as a tradeable path (structurally unfireable: volume is 0 on all 1,768,123 M1 rows and all 281,514,283 tick rows, so `engulfer.volume < engulfed.volume` is always `0 < 0 = False`). Triggers A/B/C unaffected; vendor re-sourcing deferred until Phase C fidelity justifies it. No code change.
- **Canonical series:** `07_DATA/XAUUSD_M1.parquet` (1,768,123 M1 bars, 2021-04-12 11:00 → 2026-04-10 20:59 UTC; SHA-256 `e5d730ea…d17fee9` recorded in plan §3 A6). `07_DATA/` is git-ignored — never commit market data.

### Fixed
- `.gitignore` — dedicated local-data block (`07_DATA/`, `*.parquet`, `*.tick`, `*.ticks`) added; the pre-existing bare `data/` pattern was root-anchored to `/data/` (it had silently excluded the entire `04_SRC/smc/data/` package from version control).
- Doc sync (this session): `DATA_ACCEPTANCE_REPORT.md`, `TODO.md`, and `SESSION_HANDOFF.md` aligned to the recorded A5 ruling and Phase A closure; stale "A5 open / decision required" references replaced. No code change.

Suite: **519 → 525 passed** (`python -m pytest tests` from `04_SRC/`).

---

## [2026-09-09] — Phase 7 Complete: Live Readiness + MQL5 Safety Watchdog (V1)

### Added
- **`smc/live/` — Python live package (Option A: Python owns the brain):**
  - `config.py` — `LiveConfig` (symbol/timeframe/magic, demo-first flags, risk inputs on the single §28.7 sizing path, heartbeat/watchdog timing, detection window) + `live_config_from_dict` (timeframe coercion).
  - `heartbeat.py` — plain-text heartbeat file (`<unix_secs> <sequence>` + `state=`), atomic temp+rename writes, `HeartbeatPublisher` (interval-bounded, injected clock), `read_heartbeat`/`is_stale` (fail-closed: missing/garbage == stale), and `evaluate_watchdog` — the pure-Python decision the EA mirrors (healthy → no action; stale/unreadable → emergency). Defaults: 1 s interval, 5 s stale timeout (documented UNFROZEN operational timing, not trading thresholds).
  - `loop.py` — `LiveLoop`: connect (refuse on failure) → poll new closed bars → rolling 200-bar window → `DetectionDriver.validate_window` → arm ONLY newly-passed POIs (never re-arm; §24 anchor + §11 one-shot preserved) → `PaperRunner.run_one_cycle` over the REAL adapter/engine/risk stack → interval-bounded heartbeat. Cold start anchors history without replay; `run_once()` is the deterministic test seam; `stop()` writes a `shutdown` heartbeat (watchdog treats it like death — fail-closed).
- **`05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` — MQL5 Safety Watchdog EA only.**
  - MAY: monitor heartbeat (1 s timer, 5 s timeout vs `TimeGMT()`), emergency close ALL scoped positions + delete ALL scoped pendings on stale/unreadable heartbeat, log/alert.
  - MUST NOT: any strategy logic — no POI detection, validation, entries, PureRunner/FVG management, session/news/risk policy, sizing. Healthy heartbeat → no trading actions.
- **`smc/orchestration/detection_driver.py`** — `validate_window` extracted (Stage 0/1 → detect → merge → validate WITHOUT arming); `run` delegates and arms.
- **Tests** — `tests/test_live_phase7.py` (9): heartbeat roundtrip/freshness, fail-closed garbage/missing, sequence + clean-shutdown marker, publisher interval, watchdog decision (healthy/stale/missing), live loop over a fake connector (history anchor → new-bar cycle → heartbeat fresh → shutdown marker), start refusal, no re-arming of existing POIs, config coercion.
- Design note: `01_ARCHITECTURE/SMC_PHASE_7_DESIGN_NOTE.md` (transport + timeouts + loop structure + exact EA responsibilities + clean shutdown + manual EA validation checklist + residual risks).
- Suite: **510 → 519 passed**.

### Fixed / integrated
- The pre-Phase-7 coherence patch (CR1 detection driver, I1 single §5 state machine, I2 running equity, CR2 paper close guards, I4 retention — 510 passed) is folded into this freeze; see `SMC_PHASE_7_PREP_COHERENCE_PATCH.md`.

---

## [2026-09-09] — Phase 6 Audit Fixes (independent audit accepted)

### Fixed
- **C1 — §23/§24 unfilled-order expiry wired into the integrated loop.**
  `BacktestRunner` runs an expiry step (3c, before fills) calling
  `expired_by_section23(timeframe)` + `expired_by_give_up`; affected
  POIs are driven TESTED through the state machine via
  `PipelineAdapter.notify_order_expired`; paper cancels GTC pendings by
  age (M5 12 / M1 30 bars, §24 backstop). Resting limits can no longer
  fill past their frozen window.
- **C2 — paper fill matching by order identity linkage, not ticket
  equality.** `PositionSnapshot` now surfaces `magic`/`comment`;
  `PaperRunner._observe_fills` matches a fill to a pending on
  (symbol, magic, comment) — the fields real MT5 carries from the order
  to the position record (`POSITION_MAGIC`/`POSITION_COMMENT`); the
  position ticket is keyed separately. The false "position id equals
  order ticket" claim is retracted in the M6 note + SESSION_HANDOFF.
- **I1 — ATR/spread fed per bar in the integrated backtest path**
  (`PipelineAdapter.current_atr` on the honest prefix; spread from
  `RunnerConfig.spread_price`) so BE/spread/same-level gates are not
  silently disabled; parity with the paper runner.
- **I2 — the real `PipelineAdapter` is auto-attached by `PaperRunner`**
  (`init`), with a real-adapter composition test; POI provisioning for
  demo use documented in the M6 note.
- **I3/I5 rulings recorded** in the M4/M6 design notes (hard-cancel
  workflow survival + re-placement bounds; fill-before-entry is the V1
  rule).
- Suite: **496 → 501 passed** (2 backtest expiry tests + 3 paper tests:
  linkage fill, age expiry, real-adapter composition).

---

## [2026-09-09] — Phase 6 Complete: Backtesting & Paper Trading (V1)

### Added
- **`smc/backtest/`** — deterministic, MT5-free backtest stack (M1–M5):
  - `data_feed.py` — `CandleSeries` (single- and multi-TF feed shape,
    exact-timestamp indexing contract).
  - `clock.py` — `BarClock`: the injected `now` (strictly advancing;
    reading before the first bar raises; zero wall-clock reads).
  - `bar_loop.py` — `BarLoop` + `BarHandler` seam: ONE loop, two
    backends (backtest + later live), deterministic bar order and
    `LoopStats`.
  - `orders.py` — `PendingOrderBook`: insertion-ordered pending LIMIT
    book, deterministic tickets, §23/§24 unfilled-order expiry.
  - `fill_model.py` — limit fills AT THE LIMIT PRICE; physical SL/TP
    with the same-bar SL-FIRST rule; `CloseKind` taxonomy.
  - `positions.py` — `PositionStore`: open/close/modify with POI/trigger
    identity on every position; `ClosedPosition` trade-log records.
  - `runner.py` — `BacktestRunner`: the LOCKED per-bar order —
    `reset_day` on UTC date change → `evaluate_friday_close` once →
    `hard_cancel_pending` (§11) → per-position risk exits (FVG
    invalidation + PureRunner BE; `on_be_applied` only after a
    successful modify) → pending-limit fills + physical SL/TP → new
    entries LAST. Blocked risk verdicts place nothing. `submit_entry`
    seam (M3) + `set_pipeline_adapter` (M4) + `result()` snapshot (M5).
  - `pipeline_bridge.py` — `TriggerRoute` → `CandidateEntry` pure
    mapping: direction / limit entry / SL, §15 confluence score,
    `poi_id` + `trigger` + `route_id` ("{poi}:{trigger}@{bar}" §11
    event identity), and the bound FVG provider (Trigger F's signal FVG
    only — geometry never invented).
  - `pipeline_adapter.py` — per-bar engine drive: scan-before-feed (§5
    first-touch OK window covers the touch bar + one bar so an in-zone
    Trigger D pattern stays routable), §11 one-shot workflows (BLOCKED
    verdicts re-submit the SAME candidate without consuming; §24 expiry
    or POI VIOLATED retires the workflow and cancels the resting limit),
    no-lookahead prefix scans.
  - `reports.py` / `export.py` — `build_report(RunnerResult)`: trade
    list, win rate, gross/net P/L, profit factor (zero-loss case →
    explicit `None`, never inf), max drawdown on the closed-trade equity
    curve, per-trigger + per-POI breakdowns (`unattributed` when
    identity is absent), blocked-entry counts by reason, empty-run
    defined zeros; deterministic CSV + JSON export (`sort_keys`).
- **`smc/paper/`** — paper trading over the live execution layer (M6):
  - `runner.py` — `PaperRunner`: the same locked bar order applied
    bar-close driven; implements the M4 adapter seam directly
    (`submit_entry` / `on_candidate_accepted` /
    `cancel_pending_for_poi`) so the identical `PipelineAdapter` drives
    backtest AND paper; broker-truth observation (fill = pending ticket
    appears as a position; close = tracked position disappears);
    `on_trade_opened` on fill; `on_be_applied` ONLY on a confirmed
    modify; dry-run flag; refuses to start when
    `connector.initialize()` fails.
  - `broker_adapter.py` — thin `OrderManager`/`PositionManager`
    boundary: place-limit (§10 limits only), close (opposite DEAL),
    cancel; SL modify re-sends the untouched TP (post-audit rule at the
    execution layer); raises nothing — returns success/latency outcomes
    measured with the injected `perf` source.
  - `kpi_logger.py` — append-only structured KPI records (decision,
    order_ack, management, fill, trade_closed, missed_bar, hard_cancel,
    friday_close) with INJECTED timestamps only; derived `counters()`;
    deterministic JSON/JSONL/CSV exports. NO pass/fail threshold engine
    (Future Flexibility Clause thresholds are not frozen — metrics
    logged only).
- **Design notes** — `01_ARCHITECTURE/SMC_PHASE_6_M4_DESIGN_NOTE.md`,
  `SMC_PHASE_6_M5_DESIGN_NOTE.md`, `SMC_PHASE_6_M6_DESIGN_NOTE.md`
  (alongside the phase-level `SMC_PHASE_6_DESIGN.md`).
- **Tests** — M1–M6 suites including pipeline-integration (9), reports
  (14) and paper (15) files — **496 tests total passing**
  (`python -m pytest tests` from `04_SRC/`); suite progression 458 (M3
  accepted) → 467 (M4) → 481 (M5) → **496 (M6)**.

### Binding decisions honored (Phase 6 constraints)
- Fill AT THE LIMIT PRICE; same-bar SL-first on physical closes.
- Injected `now` only — bar clock in backtest, bar timestamps + injected
  `perf` monotonic source in paper; no wall-clock reads.
- Pure `RiskEngine` (decisions only); `PipelineEngine` finds/validates/
  routes; runners/stores apply.
- A blocked risk verdict places nothing and consumes nothing — the POI
  one-shot survives (I2 parity across engine, adapter and paper runner).
- Single sizing path (§28.7 policy band + `LOT_MAX_SAFETY` cap) in both
  runners; no second sizing implementation.
- FVG context attached at trade open ONLY when the signal can supply a
  real one (Trigger F); otherwise absent and invalidation skipped —
  geometry never fabricated.

### Changed
- `smc/orchestration/engine.py` — `scan_route(..., to_bar=)` no-lookahead
  cap + `tracked_pois()` arm-order registry (M4 integration seams; no
  trading-logic change).
- `README.md` — Phase 6 milestones + test counts updated to 496.

### Deferred to V1.1 (recorded, not built)
- Walk-forward analysis; Monte Carlo; Future Flexibility KPI pass/fail
  thresholds; slippage simulator; Redis/event-bus abstraction (V1
  in-memory stores documented as the seam).

---

## [2026-09-08] — Phase 0–5 Audit Fixes (Lead Architect approved)

### Fixed
- **PositionManager SL/TP clobber (C1)** — `modify_sl` / `modify_tp` no
  longer send `0.0` for the untouched protective field. Both fetch the
  current position snapshot and RE-SEND the current opposite price (the
  cab_watcher `_modify_sl` pattern); an unknown ticket raises instead of
  sending a clobbering request. Regression tests: modifying SL preserves
  TP and vice versa; unknown ticket sends nothing.
- **Single sizing policy path (C2)** — `PipelineEngine.compute_risk_lots`
  now routes through the Phase 5 policy layer
  (`smc.risk.lot_sizing.sized_lots`: RISK_PCT band clamp + `LOT_MAX_SAFETY`
  cap) instead of the raw `risk_lots` formula. No public helper sizes
  outside `RISK_PCT_MIN`/`RISK_PCT_MAX` or above `LOT_MAX_SAFETY`.
- **Blocked routes no longer burn the POI one-shot (I2)** —
  `PipelineEngine.execute_route` marks the POI fired ONLY on an accepted
  execution attempt; news/session blocks return `blocked` outcomes without
  consuming the §11 event identity, so the route can be re-attempted once
  the gate clears.
- **Same-bar tie-break pinned A-first (I3)** — on equal bar + equal §15
  grade the EARLIER trigger letter wins (A before F).
  `TriggerRouter.evaluate_at` (negated-grade ascending key) and
  `CompatibilityMatrix.eligible_triggers` (letter-ascending within grade)
  are aligned; regression test drives F before A in the trigger list and
  asserts A wins.
- **§7 inducement literals (I4)** — `pillar_5_inducement.py` and
  `validation_pipeline.py` import and use `INDUCEMENT_WITH_SCORE` /
  `INDUCEMENT_WITHOUT_SCORE` from `locked_constants`; no bare 1.0/0.7 or
  `!= 1.0` comparisons remain.
- **Injected clock (I5)** — `PipelineEngine.execute_route(..., now=...)`
  requires the caller to inject `now` (required keyword; no
  `datetime.now()` default) for backtest determinism; omitting it fails
  loudly with `TypeError`.

### Changed
- Governance docs (SESSION_HANDOFF / CHANGELOG / TODO) now describe the
  post-audit RiskEngine API: portfolio-level `evaluate_friday_close`,
  `on_trade_opened` / `on_be_applied` lifecycle hooks,
  `hard_cancel_pending`, `EntryRequest.current_spread_price` (price units,
  not MT5 points) and the closed-bar FVG contract
  (`PositionState.closed_close` only). The old "Friday inside
  `evaluate_exit`" description is removed — Friday EOD is evaluated ONCE
  per bar BEFORE per-position exits.
- Tests: C1/C2/I2/I3 regression tests added; engine tests inject `now`;
  inducement tests assert against the frozen constants. **Suite 353 → 363
  passing** (`python -m pytest tests` from `04_SRC/`).

### Notes / design decisions
- `modify_sl`/`modify_tp` fail fast (`ValueError`) when the ticket is not
  open — never send a protective-field-clobbering request blindly.
- The §28.7 clamp direction is confirmed: sub-band risk fractions are
  clamped UP to `RISK_PCT_MIN` (the caller chooses within the band; the
  policy guarantees the band). LOT_MAX_SAFETY caps the final size.

---

## [2026-09-07] — Phase 5 Complete: Risk Layer (v25_DIAG Port)

### Added
- **§28 Risk constants lock (2026-09-07, Lead Architect approval)** — 17 risk thresholds formally frozen in `locked_constants.py` (new §28 group) and mirrored in `LOCKED_DECISIONS.md` §28.1–28.9: `PURE_RUNNER_BE_ATR` 1.0, `PURE_RUNNER_BE_BUFFER_ATR` 0.10, `CIRCUIT_BREAKER_LOSS_COUNT` 3, `CIRCUIT_BREAKER_PAUSE_HOURS` 4, `SAME_LEVEL_GUARD_ATR` **0.15** (running v25 default; supersedes the outdated 0.1 header comment), `SAME_LEVEL_GUARD_COOLDOWN_BARS` 4, `FRIDAY_EOD_CLOSE_HOUR_UTC` 20, `SPREAD_MAX_ATR` 0.15, `SPREAD_GRADE_MULTIPLIERS` (A+ 1.5 / A 1.0 / B 0.7 / C 0.5), `SPREAD_GRADE_SCORE_THRESHOLDS` (A+ ≥8 / A ≥5 / B ≥3 / C <3), `SWEEP_GUARD_ZONE_ATR` 0.5, `SWEEP_GUARD_COOLDOWN_BARS` 4, `RISK_PCT_MIN` 0.5 / `RISK_PCT_MAX` 1.0 (band kept; caller chooses within), `LOT_MAX_SAFETY` 0.10, plus optional gates `ADX_MIN_ENTRY` 25.0 and `ATR_FLOOR_MIN_SL` 1.0. Explicitly deferred: Immediate Trail, fixed-dollar risk mode, fixed-lot fallback, dynamic SL buffers, PureRunner TP RR. **Primary exit model: PureRunner (BE at 1.0× ATR + buffer) + FVG Invalidation.**
- **`smc/risk/`** — Stage 5 ported from v25_DIAG, all thresholds imported from §28 (zero hardcoding), no MT5 calls (pure decisions + injectable state):
  - `lot_sizing.py` — re-exports the Phase 4 `risk_lots` pure formula (single sizing path, no parallel implementation) + policy layer: `clamp_risk_fraction` enforces the frozen RISK_PCT band, `sized_lots` applies the `LOT_MAX_SAFETY` cap.
  - `circuit_breaker.py` — `CircuitBreaker` + injectable `CircuitBreakerState`: pause after `CIRCUIT_BREAKER_LOSS_COUNT` consecutive losses for `CIRCUIT_BREAKER_PAUSE_HOURS`; resets on WIN or new day (v25 `TradeAllowed` semantics).
  - `same_level_guard.py` — blocks re-entry while the new SL sits within `SAME_LEVEL_GUARD_ATR` × ATR of the last closed SL and fewer than `SAME_LEVEL_GUARD_COOLDOWN_BARS` bars have elapsed (v25 `g_lastSLLevel` block semantics).
  - `friday_eod.py` — once-per-Friday force-close decision at `FRIDAY_EOD_CLOSE_HOUR_UTC` with latch + reset (v25 `g_fridayClosed`); pure decision — the caller performs closes/cancels.
  - `sweep_guard.py` — per-direction failed-sweep re-entry block (`SWEEP_GUARD_ZONE_ATR` zone, `SWEEP_GUARD_COOLDOWN_BARS`; v25 `IsFailedSweepBlocked` semantics, daily reset).
  - `spread_grading.py` — score-tier grading (`grade_for_score` over `SPREAD_GRADE_SCORE_THRESHOLDS`) + `effective_max_spread` = multiplier × `SPREAD_MAX_ATR` × ATR.
  - `pure_runner.py` — one-shot BE: fires at `PURE_RUNNER_BE_ATR` × ATR profit from entry, new SL = entry + dir × `PURE_RUNNER_BE_BUFFER_ATR` × ATR, only when it improves the current SL; no partials in V1.
  - `fvg_invalidation.py` — `FvgContext` frozen dataclass (valid/low/high/direction) + `is_invalidated` closed-candle structural-failure check with machine-readable exit reasons.
  - `risk_engine.py` — the orchestrator: `RiskEngine` composes all components (dependency-injected, §28 defaults). `evaluate_entry(EntryRequest) -> EntryDecision` gates in v25 pipeline order (news → session → circuit breaker → same-level → sweep → spread → risk-band clamp + sizing; first block wins, machine-readable `blocked_by`). Per-position `evaluate_exit(PositionState, *, now, fvg_context) -> ExitDecision`: FVG invalidation → PureRunner BE (`MOVE_SL` carries `new_sl`); Friday EOD is portfolio-level via `evaluate_friday_close(now)` called once per bar BEFORE per-position exits. Lifecycle hooks `on_trade_opened()` (re-arm BE latch) / `on_be_applied()` (set latch only after broker acceptance); §11 `hard_cancel_pending(now, news_events)`; `EntryRequest.current_spread_price` in PRICE units; FVG invalidation consumes only the closed-bar `PositionState.closed_close`. State pass-throughs: `record_result`, `record_sl_close`, `record_failed_sweep`, `reset_day`. Typed contracts: `RiskAction` (HOLD/ENTER/MOVE_SL/EXIT), `EntryRequest`/`EntryDecision`, `PositionState`/`ExitDecision`.
  - `__init__.py` — public re-exports of all risk components + decision types.
- **Tests** — 10 Phase 5 test files (90 tests: `test_locked_constants` §28 assertions + `test_risk_lot_sizing`, `test_circuit_breaker`, `test_same_level_guard`, `test_friday_eod`, `test_sweep_guard`, `test_spread_grading`, `test_pure_runner`, `test_fvg_invalidation`, `test_risk_engine`) — **340 total passing** (36 Phase 0 + 56 Phase 1 + 42 Phase 2 + 40 Phase 3 + 76 Phase 4 + 90 Phase 5).

### Changed
- `locked_constants.py` — old "v25_DIAG risk thresholds deliberately excluded" notice replaced by the §28 lock notice (only the deferred set remains excluded); `__all__` extended with the 17 §28 names.
- `00_LOCKED/TODO.md` — Phase 5 fully checked off; phase table row 5 → ✅ COMPLETE; current phase → 6 (Backtesting & Paper Trading); Kalman/ADX-gate/ATR-floor marked NOT ported (constants locked as conditional gates only).
- `SESSION_HANDOFF.md` — Phase 5 marked ✅ BUILT; current/next phase → Phase 6; Phase 5 implementation notes (RiskEngine API + Phase 6 open questions) added.
- `smc/execution/lot_sizing.py` — unchanged; now re-exported (not duplicated) by `smc/risk/lot_sizing.py`.

### Notes / design decisions
- **No parallel sizing path** — `PipelineEngine.compute_risk_lots` still consumes `smc.execution.lot_sizing.risk_lots`; the risk layer adds policy (band clamp + cap) on top of the same formula.
- **Pure decisions, no broker calls** — every risk component and the engine return typed decisions; Phase 6/7 runners apply them.
- **Gate order mirrors v25's entry pipeline** (environment → breaker → re-entry guards → spread quality → size); exit priority mirrors v25 on-tick management (Friday close outranks per-position exits).
- **Open questions for Phase 6:** FVG context capture at trade open (trigger layer doesn't persist FVG boundaries yet), exit evaluation cadence (closed bars vs ticks), daily `reset_day()` clock edge ownership, whether ADX/ATR-floor gates get ported, slippage policy (v25 `InpSlippage` deferred).

---

## [2026-09-07] — Phase 4 Complete: LTF Triggers (A–F) + Python Execution

### Added
- **`smc/triggers/`** — Stage 3 per LOCKED_DECISIONS §10/§12/§15/§22–§24 and R1 §7/§11:
  - `base_trigger.py` — `Trigger` ABC + `TriggerContext`/`TriggerSignal` (entry limit + stop reference, `completion_index`, `expiry_bars`, `detail`, and `data: dict = field(default_factory=dict)` — never None).
  - `trigger_a_choch.py` … `trigger_f_bos_ob.py` — the six triggers: A CHOCH Reversal, B Leading Diagonal (5-wave initiation), C Ending Diagonal (throw-under reclaim), D Two-Bar Reversal (frozen 50% engulfing-body limit, §10), E RSI Divergence, F BOS + OB continuation. Every trigger is a LIMIT entry — none emits a market order.
  - `wave_structure.py` — deterministic V1 5-wave impulse extraction (`find_impulse`) feeding Triggers B/C.
  - `trigger_router.py` — chronological first-valid routing (§12) within the §24 give-up window; same-bar tie-break by §15 compatibility grade (PREFERRED > STRUCTURAL > UNCOMMON) then trigger letter.
  - `trigger_expiry.py` — §24 per-trigger validity windows (`window_bars_for`) + §23 unfilled-order expiry anchors + POI-wide give-up window (Trigger A's 20 M5 bars, V1).
  - `compatibility_matrix.py` — §15 per-model grades (`DEFAULT_MATRIX`); routing tie-break only, no frozen cell is forbidden.
- **`smc/execution/`** — Stage 4:
  - `order_manager.py` — `OrderManager` limit/market placement, cancel, modify via a connector; `OrderRequest`/`OrderResult` contracts.
  - `position_manager.py` — position monitoring + SL/TP adjustment.
  - `news_guard.py` — §11 `should_block_entry` (CPI/NFP/FOMC blackout).
  - `session_filter.py` — §2 `is_allowed_session` gate.
  - `lot_sizing.py` — `risk_lots` sizing helper (Phase 5 risk engine consumer).
- **`smc/orchestration/engine.py`** — `PipelineEngine` (Stage 2→3→4 seam): merge-before-validate, displacement injection, arm-bar bookkeeping, per-bar §5 state feed (`feed_bar`), give-up-bounded `scan_route`, and `execute_route` (news + session gates → LIMIT order → `ExecutionOutcome` with `order_result`).
- **Tests** — 16 Phase 4 files (`test_trigger_{a..f}_*.py`, `test_trigger_router.py`, `test_trigger_expiry.py`, `test_compatibility_matrix.py`, `test_order_manager.py`, `test_position_manager.py`, `test_news_guard.py`, `test_session_filter.py`, `test_lot_sizing.py`, `test_rsi.py`, `test_pipeline_engine.py`) — **76 Phase 4 tests, 250 total passing** (36 Phase 0 + 56 Phase 1 + 42 Phase 2 + 40 Phase 3 + 76 Phase 4).

### Changed
- `00_LOCKED/TODO.md` — Phase 4 fully checked off; phase table row 4 → ✅ COMPLETE; current phase → 5 (Risk Layer — Port v25_DIAG to Python); wave-counting blocked item resolved (deterministic V1 `wave_structure.py`).
- `SESSION_HANDOFF.md` — Phase 4 marked ✅ BUILT; current/next phase → Phase 5; Phase 4 implementation notes + Phase 5 integration seams added.

### Fixed
- **`ExecutionOutcome.order_result` typed field** — was an unannotated attribute that `@dataclass(slots=True)` silently dropped from `__init__` (plain class attribute, not a field), so `engine.execute_route()` raised `TypeError: unexpected keyword argument 'order_result'`. Now `order_result: Optional[OrderResult] = None` with `OrderResult` imported — the execution outcome carries the placed order.
- **Trigger B `TriggerSignal.data` dict contract** — guaranteed every returned signal carries a real dict (never None) so `signal.data["wave5_index"]` is always safe; the Trigger B test fixture no longer crashed before the data assertion. These two fixes took the suite from 245 → **250/250 green** (`python -m pytest tests` from `04_SRC/`).

### Notes / design decisions
- All six triggers are LIMIT entries (Trigger D frozen at 50% of the engulfing body, §10) — no trigger emits a market order.
- Routing is chronological first-valid (§12); the §15 compatibility matrix influences routing only as a same-bar tie-break.
- §7 inducement literals (`score_modifier=1.0/0.7`) from the Phase 3 audit remain value-identical to frozen constants; a constant import refactor is still a candidate at Phase 5 kickoff (no numeric discrepancy).
- v25_DIAG risk thresholds (Phase 5 port scope) remain deliberately outside `locked_constants.py` until formally locked in `LOCKED_DECISIONS.md`.

---

## [2026-09-07] — Phase 3 Independent Audit (docs-only follow-up, no logic change)

### Added
- Independent audit of every file in `04_SRC/smc/validation/` and the 7 Phase 3 test files against the 11 audit criteria (directory/modules, locked-constants-only, Pillar 1 ±0.5×ATR refinement, Pillar 2 displacement reuse, Pillar 3 sole reject ownership, Pillar 4 1-touch freshness, Pillar 5 soft inducement, pipeline order/short-circuit/arming+scoring, state-machine atomicity/terminals/expiry, unit tests, governance docs). Result: **11/11 PASS (2 Notes)** — full audit table reported to the Lead Architect; suite re-run **174/174 green** (36 Phase 0 + 56 Phase 1 + 42 Phase 2 + 40 Phase 3).
- `SESSION_HANDOFF.md` — added a consolidated **"Integration seams Phase 4 must respect"** list to the Phase 3 Implementation Notes (displacement injection contract, merge-before-validate, score-assignment timing/ownership, M8 not-assumed-fresh, state-based Pillar 4 + creation-bar gap, §7 literal-modifier note, `atr_period=14` indicator default). The three audit confirmations (Pillar 3 sole owner of the §6 reject, Pillar 2 caller-injected `DisplacementResult`, UNAVAILABLE on pillars 1–4 ⇒ reject) were already verbatim in the notes — no edit required.

### Changed
- No validation logic or numeric values changed (comments/documentation only, per audit instructions).
- `00_LOCKED/TODO.md` — Completed-log row added for the Phase 3 audit.

### Notes / audit findings (no code fix applied)
- **§7 inducement modifiers used as literals:** `pillar_5_inducement.py` returns `score_modifier=1.0 / 0.7` and `validation_pipeline.py` defaults/comparisons use `1.0` — values exactly match the frozen `INDUCEMENT_WITH_SCORE` (1.0) / `INDUCEMENT_WITHOUT_SCORE` (0.7) in `locked_constants.py` and the docstrings name those constants, but the code does not import them (codebase convention is to import frozen values). No numeric discrepancy; a value-identical constant refactor is recommended before/at Phase 4 kickoff. Remaining literal `atr_period=14` (context/pipeline) is an indicator parameter inherited from `smc.utils.atr`, not a frozen decision value.

---

## [2026-09-07] — Phase 3: 5-Pillar Validation Pipeline (Stage 2)

### Added
- **`smc/validation/`** — Stage 2 per LOCKED_DECISIONS §3/§5/§6/§7/§13 and R1 §6 (pillars 1–5 run in order; 1–4 are hard gates, 5 is soft):
  - `pillar.py` — `Pillar` ABC (number/name/`run(context)`) + `PillarStatus` (PASS/FAIL/UNAVAILABLE), `PillarResult` (detail + score_modifier + data), and the `ValidationContext` every pillar consumes (POI, candles, swings, liquidity levels, pre-computed dealing range / displacement).
  - `pillar_1_zone_refinement.py` — §13: unmitigated FVG or OB (candle before the first FVG candle, R1 §3.1) must overlap the POI level band (zone midpoint ± `ZONE_REFINEMENT_ATR` × ATR); a candidate is mitigated once price closes through its opposite extreme after formation; naked level = FAIL, insufficient data = UNAVAILABLE.
  - `pillar_2_displacement.py` — §3 gate that CONSUMES the Phase 1 `check_displacement` result (BOS + FVG + ≥1× ATR; hard fail < 0.5× ATR). No blind recompute — missing result = UNAVAILABLE (documented reuse decision).
  - `pillar_3_premium_discount.py` — §6 gate and SOLE owner of the 45%/55% hard reject: LONG must classify DISCOUNT, SHORT must classify PREMIUM, 45–55% EQUILIBRIUM = REJECT; `compute_dealing_range() == None` → UNAVAILABLE (never a silent pass).
  - `pillar_4_freshness.py` — §5 strict 1-touch gate: CREATED/FRESH pass; TESTED/VIOLATED reject (state-based; per-bar transitions owned by the state machine).
  - `pillar_5_inducement.py` — §7 SOFT pillar: SSL pools (equal lows / unconfirmed minor swing lows) between the zone approach boundary and last close = 100% (modifier 1.0); none = 70% (modifier 0.7), never a rejection. Trendline inducement not machine-testable in V1 (documented).
  - `validation_pipeline.py` — `ValidationPipeline` runs pillars 1→5 and short-circuits on the first hard (1–4) non-pass; on success arms the POI (CREATED→FRESH) and assigns the §1 confluence `score_poi` when unset; returns a `ValidationResult` (decision PASS/REJECTED, per-pillar results, quality score, inducement modifier, first failure). Dealing range auto-computed from swings via Phase 2 `compute_dealing_range` when not injected.
  - `state_machine.py` — `POIStateMachine` with atomic §5 transitions (CREATED→FRESH→TESTED/VIOLATED, terminals immutable; illegal moves raise `IllegalTransitionError`), `can_trade` (FRESH only — first-touch-OK / no second touches), `touches_zone` helper, and §23 unfilled-order expiry (`expire_unfilled`; frozen M5 = 12 / M1 = 30 bars; H1+ have no frozen rule). V1 in-memory store documented as the seam for a later Redis CAS.
  - `__init__.py` — public re-exports (pillars, pipeline, machine, context/result types).
- **Tests** — 7 new files in `04_SRC/tests/` (`test_pillar_{1..5}_*.py`, `test_validation_pipeline.py`, `test_state_machine.py`) with synthetic OHLCV + reused Phase 1 `check_displacement` fixtures. Each pillar pass/fail (soft path for P5), pipeline short-circuit on first hard fail, full success path (score assignment + arming), dealing-range-None → Pillar 3 UNAVAILABLE/reject, freshness terminal states + first/second-touch semantics, expiry M5/M1. **174 tests total passing** (36 Phase 0 + 56 Phase 1 + 42 Phase 2 + 40 Phase 3).

### Changed
- `00_LOCKED/TODO.md` — Phase 3 fully checked off; phase table row 3 → ✅ COMPLETE; current phase → 4 (LTF Triggers).
- `SESSION_HANDOFF.md` — current phase/next task refreshed to Phase 3 → Phase 4 (still pending in this pass), Phase 3 marked ✅ BUILT in the plan list, Phase 3 implementation notes added below.

### Notes / design decisions (no frozen numbers invented)
- **UNAVAILABLE on pillars 1–4 rejects.** R1 defines PASS/FAIL/UNAVAILABLE; the pipeline treats anything that is not PASS on a hard pillar as a rejection (fail-fast, no silent accept). Distinct from FAIL in the log via `PillarStatus`.
- **Pillar 3 ownership:** the §6 hard reject lives ONLY here; `deal_range.py` classifies the region and nothing more (per the Phase 2 audit note).
- **Pillar 2 input contract:** the caller must inject the Phase 1 `DisplacementResult` for the POI's own sweep → BOS. Phase 2 detectors do not store the sweep/BOS indices yet, so deriving one inside the pillar would be model-specific guesswork; this stays UNAVAILABLE until the detector→pipeline glue supplies it.
- **Pillar 4 is state-based at validation time** (a POI just created has no touches *since creation*); historical per-bar touches/expiry are owned by `POIStateMachine`. A POI creation bar index is not stored on `POI` (Phase 2); revisit if a pre-creation zone-touch scan is wanted.
- **Pillar 5 inducement interval:** structure must lie strictly between the zone's approach boundary and the last close (zone TOP for buys, zone BOTTOM for sells); structures inside the zone body are the POI itself, not inducement.

---

## [2026-09-07] — Phase 2 Independent Audit (docs-only follow-up, no logic change)

### Added
- Independent audit of every file in `04_SRC/smc/poi/` (incl. `models/`) and the Phase 2 tests against the 11 audit criteria (directory/modules, equal-tag architecture, locked-constants-only, CHOCH Rules 1/2/3, M5 vs M7, Model 8, QML full-wick anchor, confluence tiers, deal-range bands, unit tests, governance docs). Result: **11/11 PASS** — full audit table reported to the Lead Architect; suite re-run **134/134 green**.
- `SESSION_HANDOFF.md` — added the audit-required ownership note (**Pillar 3 is the SOLE owner of the §6 45%/55% hard reject; `deal_range.py` only classifies regions for Pillar 3 to consume**) and a consolidated "V1 simplifications / edge cases Phase 3 must be aware of" list (M4 consecutive-swings-only, M8 most-recent-only per kind + forward D&S scan, single-pass `merge_overlapping`, CHOCH Rule 3 last-swing-or-intermediate wick reference, M5 co-tagging M7-style fixtures, M3 shared single tag). Phase 0–2 marked ✅ BUILT in the "Must Be Built" plan list.

### Changed
- No detection or model logic changed (comments/documentation only, per audit instructions).
- `00_LOCKED/TODO.md` — no edit required; already reflects Phase 2 completion (42 Phase 2 tests / 134 total).

---

## [2026-09-07] — Phase 2 Completion Audit + SESSION_HANDOFF Refresh (no logic change)

### Added
- Full audit of the Phase 2 deliverables against the Phase 2 coding prompt and `LOCKED_DECISIONS.md` §1/§6/§8/§9/§14/§17/§20–§22/§26, `CHOCH_TYPES_AND_SWING_VALIDITY.md`, `MODEL_8_HTF_DEMAND_SUPPLY.md`, and R1 §5. Result: PASS — all 14 modules present, no priority hierarchy (equal tags), all numeric thresholds sourced from `locked_constants.py`, Phase 0/1 types + detectors reused.
- **Test hardening (Phase 2 count 41 → 42):** `tests/test_poi_models.py` M8 acceptance now asserts the supply zone equals the FULL high-low range of the single last bullish candle (§22), and a new test asserts M8 ignores non-D1/H4 series (§21 detection-TF rule). **134 tests total passing** (`python -m pytest tests` from `04_SRC/`).
- `SESSION_HANDOFF.md` — refreshed to point at Phase 3 (was stale: still listed Phase 1 as current and Phase 2 as next) + added a Phase 2 Implementation Notes section.

### Changed
- `00_LOCKED/TODO.md` — Phase 2 test counts updated (41 → 42 tests; 133 → 134 total); Phase 2 remains ✅ COMPLETE; phase table unchanged.
- No trading logic changed in `04_SRC/smc/` during this session.

### Notes / audit findings (no code fix applied)
- `confluence_scorer.merge_overlapping` performs a single-pass merge against the first POI of each group; chain-overlapping zones (A∩B and B∩C but not A∩C) can still leave B-adjacent POIs overlapping in the output. Behaviour is documented in the docstring and acceptable V1; revisit if zone-union semantics need a fixed-point merge.
- The §6 dealing-range PASS/FAIL buy/sell gate is intentionally deferred to Phase 3 Pillar 3 (Pillar 3 = Premium/Discount); `deal_range.py` exposes the frozen region classification (`classify_region`) used by that pillar.

---

## [2026-09-06] — Phase 2: POI Classification (M1–M8 modular tags + confluence + CHOCH)

### Added
- **`smc/poi/`** — Stage 1/1b per LOCKED_DECISIONS §1/§4/§8/§9/§17/§20-§22/§26 and R1 §5 geometry:
  - `base_model.py` — `POIModel` abstract contract (`detect(candles, swings, liquidity_levels) -> list[POI]`) + shared pure geometry helpers (`zone_for_swing/zone_for_level/zone_for_candle`, `first_close_beyond`, `atr_up_to`, `has_directional_fvg_after`, `most_recent_swing`). Window slicing is the caller's responsibility (documented V1).
  - `model_registry.py` — `ModelRegistry` (one instance per `ModelType`, idempotent per tag, duplicate registration raises) + `build_registry(timeframe, htf_candles=None)` registering all 8 models.
  - `confluence_scorer.py` — §1 equal-tag scoring: independent tag count, quality tiers (1 base / 2 elevated / 3+ institutional from locked constants), M8 `+0.10` HTF-overlap bonus (§21/§26, quality-score only), and `merge_overlapping` (same-direction zone unions: widest zone, union tags, earliest id, OR overlap flag).
  - `choch_classifier.py` — CHOCH Rule 1 (standard body close beyond last structural swing), Rule 2 (inside body on an intermediate level, last swing intact), Rule 3 (inside wick, kept) per §17/§20; sweep of the final extreme is a pre-condition; bullish is classified via price inversion so one geometric path serves both sides.
  - `deal_range.py` — §6/R1 §3.4 dealing range (recent §19-valid high/low with window-extreme fallback) + premium/discount/equilibrium classification on the frozen 0.45/0.55 thresholds. The actual §6 PASS/FAIL gate is intentionally deferred to Phase 3 Pillar 3.
  - `models/m1_origin_base.py` … `models/m8_htf_demand_supply.py` — the 8 equal-tag model detectors: M1 origin base (BOS + directional FVG + ≥1× ATR from a §19-valid swing), M2 RBS/SBR flip, M3 CHOCH retest (3 sub-variants share one tag), M4 Quasimodo (head beyond shoulder + neckline close), M5 proactive equal-high/low cluster break (EQH/EQL tolerance), M6 double top/bottom neckline retest, M7 reactive bounce-shelf after expansion, M8 HTF D1/H4 zones (OB = pre-FVG candle, FVG zones, §22 last-opposing-candle zones) with the §21/§26 D1+H4 `htf_overlap` flag. M8 implements zone identification only (Step 1) — no M5-approach / M1-trigger logic yet.
  - `smc/poi/__init__.py` — public re-exports.
- **Tests** — 5 new files in `04_SRC/tests/` (`test_model_registry.py`, `test_choch_classifier.py`, `test_deal_range.py`, `test_confluence_scorer.py`, `test_poi_models.py`); `conftest.py` gained a shared `swing_factory` fixture. Per-model acceptance fixtures reproduce the canonical R1 §5 geometry with synthetic OHLCV plus a decoy (same geometry minus the decisive element). **133 tests total passing** (36 Phase 0 + 56 Phase 1 + 41 Phase 2).

### Changed
- `00_LOCKED/TODO.md` — Phase 2 fully checked off (registry path corrected to `smc/poi/model_registry.py` per the coding prompt); phase table row 2 → ✅ COMPLETE; current phase → 3.
- No triggers (A–F), 5-pillar validation, execution, or risk implemented.

### Notes / design decisions (no frozen numbers invented)
- **UNFROZEN V1 geometry choices** (documented at each site, not added to `locked_constants.py`): bare-level zone half-width reuses the frozen §13 0.5× ATR multiplier (`level_band_half_width`); M5 cluster zone = full-wick union of the two member candles. List these before live use.
- M3's Rule 1/2/3 variants all emit a single `ModelType.M3` tag (§1 equal-tags; the specific rule is exposed via `ChochBreak.rule` for research logging).
- CHOCH Rule 1 breaks require the break to happen AT the anchored bar (an earlier close below the level disqualifies the bar — the break candle is the classification bar).
- M8 accepts `htf_candles` at construction; zones are scanned per D1/H4 and `htf_overlap` is set only for same-direction D1/H4 price overlap (the +0.10 score bonus is applied by `score_poi`, never to position size).
- Overlapping same-direction POIs from different models are merged by `merge_overlapping`; the confluence/validation layers consume `list[POI]` so co-labeled levels stay intact.

---

## [2026-09-06] — Phase 2 Coding Prompt (planning artifact)

### Added
- `01_ARCHITECTURE/SMC_PHASE_2_CODING_PROMPT.md` — Lead Architect instruction prompt for Phase 2 (POI Classification), mirroring the Phase 0/1 prompt format: exact module list for `smc/poi/` (`base_model`, `model_registry`, `confluence_scorer`, `choch_classifier`, `deal_range`, `models/m1–m8`), strict rules (locked constants only, R1 §5 geometry, §1 equal-tags superseding R1 priority text), CHOCH/deal-range/confluence/M8 requirements, per-model acceptance-fixture test requirements, and the required ambiguities report. No code changed; TODO Phase 2 remains Pending until the prompt is executed.

---

## [2026-09-06] — Phase 1: Core Detection (Stage 0A/0b/0c)

### Added
- **`smc/detection/`** — 10 modules implementing Stages 0A/0b/0c per LOCKED_DECISIONS §2/§3/§18/§19/§27:
  - `liquidity_scanner.py` — orchestrator returning `List[LiquidityLevel]` (session, periodic PDH/PDL+PWH/PWL, EQH/EQL, structural-swing families; family filter). POI-level / D&S / OB-boundary types deferred until POI zones exist (Phase 2+).
  - `session_levels.py` — Asia/London/NY session H/L from the frozen §2 UTC windows.
  - `periodic_levels.py` — PDH/PDL + PWH/PWL over the most recent COMPLETED trading day/week (weekend-aware: skips days with no candles).
  - `eqh_eql_detector.py` — clusters swing highs/lows within `EQH_EQL_TOLERANCE` (4.5 pips); BSL level = extreme high, SSL level = extreme low; anchor-bound clustering (no pairwise chaining).
  - `structural_swing_detector.py` — N-bar fractal swings (§27 N=5 HTF / N=3 LTF via `Timeframe.n_bar_confirmation`), plateau-safe, Base-Candle anchored, §19-validated.
  - `base_candle.py` — §18 identification incl. the bearish special wick rule (previous bearish candle stays the Base Candle when the next candle's wick makes the lower low and closes back).
  - `swing_validator.py` — §19 decision gate: valid only on body CLOSE beyond the base candle's opposite extreme; wick-only / two-bar reversal = invalid.
  - `sweep_detector.py` — wick-pierce + body-close-back confirmation for BSL/SSL levels (never self-sweeps the forming candle).
  - `fvg_detector.py` — 3-candle imbalance gaps → `Zone` (bullish/bearish).
  - `displacement_checker.py` — §3 check: BOS close + directional FVG + magnitude ≥ 1× ATR (pre-move Wilder ATR); hard fail < 0.5× ATR; preferred > 1.5× ATR.
- **Tests** — 10 new test files (`04_SRC/tests/test_{base_candle,swing_validator,structural_swing_detector,eqh_eql_detector,session_levels,periodic_levels,sweep_detector,fvg_detector,displacement_checker,liquidity_scanner}.py`) with synthetic OHLCV; shared `candle_factory` fixture in `tests/conftest.py`. **92 tests total passing** (36 Phase 0 + 56 Phase 1).

### Changed
- `00_LOCKED/TODO.md` — Phase 1 fully checked off; phase row 1 → ✅ COMPLETE; current phase → 2.
- No trading logic beyond detection implemented (no POI models, triggers, execution, or risk).

### Notes / design decisions (no frozen numbers invented)
- Swings are only *structural* once §19-validated over available history; candidates are returned with `is_valid=False` until then. Scanner emits only valid swings as `STRUCTURAL_SWING` levels.
- EQH/EQL is detected on swing candidates regardless of §19 validity (an equal-level pool exists at formation, before any later break).
- PDH/PDL semantics: most recent completed *trading* day (calendar days without data are skipped).
- Sweep/structural/EQH families may co-label the same price region; confluence/POI phases dedupe (per §1 modular-tag design).
- Displacement magnitude measured from the sweep candle's extreme to the BOS candle's close; FVG must be directional and start within the move.

---

## [2026-09-06] — Phase 0 Audit & Comment Clarifications (no logic change)

### Added
- Full audit of Phase 0 deliverables performed (code inspection + LOCKED_DECISIONS.md cross-check).
  - Result: PASS. Tree matches claim; all 36 constants exported and frozen-value tests green; 36/36 unit tests pass.
- **Comment clarification A** (`smc/utils/pips.py`): explicit comment block that the `XAUUSD_PIP_SIZE = 0.1` (1 pip = 0.10) assumption is NOT frozen, is broker-dependent, and MUST be verified against the live broker's `digits`/`point` before Phase 4 (execution) and Phase 7 (live).
- **Comment clarification B** (`smc/config/locked_constants.py`): comment block at the top of the file stating that the v25_DIAG risk thresholds (BE 1×ATR, circuit breaker 3 losses → 4h, same-level guard 0.1×ATR, Friday EOD 20:00 UTC, risk 0.5–1.0%, spread grades, 4-bar sweep cooldown, ADX ≥ 25, 1.0×ATR floor) are PROVEN but not yet formally frozen in LOCKED_DECISIONS.md and are therefore deliberately excluded; they will be added before Phase 5.

### Changed
- No logic or values changed — comments only (per Lead Architect instruction).
- `00_LOCKED/TODO.md` — Phase 0 remains ✅ COMPLETE (verified, no edit required).

### Notes
- Audit finding (no fix applied, comments-only scope): LOCKED_DECISIONS.md §10 "Limit order at 50% of the engulfing body" is the only frozen numeric rule not yet in `locked_constants.py`; it belongs with Trigger D and should be added as a named constant when Phase 4 begins.

---

## [2026-09-06] — Phase 0: Foundations — SMC Python Package

### Added
- **04_SRC/smc/** — Complete Phase 0 Python package (Python 3.10+, type hints, dataclasses)
  - `smc/config/locked_constants.py` — All frozen thresholds from `LOCKED_DECISIONS.md` (EQH/EQL 4.5 pips, displacement 1.0/1.5/0.5× ATR, zone refinement 0.5× ATR, P/D 0.55/0.45, expiry M5=12/M1=30 bars, N-bar HTF=5/LTF=3, trigger A–F expiries, sessions, news protocol, Model 8 RR/bonus). Risk-layer numbers (v25_DIAG port scope) deliberately excluded until formally locked.
  - `smc/config/timeframe.py` — `Timeframe` IntEnum (MT5-compatible values) + §27 HTF/LTF N-bar helpers
  - `smc/config/model_type.py` — `ModelType` M1–M8 equal tags (§1)
  - `smc/core/` — `Candle`, `Swing`, `Zone`, `LiquidityLevel`, `POI`, `Event` dataclasses + `enums.py` (`TriggerType` A–F, `LiquidityType` 8 types, `POIState`, `Direction`, `PoolType`)
  - `smc/data/mt5_connector.py` — Thin lazy-import wrapper over the MetaTrader5 API (copy_rates, order_send, order_check, account_info, positions_get, connect/login/shutdown); reusable patterns extracted from `cab_watcher_v16_3-1.py` documented in docstring. No connection at import.
  - `smc/data/csv_loader.py` — stdlib OHLCV CSV → `list[Candle]`
  - `smc/utils/atr.py` — Wilder ATR (matches MT5 `iATR`)
  - `smc/utils/timestamps.py` — UTC normalization + Asia/London/NY session detection (§2 hours, sourced from locked constants)
  - `smc/utils/pips.py` — XAUUSD pip helpers (1 pip = 0.1 price units; 4.5-pip EQH tolerance default)
  - Placeholder packages `smc/detection|poi|validation|triggers|execution|risk|logging|backtest|paper|live/` (importable, no logic)
- **04_SRC/tests/** — 5 Phase 0 unit-test files (dataclasses, enums, locked constants, mocked MT5 connector, ATR) — **36 tests passing** (`python -m pytest tests` from `04_SRC/`)

### Changed
- `00_LOCKED/TODO.md` — Phase 0 checked off; phase table row 0 → COMPLETE; current phase → 1
- No trading logic implemented — structure, types, constants, and thin wrappers only (per Phase 0 scope)

### Notes
- `redis_store.py` left unimplemented (explicitly OPTIONAL for V1; in-memory state acceptable) — decision still open in TODO "Blocked/Waiting"
- v25_DIAG risk thresholds (Phase 5) intentionally NOT added to `locked_constants.py` — not yet frozen in `LOCKED_DECISIONS.md`; see module note

---

## [2026-09-06] — Project Restructuring & Architecture Lock

### Added
- **00_LOCKED/** — Source of truth directory
  - `LOCKED_DECISIONS.md` — Frozen Rev 5 (2026-09-01)
  - `DEVELOPMENT_PLAN.md` — Option A Locked (Python-First + MQL5 Safety Watchdog)
  - `CHOCH_TYPES_AND_SWING_VALIDITY.md`
  - `MODEL_8_HTF_DEMAND_SUPPLY.md`
  - `SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md`
  - `TODO.md` — Phase-by-phase task board
  - `CHANGELOG.md` — This file
  - `SESSION_HANDOFF.md` — Full context for future agents
- **01_ARCHITECTURE/** — Current design docs
  - `SMC_R1_MODULE_ARCHITECTURE.md`, `SMC_WORKFLOW_ORCHESTRATION.md`, `SMC_R1_POI_TRIGGER_COMPATIBILITY.csv`
  - `SMC_SESSION_HANDOFF.md`, `SMC_STATE.json`
  - `N8N_WORKFLOW_GUIDE.md`, `N8N_WORKFLOW_PROMPT.md`, `SMC_Zero_Lag_Pipeline_n8n_workflow.json`
  - `Flowcharts/` — Only v5 diagrams (7 files)
- **02_KNOWLEDGE_BASE/** — 57 PNG visual references
- **03_REFERENCE_CODE/** — Active code for study
  - `GOLD_SMC_v25_DIAG.mq5` — Reference implementation
  - `CAB_Unified_v16.4.mq5`, `cab_watcher_v16_3-1.py`, `start_bot_cab.bat` — CAB bridge pattern (temporary)
- **04_SRC/** — Empty, ready for new Python codebase
- **05_MQL5_SAFETY/** — Empty, ready for Safety Watchdog EA
- **06_RESEARCH/** — Active research scripts and experiments
- **ARCHIVE/** — All historical files organized by era

### Changed
- **Architecture decision locked:** Python-First + MQL5 Safety Watchdog (Option A)
  - Python owns ALL trading logic (Stages 0A–5)
  - MQL5 reduced to Safety Watchdog only (heartbeat + emergency close)
  - Future Flexibility Clause: selectively port back to MQL5 only after measured evidence
- **Project root cleaned:** 14 old directories replaced with 8 numbered folders + ARCHIVE

### Architecture Decisions
- Option A Locked: Python owns ALL trading logic
- MQL5 role: Safety Watchdog only (heartbeat monitoring + emergency position close)
- No HTTP bridge needed — Python connects directly to MT5 via MetaTrader5 API
- v25_DIAG is a reference implementation for porting, not a runtime component

### Notes
- 49 old MQL5 files archived to `ARCHIVE/MQL5_History/`
- 34+ TradingView scripts archived to `ARCHIVE/TradingView_Era/`
- 19 research ledger files archived to `ARCHIVE/Research_Archive/`
- Old flowcharts (v1–v4) archived to `ARCHIVE/Old_Flowcharts/`
- Old reports/logs archived to `ARCHIVE/Old_Reports_Logs/`
- Superseded docs archived to `ARCHIVE/Superseded_Docs/`
