# DUMB FLOWCHART V1 — DESIGN LOCK

**Banner: DESIGN LOCK ONLY — NOT IMPLEMENTED — NOT EDGE.**

Authority: Architect 2026-10-21. Engagement mode: **DOCS / DESIGN LOCK ONLY**.
This note lockes a *simple* parallel path — SWEEP → PATTERN CONFIRMATION →
ENTRY — whose trades may be loose (higher count, readable) but must follow
that story. Nothing here is implemented; implementation is a **separate
prompt after Architect review of this lock**.

Hard bans honoured by this engagement: no `04_SRC/smc/**` strategy-logic edit;
no `locked_constants.py` change; no optimisation, no window-widening for PF,
no edge claim; no "quietly simplify" of production code under the old mode
name; COMPLEX stays the default until a dated Architect promotion ruling
(`00_LOCKED/BASELINE_COMPLEX_V1_1_COMPARISON_POINT.md`).

Codebase survey below is **read-only** (imports, detectors, constants,
runners). Code snippets quoted in §5 are seams, not edits.

---

## §1 Problem statement

The COMPLEX stack (multi-TF POI families, five validation pillars, trigger
matrix A–F, lifecycle dedup, structural TP feed, seek postures) is precise
but **does not currently show economic significance**: four frozen 6-month
windows produce only 44–75 fills each, with mixed paths and an unstable exit
shape (`UNSTABLE_SHAPE`), and none of the diagnostics carries an edge claim.

The user's requirement is different: a **flowchart essence** — sweep →
confirm → entry — that a junior can trace on one chart in one minute. Loose
is acceptable (more trades, readable trades); sophistication is not. DUMB V1
is therefore judged on *traceability and readable trade count*, explicitly
**not** on profitability, and nothing in COMPLEX is removed or re-tuned to
make DUMB look good.

---

## §2 Non-goals

- **Not** a Mode-B mid-TF scalp variant, and not a relabeling of Mode T.
- **Not** an ML / statistical-learning path; no model fitting, no parameters
  tuned on outcomes.
- **Not** a TP-distance or exit tuning of COMPLEX (that measurement leg stays
  its own Architect call).
- **Not** a removal or demotion of COMPLEX from the repo — COMPLEX stays the
  default runner and the comparison point stays frozen
  (`BASELINE_COMPLEX_V1_1_COMPARISON_POINT.md`).
- **Not** live promotion: DUMB ships as a measurement path on the same
  frozen windows (W1–W4) first; no live, no EA, no order routing beyond an
  offline runner.
- **Not** an edge claim of any kind — the first implementation leg is
  accepted or rejected purely on trade count and traceability criteria (§6).

---

## §3 Normative story — three steps, six rules

### R1 — LEVEL: the trade's level is an ALREADY-EMITTED HTF POI zone (M8 / H4 / H1 family)

**Definition (normative):** the trade's level is the zone of an HTF POI
emitted by the product's existing `M8HtfDemandSupply` scan (source:
`smc/poi/models/m8_htf_demand_supply.py`) on the W1/D1/H4 series it already
receives — the zone triple kind ∈ {`ob`, `demand_supply`, `fvg`} with frozen
constants (`DISPLACEMENT_MIN_ATR = 1.0`, `N_BAR_LTF = 3`) and episode
collapse (`collapse_episodes`, one geometric episode = one zone). For DUMB V1 the product reality uses the H4+H1 families exactly as the composition does today
(D1 forwarded per contract §1). Direction of the candidate trade is
`zone.direction` (LONG demand / SHORT supply).

**Why not a second, light-weight level rule:** a "single explicit level"
alternative (e.g., prior-day high/low) would be *cheaper per bar* but is
**not actually simpler end-to-end**, because it introduces a second level
source whose freshness, deduplication, and direction labeling would all be
new state DUMB must own, while `M8` output is already produced, already
episode-deduplicated (one geometry → one POI, `M8_KIND_PRIORITY`), already
direction-tagged, and already unit-tested. Re-reading both
`m8_htf_demand_supply.py` and the zone primitive (`Zone.top/bottom/midpoint/
contains`, `smc/core/zone.py`) confirms a POI-anchored level needs **zero new
model code** — R1 reuses what exists and nothing more. **No new model zoo, no
new detector, and no COMPLEX quality gates are applied to the chosen zone
(no premium/discount band, no confluence score, no overlap filter).**

### R2 — SWEEP: WICK beyond the zone extreme + CLOSE back inside (one bar)

**Definition (normative, LONG candidate at a demand zone):** the first M5
bar, on or after the bar the zone was emitted from, with

```
sweep_long(bar, zone)  :=  bar.low  < zone.bottom  AND  bar.close > zone.bottom
sweep_short(bar, zone) :=  bar.high > zone.top     AND  bar.close < zone.top
```

i.e. the **wick** pierces beyond the zone extreme and the **body closes back
inside** the zone. This is deliberately the same *wick-pierce + body-close*
discipline the codebase already locks for level sweeps
(`smc/detection/sweep_detector.py`: *"A candle that closes beyond the level
(a genuine breakout) is NOT a sweep."* — quoted verbatim from the module
docstring) transposed from a single `LiquidityLevel` to the zone extremes by
substituting `zone.bottom` / `zone.top` for `level.level`.

**Direction relative to the level:** LONG trades only off demand zones
(from below: the sweep pierces `zone.bottom`); SHORT trades only off supply
zones (from above: the sweep pierces `zone.top`). A zone must be unswept
since emission to start a candidate; after a filled or expired episode, the
**same zone may re-arm** on a new sweep bar with no cooldown (DUMB owns no
`SWEEP_GUARD_*` equivalents — see §4).

**Rejected alternative (recorded):** close-through sweep (close beyond the
extreme, reclaim over a later bar). Rejected because it needs two bars of
state and a second gate to prevent "genuine breakout" ambiguity, while the
single-bar wick rule needs none and matches what the codebase already
considers a sweep.

### R3 — CONFIRMATION: the RECLAIM bar — first later M5 close through the zone MID in trade direction

**Definition (normative, exactly one pattern for DUMB_V1):** after the sweep
bar, the **first subsequent M5 bar whose close crosses the zone midpoint in
the trade direction** is the confirmation bar:

```
confirm(bar, zone)  :=  bar.close >= (zone.bottom + zone.top) / 2   (LONG)
confirm(bar, zone)  :=  bar.close <= (zone.bottom + zone.top) / 2   (SHORT)
```

- The sweep bar itself is **not eligible** (R2 already requires its close
  inside the zone; requiring a *later* bar makes the confirm an independent
  follow-through event).
- A candidate that has not confirmed within a proposed
  **`DUMB_CONFIRM_MAX_BARS = 12`** M5 bars of its sweep bar (one trading
  hour) **expires** — constant is a *proposed name* owned by DUMB
  (`DUMB_` prefix), deliberately NOT a silent alias of any COMPLEX give-up
  clock (`TRIGGER_*_EXPIRY`, `poi_give_up_bars()`), whose semantics (per-POI
  trigger hunt) differ. The value is frozen at implementation, not tuned.
- If no sweep of the zone has occurred yet, no candidate exists and the
  confirm check is skipped (chronology: sweep must strictly precede confirm
  by at least one bar).
- Expired-or-not, the zone itself never "closes" — the next sweep starts a
  fresh candidate.

**Why this one (one paragraph):** the codebase's existing confirm/sweep
patterns (`CHOCHReversal`, `BosObContinuation` = trigger F, `TwoBarReversal`,
`EndingDiagonal`) all need swing/diagonal state machines or liquidity labels;
the *Architect default* ("a later bar closes back inside the zone or through
zone mid") needs none. Of the two sub-forms, "closes back inside the zone" is
nearly vacuous here because R2's sweep close already sits inside — the
**mid-through close** is the minimal strictly-stronger displacement test a
junior can verify on a chart (is the close past the 50 % line?) — so the
mid-through form is normative. Alternatives are listed here for the record
only: CHOCH (swing state machine), BOS+OB / trigger F (order-block
relabeling + entry-anchor semantics), two-bar reversal (needs two bars +
engulfing fraction). **None of these is normative for DUMB_V1.**

### R4 — ENTRY: MARKET at the confirmation bar's close, inside-touch only

**Definition (normative):** on the confirmation bar (the bar whose close
satisfied R3), a market order is admitted **at that M5 close price**, subject
to the built-in distance rule:

```
entry(bar) := bar.close            (market, next-bar semantics = this bar's close price)
admitted   := zone.contains(entry)   # close must still be inside the zone
```

- Because R3 requires `confirm.bar.close` to be beyond the mid *and* R4
  requires it to be inside the zone, the entry is structurally confined to
  the zone's mid-half — the "must be near level" requirement is satisfied
  **by construction, with no extra ATR distance constant**.
- If the confirm close is beyond the far extreme of the zone (price ran
  through), the candidate is **discarded for this episode** (no chasing; the
  zone may re-arm on the next sweep).
- **Rejected alternative (recorded):** limit order resting at the zone edge
  from the sweep bar onwards. Rejected because it decouples entry from the
  confirm event (fills can occur without any confirm), which is exactly the
  story DUMB is not allowed to loosen; also the codebase carries an
  explicit anti-limit precedent for unrelated reasons
  (`TRIGGER_D_ENGULFING_FILL` documents "Limit order … (NOT market)" as a
  *trigger-specific* choice, not a product default) — a DUMB limit would
  need its own fill/validity book, i.e. new state. Market-on-confirm-close
  needs none.

### R5 — SL: beyond the sweep extreme, buffer is a DUMB-owned PROPOSED constant

**Definition (normative):** the stop rests beyond the **sweep bar's**
extreme (the wick that caused the candidate), not the zone edge:

```
sl(bar) := bar.low  − DUMB_SL_BUFFER_ATR × ATR(M5, 14)   (LONG)
sl(bar) := bar.high + DUMB_SL_BUFFER_ATR × ATR(M5, 14)   (SHORT)
```

with ATR from the existing Wilder helper (`smc/utils/atr.py`, `latest_atr`,
period 14 — the codebase's standard period, used unchanged).

- **`DUMB_SL_BUFFER_ATR` is a PROPOSED constant name**, owned by the DUMB
  track, frozen at implementation. It is **deliberately not silently equal**
  to any COMPLEX value. Survey of the inventories:
  - `SAME_LEVEL_GUARD_ATR = 0.15` (locked_constants.py, InpSameSLZone) and
    `PURE_RUNNER_BE_BUFFER_ATR = 0.10` (InpBEBuffer) are the two COMPLEX
    buffers in the 0.10–0.15× ATR neighbourhood, but both mean "distance
    guard", not "stop placement beyond a sweep wick";
  - `SWEEP_GUARD_ZONE_ATR = 0.5` governs *same-level cooldown radius after a
    loss*, which DUMB does not implement at all.
  - **Reuse is therefore not intentional-carryover; DUMB proposes its own
    name and value** (proposal for the implementation leg: `0.10` — same
    order of granularity as `PURE_RUNNER_BE_BUFFER_ATR`, chosen for dumb
    readability; the Architect may set any value implied by the sweep
    geometry before implementation).
- No COMPLEX entry-blocker interacts with this SL: DUMB deliberately does
  **not** carry `ATR_FLOOR_MIN_SL = 1.0` (stop-distance-at-least-1-ATR gate)
  or the `SAME_LEVEL_GUARD_*` / `SWEEP_GUARD_COOLDOWN_BARS` machinery (§4).

### R6 — TP: FIXED multiple of the initial risk — **2R**, one number, no feed

**Definition (normative):** profit target = entry ± 2R

```
r(bar, sl) := |entry − sl|                       # R_stop of the dumb trade
tp(bar, sl) := entry + 2.0 × r(bar, sl)          (LONG)   # SHORT mirrored
```

**(a) fixed-R is normative; (b) next-opposite-swing is rejected for V1.**
The codebase *does* already hold a swing feed (`structural_swing` tp_source
shows structural targets flow through the COMPLEX books), so option (b) is
technically reachable — but it would hand DUMB a *placement* decision (which
swing? how far past?) whose answer is exactly the research question the
TP_DISTANCE legs showed to be window-specific and not yet understood
(placement, not distance median, is the discriminator). A fixed 2R keeps the
measurement unambiguous: every trade's target geometry reduces to its own
initial R. **`DUMB_TP_R_MULTIPLE = 2.0` is a PROPOSED constant name** for the
implementation leg (Architect may flip to 1.5R at review — it is listed as a
real fork in §7). Unless stated otherwise: no trailing, no BE move, no partial
exits, no session or Friday-EOD force-close inside V1's offline measurement
(books close the window at its end like COMPLEX's offline books do).

---

## §4 What COMPLEX does that DUMB explicitly IGNORES

- **Pillar hard gates (validation):** pillar 1–5 chain (session windows,
  displacement quality via `DISPLACEMENT_*_ATR`, premium/discount bands
  `DISCOUNT_THRESHOLD 0.45 / PREMIUM_THRESHOLD 0.55` with equilibrium reject,
  EQH/EQL tolerance, inducement scoring).

  *COMPLEX: niveaus validated up-front; a POI that fails any gate never arms.
  DUMB: **skip** — no pillar runs at all; every M8 zone is a candidate from
  its emission bar.*

- **Confluence / compatibility grading:** tag-count scores, spread grades,
  `htf_overlap` bonus, `compatibility_matrix` grades PREFERRED > STRUCTURAL
  > UNCOMMON used for route tie-breaks.

  *COMPLEX: gates and tie-break routing / rendered grades. DUMB: **skip** —
  optionally log the emitted zone's raw fields in the trade journal for
  later audit, with no admission effect.*

- **Trigger matrix A–F and expiries:** six trigger detectors with per-letter
  expiry clocks (`TRIGGER_A_EXPIRY = 20` … `TRIGGER_F_EXPIRY = 1`), same-bar
  tie-breaks by compatibility then letter order.

  *COMPLEX: route determination chooses which trigger’s entry completes
  first. DUMB: **skip the whole matrix** — the confirm event is R3
  unconditional. No compatibility matrix access, no trigger-letter tagging.*

- **Seek postures / scan contract / §5a:** multi-posture scanner toggles and
  seek-mode selection breadth machinery.

  *COMPLEX: postures reorder scanner aggressiveness and runtime state. DUMB:
  **skip** — a single fixed posture (always scanning the emitted zones).*

- **R7/R9 intent book:** armed-episode intent persistence,
  place-on-re-entry R9 semantics, episode store resolution.

  *COMPLEX: maintains the intent/episode book across re-entries and reloads.
  DUMB: **skip** — no book; candidates are stateless per window pass
  (a flat event log instead).*

- **ZoneDedup retire lifecycle + registry (LEG 5b):** owner-attributed keys,
  `retire(owner_id)`, dead-episode retirement sweeps.

  *COMPLEX: revives/deduplicates arming across episodes with a live registry.
  DUMB: **skip** — no dedup registry; if two M8 zones overlap, both produce
  candidates independently (logged as-is).*

- **Structural TP feed:** swing-derived target placement with `tp_source ∈
  {structural_swing, atr_fallback}` fallback decisioning.

  *COMPLEX: computes per-trade targets from structure with fallback. DUMB:
  **skip** — fixed 2R (R6); optionally log `structural_swing`-style distance
  for later comparison, decision-inert.*

- **Risk layer + guards:** circuit breaker (`CIRCUIT_BREAKER_*`),
  same-level SL guard ("same SL zone" block + cooldown), failed-sweep guard
  (`SWEEP_GUARD_ZONE_ATR`, `SWEEP_GUARD_COOLDOWN_BARS`), spread grading with
  `SPREAD_GRADE_MULTIPLIERS`, news hard-cancel, ADX gate (`ADX_MIN_ENTRY`),
  ATR stop-floor (`ATR_FLOOR_MIN_SL`), Friday EOD force close, lot caps, live
  order/heartbeat plumbing.

  *COMPLEX: all active on the product path. DUMB: **skip** for the
  measurement leg — offline books sanitize costs to zero and carry none of
  these; each is logged as "not implemented in DUMB_V1" once, so a later
  realism leg cannot silently assume it.*

- **`locked_constants.py` thresholds** as a family: none is consulted by the
  DUMB path except the frozen `M8` constants DISPLACEMENT_MIN_ATR / N_BAR_LTF
  *inside the reused M8 scan itself* (they are part of the level definition,
  unchanged), plus `atr.py` period 14 by convention. Everything else listed
  above is COMPLEX-only.

---

## §5 Parallel mode contract

- **Mode id:** `DUMB_FLOWCHART_V1` (a distinct execution mode, not a config
  subset of COMPLEX).
- **COMPLEX remains the default** runner and the product path until a dated
  Architect promotion ruling says otherwise. Nothing in this note changes a
  flag, a file, or a constant today.
- **Same data windows W1–W4** (`2024-06-01 → 2026-03-31`, the four frozen
  6-month books) are the pre-agreed comparison surface when implemented;
  captures reuse what exists where byte-stable, capture only gaps.
- **Isolation seam (survey, read-only).** The current execution spine is:
  `MultiTFProductRuntime.run_batch` (H4+H1 detect cadence) →
  `PipelineEngine` arm → `PipelineAdapter` scan/route → `BacktestRunner`
  risk/placement (`orders.py`, `positions.py`), with `TriggerRouter`
  deciding the entry inside `PipelineAdapter`. Survey of those modules shows
  the arm/route/place chain is woven through the engine (five-pillar gates,
  matrix routing, skip/reject book-keeping), so **there is no present hook to
  hang a three-step path on the existing spine without either touching
  engine internals or faking a POI family**, both of which would entangle
  DUMB with COMPLEX. **Preferred seam: a NEW, separate runner path** — a
  `dumb` runner module (its own top-level function, own state machine, zero
  imports from `triggers/` or `orchestration/engine.py`) that imports only
  the *data layer* (parquet loader, `resample_multi`) and reuses the *M8 zone
  scan* as a plain function call against frozen HTF series, then walks M5
  bars itself and emits flat trade rows in the same `trades.csv` schema. A
  config flag (e.g. `mode=dumb_flowchart_v1` in the research runner
  invocation) selects between COMPLEX and DUMB runners at the **outermost**
  layer only — never a branch inside an existing strategy module, so that
  COMPLEX's behaviour is bit-for-bit unaffected in either mode (no risk of
  "quietly simplified" production code). Tests for the mode live in a new
  test file; no COMPLEX test changes.

---

## §6 Success criteria for a FUTURE implementation leg (NOT this leg)

1. **Trade count materially higher than COMPLEX on the same window.** Order-
   of-magnitude guidance, exact target set at implementation review: COMPLEX
   closes 44–75 trades per 6m; DUMB V1 aims for a **readable sample —
   roughly 3–10× COMPLEX's fill count** on the same window — not "max
   trades"; quality of the flowchart trace is the reason for the count, and
   counts above that band trigger §6.3-style tightening rather than
   celebration.
2. **Chart-traceability ≥ 70 %.** On the first implementation, ≥ 70 % of a
   random-sampled set of DUMB trades must score **PARTIAL or better** on a
   four-item rubric, scored from charts *without* observing exits:
   (i) a visible level (the HTF zone), (ii) a visible wick+sweep beyond an
   extreme, (iii) a visible reclaim close past the zone mid, (iv) entry at
   the confirm close, inside the zone. Partial = at least three of four;
   the expert marks misses; the sample size and rubric file are fixed at
   that leg's start.
3. **Still no edge claim required.** Implementation is accepted or rejected
   on count + traceability only; PnL/expectancy/PF comparisons to COMPLEX
   are explicitly out of the acceptance criteria (measurement may still be
   *recorded* for the record, labelled diagnostic).

---

## §7 Open decisions for the Architect (max 5 — real forks only)

1. **Confirm timing — the RECLAIM event (R3):** locked as *first later bar
   closing through the zone mid*. Fork: relax to "close back inside the zone"
   (weaker, more trades), or tighten to "close back beyond the sweep origin"
   (stronger, fewer). Default stands unless overridden before implementation.
2. **Entry style (R4):** locked as *market at the confirm bar's close*.
   Fork: limit at the zone edge from the sweep bar onward (decouples entry
   from confirm — rejected by default; reversing it adds fill/validity state).
3. **TP multiple (R6):** locked as **fixed 2R**. Fork: 1.5R, or structural
   next-swing. Default stands; a flip is a one-line constant change.
4. **SL buffer value (R5):** the *name* `DUMB_SL_BUFFER_ATR` and the
   "sweep-extreme anchor" are locked; the **value** is proposed 0.10× ATR and
   open (0.05 tighter / 0.25 looser are plausible positions chosen without
   outcome search).
5. **Candidate cap per zone:** none in V1 (a zone may produce unbounded
   sequential candidates, one per sweep). Fork: one open position per zone
   at a time (closer to COMPLEX's non-overlap discipline; adds state).
   Default is "no cap, log everything"; the Architect may tighten at review.

---

## §8 Self-check

**`DESIGN_LOCK_STATUS: PASS`** — R1–R6 above are each a single rule with a
normative formula, a stated constant owner (`DUMB_*` names where new
constants exist), a rejected-alternative record, and no second pattern. A
junior can implement SWEEP → CONFIRM → ENTRY from §3 + §5 without inventing:
the level comes from one existing scan, the sweep from one boolean pair, the
confirm from one close-mid comparison, the entry from one market-on-close
call with an inside-zone check, the SL from one ATR-buffered sweep extreme,
and the TP from one multiple of initial risk.
