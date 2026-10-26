# STRUCTURAL TP FEED — DESIGN LOCK (first swing → existing structural_else_4ATR)

**Status:** DESIGN LOCK — **ACCEPTED 2026-10-05** (Architect review; implementation authorized per the accepted design).

> **ARCHITECT RULINGS ON PROPOSED CONSTANTS (2026-10-05):**
> 1. `STRUCTURAL_TP_MIN_ATR = 0.25` — **Accepted** for implementation as an
>    interim constant (same class as FR-2 constants — exact value pinned in
>    tests; formal § lock can follow).
> 2. Reuse of `poi_give_up_bars()` as pre-arm swing tolerance — **Accepted
>    ONLY as an optional search bound (CPU/age cap), not a new market
>    meaning.** Primary rule remains: all §19-confirmed swings with
>    `confirmed_index < placement_bar` on the place-time prefix; the
>    `poi_give_up_bars()`-before-arm cap is a documented **bound**, never
>    "give-up semantics".

Design-only engagement; NO production code was written in the design phase. **LOGIC_CHANGED: NO.**
**Date:** 2026-10-05 · **Authority:** Lead Architect policy 2026-10-05
(`06_RESEARCH/POLICY_TP_SL_PARTIAL_2026-10-05.md`): (A) structural /
first-swing TP MAY be fed via the existing `structural_else_4ATR` branch;
(B) SL unchanged — out of scope; (C) 30-pip = MAE yardstick only — out of
scope.
**Verified code facts (read 2026-10-05, no edits):**
`smc/backtest/pipeline_bridge.py` — `resolve_take_profit(entry_price,
direction, atr, structural_target=None)`: a caller-supplied structural
target **wins when finite and strictly favorable** (LONG above entry,
SHORT below); anything else falls back to `entry ± FR2_TP_ATR_MULTIPLE ×
ATR` (`FR2_TP_ATR_MULTIPLE = 4.0`, `smc/triggers/base_trigger.py:45`);
missing/non-positive ATR → `None`. `candidate_from_route(route, ...,
structural_target=None)` already carries the kwarg today, defaulted to
`None`. `PipelineAdapter.generate_candidates` (pipeline_adapter.py ~L193)
is the single production call site and passes only `atr` — hence the
branch is UNFED (C3/FR-2 status honest: wired, tested
(`tests/test_fr2_sl_tp_routing.py`), dormant).

---

## 1. Problem statement

- The FR-2 structural TP branch exists (`resolve_take_profit` +
  `candidate_from_route(structural_target=...)`) but **no trigger emits a
  structural target** — the adapter is the only call site and never
  supplies one. Product fills in the diagnostic funnels (3m/6m under the
  new §5a contract) therefore carry TP exclusively via the frozen 4×ATR
  fallback (TP non-null 100% on placed orders in both funnels — the
  fallback path, not a structural one).
- The operator/expert-chart narrative (TP at the first relevant opposing
  structure in profit direction) is absent from the machine. The expert
  charts' TP story is swing-based, not ATR-multiple-based.
- This design defines **exactly** how the first swing is chosen at
  place time, lookahead-safely, from data the adapter already holds, and
  how it is attached so the existing branch becomes live — without
  touching SL, triggers, pillars, or risk.

## 2. Design principles

- **"First swing" in market terms:** the most recent confirmed opposing
  structural extreme that price must traverse to reach profit — the
  inventory of obvious opposing structure between entry and the open
  horizon. LONG → the nearest confirmed swing **high** above the entry
  (the liquidity shelf the move must take out); SHORT → the nearest
  confirmed swing **low** below entry. "First" = first one encountered
  moving away from entry in the profit direction (nearest in price),
  not the first in time.
- **One decision, one source:** the TP price is computed ONCE at
  place-time (candidate construction), from information available at
  that bar. No fill-time refinement, no trailing.
- **No new vocabulary engines:** the design depends only on the §19
  swing machinery the engine already maintains per series (`SeriesState`
  / `SwingIndex` — `last_valid(is_high, before)`), not on Fib, double
  top/bottom, CHOCH-as-pattern, or ending-diagonal engines that do not
  exist (expert match-note honesty).
- **Fallback is the frozen contract:** absent/invalid swing → the
  existing 4×ATR path, unchanged. Structural TP is an overlay on the
  branch that already exists, not a replacement of it.
- **What this is NOT:** not a trail, not a partial scale-out grid, not a
  Fib TP, not a 30-pip SL, not a new detector, not a quality filter on
  entries.

## 3. Normative rules (implementable)

### 3a. Swing definition

- **Source: REUSE the existing helper — `proposed_pure_function: NO.**
  The selection function `structural_tp_target(...)` will be a new small
  pure function (selector, not a detector), but the swing data comes
  from the already-maintained §19 swing index —
  `SeriesState.swings.last_valid(is_high=..., before=...)`
  (`smc/backtest/series_state.py`) — the SAME §27/§19 swing artifacts the
  trigger scan itself consumes. No new pivot detector is built.
- Pivot rule: inherited, not restated — §18/§19 Base-Candle confirmation
  (a swing exists as valid only after the Base Candle's opposite extreme
  is broken with a body close). **No new number is introduced.**
  `PROPOSED_NEW_CONSTANTS: none` — this design reuses `FR2_TP_ATR_MULTIPLE`
  (fallback) and the §19 machinery; any minimum-distance guard reuses the
  locked ATR basis with `PROPOSED` status (see 3c).

### 3b. Selection rule by direction

- **LONG:** first = the most recent §19-valid swing **high** whose level
  is **strictly above the entry limit price**, searching **backward in
  time from the placement bar** (`before = placement_bar`), taking the
  **nearest to entry in price** among the swings available in the prefix
  (implementation: scan the valid-highs prefix slice from most recent
  backward, stop at the first strictly-above-entry swing — recency and
  price-proximity coincide for a monotone walk; the first hit walking
  back from "now" is the most recent swing above entry, which for a
  rising-into-entry structure is the nearest shelf. Ties in level:
  deterministic tie-break by **most recent** `candle_index`).
- **SHORT:** mirror — most recent §19-valid swing **low** strictly below
  the entry limit, same backward walk, same tie-break.
- **Search window: bars before the placement bar only — bounded
  lookback = the armed POI's own lifecycle:** the candidate swing must
  have `confirmed_index >= arm_bar` OR `candle_index >= arm_bar - 20`
  (the §5a scan-horizon constant `poi_give_up_bars()` is REUSED as the
  pre-arm tolerance, PROPOSED — justification: a swing older than the
  structure's own scan horizon predates the thesis and belongs to the
  previous regime; reusing the locked horizon avoids inventing a number).
  `before = placement_bar` (prefix-bounded — see §4). Swing **timeframe
  = the execution series (M5)** — the same series the triggers read;
  HTF swing harvesting is explicitly out of scope (would need new
  plumbing + new validity questions).

### 3c. Validity filters

- **Minimum distance from entry:** the structural target must be at
  least `0.25 × ATR` beyond entry (`PROPOSED` constant
  `STRUCTURAL_TP_MIN_ATR = 0.25` — justification: below a quarter-ATR the
  "shelf" is inside noise; costs/spread dominate; 0.25 is a coarse,
  named, listed-for-lock guard, not a tuned optimum). Fails the guard →
  fallback 4×ATR.
- **Stop side rejection (implied):** a swing on the stop side of entry
  is never selected by construction (LONG requires strictly above entry;
  SHORT strictly below) — `resolve_take_profit` re-validates sidedness
  anyway (defense in depth, existing test `test_resolve_tp_invalid_
  structural_falls_back` covers wrong-sided input → fallback).
- **Multiple swings:** "first" = **nearest in price** with recency
  tie-break (3b). Not "first in time" — an old far swing is not the
  inventory price must traverse first.

### 3d. Attachment point

- **Write the price into `candidate_from_route(structural_target=...)`
  at the existing adapter call site** (`PipelineAdapter.generate_
  candidates`, ~L193): the adapter computes
  `structural_tp_target(state, poi, route.signal.entry_price, direction,
  placement_bar)` (new pure selector in `pipeline_bridge.py`, section 3a)
  and passes it as the kwarg that ALREADY EXISTS. `resolve_take_profit`
  is untouched — its sidedness/finiteness re-validation stays as the
  second gate.
- The trigger signal's `data` dict is NOT modified; no trigger body
  changes; route provenance unaffected. The structural origin is
  recorded for audit by extending the candidate's existing provenance
  string (same pattern as `pillar_path`) — `tp_source=structural_swing`
  vs `tp_source=atr4_fallback` — logging/audit only.
- Live/paper parity: the paper runner's candidate construction flows
  through the same adapter seam; no separate live path is added.

### 3e. Fallback

- Unchanged, byte-for-byte: swing absent / invalid / wrong-sided /
  inside the 0.25-ATR guard / non-finite → `resolve_take_profit` takes
  its existing 4×ATR branch. Missing/non-positive ATR → `None` exactly
  as today. The frozen funnel TP-non-null-rate=100% expectation carries
  over as an implementation-phase invariant.

### 3f. Interaction with BE / PureRunner / FVG invalidation

- **BE latch ordering:** TP is set at place time and is never moved by
  the BE machinery (break-even moves SL only). No conflict by
  construction; the design adds no TP mutation API.
- **PureRunner / FVG invalidation:** FVG invalidation may close a
  position before TP is reached — unchanged; a structural TP neither
  suppresses nor defers invalidation. Ordering constraint (normative):
  TP is written into the order at placement; management (BE, FVG,
  Friday EOD, circuit breaker) operates on SL/exit only and must never
  modify TP in this design. Any future TP-modify mechanism requires its
  own dated ruling.

### 3g. SL

- **Explicit: UNCHANGED.** `FR2_SL_*` constants, structural-SL helpers,
  buffers — out of scope, untouched. Policy B governs. The 30-pip expert
  statement remains the MAE review yardstick (policy C) and appears in
  no order path.

---

## 4. Lookahead / leakage control

- **Place-time only:** the selector reads `state` — the SAME growing
  prefix (`SeriesState`) the trigger scan reads on that bar — and is
  bounded by `before = placement_bar` (strictly `< placement_bar` via
  `last_valid`-style prefix slices). The placement bar is the bar on
  which `generate_candidates` constructs the candidate (the route
  completion bar); the limit rests thereafter. No bar `> placement_bar`
  is readable by construction (the prefix does not contain them yet).
- **Confirmation-time honesty:** a §19 swing used as TP must be
  CONFIRMED by `placement_bar` (`confirmed_index < placement_bar` —
  inherited from `last_valid` on the valid lists). An unconfirmed
  (pending) extreme is never used — using it would leak the future
  confirmation.
- **Arm-bar horizon bound (3b) is backward-looking only:** it filters
  swings by `candle_index`/`confirmed_index` relative to `arm_bar`,
  never by anything after the placement bar.
- **No fill-time refinement is proposed.** The TP is frozen at place
  time; if it fills, TP is already on the order. Any future fill-time
  refinement would be a separate design with its own leakage analysis.
- **Determinism:** same prefix + same inputs → same selector output
  (pure function, no clock, no RNG, no global state) — required for the
  dual-run byte-identity invariant.

## 5. Rejected alternatives (short)

- **Fixed RR multiple** — invents geometry price must not respect; the
  expert narrative is structural, not ratio-based.
- **Fib 1.618 / golden-only TP** — depends on a Fib engine that does not
  exist (match-note vocabulary gap); banned by this design's no-new-
  detectors principle.
- **Trail-as-TP / managed exits** — changes Stage 5 semantics (BE,
  PureRunner); violates the frozen management contract; out of scope.
- **Always 4×ATR (status quo)** — keeps the branch dead; ignores the
  accepted policy A.
- **HTF (H4/H1) swing harvesting for the M5 TP** — needs new plumbing,
  new confirmation questions, new leakage surface; unjustified for the
  first feed.
- **Zone edge as TP** — for many POIs the zone edge is on the entry side
  (entries are re-anchored to zone edges); wrong-sided more often than
  not; not "opposing structure".

## 6. Success metrics for the implementation phase

Non-PnL first (diagnostic funnels on the frozen windows, dual-run):

1. **TP non-null rate on placed orders remains 100%** (fallback
   guarantees it; invariant must not regress).
2. **Share of placed orders with `tp_source=structural_swing` vs
   `tp_source=atr4_fallback`** — reported, both counts, no target
   (fallback-heavy is an acceptable honest outcome; sparse-swing
   residual §8).
3. **Determinism: trades.csv + report.json byte-identical** across
   run1/run2 on the frozen 3m/6m windows (selector purity).
4. **No change to SL distribution / stop-policy tests** — SL paths
   byte-identical outputs where inputs unchanged; all FR-2 tests green
   unmodified.
5. **Suite green** (805 baseline + new selector tests);
   `locked_constants.py` diff empty.
6. **Optional diagnostic (NOT an optimization target):** MFE vs
   structural-TP distance and vs 4×ATR distance on closed trades —
   reported as distributions, never used to tune the 0.25-ATR guard or
   any threshold.

## 7. Implementation surface (preview)

**Expected to change (implementation phase, after Architect review):**

- `smc/backtest/pipeline_bridge.py` — ADD one pure selector
  `structural_tp_target(...)` (reads a `SeriesState`-like swing index +
  prices + bar bounds; no engine coupling). No change to
  `resolve_take_profit`.
- `smc/backtest/pipeline_adapter.py` — call the selector at the existing
  `candidate_from_route` call site (~L193) and pass the kwarg that
  already exists; extend the provenance string with `tp_source=`.
- `04_SRC/tests/` — new test file(s): selector known-cases (LONG/SHORT,
  sidedness, 0.25-ATR guard, recency tie-break, arm-horizon bound,
  unconfirmed-swing exclusion, fallback passthrough), adapter wiring,
  determinism.

**Explicitly out of scope:** trigger bodies (A–F evaluation untouched);
`resolve_take_profit` (untouched); SL/stop policy; RiskEngine; BE /
PureRunner / FVG invalidation; live loop; paper runner; locked constants
(the two PROPOSED guards are written in the note only); any detection
module; any new detector.

## 8. Risks & residuals

1. **Sparse swings → heavy fallback.** M5 valid swings may be scarce in
   quiet regimes; the arm-horizon bound (3b) tightens supply further.
   Expected: structural share well below 100%; both sources reported
   (metric 2). Accepted honest outcome, not a defect.
2. **Choppy swings → tight TPs / early exits.** A nearby 0.25–0.5 ATR
   shelf yields a TP closer than the old 4×ATR — earlier exits on
   trades that would have run. This is a behavioral change to exit
   geometry (that is the point of policy A); it is disclosed, and the
   diagnostic funnels will show exit-mix deltas. No edge claim is made
   either way.
3. **Zone-edge re-anchor interaction.** With `zone_edge_reanchor`
   entries, entry sits at the zone edge; the first opposing swing may
   frequently be the swing that formed the zone itself (recent, near,
   confirmed). The guard (3c) filters sub-quarter-ATR cases; residual:
   structural TP ≈ zone height — coherent with the narrative but must
   be observed, not assumed.
4. **PARTIAL quality tagging not in this design.** Policy D's quality
   tag / half-risk posture is a separate track; this TP feed must not
   become its vehicle.
5. **Constant-for-lock discipline.** `STRUCTURAL_TP_MIN_ATR = 0.25`
   (PROPOSED) and the reuse of `poi_give_up_bars()` as the pre-arm
   tolerance (PROPOSED reinterpretation of an existing locked constant
   for a NEW purpose — flagged for the Architect's explicit nod) must be
   locked via a dated ruling before implementation writes them.

## 9. Self-check

- **Hard bans:** no production code written (this note only); SL
  untouched; 30-pip absent; no new magic numbers beyond the two named,
  justified, listed-for-lock PROPOSEDs; no expectancy claims; trigger
  bodies untouched; `locked_constants.py` conceptually untouched — **PASS.**
- **Policy A–C:** A honored (feed the existing branch, first swing);
  B honored (§3g); C honored (absent from all order paths) — **PASS.**
- **Lookahead:** place-time prefix-bounded selection, confirmed-swings
  only, no fill-time refinement (§4) — **YES, lookahead-safe.**
- **Vocabulary honesty:** depends only on existing §19 swings; no Fib /
  double-top / W1 dependency — **PASS.**
- **Failure mode check:** if a lookahead-safe first-swing rule could not
  be defined without inventing data, this note would set
  DESIGN_LOCK_STATUS: FAIL. It could be defined from existing artifacts;
  **DESIGN_LOCK_STATUS: PASS.**

---

**Artifacts:** this note. No code, no tests, no constant written in this
engagement. Implementation phase proceeds only after Architect review of
this design lock.
