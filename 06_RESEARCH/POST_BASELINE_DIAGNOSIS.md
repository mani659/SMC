# POST-BASELINE DIAGNOSIS MEMO (Track R closeout)

**Status:** FINAL 2026-09-19 · closes Track R measurement (R1/R2/R3/R4 all PASS).
**Evidence base:** Phase C baseline (761 trades, dual-run byte-identical) + R1 MFE/MAE + R2 fixed-TP counterfactuals + R3 attribution/identity + R4 entry-selectivity (335-kill full population). Reports: `PHASE_C_BASELINE_REPORT.md`, `PHASE_R1_MFE_MAE_REPORT.md`, `PHASE_R2_TP_COUNTERFACTUAL_REPORT.md`, `PHASE_R3_BASELINE_ATTRIBUTION.md`, `PHASE_R4_ENTRY_SELECTIVITY_REPORT.md`.
**Authority:** binding interpretation for what comes next; any locked change still needs a dated Lead Architect ruling in `POST_V1_PLAN_OF_ACTION.md`.

---

## 1. Executive diagnosis (plain language)

The frozen V1 system loses because its entries die before targets, not because targets are missing. Across 761 trades: median favorable excursion 0.55R against 1.73R adverse; 62.5% never reach 1R; fixed take-profits at 1.5R/2R/3R convert 11/4/1 trades and trail the BE-only baseline 30×. The book is one live pattern — Trigger F continuation on M1 with sub-ATR stops (87% of flow) — plus a directionally-fair B tail paid in BE crumbs. The validation funnel kills mostly on missing FVG (91% of Pillar-2 kills lack it), yet killed zones move too much to call junk and admitted entries die too fast to call the funnel selective. Two artifacts flatter the headline number: Friday-flatten luck (+22.93 of −47.81 net) and the missing exit debate itself (settled: exits are not the problem).

## 2. Proved / rejected

| # | Statement | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | Implementation executes the frozen spec faithfully | PROVED | Dual-run byte-identity, all invariants, 580 tests |
| 2 | Frozen V1 has negative expectancy (PF 0.344, −4.78% eq) | PROVED | Phase C, 761 trades |
| 3 | Missing TP explains the loss | REJECTED | R2: best fixed-TP arm PF 0.011; higher-R monotonically worse |
| 4 | Entries reach targets but BE/scratch wastes them | REJECTED | R1: 62.5% never reach 1R; R2: 98.6% stopped before 1.5R |
| 5 | B holds harvestable excursion convertible by TP | REJECTED | R2: SL-first 70/70; R1's 6.12R median = BE-protected wandering |
| 6 | The system trades the full 8-model flowchart | REJECTED | F=86.6%; C/E/D statistically absent; M8 unmeasurable |
| 7 | Pillar-2 magnitude tiers separate good/bad candidates | REJECTED | R4: hard-fail 57.7% vs twilight 52.7–54.9% reachability |
| 8 | Friday/BE artifacts dominate the P/L shape | PROVED | Friday +22.93 (48% of gross positive); BE +2.14 dust |
| 9 | Lot-cap binds sizing (risk% inert) | PROVED | 761/761 at 0.10 lots |
| 10 | Spread gate is ATR-regime-dependent | PROVED | Ladder 52→0 at 0.35 (2023); live 0.26 passes at ATR 3.75 |

## 3. Actually-traded vs flowchart-described

| Flowchart claim | Measured reality |
|-----------------|------------------|
| 8 equal confluence models | 1 live trigger family (F) + B sidecar; admitted model tags unrecoverable |
| 6 triggers A–F | F/B/A fire; C/E ghosts (n=1/2); D structurally dead (volume-less data) |
| 5-pillar selectivity | Pillar 2 does ~75% of killing, on FVG-absence; batch pass 17% ≈ per-bar 14.8% |
| M8 HTF confluence (preferred setup) | Zero representation — no HTF feed in any runner |
| PureRunner profit management | BE scratch dispenser (+2.14 over 187 trades); exit model is stop-or-scratch |

## 4. Failure-mode hierarchy (net contribution)

1. instant_stop 223 trades / −33.65 (stopped, zero favor — location/timing)
2. no_follow_through 253 / −33.22 (some favor, never 1R — selection)
3. gave_back 91 / −6.01 (reached 1R+, still lost — conversion)
4. be_scratch 187 / +2.14 (system working, payoff trivial)
5. friday_artifact 7 / +22.93 (calendar luck masking ~half the loss)

## 5. Pillar-2 conclusion: INDETERMINATE (structured)

Kills (n=335, full population): median magnitude 0.77×ATR; 78% BOS-present, 9% FVG-present; 54%+ reach 1R under generous hypothetical stops — too much movement to call junk, under too-generous assumptions to call gold. Magnitude tiers don't discriminate; FVG-absence does the killing. Admitted F (strict reality): 31% never favorable, 0.55R median. Verdict: the funnel is neither proven selective nor proven overfiltering — **MIXED**, with the binding constraint identified as FVG-presence, whose predictive value is currently unmeasurable (only 31 FVG-present kills exist; admitted FVG rate unknown — see §6).

## 6. Identity/export gaps blocking flowchart-level conviction

1. **Model tags on admitted trades: absent.** Kills carry real tags (M5 29%, M4/M6-heavy, M3 ~absent); the traded book cannot be arraigned by pattern. Killed-vs-traded vocabulary mismatch is therefore suggestive, not conclusive.
2. **Pillar paths on admitted trades: absent.** Per-POI validation paths exist only inside runs.
3. **Armed-never-traded registry: absent.** The 5166→981 armed-to-route gap is unanalyzable.
4. **FVG context at trade open: absent** (flagged since Phase 5 notes).
5. **M8 measurability: structurally absent** (no HTF feed anywhere).

## 7. Decision gates + recommendations

| Gate | Recommendation | Rationale |
|------|----------------|-----------|
| Exit-model work (TP/trail redesign) | **NO** | R2 conclusive: no fixed-R level helps; higher-R strictly worse; best arm 30× below baseline |
| Entry-selectivity research | **YES** | F is 87% of flow and dies instantly; FVG-absence question is precise and unanswered |
| F-pattern deep dive vs KB/flowcharts | **YES** | Offline only: match R3/R4 F geometry against KB charts + locked pattern specs; killed M5/M4/M6 tags vs traded F triggers |
| Export patch (model_tags + pillar_path + disp_magnitude_atr on every trade/candidate, backtest AND live) | **YES** | Logging-only, zero logic change; prerequisite for ALL future diagnosis; without it every study repeats R4's reconstruction cost |
| R4 follow-ups | **Only the FVG-present-killed look (n=31, small-n, cheap) and only if the architect wants it** | Everything else in R4 is exhausted |

## 8. Proposed next 30 days (Phase D ops throughout, in background)

- **Week 1:** Architect rules on export patch → implement logging-only patch (+ regression tests proving byte-identical trading behavior) → suite green.
- **Week 2:** F-pattern KB/flowchart matching study (offline; R3/R4 geometry vs Knowledge Base charts vs R1 specs) → pattern-conviction memo: which F variants die fastest.
- **Week 3:** FVG-absence selectivity analysis on export-patched re-runs (short windows only — no 5y rerun until a question needs it): admitted FVG rate vs kill FVG rate, the actual predictive split.
- **Week 4:** Gate memo #2: promote/quarantine per pattern family with the §6 promotion bar (bootstrap CI, n≥100, ≥2 ATR regimes, walk-forward); or rule the concept unselective at M1 and redirect (TF scope? pattern scope? — architect's call, with evidence attached).
- Throughout: Phase D ops checklist (EA attach, drill, live bar-cycles, divergence log, 2-week stability) — zero research attention once scheduled.

## 9. Explicit non-goals (binding until ruled otherwise)

No TP implementation · no threshold tuning · no strategy redesign · no parameter fishing · no edge claims · no live money · no capital scaling · no M8 provisioning (deferred until export patch lands and F-questions resolve) · no 5-year re-runs for exploration · no treating demo P/L as idea evidence.

---

*End of Track R measurement. Next action: Lead Architect rulings on §7 gates, then §8 week 1. Phase D ops continues in parallel.*
