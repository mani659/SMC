# FLOWCHART / KB MATCH NOTES (V1 curated charts)

**Status:** COMPLETE 2026-09-20 · analysis + documentation only. No strategy-code, threshold, or MT5 changes.
**Evidence:** 13 curated charts + sidecars (`results/trade_inspector/curated/`, tickets 1–5 F-loss, 8–12 F-non-loss, 78/90/91 B) against `LOCKED_DECISIONS.md` and `SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md` (§M1/M5/M7, §Trigger B/F). Rule text checked, not assumed; unlocatable rules marked UNDOCUMENTED (none needed — all cited rules located).
**Scoring (conservative):** STRONG needs chart + tags + trigger to jointly match a documented path (never awarded on visual impression alone here); PARTIAL = some elements match, key geometry unverifiable; WEAK = labels exist but chart undermines the setup; UNCLEAR = insufficient context. Zone/wave geometry is in no export, so no STRONG ratings are possible in this round.

---

## 0. Measurement caveat discovered during review (load-bearing for R1–R3)

Exported `sl` is the position's **final** SL (post-BE-modify), not the original stop: BE-scratch sidecars show SL on the profit side of entry (e.g. long entry 3888.978 / sl 3889.161). Consequences, recomputed from stored artifacts:
- R1 MFE_R mixes two denominators. Decontaminated: **non-BE trades (567 SL + 7 Friday): median MFE 0.18R (was 0.55 blended), 17.1% reach 1R (was 37.5%), 39.7% never favorable. BE trades (187): median MFE 20.66R, 100% ≥1R** — inflated by BE-tightened denominators + BE-protected lifetimes.
- R3 stop/ATR mixes two SL definitions: **non-BE median 0.84–0.89×ATR (F-nonBE 0.841); BE median 0.099×ATR (= the 0.10 buffer — these aren't stops at all).** The "sub-ATR stops" conclusion survives on honest stops; the 0.72 blended figure is retired.
- R2 replayed 187 trades against BE-tightened stops → TP-hit counts are conservative lower bounds; the "fixed TP fails" direction is robust (wider original stops can only add hits, and 11≪needed regardless).
- Fix: persist **original SL at placement** alongside current SL (export-patch follow-on).

## 1. Scope & evidence base

13 rows = **~5 distinct setups** (verify-run over-arming re-detects one zone per bar under fresh uuids): L1 = tickets 1–5 (F short loss, M1); L2a = tickets 8,9,10 (F long scratch, M1+M7 / M4 / M5 across re-detections); L2b = tickets 11,12 (F long scratch, M1+M7 / M4); B1 = ticket 78 (B short loss, M5+M6+M7); B2 = tickets 90,91 (B short scratch, M7 / M1+M4+M7). Row counts below are setup-weighted where stated — five similar rows are one observation, not five.

## 2. Method

Sidecar identity (trigger/models/pillar/disp/MFE/failure) + chart read (pre-entry structure, entry timing, stop placement, aftermath) → scored against the cited spec blocks. Facts observed vs interpretation separated per trade. F and B kept separate throughout.

## 3. Family conclusions

### F losses (1 setup: tickets 1–5, M1, gave_back, hold 2)
Rally to ~3875 top, sharp drop, short entry 3865.325 mid-pullback, SL 0.93 above, wicked out, continuation down ~13pts after the stop. Entry timing and direction match the M1-bearish-origin + F-continuation path (swing high → break → pullback entry, first touch); the stop sat inside the return-wick zone. Direction right, stop-timing wrong — the canonical instant/gave-back bleed. **PARTIAL** (entry narrative fits; OB-proximal/50% placement and beyond-distal SL unverifiable without zone geometry).

### F non-losses (2 setups: L2a tickets 8,9,10; L2b tickets 11,12 — all be_scratch)
Both are **late-chase longs deep into extended rallies** (L2a entry after ~30pt run-up, SL 0.18; L2b similar, SL 0.19), exited at BE while price chopped/continued. Structurally the opposite of a retrace-to-origin entry: no pullback is visible at the entry bar. **WEAK, both.** Tags flicker across re-detections of identical geometry (L2a: M1+M7 → M4 → M5; L2b setup shared by M1+M7 and M4 rows), and **M4 (Quasimodo reversal) tags sit on with-trend continuation entries with no visible head/shoulders reversal geometry** — a tag/chart vocabulary mismatch.

### B (2 setups: B1 ticket 78 loss; B2 tickets 90,91 scratch)
B1: short into a repeatedly-rejected shelf (~3959, multiple touches), SL 1.52 above, immediate break-through-stop; aftermath continued adverse. B2: same shelf area, short, tight stop, BE rescue amid large both-way excursion (MFE 13.25R on BE-tight denominator — see §0). Shelf tags (M5/M6/M7) visibly correspond to the repeated-touch level — the best tag/chart agreement in the set. But **Trigger B's documented mechanism (5-wave impulse → Fib 50–61.8% Wave-2 pullback, SL beyond Wave-1 origin) is unverifiable by eye at M1 resolution on these charts**, and B2 adds M1+M4 tags onto the same shelf (same flicker as F). **PARTIAL, both**, carried by shelf-tag agreement, capped by unverifiable wave structure.

## 4. Rule-by-rule match table

| Ticket(s) | Trig | Tags | Intended rule path | Match | Why | Death mode |
|-----------|------|------|--------------------|-------|-----|------------|
| 1–5 (1 setup) | F | M1 | M1 bearish origin + F retrace-entry, first touch | PARTIAL | Entry narrative fits; OB proximal/50% + distal SL unproven (no geometry) | Stop-timing (wick through tight SL, continuation after) |
| 8,9,10 (1 setup) | F | M1+M7 / M4 / M5 (flicker) | F continuation + origin retest | WEAK | Late-chase entry, no pullback visible; M4-on-continuation mismatch; tags unstable across identical geometry | BE scratch (late entry, noise stop) |
| 11,12 (1 setup) | F | M1+M7 / M4 (flicker) | F continuation + origin retest | WEAK | Same as L2a; 26R MFE is BE-denominator inflation (§0) | BE scratch |
| 78 (1 setup) | B | M5+M6+M7 | Shelf/breaker POI + B Wave-2 pullback | PARTIAL | Shelf tags match visible repeated level; 5-wave/Fib structure unverifiable visually | Stop-timing (break-through, SL 1.52) |
| 90,91 (1 setup) | B | M7 / M1+M4+M7 (flicker) | Shelf POI + B Wave-2 pullback | PARTIAL | Same shelf agreement; M1+M4 add-ons unsupported; wave structure unverifiable | BE scratch amid both-way excursion |

F STRONG/PARTIAL: 1 setup (PARTIAL), 0 STRONG. F WEAK/UNCLEAR: 2 setups (both WEAK).

## 5. Pattern vocabulary mismatch

1. **Tag flicker:** identical zone geometry re-detected across bars yields different tag sets (M1+M7 → M4 → M5; M7 → M1+M4+M7). Tags are detection-path-dependent, not geometry-intrinsic — per-tag conviction from trade counts alone is unsafe.
2. **M4 on continuation flow:** Quasimodo (documented as asymmetric reversal) tags two with-trend long entries with no visible reversal structure. Either the detector sees swings the eye can't at this resolution, or the tag overfires — currently UNCLEAR, leaning mismatch.
3. **Traded triggers vs killed patterns:** admitted flow is F-trigger continuations while R4 kills are M5/M4/M6-pattern zones — the funnel's pattern vocabulary and the trigger's pattern vocabulary barely overlap (R4 §F; corroborated here: F trades carry M1/M5/M6/M7 tags interchangeably on similar pullback shapes).
4. **Geometry gap:** entry-at-proximal/50%, beyond-distal SL, Fib levels, wave counts — none exportable, none verifiable. Every geometric assertion in §M1/§F/§B specs is currently uncheckable per trade.

## 6. What we can hold conviction on

- F fires on real BOS-continuation pullback geometry (L1 is the intended shape, working as drawn except the stop).
- BE latch banks scratches exactly as designed (L2a/L2b/B2 exits).
- Shelf/level tags (M5/M6/M7) correspond to visible repeated-touch levels (B1/B2).
- Stops are the binding constraint: tight stops tagged before continuation (L1, B1); BE rescues the rest.
- Decontaminated baselines are WORSE than published for entries (0.18R median / 17.1% ≥1R on honest denominators) — the entry-side verdict strengthens.

## 7. What we cannot claim yet

- That M1/M4 tags identify distinct validated patterns (flicker + continuation-mismatch).
- That any entry sat at its documented geometric point (no zone/wave exports).
- Any per-family expectancy (5 setups; contaminated denominators now bounded but not repaired).
- That B's wave-structure mechanism operates as specified (unverifiable at this resolution).

## 8. Implications for next research

- **Export geometry needs (ordered):** (1) ORIGINAL sl at placement (repairs all R-multiple math); (2) POI zone top/bottom (+ timeframe); (3) trigger geometric refs (OB proximal/distal used, Fib zone for B); (4) displacement BOS index + FVG bounds. Logging-only, same patch pattern.
- **More inspector cases:** yes — stratified sample (F scratches vs instant-stops × sessions; B holds × years), scored with this template; 5 setups is a pilot, not a survey.
- **Selectivity questions:** late-chase (L2-shape) vs structured-pullback (L1-shape) entry timing as the candidate F discriminator; FVG-absence (R4) unchanged as the kill-side question.
- **Stop-timing questions:** confirmed central, but all stop analysis must use ORIGINAL stops post-patch; current stop findings carry the §0 contamination note.

---

*End of match notes. Evidence: 13 curated PNG+JSON + locked specs §§M1/M5/M7/TB/TF. No redesign proposed; no thresholds questioned; geometry gaps marked, never filled.*
