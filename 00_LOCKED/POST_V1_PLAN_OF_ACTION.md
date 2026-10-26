# POST-V1 PLAN OF ACTION — SMC BOT

**Status:** ACTIVE — binding operational plan for everything after the V1 build.
**Created:** 2026-09-09 (V1 frozen: Phases 0–7, **519 tests green**, commit `55c7933`).
**Authority:** This document is the source of truth for post-V1 sequencing. Every future agent starts here, works ONE phase at a time, and updates the phase marker + checkboxes when a phase completes. Do not skip phases. Do not reorder priorities without a Lead Architect ruling recorded here.

---

## ⚡ ACTIVE PHASE: **Phase D — Demo/Paper Operational Validation + Research Diagnosis track ACTIVE in parallel** (Phase A CLOSED 2026-09-09: PASS · Phase B CLOSED 2026-09-14: PASS · **Phase C CLOSED 2026-09-19 — Lead Architect sign-off GRANTED on the closeout package** · Phase D OPENED 2026-09-19, ops session 1 executed)

(Update this marker — and the checklist below — when a phase completes. Phases run strictly in order A → B → C → D → E.)

**Day-to-day checklist:** `00_LOCKED/POST_V1_ACTIVE_TODO.md` is the working checklist for the post-baseline period (Track R research diagnosis + Track D ops). This plan remains the binding authority; the TODO is subordinate to it.

**Operator pack (Phase D run surface):** `run_live.bat` (repo-root launcher) → `config/live_demo.json` (dry_run default TRUE, EXNESS Copy terminal, XAUUSDm, magic 20260919) → `04_SRC/smc/live/run_operator.py` with console board + backend logs under `logs/phase_d/` (gitignored).

**Primary diagnostic finding (triple-audit agreement, 2026-09-19):** the frozen V1 trade system is incomplete — no TP path exists (`tp_price=None` hardwired; 754 SL + 7 Friday-EOD closes over 761 trades). Every baseline metric measures the missing exit, not the entries. Forced next research action: R1 MFE/MAE + synthetic TP counterfactuals on the frozen 761-trade book (Track R). Paper/demo is ops-only and will not validate the idea.

---

## 1. Current status

- **V1 build complete:** Phases 0–7 delivered and frozen — core types/data (0), detection (1), POI models M1–M8 (2), 5-pillar validation (3), triggers A–F + execution layer (4), RiskEngine §28 port (5), backtest engine + reports + paper runner (6), live loop + heartbeat + MQL5 Safety Watchdog (7).
- **Suite:** 580 passed, 0 skipped (`python -m pytest tests` from `04_SRC/`; 519 at V1 freeze → 580 after Phase A loader, audit fixes, Phase 7, and operator-pack tests).
- **Frozen (do not modify without an architect ruling):** `LOCKED_DECISIONS.md` Rev 5 incl. §28 risk constants; trigger geometry and the §15 compatibility matrix; §5 one-touch state machine; §11 one-shot event identity; §23/§24 unfilled-order expiry; fill model (limit-price fills, SL-first same-bar, fill-before-entry); single sizing path (§28.7 band + `LOT_MAX_SAFETY`).
- **Architecture:** Option A locked — Python owns ALL trading logic; MQL5 is ONLY the Safety Watchdog.
- **Explicitly deferred (V1.1, NOT built):** walk-forward analysis, Monte Carlo, Future Flexibility Clause KPI pass/fail thresholds, production alerting (Telegram/email), M8 HTF provisioning in the live driver, remote/VPS heartbeat transport.
- **Done since this plan was written:** the historical backtest HAS been run (Phase C closed 2026-09-19: 761 trades, PF 0.344, WR 25.49%, net −4.78% equity — diagnostic only); the baseline expectancy figure EXISTS (`06_RESEARCH/PHASE_C_BASELINE_REPORT.md`); the watchdog EA has been compiled clean, deployed, and idle-loop validated on the EXNESS Copy demo terminal (Phase D session 1 — attach/drill/live-sends still pending). **Do not claim edge, tune, or scale capital — the baseline authorizes diagnosis (Track R) and ops validation (Phase D), nothing else.**

## 2. Strategic priority order (BINDING)

1. **Historical fidelity validation / baseline backtest** (Phases A → B → C) — FIRST. ✅ DONE (all three CLOSED).
2. **Demo / paper operational validation** (Phase D) — SECOND. ✅ OPEN, session 1 executed.
3. **V1.1 research upgrades** (Phase E) — ONLY AFTER 1 and 2.

**Parallel track (added 2026-09-19):** Track R research diagnosis (R1 MFE/MAE → R2 TP counterfactuals → per-trigger decomposition) runs IN PARALLEL with Phase D ops. Track R does not reorder the A→E sequence — it is diagnosis on the closed Phase C book, not a new phase. Day-to-day checklist: `00_LOCKED/POST_V1_ACTIVE_TODO.md`.

**Rationale (binding, not advisory):**
- We must first prove the implementation faithfully executes the frozen spec on real data and capture an honest diagnostic baseline. A backtest that reveals wiring bugs (detection never fires, expiry miscounted, gates silently off) invalidates every downstream number — demo trading on a broken stack proves nothing.
- Demo validation is necessary for operational proof (live bar flow, broker rejects, watchdog, KPI latencies) but it is secondary: one month of demo produces a handful of trades and cannot validate 5-year behaviour.
- **No optimization, parameter fishing, or edge claims before the diagnostic baseline exists.** The first full backtest is a measurement of what the frozen system DOES, not a search for what makes money.

## 3. Phase A — Data acceptance

**Goal:** certify `07_DATA/XAUUSD_M1.parquet` (twin: `XAUUSD_M1.csv`) as the canonical backtest dataset. Verified on 2026-09-09: 1,768,123 rows × 6 cols (`timestamp, open, high, low, close, volume`), 2021-04-12 11:00 → 2026-04-10 20:59, 0 duplicate timestamps, monotonic increasing, 0 OHLC-inconsistent rows, **`volume` = 0 on every row**, 1,679 gaps > 1 min (max 4,382 min ≈ 3.05 days — weekend boundaries).

**Checklist (write the acceptance script under `06_RESEARCH/scripts/`, do not hand-verify):**

- [x] **A1 Schema vs Candle:** columns map exactly to `smc.core.candle.Candle(timestamp, open, high, low, close, volume, timeframe=Timeframe.M1)`; dtypes float64/float64/float64/float64; a loader (`smc/data/parquet_loader.py` or extend `csv_loader`) converts rows → `Candle` losslessly; assert round-trip equality on a 10k-row sample.
- [x] **A2 Timestamps/UTC:** source is tz-NAIVE (`datetime64[us]`); the loader MUST attach UTC explicitly (`tz_localize("UTC")`) — never `tz_convert` on naive values; assert all stamps fall inside 2021-04-12..2026-04-10, strictly increasing, and that bar stamps are minute-aligned OHLC-close times consistent with the feed contract.
- [x] **A3 Gaps/duplicates:** 0 duplicates (verified); enumerate all 1,679 gaps; confirm every gap ≥ ~weekend length or a documented session/holiday boundary; **classify any unexplained intraday gap as a finding** (it interacts with `reset_day`, §23 bar counts, and session-level weeks — the plan must state bar-count expiry counts BARS, not wall-clock time, so weekend gaps do not trigger §23/§24 early).
- [x] **A4 Units/price consistency:** prices are XAUUSD in dollars with 3-decimal ticks (e.g. 1740.548); `pip_value_per_lot` (10.0) and pip size (0.1) are UNFROZEN broker caveats — record the exact intended contract-size interpretation in this document before Phase C sizing runs; assert `high ≥ max(open,close)`, `low ≤ min(open,close)` (verified: 0 violations), and no negative/zero prices.
- [x] **A5 Volume zero — BINDING DECISION REQUIRED:** Trigger D's frozen confirmation is `engulfer.volume < engulfed.volume` — with `volume == 0` everywhere the comparison is `0 < 0` = False, **so Trigger D can never fire on this dataset**. Options: (a) accept the dataset as tick-volume-less and run the baseline WITHOUT Trigger D (documented limitation); (b) source the same series WITH tick volume and re-run Phase A. `> DECISION (2026-09-09, Lead Architect): OPTION (a) — the canonical dataset is accepted as volume-less; the baseline runs WITHOUT Trigger D as a tradeable path (it remains compiled but structurally unfireable — per-trigger breakdowns will show 0). Rationale: volume is 0 on all 1.77M M1 rows AND all 281.5M tick rows, so no re-derivation from existing data is possible; triggers A/B/C are unaffected; re-sourcing a vendor feed is deferred until the Phase C baseline proves the rest of the stack's fidelity makes it worthwhile.`
- [x] **A6 Canonical decision:** designate the parquet (preferred: binary, typed) as `CANONICAL`; CSV remains the human-readable twin; checksum both (`sha256sum 07_DATA/XAUUSD_M1.*`) and record the hashes here: `> SHA256: parquet `e5d730eae5af8348ac38f46f31e9ee6e1a481cbeaaa57cda342b9e56fd17fee9` · csv `54cf61559673adc7f6917f086bd4ef8d71808c3834f2faa82cd9323ee119311c` · ticks `637087df5cbe13a3c5c270c32b115691e7c7e53a4f9a92ac51fb78b35bfbd82e` (recorded 2026-09-09)`; all Phase B/C runs must load via the accepted loader only (`smc.data.parquet_loader.load_ohlcv_parquet`).

**Phase A execution record (2026-09-09 — script `06_RESEARCH/scripts/phase_a_data_acceptance.py`, full report `06_RESEARCH/DATA_ACCEPTANCE_REPORT.md`):**

- A1 PASS — schema exact; 10k-row Candle round-trip via the loader. A2 PASS — 0 duplicates, minute-aligned, strictly ascending, UTC localized by the loader. A3 PASS — 1,679 gaps >1 min fully classified: 302 weekend/holiday closures; 1,377 intraday holes of which 1,298 start 20:00–23:00 UTC (991 of them 60–120 min = the NY-5pm rollover hour the broker omits) and only 79 fall in London/NY hours, all ≤15 min — **no unexplained class**. A4 PASS — 0 OHLC violations, 0 NaN/inf, 0 error-spikes; max price 5,596.805 verified as a genuine 7-week repricing regime (sustained run, not isolated spikes). A6 DONE — canonical parquet designated, SHA-256 recorded above, accepted loader `smc/data/parquet_loader.py` merged with 6 unit tests (suite 525 green) and verified loading all 1,768,123 rows.
- **A5 CLOSED — ruled option (a) on 2026-09-09 (see checklist): baseline WITHOUT Trigger D as a tradeable path.** Tick-file evidence stands: `XAUUSD_mt5_ticks.csv` (281,514,283 ticks) has volume = 0 on every row, so option (b) was unsatisfiable; re-sourcing a vendor feed is deferred until Phase C fidelity justifies it.

**Exit criteria:** every checkbox A1–A6 checked or explicitly decided; loader unit test merged (suite still green); no unresolved unexplained gap; volume decision recorded. Phase B must not start otherwise. *(Status: 6 of 6 met — **PHASE A CLOSED 2026-09-09, PASS**.)*

## 4. Phase B — Short fidelity backtest (1–3 months of M1 data)

**Goal:** prove implementation fidelity on a small window (e.g. 2025-10-01 → 2025-12-31) BEFORE burning the full 5-year run. This is a debugging/fidelity gate, not a performance measurement.

**Mandatory counters/metrics (from `build_report` + direct store introspection):**
- [x] bars processed; POIs detected / merged / validated / armed (per model M1–M8); triggered routes per trigger type; entries placed / filled / expired (§23/§24) / hard-cancelled (§11) / Friday-closed; blocked entries **by reason** (`blocked_by` from the report); positions opened / SL-closed / TP-closed / risk-exited; BE modifies proposed/applied. *(CLOSED 2026-09-14 — see status line + fidelity report.)*

**Stage kill-funnel (each stage must be NON-ZERO or explained in writing):** raw bars → detection fires → POIs created → validated (Pillar-1→5 pass counts, first-failure histogram) → armed → routed (per trigger) → risk-accepted vs blocked → limits placed → filled → closed. Any stage collapsing to 0 (e.g. "0 POIs validated") is a fidelity bug to fix before proceeding — the funnel is the diagnostic.

**Frozen-rule invariants to verify explicitly:**
- [x] §23/§24: every resting limit is cancelled no later than `placed_bar + expiry_bars(M1=30)/give-up(20)`; the POI transitions TESTED via the state machine; an expired order NEVER fills.
- [x] §11 one-shot: at most ONE placed order per POI; blocked entries consume nothing (a POI may fire on a later bar); VIOLATED POI → resting limit pulled.
- [x] §5 one-touch: no POI ever trades twice; touch → TESTED is terminal.
- [x] BE: `on_be_applied()` fires only on a successful (improving) modify; never twice per trade.
- [x] Same-bar rule: when SL and TP are both touchable in one bar, the close is recorded SL-first (loss) — verified over ALL 41 October trades (`phase_b_sl_first_check.py`), stronger than the requested sample.
- [x] Fill rule: every fill price equals the resting limit price (touch semantics), never the bar's open/close.
*(All six CLOSED 2026-09-14 — invariants OK × 2 runs, machine verdict PASS.)*

**Determinism rerun (hard requirement):** run the identical window twice; `runner.result()` must produce byte-identical CSV/JSON exports (`smc.backtest.export`, `sort_keys=True`). Any difference is a blocking bug (hidden wall-clock, dict-ordering, RNG).

**Failure conditions that BLOCK progression to Phase C:** any zeroed funnel stage without a written explanation; any invariant violation; non-deterministic rerun; exception/crash mid-run; report metrics that are structurally impossible (e.g. PF on a zero-loss book reported as inf instead of `None`).

**Exit criteria:** all invariants hold; determinism proven; funnel explained; a one-page fidelity note appended to this document (findings + fixes). Only then run Phase C.

*(Status: **PHASE B CLOSED 2026-09-14, PASS.** Full evidence: `06_RESEARCH/PHASE_B_FIDELITY_REPORT.md` · machine verdict `06_RESEARCH/results/phase_b_verdict.json` = PASS · artifacts `06_RESEARCH/results/phase_b_run{1,2}/` (31,619 bars each, 2025-10-01 → 2025-10-31) · golden pairs `phase_b_oct_short_run{1,2}/` + `phase_b_golden_check/`.)*

### Fidelity note (one page, plan §4 requirement) — findings + fixes

1. **§28.1 BE latch bug found and fixed (true integration bug).** The v25_DIAG single-position EA's shared `g_beMoved` flag was unsafe in the multi-position Python runners: a later trade's `reset_trade()` released the shared latch and re-proposed BE on an already-modified position (tripped `be_once_per_trade` in the first smoke run). Fix: per-trade keying (`PureRunnerState.latched` set + `trade_key` threading through `RiskEngine`/runners) + 4 regression tests. Suite 525 → 529.
2. **Quadratic per-bar scan cost found (py-spy) and fixed, semantics proven preserved.** `generate_candidates` re-ran O(prefix) swing detection + per-trigger O(prefix) rebuilds (inversions, RSI, ATR) for every tracked POI every bar, and never-routed POIs stayed FRESH forever — O(bars²). Fix: arm-anchored scan cursor (evaluate each §24-window bar exactly once; context anchor stays `from_bar=arm_bar`), deadline-anchored exhaustion, `scan_route(scan_from=)` resume param. Suite 529 → 532. **Proof: byte-identical Oct 1–3 golden re-run on patched code.** Full October: 11.8 h/run at 0.75 bars/s, linear remaining cost.
3. **Fidelity signals on the full window:** funnel every stage non-zero or explained (placed 42 → opened 41 via 1 × §24 give-up expiry; `positions_still_open = 0` = flat book by design); all 7 §4 invariants OK × 2 runs; Trigger D = 0 as A5-ruled; same-bar SL-first rule verified over **all 41 trades** (every exit price == SL exactly; zero ambiguous bars) — better than the requested sample. Determinism: byte-identical `trades.csv`/`report.json`; summary identical ex-runtime.
4. **Baseline warning for Phase C (binding):** October closed-trade P/L is **−7.66** with PF 0.0501, WR 36.6%, maxDD 7.66 — all 41 exits are SL closes, the 15 "wins" are exactly the BE-modified positions locking ≤ 0.06 each, and TP is never reached. Per §5 interpretation: this is a diagnostic shape, NOT a performance verdict on the 5-year window, and does NOT authorize redesign — it feeds Phase D divergence checks and Phase E evidence.

## 5. Phase C — Full 5-year baseline

**Goal:** ONE diagnostic baseline of the frozen system over the canonical dataset. This measures what the system does; it is not a search for what makes money.

- [ ] **One frozen config, committed alongside the run:** `equity=10_000`, `risk_fraction=0.01` (mid-band), `pip_value_per_lot=10.0`, `min_lots=0.01`, `lot_step=0.01`, `timeframe=M1`, sessions/news/spread as Phase B left them — recorded verbatim in the run note; afterwards NO parameter may be changed and re-run for comparison (that is Phase E territory with WF/MC methodology).
- [ ] **No parameter fishing:** if a result looks bad, the response is analysis, not re-tuning. Any parameter change invalidates the baseline and restarts Phase C with an architect ruling on record.
- [ ] **Required outputs:** full `BacktestReport` + CSV trade list + JSON export; kill-funnel counts; per-trigger and per-POI breakdowns; blocked-reason histogram; equity curve (closed-trade) with max DD; runtime + memory note (the O(bars²) per-bar prefix rescan is a known cost — record bars/sec so Phase E can justify an optimization with evidence).
- [ ] **Spread sensitivity requirement:** the §28.5 spread gate is OFF when `spread_price=0.0`. Run the frozen baseline ONCE as-is, then re-run with `spread_price` at a documented representative XAUUSD value (e.g. 0.35) and report both. The two runs are labelled SENSITIVITY-CHECK, not a parameter sweep — the as-is run remains THE baseline.
- [ ] **Interpretation (binding):** results are a diagnostic baseline of the frozen V1 — the reference point for every future change (does WF/MC/patch X improve on the frozen baseline?). P/L is raw price×volume units, not account currency; PF/DD/win-rate are the decision-relevant shapes. A losing baseline does NOT authorize redesign; it authorizes Phase D and evidence-gated Phase E work.

**Exit criteria:** baseline artifacts committed (`06_RESEARCH/results/` or equivalent) + a `PHASE_C_BASELINE.md` summary; config checksum recorded; Phase D may start.

*(Status 2026-09-19: **all exit criteria executed** — dual segmented pair complete (1,768,123 bars each, byte-identical, verdict PASS re-stamped 09:55:10 on the final artifacts); report `06_RESEARCH/PHASE_C_BASELINE_REPORT.md` carries the frozen config + checksums (§2), kill funnel, per-year/per-trigger breakdowns, boundary ruling **accept + document** (§7), spread ladder {0.00, 0.05, 0.15, 0.35} with adequacy note (§8), anomalies and binding interpretation; suite 565 green; guard task + Startup copy removed. **"Phase D may start" awaits the Lead Architect's sign-off on the report — GRANTED 2026-09-19: Phase C CLOSED.**)*

## 6. Phase D — Demo / paper forward

**Goal:** operational proof that the same stack runs live on demo, protected by the watchdog. Trading results in demo are NOT the metric; operations are.

*(Status 2026-09-19 — Phase D OPENED: session 1 executed on the ONLY permitted terminal `C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe` — identity PASS (DEMO 474608655 @ Exness-MT5Trial15, symbol **XAUUSDm**); watchdog EA deployed + compiled (0 err/0 warn) with the heartbeat contract verified; idle LiveLoop session clean (60 polls / 0 errors / dry-run); order payloads `order_check`-validated, magic **20260919** (NO sends — market closed + Algo Trading OFF); divergence log opened with the ATR-regime spread-gate finding (`06_RESEARCH/PHASE_D_DIVERGENCES.md`). Checkboxes below stay open until their criteria are met — EA attach (GUI), Algo Trading ON, live bar cycles, order sends, emergency drill, 2-week unattended window.)*

- [ ] **Watchdog checklist first:** execute the manual validation checklist in `01_ARCHITECTURE/SMC_PHASE_7_DESIGN_NOTE.md` §6 (compile EA in MetaEditor; healthy-heartbeat silence; stale → close-ALL + delete-ALL + Alert; garbage-file → same; magic/symbol scoping; recovery). Record completion date here.
- [ ] **Live loop checks:** `LiveLoop.start()` connects; cold start anchors history without replaying; new closed bars each cycle drive driver → arm → `PaperRunner.run_one_cycle`; heartbeat written every ~1 s and never stale under load; `stop()` writes `state=shutdown`.
- [ ] **KPI logging on:** confirm JSONL KPI records accumulate (decision latency, order_ack success/retcode, management latency, fills, missed bars, hard-cancels, friday_close); review weekly; **no pass/fail thresholds** — collect evidence for the Future Flexibility Clause only.
- [ ] **Backtest-assumption comparison (the real deliverable):** for each demo trade, compare against what the backtest would have done on the same bars — fill price vs limit price (slippage), same-bar SL-first vs broker's actual intrabar resolution, spread at entry vs the Phase C sensitivity value, reject codes vs backtest's zero-reject assumption. Document divergences in a running `PHASE_D_DIVERGENCES.md`.
- [ ] **Paper residuals:** ambiguous broker closes (no SL/TP level touched on the closing bar) carry `win=None` and are not fed to the breaker (honest V1 limitation); partial fills are logged at reported volume; no retry policy on rejects. Confirm these are visible in KPI logs, not silent.

**Exit criteria:** ≥ 2 consecutive weeks of unattended demo operation with zero unhandled exceptions, watchdog validated, divergence log started; KPI evidence archived.

## 6b. Visualisation roadmap (locked 2026-09-20; conviction support, not validation)

- **Order is binding:** (1) export identity patch first — COMPLETE 2026-09-20 (`model_tags` + `pillar_path` + `disp_magnitude_atr` on every trade); (2) Python research trade inspector / chart renderer (Track V1, near-term conviction tool over backtest/paper/R3/R4 artifacts); (3) optional MT5 display-only overlay for the paper terminal (Track V3, paper support only).
- **Option A preserved:** Python owns all logic at every stage; any MQL5 chart work is draw-only (no detection/entry logic), with clean-chart rules (shared prefix, ownership by poi_id/route_id, delete on TESTED/VIOLATED/expiry, layer toggles, history cap).
- **Checklist:** Track V in `00_LOCKED/POST_V1_ACTIVE_TODO.md`; design note `01_ARCHITECTURE/SMC_VISUALIZATION_ROADMAP.md`. Chart overlays never substitute for identity export and never expand MQL5 logic.

## 7. Phase E — V1.1 (only after baseline)

Each item is a separate, prompt-scoped engagement; none starts before Phases A–D are complete.

- [ ] **Walk-forward:** anchored/rolling IS/OOS splits over the canonical dataset using the SAME frozen config; baseline (Phase C) is the reference, not a tuning target.
- [ ] **Monte Carlo:** trade-order shuffling, spread/slippage resampling around the baseline's per-trade P/L; produces robustness bands on PF/DD — never "better parameters".
- [ ] **Future Flexibility Clause thresholds:** using the Phase D KPI archive + Phase B/C diagnostics, propose measurable thresholds for "which component, if problematic, gets ported back to MQL5" — for Lead Architect approval, then freeze into `locked_constants`.
- [ ] **Residual tech debt, only if evidence-blocking:** M8 HTF provisioning in the live driver (only when M8 HTF zones are demonstrably needed by baseline results); O(bars²) scan optimization (only when Phase C runtime is a demonstrated blocker); paper deal-history reconciliation (only when ambiguous-close frequency in Phase D is material). Each requires its own design note.

## 8. Explicit non-goals (until the baseline exists)

- No strategy redesign — no new POI models, triggers, exit rules, or session/news logic.
- No MQL5 strategy logic — the watchdog stays heartbeat + emergency flatten ONLY (Option A is locked).
- No parameter tuning, walk-forward-based selection, or "improvement" commits.
- No capital scaling, live-money, or VPS deployment decisions from the first backtest (or demo) alone.
- No new datasets replacing the canonical one without re-running Phase A.
- No trading-logic changes at all except a documented true integration bug (then: fix + regression test + note here).

## 9. Known V1 limitations that affect interpretation

Read every baseline number with these in mind:

- **Limit-fill conservatism:** pending limits fill AT THE LIMIT PRICE on touch — no slippage, no partial fills, no requotes. Live fills will be equal or worse; the Phase D divergence log quantifies the gap.
- **Fill-before-entry (V1 rule):** a limit placed on bar N cannot fill on bar N (no same-bar fill of a just-placed limit) — slightly conservative vs a broker that fills intrabar.
- **Same-bar SL-first:** when one bar touches both SL and TP, V1 books the LOSS (mirrors the fill model's conservative tie-break). Real intrabar path could differ; this systematically understates results on volatile M1 bars.
- **Trigger D volume dependency:** Trigger D requires `engulfer.volume < engulfed.volume`; the canonical dataset's `volume` is all-zero, so per the A5 ruling (option (a), 2026-09-09) Trigger D is ABSENT from the Phase B/C baselines as a tradeable path — per-trigger breakdowns will show 0.
- **Multi-TF/M8 completeness:** the live driver is fed only the execution timeframe (M8 emits nothing without D1/H4 series); session-level detection assumes continuous calendar weeks — multi-day data gaps (A3) shift session-high windows. Verify M8/session behaviour in the Phase B funnel before trusting per-model counts.
- **§11 news gate dormant by default:** `news_events` defaults to an empty list — no hard-cancels occur unless a calendar is configured. The baseline therefore excludes news risk; state this in every report.
- **Backtest ATR/spread:** ATR is fed per bar from the honest prefix (Wilder); spread defaults to 0.0 (gate off) — see the Phase C sensitivity run.
- **Paper/live residuals:** ambiguous close P/L is not reconstructed from MT5 history (win=None closes never feed the breaker); partial fills logged at reported volume; no reject retry policy; watchdog EA is untested on a real terminal until the Phase D checklist runs; heartbeat transport assumes Python and the terminal share a filesystem.
- **Equity accounting:** backtest equity = config start + realized P/L × pip-value-per-lot (raw-unit conversion); sizing follows §28.7 with the `LOT_MAX_SAFETY` cap — P/L is NOT account-currency truth.

## 10. Working protocol for future sessions

1. **Order is binding:** work proceeds prompt-by-prompt strictly in A → B → C → D → E. A phase starts only when the previous phase's exit criteria are met and recorded here.
2. **One phase per engagement:** an agent asked to "do Phase B" does Phase B — not C, not a redesign discovered along the way. Out-of-scope findings get recorded in this document, not implemented.
3. **Update on completion:** when a phase finishes, the agent checks its boxes here, updates the ACTIVE PHASE marker (top of this document), and adds a one-paragraph entry to `00_LOCKED/SESSION_HANDOFF.md` — before ending the session.
4. **Decisions get recorded:** any binding choice (A5 volume, Phase C config, thresholds) is written into this document with date + rationale. Undocumented decisions are not decisions.
5. **Suite discipline:** every session ends with `python -m pytest tests` green (currently 580 = 519 V1 freeze + 6 Phase A loader tests + audit fixes + Phase 7 + operator-pack tests). A session that leaves the suite red is incomplete.
6. **No silent logic changes:** documentation phases change no code; code phases change no frozen constants. Both are visible in `git diff` and the CHANGELOG.
7. **Current point of execution:** `> NEXT ACTION (dual): (a) R1 MFE/MAE study on the Phase C 761-trade book — offline diagnosis, no strategy-code changes (Track R, PRIORITY — see POST_V1_ACTIVE_TODO.md §2); (b) Phase D ops validation — attach SMC_Safety_Watchdog EA on the EXNESS Copy terminal (XAUUSDm chart; InpHeartbeatFile=smc_heartbeat.txt, InpSymbolFilter=XAUUSDm, InpMagicFilter=20260919); Algo Trading is ON (verified 2026-09-19). Launch controlled sessions via run_live.bat (operator pack — dry_run default, strict config); live bar-cycle + demo order sends (place/cancel/SL-modify/close) per §6; divergence log running at 06_RESEARCH/PHASE_D_DIVERGENCES.md.`
8. **Phase C audit ruling needed (2026-09-15) — RULED 2026-09-19, option (a) accept + document.** The independent perf-patch audit closed PASS WITH FINDINGS (`06_RESEARCH/PHASE_C_PERF_AUDIT.md` §5/§6): the segmented runner's fresh-stack-per-segment design drops episode/one-shot state at segment boundaries (probe: CARRY_LOSS = 1 on real October data) and positions open at a segment end are dropped from the merged trade list — 2021→22/22→23/23→24 are Friday-pre-flattened, **2024→25 and 2025→26 were exposed**. Ruled **option (a): accept + document as a known baseline limitation** — rationale and full quantification in `06_RESEARCH/PHASE_C_BASELINE_REPORT.md` §7: 0 dropped/force-closed positions at any boundary (`positions_opened` = trades exported = 761 per segment, `positions_still_open` = 0 everywhere); ±14-day boundary-window stress leaves the shape unchanged (664 trades, net −39.83, PF 0.383); **0 warm-up-zone trades** verified per segment (merge offsets exact, `route_id` unique 761/761), so the Option-B warm-up trim below is **moot**. The boundary-overlap re-merge is retained only as a documented contingency for future research-grade re-runs. No continuous-run identity is claimed anywhere in the Phase C report.

---

*End of plan. This document supersedes any informal sequencing discussed in prior sessions and remains authoritative until the Lead Architect revises it.*
