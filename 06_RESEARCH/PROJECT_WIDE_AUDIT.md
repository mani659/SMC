# PROJECT-WIDE AUDIT — XAUUSD SMC Trading System

**Audit date:** 2026-09-15
**Auditor:** Buffy (independent agent session, read-only review + full suite run)
**Trigger request:** "give me comprehensive report of the audit — what you found critical, what we have coded well, where we need to bring more clarity, code enhancements in terms of our goal, where we are standing"
**Companion audit:** `06_RESEARCH/PHASE_C_PERF_AUDIT.md` (2026-09-15, independent perf-patch audit — PASS WITH FINDINGS)
**RE-CHECK SCHEDULED:** revisit this document when the 5-year Phase C baseline pair completes (see §7 checklist).

---

## 0. Scope and method

Reviewed 2026-09-15, on the live checkout while the Phase C dual baseline pair was running:

* **Production code:** 13,503 lines in `04_SRC/smc` across 15 submodules
  (`backtest`, `config`, `core`, `data`, `detection`, `execution`, `live`,
  `logging` (placeholder), `orchestration`, `paper`, `poi`, `risk`,
  `triggers`, `utils`, `validation`).
* **Tests:** 10,401 lines across 69 test files; full suite run during the audit.
* **Research layer:** 16 scripts in `06_RESEARCH/scripts/` (phase A/B/C
  acceptance, probes, experiments) + audit docs.
* **Governance layer:** `00_LOCKED/` (LOCKED_DECISIONS Rev 5, TODO, SESSION_HANDOFF,
  POST_V1_PLAN_OF_ACTION, CHANGELOG).
* **Method:** module-by-module reading of the critical path (risk engine,
  locked constants, backtest runner/series_state/pipeline_adapter, data
  loaders), hygiene greps (TODO/FIXME, bare excepts, wall-clock reads,
  asserts, type: ignore), test-coverage mapping by import, plus the suite run.

---

## 1. CRITICAL FINDINGS (C1–C3)

### C1 — Midweek year-boundary carry loss (known; disposition pending)
The fresh-stack-per-segment Phase C design drops any position / episode /
one-shot state crossing a segment boundary (probe: `CARRY_LOSS = 1`,
`LONG 2025-10-15 05:32 UTC, −0.098, stop_loss`, reproduced identically by the
corrected re-run). Materiality is scoped:

* **Exposed (midweek year ends):** 2024→2025 (Tue Dec 31), 2025→2026 (Wed Dec 31).
* **Pre-flattened (Friday-EOD latch):** 2021→22, 2022→23, 2023→24
  (2021 segment evidence: `positions_still_open=0`, `friday_eod=1`).

Affects only the merged 5-year baseline verdict. Disposition —
(a) accept + document as known baseline limitation, or (b) boundary-overlap
trim in the merge — is **deferred to the Lead Architect** (plan §10 item 8,
audit §6). No production code was changed by the audit.

### C2 — Segment-end open positions silently dropped from merged results
`BarLoop` / `BacktestRunner.result()` snapshot without closing open positions
at end-of-data, and the merge has no `still_open` stage. Harmless for the
Friday-flattened years, but it means the merged trade list undercounts
whenever C1 applies, and there is **no warning anywhere** for "position open
at end of data" — a silent accounting gap. Proposed remedy: an explicit
`finalize(end_of_data=True)` contract on the runner that closes or explicitly
flags open positions and emits a `boundary_open` warning (audit enhancement E1).

### C3 — Paper/live runner is the largest, least-tested heavy module
`smc/paper/runner.py` (681 lines — largest file in the project) carries the
same risk-engine integration as the backtest runner but has only ~2 test
files importing `smc.paper` (vs 8+ for `smc.backtest`). Before Phase 7 (live),
this is the biggest unverified surface. Proposed remedy: paper-runner test
battery to backtest-runner parity (audit enhancement E3).

---

## 2. WHAT IS CODED WELL (verified strengths)

1. **Constants governance is exemplary.** Every threshold in
   `smc/config/locked_constants.py` cites its frozen section (§N) and lock
   date; `test_locked_constants.py` asserts name/value pairs against
   `LOCKED_DECISIONS.md` Rev 5. Invented numbers — the classic strategy-code
   failure mode — are structurally prevented.
2. **Determinism is engineered, not hoped for.** No wall-clock reads in
   backtest paths (`datetime.now()` only in live `heartbeat`/`loop` and the
   injectable `PipelineEngine` clock); no randomness; pinned iteration order.
   Verified live during the audit: the Phase C pair at identical progress
   counters, and 2021 completed byte-identical.
   *Minor observation:* `POI.created_at` defaults to wall clock
   (`core/poi.py:29`), but the detection driver's contract injects run-clock
   values and byte-identity is empirically proven; a deterministic-by-default
   guard would still be nice-to-have.
3. **The Phase C perf patch is a model of honest optimization.**
   `smc/backtest/series_state.py` documents an exact-equivalence argument for
   every replaced O(prefix) recomputation (Wilder folds, monotone first-confirm
   swing heaps, `SwingIndex` queries) and is pinned by
   `test_series_state_equivalence.py` + the October golden replay
   (byte-identical `trades.csv`/`report.json`).
4. **Risk engine is pure, typed, DI-composed.** `RiskEngine` never calls the
   broker — it returns frozen dataclass decisions (`EntryDecision` /
   `ExitDecision`); all seven pre-entry gates ordered per the v25 pipeline;
   the per-trade BE latch (Phase B fidelity fix) prevents one fill from
   un-latching another trade's BE move, with lifecycle hooks
   (`on_trade_opened` / `on_be_applied` / `on_trade_closed`).
5. **Backtest causality is explicit.** `pipeline_adapter.py` caps every scan
   at `bar_index + 1` (no lookahead), feeds §5 state *after* scanning
   (Trigger D same-bar overlap rule), and cancels resting limits on zone
   violation ("no ghost order may fill later"). These are the subtle bugs
   that silently inflate backtests; all three are guarded.
6. **Data validation is strict.** `smc/data/parquet_loader.py` enforces the
   A2 ruling (tz-localize, never convert), rejects non-chronological /
   duplicate / non-finite / non-positive rows, and is the mandatory load path
   per plan §3 A6.
7. **Hygiene metrics are genuinely rare for a codebase this size:**
   * TODO/FIXME/HACK markers in src: **0**
   * bare `assert` statements in src: **0**
   * `type: ignore`: **1** in 13.5k lines
   * broad `except Exception:`: **3**, each carrying an explicit
     `# noqa: BLE001` justification comment (sizing number vs crash, broker
     verdict vs crash, broken adapter must not kill the bar).
8. **Deferrals are recorded, not forgotten.** The v25 gates deliberately not
   ported (daily-loss limit, max daily losses, max trades/day, MaxDD cooldown,
   `InpMaxConsecLoss` backstop, DD-scaled risk multiplier, trail modes, fixed
   risk/lot modes, dynamic SL buffers, PureRunner TP RR) are all listed with
   reasons in the risk-engine docstring and the constants module note.

---

## 3. WHERE WE NEED MORE CLARITY

1. **Boundary semantics have no first-class API.** "What happens at
   end-of-segment" is implicit behavior of `result()`. It should be an
   explicit, documented contract (close-at-EOD? carry? warn?) — the C1/C2
   debate exists only because it is implicit.
2. **`logging/` and parts of `live/` are placeholders with stale pointers.**
   `logging/__init__.py` says "implemented in Phase 5" but Phase 5 (risk) is
   done — clarify whether logging is now Phase 6/7 scope or forgotten.
3. **Coverage accounting is opaque.** No coverage report exists; module-level
   test counts here come from import-grep. A `pytest --cov` baseline would
   make thin-spot claims (paper≈2, live≈1, data≈2 test files) precise.
4. **Deferred v25 gates have no decision deadline.** Daily-loss limit,
   max trades/day, MaxDD cooldown are "pending a Lead Architect decision"
   with no owner-date — for a live system these cannot stay optional forever.
5. **Trigger/detection test→locked-section mapping is invisible.** 13 trigger
   and 20 detection test files exist, but nothing maps tests to the §N they
   verify (§24 expiry, §19 swings, …). The constants have this discipline;
   the tests do not yet.

---

## 4. CODE ENHANCEMENTS FOR THE GOAL (ranked)

| # | Enhancement | Why it matters | Addresses |
|---|-------------|----------------|-----------|
| E1 | **Boundary contract:** `finalize(end_of_data=True)` on the runner — closes or explicitly flags open positions, emits `boundary_open` warning | Resolves C1/C2 before the 2024/2025 segments run; makes the merged baseline defensible | C2, clarity-1 |
| E2 | **Boundary-overlap trim in the Phase C merge** (drop trades whose `entry_bar < own_start`) | Bookkeeping-only alternative/complement to E1; removes the only known falsifier of the 5-year verdict | C1 |
| E3 | **Paper-runner test battery** to backtest-runner parity (risk integration, order lifecycle, adapter seams) | Rehearsal for live; least-verified critical path today | C3 |
| E4 | **End-to-end determinism gate in CI:** run a 2-week slice twice, hash the trade list, fail on mismatch | Byte-identity is currently proven manually per session; make it automatic | strength-2 upkeep |
| E5 | **Coverage baseline + thin-spot targets** (`pytest --cov`) | Converts clarity-3 into a tracked number | clarity-3 |
| E6 | **Stale placeholder sweep** (logging doc pointer, Phase 4/5 mentions) | Trivial hygiene; prevents stale pointers misleading future readers | clarity-2 |

---

## 5. WHERE WE STAND (as of audit)

* **Overall verdict:** the codebase is in unusually good shape for its stage —
  the governance layer (locked constants, dual-run determinism, honest
  deferrals) is stronger than most production quant codebases at this size.
  Critical findings concentrate in ONE theme: segment/boundary semantics —
  not in strategy, risk, or detection logic.
* **Phase C baseline (2026-09-15):** 2021 done, byte-identical; 2022 ~92%
  (bar 326,000/357,509, ETA ~1.4 h), pair in lockstep (identical counters:
  armed=855, placed=116, closed=109); 565/565 tests green.
* **Blocking decision:** boundary-carry disposition (C1) — Lead Architect.
* **Trajectory:** after 2023–2026 segments complete (~2 days), remaining
  milestones to the V1 verdict are the spread sensitivity check, the
  `PHASE_C_BASELINE_REPORT.md`, and the PASS/FAIL package. E1–E3 should land
  before Phase 7 (live).

---

## 6. Companion audit summary — Phase C perf-patch audit

Full document: `06_RESEARCH/PHASE_C_PERF_AUDIT.md` (same date). Verdict:
**PASS WITH FINDINGS** (self-downgraded per its §5 pre-stated rule).

* 17 static equivalence claims re-derived and OK (adapter scan cursor, §24
  retirement, `SeriesState` folds, inverted-space RSI, §27/§19 heap events,
  `SwingIndex` queries, mirror artifacts, stage0 hoists, `raw.sweeps` reuse,
  `WindowCache` suffix arrays, trigger/CHOCH hints, runner warm-up,
  deterministic merge, verdict watcher). F1 LOW-latent
  (`PipelineAdapter.current_atr` on negative `bar_index`, no production
  caller); F2 INFO (merged ticket numbers restart per segment).
* Dynamic evidence: suite 551 at audit time (565 with the audit's own
  battery by day end), 14-test fresh-seed battery, Wilder fold warm-up
  convergence on real data (ATR bit-identical from warm-bar 510, RSI 465),
  year-boundary warm-up margins 5,514–6,898 bars vs 2,880 required.
* Boundary probe (real Oct 6–17 split at Oct 15 00:00):
  `CARRY_LOSS = 1` reproduced identically across two runs; the probe's own
  first-run false PREFIX_IDENTITY (17 vs 20) was a midnight-truncated window
  in the probe — fixed, disclosed, corrected re-run returns
  PREFIX_IDENTITY True (20 vs 20). The stack itself is serial-faithful;
  the surviving finding is exactly the C1 boundary-carry gap.

---

## 7. RE-CHECK CHECKLIST (when the 5-year baseline completes)

1. [ ] C1 materialized? Check 2024→25 and 2025→26 segment summaries for
      `positions_still_open > 0` at segment end; if zero, the exposure never
      fired — record that.
2. [ ] Confirm the boundary-carry disposition was ruled and applied (option a
      or b) before the final merge was signed.
3. [ ] Re-verify C2: whether any merged trade count changed after applying
      the disposition, and that the verdict watcher's coverage/byte-identity
      checks passed on all 5 segments × 2 runs.
4. [ ] Re-run E1–E6 status: which enhancements landed since 2026-09-15;
      update §4.
5. [ ] Re-confirm the suite is green at the 5-year milestone and that the
      Phase C verdict (diagnostic, NO edge claim — plan §5 interpretation
      binding) is recorded in the baseline report.
6. [ ] Confirm C3 progress: paper-runner test coverage before Phase 7 prep.
