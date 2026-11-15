# BRANCH B — CONFIRM COMPLETION vs ZONE (SURVEY + DESIGN NOTE)

**Status:** `CONFIRM_VS_ZONE_STATUS: PASS` (survey + design only — nothing implemented)
**Authority:** Lead Architect — GO, "BRANCH B — CONFIRM COMPLETION vs ZONE (SURVEY + DESIGN)"
**Date:** 2026-11-07
**Predecessor:** `06_RESEARCH/OPT_B_WIDER_MEASURE_NOTE.md` (ON_WINDOW ~48 % either flag),
`06_RESEARCH/POI_TIMING_EARLY_LATE_REPORT.md` (adapter path ~77 % LATE),
`06_RESEARCH/POLICY_OPT_B_FLAG_2026-11-07.md` (live flag frozen OFF — **unchanged by this note**)

```
LOGIC_CHANGED: NO   — survey + design note only; zero 04_SRC edit; no R7/R9 or
                      threshold touch; OPT-B flag stays false; no Mode B
```

> **DIAGNOSTIC — NOT EDGE — NOT A PERFORMANCE CLAIM.** No PnL, no expectancy,
> no edge. Every number quoted is a geometry count from already-written notes.

---

## PART 1 — THE TRADED PATHS (explicit, with wiring citations)

**The live/demo product_v1 confirmation path is the per-tier MENU**, and Branch B
targets it. A second, still-wired body exists but is *latent* in live; it is the
research-funnel pre-menu path. Both converge on ONE candidate/place seam.

| path | used when | wiring (file:line) |
|---|---|---|
| **Menu (ProductMenuEngine)** — sweep-gated per-tier confirmation | `strategy_mode == PRODUCT_V1` **and** the configured detection set covers all four tiers (`menu_covers` → D1,H4,H1,M15); exactly what `config/live_demo.json` ships (`detection_timeframes ["D1","H4","H1","M15"]`) | `run_operator.py:413-436` builds it; `loop.py:259-260` drives it per execution bar (`_drive_menu_confirmation`, `loop.py:339-400`); winners queued via `PipelineAdapter.queue_menu_candidate` (`pipeline_adapter.py:297`) |
| **Adapter (PipelineAdapter)** — exec-TF arm-bar scan, **no sweep gate** | partial detection set (the H4+H1 floor / single-TF degraded), or any non-product_v1 mode, and every research funnel (`phase3_structure_funnel`, timing study, OPT-B measure) | `run_operator.py:477` builds the adapter; scan lives at `pipeline_adapter.py:161-275` (`generate_candidates`); menu-owned POIs are excluded from its scan (`pipeline_adapter.py:199`, `own_menu_confirmation` `:279-291`), so with the full menu live **it produces no competing confirmation** |

**The shared seam (where labels, risk verdicts and placement actually happen):**
menu winner candidate or adapter workflow candidate → `candidate_from_route()`
(`pipeline_bridge.py:179-282`, frozen §10: **entry is always a resting LIMIT,
never market**) → `PaperRunner.submit_entry` → risk verdict → **R7 place guard**
→ `broker.place_limit` (`runner.py:855-913`). Research harnesses use the same
seam, which is why the timing study and the wider OPT-B measure both speak
about the same geometry.

Because live `product_v1` runs the full menu, **TRADED_PATH = menu**; the
adapter path is documented here because it is (a) the fallback when the menu
does not cover, and (b) the path whose 77 % LATE motivated the whole timing
question — and its scan properties differ materially (Part 2 §6.5).

---

## PART 2 — CODE SURVEY (file:function)

### 2.1 What event is "confirmation complete"?

* **Menu path:** a *closed confirmation-TF bar* on which `TriggerRouter.evaluate_at_tf`
  returns a route for an ACTIVE episode — `product_menu_mtf.py:_evaluate_confirm_bar`
  (450-503) → `_win` (595-618) consumes the episode one-shot, builds the
  candidate (`_candidate`, 620-658) and the winner is queued for the same
  execution bar (`loop.py:381-394` → `pipeline_adapter.py:168-172` submits it).
  The ROUTE is **route_id = `{poi_id}:{trigger}@{completion_index}`**
  (`pipeline_bridge.py:259`) — `signal.completion_index` is the index in the
  confirm-TF series where the trigger's pattern + entry condition completed
  (`base_trigger.py:208-219`). Note the chronology subtlety: the bar that
  *carries a completed pattern* can be earlier than the bar that *carries the
  sweep-in-window eligibility* — the router evaluates `[from_index … index]`'
  newest actionable completion.
* **Adapter path:** `PipelineEngine.scan_route(...)` (`pipeline_adapter.py:208-217`)
  completing on an exec-TF closed bar → `_Workflow(candidate, completion_index,
  expiry_bars)`; unlike the menu, its one-shot is consumed only on an
  **accepted placement** (`on_candidate_accepted`, `pipeline_adapter.py:301-305`:
  blocked candidates are re-submitted every bar until §24 expiry
  `signal_expired(completion_index, expiry_bars, bar_index)`,
  `pipeline_adapter.py:257-260`).

### 2.2 What price are ON_WINDOW / LATE labelled from?

The frozen label (`poi_timing_early_late_study.py:190-221`, reused verbatim by
the OPT-B harness) is a **close-of-the-confirm-bar** metric:
`zone_edge_distance(zone, confirm_close) / ATR` with the locked
`ZONE_REFINEMENT_ATR = 0.5` band (`locked_constants.py:128`) →
`ON_WINDOW` (≤ band), `LATE` (beyond band on the displacement side, away from
the protective stop), `BEYOND_STOP_SIDE` (beyond band past the zone).
**No limit price, no zone-edge reference, no mid** — the label is a property of
the confirm bar close only.

### 2.3 How is the entry price chosen relative to the zone?

Always a **resting limit** from the trigger spec — completion geometry does not
move it:

| trigger | entry anchor | where |
|---|---|---|
| F (BOS→OB, the dominant route trigger — F 9/10 routes in the frozen 6m funnel run1) | **FR-3.1** — the OB **proximal edge** (on-zone OB bit-exact pre-FR-3.1); an OB outside the routed zone **re-anchors to the nearest zone edge**, stop = the same geometry's DISTAL edge (0.3×ATR buffer) | `trigger_f_bos_ob.py:15-25` |
| A (CHoCH) | `choch.broken_level` | `trigger_a_choch.py:72` |
| B (leading diagonal) | limit at the **50 % level** of the retracement band | `trigger_b_leading_diagonal.py:12-13,88` |
| C / D / E | pattern boundary / own-bar entry / pattern.entry | `trigger_c_ending_diagonal.py:105`, `trigger_d_two_bar.py:70`, `trigger_e_rsi_divergence.py:83` |

`zone_anchored_entry` (`base_trigger.py:137-169`) is the shared direction-aware
proximal anchor (LONG → zone high, SHORT → zone low) — it re-anchors an off-zone
reference **into the zone** and explicitly does **not** use the FR-3 band
(`base_trigger.py:152-157`). The frozen FR-3 *gate* then re-checks the routed
entry: `entry_within_zone` (`base_trigger.py:114-134`, tol = `ZONE_REFINEMENT_ATR`).

### 2.4 Why can completion be LATE while entry is on-zone? (the geometric decoupling)

Three different references are computed from three different bars, and nothing
ties them together:

1. **Completion reference** (labels, research): the confirm bar's **close**
   (`§2.2`). A CHoCH/BOS completes *because* price displaced across a level —
   i.e., completion-grade patterns are biased toward closes that are already
   far from the POI zone. The label measures where the close is; it is a
   legitimate finding that ~52 % of menu completions sit outside the 0.5 ATR
   band (W1/W2 wide measure).
2. **Entry reference** (place geometry): a **resting limit anchored INTO the
   zone** (§2.3) — for F, the OB proximal / re-anchored zone edge. This price
   does not depend on the completion close at all; it is FROZEN by `replace()`
   into the CandidateEntry at win time (`product_menu_mtf.py:620-658`).
3. **Place reference** (R7 gate): the **execution-bar close** at submit time,
   tested against the same 0.5 ATR band (`runner.py:864-896`,
   `SKIP_PLACE_FAR_FROM_ZONE` → **R9** deferred re-entry intent, armed at
   `runner.py:887-896`, re-placed only when the close re-enters the band with
   ≥3 fill-eligible bars remaining, `runner.py:580-654`).

Therefore "completion LATE, entry on-zone" is not a bug or a contradiction: a
late-closing pattern still routes an entry whose limit sits at the zone edge.
The completion record and the entry contract are simply **different frames**.
Consequences already measured: in the 6m timing study **all R7-blocked events
were LATE** (close-displaced bars fail `zone_place_allowed`), the runner
skips-then-defers via R9, and fills arrive on re-entry — i.e., lateness
translates into *placement latency*, while the entry itself stays on-zone and
can fill later. (This is why "entry on-zone" and "77 % LATE" can both be true on
the adapter path, and why the menu still shows ~48 % ON_WINDOW completions.)

### 2.5 Earliest bar a confirm could complete vs the bar it does complete (delay inventory)

| # | source of delay | where in code |
|---|---|---|
| 1 | **Sweep gate** — menu needs a *closed* detection bar satisfying the locked R2 sweep (`is_sweep`); unused as-of window = the detection bar's own interior ⇒ this is exactly the OPT-B candidate (frozen OFF by policy). | `_check_sweeps` `product_menu_mtf.py:396-431` |
| 2 | **Eligibility anchor** (default OFF path) — from the first confirm-TF **close at/after the sweep close**; strictly-closed-prefix only, no interior evaluation. | `_first_close_at_or_after` `:506-510`; `_evaluate_confirm_bar` 479-490 |
| 3 | **Confirm-TF close quanta** — a pattern complete mid-bar is only evaluated at that bar's close (M1/M5/M15/H1 granularity). | `_evaluate_confirm_bar` indices/closed prefixes 450-503 |
| 4 | **Pattern formation itself** — A/D/F completion needs the geometry (a break, a two-bar set, a divergence swing) which may only exist several bars later. | `triggers/*.py` (each spec) |
| 5 | **One-shot** — the *first* completed route on the *winning* TF consumes the episode (`_consumed`); no re-completion ever replaces a winner (a later, closer confirm on another confirm-TF cannot win). | `_win` 595-618, `_check_sweeps` gate 408-413 |
| 6 | **Expiry / give-up** — episode dies at `sweep_index + 20` detection-TF bars (`:433-448`); the signal dies at `completion_index + expiry_bars` (§24, `trigger_expiry.py:66-73`); the adapter scan retires at `arm_bar + poi_give_up_bars()` (`pipeline_adapter.py:184-191`). | as cited |
| 7 | **FR-3.1 re-anchor** — moves the *entry* to the proximal edge, never the completion; so completion distance is unaffected by entry anchoring. | `trigger_f_bos_ob.py:15-25`, `base_trigger.py:137-169` |
| 8 | **R7 + R9 placement lag** — after the win, placement itself may be skipped/deferred until the market re-enters the band (`§2.4` ref 3). | `runner.py:864-896`, `:559-654` |

**Answer to "earliest vs actual":** on the default path the earliest *eligible*
bar is per #1–2; the bar a completion *does* occur on is pushed by #3–4 (real
pattern development) and then the *placement* is further pushed by #5–8. OPT-B
moved exactly #1–2 and produced flat ON_WINDOW / −2 confirms (wide measure) —
so #3–4, not the anchor, dominate the lateness on the menu path. On the adapter
path there is **no sweep gate at all** (`§1`): the earliest possible scan bar is
the arm bar itself, and every exec-TF bar after it is scanned cursor-style until
give-up — its lateness is therefore driven by #4 + #8 only.

### 2.6 Data available vs missing for measurement

**Already available (menu path, mostly in-band):**
* `signal_data_json` stamp on every menu candidate (`product_menu_mtf.py:631-641`):
  tier, detection_tf, **confirmation_tf**, poi_id, zone bounds, episode_id,
  **sweep_ts** (ISO), trigger.
* `route_id` embeds the completion index (`pipeline_bridge.py:259`).
* The stamp is carried into pending/position records (`runner.py:640-645`
  copies `signal_data_json` into `_TrackedPending`), so the trade lineage can
  be re-joined offline.
* KPI events with route_id + poi_id + trigger: `entry_blocked`, `place_skip`
  (`SKIP_PLACE_FAR_FROM_ZONE`), `intent_*` lifecycle (`runner.py:276-286`,
  569-578, 879-886); console telemetry counters.
* Off-path: the science artifacts (wide measure episode CSVs, timing-study
  event CSV) hold full confirm geometry for their research universes.

**Missing for honest measurement on the traded path (the OPT-1 gap):**
* On the **candidate/trade rows**: the completion bar's **close**, its
  **close-ts** (only `sweep_ts` and the route_id number exist; `completion_close`
  is never materialised), `atr_at_confirm`, `distance_at_confirm_atr`, and the
  frozen **timing label** — none are exported; every geometry re-derivation
  currently needs a research replay.
* On the **adapter path**: no sweep stage ⇒ no sweep_ts by construction; the
  scan's own completion metrics (route creation ts, submission lag count) are
  equally unmaterialised.
* No exported column joins a trade to its `place-time` band distance or its
  re-entry lag (#8), so "completion lateness → placement latency → fill"
  cannot be quantified from existing logs.
* The per-run console successfully logs winners but rolls off (bounded lines).

---

## PART 3 — DESIGN OPTIONS (note only; nothing implemented)

Shared constraints honoured by all options: no R7 disable or loosening, no OPT-B
flag default true (policy note stands), no Mode B, no PnL optimisation, no new
threshold numbers (reuse `ZONE_REFINEMENT_ATR` and the frozen labels only).

### OPT-1 — Measure-only enrichment (export completion geometry) — **RECOMMENDED**

* **What:** append to the frozen menu stamp (and mirror in adapter candidates'
  `signal_data_json`) five LOGGING-ONLY fields: `completion_ts`,
  `completion_close`, `atr_at_confirm`, `distance_at_confirm_atr`,
  `timing_label`; and record one KPI event per winner with the same fields +
  `zone_place` distance at submit. No decision input.
* **Lookahead risk:** NONE — every field is known at the completing bar's
  close (Wilder-prefix ATR on closed bars only); nothing reads a forming bar.
  (Mirrors the existing stamp discipline.)
* **R7 interaction:** none — a pure export; R7/`zone_place_allowed` byte-identical
  one-shot.
* **One-shot:** untouched — one-shot consumption rules unchanged (§2.1).
* **Testability:** pure stamp/equality tests — existing `test_product_menu_mtf`
  pattern extends; assertions that the new fields are present, honest (None
  never invented), and that decisions are unaffected (golden-diff on winners).
* **Expected effect (hypothesis, geometry only):** none on ON_WINDOW/LATE rates
  by construction; it *enables* the true labels-vs-places join (completion
  lateness → R7 skip rate → re-entry lag) on the traded path, which §2.6
  currently blocks. The wider measure's 84/216 POI sample measured episodes;
  this exports the same geometry for actual candidates/trades.

### OPT-2 — Reject/defer candidates whose completion is LATE (reuse band + labels)

* **What:** at win time, apply the frozen `timing_label` on the completion
  reference; if `LATE` → either DEFER (arm an R9-style re-entry intent
  immediately, skip the direct submit attempt) or REJECT (drop candidate).
* **Lookahead risk:** none (label from closed bars at win time).
* **R7 interaction:** significant and non-trivial — R7 already skips
  LATE-at-submit bars and defers via R9. OPT-2 would move that gate UPSTREAM:
  LATE completions whose submission-bar close happened to fall back inside the
  band would ALSO be deferred/rejected, which R7 would currently place. That is
  a behaviour change in the one-shot-expiring window where episodes die at
  20 detection-TF bars — a deferral may systematically burn fills the current
  path takes. Requires the OPT-1 exports to quantify both directions first.
* **One-shot:** interacts — a REJECT burns it; a DEFER must keep it alive
  (new plumbing in the intent book or a defer flag the runner honours).
* **Testability:** pure-function testable at the candidate layer + full-suite
  regression; but intent plumbing changes mean a wider blast radius.
* **Expected effect (hypothesis):** ON_WINDOW share of *placements* rises
  (fewer late placements), LATE share of placements falls; total placed count
  likely falls (episode expiry kills deferred ones). NOT claimable as better
  outcomes without traded-path measurement.

### OPT-3 — Change *when* triggers may complete

* **Survey verdict: NOT RECOMMENDED.** On the traded menu path every closed
  confirm-TF bar at/after the sweep close is already evaluated serially
  (§2.5 #1–5); the ONLY unused as-of window is the detection bar's interior —
  which is precisely OPT-B (wider-measured, policy-frozen OFF). Any other
  completion-anchor change would either (a) re-litigate a frozen measure with a
  new number (banned), or (b) loosen the §11/§24/one-shot contract, which is
  behaviour-level change without evidence. No clear unused window exists.
* (Documented for completeness, with the honest note that this is the option
  whose only real variant — OPT-B — the Architect already resolved to NO with
  the wide measure.)

### OPT-4 — (optional, structural) align the completion reference with place geometry

* **What:** make the *placement-side* metric (distance of the submit-bar close
  to the zone band — the exact reference `zone_place_allowed` reads) the
  primary published completion-quality column, and keep close-based labels for
  history. Optionally: publish BOTH `distance_at_confirm` and
  `distance_at_place` on every candidate row.
* **Lookahead risk:** none if report-only; becomes OPT-2 the moment the
  place-reference drives a decision.
* **R7 interaction:** none (it *describes* the R7 reference; never relaxes it).
* **One-shot:** untouched.
* **Testability:** exports again — same shape as OPT-1.
* **Expected effect (hypothesis):** kills the analytic confusion (LATE label +
  on-zone entry) by separating "completion lateness" from "place-side
  distance"; better root-cause attribution for future measures.

### Recommendation

**OPT-1 first** (with the OPT-4 dual export folded in, since it is the same
enrichment work — one frozen stamp, two distances. Care: report the two
references side-by-side, never re-label the frozen ON_WINDOW/LATE taxonomy).
Rationale: the traded path currently cannot answer the exact question Branch B
exists to answer — when/where confirmation completes relative to the POI zone
**on the path we trade** — without a research replay (§2.6). OPT-2 is blocked
on OPT-1's data (its key unknown is how many LATE completions would have placed
inside the band, which a freeze-risky change cannot be designed around today);
OPT-3 is surveyed out (no unused window besides frozen OPT-B); OPT-4 alone
without OPT-1 cannot fix the missing completion-record problem.

**NEXT (single):** Architect accept/reject OPT-1 (+OPT-4 fold-in) — then an
implement prompt. Not implemented here.

---

## Constraints and bans honoured (checklist)

- Traded path defined with wiring citations (Part 1) — **TRADED_PATH: menu**
  (adapter documented as fallback + research). ✔
- All survey items answered file:function; FR-3.1 re-anchor cited in the delay
  inventory and decoupling argument. ✔
- One root-cause sentence: **the confirm record, the entry contract and the
  place gate each use a different reference frame (confirm close vs
  zone-anchored resting limit vs submit-bar close), and nothing joins them —
  so a completion can legitimately be LATE while its entry is on-zone.** ✔
- No implementation, no OPT-B default true, no R7 disable, no threshold
  fishing, no Mode B, no PnL. ✔
- `LOGIC_CHANGED: NO`; OPT-B policy freeze unchanged. ✔

## Reproduce / verify

```
config flag:        config\live_demo.json → "enable_opt_b_same_bar_confirm": false
menu coverage:      run_operator.py:413-436 + menu_covers() product_menu_mtf.py
labels (frozen):    poi_timing_early_late_study.py:190-221 ; ZONE_REFINEMENT_ATR locked_constants.py:128
place guard:        runner.py:864-896 ; R9 559-654 ; R8/P24 expiry triggers/trigger_expiry.py:66-73
wider evidence:     06_RESEARCH/OPT_B_WIDER_MEASURE_NOTE.md (+ results/opt_b_confirm_wider/)
```
