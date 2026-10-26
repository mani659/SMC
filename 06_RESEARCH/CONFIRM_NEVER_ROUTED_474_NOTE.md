# 474 NEVER-ROUTED DECOMPOSITION (DIAGNOSTIC)

> **DIAGNOSTIC — NOT EDGE.**
> Exclusive taxonomy of why 474 post-sweep confirmed episodes never
> became post-sweep product routes. No threshold was changed, no gate
> follows, no production code was touched. No table supports or
> refutes edge or licenses any filter — several buckets explicitly
> record the machine working as designed.

**Date:** 2026-10-11 · **Authority:** Lead Architect directive (after POI_CONFIRM_ENTRY_PATH_NOTE.md).
**NEVER_ROUTED_STATUS: PASS** (population reconciles exactly; 3 new tests green).
**LOGIC_CHANGED: NO** (research script + tests only); locked_constants empty.

---

## 1. Reconciliation + top table (n = 474 exactly: 340 + 32 + 102 + 0)

| Reason | n | % of 474 | Median bars sweep→confirm | Examples (earliest first-sweep) |
|---|---|---|---|---|
| **A no-product-POI** | **340** | **71.7%** | 25.0 | poi-m8-h4-53094fb7, poi-m8-h4-5a6da789 (+2) |
| B routed-before-sweep | 32 | 6.8% | 21.0 | poi-m8-h4-8656a7c9, poi-m8-h4-d7137977 |
| C scanned-no-route | 102 | 21.5% | 25.0 | (per sub-bucket below) |
| D other/gap | 0 | 0.0% | — | — (never-scanned 0, unclassified 0) |

## 2. A split: validated-elsewhere 271 vs never-validated 69

Of the 340 episodes with no product POI covering their geometry, **271
sit on geometry present in the accepted H4/D1 packs** while only 69
are raw-only detections. The dominant gap is therefore NOT pillar
rejection of unknown zones — it is validated-geometry that this run's
batches never armed (passed→armed selection and batch/dedup dynamics;
per-POI arming logs don't exist, so validation-reject vs
never-armed cannot be split from here — fix class: instrument first,
then Architect). The 69 raw-only rows are pillar-stage territory
(fix class: real rule change, Architect only).

## 3. C sub-break (frozen priority: expired > late > matrix > rest)

| Sub-reason | n | Fix class |
|---|---|---|
| C1 expired-give-up (confirmation after arm+20) | 72 | real rule change (horizon length — Architect only; the deadline did its designed job) |
| C2 scan-late (first scan after confirmation) | 25 | arm timing |
| C3 matrix-ineligible | **0** | — (validates the router docstring empirically: the §15 matrix grades ties, forbids nothing) |
| C4 scanned-no-route-unspecified | 5 | instrumentation (per-scan posture/cursor/signal logging) |

Examples: C1 poi-m8-h4-e56ac38a, poi-m8-h4-2fb002b1; C2 poi-m8-h4-435fe94f,
poi-h1-64810906; C4 poi-m8-h4-c3a21e4d, poi-m8-d1-a27ecaf3.

## 4. B note: working as designed (not a gap)

All 32 B rows routed earlier on the same episode (one-shot consumed);
post-sweep confirmation of a decided POI is moot by LOCKED §11
identity. Fix class: none. Removing B from "the problem" leaves 442,
of which A still dominates (77%).

## 5. Dominant reason — code vs policy (one paragraph)

**A-validated-elsewhere (271/474, 57%) dominates**: confirmed geometry
the packs accept but the product never armed — a batch/dedup/arming
question, not a trigger question, and its fix class is instrumentation
(per-POI validation→arming logs) before any Architect ruling on
selection; next come C1-expired-give-up (72, horizon policy — the only
large bucket a rule change could address, and the deadline behaved as
designed) and A-never-validated (69, pillar policy). Code (a defect to
fix now): nothing — no unclassified rows, no join failure, no
mis-timestamping found. Policy (Architect only): give-up horizon,
pillar bands, arm-selection, one-shot identity — in that evidence
order. Everything else is measurement needed first.

## 6. Method + limitations (binding)

Population = Step-4 lifecycle rows with gap_reason set (confirmed,
never post-sweep routed); Step-4 helpers reused (episode keys, gap
taxonomy); M5 grid rebuilt identically (35,725 bars, endpoints
asserted); accepted-pack geometry via episode-key match; matrix via
`router.eligible_types` on merged tags (empty tags default eligible —
never counted ineligible, documented). Medians use
bars_sweep_to_confirm (M5 bars). Containment joins inherit Step-4
Tier-B matching. No gate, no threshold, no live rule follows.

---

**Artifacts:** `06_RESEARCH/scripts/confirm_never_routed_474.py` (new) ·
`06_RESEARCH/results/confirm_never_routed_474/` (`decomposition.csv`
474 rows, `summary.json` with frozen rules + tables + fix classes) ·
tests `04_SRC/tests/test_confirm_never_routed_474.py` (3).
