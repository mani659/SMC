# ENTRY PATH ON CONFIRMED SWEPT POIs — FLOWCHART STEP 4 (READ-ONLY NOTE)

> **DIAGNOSTIC — NOT EDGE.**
> Of 490 confirmed episodes, 16 route post-sweep, 4 place, 3 fill —
> measured through the product's own code path with an instrumented
> replay proven byte-identical to the frozen run. No threshold was
> changed, no gate follows, no production code was touched. No table
> supports or refutes edge or licenses any filter.

**Date:** 2026-10-11 · **Authority:** Lead Architect Step-4 directive (after POI_SWEPT_LTF_CONFIRM_NOTE.md).
**ENTRY_PATH_STATUS: PASS** (fidelity gate green; gap tables published; 4 new tests green).
**LOGIC_CHANGED: NO** (call-through recording wrappers, restored after; research script + tests only).

---

## 1. Method (one line)

The frozen `phase3_structure_funnel.run` driven verbatim (same window,
same config incl. explicit costs) with record-only wrappers on
scan/route/place/close plus a runner-instance stash for the blocked
log (FR-4 pattern; true originals restored in `finally`), then
confirmed episodes joined to engine POIs by episode key (exact),
same-direction containment (smallest container), or none — with
sweep-anchored time qualification (route/place/fill at/after
first_sweep_ts; pre-sweep routes tracked as one-shot consumed).

## 2. Fidelity gate (why the numbers below are product facts)

Replay vs the 6m refresh run1: `trades.csv` **byte-identical**,
`report.json` **byte-identical**, funnel identical on every count
(30 armed / 10 routes F9+C1 / 4 placed / 3 fills / intents 7-3-0).
The gate caught one real defect mid-build (replay initially ran
zero-cost — same gross economics, different cost columns — fixed by
importing the single-source `PILOT_COSTS`; funnel counts alone would
have missed it). M5 bar-index mapping proven against the replay's own
window (35,725 bars, 2025-06-01T22:00 → 2025-11-30T23:55 — Sunday-open
start, not midnight). Script:
`06_RESEARCH/scripts/poi_confirm_entry_path.py`.

## 3. Lifecycle: where the 490 → 3 collapse happens

Of 490 confirmed episodes: **340 (69%) never had a product POI
covering their geometry at all** (never validated/armed — pillars +
dedup happened upstream); of the 150 joined (7 exact + 143
containment), **32 were already routed before the sweep**
(one-shot consumed — the confirmation arrived too late for a decided
POI) and **102 were scanned but never routed post-sweep** (the scan
finds nothing silently — no per-scan reason exists; every joined POI
was scanned, so "never scanned" contributes 0); **16 routed
post-sweep (3.3%, all F)** → **4 placed (25%)** → **3 filled (75%)**.
Blocked reasons attached post-sweep (per-event): session 7, R7
far-from-zone 9. In one paragraph: confirmation is plentiful and the
scan always runs, but seven in ten confirmations belong to geometries
the product never arms, most of the remainder were decided before the
sweep or find no route, and placement gates admit a quarter of what
routes — the book starves at validation, chronology, and placement,
in that order.

@20 secondary (282 confirmed): none 195 / containment 83 / exact 4;
routed 12 (4.3%, all F); placed 3; filled 2; gaps no-POI 195 /
pre-sweep 16 / scanned-no-route 59; blocked session 5 / R7 7 — same
shape, slightly richer routing inside the give-up scale.

## 4. Gap table: confirmed but never routed post-sweep (474 rows)

| Reason (frozen taxonomy) | n | Reading |
|---|---|---|
| no-product-POI | 340 | geometry never validated/armed (pillars + dedup upstream) |
| routed-before-sweep | 32 | one-shot consumed pre-sweep; post-sweep confirmation moot |
| scanned-no-route | 102 | scan ran, chronology/windows admitted nothing (silent by construction) |
| never-scanned | 0 | scans run unconditionally once armed — no gap here |

Routed-never-placed (12 episodes): placement gates (session blocks, R7
far-from-zone defers-to-intent, risk sizing) — 16 blocked events
attached post-sweep. Placed-never-filled (1 episode order): §24
expiry / cancel (intent lifecycle in the funnel: 0 expired this run —
the order simply never touched).

## 5. The C trade (answered pre-emptively — DIAGNOSTIC)

The C fill (SHORT entry 2025-09-02 13:45, TP exit) joins NO confirmed
episode — correctly, not defectively: its structure (SHORT, swept
2025-09-02 04:00) shows zero Stage-3 completions inside the frozen
+48 M5 bars post-sweep, while the product (arm-anchored seek, merged
multi-tag POI) routed its C trigger roughly 100+ M5 bars after the
sweep. Step-3's sweep-anchored window and the product's arm-anchored
seek overlap without containing each other — this bounds what the
frozen +48 horizon can see and is itself a product-vs-idea geometry
finding, not a contradiction. The two F fills join cleanly
(post-sweep routes, SL exits).

## 6. Limitations (binding on synthesis — DIAGNOSTIC)

- Containment joins (143/150) match census geometry inside wider
  engine zones — direction-only, no tolerance invented; Tier counts
  published so the join can be re-cut without re-running.
- Blocked reasons come from the placement-time log; scan-quiet has no
  reason by construction; intent lifecycle contributes funnel counts.
- One replay, one window; the fidelity proof covers exactly this
  composition/config/data slice.
- No gate, no threshold, no live rule follows.

## 7. Pointer: NEXT = Architect flowchart synthesis

`lifecycle_per_episode.csv` (490 rows: join tier, scan/route/place/fill
flags + timestamps, blocked reasons, gap reason) joined to Steps 1–3
artifacts completes the measured chain POI → sweep → confirm →
admit: 1,093 → 946 → 490 → 16 → 4 → 3.

---

**Artifacts:** `06_RESEARCH/scripts/poi_confirm_entry_path.py` (new;
+ `replay_run1/` frozen-run artifacts for the fidelity check) ·
`06_RESEARCH/results/poi_confirm_entry_path/` (`lifecycle_per_episode.csv`
490 rows, `summary.json` with frozen rules + tables) · tests
`04_SRC/tests/test_poi_confirm_entry_path.py` (4).
