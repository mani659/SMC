# PRODUCT RUNTIME CONTRACT — ONE MULTI-TF RUNTIME (V1)

**Status:** LOCKED — Phase 0 of the C1 ruling (Lead Architect, 2026-09-23).
**Authority:** Lead Architect instruction "Phase 0 (product contract) + Phase 1 (C1 MultiTF on live/paper + shared HTF seam)".
**Supersedes:** nothing — it makes explicit what the as-coded audit found implicit (two different detection drivers: research = multi-TF, live/paper = single-TF).
**Evidence base:** `06_RESEARCH/AS_CODED_ARCHITECTURE_FLOWCHART.md` (as-coded extraction, 2026-09-23).

---

## 1. Canonical runtime (V1)

Research, paper, and live run **the same detection → execution runtime**:

| Layer | Canonical setting | Source |
|---|---|---|
| Detection timeframes | **H4 + H1 required** (R2 minimum) | `smc/orchestration/multi_tf.py` `M8_HTF_TIMEFRAMES` / FR-1 |
| M8 HTF input | D1 supplied **when available**; H4 always shared from the detection series | FR-1 §5 / as-coded `validate_multi` auto-share |
| Execution timeframe | **M5 primary** (M1 only where already coded as trigger/LTF context; no new M1-exec product) | LOCKED §21/§22, FR-1 |
| Path | multi-TF detect → merge/validate/arm → LTF trigger scan → RiskEngine → place/intent → manage | as-coded pipeline |

The **per-bar execution loop is unchanged** (M5 bars, `PaperRunner.run_one_cycle` /
`BacktestRunner.on_bar`). Only the *detection cadence* is product-defined: **one multi-TF batch per new H1 close**
(the cadence the accepted research chain already uses).

## 2. The one-driver rule (shared seam)

Public API — **the only sanctioned detection/arming entry point**:

* Module: `smc/orchestration/multi_tf_runtime.py`
* `MultiTFProductRuntime(*, execution_timeframe=M5, detection_timeframes=(H4, H1), optional_timeframes=(D1,), atr_period=14, allow_single_tf_degraded=False, supply_d1_to_m8=True)`
* `MultiTFProductRuntime.build_htf_prefixes(series_by_tf, as_of)` — honest prefixes (bars with `timestamp <= as_of`)
* `MultiTFProductRuntime.run_batch(*, engine, series_by_tf, as_of, arm_bar, adapter=None, execution_candles=None, dedup=None) -> MultiTFBatchReport`
* `smc.orchestration.multi_tf_runtime.ZoneDedup` (shared geometry dedup: same direction + overlapping zone = one episode)
* Live: `LiveLoop` runs the batch through this runtime on each new H1 close (`LiveLoop._detect_and_arm`).
* Paper: `PaperRunner.arm_multi_tf(series_by_tf, *, as_of=None, arm_bar=None, execution_candles=None)` delegates to the same runtime.
* Research: scripts call `MultiTFProductRuntime.run_batch` (parity smoke: `06_RESEARCH/scripts/c1_multi_tf_parity_smoke.py`).

`MultiTFDetectionDriver.validate_multi` remains the single detection implementation — the runtime is a **facade**, not
a second stack (no forked detection, no copied thresholds).

## 3. Loud-fail policy (missing HTF)

1. **Product mode (default):** a batch whose required H1/H4 series are missing, empty, or unreadable raises
   `MultiTFProductRuntime`'s `MissingHtfSeriesError` naming every missing timeframe. The batch arms **nothing**.
2. **No silent degradation:** `allow_single_tf_degraded` defaults to `False` in live/operator and paper. With it `False`
   there is **never** a single-TF detect fallback.
3. **Explicit degraded mode (tests only):** `allow_single_tf_degraded=True` opts into the legacy single-TF
   `DetectionDriver.validate_window` path; the batch report is stamped `degraded=True` with a reason and the mode is
   logged. Operator config exposes the flag but the shipped config keeps it `false`.
4. **Start gate:** `LiveLoop.start()` refuses to start (returns False, logs the reason) when the runtime is in product
   mode and an HTF probe returns no usable H1/H4 series. A live session must never begin half-provisioned.
5. **Mid-session failure:** a batch that fails loudly is recorded (`arm_errors`, `last_arm_error`) and the session keeps
   polling — repeated loud errors, no fallback, no silent single-TF detection.
6. **Single-TF detect+exec is prohibited by contract:** an operator config whose `detection_timeframes` collapse onto the
   execution timeframe is rejected unless degraded mode is explicitly requested.

## 4. Non-goals (V1)

* Redis / event-bus / distributed state — in-memory stores stay.
* ADX gate / ATR-floor gate (`ADX_MIN_ENTRY`, `ATR_FLOOR_MIN_SL` stay unimported until ruled).
* Trigger D (volume-less dataset — unchanged).
* Structural TP feed (TP stays the FR-2 4×ATR fallback until a trigger emits a structural target).
* Full ActiveDraw / visualization work.
* Any locked-constant edit, pillar change, trigger-geometry change, R7/R8/R9 threshold change, or zone-band widening.

## 5. Acceptance tests (mirror Phase 1 test file)

`04_SRC/tests/test_multi_tf_product_path.py`:

1. `run_batch` raises `MissingHtfSeriesError` when H4 (or H1) series is missing/empty and degraded=False.
2. Degraded=True allows the single-TF fallback, stamps `degraded=True` + reason, and arms nothing silently.
3. Synthetic H1+H4(+D1) fixtures: `run_batch` returns a structured report (per-TF counts, no exception,
   `single_tf_detect_exec=False`) and can arm into a real `PipelineEngine`.
4. Shared dedup: a re-detected identical zone is skipped (`duplicates`), never double-armed.
5. `LiveLoop` (fake connector) invokes the multi-TF batch on a new H1 close and not twice within the same H1 bar.
6. `LiveLoop.start()` refuses when HTF is unavailable in product mode; degraded=True starts.
7. `PaperRunner.arm_multi_tf` delegates to the shared runtime (spy) and requires a real engine.
8. Operator config: `detection_timeframes` + `allow_single_tf_degraded` accepted/validated; detect==exec rejected.
9. Existing single-TF/multi-TF unit tests remain green (no regression).

## 6. Residuals (recorded after implementation)

* **R9 paper parity** — intents already exist in `PaperRunner` (shared `IntentBook`); this task does not extend them.
* **News calendar** — §11 remains `news_events=[]` (dormant by config; unchanged).
* **Structural TP** — still the 4×ATR fallback (unchanged).
* **HTF depth** — live fetches a bounded HTF window (`htf_window_bars`, default 300 bars per TF); deep-history
  warm-up is not provisioned in V1 (documented).
* **Cold start** — the live loop still anchors to the latest bar and does not replay history (unchanged).
* **Research scripts** — FR-4b/FR-4 evidence scripts are left frozen; the parity smoke is the bridge proving the
  shared seam on real data.

## 7. Pointers

* Implementation: `smc/orchestration/multi_tf_runtime.py`, `smc/live/loop.py`, `smc/paper/runner.py`,
  `smc/live/operator_config.py`, `smc/live/run_operator.py`
* Evidence/notes: `06_RESEARCH/C1_MULTI_TF_PRODUCT_PATH_NOTE.md`
* Governance: `00_LOCKED/SESSION_HANDOFF.md`, `00_LOCKED/POST_V1_ACTIVE_TODO.md`, `00_LOCKED/CHANGELOG.md`

## 8. Silent / deferred policy table (Track A residual C4, 2026-09-24)

Formal disposition of the three silent gates (design record: `06_RESEARCH/RESIDUAL_A_E1_C3_C4_NOTE.md`):

| Gate | Disposition | Basis (as-coded) |
|------|-------------|------------------|
| News §11 | **DEFERRED** | Gate plumbing exists (`EntryRequest.news_block`) but no calendar ingestion in `04_SRC`; configs ship `news_events=[]`. Requires an operator-supplied external calendar before it can be proven live — no synthetic calendar (hard ban). |
| Spread §28.5 | **WIRED (operator input)** | `spread_price` is threaded end-to-end: `LiveConfig`/`RunnerConfig` → `EntryRequest.current_spread_price` → ATR-relative grading vs `effective_max_spread(score, atr)`; operator whitelist in `live/operator_config.py`. Wiring is proven; the VALUE is operator-supplied. |
| Sweep guard | **DEFERRED** | Guard + plumbing implemented and dormant (`risk/sweep_guard.py`, `EntryRequest.sweep_level`); NO trigger emits a sweep level today. Requires a trigger-level real sweep attribution — none invented. |
| Structural TP (C3) | **DESIGNED / UNFED** | `resolve_take_profit` structural branch is wired and unit-tested; no trigger emits a structural target in V1, so TP stays the frozen 4×ATR fallback (FR-2 R4). Validity definition + no-invention ruling in the note (§C3). |
| entry_anchor (E1) | **EXPORTED** | First-class `entry_anchor` provenance on candidate → order → position → `TradeRecord` → CSV/JSON (appended, backward compatible); preserved through `modify_sl` (E1, Track A). |

**Standing statement:** product runs with `news_events=[]` and `spread_price=0.0` remain
**diagnostic** — news/spread/sweep-guard are NOT "gates proven live" until a real operator feed
(calendar / spread series / trigger sweep attribution) exists. Structural TP remains the 4×ATR
fallback until a trigger honestly emits a structural target under the §C3 validity rules.

**BASELINE FROZEN (2026-09-24):** this runtime is the frozen V1.1 baseline — see
`00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md`. Changes to locked constants, pillars, triggers,
zone bands, or R7/R9 require a dated ruling in that file or `POST_V1_PLAN_OF_ACTION.md`.

## 10. Amendment 2026-10-21 — ESSENCE M1 path (F1 ruling, Architect)

**Architect F1 ruling (2026-10-21), under the SIGNED `00_LOCKED/ESSENCE_CONTRACT_V1.md` 
(Owner Salman + Architect sign-off):** the older **"no M1-exec product"** line in §1 is
**SUPERSEDED FOR THE ESSENCE PATH ONLY**. A parallel essence product path MAY
**detect/confirm/enter on M1** (`ESSENCE_SLICE` — `04_SRC/smc/essence/**`), executing the
signed picks: entry TF **A (M1 sniper)**, LIMIT-style entry inside the HTF zone, confirm
set **C** (ending diagonal primary) read on M1, SL band **B** (2–5 pips beyond the M1
structure), TP **D** (macro HTF target with the hard 1:5 gate), PureRunner BE **ON**
(1.0 × ATR, 100 % runner).

Scope and limits of this amendment (verbatim intent):

* **The COMPLEX / V1.1 baseline is untouched and remains M5-oriented** — §1's canonical
  runtime, the per-bar M5 execution loop, the one-driver rule, the loud-fail policy and the
  §4 non-goals all stand unchanged for the COMPLEX path. COMPLEX stays the frozen
  comparison baseline (`00_LOCKED/BASELINE_COMPLEX_V1_1_COMPARISON_POINT.md`, `b5e8c53`).
* **The essence path is a parallel package** (`smc/essence/**`) — not a branch inside the
  COMPLEX spine, no `if essence:` anywhere outside the package, and its only shared code is
  read-only reuse (M8 zone scan, structural swings, wave-structure ending diagonal, the
  locked conservative fill model, PureRunner, the frozen §21/§23/§26/§28.1 constants).
* **The essence path is diagnostic** — expert stage-scoring recall (§8 rubric), no PF
  optimisation, no edge claim, and the fallback boundary-sweep family is OUT of the v1
  build (signed "include later").
* Locked constants are **not edited**: the signed values this wiring relies on
  (`M8_SL_MIN_PIPS`/`MAX_PIPS` 2.0/5.0, `M8_MIN_RR` 5.0, `M1_EXPIRY_BARS` 30,
  `PURE_RUNNER_BE_ATR`/`BUFFER` 1.0/0.10) already exist and are consumed read-only by the
  essence path. Any change is a dated amendment, one rule at a time.

Mapping evidence for each rule: `06_RESEARCH/ESSENCE_V1_CODE_MAPPING.md` (REQUIRED
FOLLOW-UP list, F1–F12 — F1 is resolved by this amendment; the remaining items rule per
leg). Implementation record: `06_RESEARCH/ESSENCE_V1_SLICE_NOTE.md`.

## 9. Residual engineering (Track A) scope

In scope and closed by Track A: E1 entry_anchor export (done). Explicitly out of scope:
C3 feed implementation (unfed — no real source), news calendar ingestion, sweep-level trigger
attribution, any new constants, any threshold/band/geometry change.
