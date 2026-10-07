# TRACK R3 — BASELINE ATTRIBUTION + RULE IDENTITY REPORT

**Status:** COMPLETE 2026-09-19 · offline diagnosis only, no strategy-code changes, no locked-constant edits.
**Script:** `06_RESEARCH/scripts/r3_attribution.py` (imports the data loader only).
**Inputs:** `results/phase_c_baseline_run1/merged/trades.csv` (761) + R1 `trades_mfe_mae.csv` + R2 `r2_summary.json` (no-BE control only) + canonical parquet (session/ATR context).
**Outputs:** `results/r3_attribution/trades_identity.csv` (761 rows) + `summary_by_trigger.csv` + `summary_by_failure_mode.csv` + `r3_summary.json`.
**Identity recovery:** trigger/poi_id/route_id/direction/prices/bars/timestamps from the export; session from entry hour (locked §2); year + Wilder ATR(14) at entry + stop/ATR ratio computed from the canonical series. **Model tags are NOT on any artifact** (`report.json` by_poi carries P/L only) → recorded as `unknown`, never invented.
**Reconciliation:** exit mix 567+187+7=761 ✓ (754 stop_loss kind ✓); net sums to −47.81 ✓; year nets match Phase C §6.1 exactly ✓; sessions Asia 326 / London 203 / NY 232 / off-session 0 ✓ (gating fidelity signal).

---

## 1. Exit attribution (every trade classified)

| Exit class | n | % book | Net raw | Note |
|------------|---|--------|---------|------|
| full_sl (full stop loss) | 567 | 74.5% | −72.88 | The book's loss engine |
| be_scratch (BE-protected positive) | 187 | 24.6% | +2.14 (avg +0.011/trade) | BE works as designed — crumbs by design |
| friday_artifact (Friday EOD) | 7 | 0.9% | **+22.93** | Calendar luck, see below |

- BE contributes +2.14 total: it fires correctly but locks dust (buffer 0.10×ATR).
- **The 7 Friday closes (+22.93, median hold 1480 bars) offset nearly half the book's loss.** These are multi-day B/F holds flattened by the calendar after huge favorable runs (2 B, 4 F, 1 C — including the lone C trade +0.089). Without them the book reads −70.75, not −47.81. Friday flattening is the book's largest single positive contributor — pure regime/calendar artifact, not edge.

## 2. Trigger-family decomposition

| Fam | n | WR | Net | PF | Med hold | Med MFE_R / MAE_R | Never-fav | Dominant death |
|-----|---|-----|------|------|----------|-------------------|-----------|----------------|
| F | 659 | 22.9% | −32.76 | 0.397 | 1 bar | 0.55 / 1.75 | 31.3% | no_follow_through |
| B | 70 | 50.0% | −12.17 | 0.212 | 14 bars | 6.12 / 1.86 | 20.0% | be_scratch (33) ≈ full_sl (35) |
| A | 29 | 24.1% | −2.77 | 0.044 | 4 bars | 0.54 / 1.42 | 10.3% | no_follow_through |
| C/E | 1/2 | — | — | — | — | — | — | counts only |

- F median stop is **0.72×ATR** (sub-ATR stops); B 0.92×ATR (wide spread 0.10–2.98); A 1.33×ATR. F's tight stops + 1.75R median adverse explain the bleed rate.
- B's 50% WR is 33 BE-scratches + 2 Friday closes vs 35 full stops — average loss dwarfs average win 4.7×. Directionally right half the time, paid in crumbs, charged full stops.
- Removing F makes things WORSE (no-F PF 0.188 < F-only 0.397 < book 0.344... note book PF sits between: F-only is the best-expectancy subset, still deeply negative).

## 3. Rule / pattern identity mapping

- **Which triggers actually trade:** F (86.6%), B (9.2%), A (3.8%), E (0.3%), C (0.1%), D (0%). Three of six triggers are statistically absent.
- **One pattern family dominates:** Trigger F continuation on M1 is the book. The "8-model modular confluence" system, as executed, is a single-pattern system with a slow B tail.
- **Losses concentrate:** F full-SL = 508 of 567 full stops (89.6%). Every failure mode's top trigger is F.
- **Model tags: unknown** (not exported — flagged as an instrumentation gap for any future run: persist `model_tags` onto the trade record).
- **Sessions:** entries gated correctly (0 off-session); no session dominates counts enough to matter (Asia 326 / London 203 / NY 232).

## 4. Failure-mode taxonomy (mechanical, mutually exclusive)

| Mode (rule) | n | % book | Net raw | Med hold | Reading |
|-------------|---|--------|---------|----------|---------|
| friday_artifact (Friday close) | 7 | 0.9% | +22.93 | 1480 | calendar luck, not signal |
| be_scratch (pnl>0, SL kind) | 187 | 24.6% | +2.14 | 8 | system working, payoff trivial |
| instant_stop (never favorable) | 223 | 29.3% | −33.65 | 0 | stopped with zero favor — location/timing |
| no_follow_through (0<MFE_R<1) | 253 | 33.2% | −33.22 | 2 | some favor, never 1R — selection |
| gave_back (MFE_R≥1, lost) | 91 | 12.0% | −6.01 | 1 | reached 1R+, still lost — conversion |

- 62.5% of trades (instant + no-follow) produce ~140% of net loss. The book dies at entry/selection, not at conversion: only 12% even reach 1R before losing.

## 5. Ablations (stored book only, no re-runs)

| Book | n | WR | Net raw | PF |
|------|---|-----|---------|-----|
| Full baseline (BE on) | 761 | 25.5% | −47.81 | 0.344 |
| F-only | 659 | 22.9% | −32.76 | 0.397 |
| no-F | 102 | 42.2% | −15.06 | 0.188 |
| B-only | 70 | 50.0% | −12.17 | 0.212 |
| A-only | 29 | 24.1% | −2.77 | 0.044 |
| no-BE replay (R2 TP_INF) | 761 | 0.0% | −75.08 | 0.0 |

- No subset is viable; F-only is the least-bad. BE contributes +27.27 raw vs no-BE — the system's only positive-expectancy component is the scratch mechanism itself.

---

## Interpretation (plain language)

1. **Exact identities producing the book:** Trigger F continuation entries on M1 (86.6%), mostly Asia session, sub-ATR stops (0.72×), dying in 1–2 bars without reaching 1R — plus a 70-trade B tail that is directionally fair (50% WR) but paid in BE crumbs against full stops, plus statistical ghosts (C/E/D).
2. **Most losses come from:** 476 F/B/A entries that never reach 1R favorable (instant_stop + no_follow_through = −66.87 raw), partially masked by +22.93 of Friday-flatten luck and +2.14 of BE dust.
3. **Yes — mostly one live pattern.** The flowchart's breadth is theoretical: as executed, this is Trigger F + stop-bleed with a B sidecar. C/D/E never meaningfully fire (D structurally dead on volume-less data).
4. **Conviction focus, in order:** (a) **F entry selectivity** — 31% never favorable with sub-ATR stops is a location/timing defect, and F is 87% of flow, so this is the whole game; R4 (Pillar-2 kill-sample on F routes) is the sharpest next probe. (b) **Stop placement/timing fact base** — stop/ATR ratios now exist per trade; any future stop work starts from §4 tables, not opinions. (c) **B stop-timing** — B finds direction but dies on tight-stop tagging (R2: SL-first 70/70); needs entry-timing or stop-structure work, explicitly NOT a TP track. (d) **Missing patterns** — C/E/D and M8order no verdicts; M8 needs HTF provisioning before it can even be measured. **Not in focus:** exit-model work (R2 killed it), TP ranking (moot), BE tuning (+2.14 total cannot move the needle).

---

*End of R3 report. R4 (Pillar-2 kill-sample on F routes) is justified as the next probe — separate prompt. No locked-constant edits, no strategy-code changes made or proposed.*
