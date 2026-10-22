# ARMING FORENSICS — BUCKET A (DIAGNOSTIC)

> **DIAGNOSTIC — NOT EDGE.**
> Of 271 confirmed episodes on accepted-pack geometry that the product
> never armed, 138 overlap an armed episode in price+time (identity
> candidates for chart check), 82 passed validation but stayed
> unarmed, 51 failed pillars in-batch, and 0 are unexplained by data
> gaps. No threshold was changed, no gate follows, no production code
> was touched. No table supports or refutes edge or licenses any
> filter — several buckets explicitly record the machine working as
> designed.

**Date:** 2026-10-11 · **Authority:** Lead Architect directive (after CONFIRM_NEVER_ROUTED_474_NOTE.md).
**ARMING_FORENSICS_STATUS: PASS** (population reconciles exactly; 5 new tests green).
**LOGIC_CHANGED: NO** (call-through recording wrappers, restored after; research script + tests only).

---

## 1. Method in one paragraph (frozen)

The frozen p3 composition driven verbatim with record-only wrappers
(raw detections per batch, validated outcomes with PASS/first-failure
via details-carried POIs, arm events; true originals restored in
`finally`), proven identical to the 6m refresh (byte-identical
trades.csv + report.json, funnel equal on every count). Each of the
271 A-validated-elsewhere episodes classified by frozen priority
(identity > pass > fail > absence > gaps) against the recording:
A4 = same-direction overlap with an armed episode within ±30 days
(heuristic identity evidence); A3 = any PASS + never armed (dedup
tested with the exact ZoneDedup rule — same direction + overlap with
a strictly-earlier-batch arm; same-batch order unknowable);
A2 = all matched failed (pillar histogram kept); A1 = absent from
every validated set (A1a never detected anywhere vs A1b raw exists);
A5 = inputs missing. Medians use bars_sweep_to_confirm; examples are
earliest-first-sweep per bucket. Script:
`06_RESEARCH/scripts/arming_forensics_bucket_a.py`.

## 2. Table: reason → n → % of 271 → median bars → fix class

| Reason | n | % | Median | Fix class |
|---|---|---|---|---|
| **A4 armed_other_identity** | **138** | **50.9%** | 25.0 | identity review (human chart check — see §3) |
| A3 passed_not_armed | 82 | 30.3% | 27.5 | dedup-loser 47: batch/dedup dynamics (instrument arm order first); other 35: instrumentation (no other filter exists in `_arm_passed` — verified by reading) |
| A2 in-batch-failed-pillars | 51 | 18.8% | 20.0 | pillar bands (Architect only) |
| A1 never-in-batch | 0 | 0.0% | — | — (every episode appears in some batch's validated set) |
| A5 data_gap | 0 | 0.0% | — | — (no missing inputs) |

## 3. Dominant miss reason: A4, with evidence grades (not a verdict)

The 138 A4 rows are overlap candidates in three tiers — **exact 0,
contained 41, partial 97** — with arm-to-first-seen gaps at median 8
days (p90 22, max 30 by construction). All 41 contained cases run the
same direction: the **armed zone is SMALLER, inside the census zone**
— consistent with Pillar-1 refinement narrowing raw zones before
arming (a coherent product story, not proof). No episode was armed
under identical bounds without being scanned (exact 0 — Step-4's
Tier-C-none stands uncontradicted). Reading honestly: containment +
8-day median proximity is moderate evidence of true identity; partial
overlap at blanket-zone density is weak evidence either way. The
chart-check list (episode bounds + matched armed bounds + both
timestamps in `forensics.csv`, examples `poi-m8-d1-d7d90066`,
`poi-m8-d1-c1667336` first) decides identity — this note does not.
Selection vs pillars vs identity: A4 is an **identity** question;
A2 (P1 618 / P2 20,029 / P3 586 fail-events — pillar histogram as
required) is **pillars**; A3-dedup-loser (47, exact-rule replications)
is **selection** (ZoneDedup, the only passed→armed filter in code —
no cap, score, freshness, or TF-schedule filter exists); A3-other
(35) is genuinely unexplained and needs batch arm-decision logs.

## 4. What this changes about the 474 story

Bucket A is not "pillar rejection of unknown zones": every row sits
on accepted-pack geometry, every row was seen validated in-batch
(A1 = 0), and over half overlap an armed episode in price+time.
Combined with Step-4's gap table, the measured chain now reads:
confirmed 490 → 340 no-product-POI, of which 271 pack-present split
138 possibly-armed-under-another-identity / 82 passed-unarmed (47
dedup losers) / 51 pillar-killed. The remaining unknowns are
concrete and loggable: per-batch arm-order (dedup-possible is 0
precisely because intra-batch order is unlogged, not because it
doesn't happen) and the 35 A3-other passes that nothing in the code
explains away.

## 6. Concrete examples for human chart check (5 per top reason)

Columns: episode_id · side · bounds · first_seen · first sweep · sub ·
matched-arm ts / match-kind · fail history (pillar x batches).

A4 (overlap candidates — chart decides identity):
- poi-m8-d1-d7d90066 · SHORT 3343.448–3384.495 · seen 2025-06-04 ·
  sweep 2025-06-05T00:00 · armed 2025-06-04 · partial
- poi-m8-d1-c1667336 · SHORT 3320.985–3339.048 · seen 2025-06-05 ·
  sweep 2025-06-06T00:00 · armed 2025-06-27 · partial
- poi-m8-h4-310bb224 · LONG 3308.425–3358.748 · seen 2025-06-02 ·
  sweep 2025-06-06T20:00 · armed 2025-06-02 · partial
- poi-m8-h4-3bc1f66c · SHORT 3309.018–3320.985 · seen 2025-06-08 ·
  sweep 2025-06-09T08:00 · armed 2025-06-30 · partial
- poi-m8-h4-83598d60 · SHORT 3310.525–3331.965 · seen 2025-06-09 ·
  sweep 2025-06-09T16:00 · armed 2025-06-27 · partial

A3 (passed, never armed):
- poi-m8-h4-53094fb7 · LONG 3347.745–3364.948 · seen 2025-06-04 ·
  sweep 2025-06-04T12:00 · dedup-loser · fails 2x1772;1x152;3x116
- poi-m8-h4-5a6da789 · LONG 3364.935–3370.665 · seen 2025-06-04 ·
  sweep 2025-06-04T12:00 · dedup-loser · fails 2x1946;1x145;3x116
- poi-h4-512a3ea1 + poi-m8-h4-cea65fa4 · LONG 3332.575–3362.948 (same
  geometry, H4-census and M8-census rows) · seen 2025-06-05 /
  2025-06-03 · sweep 2025-06-10T08:00 · dedup-loser · fails
  2x1499;1x151;3x74
- poi-m8-h4-0b45f63a · SHORT 3312.595–3316.065 · seen 2025-06-06 ·
  sweep 2025-06-06T16:00 · other (no earlier overlap; nothing in code
  explains the miss) · fails 2x1867;3x65;1x16
- poi-m8-h4-68eb3495 · LONG 3329.285–3331.065 · seen 2025-06-25 ·
  sweep 2025-06-25T04:00 · other · fails 2x3727;1x157;3x130

A2 (failed pillars — P2-dominated throughout):
- poi-m8-h4-329fbeac · LONG 3418.915–3438.655 · seen 2025-07-23 ·
  sweep 2025-07-23T04:00 · fails 2x111;3x19;1x2
- poi-m8-h4-d4e6874b · LONG 3471.915–3498.115 · seen 2025-09-02 ·
  sweep 2025-09-02T08:00 · fails 3x16;2x4
- poi-m8-h4-61dc16f0 · LONG 3489.845–3517.845 · seen 2025-09-02 ·
  sweep 2025-09-02T12:00 · fails 2x115;3x27
- poi-m8-h4-648cdc24 · LONG 3520.215–3525.848 · seen 2025-09-02 ·
  sweep 2025-09-02T16:00 · fails 2x378;3x26
- poi-m8-h4-ded9f31b · LONG 3525.848–3537.548 · seen 2025-09-02 ·
  sweep 2025-09-02T16:00 · fails 2x362;3x15

A1/A5: n = 0 — no examples exist (every episode appears in some
batch's validated set; no inputs missing).

## 7. Limitations (binding — DIAGNOSTIC)

- A4 overlap is cheap evidence under 99.9% zone-blanket coverage;
  only the chart check promotes candidates to identities.
- ±30-day identity window is a heuristic (documented, frozen).
- Passed-but-unarmed beyond dedup has no code explanation — the
  "other" bucket is a measurement of the logging gap, not a finding.
- Model skips: zero batches (clean run); thin-prefix skips: 15
  (out-of-window dates).
- Matrix/router out of scope (already C3 = 0, empirically).
- No live rule changes recommended in this note body — facts for
  Architect ruling only.

---

**Artifacts:** `06_RESEARCH/scripts/arming_forensics_bucket_a.py` (new;
+ `replay_run1/` fidelity artifacts) ·
`06_RESEARCH/results/arming_forensics_bucket_a/` (`forensics.csv` 271
rows, `summary.json` with frozen rules + tables + fix classes) · tests
`04_SRC/tests/test_arming_forensics_bucket_a.py` (5).
