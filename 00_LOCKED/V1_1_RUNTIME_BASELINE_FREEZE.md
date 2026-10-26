# V1.1 RUNTIME BASELINE FREEZE

**Status:** FROZEN — implementation baseline recorded; the default posture is
**operate and observe under contract**, not redesign.
**Date:** 2026-09-24
**Authority:** Lead Architect + owner (this file and `POST_V1_PLAN_OF_ACTION.md` are the
authoritative records; a change to this freeze requires a **dated ruling** recorded here or
in the plan).
**Scope of the freeze:** the frozen item is the *implementation* baseline — what is built,
wired, and proven as infrastructure. **Nothing in this file is an edge claim.** No expectancy,
profit factor, or live profitability is validated by anything below.

---

## 1. Baseline inventory (DONE, with evidence paths)

### Choice 1 — Product Runtime Unification (Phase 0→4, all PASS)
- **Phase 0 — product runtime contract:** `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md`
  (canonical runtime H4+H1 detection / M5 execution, one-driver rule, loud-fail policy,
  non-goals, acceptance tests, residuals, §8 silent/deferred policy table).
- **Phase 1 / C1 — one multi-TF product runtime:** shared seam
  `04_SRC/smc/orchestration/multi_tf_runtime.py` (`MultiTFProductRuntime.run_batch`,
  `build_htf_prefixes`, shared `ZoneDedup`, `MissingHtfSeriesError`); live + paper wired;
  parity smoke `06_RESEARCH/results/c1_multi_tf_parity/run1/`; note
  `06_RESEARCH/C1_MULTI_TF_PRODUCT_PATH_NOTE.md`.
- **Phase 2 — layer/pillar contract tests:** 28 contracts in
  `04_SRC/tests/test_phase2_layer_contracts.py`; note
  `06_RESEARCH/PHASE2_LAYER_CONTRACTS_NOTE.md`; population snapshot
  `06_RESEARCH/results/phase2_contracts/snapshot.json`.
- **Phase 3 — structure funnel / information-flow audit:** report
  `06_RESEARCH/PHASE3_STRUCTURE_FUNNEL_REPORT.md`; artifacts
  `06_RESEARCH/results/phase3_structure_funnel/` (+ `charts/`); sample audit 8/8, zero flow gaps.
- **Phase 4 — frozen 3-month unified backtest:** report
  `06_RESEARCH/PHASE4_UNIFIED_BACKTEST_REPORT.md`; artifacts
  `06_RESEARCH/results/phase4_unified/`; **trades.csv + report.json byte-identical across
  run1/run2** (SHA-256 verified); paper dry wiring smoke included. 1 fill in-window
  (BE-scratch +0.0715 raw, diagnostic only, n=1 — NOT edge evidence).

### Track A — residual engineering (COMPLETE)
- **E1 entry_anchor export DONE:** first-class `entry_anchor` on the full trade path
  (candidate → order → position → TradeRecord → CSV/JSON, appended + backward compatible;
  preserved through `modify_sl`). Tests `04_SRC/tests/test_residual_a_e1_entry_anchor.py`;
  note `06_RESEARCH/RESIDUAL_A_E1_C3_C4_NOTE.md`.
- **C3 structural TP UNFED_DESIGN_ONLY:** design ruling locked in the note §C3; no trigger
  emits a structural target; TP remains the frozen 4×ATR fallback (FR-2 R4). Nothing invented.
- **C4 dispositions:** news §11 DEFERRED, sweep-guard DEFERRED (no trigger emits
  `sweep_level`), spread §28.5 WIRED (operator-supplied `spread_price` value). Formal
  Silent/deferred policy table: `PRODUCT_RUNTIME_CONTRACT.md` §8. Shipped configs with
  `news_events=[]` / `spread_price=0.0` remain **diagnostic**, not "gates proven live".

### Phase D — HTF product-runtime probe (ops PASS, DEMO only)
- Script `06_RESEARCH/scripts/phase_d_htf_probe.py`; artifacts
  `06_RESEARCH/results/phase_d_htf_probe/` (`identity.json`, `probe_summary.json` status PASS,
  `events.log`); report `06_RESEARCH/PHASE_D_DIVERGENCES.md` §9.
- Result: identity MATCH (EXNESS Copy terminal, DEMO 474608655 @ Exness-MT5Trial15, XAUUSDm,
  magic 20260919); product-mode HTF probe **H4=300 / H1=300 / D1=300 bars**
  (`missing_series=[]`); `LiveLoop.start()` contract-compliant; degraded smoke stamped loud
  (`degraded=True` + reason); 60 s dry_run loop, 0 unhandled errors, clean shutdown.
- **Watchdog EA chart-attach: BLOCKED (GUI-only)** — stale-heartbeat emergency drill pending.

### Prior foundation (frozen reference)
- Foundation Fidelity Reset rulings R1–R9 implemented + recorded: `00_LOCKED/FOUNDATION_RESET_PLAN.md`
  §8 (M8 multi-TF wired, FR-2 SL/TP routing, FR-3 zone gate, R7/R8 fill regime, R9 place-on-reentry intent).
- Phase A data acceptance (`06_RESEARCH/DATA_ACCEPTANCE_REPORT.md`), Phase B/C fidelity
  baselines (archived, pre-reset — incomparable by design), Phase D ops sessions 1–3
  (`PHASE_D_DIVERGENCES.md`).

---

## 2. Suite reference

`cd 04_SRC && python -m pytest tests -q` → **737 passed** (2026-09-24, read-only verification).
Locked constants untouched: `git diff --stat -- 04_SRC/smc/config/locked_constants.py` empty.

---

## 3. Allowed WITHOUT a new ruling

- **Phase D operations:** watchdog EA GUI chart-attach + stale-heartbeat emergency drill;
  live ops stability logging; spread/tick distribution sampling; KPI latency measurement.
- **Bugfixes that restore CONTRACT behavior** (a defect against `PRODUCT_RUNTIME_CONTRACT.md`
  may be fixed; the fix + its evidence are recorded in `CHANGELOG.md`; no threshold rides along).
- **Documentation:** governance, notes, reports, charts of existing artifacts.
- **Read-only research** over EXISTING frozen artifacts (no new PnL experiments on live/demo books).

## 4. REQUIRES a dated ruling (in this file or `POST_V1_PLAN_OF_ACTION.md`)

- Any **locked_constants** numeric change (incl. the 7 never-imported constants: ADX_MIN_ENTRY,
  ATR_FLOOR_MIN_SL, EQUILIBRIUM_MIN/MAX, M8_MIN_RR, M8_SL_MIN/MAX_PIPS).
- Any **pillar / trigger / zone-band / R7/R9** threshold or geometry edit.
- **F-timing research** or **Monte Carlo** as a work track (both PAUSED, R6).
- **Structural TP invention** (C3 is UNFED by design; feeding it needs a trigger-level
  emitted target under the §C3 validity rules + a ruling).
- **Treating demo PnL as idea validation** — Phase D demo books prove operations, never edge.
- **`dry_run=false` "performance" campaigns** — live sends beyond the Phase D order-drill
  scope require an explicit owner instruction, operator config `dry_run=false`, and owner presence.
- Any **news-calendar / sweep_level feed** implementation (C4 deferred items) or synthetic
  data/calendar (hard ban stands).

---

## 5. Open ops residuals

1. **Watchdog EA chart-attach** — .ex5 compiled + deployed (2026-09-19); attach is GUI-only
   and unconfirmed.
2. **Stale-heartbeat emergency drill** — blocked until attach.
3. KPI latencies under live bar load — pending an attached-EA session.
4. News calendar / sweep-level feed — DEFERRED (C4; see contract §8).

## 6. Cold-start reading order (next agent)

1. `00_LOCKED/LEAD_ARCHITECT_ROLE_AND_PROTOCOL.md` (mandatory — no work on chat memory alone)
2. `00_LOCKED/SESSION_HANDOFF.md` — "Current Phase & Next Task" section
3. This file (`00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md`)
4. `00_LOCKED/POST_V1_ACTIVE_TODO.md` (day-to-day checklist, subordinate to the plan)
5. `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` (runtime law) + §8 silent/deferred table
6. `06_RESEARCH/AS_CODED_ARCHITECTURE_FLOWCHART.md` (code truth when in doubt)

**Standing statement:** after FREEZE the project operates and observes under contract.
Paused research stays paused; ops PnL is never edge; every reopen goes through a dated ruling.
