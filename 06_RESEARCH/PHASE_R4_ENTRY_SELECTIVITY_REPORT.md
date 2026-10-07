# TRACK R4 — FULL ENTRY-SELECTIVITY / PILLAR-2 DIAGNOSIS REPORT

**Status:** COMPLETE 2026-09-19 · measurement only, no threshold changes, no redesign, no edge claims.
**Script:** `06_RESEARCH/scripts/r4_entry_selectivity.py` (imports detection/orchestration/data modules for REPLAY-ONLY diagnosis — nothing frozen is modified).
**Design:** 131 tiled 14-day own-windows (+10d prefix each) over the full canonical range; frozen `DetectionDriver.validate_window` per window (detect→merge→validate, no arming/routing/risk). Unit = window-evaluation kill events (parallels Phase C per-bar validation EVENTS; adjacent recounts disclosed, NOT deduped). Detection blind to future bars; forward path measured on stored series from the decision bar W1 (arm-bar equivalent), exactly like R1 windows.
**Outputs:** `results/r4_entry_selectivity/` — `pillar2_kills.csv` (335 rows), `window_census.csv` (131), `comparison_groups_summary.csv`, `per_trade_enriched_identity.csv` (R3 + trade-book ATR terciles + pillar_path flag), `assumptions.json`, `r4_summary.json`.
**Population:** FULL batch-mode kill population across the dataset — no sampling needed (335 P2 kills ≥ 300 target).

---

## A. Funnel census (Phase C cited + fresh batch census)

| Source | Raw → validated → armed → routed → placed → opened |
|--------|-----------------------------------------------------|
| Phase C per-bar events (report §4, cited) | 10,682,651 → 6,256,227 events (928,436 pass, 14.8%) → 5,166 armed → 981 routes → 792 placed → 761 opened |
| R4 batch windows (131, fresh) | 773 raw → 454 merged (77 pass, **17.0%**) → P2 kills 335, P/D kills 32, zone-ref kills 10 |

- Batch pass rate (17.0%) reproduces the per-bar pass rate (14.8%) within regime — the funnel's selectivity is stable across evaluation modes. (Fact)
- First-failure is Pillar-2-dominated in both modes (76% per-bar; 74% batch). Pillar 2 IS the funnel. (Fact)

## B. Pillar-2 kill population (n = 335, full population)

- **Sub-reasons (structured, from the driver's own attribution):** hard_fail (magnitude <0.5×ATR) 111 · twilight evaluated-fail 224 · unavailable 0. Median kill magnitude **0.77×ATR** — kills cluster just under the 1.0 gate, in the twilight between hard-fail and pass.
- **Binding sub-constraint is FVG, not BOS:** 263/335 kills (78%) HAVE BOS; only 31/335 (9%) have FVG. The gate kills on missing FVG first, magnitude second.
- **Kill model mix (merged tags, real labels):** M5-alone 98 (29%), M6 38, M4 31, M7 11, M1 8, M2 8, M3 1; rest multi-tag combos. M3/CHOCH is nearly absent from kills AND from the admitted book — CHOCH-pattern flow is thin end-to-end. (M8 silent: no HTF feed, as known.)

## C. Counterfactual quality of kills (two disclosed hypothetical models)

| Model | H5 med MFE/MAE | H15 med MFE/MAE | H60 med MFE/MAE | Reach 1R | Reach 2R |
|-------|----------------|-----------------|-----------------|----------|----------|
| edge (proximal entry, distal stop) | 1.34 / 0.10 | 1.82 / 0.73 | 3.07 / 2.32 | 54.3% | 46.0% |
| midbuf (mid entry, distal+0.5ATR) | 7.24 / 0.00 | 9.19 / 1.17 | 14.31 / 5.61 | 55.8% | 55.5% |

- Kills MOVE: 54%+ reach 1R within 60 bars under hypothetical stops, with fast early excursion (edge 1.34R already at +5 bars).
- **Hard-fail vs twilight do NOT separate:** hard-fail reach_1R 57.7% vs twilight 52.7–54.9%. The magnitude dimension of Pillar 2 does not discriminate counterfactual quality — the gate's 0.5/1.0 steps are not where outcomes split.
- **Generosity caveat (binding):** hypothetical entries assume fills with no touch requirement and zone-width/buffered stops FAR wider than real sub-ATR stops. Reachability here is an upper bound, not tradeability. (Fact about method; inference below.)

## D. Admitted-entry quality comparison (funnel step-by-step?)

| Group | Never-fav | Med MFE_R | Instant-stop | No-follow | Hold |
|-------|-----------|-----------|--------------|-----------|------|
| P2 kills (generous hypothetical) | n/a | H60 3.07–14.31 | n/a | n/a | fixed horizons |
| Admitted F (strict reality, R1/R3) | 31.3% | 0.55 | ~29%* | ~33%* | med 1–2 bars |
| Admitted B (R1) | 20.0% | 6.12 | — | — | med 14–15 bars |
| Armed-never-traded | **MISSING** (not persisted) | — | — | — | — |

\* book-wide failure-mode shares; F-dominated in every mode.
- Kills (generous) reach 1R at 54% vs admitted F at 36% (strict). The gap is fully explainable by assumption asymmetry (assumed fills + wide stops vs real fills + 0.72×ATR stops) — it does NOT prove overfiltering, but it DOES prove kills are not obviously junk: junk wouldn't move 3–14R in 60 bars under any stop.
- **MIXED verdict on funnel quality:** the funnel admits weak entries (admitted-F quality is poor under strict conditions) AND rejects candidates that move (under generous conditions). Neither "correctly killing junk" nor "over-killing gold" is established — the admitted and killed populations were measured under incomparable execution assumptions.

## E. Rule-identity enrichment

- Kills carry REAL merged model tags (table §B) and trigger='never_routed' — the first tag-level view of rejected flow: M5/M4/M6-heavy, M3-absent.
- Admitted book enriched: + trade-book ATR terciles (q1 0.550 / q2 1.112), session/year/stop-ATR already in R3; pillar_path and model_tags remain `unknown`/`unrecoverable_not_persisted`.
- **Minimum export patch proposed (not implemented):** persist `model_tags` (merged union) + per-POI `pillar_path` (first-failure or PASS) + `displacement_magnitude_atr` onto every trade/candidate record in backtest AND live runners. Without it, every future diagnosis repeats R4's reconstruction cost.

## F. Conviction synthesis

1. **Pillar-2 over/under-filtering: INDETERMINATE (structured).** Kills move too much to call junk, under too-generous assumptions to call gold. The magnitude tiers (0.5/1.0) do not separate outcomes; FVG-absence does the killing (91% of kills lack it). Whether FVG-absence predicts failure is untested — that is the precise next selectivity question, and it does not require touching the locked threshold to ASK (measure FVG-present-but-killed... of which only 31 exist — small-n by construction, since FVG-present usually passes).
2. **F entries: bad before entry AND bad on path.** 31% never favorable (location/timing) + sub-ATR stops (0.72×) guarantee fast bleed for the rest. Both halves need selectivity work; neither half is a stop-tweak away (stops already tight — widening is redesign + risk re-lock, not authorized).
3. **Conviction focus:** F-entry selectivity (87% of flow) → R4's kill mix says the rejected alternatives are M5/M4/M6-pattern zones failing on FVG/magnitude; the admitted flow is F-trigger continuations dying instantly. The mismatch (killed patterns ≠ traded triggers) is itself a finding: the funnel's pattern vocabulary and the trigger's pattern vocabulary barely overlap.
4. **Missing for flowchart/KB matching:** model tags + pillar paths on admitted trades (export patch above); armed-never-traded registry; FVG-context persistence at trade open (already flagged in Phase 5 notes); M8 HTF feed (M8 unmeasurable until provisioned).

---

*End of R4 report. Next: R5 diagnosis document + Lead Architect gates (separate prompt). No threshold changes, no code changes, no edge claimed.*
