# STOP-VS-STRUCTURE NOTES (original_sl only)

**Status:** COMPLETE 2026-09-20 · measurement only, no rules, no thresholds, no live gates.
**Script:** `06_RESEARCH/scripts/stop_vs_structure.py` (timestamp-anchored bars; Wilder ATR14; R3-taxonomy modes on honest MFE_R).
**Sample (labeled):** 69 pooled unique setups from verify_w0+w1 (64 F + 5 B), deduped like the wider study. NOT generalized beyond instrumented October flow.
**Outputs:** `06_RESEARCH/results/stop_vs_structure/stop_vs_structure.csv` + summary JSON. Zone-rectangle charts for tickets 121/197 (+78/90 from stratified set).

---

## 1. Headline contrast (all original_sl; ATR14 at entry)

| Family | n | Med stop/ATR | Med SL pre-touches (30b) | Exits: break / wick-tag | Entries inside zone |
|--------|---|--------------|--------------------------|-------------------------|---------------------|
| F (64) | 64 | 0.82 | **5.0** | 29 / **35** | **0 / 64** |
| B (5) | 5 | 2.65 | 1.0 | 3 / 2 | 1 / 5 |

- **F stops are tight (0.82×ATR), pre-touched (5× median), and die mostly by wick-tag (35/64):** the stop sits inside noise — price stabs through it and closes back in most deaths. Stop-inside-noise is the modal F failure.
- **B stops are wide (2.65×ATR), fresh (1 touch), and die mostly by close-through break (3/5):** the stop sits beyond structure and structure genuinely breaks. Different failure: level break, not noise tag.
- **F entries never start inside their recorded zones (0/64)** — consistent with the stratified 10/11 finding; the merge-widest-zone hypothesis stands untested.

## 2. B shelf findings (primary question)

- SL↔zone: 3/5 B stops sit INSIDE their POI zones (78, 90, 121) — the stop hides inside the zone it belongs to; 121's chart shows the wick tagging exactly the zone-top edge. 207 straddles (entry below, SL above the zone); 197 is divorced (entry/SL 700–850% above a far-below zone — pure chase).
- Shelf interpretation holds where zones are local (78/90/121/207): repeated-touch levels with the stop at/inside the extreme. Deaths split break (78 close-through, 207 grind-through) vs wick-tag (90, 121) — no single stop pathology; placement is structurally legible, outcomes hinge on whether the shelf holds.
- 197 is the exception proving the pattern: no shelf proximity at all, parabolic-top chase, instant stop. Zone-entry distance alone flags it.

## 3. F secondary comparison

- F failure modes in this pool: instant_stop 23, no_follow 15, gave_back 12, be_scratch 14 (mirrors book proportions).
- Wick-tag majority (35 vs 29 break) + 5 pre-touches + 0.82 ATR stops = the F book pays full stops for wick excursions through pre-tested levels. A stop-placement study that moves stops outside the pre-touched band is the natural next measurement — explicitly NOT authorized as a rule change here.
- Zone relation adds nothing new beyond the stratified finding (entries outside zones); F zone-entry geometry remains a merge-context question.

## 4. Exit-truth table (SL exits with honest bars)

- Close-through break: trade closed with the exit bar CLOSED beyond SL (structure broke on a closing basis).
- Wick-tag noise: SL touched intrabar, exit bar closed back (noise tag under frozen SL-first tie-break — the backtest books the loss; a live broker may or may not fill identically — divergence-log candidate for Phase D).

## 5. What this means / next

- Losses are mostly **stops inside noise (F)** with a minority of **genuine level breaks (B)** and a fringe of **entries past structure (197-shape chases)**. "Bad location" (F) dominates "stop interaction" (B) by flow share (64 vs 5 here; 659 vs 70 in the book).
- Original_sl proved CRITICAL: every ratio above uses placement stops; working-sl denominators would re-contaminate (BE median stop/ATR was 0.099 — buffer levels, not stops).
- Next (Lead Architect pick): formal flowchart↔implementation code map (are the zones/triggers on charts the objects the code computed?); stop-band measurement (pre-touch exclusion bands as pure observation); Phase D ops. None of this proposes moving a stop.

---

*End of stop-structure notes. Evidence: 69-row table + zone-rectangle B charts. No redesign proposed.*
