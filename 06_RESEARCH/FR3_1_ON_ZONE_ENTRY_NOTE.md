# FR-3.1 — ON-ZONE ENTRY ANCHOR (F / M8 PATH)

**Date:** 2026-09-22 · **Authority:** Lead Architect FR-3.1 instruction (fate report accepted; primary blocker = F entry above zone high vs FR-3 gate).
**Scope:** Trigger F (BOS+OB continuation) entry anchoring only. **The FR-3 gate is NOT widened, NOT disabled; `ZONE_REFINEMENT_ATR`, all pillar thresholds, TP/SL policy, and every locked constant are untouched.**

---

## 1. Old rule vs new rule

| | OLD (pre-FR-3.1) | NEW (FR-3.1) |
|---|---|---|
| Entry reference | OB proximal edge (`top` LONG / `bottom` SHORT) | unchanged — still the OB proximal edge |
| Resting limit | = reference, verbatim | `zone_anchored_entry(direction, zone_low, zone_high, reference)` — on-zone reference passes **bit-exactly**; off-zone reference re-anchors to the **direction-proximal zone edge** (LONG → zone HIGH, SHORT → zone LOW) |
| Stop reference | OB distal edge (`bottom` LONG / `top` SHORT) ± 0.3×ATR (FR-2) | OB distal edge ± 0.3×ATR when the entry is the OB proximal edge (classic, unchanged); **zone distal edge** ± 0.3×ATR when the entry is re-anchored (the detached OB would put the stop on the wrong side of the limit) |
| Gate | `entry_within_zone(entry, zone, atr)` — reject outside ±0.5×ATR | **unchanged**, still the last line of defense |
| Signal metadata | — | `data["entry_anchor"]` ∈ {`ob_proximal`, `zone_edge_reanchor`} + detail suffix (ledger-distinguishable) |
| Degenerate guard | — | no signal when the stop does not sit strictly on the protective side (flat zone + unknowable ATR ⇒ zero SL distance ⇒ `risk_lots` would raise) |

**Anchor choice (documented per instruction): re-anchor, not reject.** The fate report showed the only two compliant-path evaluations were silent off-zone rejects while the diag proved the machine live behind the gate — rejecting again would preserve the silent blocker. Clamping to the *nearest* edge was rejected after test evidence: the deep shape (LONG, OB below the zone) would pin the limit at the zone BOTTOM with no protective stop room. Direction-proximal anchoring (LONG → high, SHORT → low) gives sane protective geometry in every shape and matches the instruction's spec verbatim.

## 2. Implementation

- `smc/triggers/base_trigger.py` — new shared, pure helper `zone_anchored_entry(direction, zone_low, zone_high, reference_price) -> float` (exported). Contains: on-zone passthrough; proximal re-anchor; unlocatable geometry (inverted/NaN/non-numeric) returns the reference untouched **so the gate, not the anchor, rejects it**. The §13 tolerance band is deliberately NOT applied inside the anchor (no widening anywhere).
- `smc/triggers/trigger_f_bos_ob.py` — uses the helper for the resting limit before the gate check; stop-reference selection follows the anchor (table above); degenerate-side guard; provenance in `data`/`detail`.
- No second entry-setting path exists: `pipeline_bridge.candidate_from_route` passes `signal.entry_price` through verbatim (verified this session); no other trigger is zone-gated. **Strategy surface touched: F only.**

## 3. Tests (14 new, file `04_SRC/tests/test_fr31_zone_anchored_entry.py`)

1. Helper units — on-zone exactness, LONG/SHORT proximal anchors (both off-zone sides), exact-edge, flat zone, inverted/NaN passthrough, non-numeric passthrough.
2. LONG detached OB **above** zone (the October shape) → entry = zone high, stop ref = zone bottom, `zone_edge_reanchor`, pre-gate on-zone, resting buy-limit below the touch-bar market.
3. SHORT detached OB **below** zone (point-reflected fixture, incl. proper swing-low BOS) → entry = zone low, stop ref = zone top.
4. **M8 fixtures:** the poi-002480 October geometry (zone high 3995.775, OB top 4039.555) now emits an on-zone entry; M8-tagged SHORT path; gate still rejects +0.1 outside (band untouched).
5. Regression anchors: classic LONG and SHORT on-zone fixtures keep **bit-identical** pre-FR-3.1 entry/stop (`ob_proximal`); overlapping-zone OB keeps the OB reference; flat-zone/no-ATR emits nothing.
6. Updated `test_fr3_zone_m4.py::test_f_rejects_trigger_ob_outside_thesis_zone` — docstring marks the FR-3.1 supersession; the gate-reject path is still exercised via the unlocatable-zone case.

**Full suite: 636 passed** (622 pre-FR-3.1 + 14 new), zero regressions.

## 4. Smoke — frozen October window re-run (fate script, logging-only shims)

Headline: **the primary blocker is resolved as designed — 0 routes → 2 routes, gate rejects 2 → 0.**

| metric | pre-FR-3.1 (FR-4) | post-FR-3.1 (smoke) |
|---|---:|---:|
| armed POIs (4 M8) | 8 | 8 (identical) |
| completed F signals | 0 | **2** (poi-002480, poi-005293) |
| FR-3 gate events | 0 pass / **2 reject** | **2 pass / 0 reject** |
| routes created | 0 | **2** |
| trades | 0 | 0 (both resting buy-limits un-filled within §24 expiry) |
| trades.csv vs run1 | byte-identical | byte-identical (book unchanged) |

Both routed orders are genuine resting limits: poi-002480 buy-limit 3995.775 (was +43.78 off-zone), poi-005293 buy-limit 4247.355 (was +16.50 off-zone). Zero fills is the honest outcome, not a defect: the re-anchored limit sits at the zone high while price had already moved above it post-BOS; touch-fill requires a retrace to the zone within the frozen expiry, which October did not provide. No tuning was done to force fills (banned).

Artifacts: `06_RESEARCH/results/fr31_smoke/armed_poi_fate{.csv,_summary.json}` (post-FR-3.1 run; scan-call counts differ from run1 downstream of routing — expected, routing now consumes scans). The FR-4 fate ledger under `results/fr4_fidelity/` was re-verified byte-exact against the accepted FR-4 numbers after the smoke (the fate script overwrote it once; regenerated deterministically with the pre-FR-3.1 module, then FR-3.1 restored — suite re-verified 636 green after restore).

## 5. Explicit statements

- **GATE_WIDENED: NO** — `entry_within_zone` byte-unchanged; `ZONE_REFINEMENT_ATR` byte-unchanged; the gate remains the last line of defense and still rejects unlocatable geometry.
- No locked constant touched; no new interim constants (reuses `FR2_SL_BUFFER_ATR` via `structural_sl` and the frozen §13 tolerance via the unchanged gate).
- No TP/SL policy change; the stop-reference relocation applies the FR-2 helper to the correct structural edge for re-anchored entries (leaving it on a detached OB would place the stop on the wrong side of the limit — geometrically invalid, not a policy choice).
- Residual status: the FR-4 "entry geometry" residual (F entry off HTF zone) is **addressed**; the "0 fills within expiry" observation is recorded, not optimized.
- This note changes entry anchoring only. No edge claim is made; the smoke is a mechanism demonstration on one month.
