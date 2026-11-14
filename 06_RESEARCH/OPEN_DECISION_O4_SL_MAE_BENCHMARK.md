# OPEN DECISION O4 — SL / MAE VS THE ~30-PIP BENCHMARK (MEASUREMENT)

**Date:** 2026-11-14 · **Status:** MEASURED · **INTERPRETATION: KEEP_ATR_PRODUCT**
**`LOGIC_CHANGED: NO`** · **`PRODUCT_CODE_CHANGED: NO`**
**Authority:** `OPEN_DECISIONS_RESEARCH_AGENDA.md` §O4; `LOCKED_DECISIONS` §21b
(product SL = ATR buffer; 30 pips = review benchmark only); Architect locks
O1 `KEEP_STATUS_QUO` · O2 `KEEP_UPSTREAM_ONLY` · O3 `FIRST_ARMED`.
**Script:** `06_RESEARCH/scripts/o4_sl_mae_benchmark.py`
**Artifacts:** `06_RESEARCH/results/open_decisions/o4_sl_mae/`
(`trades_mae.csv`, `summary.json`; results tree gitignored).

---

## 1. Question (from the agenda)

Does the shipped ATR-buffer stop sit materially worse than the expert's ~30-pip
reference on realised paths, and would a pinned-distance stop reduce avoidable
stop-outs without changing entry validity?

---

## 2. Pre-registration (fixed before any result was read)

| Item | Value |
|---|---|
| Window | product fills, exec 2025-10-01 → 2025-10-31 UTC (same run as O1–O3) |
| Trades | `o2_htf_sweep_stage_funnel/trades.csv` — **11 fills** (labelled small-n throughout) |
| Pip | **1 pip = 0.10 price** (XAUUSD 2-digit gold) → **30 pips = 3.00 price** |
| SL source | **`original_sl`** (placement stop); never the BE-modified working `sl`. 0 rows needed the fallback |
| Path | M5 exec slice (6,324 bars, identical to the composition), entry bar → exit bar inclusive |
| MAE/MFE | LONG: MAE = max(0, entry − min low), MFE = max(0, max high − entry); SHORT mirrored |
| Clean stop | stop-like `close_kind` AND \|exit − original_sl\| ≤ **0.05** price |
| n | 11 — descriptive only, no significance claims, no PnL input |

Pip sanity: the instrument trades near 4,000 and stops span 3.3–12.0 price
units. Under 0.10 per pip that is 33–120 pips, which matches the expert's pip
language; under an FX 0.0001 pip the whole book would sit under half a pip.

---

## 3. Results

**Aggregate (n = 11: 3 take-profit, 8 stop-loss; 8 clean stops at the placement SL)**

| Metric | p25 | median | p75 | min | max |
|---|---|---|---|---|---|
| Product SL distance (pips) | 61.1 | **71.4** | 79.1 | 32.7 | 120.5 |
| MAE (pips) | 46.0 | **78.1** | 100.2 | 10.5 | 167.7 |
| MFE (pips) | 9.5 | 28.3 | 66.9 | 0.0 | 115.7 |

**Shares**

| Share | Value |
|---|---|
| MAE ≤ 30 pips | **1 / 11 (9.1%)** |
| Product SL ≤ 30 pips | **0 / 11 (0%)** |
| Product SL > 30 pips | 11 / 11 (100%) |
| Clean stop (exit at placement SL) | 8 / 11 (72.7%) |
| MAE ≤ 30 pips on the 3 winners | 1 / 3 |
| MAE > 30 pips on the 8 stop-outs | 8 / 8 |

**MAE / benchmark ratios (median):** MAE ÷ product SL = **1.18** (p25 1.01,
p75 1.28) · MAE ÷ 30-pip benchmark = **2.60** (p25 1.53, p75 3.34).

**Per trade (pips)**

| poi | dir | trig | det TF | TP source | SL | MAE | MFE | close | MAE/SL |
|---|---|---|---|---|---|---|---|---|---|
| 009633 | long | B | M15 | structural | 120.5 | 10.5 | 58.7 | TP | 0.09 |
| 009751 | long | F | H1 | structural | 59.3 | 167.7 | 20.4 | SL | 2.83 |
| 018661 | short | F | M15 | structural | 77.1 | 34.0 | 115.7 | TP | 0.44 |
| 019132 | long | F | M15 | structural | 95.4 | 111.0 | 28.3 | SL | 1.16 |
| 024560 | long | F | D1 | structural | 81.1 | 78.1 | 89.8 | TP | 0.96 |
| 025021 | long | F | D1 | ATR fallback | 71.4 | 96.0 | 70.3 | SL | 1.34 |
| 026248 | long | F | M15 | structural | 44.3 | 52.1 | 0.0 | SL | 1.18 |
| 027041 | long | F | H1 | ATR fallback | 71.0 | 104.4 | 63.5 | SL | 1.47 |
| 032552 | long | F | H1 | structural | 62.9 | 76.1 | 9.1 | SL | 1.21 |
| 033908 | long | F | H4 | structural | 32.7 | 39.9 | 9.8 | SL | 1.22 |
| 034042 | long | F | H4 | ATR fallback | 75.1 | 80.1 | 0.0 | SL | 1.07 |

By trigger: F (n=10) median SL 71.2 / MAE 79.1 pips; B (n=1) 120.5 / 10.5.
By detection TF: M15 86.2 (n=4) · D1 76.3 (n=2) · H1 62.9 (n=3) · H4 53.9 (n=2)
median stop pips.

---

## 4. Reading

1. **Product stops are wider than the benchmark, everywhere.** Median 71 pips
   (7.1× the 30-pip mark); not a single trade's stop sits at or inside 30 pips.
2. **30 pips is tighter than the path, not wider than the noise.** 10 of 11
   trades saw MAE beyond 30 pips, and all 8 stop-outs did. A pinned 30-pip stop
   would have been hit on every loser — and would have knocked out 2 of the 3
   winners (MAE 34.0 and 78.1 pips on the two that reached TP beyond it). That
   is the opposite of "reduce avoidable stop-outs": it converts winners into
   losses on this book.
3. **Stops are not "far beyond observed MAE".** MAE ÷ product SL has a median of
   1.18 (p25 1.01). Since a stopped trade's adverse excursion necessarily reaches
   the stop, this is the expected shape: the stop is where the path died, not a
   distance sitting beyond it.
4. **Clean-stop behaviour is coherent**: 8/8 losers exited at the placement SL
   (`original_sl`), confirming the exported stop is the one the runner honoured —
   no BE contamination in the denominator.
5. **The one wide-MAE outlier is a bar-span artefact, not a stop failure.**
   `009751` shows MAE 2.83× its stop because the whole entry bar counts (see
   caveat); its exit was still the placement SL.

---

## 5. Lock interpretation (words only)

Agenda O4 criteria: `KEEP_ATR_PRODUCT` when the median product stop is not
wildly larger than MAE **and** the 30-pip mark is often tighter than path noise;
`REVIEW_ATR_CALIBRATION` when stops sit systematically beyond MAE or are hit
before any meaningful MFE with MAE ≪ 30.

- Median stop 71.4 vs median MAE 78.1 pips → the stop is not beyond the path.
- 30 pips is tighter than path noise on 10/11 trades and 8/8 stop-outs.
- MFE is frequently meaningful before the stop (median 28.3 pips; 7/11 trades
  saw ≥ 9 pips of favourable excursion), so stops are not "hit before anything
  happens".

→ **KEEP_ATR_PRODUCT.** The ATR buffer stands; 30 pips remains a review
benchmark only. **No 30-pip product rule is proposed or locked** (LOCKED §21b),
and no `FR2_*` constant is touched.

One honest observation for the Architect, explicitly *not* a lock: on the two
winners whose MAE exceeded 30 pips, a 30-pip stop would have removed the trade
entirely, which is why a pinned distance is not a free improvement here. If ATR
calibration is ever revisited, it must be as its own dated design with a
larger n.

---

## 6. Caveats

- **n = 11, one window.** Every share above is a count of a very small book;
  nothing here is inferential.
- **MAE includes the whole entry bar**, i.e. movement before the limit filled is
  counted as adverse excursion. This can only *overstate* MAE (never understate
  it), which is why the reading leans conservative and one ratio exceeds 2.
- MFE/MAE are path geometry, not outcomes; PnL and PF are not computed or used.
- 3 of 11 TPs used the ATR fallback and 8 the structural swing — the O5 split,
  not a variable here.
- Reconciliation: 11 trades in → 11 rows out, 0 dropped, `csv_rows` =
  `winners_plus_losers` = 11; 6,324 exec M5 bars match the composition.

---

## 7. Return block

```text
O4_STATUS: PASS
WINDOW: exec 2025-10-01 → 2025-10-31 UTC (11 product fills)
N_TRADES: 11
PIP_DEF: 1 pip = 0.10 price (XAUUSD) → 30 pips = 3.00 price
MEDIAN_PRODUCT_SL_PIPS: 71.4
MEDIAN_MAE_PIPS: 78.1
SHARE_MAE_LE_30PIP: 9.1% (1/11)
SHARE_PRODUCT_SL_LE_30PIP: 0.0% (0/11)
INTERPRETATION: KEEP_ATR_PRODUCT
PRODUCT_CODE_CHANGED: NO
NOTE_PATH: 06_RESEARCH/OPEN_DECISION_O4_SL_MAE_BENCHMARK.md
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
HANDOFF_UPDATED: YES
NEXT_READY: Architect O4 reading | O5 TP structural pack
```
