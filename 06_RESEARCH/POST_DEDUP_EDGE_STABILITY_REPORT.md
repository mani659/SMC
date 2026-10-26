# SECOND FROZEN WINDOW — EDGE / OUTCOME STABILITY DIAGNOSTIC

**DIAGNOSTIC — NOT EDGE / NOT LIVE VALIDATION.**

Authority: Architect 2026-10-20 (option 1 after `BOOK_MIXED_PATHS_NO_CLAIM`).
Prior leg: `06_RESEARCH/POST_DEDUP_EDGE_DIAGNOSTIC_REPORT.md` (Window A, n=58).
Mode: **MEASUREMENT ONLY** — `LOGIC_CHANGED: NO` under `04_SRC/smc/**`; `locked_constants.py` diff **EMPTY**; no threshold search, no parameter change, no F-kill, no trigger ranking, no expectancy/Sharpe/annualisation language anywhere.

This leg asks one question: does the post-ZoneDedup book keep the same qualitative *shape* on a second, earlier, contiguous 6-month window? It does **not** ask whether the book is profitable, tradable, or promotable, and no result here may be read that way.

---

## 0. Windows (locked for this leg)

| | exec window (M5) | M1 load / warm-up | role |
|---|---|---|---|
| **A** | 2025-06-01 → 2025-11-30 | 2025-05-01 | published; book **reused, not re-captured** |
| **B** | 2024-12-01 → 2025-05-31 | 2024-11-01 | **new capture this leg** |

Contiguous, non-overlapping exec ranges.

**Data coverage — no shift, no cherry-pick (fail-loud check run before the capture):**

- `07_DATA/XAUUSD_M1.parquet`: 1,768,123 M1 bars, 2021-04-12 → 2026-04-10.
- Warm-up month 2024-11: **28,572** M1 bars (2024-11-01 00:00 → 2024-11-29 19:43 = Friday close).
- Window B months (M1 bars): 2024-12 **28,764** · 2025-01 **30,197** · 2025-02 **27,441** · 2025-03 **29,092** · 2025-04 **28,948** · 2025-05 **30,087**. No empty or truncated month.
- Exec M5 series actually built: **34,919** bars, 2024-12-01 23:00 → 2025-05-30 20:55 (Sunday open → Friday close, i.e. market hours, not a gap).
- Fills in the B book: 2024-12-02 05:45 → 2025-05-21 00:10 — strictly inside the window.

No alternative window was needed; nothing was moved to chase a "better" PF window.

---

## 1. Composition + provenance (imported, not forked)

- Capture drives the **same** post–ZoneDedup-lifecycle product path as LEG 5b/6: `phase3_structure_funnel.run` **imported**, with the shipped lifecycle dedup live (`MultiTFProductRuntime` product seam at new-H1-close cadence → `PipelineEngine` arm → `PipelineAdapter` scans → `BacktestRunner` risk/placement).
- Script: `06_RESEARCH/scripts/post_dedup_edge_stability.py` — `--run-id run1|run2` captures, `--analyze-only` re-derives every table from the stored books. Metric helpers are the prior leg's own (`load_book`, `build_m5_index`, `mfe_mae_r`) reused through one code path for **both** windows.
- Single-run funnel (Window B): `htf_batches 2,912` · `merged_pois 46,567` · `passed_validation 2,024` · `armed 655` · `duplicates_suppressed 1,369` · `routes 213` · `placed 45` · **`fills 44`** = `trades 44`. Runtime ≈ 1,024 s per run.
- Context only (not a claim): Window A's funnel armed 606 and filled 58; Window B armed 655 and filled 44. Arm→fill conversion is not measured here.

**Dual-run determinism (Gate D, run in place):**

| artifact | run1 | run2 | identical |
|---|---|---|---|
| `trades.csv` | sha256 `f918755f…c91031a3`, md5 `f74eba395165039d4ad8b94310d6fba4` | same | **yes** |
| `report.json` | sha256 `8b1a1206…f1e8df42`, md5 `06090516ef62a9ccd0b888c307c88553` | same | **yes** |
| funnel counts | 2912 / 46567 / 2024 / 655 / 1369 / 213 / 45 / 44 | same | **yes** |

→ **DETERMINISM: PASS.**

---

## 2. Pre-registration (coded into the script before Window B's results were read)

- **Population:** all closed trades in the post-dedup lifecycle book, per window. Nothing filtered, nothing ranked.
- **Metrics:** n; exit mix (`close_kind`, `tp_source`, `direction`); trigger mix (descriptive); net PnL + profit factor **labelled DIAGNOSTIC ONLY**; honest median MFE_R / MAE_R over the stored `[entry_at … exit_at]` window (`risk = |entry_price − original_sl|`); hypothesis counts **reused from the book's own `post_exit_class`** (never re-derived).
- **Window B label (mechanical):** `n<20 → BOOK_TOO_SMALL`; risk distances all missing / no excursion → `DATA_GAP_BLOCKING`; `Σpnl<0 → BOOK_STILL_LOSSY_DIAGNOSTIC`; otherwise → `BOOK_MIXED_PATHS_NO_CLAIM`.
- **Pair label (mechanical, shape-based — never "PF within X%"):** either n<20 → `INCONCLUSIVE_SMALL_N`; either book `DATA_GAP_BLOCKING` → `UNSTABLE_SHAPE` (not comparable); else `STABLE_SHAPE` iff **(a)** dominant `close_kind` identical and TP/SL shares within 15 pp, **(b)** dominant hypothesis bucket identical, **(c)** every hypothesis bucket with n≥5 on one side present on the other, **(d)** both labels diagnostic-family; else `UNSTABLE_SHAPE`.

Integrity guard: the shared metric path had to **reproduce Window A's published numbers exactly** before B was trusted — it does (§4).

---

## 3. Window B — book-level results

| Item | Value |
|---|---|
| n closed trades | **44** |
| close_kind | take_profit **16** · stop_loss **28** · be_scratch 0 · friday 0 · other 0 |
| TP share / SL share | 0.364 / 0.636 |
| Win rate by close_kind (share pnl>0) | TP bucket 16/16 = 1.00 (by construction) · SL bucket **20/28 = 0.714** |
| Win rate overall (pnl>0) | **36/44 = 0.818** |
| Direction | long 37 · short 7 |
| bars_held | median 5 (min 0, max 66) |

**Honesty note (the same trap as Window A, sharper here):** `close_kind=stop_loss` is **not** a loss. 20 of B's 28 stop closes finished **positive** — profit trailed into the stop. The dominant exit kind is a stop, yet the book is not a losing book. Both facts are recorded; neither is the "result".

**Net PnL + PF (DIAGNOSTIC ONLY — book-internal units, `pnl = price_diff × volume`, all costs 0.0 in the sanitized book):**

- Σpnl = Σpnl_net = **+0.8151**
- Gross win **+4.8438** · gross loss **−4.0287** · **PF = 1.2023** (diagnostic)

**Trigger mix (descriptive — no kill, no ranking):**

| Trigger | n | share |
|---|---|---|
| F | 16 | 0.364 |
| B | 14 | 0.318 |
| A | 13 | 0.295 |
| C | 1 | 0.023 |
| E | 0 | 0.000 |

Independent-field check: the `trigger` column and the `route_id` tail (`<poi>:<letter>@<bar>`) agree exactly (16/14/13/1) — the same identity cross-check as Window A.

**TP source mix:** structural_swing **33** · atr_fallback **11** (`none` 0). Detection-TF breakdown: still **not available** — no detection-TF column is stored on filled trades (same limitation as Window A; adding it would need a logging-only re-capture, not triggered here).

**Honest MFE / MAE in R (all 44 trades covered; `risk_dist` missing = 0; zero-window trades = 0; `DATA_GAP = 0`):**

| Stat | MFE_R | MAE_R |
|---|---|---|
| median | **0.812** | **0.684** |
| mean | 0.780 | 0.687 |
| count MFE_R < 0 ("never went favorable") | **0** | — |
| count MAE_R > 1.0R | — | **9 of 44** (0.205) |

**Hypothesis-style path buckets (`post_exit_class`, reused byte-stable):**

| Bucket | n |
|---|---|
| SL_THEN_TP_PATH | **18** |
| TP_REACHED | **16** |
| REJECTED | 7 |
| MFE_ONLY | 3 |
| DATA_GAP | **0** |

Coherence: `TP_REACHED` (16) == `close_kind take_profit` (16) — consistent, as in Window A.

---

## 4. Window A reproduction check (integrity of the shared code path)

Before any B number was used, the same code path recomputed Window A from its published book:

| check | result |
|---|---|
| n = 58 | ✅ |
| take_profit 30 / stop_loss 28 | ✅ / ✅ |
| F route count = 41 | ✅ |
| median MFE_R = 0.5022, median MAE_R = 0.4332 (published 0.502 / 0.433) | ✅ / ✅ |
| TP_REACHED 30 · SL_THEN_TP_PATH 14 · REJECTED 10 · MFE_ONLY 4 | ✅ |
| Σpnl +2.4501, PF 1.2091 | ✅ |

So the two columns of the stability table below are produced by one identical method, not by two scripts that happen to agree.

---

## 5. Stability table (required)

| Metric | Window A (Jun–Nov 2025) | Window B (Dec 2024–May 2025) | Note |
|---|---|---|---|
| **n** | **58** | **44** | both ≥ 20 → `INCONCLUSIVE_SMALL_N` not triggered |
| **exit mix shape** | TP 30 / SL 28 (TP 0.517 · SL 0.483) — dominant **take_profit** | TP 16 / SL 28 (TP 0.364 · SL 0.636) — dominant **stop_loss** | dominant kind **flipped**; TP share −15.36 pp, SL +15.36 pp |
| **F share** | 0.707 (41/58) | 0.364 (16/44) | largest descriptive difference; F no longer dominant in B (B 14 / A 13) |
| **PF (diagnostic)** | 1.2091 | 1.2023 | near-identical numerically; **not** a stability criterion |
| **Σpnl (diagnostic)** | +2.4501 | +0.8151 | same units, costs 0 in both |
| **med MFE_R / MAE_R** | 0.502 / 0.433 | 0.812 / 0.684 | B's trades travelled further both ways; B had 0 "never favorable" vs A's 4 |
| **MAE_R > 1R** | 19/58 (0.328) | 9/44 (0.205) | deep adverse paths exist in both books |
| **hypothesis shape** | TP_REACHED 30 · SL_THEN_TP_PATH 14 · REJECTED 10 · MFE_ONLY 4 — dominant **TP_REACHED** | SL_THEN_TP_PATH 18 · TP_REACHED 16 · REJECTED 7 · MFE_ONLY 3 — dominant **SL_THEN_TP_PATH** | dominant bucket **flipped**; REJECTED (0.172 vs 0.159) and MFE_ONLY (0.069 vs 0.068) shares are stable |
| **interpretation label** | `BOOK_MIXED_PATHS_NO_CLAIM` | `BOOK_MIXED_PATHS_NO_CLAIM` | same diagnostic family |

---

## 6. Interpretation — Window B (exactly one label)

**`BOOK_MIXED_PATHS_NO_CLAIM`**

Mechanical basis: n = 44 ≥ 20; risk distances present for all 44 and excursions computed for all 44 (no data gap); Σpnl = +0.8151 ≥ 0 → the mixed label. The book again contains genuine two-sided path variety (16 TP closes, 28 stop closes of which 20 positive, 18 stop-territory-then-TP paths), and the label asserts **nothing** about edge, quality, candidacy or readiness.

## 7. Pair stability (exactly one label)

**`UNSTABLE_SHAPE`**

Criterion detail as computed by the pre-registered rule:

| criterion | value | pass |
|---|---|---|
| dominant close_kind identical | A `take_profit` / B `stop_loss` | ❌ |
| TP share within 15 pp | **−15.36 pp** | ❌ (by 0.36 pp) |
| SL share within 15 pp | **+15.36 pp** | ❌ (by 0.36 pp) |
| dominant hypothesis bucket identical | A `TP_REACHED` / B `SL_THEN_TP_PATH` | ❌ |
| every n≥5 bucket present on the other side | A {TP_REACHED, SL_THEN_TP_PATH, REJECTED} ⊆ B ✅; B {SL_THEN_TP_PATH, TP_REACHED, REJECTED} ⊆ A ✅ | ✅ |
| both labels diagnostic-family | `BOOK_MIXED_PATHS_NO_CLAIM` / `BOOK_MIXED_PATHS_NO_CLAIM` | ✅ |

**Reading it honestly (descriptive, not a quality judgement):**

- The *book-level* claim is stable: both windows produce a describable two-sided book and the **same** diagnostic label family. Nothing about the machine's ability to produce a book changed.
- The *path anatomy* is not stable. In B, winners more often ended on a **trailing stop** after a favourable run (SL closes 20/28 positive; dominant bucket `SL_THEN_TP_PATH` 18/44) rather than at the TP target; in A, winners more often ended at the TP (`TP_REACHED` 30/58). The TP/SL shares sit **15.36 pp** apart — 0.36 pp outside the pre-registered 15 pp band — so the share test fails *marginally*, while the dominant-kind and dominant-bucket flips fail unambiguously.
- F participation is the most visibly different descriptive quantity (0.707 → 0.364). **No causal statement, no kill, no ranking** is drawn from it; it is recorded because the brief requires F share in the stability table.
- PF (1.209 vs 1.202) being nearly equal is **not** evidence of stability — the verdict deliberately ignores PF, exactly as pre-registered.

Given the marginality of the 15 pp share test, the honest summary is: **instability is confirmed by the dominant-kind/dominant-bucket flips, not by the share threshold**; the share numbers alone would have been a coin-flip against a pre-registered line that was chosen before the data and is not being moved now.

---

## 8. Limitations (stated, not hidden)

1. **No detection-TF breakdown** on either book — the column is not stored on fills (unchanged limitation from Window A).
2. **Cohort thinness in B**: E = 0, C = 1. Any per-trigger statement for those letters is uninformative; none is made.
3. **Warm-up overlap**: Window A's M1 load starts 2025-05-01, which lies inside B's exec range. No A fill occurs there (A's first fill is 2025-06-04) and no B fill is taken after 2025-05-21, so the two books share no traded bar; only ATR/HTF seeds are pre-loaded from that month.
4. **Costs are sanitized to 0.0** in both books — PF and Σpnl are book-internal diagnostic quantities, not trading results.
5. **n = 58 / 44**: descriptive only. `UNSTABLE_SHAPE` is a *qualitative shape* verdict under a pre-registered rule, not a statistical test and not a significance claim.
6. **No exit-strategy or trailing-logic investigation** was performed (banned this leg), even though §7 points straight at trailing-stop behaviour as the mechanism of the shape difference.

---

## Return block

```
EDGE_STABILITY_STATUS: PASS
WINDOW_A: 2025-06-01 -> 2025-11-30  N_A: 58
WINDOW_B: 2024-12-01 -> 2025-05-31  N_B: 44
EXIT_MIX_B: {take_profit: 16, stop_loss: 28, be_scratch: 0, friday: 0, other: 0}
TRIGGER_MIX_B: {F: 16, B: 14, A: 13, C: 1, E: 0}
NET_PL_B: +0.8151   PF_B: 1.2023
HONEST_MEDIAN_MFE_R_B: 0.812
HONEST_MEDIAN_MAE_R_B: 0.684
HYPOTHESIS_COUNTS_B: {SL_THEN_TP_PATH: 18, TP_REACHED: 16, REJECTED: 7, MFE_ONLY: 3, DATA_GAP: 0}
INTERPRETATION_B: BOOK_MIXED_PATHS_NO_CLAIM
PAIR_STABILITY: UNSTABLE_SHAPE
DETERMINISM: PASS
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
SUITE: NOT_RUN
REPORT_PATH: 06_RESEARCH/POST_DEDUP_EDGE_STABILITY_REPORT.md
NEXT_READY: Architect review of stability diagnostic
```

**Artefacts:** `06_RESEARCH/results/post_dedup_edge_stability/{run1,run2}/_funnel_capture/` (books + reports), `capture_meta.json` per run, `summary.json` (all tables + pair criteria + determinism receipt), `trades_enriched_B.csv` (per-trade MFE/MAE evidence trail). Script: `06_RESEARCH/scripts/post_dedup_edge_stability.py`.

**NEXT_READY (detail):** the diagnostic is complete; the Architect decides what (if anything) the shape difference warrants. Options that stay inside measurement: a third window, a pooled 18-month read, or a logging-only re-capture to attach detection-TF anatomy — each is a new call, none is authorised by this leg.
