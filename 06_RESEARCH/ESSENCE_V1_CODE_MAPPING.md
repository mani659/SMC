# ESSENCE v1 — CODE MAPPING (signed contract → existing modules)

**Banner: MAPPING — NOT FULL IMPLEMENTATION**

**Date:** 2026-10-21 · **Authority:** Architect 2026-10-21 (mapping leg)
**Contract:** `00_LOCKED/ESSENCE_CONTRACT_V1.md` — **SIGNED 2026-10-21**
(Owner Salman + Architect). Signed picks: entry TF **A (M1 sniper)** · SL
**B (2–5 pips beyond M1 structure)** · TP **D (Model 8 profile, min 1:5)** ·
PureRunner BE **ON** (1.0×ATR → BE, 100% runner) · confirm set **C (M8
preferred set: ending diagonal / M1 surgical)** · fallback sweep family
**include later**.

**Scope of this leg:** read-only mapping. **No strategy code, threshold, or
`locked_constants.py` value was changed.** `04_SRC/smc/**` diff: **empty**.
`locked_constants.py` diff: **empty**. This document *lists* the required
follow-up edits; it does **not** make them. No COMPLEX rewrite is proposed or
performed here.

**How to read a status:** `READY` = the contract rule is implemented as signed
today · `PARTIAL` = implemented but with a scope/availability shortfall ·
`MISSING` = no implementation exists · `CONFLICT` = something else is
implemented and it contradicts the signed rule (a ruling is required before
the code can honour the contract).

---

## 1. Stage-by-stage mapping

### 1.1 Level — HTF institutional zone, first touch (contract §1)

| Contract rule | Existing module/path | Status | Gap to close (one sentence) |
|---|---|---|---|
| Level = D1/H4 institutional zone (Demand/Supply, OB or FVG; single last opposing candle; full wick range; wicks included) | `04_SRC/smc/poi/models/m8_htf_demand_supply.py` (`M8HtfDemandSupply._zones` → `zone_for_candle`, `smc/poi/base_model.py`); wired via `04_SRC/smc/orchestration/multi_tf_runtime.py` (`MultiTFProductRuntime._build_driver` → M8_HTF_TIMEFRAMES supply) | **READY** | None for the geometry — D1/H4 zones are emitted today (`HTF_TIMEFRAMES = (W1, D1, H4)`); **but** D1 is an *optional* series (`OPTIONAL_D1_TIMEFRAME`), so with no D1 provisioning the level set silently shrinks to H4. |
| Level = **H1** institutional zone | `04_SRC/smc/poi/models/m8_htf_demand_supply.py` (M8 never scans H1) | **MISSING** | M8's scanner covers W1/D1/H4 only, so the signed **H1** level has no single-last-opposing-candle emitter — either the v1 level set is narrowed to D1/H4 (W1 context) by amendment, or M8's scanner is extended to H1. |
| Level is tradeable once (strict 1-touch freshness) | `04_SRC/smc/validation/pillar_4_freshness.py` + `04_SRC/smc/validation/state_machine.py` (CREATED/FRESH only) | **READY** | None — state-machine driven, no second-touch trades. |
| Level timeframes are D1/H4/H1 only (M30/M15/M5/M1 are not level TFs) | `04_SRC/smc/poi/model_registry.py` + `04_SRC/smc/orchestration/multi_tf.py` (M1–M7 run on the H4/H1 detection series) | **READY** | None — the product detection set is already HTF-only. |

### 1.2 Sweep — wick pierces, candle closes back inside (contract §2)

| Contract rule | Existing module/path | Status | Gap to close (one sentence) |
|---|---|---|---|
| A sweep = wick pierces the level **and** the candle closes back inside; a close-through is a breakout, not a sweep | `04_SRC/smc/detection/sweep_detector.py` (`detect_sweep` / `detect_sweeps` — `high > level and close < level`, mirrored) | **READY** | None — the close-through case is excluded by construction, not by a flag. |
| Only structural levels qualify (EQH/EQL ≤ 4.5 pips; session / PDH-PDL / PWH-PWL; §19-validated swings) | `04_SRC/smc/detection/liquidity_scanner.py` (`ALL_FAMILIES = ("session","periodic","equal","structural")`), `eqh_eql_detector.py` (`EQH_EQL_TOLERANCE = 4.5`), `structural_swing_detector.py` (§19 gate) | **READY** | None — all four coded families are structural. |
| **The swept level is the POI zone of §1** | `04_SRC/smc/detection/liquidity_scanner.py` (no `poi` / `demand_supply_boundary` / `order_block_boundary` family) | **MISSING** | The product path sweeps **liquidity levels**, never the **POI zone** — the contract's "sweep of the level" link has no runtime implementation (it exists only in research: `06_RESEARCH/scripts/poi_swept_ltf_confirm.py`), so a zone-sweep verdict must be added to the v1 path. |
| Sweep is a hard prerequisite (shipped) | `04_SRC/smc/orchestration/detection_driver.py` (`attribute_displacement`) + `04_SRC/smc/validation/pillar_2_displacement.py` | **CONFLICT** | A POI with no same-direction sweep gets no displacement and is **rejected** by Pillar 2, which is stricter than the signed contract (the contract mandates no displacement veto) — the v1 path needs the veto relaxed or the contract amended. |

### 1.3 Confirmation — signed set C: ending diagonal (primary) / F / D / A (contract §3)

| Contract rule | Existing module/path | Status | Gap to close (one sentence) |
|---|---|---|---|
| Primary confirm = ending diagonal (Trigger C) at the zone | `04_SRC/smc/triggers/trigger_c_ending_diagonal.py` + `smc/triggers/wave_structure.py` | **READY** | None — the detector exists and M8 × C is the frozen PREFERRED cell (`compatibility_matrix.py`, ✓★). |
| Alternates = BOS+OB (F), two-bar engulfing (D), CHOCH (A) | `04_SRC/smc/triggers/trigger_f_bos_ob.py`, `trigger_d_two_bar.py`, `trigger_a_choch.py` | **PARTIAL** | F and A are usable, but **Trigger D is dead on the volume-less feed** (`engulfer.volume < engulfed.volume` ⇒ no signal, `trigger_d_two_bar.py:57`) — D is unavailable as a v1 alternate until a volume-free variant is ruled. |
| **Only** the signed set may confirm (C/F/D/A); B (leading diagonal) and E (RSI divergence) are excluded | `04_SRC/smc/triggers/trigger_router.py` (scans **every** matrix-eligible trigger, chronological first-valid) + `04_SRC/smc/triggers/compatibility_matrix.py` (all cells ALLOWED; grades only break same-bar ties) | **MISSING** | The router has no allow-list — B and E can complete a v1 trade today, so a per-route confirm allow-list (set C) must be added to the v1 path. |
| Confirm is read on **M1** ("M1 surgical") | `04_SRC/smc/triggers/trigger_router.py` (the router scans the **execution-timeframe** series) | **CONFLICT** | The router only ever sees the execution timeframe (M5 in the shipped product), so the M1 read cannot happen until the entry-TF change of §4 is executed. |
| DUMB's mid-reclaim is **not** a confirmation | `04_SRC/smc/dumb/rules.py` (`is_confirm` = close strictly through the zone midpoint), `smc/dumb/runner.py` (market entry at confirm close, fixed 2R) | **READY (excluded by contract)** | None — DUMB stays a default-OFF research probe; the ban is enforced by keeping the DUMB path unwired from the product confirm path, and it is restated here so no later leg mistakes it for set C. |

### 1.4 Entry — LIMIT at the confirmation level, M1 (contract §4)

| Contract rule | Existing module/path | Status | Gap to close (one sentence) |
|---|---|---|---|
| Entry = **LIMIT** at the confirmation level, inside the zone, never a market order | `04_SRC/smc/triggers/base_trigger.py` (every trigger emits `entry_price` as a limit; `entry_within_zone` FR-3 gate; `zone_anchored_entry` FR-3.1 anchor), `04_SRC/smc/backtest/orders.py` (`PendingOrderBook` — limit book only), `04_SRC/smc/execution/order_manager.py` (`OrderRequest(kind=LIMIT)`) | **READY** | None — there is no market-order path in the product. |
| Entry timeframe = **M1** | `04_SRC/smc/live/operator_config.py` (`timeframe` default `"M5"`), `config/live_demo.json` (`"timeframe": "M5"`), `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` §1 ("no new M1-exec product") | **CONFLICT** | The product runtime executes on **M5** and the locked runtime contract forbids an M1-exec product, so M1 execution needs a **dated runtime-contract amendment**, M1 series provisioning (MT5 `Timeframe.M1 = 1` is a valid MT5 TF, so the data layer can serve it) and the expiry switch to the M1 rule. |
| Unfilled limit expires (12-bar resting window); first-valid-wins; one zone + one confirm + one trade | `04_SRC/smc/validation/state_machine.py` (`expiry_bars_for`) + `locked_constants.M5_EXPIRY_BARS = 12` / `M1_EXPIRY_BARS = 30`; one-shot via `smc/orchestration/engine.py` episode + `smc/orchestration/multi_tf_runtime.py` (`ZoneDedup`, owner-keyed) | **PARTIAL** | The §23 window is **per execution timeframe** (M1 = 30 bars once the TF lands) and the R8 policy already overrides it for HTF-detected POIs (M8 = 48 runner bars, `04_SRC/smc/risk/fill_regime_policy.py`) — the signed 12-bar window needs an explicit R8-interaction rule. |
| No spray: one trade per zone | `ZoneDedup` (geometry + owner lifecycle) + engine episode one-shot | **READY** | None. |

### 1.5 Stop loss — 2–5 pips beyond the M1 structure (contract §5)

| Contract rule | Existing module/path | Status | Gap to close (one sentence) |
|---|---|---|---|
| SL = 2–5 pips beyond the M1 structure | `04_SRC/smc/config/locked_constants.py` (`M8_SL_MIN_PIPS = 2.0`, `M8_SL_MAX_PIPS = 5.0`) — **declared but referenced nowhere in `04_SRC/smc`** (only asserted in `04_SRC/tests/test_locked_constants.py`) | **MISSING** | The 2–5 pip band has **no implementation at all** — the band must be enforced on the M8 route's SL derivation, with pip→price conversion via `04_SRC/smc/utils/pips.py`. |
| Stop anchored to the **M1** structure (swing extreme / wave-5 terminal wick) | `04_SRC/smc/triggers/trigger_c_ending_diagonal.py` (`stop_reference = diagonal.terminal_level`), `trigger_a_choch.py`, `trigger_f_bos_ob.py` | **READY** | None for the anchor — but the reference is only M1-scale once the execution TF is M1 (§4 above). |
| The 0.3 × ATR buffer rule is **not** the v1 rule | `04_SRC/smc/triggers/base_trigger.py` (`structural_sl`, `FR2_SL_BUFFER_ATR = 0.3` — interim, not a locked constant) | **CONFLICT** | The shipped stop is "structure + 0.3 × ATR" (inventory-recorded honest stops ≈ 0.82–0.89 × ATR), which is a different rule from "2–5 pips" — replacing it on the M8 route is a REQUIRED FOLLOW-UP (**listed only**, no constant edited here). |

### 1.6 Take profit — Model 8 profile, minimum 1:5 (contract §6)

| Contract rule | Existing module/path | Status | Gap to close (one sentence) |
|---|---|---|---|
| TP = M8 profile, **minimum 1:5** risk:reward | `04_SRC/smc/config/locked_constants.py` (`M8_MIN_RR = 5.0`) — **declared but referenced nowhere in `04_SRC/smc`** | **MISSING** | There is no RR gate anywhere in the runtime — a 1:5 minimum is neither checked nor enforced, so the v1 path needs a hard RR blocker (value already frozen; only the check is missing). |
| A target that can **reach** 1:5 exists (macro HTF target) | `04_SRC/smc/backtest/pipeline_bridge.py` (`resolve_take_profit` → structural target else 4 × ATR; `structural_tp_target` = first-swing selector, **wired but UNFED** — no trigger emits a structural target) | **MISSING** | The shipped TP is a 4 × ATR cap and no trigger emits a structural/HTF target, so no target source can satisfy 1:5 today — the slice must feed a target (the unfed `structural_tp_target` is the nearest existing seam). |
| The 4 × ATR fallback must not silently stand in for a 1:5 target | `04_SRC/smc/backtest/pipeline_bridge.py` (`resolve_take_profit`, `FR2_TP_ATR_MULTIPLE = 4.0`) | **CONFLICT** | With a 2–5 pip stop the 4 × ATR cap lands near ≈ 4.5–4.9 R (inventory-recorded honest stops ≈ 0.82–0.89 × ATR) — i.e. just **under** 1:5, so keeping the fallback silently violates the signed rule; the slice must **block**, not degrade (to be measured in the slice, not assumed). |

### 1.7 Manage — PureRunner break-even ON, 100% runner (contract §6)

| Contract rule | Existing module/path | Status | Gap to close (one sentence) |
|---|---|---|---|
| BE ON: after a 1.0 × ATR favourable move, SL → break-even | `04_SRC/smc/risk/pure_runner.py` (`be_moved_sl` / `mark_be_applied`, per-trade latch) + `04_SRC/smc/risk/risk_engine.py` (`evaluate_exit` → `MOVE_SL`) + `locked_constants.PURE_RUNNER_BE_ATR = 1.0`, `PURE_RUNNER_BE_BUFFER_ATR = 0.10` | **READY** | None — the signed numbers already match the frozen constants. |
| 100% runner — no partial closes, the position runs to its target | `04_SRC/smc/risk/pure_runner.py` ("V1: NO early partials") + `risk_engine.py` (no partial-close API) | **READY** | None. |
| The position runs to its 1:5 target | `04_SRC/smc/risk/risk_engine.py` (`evaluate_exit` → FVG structural invalidation closes the trade on a closed-bar FVG breach) | **CONFLICT** | The shipped FVG invalidation can close a v1 trade before its target and it is **not on the signed §6 page** — it must be added to §6 by dated amendment or scoped out of the v1 slice (it bites only on F-routed trades, and F is in the signed set). |
| Stop scoring reads the **placement** stop, not the BE-mutated one | `04_SRC/smc/backtest/pipeline_bridge.py` (`candidate_from_route` → `original_sl` = placement SL, never mutated) + export/identity patch | **READY** | None — `original_sl` is already preserved for the expert's stage-5 mark. |

### 1.8 Contract-wide exclusions and silence (contract §7, §3)

| Contract rule | Existing module/path | Status | Gap to close (one sentence) |
|---|---|---|---|
| §7: the **five pillars are not hard vetoes** in v1 | `04_SRC/smc/validation/validation_pipeline.py` (pillars 1–4 hard, 5 soft) + `detection_driver.py` / `multi_tf_runtime.py` (every POI is validated before arming) | **CONFLICT** | Every product POI is pillar-gated today, so the signed "not a hard veto" exclusion needs an explicit pillar-relaxation switch (a mode flag, not a threshold change) or a dated amendment. |
| §2: the **fallback boundary-sweep family is OUT of the v1 build** (signed "include later") | `04_SRC/smc/detection/liquidity_scanner.py` (families: session, periodic, equal, structural — **no** `demand_supply_boundary` / `order_block_boundary`) | **MISSING (deferred by signature)** | No emitter exists for the locked §2 rules 5–6 family — it must stay out of the v1 build and, when it is built later, it needs a **new detector**, not a config flip. |
| §3: **DUMB mid-reclaim ≠ confirm set C** (DUMB is a research proxy, default-OFF) | `04_SRC/smc/dumb/rules.py` (`is_confirm` = close strictly through the zone midpoint) + `smc/dumb/runner.py` (market entry at confirm close; fixed 2R) | **READY (excluded by contract)** | None — DUMB's mid-reclaim is explicitly **not** one of the signed set-C patterns and must never be substituted for them; the ban is restated here so no later leg mistakes it for set C. |
| §7: news-calendar gating is out of v1 | `04_SRC/smc/execution/news_guard.py` + `04_SRC/smc/risk/risk_engine.py` (`hard_cancel_pending`) | **PARTIAL (shipped ON)** | The shipped runtime enforces the §11 news guard while the signed page excludes news gating — one dated amendment must either restore it on the page or scope it out. |
| The risk/environment layer (session filter, circuit breaker, same-level guard, sweep guard, spread grading, lot sizing, Friday EOD) is **not on the signed page** | `04_SRC/smc/risk/risk_engine.py`, `smc/risk/*.py`, `smc/execution/session_filter.py` | **PARTIAL** | The shipped runtime blocks entries and force-closes on rules the contract never mentions, so the expert would score trades that were blocked for unstated reasons — the v1 page must state them (or scope them out) by dated amendment. |
| One product runtime for research = paper = live | `04_SRC/smc/orchestration/multi_tf_runtime.py` (`MultiTFProductRuntime`) + `smc/paper/runner.py` + `smc/live/run_operator.py` | **READY** | None — the v1 slice must run through this one seam; no parallel stack is proposed. |

---

## 2. Gap summary

| Status | Count | Rows |
|---|---|---|
| MISSING | 7 | H1 level · POI-zone sweep link · confirm allow-list (set C) · 2–5 pip SL band · 1:5 RR gate · 1:5-capable target source · fallback sweep emitter (deferred) |
| CONFLICT | 7 | sweep→displacement hard veto · M1 confirm read · M1 execution TF · 0.3×ATR SL buffer vs 2–5 pips · 4×ATR TP fallback vs 1:5 · FVG invalidation vs "run to target" · 5 pillars as hard vetoes |
| PARTIAL | 4 | Trigger D volume-dependence · §23/R8 resting window · news guard on/off · risk-layer silence |
| READY | 19 | (all other rows) |
| **Total gap rows (non-READY)** | **18** | |

**Read:** the signed contract is **mostly implementable on top of what exists** —
the detection, ordering, freshness, limit, risk and BE machinery is all
present and frozen. What is missing is concentrated in three places: (1) the
**M1 execution slice** (TF switch + M1 confirm read), (2) the **money rules**
(SL band, 1:5 target + gate), and (3) the **contract-shaped gates** (set-C
allow-list, zone-sweep link, pillar relaxation). The four CONFLICT rows are
where the code and the signed page currently disagree — each needs a dated
ruling, not a quiet edit.

---

## 3. REQUIRED FOLLOW-UP edits (LIST ONLY — none made in this leg)

**No `locked_constants.py` value changes are proposed.** The three signed
numbers already exist and already match: `M8_MIN_RR = 5.0` (§21),
`M8_SL_MIN_PIPS = 2.0` / `M8_SL_MAX_PIPS = 5.0` (§21/§26),
`PURE_RUNNER_BE_ATR = 1.0` + `PURE_RUNNER_BE_BUFFER_ATR = 0.10` (§28.1).
What is missing is their **enforcement path**, not their value.

Follow-ups that would touch a locked artefact (each needs a dated ruling
before any code edit):

| # | Follow-up | Artefact | Why |
|---|---|---|---|
| F1 | M1 execution timeframe (contract §4 pick A) | `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` §1 ("M5 primary… no new M1-exec product") + `LOCKED_DECISIONS.md` §4a | The signed entry TF contradicts the shipped runtime contract; a dated amendment is the only honest way to change it. |
| F2 | Resting window: signed 12 bars vs §23-per-TF (M1 = 30) vs R8 (H1 36 / HTF 48) | `04_SRC/smc/risk/fill_regime_policy.py` (R8 table) + `locked_constants.M5_EXPIRY_BARS`/`M1_EXPIRY_BARS` | The signed window is stricter than both shipped rules; the interaction needs a ruling (block-new? tighten M8 routes?) — no constant edited here. |
| F3 | SL: replace "structure + 0.3 × ATR" with "2–5 pips beyond M1 structure" on the M8 route | `04_SRC/smc/triggers/base_trigger.py` (`FR2_SL_BUFFER_ATR` — **interim**, not a locked constant) + `locked_constants.M8_SL_MIN_PIPS/MAX_PIPS` (frozen, activation only) | The two rules differ by roughly an order of magnitude on gold; activation must be explicit and dated. |
| F4 | TP: feed a macro/HTF target and add the hard 1:5 gate | `04_SRC/smc/backtest/pipeline_bridge.py` (`resolve_take_profit`, `structural_tp_target`) + `locked_constants.M8_MIN_RR` (activation only) | The 4 × ATR fallback must not silently substitute for a 1:5 target. |
| F5 | Confirm allow-list (set C: C/F/D/A; B and E excluded) | `04_SRC/smc/triggers/trigger_router.py` + `smc/triggers/compatibility_matrix.py` | A code-level allow-list, **not** a new threshold — the §15 matrix stays frozen; only the v1 route filter is added. |
| F6 | Zone-sweep verdict (contract §2) + Pillar-2 coupling decision | `04_SRC/smc/detection/` (new detector) + `smc/validation/pillar_2_displacement.py` (coupling) | The zone sweep has no emitter; and the shipped sweep→displacement veto is stricter than the contract. |
| F7 | Pillar relaxation (contract §7: not hard vetoes) | `04_SRC/smc/validation/validation_pipeline.py` | A mode flag on the v1 path, not a threshold change. |
| F8 | FVG invalidation: keep in v1 (and put it on the §6 page) or scope it out | `04_SRC/smc/risk/risk_engine.py` | It can close a trade before its 1:5 target; the signed page does not mention it. |
| F9 | Risk/environment layer disclosure (session, breaker, same-level, sweep guard, spread, sizing, Friday EOD) | `00_LOCKED/ESSENCE_CONTRACT_V1.md` (dated amendment) | The expert scores the sample — the page must say what else can block or close a trade. |
| F10 | News guard: in or out of v1 | `smc/execution/news_guard.py` | §7 says out; the shipped runtime has it on. |
| F11 | H1 level geometry (keep H1 in the level set, or narrow to D1/H4) | `smc/poi/models/m8_htf_demand_supply.py` (`HTF_TIMEFRAMES`) | H1 is signed but M8 does not scan H1. |
| F12 | Trigger D: rule a volume-free two-bar variant, or drop D from the signed set | `smc/triggers/trigger_d_two_bar.py` | D is dead on the volume-less XAUUSD feed. |

**Out of scope by instruction:** no COMPLEX rewrite, no silent threshold
change, no behavior change in this leg.

---

## 4. Recommended implement order

**Target:** the smallest vertical slice that can **open and manage one trade
type** end-to-end for expert review — one setup, one rule set, one readable
sample.

**The slice (W5):** *M8 HTF zone (D1/H4) → zone sweep → ending-diagonal
confirmation on M1 → LIMIT inside the zone → SL 2–5 pips beyond the M1
structure → macro target with a hard 1:5 gate → PureRunner BE at 1.0 × ATR,
100% runner.* **One setup type. One concurrent position. No spray. Paper mode
only. Through the one product runtime seam** (`MultiTFProductRuntime`) — never
a parallel stack.

| # | Work item | Contents | Done when |
|---|---|---|---|
| **W0** | Ruling leg (no code) | F1–F12 ruled on and dated | Every CONFLICT row above has a dated ruling; W1–W5 can then be specified exactly. |
| **W1** | **M1 read, dry (no orders)** | M1 series feed (MT5 `Timeframe.M1 = 1`; resample fallback) + the existing trigger stack (C only) evaluated on M1 for M8 POIs | On the frozen window (2025-06-01 → 2025-11-30, the census window) the M8 POI set produces an inspectable list of M1 ending-diagonal candidates, and **zero** orders are placed. |
| **W2** | **Confirm allow-list (set C)** | Restrict the v1 route to C/F(/D when volume-free)/A | B and E can no longer complete a v1 route; a unit test proves it. |
| **W3** | **Zone-sweep link** | Zone sweep verdict per M8 POI (wick pierce + close back inside the zone) + the Pillar-2 coupling decision (F6) | Every v1 candidate carries a reproducible sweep verdict. |
| **W4** | **The money rules** | SL band 2–5 pips (F3) + macro target source (F4) + hard 1:5 gate (F4) | Every candidate carries `sl_pips ∈ [2,5]`, a target, and `RR ≥ 5` — or it is blocked with a machine-readable reason. |
| **W5** | **THE EXPERT-REVIEW SLICE** | W1–W4 assembled into one trade type, opened and managed end-to-end in paper mode, one concurrent position | A small readable sample of closed trades, each with the six-stage expert score sheet of contract §8 attached, in which a wrong entry TF can be marked **WRONG**. |
| **W6** | **Fallback sweep family (include later)** | Deferred **after** the W5 review — a new detector | Not started in this milestone; stays out of the v1 build. |

**Sequencing rationale:** W1 is the cheapest and de-risks the most (if M1
ending-diagonals never appear on M8 zones, the whole slice is wrong and the
owner should know before any money rule is written). W2/W3 are small and
independent. W4 is where the contract's economics live, so it is written once,
against the signed numbers, with the RR gate measurable. W5 is the first
moment a trade can exist end-to-end. W6 is last because the family is signed
**out** of v1 and must not leak into the reviewed sample.

---

## 5. How the slice will be verified

- **Reuse the accepted harness** — `06_RESEARCH/scripts/phase_c_baseline_backtest.py`,
  `product_baseline_pilot.py`, `phase3_structure_funnel.py` and the frozen
  6-month window, so the slice is comparable to the existing funnel reports.
- **Existing suite stays green** — `cd 04_SRC && python -m pytest tests -q` re-run in this leg: **1255 passed, EXIT=0** (the DUMB-implementation baseline — 1236 → 1255 — is unchanged; this leg changed no code, so it must still be 1255).
- **No silent thresholds** — any constant that moves appears in §3 first, as a
  dated ruling.
- **Expert scoring is the acceptance gate** — the W5 sample is scored with
  contract §8's rubric before any further rule is added.

---

## Return block

```
ESSENCE_MAPPING_STATUS: PASS
BANNER: MAPPING — NOT FULL IMPLEMENTATION
CONTRACT_PATH: 00_LOCKED/ESSENCE_CONTRACT_V1.md (SIGNED 2026-10-21)
MAPPING_PATH: 06_RESEARCH/ESSENCE_V1_CODE_MAPPING.md
STAGES_MAPPED: 7 (Level, Sweep, Confirm set C, Entry M1 LIMIT, SL 2-5 pips, TP min 1:5 M8 profile, PureRunner BE ON)
GAPS_N: 18 (MISSING 7 · CONFLICT 7 · PARTIAL 4 · READY 19)
GAPS_MISSING: [H1 level emitter, POI-zone sweep link, confirm allow-list set C, 2-5 pip SL band, 1:5 RR gate, 1:5-capable target source, fallback sweep emitter (deferred)]
GAPS_CONFLICT: [sweep->displacement hard veto, M1 confirm read, M1 execution TF, 0.3xATR SL buffer vs 2-5 pips, 4xATR TP fallback vs 1:5, FVG invalidation vs run-to-target, 5 pillars as hard vetoes]
FALLBACK_SWEEP: OUT of v1 build (signed "include later"; no emitter exists)
DUMB_MID_RECLAIM: NOT confirm set C (excluded by contract §3; DUMB stays default-OFF research)
REQUIRED_FOLLOW_UPS: 12 (F1-F12, list only — none applied)
LOCKED_CONSTANTS_EDITS: none (signed values M8_MIN_RR=5.0, M8_SL_MIN/MAX_PIPS=2.0/5.0, PURE_RUNNER_BE_ATR=1.0 already exist and match; only enforcement paths are missing)
IMPL_ORDER: [W0 rulings, W1 M1 read dry, W2 confirm allow-list set C, W3 zone-sweep link, W4 money rules (SL band + target + 1:5 gate), W5 expert-review slice (open+manage one trade type, paper, one position, no spray), W6 fallback sweep family (later)]
SMALLEST_EXPERT_REVIEW_SLICE: M8 D1/H4 zone -> zone sweep -> M1 ending diagonal -> LIMIT in zone -> SL 2-5 pips -> macro target RR>=1:5 -> PureRunner BE 1.0xATR, 100% runner; one setup type, one concurrent position, paper mode
COMPLEX_REWRITE: NONE
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
NEXT_READY: Essence v1 implement prompt (Architect) after W0 rulings
```

**Ledger cross-refs:** SESSION_HANDOFF 2026-10-21 (7) · CHANGELOG 2026-10-21 (7)
· `00_LOCKED/POST_V1_ACTIVE_TODO.md` mapping entry.
