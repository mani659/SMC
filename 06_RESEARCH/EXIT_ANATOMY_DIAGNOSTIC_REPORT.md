# EXIT ANATOMY DIAGNOSTIC — Windows A + B

**DIAGNOSTIC — NOT EDGE / NOT LIVE VALIDATION.**

Authority: Architect 2026-10-20 (after `PAIR_STABILITY: UNSTABLE_SHAPE`).
Books: Window A `2025-06-01 → 2025-11-30` n=58 · Window B `2024-12-01 → 2025-05-31` n=44.
Mode: **OBSERVATION ONLY** — `LOGIC_CHANGED: NO` under `04_SRC/smc/**`; `locked_constants.py` diff **EMPTY**; no TP/SL/BE/trail parameter search; no exit "fix" proposed or implemented; no expectancy/scale language; suite NOT_RUN (nothing shipped changed).

**Analyze-only.** No capture was run: both books already exist and the enriched copies were regenerated and cross-checked (§1).

---

## 0. Question

Window B ends positions on stops far more often than Window A (28/44 vs 28/58) and its dominant path bucket is `SL_THEN_TP_PATH`. **How** do these positions actually end — and does "stop-heavy" mean "stopped out"?

---

## 1. Provenance + integrity (before any aggregate is read)

| check | A | B |
|---|---|---|
| book | `zone_dedup_lifecycle/run1/_funnel_capture/trades.csv` | `post_dedup_edge_stability/run1/_funnel_capture/trades.csv` |
| n | 58 | 44 |
| M5 series rebuilt (composition loader, read-only) | 35,725 bars | 34,919 bars |
| missing series / zero-bar windows (fail-loud) | 0 | 0 |
| recomputed MFE/MAE vs stored `trades_enriched*.csv` | 58/58 exact, **0 mismatches** | 44/44 exact, **0 mismatches** |
| tp-touch walk vs frozen honest path (max favourable price) | **0 mismatches** | **0 mismatches** |

Both books are chronologically coherent: among stop exits, **0 of 28** in each window had their TP touched on any bar strictly before the exit bar (`SL_WHILE_TP_VALID = 0.0` both sides; 2 same-bar touches in B are excluded by design because intrabar order is unknowable). This is a *coherence* result — with a resting TP, a pre-exit TP touch could not exist — **not** a "money left on the table" claim.

---

## 2. Exit classes (pre-registered definition)

`HARD_SL` = `stop_loss` with pnl ≤ 0 · `SOFT_SL_OR_BE` = `stop_loss` with pnl > 0 (trailing / BE-style end) · `TARGET_TP` = `take_profit` · `OTHER`.

| | A (n=58) | B (n=44) |
|---|---|---|
| `TARGET_TP` | **30 (0.517)** | 16 (0.364) |
| `SOFT_SL_OR_BE` | 9 (0.155) | **20 (0.455)** |
| `HARD_SL` | 19 (0.328) | 8 (0.182) |
| `OTHER` | 0 | 0 |
| stop-exit share (soft + hard) | 0.483 | **0.636** |
| TP-exit share | 0.517 | 0.364 |

**The headline correction to the pair verdict's framing:** B is stop-dominated but **not** loss-dominated. 20 of its 28 stop exits closed positive; only 8 of 44 trades ended in a losing stop, versus 19 of 58 in A. "Stop-heavy" in B means *trailing exits*, not damage.

---

## 3. Medians by exit class (hold, run-up, target geometry)

| window / class | n | median hold (bars) | median MFE_R | median TP_DISTANCE_R | median MFE ÷ TP distance | Σpnl (diagnostic) |
|---|---|---|---|---|---|---|
| A · `HARD_SL` | 19 | 2 | 0.220 | 1.245 | 0.114 | −11.715 |
| A · `SOFT_SL_OR_BE` | 9 | **36** | 0.942 | 1.674 | 0.527 | +0.392 |
| A · `TARGET_TP` | 30 | **1** | 0.568 | **0.510** | 1.329 | +13.773 |
| B · `HARD_SL` | 8 | 4 | **0.019** | 1.000 | 0.031 | −4.029 |
| B · `SOFT_SL_OR_BE` | 20 | 5 | **0.881** | 1.348 | **0.705** | +0.850 |
| B · `TARGET_TP` | 16 | 6 | 0.680 | **0.529** | 1.340 | +3.993 |

Reading (descriptive): in both books a TP exit is a trade whose target sat **inside ~0.5R** and filled quickly; a hard stop is a trade that never moved (median run-up 0.02R in B, 0.22R in A); a soft stop is a trade that ran ~0.9R, did not reach a 1.3–1.7R target, and was closed by the trail. Σpnl per class is book-internal accounting, DIAGNOSTIC ONLY.

---

## 4. Target-distance cross-tab (TP_DISTANCE_R = |tp−entry| ÷ |entry−original_sl|)

Pre-registered metric 8, tabulated (post-hoc *grouping* of a pre-registered quantity — disclosed as such, not a new rule):

| TP distance bucket | A n / TP / soft / hard | B n / TP / soft / hard |
|---|---|---|
| < 0.75R | 31 / **21** / 3 / 7 | 14 / **10** / 3 / 1 |
| 0.75 – 1.25R | 10 / 6 / 1 / 3 | 14 / 4 / **6** / 4 |
| > 1.25R | 17 / 3 / 5 / 9 | 16 / 2 / **11** / 3 |

Median `TP_DISTANCE_R`: **A 0.643 · B 1.000**. Over half of A's book (31/58) sat inside 0.75R of target; only 14/44 of B's did. Within the same bucket the TP-hit rate is broadly similar (<0.75R: 0.677 vs 0.714; >1.25R: 0.176 vs 0.125); the difference is **where the trades landed**, plus the 0.75–1.25R bucket (6/10 TP in A vs 4/14 in B, n small).

---

## 5. Side-by-side aggregates (required table)

| Metric | A | B |
|---|---|---|
| n | 58 | 44 |
| `EXIT_CLASS` | TP 30 · SOFT 9 · HARD 19 | TP 16 · SOFT 20 · HARD 8 |
| `SL_WHILE_TP_VALID` share (of stop exits) | **0.000** (0/28) | **0.000** (0/28) |
| `MFE_VS_TP` YES share (all trades) | **0.569** (33/58) | **0.523** (23/44) |
| `MFE_VS_TP` YES share (TP exits) | 1.000 (30/30) | 1.000 (16/16) |
| `MFE_VS_TP` YES among non-TP trades (derived) | 3/28 = 0.107 | 7/28 = 0.250 |
| median hold | 2 bars / 0.167 h | **4.5 bars / 0.375 h** |
| median MFE_R · MAE_R | 0.502 · 0.433 | 0.812 · 0.684 |
| median `TP_DISTANCE_R` | **0.643** | **1.000** |

---

## 6. By tp_source

| window · source | n | exit classes | median hold | median MFE_R | median TP_DISTANCE_R | `SL_WHILE_TP_VALID` YES |
|---|---|---|---|---|---|---|
| A · structural_swing | 43 | TP 27 · HARD 12 · SOFT 4 | 1 | 0.487 | 0.508 | 0 |
| A · atr_fallback | 15 | TP 3 · HARD 7 · SOFT 5 | 8 | 0.942 | 2.175 | 0 |
| B · structural_swing | 33 | TP 12 · SOFT 15 · HARD 6 | 2 | 0.779 | 1.000 | 0 |
| B · atr_fallback | 11 | TP 4 · SOFT 5 · HARD 2 | 14 | 1.200 | 1.701 | 0 |

Both books behave the same way *within* a source: structural targets are the near ones, ATR-fallback targets are the far ones (median 2.18R / 1.70R) and fill least often. Window B's structural targets simply sat further out than Window A's (1.00R vs 0.51R).

---

## 7. Interpretation (one label per window, pre-registered rule)

- **Window B — `EXIT_DOMINATED_BY_SOFT_STOPS`.** Stop exits hold 0.636 of the book (≥ 0.60), and within that group soft (positive) stops outnumber hard stops 20 : 8. The label applies the 0.60 dominance line symmetrically; the underlying shares are printed above so the threshold never has to be trusted.
- **Window A — `EXIT_MIXED_TARGET_AND_STOP`.** No class reaches 0.60 (TP 0.517, stops 0.483).
- **Disagreement: `true`.** Recorded in `summary.json` (`label_disagreement`) and not smoothed over. The return block carries B's label because B is the window whose shape motivated the leg; A's label is carried beside it.

---

## 8. Mechanism hypothesis (non-binding — one sentence, no rule change)

**B's stop-heavy shape is a target-geometry effect, not a stop-behaviour effect: B's structural targets sat a median 1.00R away versus 0.51R in A, so positions that ran ~0.88R stalled short of target and were closed by their trail, whereas A's sub-0.75R targets were reachable within one to two bars.**

Supporting (descriptive, all from pre-registered metrics): median `TP_DISTANCE_R` 0.643 → 1.000; median hold 2 → 4.5 bars; soft-stop median run-up 0.942R (A) and 0.881R (B) against targets at 1.674R and 1.348R; TP-hit share 0.517 → 0.364 while `MFE_VS_TP` (reach ≥90% of *own* target) barely moved (0.569 → 0.523).

This is offered as an explanation of the observed shape, **not** as an endorsement, a defect report, or a change proposal. No parameter was searched and none is recommended.

---

## 9. Limitations

1. **n = 58 / 44.** Every share above is descriptive; no significance claim, no test, no confidence interval.
2. **Bar-level resolution.** Intrabar ordering is unknowable from M5 bars: same-bar TP touches (2 trades, all in B) are excluded from `SL_WHILE_TP_VALID` and counted separately; `HARD_SL` vs `SOFT_SL_OR_BE` uses the book's realised pnl, not path reconstruction.
3. **TP source is the book's `tp` column**, already reflected in `tp_source`; no independent re-derivation of structural targets was attempted (that would be a different study).
4. **Costs sanitized to 0** in both books; Σpnl-per-class is internal accounting, not a trading result.
5. **No detection-TF anatomy** (column still not stored on fills).
6. **`SL_WHILE_TP_VALID = 0` is a coherence finding**, not evidence of unrealised profit — a resting TP would have filled.
7. **The 0.75R bucket boundaries in §4 are a post-hoc grouping** of a pre-registered quantity, disclosed as such; the pre-registered label rule itself never uses them.

---

## Return block

```
EXIT_ANATOMY_STATUS: PASS
N_A: 58  N_B: 44
EXIT_CLASS_A: {TARGET_TP: 30, SOFT_SL_OR_BE: 9, HARD_SL: 19, OTHER: 0}
EXIT_CLASS_B: {TARGET_TP: 16, SOFT_SL_OR_BE: 20, HARD_SL: 8, OTHER: 0}
SL_WHILE_TP_VALID_SHARE_A: 0.000  SL_WHILE_TP_VALID_SHARE_B: 0.000   (brief shorthand SHARE_B = 0.000)
MFE_VS_TP_YES_SHARE_A: 0.569  MFE_VS_TP_YES_SHARE_B: 0.523
MEDIAN_HOLD_BARS_A: 2.0  MEDIAN_HOLD_BARS_B: 4.5
MEDIAN_TP_DISTANCE_R_A: 0.643  MEDIAN_TP_DISTANCE_R_B: 1.000
INTERPRETATION: EXIT_DOMINATED_BY_SOFT_STOPS   (Window B; Window A: EXIT_MIXED_TARGET_AND_STOP — disagreement recorded)
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
SUITE: NOT_RUN
REPORT_PATH: 06_RESEARCH/EXIT_ANATOMY_DIAGNOSTIC_REPORT.md
NEXT_READY: Architect review of exit anatomy
```

**Artefacts:** `06_RESEARCH/results/exit_anatomy/{summary.json,trades_exit_anatomy.csv}` (102 per-trade rows: class, R_stop, R_tp, TP_DISTANCE_R, MFE/MAE_R, MFE_VS_TP, SL_WHILE_TP_VALID, hold). Script: `06_RESEARCH/scripts/exit_anatomy_diagnostic.py` (analyze-only, re-runnable).

**NEXT_READY (detail):** the anatomy is fully described; whether the target-geometry effect warrants any further leg (e.g. a TP-placement *measurement* across more windows) is an Architect call. No exit rule, threshold or product line was touched, and none is proposed.
