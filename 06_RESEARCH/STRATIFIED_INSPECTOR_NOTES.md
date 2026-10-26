# STRATIFIED INSPECTOR NOTES (conviction sample, not a survey)

**Status:** COMPLETE 2026-09-20 · visual analysis only, no code/threshold changes.
**Charts:** `06_RESEARCH/results/trade_inspector/stratified/` (11 verify-window) + `stratified/phase_c_b/` (5 Phase C B) — 16 charts + sidecars.
**Tooling incidents (disclosed):** (1) merged Phase C exports restart ticket numbers per segment — two `--ticket` renders initially hit wrong-segment rows (an F row rendered as "B"); fixed by route-id re-render + new inspector guard refusing ambiguous tickets loudly. (2) Inspector sidecar MFE now prefers `original_sl` (working-sl inflation removed at the tool level).

---

## 1. Set composition

| Stratum | Tickets | Sessions | Identity |
|---------|---------|----------|----------|
| A. F instant-stop | 14 (london), 48 (new_york), 92 (new_york) | mixed | full (verify export) |
| B. F no-follow, small MFE | 28 (asia), 63 (new_york), 87 (asia) | mixed | full |
| C. F non-loss/scratch | 8, 53 (asia), 115 (new_york) | mixed | full |
| D-verify. B holds | 78, 90 (Oct week) | — | full |
| D-phaseC. B full-SL × year | 62 (2021), 33 (2022), 132 (2024), 172B (2025), 9 (2026) | n/a | partial (pre-patch export: R3-joined failure/MFE only) |

Failures occur in every session (unique-setup split: instant-stops in asia/london/NY alike) — no session effect visible at this n. Duplicates collapsed: Group-1-style re-arm rows render once (tickets 1–5 = one L1 setup, reviewed in match notes, not re-rendered here).

## 2. Per-chart summary

| # | Trig/Sess | Models | Entry vs recorded zone | Visual call | Death mode |
|---|-----------|--------|------------------------|-------------|------------|
| 14 | F short/london | M1+M4+M5+M6+M7 | 116% below (8.2pts under) | late short into cascade, no pullback | instant_stop; continuation after stop (timing-wrong) |
| 48 | F short/NY | M1+M4+M7 | 405% below (16.2pts under) | knife-catch short at cascade lows | instant_stop; full reversal after (direction-wrong) |
| 92 | F short/NY | M1+M5+M7 | 213% below | short under choppy top, no impulse structure | instant_stop; rally after (direction-wrong) |
| 28 | F long/asia | M4+M5+M6 | 220% above | top-tick long after grind-up | no_follow_through; instant reversal |
| 63 | F long/NY | M1+M4+M5+M7 | 236% above | mid-leg long, no pullback; 4 tags incl M4 | no_follow_through; chop then stop |
| 87 | F long/asia | M1+M4+M5+M7 | 84% above | chop-zone long, no impulse origin | no_follow_through; grind-down |
| 8 | F long/london | M1+M7 | 354% above | late chase into extended rally | be_scratch |
| 53 | F long/asia | M1+M4+M7 | 94% above | **structured V-recovery retest — best F shape in set** | be_scratch (gave back a real 4.04R-honest run) |
| 115 | F long/NY | M1+M5+M7 | 38% above | chop entry, no impulse; rally came after exit | be_scratch |
| 78 | B short | M5+M6+M7 | INSIDE | shelf-fade at repeated level, instant break-through | no_follow_through (level broke) |
| 90 | B short | M7 | 191% below | same shelf, tight stop, both-way excursion | be_scratch |
| 62 | B long/2021 | unknown | n/a (pre-patch) | grind-top long, chop-through-stop, rally after | no_follow_through (timing-wrong) |
| 33 | B long/2022 | unknown | n/a | mid-chop long, breakdown through stop | no_follow_through (direction-wrong) |
| 132 | B short/2024 | unknown | n/a | post-top rollover short, wick-through-stop in chop | no_follow_through |
| 172B | B short/2025 | unknown | n/a | shelf short, grind-through-stop over 9 bars | no_follow_through |
| 9 | B short/2026 | unknown | n/a | shelf short, shelf broke, fully adverse | no_follow_through (direction-wrong) |

## 3. F pullback vs chase

- **Structured pullback: 1 of 9 F charts** (ticket 53: V-recovery retest with real 4R-honest excursion, gave back to BE).
- **Late-chase / mid-move / chop entries: 7 of 9** (28 top-tick; 63 mid-leg; 87 chop; 48 cascade-knife; 92 under-top; 8/115 extended-rally chase).
- **Borderline: 1** (ticket 14: pullback shape exists but entry sits mid-drop below any plausible origin).
- Reading (Inference): the F trigger as executed buys/sells momentum position, not pullback location — entries cluster mid-move or at extremes, 1–4 zone-heights from their recorded zones.

## 4. Zone geometry verdict: PARTIAL (useful with a staleness warning)

Bounds are real exported data and the one INSIDE case (B-78) renders exactly as intended. But 10/11 verify entries sit outside their recorded zones (38–405% of zone height away), so a naive rectangle would mislead more often than orient. Likely mechanism (Inference): confluence merge keeps the widest overlapping zone while the trigger fills at its own OB — merged-zone ≠ entry-zone. Recommendation: draw the zone **plus** the entry↔zone distance readout (already computable), and treat far-outside entries as their own finding (chase metric), not as rendering failures.

## 5. Key visual patterns (across strata)

1. **Chase/mid-move entries dominate F** (7/9): no visible pullback-to-level at the entry bar; entries at local extremes or mid-leg.
2. **Instant death has two aftermaths:** timing-wrong (continuation after stop: 14, 28?, 62) vs direction-wrong (reversal/continuation-against: 48, 92, 87, 9). Stop-timing fixes only help the first kind.
3. **Multi-model tags on momentum shapes:** 4–5-tag rows (14, 63, 87) incl. M4 sit on chases/tops, not on distinct pattern geometry — tag-count ≠ pattern-quality, visually corroborating the flicker finding.
4. **B is shelf-trading:** all 7 B charts center on repeated-touch levels; deaths are break-through (78, 9), wick-through in chop (132, 172B), or grind-through (33) — stop placement relative to the shelf, never a visible 5-wave structure, decides them.
5. **Scratches bank on excursion then full retrace** (53, 8, 115, 90): BE converts would-be give-backs into dust — the exit works mechanically while the entry timing wastes the move.

## 6. What this means for next research

- **F timing discriminator first:** structured-pullback (53-shape) vs chase (28/63/87-shape) coded as a chart-labeled feature on a larger stratified sample; test whether pullback-shape F entries survive to 1R at a different rate. Needs zone-entry distance (now computable) + pullback-depth features — offline feature work, no strategy change.
- **Stop-placement study needs original stops only** (now exported) + shelf distance (zone bounds now exported): B deaths are all shelf-relative stop tags.
- **No new inspector features needed** except: zone-rectangle rendering with distance readout (V1 follow-on, small), and Phase C re-export with identity fields if the 5y book must be charted at scale (current Phase C CSVs lack tags/pillar/disp).
- **Session split: no signal** — failures distribute across Asia/London/NY; drop session as a research axis for now.

---

*End of stratified notes. Evidence: 16 charts + sidecars + locked specs §§M1/M5/M7/TB/TF. Duplicate re-arm rows render once (Group-1 style); Phase C B rows addressed by route_id (ticket numbers restart per segment).*
