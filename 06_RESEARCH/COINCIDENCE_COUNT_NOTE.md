# COINCIDENCE COUNT — HTF THESIS ∩ LTF PROOF IN-WINDOW

> **DIAGNOSTIC — NOT EDGE.** Counts only: 585 of 1,093 HTF zone theses
> show an LTF proof (Stage-3 completion A–F) inside a 4-hour window of
> their reference, but only 6.0% of the coincidences on armed geometry
> ever became a route and 1.1% a fill. No gate was loosened, no threshold
> moved, no routing rule, episode store or live rule follows, and no
> production code was touched. No table below supports or refutes edge.

**Date:** 2026-10-13 · **Authority:** Lead Architect owner plan
`00_LOCKED/OWNER_PLAN_MULTI_TF_TRANSLATION_2026-10-13.md` (binding ordered work,
**step 2 = coincidence count**) and proof register
`06_RESEARCH/RESEARCH_PROOF_REGISTER_2026-10.md` §B3 **BACKUP_NEXT**.
**COINCIDENCE_STATUS: PASS** (Step-3 reconciliation exact — 946 / 490 / 605,
0 mismatches; exec-bar cross-check 3/3; 12 new tests green).
**Scope:** read-only measurement. `LOGIC_CHANGED: NO` — `04_SRC/smc` decision
paths untouched, `locked_constants.py` diff empty. No routing change, no gate
change, no episode-store implementation, no live/paper trading.

---

## 1. Question and pre-registered kill criteria

The register's BACKUP_NEXT asked the cheapest architectural question on disk:
**how often does an LTF proof coincide, in a short frozen window, with an HTF
zone thesis — including theses the product never armed and never routed?**
The owner plan's step 2 states the same question and forbids any routing change
from its answer ("unarmed rows allowed **for counting only**").

Kill criteria, frozen before the run (register BACKUP_NEXT):
`COINCIDENCE_N = episodes with ≥ 1 coincidence at H = 48`

- `< 10` → **SEQUENCE_REDESIGN_MOOT** (the order constraint removes nothing
  measurable);
- `≥ 10` **and** window-stable, `|N38 − N58| / N48 ≤ 0.25` → **mass present**
  → the criteria say *carry a dated coincidence-routing design proposal*
  (still no code in this task);
- otherwise → **INCONCLUSIVE** (the definition is too fragile to carry).

## 2. Method (frozen before running)

| Item | Value |
|---|---|
| Population | **all 1,093** unique Step-1 episodes, carried by Step-2's `sweeps_per_episode.csv` (one source: swept flag, `first_sweep_ts`, zone, direction, TF, kind) |
| LTF proof | product **Stage-3 completions A–F**, evaluated exactly as Step 3 — `poi_swept_ltf_confirm`'s evaluation mode **imported, not forked** (one `SeriesState(M5)` per bar, `TriggerRouter` matrix-eligible triggers, `TriggerContext` with the episode POI). Episode POI construction is Step-3's verbatim function on Step-2 rows (no `m8_kind` enrichment — that would move the fidelity gate) |
| Reference anchor | `SWEEP` = `first_sweep_ts` (exact M5 bar, 946 episodes — Step 3's own anchor); `PROXY_DAY_CLOSE` = **last** M5 bar of `first_seen_date` (147 unswept episodes). First-seen dating is day-granular; taking the day **close** is the conservative no-look-ahead choice |
| Coincidence window | `ref_bar < completion_bar ≤ ref_bar + H` — Step 3's link rule verbatim, no new magic numbers. Primary **H = 48**; sensitivity H ∈ {20, 38, 58} (20 = the locked give-up scale; 38/58 = ±20% of 48). Derived as windowed subsets of one pass (keep-window `ref+58`), never re-run |
| De-duplication | pairs unique by `(bar, letter)`; RAW (undeduplicated) Step-3 totals reported alongside so divergence is visible |
| Costs / PnL | none — this is a counting study by instruction |
| Stratifiers (columns, never filters) | `product_fate`, `ref_kind`, `state_at_first_coincidence`, `armed_at_first_coincidence`, first-coincidence trigger letter, TF / M8 group |

`product_fate` precedence (frozen): `filled` > `routed` > `armed_never_routed`
(Step-4 lifecycle join) > `armed_never_routed_zone_only` (direction-free
containment inside one of the 30 armed POIs' zone bands) > `never_armed`.
The last two separate "the product armed geometry here" from "the product never
armed anywhere near here".

`state_at_first_coincidence` precedence: `swept` > `armed_only`
(`armed_bar ≤ bar`) > `proxy_first_seen`.

Script: `06_RESEARCH/scripts/coincidence_count.py` (≈ 8 min: 14 s load + one
pass over 42,296 M5 bars).

## 3. Integrity — the count uses Step 3's own instrument

| Check | Result |
|---|---|
| SWEEP-anchored swept episodes | **946 / 946** (Step 3's population) |
| Confirmed within 48 (sweep anchor) | **490 / 490** (Step 3's published count) |
| Completions within 48 (sweep anchor) | **605** raw = **605** deduplicated (Step 3's published total — zero duplicate pairs) |
| Per-episode flag mismatches vs `confirm_per_episode.csv` | **0** |
| Pre-run smoke (`--until 2025-06-20`): fully-covered swept subset | 92 episodes, **0** mismatches, completions 62 = 62 |
| Exec-index mapping: `armed_bar`/`entry_bar` → timestamp | warm-up offset asserted (`6018` = 2025-06-01T22:00Z) and cross-checked on the frozen run's own 3 trade entry bars — **3/3 exact** |
| Fate map cross-check | the 134 coincident lifecycle-joined `armed_never_routed` episodes decompose **exactly** into Step-4's gap reasons (`scanned-no-route` 102 + `routed-before-sweep` 32) |
| Skipped for want of an anchor | 0 |
| Determinism | full re-run (8 min, no arguments) **byte-identical on all three artifacts** (SHA-256 match) with identical counts and verdict |

The reconciliation is the point: the numbers below are produced by the same
evaluation that produced Step 3's 490, extended to a wider population, a second
anchor and four horizons — not by a re-implementation.

## 4. Headline counts

| Horizon (M5 bars) | Episodes with ≥ 1 coincidence (1,093) | Sweep-anchored subset (946) |
|---|---:|---:|
| 20 (locked give-up scale, ~100 min) | 346 | 282 *(= Step 3)* |
| 38 | 522 | 430 |
| **48 (primary, ~4 h)** | **585** | **490** *(= Step 3)* |
| 58 | 642 | 543 |

- **COINCIDENCE_N = 585 episodes** (53.5% of all theses), **713 coincident
  pairs**. By anchor: 490 sweep-anchored + **95** unswept/thesis-anchored
  (`PROXY_DAY_CLOSE`).
- Window stability: `|522 − 642| / 585 = 0.205 ≤ 0.25` → **stable**; the strict
  sweep-anchored subset is stable too (`|430 − 543| / 490 = 0.231`).
- Timing: the first coincidence lands **19 M5 bars** (median) after the sweep
  anchor — p25 10, p75 28.25, max 48; the thesis-anchored stratum is earlier
  (median 10). One third of theses (346) already coincide inside the **20-bar**
  give-up scale.
- Group rates at H = 48: H4 30/75 (**40.0%**) · H1 108/196 (**55.1%**) ·
  M8-H4 352/659 (**53.4%**) · M8-D1 81/137 (**59.1%**) · M8-W1 14/26 (**53.8%**).
- First-coincidence trigger mix (585): **F 477 (81.5%)** · A 56 · B 46 · E 5 ·
  C 1 — the same family dominance as every prior pack, now measured at the
  thesis rather than the route.

## 5. Stratification — the mass is real, but not where a routing tweak could reach it

| `product_fate` | Episodes | Coincident @48 | Coincident @20 | Routed | Filled |
|---|---:|---:|---:|---:|---:|
| `filled` | 3 | 3 | 2 | 3 | 3 |
| `routed` | 13 | 13 | 10 | 13 | 0 |
| `armed_never_routed` (Step-4 join) | 134 | 134 | 75 | 0 | 0 |
| `armed_never_routed_zone_only` (band probe) | 363 | 118 | 73 | 0 | 0 |
| `never_armed` | 580 | 317 | 186 | 0 | 0 |
| **Total** | **1,093** | **585** | **346** | **16** | **3** |

- **268 coincidences sit on armed geometry** (3 + 13 + 134 + 118); the other
  **317 are on `never_armed` theses** (250 of them Step-4 `no-product-POI` rows
  plus 67 from the unswept/other stratum). Separately, **90 of Step-4's 340
  `no-product-POI` rows do sit inside an armed POI's own zone band** — the
  direction-free probe labels them `zone_only`, not `never_armed`.
- State of the first coincidence: `swept` 543 · `armed_only` 28 ·
  `proxy_first_seen` 71; **223** first coincidences arrived at/after the
  recorded `armed_bar` of the covering (smallest-area) armed POI — the rest
  predate their covering POI's arm.
- **Validated-only vs armed-only** (disclosed cross-artifact join, no new scan):
  of the **250** coincident `never_armed` rows that appear in
  `confirm_never_routed_474/decomposition.csv` (all reason A = no product POI),
  **208 sit on geometry present in the accepted H4/D1 packs** — validated
  elsewhere, never armed here — and **42** are raw-only detections
  (pillar-stage territory). The unarmed coincidence mass is therefore dominated
  by *validated-but-unarmed* geometry, reproducing that study's 271/69 A-split at
  the coincidence stratum.
- Honest override: `armed_never_routed_zone_only` 363 is a *direction-free*
  containment probe, not a lifecycle join (8 of the 30 armed records carry no
  direction field, so no directional join was invented); where several armed
  bands contain an episode, attribution is the **smallest-area** band, ties by
  `poi_id` (Step-4 Tier-B discipline — 52 of the 1,093 episodes nest in more than
  one band, 27 of them coincident, so the choice is not vacuous). Consequence:
  **90 of
  Step-4's 340 `no-product-POI` rows sit inside an armed zone band** and are
  labelled `zone_only` here; Step-4's Tier-C says "none". Both are published;
  the disagreement is reported, not reconciled.

## 6. Conversion — coincidence is necessary, not sufficient

| Quantity | Value |
|---|---:|
| Coincident episodes on armed geometry | 268 |
| … that ever routed | **16 (6.0%)** |
| … that ever filled | **3 (1.1%)** |
| Armed-geometry episodes overall (coincident or not) | 513 → 16 routed (3.1%) |
| Routed episodes | 16 — **all 16 are coincident** (no route exists without a completion; coincidence is the necessary condition, never the sufficient one) |
| Coincidences on armed geometry that never routed | **252** — of which 134 are Step-4's known buckets: `scanned-no-route` 102, `routed-before-sweep` 32 (one-shot already consumed), and 118 sit in armed zone bands without a lifecycle join |

## 7. Kill-criteria verdict

```
KILL_CRITERIA_VERDICT: COINCIDENCE_MASS_PRESENT
  COINCIDENCE_N (H=48) = 585 / 1,093 episodes, 713 pairs, 81.5% trigger F
  window swing |522-642|/585 = 0.205 <= 0.25 (stable)
  strict sweep anchor: 490/946 (identical to Step 3), swing 0.231 (stable)
  the verdict does not depend on the anchor or the horizon choice
```

**Reading — is the sequential-order constraint binding?** Not on *proof
availability*. Proof is abundant (585 theses, 713 completions) and **early**
(median 19 M5 bars ≈ 95 minutes after the sweep; a third of it inside the
20-bar give-up scale), so "the LTF never confirms in time" is not what starves
the book. Where it binds is **conversion**: coincidence → route is 6.0% on
armed geometry, and route → fill is 3/16 — with 252 armed-geometry
coincidences ending in `scanned-no-route`, `routed-before-sweep`, or no
lifecycle join at all. This composes exactly with the two facts already on
record: the near-miss study's **PLACEMENT_NOT_PRIMARY** (the gates removed
nothing takeable) and Stage-3 visibility's **261 of 263** completions arriving
after the armed POI's scan had closed (the FRESH → first-touch lifecycle, not
missing geometry).

So the owner plan's step-2 question has a two-part answer. (1) A
**coincidence-routing idea has measurable mass on disk** — dozens-plus,
window-stable, not single digits; per the register it therefore earns a *dated
design proposal*, and this note recommends it be carried as the owner plan's
steps 3–4 (**unified episode store → explicit reactive admission rule**) rather
than a wider window. (2) Mass is not the same as permission: 74% of the
coincidences (435/585) sit on theses the product never armed, so admitting them
is an **admission/validation** decision — and 208 of the 250 unarmed
coincidences already sit on geometry the accepted packs contain, so the question
is *arming and admitting* that geometry, not finding it. The standing bans plus
the near-miss verdict both argue against reaching it by loosening gates for
sample size. No gate, threshold, window or store change is proposed, and none
is authorized by this note.

## 8. Limitations (binding on any reuse)

- **Counts, not rates with error bars:** one 6m window, one feed, one grid. The
  verdict is a threshold on a count, not a statistical test.
- **PROXY anchor:** the 147 unswept theses use the day **close** as their
  reference (conservative, no look-ahead). They carry 95 of the 585
  coincidences and are always reported as their own stratum — enabling them
  moves the headline, so the strict sweep-anchored 490 is quoted beside it.
- **Fate is a stratification label, not a per-POI arming log:** per-POI
  validation/arm logs do not exist (register F-08). Episodes outside Step-4's
  490 confirmed rows are never labelled `routed`/`filled` (route/fill facts are
  time-qualified only in the lifecycle); 90 rows disagree with Step-4's Tier-C
  "none" under the direction-free band probe.
- **`armed_never_routed_zone_only` is a probe, not a join** (direction-free,
  inclusive bounds, no tolerance invented).
- **Completion bars index the warm-up-inclusive Step-3 M5 grid**; the replay's
  `armed_bar`/`entry_bar` are exec-window indices, converted with the asserted
  warmup offset and cross-checked 3/3 on the frozen run's trades.
- **Single-pass horizon derivation:** H ∈ {20, 38, 58} are windowed subsets of
  the ref+58 pass; the keep-window itself is never re-run.
- **Banner convention:** no CSV carries an in-file banner — every research CSV
  in this repo is a banner-free data table by convention; the
  `DIAGNOSTIC — NOT EDGE` stamp is carried by `summary.json` (`banner`) and by
  this note, once per artifact set.
- No expectancy, PnL, win-rate, profit-factor or edge claim exists anywhere in
  this artifact set.

## 9. Artifacts, governance, NEXT

- Script: `06_RESEARCH/scripts/coincidence_count.py` (imports Step-3's
  evaluation + the population artifact; forks nothing; `--until` smoke mode).
- Results (local-only, gitignored): `06_RESEARCH/results/coincidence_count/`
  — `episode_coincidence.csv` (1,093 rows: fate, anchors, horizon flags,
  first coincidence, state), `pair_events.csv` (809 recorded pairs, 713 inside
  H=48), `summary.json` (banner, frozen rules, integrity gate, mixes,
  sensitivity, kill-criteria verdict, limitations).
- Tests: `04_SRC/tests/test_coincidence_count.py` (**12**: frozen horizons +
  exec origin pinned, window edges both sides, `None` safety, nested-horizon
  monotonicity, de-duplication, day-close proxy anchor, containment bounds +
  smallest-area container tie-break, fate precedence, state precedence, kill-rule
  bounds incl. the 25% stability edge, TF group).
- Governance: `SESSION_HANDOFF.md`, `POST_V1_ACTIVE_TODO.md`, `CHANGELOG.md`
  (LOGIC_CHANGED: NO).
- **NEXT:** per verdict → carry the coincidence/admission design as owner-plan
  steps 3–4 (episode-store design lock, then the explicit reactive admission
  rule with a pre-registered measure **before** code); in parallel the
  entry-representation question stays the open strategy thread
  (near-miss: entries are zone-edge limits left far behind by the impulse).
  No gate loosening, no routing change, no ML.

---

**RETURN BLOCK**

```
COINCIDENCE_STATUS: PASS
WINDOW: exec 2025-06-01 → 2025-11-30 (M5, warm-up from 2025-05-01)
N_EPISODES: 1093
N_COMPLETIONS: 809 recorded reconstructions (713 inside H=48)
N_EPISODES_WITH_COINCIDENCE: 585
N_PAIRS: 713
PRIMARY_H_BARS: 48
RATE_EPISODE: 0.5352
BY_FATE: {filled: 3/3, routed: 13/13, armed_never_routed: 134/134,
          armed_never_routed_zone_only: 118/363, never_armed: 317/580}
KILL_CRITERIA_VERDICT: COINCIDENCE_MASS_PRESENT
NOTE_PATH: 06_RESEARCH/COINCIDENCE_COUNT_NOTE.md
SUITE: 1051 passed (1039 -> 1051; +12 new)
LOCKED_CONSTANTS_DIFF: empty
LOGIC_CHANGED: NO
HANDOFF_UPDATED: YES
NEXT_READY: episode-store design-lock | entry-representation focus | Architect review
```
