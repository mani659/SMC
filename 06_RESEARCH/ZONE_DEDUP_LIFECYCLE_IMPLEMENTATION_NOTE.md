# ZONE DEDUP ↔ EPISODE LIFECYCLE — IMPLEMENTATION NOTE (LEG 5b)

> **DIAGNOSTIC — NOT EDGE.**
> The arm filter's identity rule was not touched; its **lifetime** was. Higher
> armed / placed / filled counts are the designed consequence of releasing the
> keys of dead episodes — not an expectancy, win-rate, or profit claim, and not
> an authorization to change any admission gate. Validation moved nothing:
> merged / passed / batches are **exact** against the frozen baseline.

**Date:** 2026-10-20 · **Authority:** Architect **ACCEPT** 2026-10-20 of
`06_RESEARCH/ZONE_DEDUP_LIFECYCLE_DESIGN.md` (R1–R8) — implement authorized.
**IMPL_STATUS: PASS** · **LOGIC_CHANGED: YES (dedup lifecycle only)** ·
`locked_constants.py` diff **EMPTY** · suite **1,236 passed (EXIT=0)**.

---

## 1. What changed (line-level)

| File | Change |
|---|---|
| [multi_tf_runtime.py](04_SRC/smc/orchestration/multi_tf_runtime.py) | `ZoneDedup`: keys become `(direction, round(top,6), round(bottom,6), owner_id)`; `register(zone, *, owner_id)` — owner **required** (`TypeError` otherwise, design R1); **new `retire(owner_id)`** — idempotent, removes by stored owner string (never float re-derived, design R4), returns removals, increments `retire_misses` for unknown ids (R6); counters `retired_total` / `retire_misses` / `live_keys`; `seen` **unchanged** semantics (owner-blind 4th tuple element ignored; inclusive overlap, first match, design R2); `run_batch` binds the effective registry onto the adapter **before** any policy decision (R3.4 — idempotent for the same handle, in `_arm_passed` both `register` call sites pass `owner_id=poi.id`, product `:565` + degraded `:658`) |
| [pipeline_adapter.py](04_SRC/smc/backtest/pipeline_adapter.py) | `prune_terminal_pois`: after `engine.prune_terminal` and its bookkeeping drops, **one new call** `self._retire_dead_keys(pruned, set(retain_ids or ()), bar_index)` — engine first, registry second; **new `bind_dedup_registry`** (handle identity; a *different* handle is refused loudly — R3.4); **new `_retire_dead_keys`** implementing R3.1 exactly: death = POI absent from the runner-supplied obligation set AND absent from `_workflows` AND (state `VIOLATED` OR `bar_index > arm_bar + poi_give_up_bars()`) — the SAME give-up clock the scan closure already uses; wrapped in one fail-safe `try/except` so retirement can never break the bar (R6); adapter bookkeeping fields `_dedup_registry` / `_retire_sent` (prevents re-send miss spam across the two retirement sources) |
| [runner.py](04_SRC/smc/backtest/runner.py) | `_prune_engine_state`: the runner's obligation set now also carries **alive R9 intent** POI ids (`self.intents.alive_intents()`, design F-2) — an intent may still place, so its POI's key must not retire under it |
| [paper/runner.py](04_SRC/smc/paper/runner.py) | same alive-intent clause in `_prune_engine_state` (the live product session arms through `PaperRunner`, which prunes per bar) |
| [episode_store.py](04_SRC/smc/orchestration/episode_store.py) | **signature-compatibility only** (observers): its two throwaway `ZoneDedup.register(...)` identity probes now pass `owner_id=<episode_id>`; `seen` is owner-blind, so resolution behaviour is bit-identical (suite `test_episode_store_v1` unchanged expectations) |
| [test_zone_dedup_lifecycle.py](04_SRC/tests/test_zone_dedup_lifecycle.py) | **16 new tests** (R1 owner required/stored; R2 owner-blind + freed-after-retire; R6 idempotent/misses/unbound no-op; R3.1 each branch: VIOLATED releases, obligation holds, inside-window live, FRESH-past-give-up releases with engine retention untouched; workflow-live holds; R3.4 bind identity + loud re-bind refusal; Gate C arm → kill → re-arm invariant; deterministic remaining-order) |
| [test_multi_tf_product_path.py](04_SRC/tests/test_multi_tf_product_path.py) / [test_passed_to_armed_attribution.py](04_SRC/tests/test_passed_to_armed_attribution.py) | pre-existing `register(zone)` unit calls updated to supply an owner (behaviour assertions unchanged) |

Not changed: the engine's retention (`prune_terminal`, `_may_route`,
`tracked_pois()` — design §5 explicitly leaves the F-1 engine-memory fact
alone), validation pillars, triggers, fill model, §23/§24 lifetimes,
`ZONE_REFINEMENT`, Mode T, the dedup overlap rule, any threshold or constant.
The legacy degraded live path (`LiveLoop._detect_and_arm`) has no dedup and was
deliberately not touched (design F-6 residual).

## 2. Measurement — frozen 6m dual run (import composition, not fork)

Window identical to LEG 4: M1 load from **2025-05-01**, exec **2025-06-01 →
2025-11-30** M5 (**35,725** bars), zero-cost machine-completeness config.
Script: [zone_dedup_lifecycle_measure.py](06_RESEARCH/scripts/zone_dedup_lifecycle_measure.py)
(logging-only seams, restored in `finally`); results
(gitignored): `06_RESEARCH/results/zone_dedup_lifecycle/{run1,run2}/{summary.json,retire_sweeps.jsonl.gz,_funnel_capture/*}`.

### Gate A — integrity (must be exact)

| Stage | LEG 4 baseline | run1 | run2 | Match |
|---|---|---|---|---|
| HTF batches | 2,979 | **2,979** | **2,979** | ✔ |
| merged POIs | 43,004 | **43,004** | **43,004** | ✔ |
| passed validation | 2,021 | **2,021** | **2,021** | ✔ |
| SKIP_TRACKED | 0 | **0** | **0** | ✔ |

### Gate B — the mechanism engaged

`retired_total = 606` (run1), **606** (run2) — read from the per-bar sweep
audit (`retire_sweeps.jsonl.gz`; **448 sweeps** carried retirement in each
run, monotone, max step +5). Of those, **11** retirements arrived through the
engine-prune path (VIOLATED release) and the rest through the
give-up-closed sweep of still-tracked episodes — the design's two sources
both live. `retire_misses = 0`; max concurrent `live_keys = 5`; registry ends
at **0** live keys (episode → key → retirement, round trip complete).

### Gate C — disposition deltas (deltas, never targets)

| Disposition | Baseline (LEG 4) | After | Delta |
|---|---|---|---|
| ARMED | **30** | **606** | **+576** |
| PASS → arm rate | 1.48% | **29.99%** | +28.5 pp |
| `SKIP_DEDUP_EPISODE` | **1,991 (98.52%)** | **1,415 (70.0%)** | **−576** (exact bucket conservation: 606 + 1,415 = 2,021) |
| routes | 10 | **219** (F 197 / A 9 / B 8 / E 3 / C 2) | +209 |
| placed | 4 | **65** (65 with TP) | +61 |
| fills / trades | 3 | **58** | +55 |
| R9 intents armed / placed / expired | 7 / 3 / 0 | **152 / 26 / 0** | +145 / +23 / 0 |
| armed by zone TF | H4 19 / H1 6 / D1 5 | **H4 185 / H1 322 / D1 99** | every stratum grew |
| armed M8 | 28 | **439** | +411 |

Guard confirmed: **no double-arm of a live episode** — ≤ 1 concurrent arm per
live key holds structurally (`seen` suppresses overlapping PASS events while
the key is live) and is test-pinned (arm → kill → re-arm); the count identity
`armed = retired = 606` is the round trip, not evidence of re-arming.

### Gate D — determinism

Two independent full captures: `trades.csv` SHA-256 **`8eecd3b9…`** and
`report.json` SHA-256 **`5145d54e…`** — **byte-identical** across run1/run2.
Runtime: 963.7 s (run1) / 933.3 s (run2) vs the LEG 4 capture's 883.8 s — the
sweeps cost ≈ **+6–9%** per run (O(tracked) walk per bar; `tracked_pois` is
unchanged, so no additional growth).

### Gates E / F — rails

Suite **1,236 passed (EXIT=0)** (1,220 prior + **16 new**);
`locked_constants.py` diff **empty**; `LOGIC_CHANGED: YES` declared, limited
to the files in §1. Gate F structural note: retirement only *removes* keys —
with no bound handle the run reduces to the pre-LEG-5 registry (same
`seen` / `register` / arm semantics), and the LEG 4 publication remains the
retirement-off baseline; the pre-change capture on disk reproduces its
counters exactly (verified in LEG 4).

## 3. Residuals and disclosures

1. **Measurement-seam caveat:** `runtime.dedup` counters are `null` inside the
   dumped `summary.json` (the composition imported the runtime class before
   the seam wrapped it); the authoritative counters come from the sweep
   audit, whose final record IS the registry state — `retired_total: 606`,
   `live_keys: 0`. No re-run needed; disclosed, not hidden.
2. **Research scripts** `06_RESEARCH/scripts/{d1_f1f2_resample,h4_poi_confirmation}.py`
   still call the old `register(zone)` signature; they are not product code
   and were not run here — their next use needs the one-line owner argument
   (out of the authorized edit surface this leg).
3. **F-1 untouched by design:** TESTED episodes still sit in the engine's
   arm list forever; their **keys** now retire at the give-up clock, so the
   suppression behaviour is fixed independently of engine memory.
4. **Live restarts** begin with an empty registry (in-memory, design F-7) —
   a restarted session may re-arm a structure that was live before the
   restart (disclosed residual, unchanged from the design).
5. **Edge-touch and TF-blind keys remain** as designed residuals (R5/R8).
6. The optional offline smoke (R3 predicate on the LEG 4 capture) was **not**
   performed — the LEG 4 capture does not record blocker obligations/order
   state per bar, so it cannot answer faithfully; the dual run supersedes it.

## 4. Self-check

| Design rule | Where | Verified by |
|---|---|---|
| R1 owner required, geometry unchanged | runtime `register` | tests + twin register sites |
| R2 `seen` unchanged, keys removed not flagged | runtime `seen`/`retire` | overlap-rule tests unchanged + retire tests |
| R3.1 death predicate | adapter `_retire_dead_keys` | per-branch tests |
| R3.2 call site + engine-first ordering | `prune_terminal_pois` | sweep audit (11 engine-pruned retires in-window) |
| R3.4 handle identity | `bind_dedup_registry` | bind tests |
| R5 shared TF-blind keys | unchanged key tuple | unchanged rule test |
| R6 idempotent / misses / never crashes | `retire` + try/except | tests; 448 clean sweeps in-run |
| R7 non-goals | — | diff scope §1; no threshold/constant touched |
| Gate A–D | measurement §2 | exact / 606 / −576 / byte-identical |

**IMPL ready for Architect review of the post-implement funnel** — the armed
delta (+576) and the remaining 1,415 dedup suppressions are the owner's
readings to make; nothing here authorizes further gate changes.
