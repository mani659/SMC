# POST-DEDUP EDGE / OUTCOME DIAGNOSTIC — 2025-06-01 → 2025-11-30

**DIAGNOSTIC — NOT EDGE / NOT LIVE VALIDATION.**

Authority: Architect 2026-10-20 (after commit `b5e8c53`). Prior: LEG 5b armed 30→606; LEG 6 `NEW_ARMS_SIMILAR_TO_LEGACY`; pre-dedup edge never measured (n≈3); post-dedup book n≈58 fills.
Mode: **MEASUREMENT ONLY** — `LOGIC_CHANGED: NO` under `04_SRC/smc/**`; `locked_constants.py` diff **EMPTY** (verified); no optimization, no trigger kills by PnL, no expectancy/Sharpe/"edge proven" language anywhere.

---

## 0. Data provenance (reuse, no re-capture)

- Book: `06_RESEARCH/results/zone_dedup_lifecycle/run1/_funnel_capture/trades.csv` — **58 closed trades**, gitignored artifact from the frozen 6m lifecycle composition (LEG 5b double run).
- Byte-stability: md5 `476884250d607ac1b1e3806eadceba0c` **identical across run1, run2 and the LEG 6 re-capture** (`06_RESEARCH/results/post_dedup_new_arm_quality/_funnel_capture/trades.csv`) → **analyze-only, no re-capture performed, nothing expanded**. (12m expansion would be a follow-on Architect call.)
- Script: `06_RESEARCH/scripts/post_dedup_edge_diagnostic.py` — imports the data loader + M5 resampler only (same read-only method family as `r1_mfe_mae_study.py`); writes `06_RESEARCH/results/post_dedup_edge_diagnostic/{summary.json,trades_enriched.csv}`.

## 1. Pre-registration (committed in the script before results were read)

- Population: all closed trades in the lifecycle book (n recorded exactly: **58**).
- Metrics pre-registered: win rate **by close_kind** (not a vague win flag); exit mix; net PnL+PF labelled DIAGNOSTIC ONLY; breakdowns by trigger / tp_source / direction; honest MFE/MAE in R from stored bars; hypothesis buckets **reused from the book's own path-derived `post_exit_class`** (defining lineage: `hypothesis_outcome_study.classify` via `f_selectivity_post_exit.py`); contrast vs pre-lifecycle book **sample-size only**.
- Interpretation mapping coded up front: n<20 → `BOOK_TOO_SMALL`; all risk distances missing → `DATA_GAP_BLOCKING`; else lossy-negative → `BOOK_STILL_LOSSY_DIAGNOSTIC` else `BOOK_MIXED_PATHS_NO_CLAIM`. No mapping branch can emit edge/scale language.

## 2. Book-level counts + distributions

| Item | Value |
|---|---|
| n closed trades | **58** |
| close_kind | take_profit **30** · stop_loss **28** · be_scratch **0** · friday **0** · other **0** |
| Win rate by close_kind (share pnl>0) | TP bucket 30/30 = 1.00 (by construction) · SL bucket **9/28 = 0.321** (BE-plus/trailing stops close positive) |
| Win rate overall (pnl>0) | **39/58 = 0.672** |
| Direction | long 42 · short 16 |
| bars_held | see `trades_enriched.csv` (entries→exits span M5 bars inclusive) |

**Honesty note:** `close_kind=stop_loss` ≠ loss — 9 of the 28 stop closes are positive (profit trailed into the stop / BE-plus). Mixed by close_kind, by pnl sign — both recorded.

### Net PnL + PF (DIAGNOSTIC ONLY — units are book-internal: `pnl = price_diff × volume`, sanitized contract multiplier 1.0, consistent across the book; not converted to strategy-account USD)

- Sum PnL = sum PnL_net = **+2.4501** (costs all 0.0 in the sanitized book)
- Gross win **+14.1651** · gross loss **−11.7150** · **PF = 1.2091** (DIAGNOSTIC ONLY)
- Per-trade PnL: see `trades_enriched.csv`; no expectancy, no Sharpe, no annualization, no significance claim.

## 3. Trigger mix (and pnl-by-trigger, descriptive)

| Trigger | n | (sum pnl, diag units) |
|---|---|---|
| F | **41** | −3.0123 |
| B | 8 | +1.6674 |
| A | 4 | +1.1059 |
| E | 3 | +2.2578 |
| C | 2 | +0.4312 |

F dominates participation (~71%, same shape as the LEG 6 cohort mix) and is the only negative total; A/B/C/E are small-n (≤8). **No kill/no rank decision drawn here** — explicitly banned; the table is descriptive only.

F timing labels (book column): structured_pullback 27 · mid_move 11 · late_chase 3 · NA 17.

## 4. TP source mix (and pnl, descriptive)

| tp_source | n | sum pnl |
|---|---|---|
| structural_swing | **43** | +1.1325 |
| atr_fallback | **15** | +1.3176 |

(`none` 0. Detection-TF breakdown: **not available in this book** — no detection-TF column is stored on filled trades; adding it would require a logging-only re-capture, which was NOT triggered since every core pre-registered metric was computable.)

## 5. Honest MFE / MAE in R — all 58 trades covered (risk_dist missing = 0)

Method: window = M5 resampled bars with `entry_at <= ts <= exit_at` inclusive (rebuilt from `07_DATA/XAUUSD_M1.parquet` via the composition's own loader, read-only); risk distance `= |entry_price − original_sl|`; signed excursions in R. Zero-window trades: **0**; `DATA_GAP = 0`.

| Stat | MFE_R ("max favorable; negative ⇒ trade never went favorable") | MAE_R (adverse before final close) |
|---|---|---|
| median | **0.502** | **0.433** |
| mean | 0.629 | 0.669 |
| min | −0.445 (4 trades never favorable) | 0.000 |
| max | 2.533 | 2.826 |
| p25 / p75 | 0.104 / 0.937 | 0.151 / 1.082 |
| count MFE_R < 0 | 4 | — |
| count MAE_R > 1.0 | — | **19 of 58** |

Read (descriptive only): median winners (TP-reached) gave back nothing special; 19/58 trades endured a >1R adverse excursion inside their window — deep-path trades exist in both TP and SL buckets; we do not act on it here (no exit-strategy tuning — banned).

## 6. Hypothesis-style path buckets (book's own `post_exit_class`, reused byte-stable)

| Bucket | n |
|---|---|
| TP_REACHED | **30** |
| SL_THEN_TP_PATH | **14** |
| REJECTED | 10 |
| MFE_ONLY | 4 |
| DATA_GAP | **0** |

Semantics inherited from `hypothesis_outcome_study.classify` (REJECTED ≈ never seriously approached; SL_THEN_TP_PATH ≈ hit stop-territory excursion then still reached TP — the loan-extreme paths). Coherence check: TP_REACHED (30) == close_kind take_profit (30) — consistent.

## 7. Contrast vs pre-lifecycle 6m book — SAMPLE-SIZE ONLY

| Book | n fills |
|---|---|
| Pre-lifecycle (LEG ≤4 frozen 6m) | **3** |
| Post-lifecycle (this book) | **58** |

No pnl comparison drawn at n=3 (statistically meaningless both ways; pre-lifecycle book not re-opened). This contradicts nothing in LEG 6 (`NEW_ARMS_SIMILAR_TO_LEGACY` was a per-cohort conversion result, not an edge statement).

## 8. Interpretation (exactly one pre-registered label)

**`BOOK_MIXED_PATHS_NO_CLAIM`**

Basis (pre-registered mapping, applied mechanically): n=58 ≥ 20; risk distances present for all; map pnl<0→STILL_LOSSY else→MIXED — the booked net is +2.4501 (roughly balanced grosses vs losses, PF 1.21 diagnostic), with exit mix 30 TP / 28 SL and 19/58 >1R adverse paths — the book contains genuine two-sided path variety. Neither the positive total nor the label asserts edge, candidacy, readiness, or quality: this leg's only sanctioned output is that the machine now *produces a describable book* where the pre-lifecycle book had n=3, and its path anatomy is now measurable. **No live validation, no scale signal, no expectancy claim.**

---

## Return block

```
EDGE_DIAG_STATUS: PASS
WINDOW: 2025-06-01 -> 2025-11-30
N_TRADES: 58
EXIT_MIX: {take_profit: 30, stop_loss: 28, be_scratch: 0, friday: 0, other: 0}
TRIGGER_MIX: {F: 41, B: 8, A: 4, E: 3, C: 2}
TP_SOURCE_MIX: {structural_swing: 43, atr_fallback: 15}
NET_PL_DIAGNOSTIC: +2.4501 (book-internal units; costs sanitized 0)
PROFIT_FACTOR_DIAGNOSTIC: 1.2091
HONEST_MEDIAN_MFE_R: 0.502
HONEST_MEDIAN_MAE_R: 0.433
HYPOTHESIS_COUNTS: {TP_REACHED: 30, SL_THEN_TP_PATH: 14, REJECTED: 10, MFE_ONLY: 4, DATA_GAP: 0}
INTERPRETATION: BOOK_MIXED_PATHS_NO_CLAIM
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
SUITE: NOT_RUN
REPORT_PATH: 06_RESEARCH/POST_DEDUP_EDGE_DIAGNOSTIC_REPORT.md
NEXT_READY: Architect review of edge diagnostic
```

**NEXT_READY (detail):** Architect review of the diagnostic — optionally (a) add a detection-TF column via one logging-only re-capture if TF-level anatomy is wanted, (b) 12m expansion as a follow-on Architect call, or (c) close this measurement leg and return to the live-promotion residual ruling.
