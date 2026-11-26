# BRANCH B — ROOT CAUSE (Phase 0 pack, product path only)

**Status:** COMPLETE 2026-11-26. **`LOGIC_CHANGED: NO`**, no code change.
**Scope:** why Trigger B (Leading Diagonal) produced **0 routes / 0 fills** on the
product path in the frozen liveness window. A is closed (DEFER); F was not touched.
**Authority:** Lead Architect *BRANCH B — E2E engineering (product path only)*.
**Upstream evidence:** `06_RESEARCH/PRODUCT_BRANCH_LIVENESS_REPORT.md` §3.2;
`06_RESEARCH/results/product_branch_liveness/` (gitignored).
**Window (re-used, not re-picked):** exec 2025-09-01 → 2025-11-30 UTC on M5,
warm-up 2025-08-01.

---

## 1. Method — and why the geometry is trustworthy

The liveness artifacts record *which* POIs completed B but not the numbers the C3
gate compared, so this pack re-derives the completion bar from the same frozen
composition with `06_RESEARCH/scripts/branch_b_geometry.py`:

- the identical product stack and `menu_trade_funnel.MenuCycle`;
- driven to the M5 bar whose close is the recorded completion instant;
- the real `ProductMenuEngine._route_for` is left **in place for the D1 tier** and
  stubbed only for H4/H1/M15. B is confirmable **only** on the DAY (D1) tier
  (`_TIER_ADF`), so every B completion, every B C3 rejection and every B-visible
  one-shot consumption is reproduced by the engine itself, while the ~24k unrelated
  confirmations are skipped;
- the script is **fail-loud**: it aborts unless it reproduces exactly 5 B routes at
  the recorded bar, on the exact five POI ids, all C3-rejected.

Result: `RECONSTRUCTION_OK = true`, `B_ROUTES = 5`, `B_POIS = {poi-004029,
poi-004032, poi-004092, poi-004154, poi-004759}`, `BATCH_ERRORS = 0`,
`MENU_ERRORS = 0`. Runtime 75.3 s, 14,814 M5 bars, 103 batches.

**Bar-index correction (documentation precision, not a result change).** The H1
series index recorded by the liveness tap is **1717**. That index is the H1 bar that
**opens 2025-11-13 18:00 and closes 19:00 UTC**; the liveness report quoted the bar's
opening stamp as "2025-11-13 18:00". Same bar, same count — the closing instant is
19:00 UTC. `PRODUCT_BRANCH_LIVENESS_REPORT.md` §3.2 now carries a pointer.

---

## 2. B's funnel, exactly

| Stage | Count | Source |
|---|---:|---|
| D1 episodes opened by 2025-11-13 | 14 | `results/branch_b_geometry/d1_episodes.csv` |
| — already WON earlier (F) | 6 | same (`poi-003390`, `-004095`, `-004157`, `-004305`, `-004307`, `-004385`) |
| — ACTIVE at the bar | 8 | same |
| B completions at H1 index 1717 | **5** | `b_completions.csv`; liveness `completions.csv` |
| Rejected by C3 `not_in_between` | **5** | `c3_in_between = False` on all five |
| Routes (menu winners) | **0** | liveness `winners.csv`, `summary.BY_TRIGGER.B.routes` |
| Reached the risk seam | 0 | `menu_submitted` has no B contribution |
| Placed | 0 | no B ticket in `orders.csv` |
| Fills | 0 | no B ticket in `fills.csv` |

B never reached the risk gate, the session gate or the order book: the funnel stops
at the **route** stage. `BY_TRIGGER.B` reports `gate_rejected_c3 = 5`, `routes = 0`,
`blocked_pre_place = 0`, `expired_* = 0`, `withdrawn = 0`.

The six earlier WON D1 POIs explain why the liveness count is five and not eleven:
an earlier F confirmation on the same POI consumes it (`_win` → `_consumed`), so its
episode cannot complete again. This was verified rather than assumed — the first
reconstruction attempt produced 11 routes precisely because its stubbed scan never
consumed anything, and the fail-loud check caught it.

---

## 3. Exact reject: reason and code path

- **Reason token:** `not_in_between` (`04_SRC/smc/triggers/in_between.py:20`
  `NOT_IN_BETWEEN`), recorded by the menu as `rejected_H1_not_in_between`.
- **Path:** `ProductMenuEngine.on_execution_bar` → `_route_for(episode, H1)` returns
  the route → `_win(episode, route, H1)` → `_candidate(episode, route, H1,
  window_end_ts=…)` → `candidate_from_route(..., completion_price=completion_close)`
  (`04_SRC/smc/backtest/pipeline_bridge.py:180-251`) → `trigger_in_between(
  zone_low=zone.bottom, zone_high=zone.top, completion_price=close)` →
  `False` → `_candidate` returns `None` → `_win` appends
  `rejected_H1_not_in_between` and **leaves the episode ACTIVE** so a later
  completion could still win.
- **Rule text:** `in_between.py` — "an LTF trigger completion is a VALID entry only
  when the trigger fired AND the completion bar's price sits inside the routed POI
  zone body … no tolerance band, no median gate". Master card §3.4.
- **Stage:** route/plan construction, *before* `queue_menu_candidate`, *before* the
  risk engine, *before* any placement. No other gate is involved for B.

---

## 4. Geometry of the five completions (the decisive evidence)

One shared B signal, because B's plan is defined by the **impulse**, not by the POI:

| Fact | Value |
|---|---|
| Direction | LONG (all five zones) |
| Wave-5 index / level | H1 index 1711 / **4244.925** |
| Impulse origin = stop reference | **4096.845** |
| Impulse height | **148.080** = **7.02 × H1 ATR14** (ATR14 at bar = 21.084) |
| Fib band (61.8 % → 50 %) | **4153.412 → 4170.885** |
| Planned entry (limit) | **4170.885** |
| Completion bar close (C3 input) | **4157.639** |

Per POI (`results/branch_b_geometry/b_completions.csv`):

| POI | Zone low–high | Height | Episode sweep | Close − zone | Entry − zone | Fib band vs zone |
|---|---:|---:|---|---:|---:|---|
| `poi-004029` | 3940.685–3995.775 | 55.090 | 2025-10-29 | **+161.864** (+7.68 ATR) | +175.110 (+8.31 ATR) | band entirely **157.637 above** the top |
| `poi-004092` | 3940.685–3995.775 | 55.090 | 2025-10-29 | **+161.864** (+7.68 ATR) | +175.110 (+8.31 ATR) | band entirely 157.637 above |
| `poi-004154` | 3940.685–3995.775 | 55.090 | 2025-10-29 | **+161.864** (+7.68 ATR) | +175.110 (+8.31 ATR) | band entirely 157.637 above |
| `poi-004759` | 4024.295–4137.448 | 113.153 | 2025-10-31 | **+20.191** (+0.96 ATR) | +33.437 (+1.59 ATR) | band entirely **15.964 above** the top |
| `poi-004032` | 4127.555–4155.075 | 27.520 | 2025-11-12 | **+2.564** (+0.12 ATR) | +15.810 (+0.75 ATR) | band bottom **1.663 below** the top → a **1.663-unit (0.08 ATR) overlap sliver** |

All five: `c3_in_between = False`.

Reading, no more than the numbers support:

1. **Four of the five are arithmetically impossible.** For `poi-004029/-004092/
   -004154/-004759` the *entire* 50–61.8 % band lies above the POI body, so no close
   that satisfies B's trigger can satisfy C3.
2. **One was barely possible and the market did not cooperate.** `poi-004032` has a
   1.663-unit overlap between the band's deep edge and the zone top; a close in that
   sliver would pass both rules. B requires the *first* close into the band, and that
   close was 4157.639 — 2.564 above the zone top. The trigger is not free to choose a
   different close.
3. **The planned entry is outside the zone in every case** (+175.11 / +33.44 /
   +15.81). So a gate that compared the *planned entry* instead of the completion
   close would still reject all five — the mismatch is in the anchor, not in which
   price the gate samples.
4. **The five completions are one plan, not five.** Same direction, same wave-5, same
   origin, same entry/stop: B's geometry is POI-independent. Had they routed, the
   locked ONE-STORY rule would have collapsed the three identical-zone POIs at intake
   (same direction + same trigger + exact same entry/SL/TP + overlapping zone).

---

## 5. Classification: (a) / (b) / (c)

| Rule | Where | Class | Basis |
|---|---|---|---|
| C3 completion containment | `in_between.py`; `pipeline_bridge.py:248-251`; `product_menu_mtf._candidate` | **(a) intentional policy** | Master card §3.4, single choke point, no tolerance; applied identically to every trigger |
| B entry = 50–61.8 % retracement of a 5-wave impulse | `trigger_b_leading_diagonal.py:14-18, 40-62` | **(a) intentional policy** | R1 §7; `FIB_MIN`/`FIB_MAX` are explicitly marked **UNFROZEN** in the module header ("pending authorization before live use") |

**No (b) bug.** Neither rule is misapplied: B fires exactly on "first close into the
fib band", and C3 rejects exactly "close outside the POI body". The completion really
was outside the body; the reject is correct for the rule as written.

**No (c) config mis-wire.** There is no config/flag/constant governing this
interaction. `ZONE_REFINEMENT_ATR` is not involved anywhere in the B path, and no
allow-list or tier setting can change the outcome (B is already enabled on the D1
tier; the D1 tier already evaluates B).

**The finding is the interaction, not either rule:** B's entry anchor is the
*impulse*, while C3's validity anchor is the *POI body*. Those are different
geometries, and for an impulse that travels away from the zone the retracement band
sits away from the zone too. This is a design-level incompatibility, which is why it
needs an Architect ruling and not an engineering patch.

---

## 6. The two mandated questions, answered directly

**Q1 — Is C3 applying the same rule that blocked far-outside F before the FR-3.1
re-anchor?** **No.** They are different rules at different stages with different
remedies:

| | C3 (this branch) | R7 / FR-3.1 (the F case) |
|---|---|---|
| Rule | Completion-bar **close inside** the POI body, exact, inclusive, no tolerance (`in_between.py`) | Market **close distance from the zone** against an ATR band (`zone_place_allowed`, `fill_regime_policy.py`, `SKIP_PLACE_FAR_FROM_ZONE`) |
| Stage | Route/plan construction (menu `_candidate` / adapter scan) | Placement, inside `BacktestRunner._process_entries` |
| On failure | No plan at all this bar; episode stays ACTIVE | Plan is kept and **deferred** through an R9 intent, re-tried per bar |
| Remedy if wrong | Would be an entry-validity rule change | Was a zone-anchored entry re-anchor (FR-3.1) |

So "far-outside F" was a placement-distance problem that FR-3.1/R9 solved by
anchoring the limit; B never reaches placement, so that machinery cannot help it.

**Q2 — Does B use a zone-anchored entry or a wave-based entry that systematically
sits outside the POI zone?** **Wave-based, and yes.** `entry = wave5 ∓ 0.5 × impulse
height` (`trigger_b_leading_diagonal.py:55-61`); the POI contributes only direction,
arming and the post-arm requirement that the impulse be new. With a 148.08-point
(7.02 ATR) impulse, the band sits 50–61.8 % back from the wave-5 extreme, which in
this window placed the **whole band above the POI body for four of five POIs** and
left a 0.08-ATR sliver for the fifth.

---

## 7. Ruled out (so the pack is falsifiable)

- **Not tier exclusion.** B is in `_DAY_TRIGGERS = tuple(TriggerType)`
  (`product_menu_mtf.py:239-247`); the five completions *did* reach C3, so B was
  admissible on the DAY tier.
- **Not arming starvation.** 14 D1 episodes existed by the completion bar; the five
  POIs were armed, swept and evaluated.
- **Not a menu-window problem.** All five were inside their window
  (`within_window = True`, upper bound index 1718).
- **Not a risk / session / spread / breaker / R7 problem.** Nothing reached the
  runner: `routes = 0`, `blocked_pre_place = 0`.
- **Not a duplicate-identity problem.** The ONE-STORY guard runs at intake, *after*
  the route; with zero routes it never fired for B.
- **Not a data problem.** The same M1 spine, the same resampled series, the same
  `BATCH_ERRORS = 0` / `MENU_ERRORS = 0` as the liveness run.

---

## 8. Phase-1 gate decision

Every B death is class **(a)** — and unlike A, the class is a *structural* one: two
individually intentional rules whose anchors disagree, with no bug and no config to
restore. Per the task's Phase-1 rule, **no code was changed**; no C3 relaxation, no
`ZONE_REFINEMENT_ATR` widening, no B-only exemption, no entry-anchor change was
implemented. The Architect options are set out in
`06_RESEARCH/BRANCH_B_E2E_REPORT.md` §5.

**Bans honoured:** no A re-open, no F change, no D volume proxy, no expectancy/PF
criterion, no range/constant fishing, no expert protocol, no `04_SRC` or
`locked_constants.py` edit.
