# ZONE DEDUP ↔ EPISODE LIFECYCLE — DESIGN LOCK (LEG 5)

> **DESIGN — NOT IMPLEMENTED.** This note changes no code, no constant, no
> pillar, no trigger, no fill model and no expiry. `ZoneDedup.retire` does not
> exist after this leg, and nothing is wired to it. It defines the rules an
> **implement leg** must satisfy, and the gates that leg must pass before its
> result may be read.

**Date:** 2026-10-20 · **Authority:** Lead Architect ruling **R-ARM**
2026-10-20 (`ARM_FILTER_IS_BOTTLENECK` — intentional dedup, lifetime too long;
engine prunes terminal episodes, `ZoneDedup` never forgets).
Prior HOLDs untouched: **LEG 1 `HOLD_P2_FVG`** · **LEG 3 `FILL_PATH_HEALTHY`**.
Upstream measurement: `06_RESEARCH/PASSED_TO_ARMED_ATTRIBUTION_REPORT.md`
(LEG 4). **Scope:** design only. No `04_SRC/smc` edit, no test change,
`locked_constants.py` diff **empty**, `LOGIC_CHANGED: NO` (this leg).

---

## 1. Problem (measured, not inferred)

The arm path has exactly three gates, in this order, and no others
(`MultiTFProductRuntime._arm_passed`, `04_SRC/smc/orchestration/multi_tf_runtime.py:403-503`):
`engine.episode(poi)` → `dedup.seen(poi.zone)` → `engine.arm_at(poi)`. LEG 4's
capture wrapped those three gates and attributed all 2,021 PASS events of the
frozen 6m window:

| Fact | Value | Source |
|---|---|---|
| PASS events | **2,021** | report §4 |
| ARMED | **30 (1.48%)** | report §5 |
| `SKIP_DEDUP_EPISODE` | **1,991 (98.52%)** | report §5 |
| `SKIP_TRACKED` | **0** | report §5 |
| all seven gates with no code path, `SKIP_OTHER`, `DATA_GAP` | **0** | report §5 |
| distinct blockers | **29** (of the 30 armed zones) | report §5.2 |
| blocker age — median / max | **29.5 d / 140.3 d**; **49.8%** ≥ 30 d | report §5.2 |
| suppressions from a zone armed ≥ 90 d earlier | **227** | report §5.2 |
| median coverage of the PASS zone by its blocker | **0.461** (p10 0.128 / p90 1.000) | report §5.2 |
| identical 6 dp bounds | **11.5%** (229) | report §5.2 |
| zero-area edge-touch suppressions | **11** | report §5.2 |
| cross-batch / same-batch suppressions | **1,989 / 2** | report §5.2 |
| episode clusters under the product's own rule | **30**, each armed **once** | report §5.1 |

Two readings matter for this design and nothing else does:

1. **The filter is doing real work but for a lifetime it was never meant to
   own.** The 2,021 events are 30 spatial episodes, each armed exactly once —
   identity holds. But 54.4% of suppressions overlap their blocker by less than
   half the PASS zone, half arrive ≥ 30 days after the blocker armed, and the
   extreme case shares a single boundary with zero area. A zone armed in June
   suppresses a November structure because the *key* never dies.
2. **The asymmetry in the counts is a lifetime, not an identity, defect.**
   `SKIP_TRACKED = 0` beside `SKIP_DEDUP_EPISODE = 1,991` means no suppression
   is explained by "the engine still tracks that POI" — every one is explained
   by "a key exists". `ZoneDedup` exposes `seen` / `register` / `__len__` and
   nothing else (`multi_tf_runtime.py:135-169`).

### 1.1 A sharper code fact found in this leg (corrects the LEG 4 wording)

LEG 4 says "the engine's registry *is* pruned every bar". That is true for
**VIOLATED** episodes only. The per-bar caller
(`PipelineAdapter.prune_terminal_pois`, `backtest/pipeline_adapter.py:344-373`)
retains every POI for which `_may_route(poi, state, bar_index, bar=None)` is
true (`:362-366`), and the legacy no-bar contract of `_may_route` returns
**True for any FRESH or TESTED POI** (`:442-445`). A TESTED episode is
therefore **never** pruned through the adapter path.

Verified read-only against the shipped classes (no file written, no code
changed): one `M1` POI armed at bar 0, driven to `TESTED`, `give_up = 20` bars —
`prune_terminal_pois(set(), bar_index=…)` returns `[]` and `tracked_pois()`
stays length 1 at bars **5, 25, 500 and 5000**.

Consequence for this design, stated plainly: **"retire exactly when
`prune_terminal` removes the episode" would release only VIOLATED keys** and
would leave the dominant suppression population (first-touch TESTED, and
give-up-closed FRESH) untouched. R3 therefore defines death on the product's
own lifecycle facts and lets the engine's retention behaviour stay exactly as
it is — the engine's memory is not this leg's subject, and changing what
`tracked_pois()` returns would change the per-bar scan loop.

---

## 2. Current code surface (APIs + call graph, line-level)

### 2.1 `smc.orchestration.multi_tf_runtime.ZoneDedup` — the full surface

| Member | Lines | Behaviour today |
|---|---|---|
| `__init__` | 145-147 | `self._zones: list[tuple[str, float, float]] = []` — a list of `(direction, top, bottom)`, **no owner, no timestamp, no state, no TF** |
| `seen(zone)` | 149-159 | `True` when any stored entry has the **same direction** and **inclusive** span overlap: `known_top >= bottom and top >= known_bottom`. The queried zone's floats are used **unrounded** |
| `register(zone)` | 161-166 | appends `(str(direction), round(top, 6), round(bottom, 6))` |
| `__len__` | 168-169 | number of stored keys (monotone) |

There is **no** `remove`, `retire`, `clear`, `prune`, `expire`, iteration or
ownership attribute. `_zones` is private and nothing outside the class reads it.

### 2.2 Call sites (who registers, who asks)

| Caller | Line | What it does |
|---|---|---|
| `MultiTFProductRuntime.__init__` | 272 | `self.dedup = ZoneDedup()` — the registry lives on the **runtime**, one per session/run |
| `_arm_passed` (product path) | 464 | `if dedup.seen(poi.zone): report.duplicates.append(poi.id); continue` — **the only suppression** |
| `_arm_passed` (product path) | 493 | `dedup.register(poi.zone)` immediately after `engine.arm_at` **succeeds** (so a failed arm registers nothing) |
| `_run_degraded` (tests only) | 569 / 585 | the same two calls on the explicit single-TF degraded path |
| tests / research captures | `04_SRC/tests/test_multi_tf_product_path.py`, `06_RESEARCH/scripts/c1_multi_tf_parity_smoke.py`, `06_RESEARCH/scripts/passed_to_armed_study.py` | construct or wrap the registry directly |

`run_batch(..., dedup=None)` (`:294-320`) lets a caller pass an override
registry; the default is the runtime's own.

### 2.3 Episode identity and the arm bar

| Item | Where | Fact |
|---|---|---|
| Engine episode record | `engine.py:252-262` (`_PoiEpisode`), stored in `self._episodes[poi.id]` | `arm_bar`, `posture`, `arm_candle_ts`, `revalidated_bar`, `fired`, `outcome` |
| `arm_at(poi, arm_bar)` | `engine.py:250-310` | CREATED → FRESH, then records `_PoiEpisode(arm_bar=…)`; raises for any state other than CREATED/FRESH |
| `episode(poi)` | `engine.py:312-314` | `self._episodes.get(poi.id)` — the tracked check the arm loop uses first |
| POI id | uuid4 per detection | never a stable identity; LEG 4 used it only as a lookup key |
| Armed zone object | `poi.zone` at arm time | the exact object registered in `ZoneDedup`; nothing rewrites it later (no refinement path exists in `_arm_passed`) |
| One arm → one key | `_arm_passed` | exactly one `register` per successful arm; **no episode is ever registered twice** |

### 2.4 Retirement side: what the engine and adapter actually do per bar

| Step | Where | Fact |
|---|---|---|
| Backtest per-bar prune | `backtest/runner.py:317-319` → `_prune_engine_state` (`:640-656`) | runs at step 6 **before** `adapter.generate_candidates`; retain = POI ids of `orders.active()` + `positions.open_positions()` |
| Paper per-bar prune | `paper/runner.py:773-780` → `_prune_engine_state` (`:940-951`) | same ordering; retain = pendings + open positions; falls back to `engine.prune_terminal(retain)` when the adapter has no method |
| Adapter prune | `backtest/pipeline_adapter.py:344-373` | adds `_workflows` ids to retain, adds POIs `_may_route(..., bar=None)` accepts (**all FRESH and TESTED**), calls `engine.prune_terminal(retain)`, then drops its own bookkeeping for the pruned ids |
| Engine prune | `engine.py:510-535` | drops `_episodes[poi.id]` and the POI from `_armed_order` for `TESTED`/`VIOLATED` not in `retain`; **returns the pruned ids** |
| Seek-book closure at give-up | `pipeline_adapter.py:150-164` | for a workflow-less, never-routed POI past `arm_bar + poi_give_up_bars()`: `self._routed.add(poi.id)` and the cursor is dropped — **the scan book closes; the §5 state does not change and the key is untouched** |
| Violation | `pipeline_adapter.py:238-243` | workflow dropped, resting limit cancelled; the §5 state is VIOLATED, which the engine prunes on the next bar |
| R9 intents | `backtest/intents.py:92, 140` | `intent.alive()` / `IntentsBook.alive_intents()` — an alive intent may still place, and is **not** in any retain set today |

### 2.5 Ordering inside one bar (frozen composition)

`06_RESEARCH/scripts/phase3_structure_funnel.py:245-306`: the cycle wrapper runs
`runtime.run_batch(...)` **when a new H1 close is detected**, and only then
calls `self.inner.on_bar(bar, bar_index, clock)` (the runner, whose step 6 is
the prune). Therefore, for one bar `b`:

```
run_batch(as_of=b, arm_bar=b)        ← arms; reads the key set as of b-1's prune
runner.on_bar(b): prune → scan       ← retirement happens here, for bar b
```

Causal consequence, normative for R3: **a key retired at bar `b` can first
affect an arm at the next H1 batch (bar > b).** No arm can ever be decided with
information from its own bar's prune, and no retirement can retroactively change
a batch that already ran. That is the no-lookahead guarantee this design relies
on — no new clock is introduced.

### 2.6 Findings that constrain the rules

- **F-1 (TESTED never pruned).** §1.1. Retirement may not be defined as "the
  engine removed it".
- **F-2 (live-obligation set is incomplete).** The runner's retain set is
  orders + positions; an alive R9 intent is a live obligation
  (`intents.py:92`) and is not included. Retiring a key under a live intent
  would allow a second overlapping arm and therefore a second order for one
  structure — a P1 violation.
- **F-3 (float asymmetry).** `register` rounds to 6 dp; `seen` compares the
  incoming zone **unrounded**. Re-deriving a key from floats at retire time is
  therefore lossy by construction; retirement must not re-derive geometry.
- **F-4 (keys are TF-blind).** The key has no detection-TF component, and
  `_arm_passed` uses one registry for every detection TF. H4 and H1 zones
  compete for the same key.
- **F-5 (ownership split).** The registry lives on the runtime; the prune runs
  in the adapter/runner. Nothing in the prune chain can reach the registry
  today.
- **F-6 (legacy live path has no dedup at all).** `LiveLoop._detect_and_arm`
  (`live/loop.py:415-441`) calls `engine.arm_at` directly on the degraded
  single-TF path, with no `ZoneDedup` involvement. Out of scope (§5), disclosed
  as a residual.
- **F-7 (in-memory only).** Keys are per process. A restart starts with an
  empty registry; this design neither adds nor removes persistence.

---

## 3. Principles (from the ruling; binding on R1…R7)

- **P1. One live episode → at most one arm.** Never weakened, never traded for
  frequency.
- **P2. Dedup stops re-arming the *same live structure*; it does not sterilize
  a chart region for months.** The measured 29.5 d median blocker age is the
  defect P2 names.
- **P3. Retirement is explicit, deterministic and testable** — one predicate,
  one call site, one counter, no timers, no heuristics.
- **P4. No lookahead; no pillar change.** Retirement reads state reached on or
  before the prune bar (§2.5). Validation is untouched; merged/passed counts may
  not move.
- **P5. Identity/lifecycle coupling, not new thresholds.** Every input to the
  predicate already exists: §5 state, `arm_bar`, `poi_give_up_bars()`, the
  runner's retain sets, `_workflows`, `alive_intents()`. **No new constant, no
  TTL, no age cap, no coverage cutoff.**
- **P6. Edge-touch (inclusive overlap) is a residual, not a scope.** The 11
  zero-area suppressions are documented; the overlap predicate is not rewritten.

---

## 4. Normative rules

### R1 — REGISTER (owner-attributed key)

`register` MUST store the **owner** alongside the geometry:
`(direction, round(top, 6), round(bottom, 6), owner_id)` where `owner_id` is the
`poi.id` of the armed episode. The geometry tuple is unchanged (same rounding,
same direction string). The owner is an **attribute of the key, never part of
the sameness test**. One successful arm stores exactly one key; a failed
`arm_at` stores none (today's behaviour at `multi_tf_runtime.py:487-493`).

`register` MUST remain callable from the arm seam with the same arguments
(plus the owner) so the degraded path and the research captures keep working;
a caller that omits the owner is a programming error and MUST raise
`TypeError` (never an anonymous key).

### R2 — SEEN (unchanged)

`seen(zone)` MUST keep today's semantics exactly: same direction, inclusive
overlap on the stored 6 dp bounds against the queried zone's floats, `True` on
the first match. `owner_id` is ignored by `seen`. A key exists in the registry
**iff** its episode is live (§R3); retired keys are **removed**, not flagged, so
`seen` stays a pure "is a live episode here" test and its code path does not
change. `__len__` becomes "number of live keys".

### R3 — RETIRE (one predicate, one call site, one order)

**R3.1 Death predicate.** An episode's key is retired at the first per-bar prune
step at which **all** of the following hold:

1. **No live obligation:** the `poi.id` is absent from
   `runner.orders.active()`, `runner.positions.open_positions()`,
   `adapter._workflows`, **and** `runner.intents.alive_intents()`
   (the intent's `candidate.poi_id` — findings F-2; the implement leg must add
   alive-intent ids to the retain set); and
2. **The seek book is closed:** either the §5 state is `VIOLATED`, **or**
   `bar_index > episode.arm_bar + poi_give_up_bars()` (the same clock the
   adapter already uses to close the scan at
   `pipeline_adapter.py:150-164`).

No other condition, no additional timer, no state-machine change. Notes that
make it implementable:

- `FRESH` past give-up is dead (its scan closed; it can never route —
  `pipeline_adapter.py:168-172, 459-464`).
- `TESTED` past give-up with no order/position/intent/workflow is dead (the
  first touch happened, the seek span ended, no obligation remains).
- `VIOLATED` is dead immediately (its resting limit was cancelled at
  `pipeline_adapter.py:238-243`; a still-open position keeps it live via 1).
- `TESTED`/`FRESH` **inside** the give-up window stays live even with no
  obligation — the episode may still route (P1 conservatism).
- Any POI in a retain set stays live **regardless** of state or clock: a
  resting order, an open position or an alive intent is an obligation, and P1
  outranks frequency.

**R3.2 Call site.** Retirement happens in exactly one place:
`PipelineAdapter.prune_terminal_pois`, in the same per-bar step that already
runs before the entry scan (`backtest/runner.py:317-319`,
`paper/runner.py:773-780`). It retires:

- every id returned by `engine.prune_terminal(retain)` (the VIOLATED path), and
- every id of a POI still in `engine.tracked_pois()` that satisfies R3.1.

`retire(owner_id)` is idempotent and returns the number of entries removed; the
two sources may overlap without harm. **Micro-ordering inside the step:**
`engine.prune_terminal` runs first and its returned ids are retired immediately
after — *engine first, registry second*, never the reverse — so a key cannot
outlive its episode beyond this one call and no arm can run between the two
(serial by construction; not an atomic transaction across objects). The engine's
own retention behaviour, `_may_route` and `tracked_pois()` are **not** modified
(F-1: over-retention is a pre-existing engine-memory fact, not this leg's
subject; pruning it would change the scan loop and therefore the product).

**R3.3 Ordering.** Retire **before** the bar's scan and **after** the bar's arm
batch (§2.5). Equivalent normative statement: retirement is evaluated at
`bar_index` and may only use state reached on or before `bar_index`; the first
arm it can affect is the next H1 batch. No retirement may occur mid-batch.

**R3.4 Handle identity (F-5).** The object the adapter retires from MUST be the
object `seen()` reads for that session — i.e. the runtime's effective registry
(the `dedup` argument of `run_batch`, else `runtime.dedup`). Recommended wiring:
the runtime binds its effective registry onto the adapter in the arm seam
(idempotent, once). A test asserts handle identity (`adapter.<handle> is
runtime.dedup`), so a future constructor refactor cannot silently split the two.

### R4 — KEY STABILITY (no new sameness metric)

The key's geometry stays `(direction, round(top,6), round(bottom,6))` and the
sameness test stays the inclusive overlap (F-3). Retirement is **by owner id**,
never by re-deriving bounds from floats — a re-derivation would have to guess
the rounding the registration used, and `seen` never rounds its query. No new
tolerance, no epsilon, no coordinate canonicalisation, no `ZONE_REFINEMENT`
change. Refinement (a tighter box inside a parent) is not implemented on the
arm path today; if it is ever added it must retire and register under the same
episode owner (one owner, one key).

### R5 — MULTI-TF KEYS: **shared** (unchanged), disclosed

The key remains direction + span, with **no** detection-TF component, and one
registry per runtime. H4, H1 and any W1/D1 production share it — matching the
product's counting convention and LEG 4's finding that 12 of 30 clusters span
both detection TFs and 2 suppressions are same-batch cross-TF. Retirement
therefore releases a key for *both* TFs at once, which is the intended reading
of "the episode died". Splitting keys per TF is **not** adopted (it would raise
frequency by a second, unruled mechanism). Residual: a live H4 episode still
suppresses an unrelated-enough H1 zone — see §7.

### R6 — FAILURE MODES

- `retire(owner_id)` for an unknown id: **no exception**, no state change,
  increments `retire_misses`, returns 0. Unknown ids are expected (a
  VIOLATED id already retired by the other source) and must never raise into
  the bar loop.
- No handle available (protocol stub / adapter without an engine): retirement is
  a **no-op**, the run continues, and the report carries
  `dedup_retire_available: false`. It must not be silent.
- The arm path is never allowed to raise because of retirement: `register` and
  `retire` are bookkeeping; a failure is logged and counted, and the arm
  proceeds (same fail-safe posture as the `episode_store` hooks).
- **Forbidden:** clearing the whole registry each bar or on any timer
  (`clear-all` would let a live episode arm twice — a P1 violation); TTL/age
  sweeps; retiring on `seen`; retiring inside `run_batch`; retiring a key whose
  episode is only *inside* its window.
- Counters `retired_total`, `retire_misses`, `live_keys` are exposed and
  reported; `retired_total = 0` over a window with ≥ 1 armed episode
  **invalidates** that run's acceptance (§6).

### R7 — NON-GOALS

No change to: P2 / FVG / pillars / validation; the fill model, §23/§24
lifetimes, `ZONE_REFINEMENT`, re-anchor; triggers, posture, seek/scan rules;
Mode T; the `episode_store`; the engine's retention, `_may_route`,
`tracked_pois()`; the dedup predicate, its 6 dp rounding or its TF-blindness;
any `locked_constants` value. No max-armed cap, no score-based arming, no
"arm everything that passes", no per-TF key split, no persistence across
restarts, no change to the legacy degraded live path (F-6). **No expectancy,
win-rate or profit claim may be attached to this change** — it is a lifecycle
fix, and a higher arm count is a consequence to be reported, not a target.

### R8 — EDGE TOUCH: **residual only** (default carried)

The 11 zero-area suppressions come from the inclusive predicate
(`known_top >= bottom and top >= known_bottom`). This leg does **not** adopt an
exclusive-edge clause: it is a separate sameness change, it would move the
identity rule the episode store already cites, and it is unnecessary for the
lifetime defect. Recorded in §7 as a residual for a future, separately ruled
amendment.

---

## 5. Non-goals restated as a gate on the implement leg

The implement leg may touch exactly: `ZoneDedup` (add owner + `retire` +
counters), the two `register` call sites, the adapter's prune step (retire
calls + alive-intent retain), and one bind at the arm seam. Anything else — a
threshold, a lifetime, a state, a trigger, a pillar, a constant, the engine's
retention — is out of scope and must come back as its own ruling. In
particular the implement leg **may not** "fix" F-1 by pruning TESTED episodes;
that is a different behaviour change behind a different label.

---

## 6. Acceptance metrics — pre-registered for the implement leg

The frozen 6m window is the basis (35,725 M5 bars, 2,979 batches). Windows are
not pooled; the 18m secondary is not re-captured (4.25 h measured in LEG 3).

**Gate A — integrity (must be exact).** `htf_batches = 2,979`,
`merged = 43,004`, `passed_validation = 2,021`, `bucket_sum = 2,021`, one
bucket per PASS, `batch_errors = 0`. Retirement is downstream of validation; a
moved merged/passed count means the change leaked into the decision path — stop
and investigate.

**Gate B — the mechanism actually engaged.** `retired_total ≥ 1`; the number of
retirements and the split by trigger (VIOLATED vs give-up-closed) are reported.
A run with zero retirements is **invalid**, not a null result.

**Gate C — the disposition moves in the designed direction.** `SKIP_DEDUP_EPISODE`
falls and `ARMED` rises above the **30** baseline, with the **PASS → arm rate**
(`armed / 2,021`, baseline **1.48%**) reported beside it; all three are
**deltas, never as targets**. Also required:

- **no arm at all** from a PASS whose blocker was live at that bar (P1 check
  against the LEG 4 capture: a `SKIP_DEDUP_EPISODE` event whose blocker had no
  obligation and a closed seek book must now arm **if it is the first event of
  its cluster after the key died** — later events in the same cluster are
  suppressed by the *new* live key, exactly as P1 requires);
- **≤ 1 concurrent arm per live key** — an invariant test (arm → kill → re-arm;
  a second overlapping PASS must be suppressed while the first is live and must
  arm after the key retires);
- median blocker age at suppression collapses from **29.5 d** toward the
  give-up window for untraded episodes and the trade lifetime for traded ones;
  both are reported;
- `SKIP_TRACKED` stays **0** (retirement must not create registry churn that
  surfaces as tracked skips).

**Gate D — determinism.** Two full captures produce byte-identical
`trades.csv` and `report.json`, and a `--analyze-only` rerun reproduces the
summary byte-identically. The retirement decisions are part of the capture
(`retired` events with owner, bar, trigger), so the count is auditable.

**Gate E — safety rails.** Suite green (no skips, no weakened assertions);
`locked_constants.py` diff **empty**; `LOGIC_CHANGED: **YES**` declared (unlike
LEG 1/3/4, this leg *does* change decisions and must say so); routes / placed /
fills reported as deltas with the `DIAGNOSTIC — NOT EDGE` banner and no
expectancy language.

**Gate F — regression of intent.** A control run with retirement present but not
called (or behind a flag-off) must reproduce LEG 4's frozen counters and id
sets **exactly** (2,979 / 43,004 / 2,021 / 30 / 1,991 / 0), i.e. the *only*
behavioural difference is the lifetime. LEG 1's `HOLD_P2_FVG` and LEG 3's
`FILL_PATH_HEALTHY` are untouched by construction — no pillar, fill-model,
expiry or lifetime rule is in this leg's edit surface — and their reports are
not re-run.

---

## 7. Risks and residuals

| # | Residual | Why it is not fixed here | What to do |
|---|---|---|---|
| 1 | **Edge-touch suppressions (11)** — zero-area overlap still counts as the same episode | separate sameness change (R8) | documented; optional future amendment |
| 2 | **TF-blind keys (R5)** — a live H4 episode suppresses an H1 zone of the same direction/span | changing it raises frequency by a second mechanism | disclosed; no per-TF split |
| 3 | **Float identity (F-3)** — `seen` does not round its query; 11.5% identical-bound matches are exact, the rest are overlaps | changing `seen` is a sameness change | retirement is owner-id only, so this cannot leak into retirement |
| 4 | **TESTED episodes stay in the engine forever (F-1)** | engine retention is not this leg's subject; pruning it changes the scan loop | disclosed; dedup lifetime is fixed independently of engine memory |
| 5 | **In-memory keys (F-7)** — a live restart begins with an empty registry and can re-arm an episode that was live before the restart | persistence is a separate design (episode store phase 2) | disclosed; the restart can produce one extra arm per open structure |
| 6 | **Legacy degraded live path (F-6)** arms with no dedup at all | tests-only path, not product mode | disclosed |
| 7 | **Frequency rises** — the 30-arm baseline may move substantially (up to the number of distinct structures that re-present after each death) | this is the intended effect of R3, not an optimisation | report the delta; the Architect decides whether the new frequency is acceptable, with no expectancy claim attached |
| 8 | **Give-up is a 20 M5-bar bound for HTF-detected episodes** — retirement makes a 100-minute clock decide how long a 6m-scale structure stays "the same episode" | the clock already exists and already closes the scan | if the Architect wants a longer identity memory, that is a *new* rule (P5 forbids inventing one here) |
| 9 | **Same-bar ordering** — retirement at bar `b` cannot affect the batch that already ran at `b` (§2.5) | inherent to the composition, and the safe direction | documented; the first affected batch is the next H1 close |

---

## 8. Self-check

| Check | Result |
|---|---|
| Mandatory read 1 — full `ZoneDedup` surface cited | ✔ §2.1 (`:135-169`) |
| Mandatory read 2 — `register` / `seen` call sites | ✔ §2.2 (`:464`, `:493`, `:569`, `:585`) |
| Mandatory read 3 — `prune_terminal` / `prune_terminal_pois`, when and what | ✔ §2.4, §1.1 (incl. the read-only probe) |
| Mandatory read 4 — `arm_at` / episode identity | ✔ §2.3 |
| Mandatory read 5 — LEG 4 §mechanism, dedup vs tracked | ✔ §1 (facts quoted with values) |
| Mandatory read 6 — owner plan status | ✔ `00_LOCKED/TECHNICAL_OWNER_PLAN_POST_PROBE.md` — LEG 4 DONE (`ARM_FILTER_IS_BOTTLENECK`), LEG 5 opened by R-ARM |
| Problem restated with measured facts | ✔ §1 (2,021 / 30 / 1,991 / 0; 29.5 d; 140.3 d; 11 edge) |
| R1…R7 written as implementable rules | ✔ §4 |
| Retirement predicate uses no new threshold | ✔ R3.1 (only existing state, clock and retain sets) |
| R8 edge-touch kept as residual | ✔ R8 + §7 row 1 |
| Acceptance metrics defined before any implementation | ✔ §6 (Gates A–F) |
| Non-goals explicit, incl. "no arm everything" | ✔ R7, §5 |
| Code changed in this leg | **none** — `04_SRC` untouched, no tests added or edited |
| `locked_constants.py` | **diff empty** (untouched) |
| `LOGIC_CHANGED` | **NO** (design only) |

**DESIGN_LOCK_STATUS: PASS** — the rules are complete, implementable from the
cited line-level behaviour, and gated by pre-registered acceptance metrics. The
next step is Architect acceptance of this note, then a separate implement prompt.

---

## Return block

```
DESIGN_LOCK_STATUS: PASS
DEDUP_API_SURFACE: [__init__, seen, register, __len__]
REGISTER_ON: engine.arm_at success in MultiTFProductRuntime._arm_passed (product path :493; degraded test path :585), one key per armed POI, geometry = (direction, round(top,6), round(bottom,6)) + owner poi.id (new, required)
RETIRE_ON: first per-bar prune step (PipelineAdapter.prune_terminal_pois) at which the owning episode has NO live obligation (no resting order, no open position, no alive R9 intent, no in-flight workflow) AND (state VIOLATED OR bar_index > arm_bar + poi_give_up_bars()); id-based retire(owner_id), idempotent, never re-derived from floats
KEY_DEFINITION: direction + inclusive overlapping span on 6dp bounds (unchanged sameness); owner poi id stored as an attribute only, ignored by seen()
MULTI_TF_KEYS: shared (one direction+span registry for every detection TF; no per-TF split)
EDGE_TOUCH: residual
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
NOTE_PATH: 06_RESEARCH/ZONE_DEDUP_LIFECYCLE_DESIGN.md
NEXT_READY: Architect accept design → implement prompt
```
