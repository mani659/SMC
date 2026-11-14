# OPEN DECISION O3 — MULTI-ZONE PRIORITY (MEASUREMENT)

**Date:** 2026-11-14 · **Status:** MEASURED · **INTERPRETATION: KEEP_FIRST_ARMED_STATUS_QUO**
**`LOGIC_CHANGED: NO`** · **`PRODUCT_CODE_CHANGED: NO`**
**Authority:** `OPEN_DECISIONS_RESEARCH_AGENDA.md` §O3; Architect locks
O1 `KEEP_STATUS_QUO` (C3) and O2 `KEEP_UPSTREAM_ONLY` (sweep).
**Script:** `06_RESEARCH/scripts/o3_multi_zone_priority.py`
**Artifacts:** `06_RESEARCH/results/open_decisions/o3_multi_zone_priority/`
(`arms.csv`, `clusters.csv`, `summary.json`; results tree gitignored).

---

## 1. Question (from the agenda)

When D1 / H4 / H1 / M15 armed zones overlap or conflict, what should win —
first-armed, highest TF, tightest zone, or all-as-equal-tags?

---

## 2. Method (offline, no re-run)

- **Source:** the O2 armed table (441 arms, frozen composition, October window,
  full D1/H4/H1/M15 set). Its SHA-256 (`b7dee5ef…`) is verified against the O2
  `summary.json` before use, so the reuse is provable. No broker path is
  re-simulated; fills are outcome identities only, never PnL.
- **Pre-registered overlap** (fixed before any cluster was inspected):
  opposite direction + ranges intersect **OR** same direction + intersection /
  min(height) ≥ **0.50**.
- **Pre-registered TF order:** D1 > H4 > H1 > M15.
- **Counterfactuals** (singletons always survive): CF1 highest TF, CF2 smallest
  zone height, CF3 earliest arm (sanity). Fill/rout/C3 identity is carried per
  `poi_id`.
- **Current product behaviour:** `multi_tf_runtime.ZoneDedup` makes
  same-direction overlapping spans ONE episode owned by the first registration
  (`register` runs only after an arm wins; keys retire with the owner). No TF
  rank exists anywhere in the runtime — first-armed is the de facto rule.

---

## 3. Results

### View A — pre-registered relation, all arms (PRIMARY)

| Metric | Value |
|---|---|
| Armed | 441 |
| Overlap clusters | 5 |
| Arms inside clusters | **441 (100%)** |
| Largest cluster | **271 arms** |
| Multi-TF clusters | 3 |
| Same-direction overlapping pairs | 9,827 |
| Direction-conflict pairs (long×short) | 3,212 |
| Clusters with a direction conflict | 2 |

| Counterfactual | arms kept | routed kept / dropped | C3 passes kept / dropped | **fills kept / dropped** |
|---|---|---|---|---|
| CF1 highest TF | 5 | 1 / 130 | 0 / 12 | **0 / 11** |
| CF2 tightest | 5 | 0 / 131 | 0 / 12 | **0 / 11** |
| CF3 first-armed | 5 | 2 / 129 | 0 / 12 | **0 / 11** |

### View B — same detection batch only (SECONDARY, exploratory)

| Metric | Value |
|---|---|
| Overlap clusters | 3 |
| Arms inside clusters | 6 (1.4%) |
| Multi-TF clusters | 0 |
| Same-direction overlapping pairs | **0** (already removed by `ZoneDedup`) |
| Direction-conflict pairs (M15×M15) | 3 |

| Counterfactual | arms kept | routed kept / dropped | C3 passes kept / dropped | **fills kept / dropped** |
|---|---|---|---|---|
| CF1 / CF2 / CF3 | 438 | **131 / 0** | **12 / 0** | **11 / 0** |

TF-pair matrix (View A, pairs): D1∩D1 4,635 · D1∩H4 2,528 · D1∩M15 1,332 ·
H4∩M15 1,001 · M15∩M15 922 · H1∩H1 721 · H1∩M15 659 · D1∩H1 506 · H4∩H1 370 ·
H4∩H4 365. View B: M15∩M15 3 only.

---

## 4. Reading

1. **Price-space overlap is universal, not selective.** Every one of the 441
   arms sits inside an overlap cluster and the largest holds 271 arms: D1 bodies
   span hundreds of pips, so the pre-registered relation transitively chains
   almost the whole book into single clusters. Any global "one survivor per
   cluster" rule therefore *deletes the product*, not duplicates: CF1/CF2/CF3
   each retain **0 of 11** realised fills and 0 of 12 C3 passes. That is
   disqualifying on its own — a rule that removes every traded identity cannot
   be described as "removing dead arms".
2. **The decision surface a priority rule could act on is tiny.** At the only
   moment a rule can arbitrate — arms landing in the same detection batch —
   there are **6 arms in 3 clusters**, and all three are opposite-direction M15
   pairs. Same-direction simultaneous overlaps are already gone (0 pairs), which
   is exactly `ZoneDedup` doing its job.
3. **Removing the residual conflicts changes nothing measurable.** Dropping the
   three simultaneous conflict pairs retains 131/131 routed, 12/12 C3 passes and
   11/11 fills. There is no measured benefit to buy with new priority semantics.
4. **Direction conflicts exist but are not simultaneous in the main.** 3,212
   long×short overlapping pairs across the window are zones of opposite bias
   intended at different times — a structural feature of accumulating a POI
   book, not a merge error. Nothing in the product needs them resolved to one
   winner; both sides simply arm when their own trigger completes.
5. **Consistent with code and locked decisions:** first-armed ownership is what
   `ZoneDedup` implements, and the measurement gives no reason to add a TF rank
   on top of it.

---

## 5. Lock interpretation (words only)

Agenda O3: `KEEP_FIRST_ARMED_STATUS_QUO` if multi-TF conflict is rare **or**
CF1/CF2 drop almost no actual fills / do not clearly improve outcomes;
`PRIORITY_RULE_WARRANTED` if direction conflicts are material **and** the rules
systematically drop only dead arms while retaining fills.

- Multi-TF *simultaneous* conflict is rare (3 M15 pairs; 0 cross-TF).
- The counterfactuals do not "drop only dead arms" — under the primary relation
  they drop **every** fill; under the simultaneous relation they drop **none**,
  but retain everything, so nothing improves.
- Neither branch of the warrant condition is met → **KEEP_FIRST_ARMED_STATUS_QUO**.
  No TF priority rule is proposed; if the Architect ever wants one, it would
  have to come from a dated design aimed at *simultaneous opposite-direction*
  conflicts, which this window shows to be 3 cases.

---

## 6. Caveats and DATA_GAP

- The exported armed table has **no episode death time**, so View A cannot
  distinguish "coexists in price" from "coexists in time". This is stated, not
  patched: adding lifetime data would be a separate, larger pack (episode store
  join), and View B sidesteps the issue by using the batch timestamp the table
  already carries.
- One window; fills n = 11. Counts are descriptive; no significance claims and
  no PnL input.
- View B was added after View A showed transitive chaining. It is labelled
  exploratory and is not the basis for the lock reading — the lock follows the
  pre-registered relation, which points the same way (status quo) for the
  opposite reason.
- Reconciliation: `arms.csv` 441 rows, `clusters.csv` 5 rows (View A clusters),
  arms-in-clusters 441 = singletons 0 + members 441.

---

## 7. Return block

```text
O3_STATUS: PASS
WINDOW: exec 2025-10-01 → 2025-10-31 UTC (load from 2025-05-01; O2 armed table reused, SHA verified)
N_ARMED: 441
N_OVERLAP_CLUSTERS: 5 (pre-registered price overlap) / 3 (same-batch view)
SHARE_ARMS_IN_CLUSTERS: 100.0% (price overlap) / 1.4% (same-batch)
DIRECTION_CONFLICTS: 3212 pairs / 2 clusters (price overlap); 3 pairs / 3 clusters (same-batch)
CF1_FILLS_RETAINED: 0/11 (price overlap) · 11/11 (same-batch)
CF2_FILLS_RETAINED: 0/11 (price overlap) · 11/11 (same-batch)
INTERPRETATION: KEEP_FIRST_ARMED_STATUS_QUO
PRODUCT_CODE_CHANGED: NO
NOTE_PATH: 06_RESEARCH/OPEN_DECISION_O3_MULTI_ZONE_PRIORITY.md
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
HANDOFF_UPDATED: YES
NEXT_READY: Architect O3 reading | O4 SL MAE pack
```
