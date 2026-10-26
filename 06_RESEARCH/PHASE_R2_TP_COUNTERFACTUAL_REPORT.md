# TRACK R2 — SYNTHETIC TP COUNTERFACTUAL REPORT

**Status:** COMPLETE 2026-09-19 · offline diagnosis only, no strategy-code changes, no locked-constant edits.
**Script:** `06_RESEARCH/scripts/r2_tp_counterfactual.py` (imports the data loader only).
**Inputs:** frozen entries + ORIGINAL stops from `06_RESEARCH/results/phase_c_baseline_run1/merged/trades.csv` (761) + canonical `07_DATA/XAUUSD_M1.parquet` via `load_ohlcv_parquet`.
**Outputs:** `06_RESEARCH/results/r2_tp_counterfactual/trades_r2.csv` (3044 rows = 761 × 4 arms) + `summary_by_policy.csv` + `per_trigger_policy.csv` + `r2_summary.json`.
**Resolution (frozen SL, no BE, no FVG exits):** per bar, SL touch → loss; TP touch → win; both → SL wins (frozen tie-break). TP evaluated from entry_bar+1 (conservative fill-ordering — mirrors fill-before-entry); SL from entry_bar. Friday-EOD trades unresolved by window end close at baseline outcome (never needed — all 761 resolved via touch in every arm). Non-Friday unresolved → OPEN/excluded (0 in every arm).

---

## 1. Per-arm results (resolved = 761/761, open_excluded = 0, all arms)

| Arm | TP wins | SL losses | WR | Net raw | Net ccy | PF | MaxDD ccy |
|-----|---------|-----------|-----|---------|---------|-----|-----------|
| BE-only baseline (cited, Phase C) | 187 micro* | 567 + 7 Fri | 25.49% | −47.81 | −478.15 | **0.344** | 49.15 raw |
| TP_1.5R (fixed SL, no BE) | 11 | 750 | 1.45% | −73.69 | −736.91 | **0.011** | 736.91 |
| TP_2R (fixed SL, no BE) | 4 | 757 | 0.53% | −74.72 | −747.23 | **0.0032** | 747.23 |
| TP_3R (fixed SL, no BE) | 1 | 760 | 0.13% | −75.02 | −750.22 | **0.0006** | 750.22 |
| TP_INF (no-TP/no-BE control) | 0 | 761 | 0.0% | −75.08 | −750.82 | 0.0 | 750.82 |

\* Baseline "wins" are 187 BE-locked micro-closes + 7 Friday closes, 0 TP.

- Higher TP is strictly worse. The best fixed-TP arm (1.5R, PF 0.011) sits 30× below the BE-only baseline (0.344).
- Two-effect split: dropping BE costs −27.27 raw (TP_INF −75.08 vs baseline −47.81); adding 1.5R TP recovers only +1.39 raw (11 wins). Arms differ from baseline by both changes — reported separately, not conflated.

## 2. Per-trigger splits (mandatory; C n=1 / E n=2 — counts only)

| Trigger | 1.5R wins / PF | 2R wins / PF | 3R wins / PF |
|---------|----------------|--------------|--------------|
| F (659) | 11 / 0.015 | 4 / 0.0043 | 1 / 0.0008 |
| B (70) | 0 / 0.0 | 0 / 0.0 | 0 / 0.0 |
| A (29) | 0 / 0.0 | 0 / 0.0 | 0 / 0.0 |
| C (1) | 0 | 0 | 0 |
| E (2) | 0 | 0 | 0 |

All 16 TP wins across all arms are Trigger F. A/B/C/E: zero at every level.

## 3. Mechanism: TOUCH ≠ REACHABLE (the central finding)

At 1.5R, 232 trades touch the TP level somewhere in-window (exactly R1's ≥1.5R count — verified), but only 11 win. The 221-touch gap decomposes as:

| Fate of TP touch (1.5R) | Count | Share of touches |
|-------------------------|-------|------------------|
| Entry-bar-only (excluded by conservative fill-ordering) | 25 | 10.8% |
| Post-entry but SL touched same bar or earlier (SL-first kills) | 196 | 84.5% |
| Strict win (TP strictly before any SL touch) | 11 | 4.7% |

- **Chronology dominates, not the entry-bar rule:** 84.5% of touches die to SL-first ordering; only 10.8% to the entry-bar exclusion.
- **B (70/70 SL-first at every level):** ~35 B trades touch ≥1.5R post-entry, all after-or-with SL tags on tight stops. **R1 framing corrected:** R1's B median 6.12R is excursion-within-BE-protected-lifetime (baseline survived via BE latch while wandering), NOT reachable-before-stop. Under fixed stops B reaches 1.5R-first in 0/70.
- **F:** 639/659 SL-first at 1.5R; median bars_to_mfe 0 means much F excursion sits on the entry bar, but even post-entry touches (207−25=182 non-entry-only… of which 11 win) overwhelmingly die to SL-first.

## 4. Gate update (ACTIVE_TODO §6)

- **Gate 6.1 (book-wide exit fix): NOT CLEARED — conclusively.** No TP level helps; higher R is monotonically worse; best arm trails the BE baseline 30×. There is no fixed-R exit policy worth promoting.
- **Gate 6.3 (family-level): REFINED, direction changed.** B is NOT an exit-model opportunity under fixed stops — it is a stop-placement/timing problem (tight SL tagged before excursion develops in 70/70). That is entry-design territory, and no redesign is authorized by this study.
- **Gate 6.2 (entry-side primary): CONFIRMED book-wide.** 750/761 trades (98.6%) are stopped before 1.5R. The binding constraint is entries surviving to targets, not targets existing.
- **R4 (Pillar-2 kill-sample for F-routes): now the highest-value open item** — F entries die to SL-first; whether Pillar 2 admits weak displacements is the next empirical question.

## 5. R3 recommendation (rescoped)

"Expectancy under best exit policy" is moot — no policy beats the BE baseline. R3 is still justified but RESCOPED: ablation on the BASELINE (BE-inclusive) book — F-only / no-F / B-only expectancy + BE-attribution per family (how much of each family's baseline comes from BE micro-wins vs Friday closes). Purpose: test whether any subset merits a future exit-model track, not to rank TP policies.

---

*End of R2 report. No locked-constant edits, no strategy-code changes, no TP implementation proposed. Next: rescoped R3 ablation (separate prompt).*
