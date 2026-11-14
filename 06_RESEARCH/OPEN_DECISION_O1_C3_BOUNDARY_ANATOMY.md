# OPEN DECISION O1 — C3 REJECT / BOUNDARY ANATOMY (MEASUREMENT)

**Date:** 2026-11-14 · **Status:** MEASURED · **INTERPRETATION: KEEP_STATUS_QUO**
**`LOGIC_CHANGED: NO`** · **`PRODUCT_CODE_CHANGED: NO`**
**Authority:** `OPEN_DECISIONS_RESEARCH_AGENDA.md` §O1 (lock criteria binding),
`LOCKED_DECISIONS.md` §25 (in-between REQUIRED, completion **close**),
`C3_IN_BETWEEN_GATE_NOTE.md`, `POST_C2_DIAGNOSTIC_REPORT.md`.
**Script:** `06_RESEARCH/scripts/o1_c3_boundary_anatomy.py`
**Artifacts:** `06_RESEARCH/results/open_decisions/o1_c3_boundary/rejects.csv`,
`summary.json` (results tree is gitignored).

---

## 1. Question (from the agenda)

Are C3 `not_in_between` rejects mostly far-from-zone noise, or edge/boundary
interactions that a *separate* boundary-sweep path might legitimately catch?

---

## 2. Window and composition (frozen before any result was inspected)

| Item | Value |
|---|---|
| Load prefix | 2025-05-01 UTC |
| Execution | 2025-10-01 00:00 → 2025-10-31 20:55 UTC |
| Exec TF | M5 (6,324 bars) |
| Composition | Phase 3 product composition (same code path as `post_c2_diagnostic`) |
| Detection set | **D1 / H4 / H1 / M15** via `lib/product_htf_series.ensure_product_detection_frames` |
| Derived HTF sizes | H1 3,024 · H4 817 · D1 158 · **M15 2,108** |
| HTF batches | 526 (1 cold-start error, pre-existing) |

**Pre-registered bucket edges** (declared in the script before the run, not
edited afterwards): `EDGE_NEAR_ATR = 0.25`, `EDGE_WIDE_ATR = 1.0`, with the
same ratios applied to zone height only when ATR is unavailable (labeled
DATA_GAP — it was 0% here).

**Gate measured:** the single function that applies C3 for both call sites
(`candidate_from_route` in `smc/backtest/pipeline_bridge.py`), wrapped
read-only. All 149 evaluations came through the adapter-scan call site.

---

## 3. Determinism and reconciliation

- Single run (the composition is deterministic and export-independent); the
  reject table checksum is recorded in `summary.json`
  (`447754677411f6a0…` over the sorted CSV).
- **Cross-run reproduction:** this run reproduced the post-C2 diagnostic counts
  exactly — armed **441**, routes **149** (F 122 / A 15 / B 11 / C 1),
  candidates 12, placed/filled 11, duplicates suppressed 586. Two independent
  runs of the composition agreeing to the unit is the determinism evidence.
- `summary.json` reconciles to the CSV: 149 gate rows = 137 rejects + 12 passes;
  0 rows lacking a completion price; 0 probe errors.
- Sanity: **0** rejects with `close_inside`; **0** passes with `close_outside`.
  The gate's predicate and the recorded geometry agree.

---

## 4. Results

| Metric | Value |
|---|---|
| N C3 evaluations | 149 |
| N `not_in_between` | **137** (91.9%) |
| N passed C3 | 12 |
| B1 EDGE_NEAR (≤0.25 ATR) | **2** (1.5%) |
| B2 EDGE_WIDE (0.25–1.0 ATR) | **2** (1.5%) |
| B3 FAR (>1.0 ATR) | **133** (97.1%) |
| B4 touch-but-close-out (cross flag) | **1** (0.7% of rejects; 1 of 1 touching rejects) |
| B0 close inside (should be 0) | 0 |
| B_UNLOCATABLE | 0 |
| Median outside distance | **35.9 ATR** (≈4.05× zone height) |
| p25 / p75 distance | 11.8 / 98.4 ATR |
| Max distance | 297 ATR |
| ATR data gap | 0% |
| Resting limit inside the zone | **112 / 137** (81.8%) |

### By trigger

| Trigger | Rejects | B1 | B2 | B3 | B4 |
|---|---|---|---|---|---|
| F | 111 | 2 | 1 | 108 | 1 |
| A | 15 | 0 | 1 | 14 | 0 |
| B | 10 | 0 | 0 | 10 | 0 |
| C | 1 | 0 | 0 | 1 | 0 |

### By detection timeframe

| TF | Rejects | B1 | B2 | B3 | B4 |
|---|---|---|---|---|---|
| D1 | 67 | 0 | 0 | 67 | 0 |
| M15 | 27 | 2 | 2 | 23 | 1 |
| H4 | 25 | 0 | 0 | 25 | 0 |
| H1 | 18 | 0 | 0 | 18 | 0 |

Every edge-adjacent reject (B1/B2) and the single touch-but-close-out case comes
from **M15** POIs; D1/H4/H1 rejects are all far.

---

## 5. Reading

1. **C3 is a proximity/validity filter here, not an edge-trimmer.** 133 of 137
   rejects closed more than 1 ATR outside the body, with a median of ~36 ATR and
   a p75 near 98 ATR. These are not bars grazing a boundary — they are bars
   trading far from the zone.
2. **The boundary hypothesis is not supported by this window.** A boundary-sweep
   path is defined as catching completions that interact with the *edge*. That
   population is 2 (B1) + 1 (B4) = 3 cases, 2.2% of rejects — and the single
   touching reject sits 0.13 ATR away, i.e. it would be indistinguishable from
   noise inside any reasonable edge band.
3. **Most rejects are stale/far routes, not near-misses.** In 112 of 137 rejects
   the resting limit was still inside the zone while the completion bar had
   closed far away: the trigger fired long after (and far from) the POI became
   relevant. C3 is doing exactly the job §25 gives it — refusing a completion
   that is not happening *in* the zone.
4. **No timeframe corner case.** Edge-adjacent rejects concentrate in M15 (the
   tightest zone bodies), which is expected from body size alone and is
   consistent with C2b's color-free geometry rather than a specific defect.
5. **Observation only (not an O1 conclusion, not a proposal):** the distance
   distribution suggests the dominant cost is POIs staying in the scan after
   price has left, not the in-between predicate. Any change there would be a
   separate question with its own design and lock; it is explicitly not in this
   pack and must not be read as licence to touch C3.

---

## 6. Lock interpretation (words only — no product change)

Against agenda O1's criteria:

- **KEEP_STATUS_QUO** — the "far (B3) dominates and B4 is small" condition holds
  emphatically (B3 97.1%, B4 0.7%, B1+B4 2.2%).
- **BOUNDARY_DESIGN_WARRANTED does not apply.** The agenda deliberately set no
  numeric "material" bar; the qualitative reading plus the distribution (median
  36 ATR) leaves nothing to design against.
- **Never in this pack:** widening the close-inside rule or treating the
  distribution as a soft-in-between mandate. Neither was done.

**Recommendation to the Architect:** close O1 as **KEEP STATUS QUO** (C3
unchanged); if anything is opened later, it should be the *stale-POI lifetime*
question raised in §5.5, not the in-between predicate.

---

## 7. Caveats

- One window (October 2025), n = 137 rejects; counts above are descriptive.
- M1 is not a detection TF, so "M1" in the model tags refers to the
  liquidity-map model, not a detection series.
- No PnL/PF figure is used or reported here; it is not a lock input.
- Charts were optional and are not included: with 97% of rejects in one bucket
  a histogram adds nothing to the table.

---

## 8. Return block

```text
O1_STATUS: PASS
WINDOW: exec 2025-10-01 → 2025-10-31 UTC (load from 2025-05-01)
N_C3_EVALS: 149
N_NOT_IN_BETWEEN: 137
N_PASSED_C3: 12
BUCKET_SHARE: B1=1.5% B2=1.5% B3=97.1% (of rejects)
TOUCH_CLOSE_OUT_SHARE: 0.7% of rejects (1 of 137)
MEDIAN_DIST_ATR_OR_HEIGHT: 35.94 ATR (≈4.05× zone height)
TRIGGER_SPLIT: {"F": 111, "A": 15, "B": 10, "C": 1} rejects
INTERPRETATION: KEEP_STATUS_QUO
PRODUCT_CODE_CHANGED: NO
SUITE: N/A (scripts + docs only)
NOTE_PATH: 06_RESEARCH/OPEN_DECISION_O1_C3_BOUNDARY_ANATOMY.md
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
HANDOFF_UPDATED: YES
NEXT_READY: Architect O1 reading | O2 HTF-sweep stage pack
```
