# R0 — TRIGGER ADMISSION MAP (as-coded, code-cited)

**Status: documentation only — `LOGIC_CHANGED: NO`.** Every claim below is read
from the shipped modules (file + line cited). No default changed, no code
touched, `locked_constants.py` diff empty.

---

## 1. Per detection tier: which trigger letters are on the confirm menu

`ProductMenuEngine` builds each tier's confirmation router from
`tier.trigger_types` (`04_SRC/smc/orchestration/product_menu_mtf.py`,
`MenuTier` L228-235, tier table L238-250, router construction L375-378 +
`_router_for`). Detection TF → tier lookup is the module map
`_TIER_BY_DETECTION` (L262) read by `tier_for` (L424); `register_armed`
(L450-486) returns `False` for a POI whose detection TF has no tier — such a
POI is never menu-eligible.

| Tier | Detection TF | Confirmation TF(s) | Confirm menu (`trigger_types`) | Window expiry |
|---|---|---|---|---|
| `DAY` | D1 | H1 | **A, B, C, D, E, F** (`_DAY_TRIGGERS = tuple(TriggerType)`) | `MENU_EXPIRY_BARS = 20` D1 bars |
| `H4` | H4 | M5, M15 | **A, D, F** (`_TIER_ADF`) | 20 H4 bars |
| `H1` | H1 | M5, M1 | **A, D, F** (`_TIER_ADF`) | 20 H1 bars |
| `M15` | M15 | M1 | **A, D, F** (`_TIER_ADF`) | 20 M15 bars |

Consequences (code-forced):
- **B (Leading Diagonal), C (Ending Diagonal), E (RSI Divergence) are
  confirmable on the DAY tier alone.** On every M15/H1/H4-detected POI their
  confirmation is structurally impossible — the tier router never carries the
  letter. This is the dominant starvation gate measured in
  `06_RESEARCH/BCE_STARVATION_PROBE_REPORT.md` (§4: B 144/185, C 10/12,
  E 19/21 `MENU_TIER_EXCLUDED`).
- The §15 compatibility matrix never blocks a pair — every (model, trigger)
  cell is ALLOWED; the grade (PREFERRED > STRUCTURAL > UNCOMMON,
  `compatibility_matrix.py` L1-16) is a same-bar tie-break only.

## 2. The chronological race when multiple triggers are eligible

Two race layers exist:

1. **Inside a confirmation TF (router scan):** the router evaluates bar by
   bar from the POI's arm onward; the FIRST bar at which any eligible trigger
   fires is the winner — frozen §12 chronological rule; there is no priority
   hierarchy (`trigger_router.py` L1-18). When two triggers complete on the
   SAME bar, the V1 tie-break is the §15 grade (best grade across the POI's
   model tags), then trigger letter order with the EARLIER letter winning
   (A before F, pinned post-audit) — the matrix influences routing as a
   tie-break only.
2. **Cross-TF (menu `_win`):** when several confirmation TFs of a tier carry
   completions, `confirmation_order_key` decides — earliest COMPLETION
   instant wins, an exact timestamp tie chooses the lower timeframe, then the
   stable route id (`product_menu_mtf.py` L111-123, applied L589-606). Feed
   arrival order never decides.

Because the menu is a ONE-SHOT discipline, one confirmation consumes the
episode (`_win` → winner; C3 reject leaves the episode ACTIVE,
`_candidate` L974-1048) and the POI (`_consumed`), so in the production mix a
fast A/D/F completion eliminates any later B/C/E completion on the same POI —
not by priority, but by chronology + one-shot.

## 3. Where one-story / uniqueness applies

**At the `PipelineAdapter` intake — after the menu, before risk**
(`pipeline_adapter.py`):
- Menu winners: `queue_menu_candidate` (L361-405) → `_duplicate_story`
  (source `"menu"`) → duplicate plans are dropped here and the POI is retired
  (`_drop_duplicate_poi`); survivors are claimed and submitted to the runner.
- Seek routes: the same intake guard with source `"seek"` (L607-616).
- The claim is sealed on real placement (`on_candidate_accepted` L656-671)
  and then follows the BOOK (`story_live_plans`): a sealed claim is pruned
  once nothing rests/open/in-flight carries the plan, so a later identical
  plan is a NEW story.
- F7: a confirmed winner whose risk verdict is pending is resubmitted each
  bar until accepted or its menu window closes (`_menu_deadline` L421-460);
  the research `BacktestRunner` does not report per-candidate outcomes
  (`supports_candidate_outcomes` absent) → historical one-submit semantics —
  this is the as-coded product_1y behavior (`menu_accepted 0`,
  `menu_pending 0` in every segment).
- Measured product_1y footprint: 580 duplicate winners dropped across the
  year, placed 252 → fills 239.

The menu itself does NOT run the guard — it is purely intake-level. R1 keeps
this guard AS-CODED (documented, not disabled).

## 4. CURRENT product vs INTENDED research direction

| Aspect | CURRENT (as-coded) | INTENDED (research direction) |
|---|---|---|
| Menu structure | ONE shared `ProductMenuEngine`; four tiers, per-tier trigger subsets (`_TIER_ADF` / `_DAY_TRIGGERS`) | Every trigger tag evaluable on the tiers where it is meaningful, **without cross-tag elimination** |
| B/C/E admission | DAY tier only; M15/H1/H4 structurally exclude them | R1 counterfactual: pure-tag books on the DAY tier (R1-D1) AND on the mid tiers (R1-MID) |
| Cross-tag race | Chronological first-valid + one-shot POI consumption; A/D/F normally win | No competing tags by construction in a pure book (no cross-tag race) |
| One-story guard | Single shared book at adapter intake across all tags | AS-CODED in R1 (interactions reported via `story_counters`); any per-tag book split is a FUTURE design ruling |
| Books | One blended book (one open order per plan, shared claims) | Parallel dedicated books per tag = **future; evidence from R1 feeds the design, nothing implemented this engagement** |

## 5. BCE starvation pointer

The measured FIRST-gate explanation for B/C/E zero fills is
`06_RESEARCH/BCE_STARVATION_PROBE_REPORT.md` (dominant gate
`MENU_TIER_EXCLUDED`: B 144/185, C 10/12, E 19/21; lifecycle 15.6%; fill seam
0%). R0 is the code-level restatement of that report's §1/§2; R1 is its
controlled counterfactual.

## 6. R1 method pointer

Pure single-tag books via a research-only harness that INJECTS
`tiers = (MenuTier(..., trigger_types=(T,)), ...)` into `ProductMenuEngine`
instance construction and the module `_TIER_BY_DETECTION` map at runtime —
production tier constants (`PRODUCT_MENU_TIERS`, `_TIER_ADF`,
`_DAY_TRIGGERS`) and every shipped default remain untouched; the live demo
path is never imported into the harness runs' decision surface with modified
constants (runtime patch is per-process, restored after each run, production
files unedited). See `06_RESEARCH/R1_PURE_TAG_BOOKS_REPORT.md` §2.
