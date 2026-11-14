# OPEN DECISION O2 — HTF SWEEP: HARD STAGE VS UPSTREAM-ONLY (MEASUREMENT)

**Date:** 2026-11-14 · **Status:** MEASURED · **INTERPRETATION: KEEP_UPSTREAM_ONLY**
**`LOGIC_CHANGED: NO`** · **`PRODUCT_CODE_CHANGED: NO`**
**Authority:** `OPEN_DECISIONS_RESEARCH_AGENDA.md` §O2 (lock criteria),
Architect O1 lock (C3 `KEEP_STATUS_QUO`), `LOCKED_DECISIONS.md` §3 / Stage 0.
**Script:** `06_RESEARCH/scripts/o2_htf_sweep_stage.py`
**Artifacts:** `06_RESEARCH/results/open_decisions/o2_htf_sweep_stage/armed_sweep_join.csv`,
`summary.json` (results tree gitignored).

---

## 1. Question (from the agenda)

Must the *same* POI show a clear HTF sweep before the LTF seek, or is
displacement / pillar context enough?

---

## 2. Pre-registration (written into the script header before any outcome was read)

| Item | Value |
|---|---|
| Window | load 2025-05-01 · exec 2025-10-01 → 2025-10-31 UTC (identical to O1) |
| Detection set | D1 / H4 / H1 / M15 via `lib/product_htf_series` |
| Sweep source | `smc.detection.liquidity_scanner.scan(candles, tf, include=ALL_FAMILIES)` → `smc.detection.sweep_detector.detect_sweeps` (the frozen pair `DetectionDriver._stage0` composes) |
| **J1 (primary)** | sweep level inside `[zone_low, zone_high]` **AND** same direction (BSL→short, SSL→long) **AND** sweep candle timestamp ≤ arm time |
| J2 (secondary, LOOSE) | same direction, sweep level within **0.25 × ATR** of a zone edge — reported separately, never a lock input |
| No lookahead | sweeps computed once on the maximal closed-bar series per TF, then time-filtered at each arm |
| Cohorts | S+ = has J1 join; S− = no J1 join |

`J2_EDGE_ATR = 0.25` was fixed before the run and not retuned.

---

## 3. Coverage and reconciliation

- Armed POIs: **441**; CSV rows **441** — matches the funnel's `armed` exactly.
- **0** armed POIs lacked a detection series; **0** probe errors → **DATA_GAP 0%**.
- Sweeps available per detection TF: H1 1,009 · H4 747 · D1 242 · M15 485.
- Every armed POI carried displacement context (**441/441**), so the product's
  own L1 stamp cannot separate the cohorts — the sweep join is the discriminator.
- 131 distinct POIs produced the funnel's 149 C3 evaluations (some POIs routed
  more than once); the funnel's `routes`/`fills` reproduce O1 and post-C2
  exactly (149 / 11).

---

## 4. Results

**Cohorts (J1)**

| Cohort | n | share | routed | route rate | passed C3 | pass rate \| routed | filled | fill rate (of armed) |
|---|---|---|---|---|---|---|---|---|
| S+ (sweep in zone) | 369 | 83.7% | 108 | **29.3%** | 12 | **11.1%** | 11 | 2.98% |
| S− (no sweep) | 72 | 16.3% | 23 | **31.9%** | 0 | **0.0%** | 0 | 0.00% |

**J2 (LOOSE, secondary — same shape, not a lock input)**

| Cohort | n | routed | route rate | passed C3 |
|---|---|---|---|---|
| S+ loose | 378 | 110 | 29.1% | 12 |
| S− loose | 63 | 21 | 33.3% | 0 |

**By detection TF**

| TF | armed | S+ | routed | passed C3 | filled |
|---|---|---|---|---|---|
| D1 | 205 | 166 (81%) | 61 | 3 | 2 |
| H1 | 65 | 65 (100%) | 19 | 3 | 3 |
| H4 | 78 | 65 (83%) | 23 | 2 | 2 |
| M15 | 93 | 73 (78%) | 28 | 4 | 4 |

**Among C3 rejects** (routed but not passed): 119 POIs, **96 S+ (80.7%)**,
23 S− — i.e. the reject population is sweep-carrying too.

---

## 5. Reading

1. **Route generation is sweep-blind.** Sweep-carrying and sweep-free POIs reach
   C3 at the same rate (29.3% vs 31.9%, difference inside sampling noise at
   n=72). A hard sweep stage would therefore not have changed *which* POIs the
   LTF seek picks up in this window.
2. **The one visible separation is downstream of the seek.** Among routed POIs,
   12/108 S+ passed C3 versus 0/23 S−. That is a real-looking asymmetry but an
   *absence* on a small denominator (expected ≈2 passes at the pooled 9.2%
   rate, p ≈ 0.1 by eye); it cannot carry a lock, and it is confounded by
   geometry — 3 of 4 TFs' zone widths make J1 easy to satisfy (see §6).
3. **Sweep and reject co-occur.** 80.7% of C3 rejects are S+, so a sweep is not
   a proxy for a valid completion; the gate that matters remains in-between
   position, not sweep presence.
4. **H1 has no S− at all** (65/65). Any cohort split on H1 is structurally
   impossible, which is another reason not to build a stage on this measure.
5. **Consistent with the code**: `PipelineEngine.validate` has no sweep pillar
   and no trigger emits a sweep level; the measurement gives no reason to add
   one on this window.

---

## 6. Confound worth recording

J1 requires a sweep level *inside the zone band*, so wider zones (D1, H4) are
mechanically easier to satisfy than M15 bodies. The 83.7% S+ rate is therefore
partly a zone-width artefact, not evidence that sweeps are ubiquitous. A future
pack that wanted to test this properly would need a width-normalised join
(e.g. sweep within 0.25 × ATR of an edge, which J2 approximates) — and J2 shows
the same picture, so the conclusion does not rest on J1's width sensitivity.

---

## 7. Lock interpretation (words only)

Agenda O2 requires *consistently worse* route **and** path metrics for S−, with
enough n, reproduced, before a hard stage. Here:

- **route**: no difference (S− marginally *higher*),
- **path**: one asymmetry (0/23 vs 12/108) that is small-n and confounded,
- **reproduction**: not attempted (single window; the agenda makes a second
  window optional only where n allows).

Therefore **KEEP_UPSTREAM_ONLY**, which is also the agenda's default bias and
matches current code. Sweep stays context for zone birth and pillars; no sweep
pillar, trigger field or gate is proposed. No C3 / C2a / C2b change.

---

## 8. Caveats

- One window, n = 441 armed / 131 routed; rates are descriptive, not inferential.
- PnL was not used at any point; fills are counted as outcomes only.
- Fill counts are tiny (11) and are reported to show the horizon, not to rank
  the cohorts.
- The sweep↔POI join uses the same detection-TF series the batch saw, but is
  recomputed independently (not read from the driver's discarded `DetectionRun`),
  so it verifies rather than repeats product internals.

---

## 9. Return block

```text
O2_STATUS: PASS
WINDOW: exec 2025-10-01 → 2025-10-31 UTC (load from 2025-05-01)
SWEEP_JOIN_RULE: J1 — same-direction Stage-0 sweep whose level lies inside [zone_low, zone_high] on the POI's detection TF, candle time <= arm time
N_ARMED: 441
SHARE_S_PLUS: 83.7%
ROUTE_RATE_S_PLUS: 29.3%
ROUTE_RATE_S_MINUS: 31.9%
PASS_C3_RATE_S_PLUS: 11.1% (12/108)
PASS_C3_RATE_S_MINUS: 0.0% (0/23)
FILL_RATE_S_PLUS: 2.98% of armed (11/369)
FILL_RATE_S_MINUS: 0.0% (0/72)
DATA_GAP: 0 (0 armed POIs without series, 0 probe errors)
INTERPRETATION: KEEP_UPSTREAM_ONLY
PRODUCT_CODE_CHANGED: NO
NOTE_PATH: 06_RESEARCH/OPEN_DECISION_O2_HTF_SWEEP_STAGE.md
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
HANDOFF_UPDATED: YES
NEXT_READY: Architect O2 reading | O3 multi-zone priority pack
```
