# FR-3 ZONE / ENTRY GEOMETRY + M4 FIDELITY NOTE

**Status:** COMPLETE 2026-09-21 · R1 spec + locked-tolerance grounded. No thresholds invented, no locked edits, no live gates.
**Tests:** `tests/test_fr3_zone_m4.py` (4 new) + M4 marginal decoy + 3 fixture updates (F zones, FR-2 warming ctx, M4 head). Suite **622 passed** (617 + 5), zero regressions — notably no pipeline-integration fallout.

---

## 1. Root causes found (survey)

- **Merge artifact CONFIRMED at code level:** `confluence_scorer.merge_overlapping` keeps the union envelope `[min(bottom), max(top)]` with tag union. Merged zones are envelopes by design (equal-tags doctrine protects the union).
- **Trigger OB ≠ POI zone by construction:** F finds its own origin OB from candles; the tracked (merged) POI zone is only the thesis container. Nothing constrained their relation — hence entries 1–4 zone-heights outside recorded zones.
- **M4 continuation tagging:** `M4Quasimodo.detect` accepted ANY head excess (`c.level > a.level`) over the shoulder, so grinding trends mint SHORT tags on every minor higher-high + dip. The R1 spec's "beyond" had no measurable content.
- **Tag flicker:** per-bar re-detection mints fresh uuids; shifted windows yield different tag sets on overlapping geometry; merge unions whatever co-occurs. Structural to the rolling design, not a one-line bug.

## 2. Policy chosen (entry↔zone)

Routed entries must lie inside their POI thesis zone ± the frozen §13 refinement tolerance (`ZONE_REFINEMENT_ATR`, no new number), enforced in `BosObContinuationTrigger.evaluate` via shared `entry_within_zone()` (ATR-unknowable → strict containment, never pass-through). A trigger OB outside its thesis is not routed — far-outside fills are rejected, never silently taken. Merge is deliberately UNTOUCHED (frozen confluence scoring depends on union tags/envelope; changing it has larger blast radius than the trigger-side check). A/D/E entry↔zone relations are unmeasured — residual, not exempt-by-proof.

## 3. M4 tightening (M4/M5 domain split)

Head must exceed its shoulder by MORE than the frozen EQH tolerance (`pips_to_price(EQH_EQL_TOLERANCE)` = 0.45 price units): at-or-under is equal-peaks structure (M5/M7 domain per §8), not a Quasimodo sweep. Uses only frozen constants. Acceptance fixture head strengthened 102.0 → 102.3 (synthetic test data depicting an unambiguous head; zone assertions untouched); new marginal-head decoy (0.4 excess → silent) pins the split. Partial by design: large-step grinds still tag — full trend-context cure needs FR-4+ work.

## 4. Modules touched

`triggers/base_trigger.py` (`entry_within_zone` + `__all__`), `trigger_f_bos_ob.py` (containment gate), `poi/models/m4_quasimodo.py` (domain split), `tests/test_fr3_zone_m4.py` (new), fixture updates in `test_trigger_f_bos_ob.py` (zones now meaningful, not dummies), `test_fr2_sl_tp_routing.py` (warming ctx zone), `test_poi_models.py` (head + decoy).

## 5. Residuals (explicit)

- A/D/E entry↔zone containment unmeasured (code paths untouched).
- Merge envelope still exports (charts show envelopes; routing now geometrically gated).
- Tag flicker structural (needs cross-bar episode identity — FR-4+).
- M4 large-step-grind tagging possible (trend-context rule deferred).
- Post-FR-3 books incomparable to Phase C (like post-FR-2); full measurement is FR-4.

---

*End of note. Next: FR-4 fidelity re-baseline order (Lead Architect). No redesign proposed beyond the ruled scope.*
