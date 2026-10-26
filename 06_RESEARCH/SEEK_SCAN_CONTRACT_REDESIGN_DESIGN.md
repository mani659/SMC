# SEEK / SCAN CONTRACT REDESIGN — DESIGN NOTE (Option B, DESIGN LOCK)

**Status:** DESIGN_ONLY — written BEFORE any production code, per Lead Architect directive.
**Date:** 2026-10-05 · **Author:** local implementation agent (per dated Architect prompt)
**Ruling implemented (design only):** Lead Architect **Option B** — the current arming + one-touch seek contract is defective for the measured data; restore product visibility to Stage 3 completions that form on still-valid HTF POIs.
**Source of measured facts:** `06_RESEARCH/STAGE3_LIFECYCLE_TIMING_REPORT.md` (do not re-litigate; facts restated, no new analysis).
**Motto constraint:** we are building a bot that can trade profitably. A contract that renders 99.24% of formed Stage 3 geometry invisible is not acceptable.

---

## 1. Problem statement (measured facts only)

Current seek contract, as coded (`smc/orchestration/engine.py` `feed_bar` + `scan_route`, `smc/backtest/pipeline_adapter.py` `_may_route`, `smc/validation/state_machine.py` §5 machine, `smc/triggers/trigger_expiry.py` §24): a POI arms at the HTF structure close (`arm_bar` = first M5 bar at/after close); the trigger scan runs only while the POI is §5-FRESH, or §5-TESTED within the touch bar +1; the §24 give-up deadline is `arm_bar + poi_give_up_bars()` = arm + 20 M5 bars. Two measured failure modes make the effective seek span far shorter than the locked 20-bar horizon:

**Failure mode 1 — in-zone-at-close (199 of 263 completions, 75.67%).**
For all 199 touch-closed structures, `first_touch_ts == arm_ts`: price is already inside the HTF zone when the structure closes, so the arm bar's wick contact flips the POI §5-TESTED on the very bar it became actionable. The first-touch +1 gate then limits the scan to the touch bar and the bar after — an effective live span of `[arm, arm+1]` (two M5 bars). All 199 completions arrive later (median +11 bars after first touch; median +10 bars after scan close, p25 4.5 / p75 13.5) and are invisible to the product.

**Failure mode 2 — violation-at-arm (62 of 263 completions, 23.57%).**
For all 62 violation cases, the violation fires on the arm bar itself (`scan_close_event_ts == arm_ts`, 62/62): price closes beyond the zone on the same bar the HTF structure closes, the POI flips §5-VIOLATED before any scan opens (scan span = zero bars), and the scan never runs. Yet Stage 3 completions still form later for all 62 rows, inside the locked 20-bar horizon.

**Net effect (the two facts that define "defective"):**

1. **261/263 (99.24%)** of Stage 3 completions occur **after** the scan has closed. Only **2/263 (0.76%)** — the two F-routed rows — complete inside an open scan (OPEN_SCAN), and both complete **exactly on the last open scan bar**.
2. Trigger **F dominates** the completion population (**204/263**, 77.6%): the contract's collapse is not an edge-case of one trigger type; it silences the dominant pattern family.

The locked 20-bar horizon (`poi_give_up_bars()` = `TRIGGER_A_EXPIRY` = 20) already contains every one of the 263 completions (all sit 2–20 bars after structure close). The horizon is not the binding constraint — the seek contract's early termination is.

---

## 2. Design principles

**What the new contract preserves from the original flowchart:**

1. **HTF POI → interaction → LTF surgical trigger, still in that causal order.** The HTF zone remains the *where*; the LTF trigger completion (A–F, untouched) remains the *when* and the *how*. Nothing in this design lets a trade exist without a completed LTF trigger geometry — there is no "zone touch = entry" shortcut, and no entry without a routed `TriggerSignal`.
2. **Chronological first-valid trigger wins (§12), unchanged.** The redesign changes *when the scan is allowed to listen*, never *which trigger wins* or *how a trigger evaluates*.
3. **Invalidation is preserved — the zone can still die.** A genuine adverse close beyond the zone during a live seek still kills the episode (§5-VIOLATED semantics retained for post-arm bars). What changes is only the treatment of the **arm-bar artifacts** (in-zone-at-arm, violation-at-arm) — the two measured cases where the §5 event and the arming event coincide on one bar and the current machine reads that coincidence as a completed lifecycle.
4. **One-shot identity is sacred (§11).** One validated POI + one trigger + one execution. The redesign widens no identity, creates no second episode, and never re-routes a routed POI.
5. **All locked constants and locked windows stand.** Nothing in `locked_constants.py` changes; the outer horizon stays `poi_give_up_bars()` = 20; §23 unfilled-order expiry (M5 12 / M1 30) and every per-trigger §24 expiry (A 20 / B 30 / C +3 / D next-bar / E 15 / F first-touch) apply exactly as frozen.

**What the new contract is explicitly NOT trying to do:**

- **Not spray entries.** Route eligibility is still gated by: a completed A–F trigger geometry, that trigger's own §24 window, the give-up deadline, one-shot identity, and (new) the arm-bar revalidation gate of §3.R4. Every gate that existed survives; only the two arm-bar coincidence rules change.
- **Not ignore structure invalidation.** Post-arm adverse closes remain terminal, workflow-dropping, order-cancelling — byte-for-byte the current behaviour.
- **Not change Stage 3 pattern definitions.** Trigger A–F evaluation logic, their anchors, expiries, and signal payloads are untouched. A "completion" means exactly what it meant in the visibility audit.
- **Not widen any window.** The horizon stays 20 M5 bars from arm. The design reclaims span the horizon already grants but the seek contract currently refuses to use.
- **Not touch locked constants, pillars, risk, sizing, spread, TP/SL, PureRunner, or FVG invalidation.**

---

## 3. Proposed new rules (normative, declarative)

The lifecycle of one armed HTF POI is an **episode** with a **seek posture**. The §5 state machine (`CREATED → FRESH → TESTED/VIOLATED`, atomic transitions, terminal states) is **unchanged**; the seek posture is episode-level bookkeeping owned by the engine/adapter layer, not a new §5 state. Rules are numbered for later test mapping.

### R1 — Arming rule (unchanged behaviour, stated for completeness)

- **R1.1** A POI arms exactly as today: on HTF structure close, `arm_bar` = first M5 bar at/after the structure close (weekend/non-trading gap → first tradable bar). Episode bookkeeping (`episode.arm_bar`) is created at arm; the §5 machine moves the POI CREATED → FRESH via the existing `arm()` path.
- **R1.2** **Initial-presence classification.** On the arm bar, exactly one of three postures is recorded, derived from the arm bar's relationship to the zone (the zone geometry from validation, ± nothing — no new tolerance):
  - **R1.2a `IN_ZONE_AT_ARM`** — the arm bar's range intersects the zone (`touches_zone` semantics, inclusive, unchanged): the arm-bar wick contact is recorded as **initial presence**, NOT as a §5 touch. The POI stays FRESH and the episode posture is SEEKING.
  - **R1.2b `VIOLATION_AT_ARM`** — the arm bar closes beyond the zone on the adverse side (LONG: `close < zone.bottom`; SHORT: `close > zone.top`): the episode posture is REVALIDATION. The POI stays FRESH; the §5-VIOLATED transition is **deferred** (see R4.2). The bar that caused this is the same HTF candle that created the POI — the machine must not read the arming candle as fresh adverse LTF price action.
  - **R1.2c `CLEAN_ARM`** — neither of the above: the arm bar neither touches the zone nor closes beyond it adversely. Behaviour is exactly today's: FRESH, SEEKING, and the per-bar §5 feed governs from the next bar.
- **R1.3** **Valid first interaction vs "already in zone at close".** A "first interaction" under this contract is the **first completed A–F trigger geometry** (a Stage 3 completion), not the HTF zone wick contact. "Already in zone at close" is therefore not an interaction at all — it is a starting condition (R1.2a): the scan opens with price inside the zone, and the seek listens for the trigger geometry from the arm bar onward. The HTF zone wick contact continues to be *recorded* (feed result, telemetry, Pillar-4 freshness at validation time) but no longer *terminates the seek*.

### R2 — Scan-open rule

- **R2.1** **The scan opens at `arm_bar` for every armed POI, in all three postures.** There is no posture in which the scan does not open. (Today: failure mode 2 opens no scan; failure mode 1 opens a two-bar scan.)
- **R2.2** **In-zone-at-arm does not wait for a fresh excursion before listening.** The scan runs from the arm bar; any trigger completion at bar ≥ `arm_bar` that satisfies the trigger's own §24 window is a valid candidate. Rationale (measured, §1): the 199 in-zone rows complete at median +10 bars past the old scan close, i.e. the LTF trigger geometry forms while price works *inside or around* the HTF zone — the geometry itself is the surgical gate, and Trigger F's "first touch" refers to the trigger's own LTF OB, not the HTF zone.
- **R2.3** **Revalidation posture listens immediately but routes only after zone re-entry.** Under `VIOLATION_AT_ARM`, the scan runs from the arm bar, but a route may form only on a bar **at or after the first bar that closes back inside the zone** (re-entry geometry = the existing named rule `market_reentered_zone` in `smc/risk/fill_regime_policy.py`, reused verbatim — no new number). A trigger completion before re-entry is recorded as a completion (visibility/telemetry) but does not route.
- **R2.4** The scan is one chronological scan per episode (existing `scan_from` cursor contract): evaluations resume, never restart; no bar is evaluated twice; the first valid route consumes the one-shot (R5).

### R3 — Scan span

- **R3.1** The seek span is `[arm_bar, min(arm_bar + poi_give_up_bars(), per-trigger deadline of any live candidate)]` — i.e. the existing §24 give-up deadline computation in `scan_route`, **unchanged**. What changes is only that no §5 event *inside* that span ends the span early except the terminators in R4.

### R4 — Scan-close / invalidation rules

- **R4.1** **Terminators (any one ends the seek):**
  - **R4.1a Give-up:** bar index passes `arm_bar + poi_give_up_bars()` (= 20) → episode retires via the existing give-up backstop path (FRESH → TESTED, as in `notify_order_expired` today). No completion → no route, exactly like today's never-routed POIs.
  - **R4.1b Violation after live seek:** on any bar **after** the arm bar, an M5 close beyond the zone on the adverse side (LONG: `close < zone.bottom`; SHORT: `close > zone.top`) → §5-VIOLATED (existing `on_violation` transition, atomic, terminal). The active workflow is dropped and any resting limit is cancelled (`cancel_pending_for_poi`) — unchanged dead-thesis behaviour.
  - **R4.1c Route formed:** the one-shot fires (R5) — the seek ends in success; downstream §23/§24/R7/R8/R9 rules govern the order exactly as frozen.
- **R4.2** **Violation-at-arm vs violation-after-live-scan — the deliberate asymmetry.** An adverse close **on the arm bar** (R1.2b) defers the §5-VIOLATED transition and puts the episode in REVALIDATION; an adverse close on **any later bar** is terminal (R4.1b). Rationale, stated honestly: the arm bar's close belongs to the HTF candle whose close *created* the POI — treating it as fresh adverse LTF information double-counts the same candle and yields a zero-bar seek (measured: all 62 rows). The revalidation gate (close back inside the zone) ensures the episode cannot route while price sits beyond the zone: the zone must demonstrably hold before the thesis is tradeable. If price never closes back inside within the 20-bar horizon, the episode retires at give-up (R4.1a) — the zone has failed, and the deferred VIOLATED is realised at retirement for telemetry.
- **R4.3** **What no longer terminates the seek:** the HTF zone wick touch (§5 TESTED-by-touch) on the arm bar or any seek bar. A touch is recorded and the POI's §5 state may flip TESTED for *freshness bookkeeping* — but a §5 TESTED state inside the seek span **no longer closes the scan**. The one-touch freshness meaning is preserved where it matters for trading: §23 unfilled-order expiry still marks POIs TESTED; a routed POI is retired on its one-shot; and no POI ever routes twice. (Behaviour change vs current §5 one-touch+1 — itemised in §3.d.)
- **R4.4** **Opposite-structure / confluence events:** no new invalidation source is introduced by this design. Any existing engine-level retirement that applies to armed POIs today continues to apply; this design adds none and removes none beyond R4.3.

### R4.d / 3.d — Relationship to existing locked constants (explicit)

**Obeyed unchanged (complete list of the constants this contract touches):**

| Constant | Value | Role under the new contract |
|---|---|---|
| `TRIGGER_A_EXPIRY` | 20 M5 bars | = `poi_give_up_bars()`; outer seek horizon `[arm, arm+20]` — **unchanged** |
| `TRIGGER_B_EXPIRY` | 30 bars | per-trigger §24 window for B — **unchanged** |
| `TRIGGER_C_EXPIRY_EXTRA` | sweep + 3 | per-trigger §24 window for C — **unchanged** |
| `TRIGGER_D_EXPIRY` | 1 bar | per-trigger §24 window for D — **unchanged** (touch-bar +1 workflow grace for D preserved) |
| `TRIGGER_E_EXPIRY` | 15 bars | per-trigger §24 window for E — **unchanged** |
| `TRIGGER_F_EXPIRY` | first touch | F's window is F's own LTF first-touch rule — **unchanged** |
| `M5_EXPIRY_BARS` / `M1_EXPIRY_BARS` | 12 / 30 | §23 unfilled-order expiry, still marks POI TESTED — **unchanged** |
| `ZONE_REFINEMENT_ATR` | 0.5×ATR | R7 place-guard band + FR-3 entry gate — **unchanged**; the revalidation gate of R2.3 uses raw zone boundaries only (no tolerance, no new number) |
| `RISK_PCT_*`, `LOT_MAX_SAFETY`, §28.5 spread, TP/SL policy | frozen | untouched — downstream of the seek |

**Behaviour changed relative to current §5 one-touch +1 (complete list):**

1. **Touch no longer ends the seek.** Current: first §5 touch → TESTED → scan allowed only on touch bar + 1 (`_may_route`). New: a touch is bookkeeping; the seek continues to the give-up deadline. (Eliminates failure mode 1: effective span `[arm, arm+1]` → `[arm, arm+20]`.)
2. **Arm-bar violation no longer pre-empts the scan.** Current: arm-bar adverse close → VIOLATED → no scan ever. New: REVALIDATION posture; scan opens; routing gated on zone re-entry. (Eliminates failure mode 2: span 0 → `[arm, arm+20]`, route-gated.)
3. **Post-touch routing window removed** (subsumed by 1): the `tested_bar + 1` grace rule and the `_tested_bar` gate lose their routing role; the trigger-D next-bar contract is preserved by D's own `TRIGGER_D_EXPIRY = 1`.
4. **Nothing else.** Arming, arm anchor, give-up computation, one-shot identity, §23/§24 expiry semantics, R7/R8/R9 fill-regime behaviour, workflow submission/resubmission, dead-thesis cancellation: all byte-for-byte current behaviour.

### R5 — One-shot / episode identity (no double-routing)

- **R5.1** §11 identity is untouched: one validated POI + one trigger + one execution. The adapter's `_routed` set, `_workflows` dict, and `on_candidate_accepted` consumption behave exactly as today: the FIRST valid route creates the single workflow; a blocked risk verdict resubmits the same candidate; nothing mints a second candidate.
- **R5.2** A routed episode is closed to further seeking (scan cursor dropped, `_routed` set) — a later trigger completion on the same POI can never route. Under the wider span this matters more (more completions fall inside an open seek), so the invariant is explicit: **at most one route per episode, machine-checked** (success metric M4b).
- **R5.3** REVALIDATION episodes obey the same one-shot: the first post-re-entry valid route consumes it; the re-entry bar itself is not an identity event.
- **R5.4** R9 place-on-reentry intents (one intent per route per run, clock never refreshed) are untouched: R2.3's revalidation gate is a *pre-route* gate in the adapter/engine; R9 remains a *post-route* placement mechanism. They compose without interaction.
- **R5.5** Episode pruning (I4) semantics unchanged: terminal POIs are pruned with the same retain rules (resting orders, open positions, workflow-live, routable-window POIs — the last now meaning "inside the seek span" under the new gate).

---

## 4. Rejected alternatives

1. **Fixed N-bar extension of the post-touch window** (e.g. touch bar + N instead of +1). Rejected: N is an arbitrary magic number not derived from any locked constant or named rule (hard-ban violation by construction); it addresses only failure mode 1 — the 62 violation-at-arm rows still never get a scan; and it leaves the seek span hostage to *when* the (uninformative) arm-bar touch happens rather than to the locked horizon the data already fits inside.
2. **Remove the first-touch gate entirely / make zone touch globally non-terminal** (including for §23 order bookkeeping and Pillar-4 freshness). Rejected: it destroys §5 freshness where it still does work — unfilled-order expiry marking, validation-time freshness, and the no-second-touch guarantee for resting orders; it would allow routing after a §23-expired order on a stale zone; and it is a far larger semantic change than the measured defect requires. The chosen design instead narrows the change to *seek-window governance* and keeps the §5 machine intact.
3. **Raise `poi_give_up_bars()` beyond 20.** Rejected twice over: it is explicitly banned by this engagement's hard bans, and on the merits it is unnecessary — all 263 completions already sit 2–20 bars after structure close, inside the frozen horizon. The binding constraint is the seek contract's early termination, not the horizon; widening the horizon would be the path of least resistance that also changes a locked constant.
4. **Route immediately on in-zone-at-arm without a trigger completion** (treat "price in HTF zone" as the entry condition). Rejected: this is spray entries — it bypasses the LTF surgical trigger, violates design principle 1, and removes the very geometry (A–F completion) that Stage 3 exists to supply.

---

## 5. Success metrics for the subsequent implementation + measurement phase

All metrics are measured on the **same frozen window** as the lifecycle audit (exec 2025-06-01 → 2025-11-30, warm-up 2025-03-01), with the same inputs (accepted H4/D1 packs, canonical M1 parquet), via an instrumented replay that mirrors the production adapter semantics. Identification only — **no PnL / expectancy / edge claims**. Baselines from `STAGE3_LIFECYCLE_TIMING_REPORT.md`.

- **M1 — Visibility (primary).** OPEN_SCAN share of Stage 3 completions (completions inside the open seek span) rises from **0.76% (2/263)** to a target of **≥ 80%**, with the exact value reported. Upper bound is data-dependent: rows whose post-arm bars contain an adverse close before their completion remain hidden under R4.1b (correctly — that is genuine invalidation). The measurement must report the *reason* breakdown for every still-hidden row (violation-after-arm vs give-up-before-completion) — none may be hidden by unexplained causes.
- **M2 — No regression on routed rows.** The two currently routed rows (`s3-F-evt-ec41701aca47-25836`, `s3-F-evt-499a786ac28b-46505`) remain routable under the new contract, at the same bars (their lifecycle is untouched: CLEAN_ARM-style rows whose scans already stayed open past completion). Pre-pillar route count on the window may only stay equal or rise via newly-visible episodes — reported exactly.
- **M3 — Timing alignment.** Median(completion − scan_close) for previously CLOSED_TOUCH rows moves from **+10 bars** to **≤ +2 bars** (p75 ≤ +5); for CLOSED_VIOL rows, completions inside an open REVALIDATION seek are reported with their re-entry lag distribution. Nulls are never invented — rows still hidden by R4.1b keep the existing null-safe convention.
- **M4 — Selectivity guardrails (explosion protection).**
  - **M4a — Armed count invariant:** the armed-POI count on the window is **exactly identical** to the baseline (arming rule untouched; any difference is a defect, not a finding).
  - **M4b — One-shot invariant:** at most **one** route per episode, machine-checked across the full replay; zero double-routes is a hard pass/fail.
  - **M4c — Route share report:** pre-pillar routes per armed POI reported in full; a route count exceeding **50% of episodes** on the window is flagged as a loss-of-selectivity alarm for Architect review (it would indicate the revalidation gate or trigger gates are not binding; no parameter may be tuned in response — the flag is a review trigger only).
  - **M4d — No downstream drift:** fills/orders/R9-intent counts on any frozen book are out of scope for this phase, but the harness must assert the seek redesign alone produces these deltas (no accidental change to risk/fill paths).
- **M5 — Engineering gates.** Full suite green (780 baseline + new tests); double-run of the measurement harness **byte-identical**; `locked_constants.py` diff **empty**; trigger A–F module files diff **empty**; state machine transition table diff **empty**.

---

## 6. Implementation surface (preview only)

**Expected to change:**

- `smc/orchestration/engine.py` — `PipelineEngine`: episode gains a seek-posture field (`IN_ZONE_AT_ARM` / `VIOLATION_AT_ARM` / `CLEAN_ARM` + REVALIDATION flag) set at `arm_at` from the arm bar vs zone geometry; `feed_bar` gains the arm-bar classification and the R4.3 touch-vs-seek separation (touch recorded, seek not ended); `scan_route` deadline logic **unchanged**.
- `smc/backtest/pipeline_adapter.py` — `_may_route` replaced by the seek-window gate (FRESH-or-REVALIDATED-eligible inside `[arm, arm+20]`, one-shot respected); `_tested_bar` bookkeeping reduced to telemetry; REVALIDATION route gating via `market_reentered_zone`; scan-cursor contract unchanged.
- `smc/risk/fill_regime_policy.py` — at most an export/reuse of `market_reentered_zone` (existing function, no behaviour change).
- Measurement harness: new `06_RESEARCH/scripts/` script + tests mirroring `stage3_trigger_visibility.observe_routes_instrumented`, updated to the new contract (research-side only).

**Explicitly out of scope (must not change):** detectors and stage-0 (`smc/detection/**`), POI models and merge (`smc/poi/**`), validation pillars (`smc/validation/pillar_*.py`), trigger A–F implementations (`smc/triggers/trigger_[a-f]_*.py`), trigger router internals, risk (`smc/risk/**` except the read-only reuse above), order/fill model (`smc/backtest/orders.py`, `runner.py` fill steps), PureRunner / paper runner management, TP/SL policy, lot sizing, spread grading, news guard, `smc/config/locked_constants.py`, `smc/orchestration/multi_tf_runtime.py` (seam is posture-agnostic), MT5 connector.

**§5 state machine disposition:** `smc/validation/state_machine.py` transition table, atomicity, and terminal semantics are **not modified**. The seek posture is engine/adapter bookkeeping; deferred-VIOLATED at arm is realised as a posture, and any actual `on_violation` transition still goes through the frozen machine. If implementation reveals a unavoidable machine-level need, it returns to the Architect as a design amendment — not improvised.

**Confirmation:** trigger A–F evaluation logic itself is untouched — their completion definitions, anchors, expiries, signal payloads, and the chronological-first-valid-wins router rule are exactly as frozen. The redesign governs only **when the scan listens and what it may route**, never **what a trigger is**.

---

## 7. Risks & residuals

- **Late completions on degraded zones.** A zone touched at arm (or re-entered late) may be institutionally stale by the time its trigger completes at +10..+19 bars. The design accepts this deliberately: visibility first, quality measured later. No PnL claim is made or permitted in this phase; the M4c alarm and a later quality-filter design (separate ruling) are the intended answers.
- **Ghost routes from REVALIDATION rows.** A marginal close back inside the zone could re-arm a genuinely broken thesis. Mitigations already frozen: the trigger's own geometry + §24 window, one-shot identity, §23 unfilled expiry, R7 place-guard band, R9 intent clock. Residual risk is accepted and *counted* (M1 reason breakdown reports every REVALIDATION-routed row).
- **Hidden rows remain by design.** Rows with a post-arm adverse close before completion stay invisible (R4.1b) — correct behaviour, but the visibility target (M1 ≥ 80%) could miss if that population is larger than expected. The measurement phase reports the exact reason split; if the share is materially below target with a dominant violation-after-arm cause, that is an Architect decision point, not a tuning trigger.
- **Double-counting / replay-vs-product drift.** The measurement harness must mirror adapter semantics exactly (the prior packs' replay parity discipline: double-run byte-identical, independent classification path reproducing the funnel). Risk mitigated by M5's engineering gates.
- **Initial-dwell routing geometry.** A trigger completing while price sits deep inside the zone during initial presence may have poor entry geometry (entry far from the trigger's structural reference). Mitigation is already frozen and untouched: FR-3 entry gate + FR-3.1 on-zone limit anchoring + R7 place guard. Not solved by this design; measured downstream.
- **§5 documentation drift.** `LOCKED_DECISIONS.md` §5 text ("strict 1-touch only", touch → TESTED terminal) will no longer fully describe seek behaviour after implementation. This design does NOT amend the locked doc; a dated §5 amendment (seek-window clause) must accompany or follow the implementation ruling.
- **Intentionally unsolved here:** any quality/selectivity filter on the newly visible completions; any change to F-timing research posture (still PAUSED, R6); any expectancy question; whether the REVALIDATION gate should require a deeper re-entry than zone re-touch (currently: zone boundary, no tolerance — a named-rule reuse, changeable only by ruling).

---

## 8. Self-check (recorded, per process rules)

**Against the five measured facts:**

1. *261/263 completions after scan close* → addressed by R2.1/R3.1 (scan open for the whole locked horizon in every posture) and measured by M1 (target ≥ 80% visible, reason split for the rest).
2. *199 touch-closed: first_touch == arm, effective span [arm, arm+1]* → addressed by R1.2a/R1.3/R4.3 (arm-bar touch is initial presence, not interaction, not terminator); behaviour change itemised in §3.d item 1.
3. *62 violation-at-arm: scan never opens, completions still form* → addressed by R1.2b/R2.3/R4.2 (REVALIDATION posture, route gated on zone re-entry via the existing `market_reentered_zone` rule); asymmetry rationale recorded.
4. *Median completion +10 bars after scan close, inside locked 20* → addressed by R3.1 (span reclaims the granted horizon; no widening); alignment measured by M3.
5. *2 OPEN_SCAN rows complete on last open bar; F dominates 204/263* → addressed by M2 (no regression, same bars) and by the design's trigger-agnostic posture (trigger A–F untouched; F's own first-touch rule is its LTF OB, preserved).

**Against the hard bans:**

- Detection / pillars / trigger A–F logic / risk / PureRunner / FVG invalidation / lot sizing / spread grading / TP/SL policy / `locked_constants.py`: **not modified by this note; listed out-of-scope in §6; M5 asserts empty diffs.**
- No arbitrary window widening: horizon stays `poi_give_up_bars()` = 20 (§3.d table; rejected alternative 3).
- No new magic numbers: the only geometry introduced is zone re-entry (`market_reentered_zone`, existing named rule); zone boundaries used raw, no tolerance (R2.3); the M4c 50% alarm is a *review trigger*, not a trading parameter.
- No expectancy / PnL / edge claims: §5 metrics are visibility/timing/invariant counts only; non-claims restated in §5.
- Outer horizon unchanged: R3.1.

**Design-note-first process:** this note was written before any production edit; no production file has been touched in this engagement; governance docs updated with `LOGIC_CHANGED: NO`.

---

**RETURN BLOCK (this engagement):**

```
DESIGN_LOCK_STATUS: PASS
NOTE_WRITTEN: YES (06_RESEARCH/SEEK_SCAN_CONTRACT_REDESIGN_DESIGN.md)
SECTIONS: 7/7 (+ self-check §8)
FACTS_ADDRESSED: 5/5
HARD_BANS_RESPECTED: YES
LOGIC_CHANGED: NO
PRODUCTION_CODE_CHANGED: NO
LOCKED_CONSTANTS_DIFF: EMPTY
SUITE_STATUS: (see return block printed at session end)
GOVERNANCE_DOCS_UPDATED: YES (SESSION_HANDOFF / POST_V1_ACTIVE_TODO / CHANGELOG)
RETURN_BLOCK_KEYS_NOTE: the directive's "RETURN BLOCK (exact keys)" list was truncated in the prompt; the keys above are derived honestly per the fallback instruction.
```
