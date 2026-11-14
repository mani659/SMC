# OPEN DECISION O5 — TP: STRUCTURAL SWING VS 4×ATR FALLBACK (MEASUREMENT)

**Date:** 2026-11-14 · **Status:** MEASURED · **INTERPRETATION: KEEP_DUAL_TP_POLICY**
**`LOGIC_CHANGED: NO`** · **`PRODUCT_CODE_CHANGED: NO`**
**Authority:** `OPEN_DECISIONS_RESEARCH_AGENDA.md` §O5; `LOCKED_DECISIONS` §21b
(TP = first valid structural swing, 4×ATR fallback, ESSENCE 1:5 = benchmark
only); Architect locks O1–O4 status-quo.
**Script:** `06_RESEARCH/scripts/o5_tp_structural_vs_fallback.py`
**Artifacts:** `06_RESEARCH/results/open_decisions/o5_tp_source/`
(`trades_by_tp_source.csv`, `summary.json`; results tree gitignored).

---

## 1. Question (from the agenda)

How often is a structural TP available, and do structural-TP trades have
different path quality from the 4×ATR fallback?

---

## 2. Pre-registration (fixed before any result was read)

| Item | Value |
|---|---|
| Window | product path, exec 2025-10-01 → 2025-10-31 UTC (the O1–O4 run; no 6-month slice mixed in) |
| Labels | `structural_swing` / `atr_fallback` / `none` / `unknown` — **read from the export only** |
| Path | M5, entry bar → exit bar inclusive (O4 convention) |
| `hit_tp` | `take_profit` close OR \|exit − tp\| ≤ 0.05 |
| R-multiple | `tp_dist / |entry − original_sl|` |
| Placement level | `sample_audit.csv` has **no** `tp_source` column, so the mix comes from `trades.csv` (11 placements → 11 fills) |

---

## 3. Results

**Source mix (fills)**

| Source | n | share | hit TP | hit rate |
|---|---|---|---|---|
| `structural_swing` | 8 | 72.7% | 3 | **37.5%** |
| `atr_fallback` | 3 | 27.3% | 0 | **0.0%** |
| `none` / `unknown` | 0 | — | — | — |

**Path and geometry by source**

| Metric (median) | structural_swing (n=8) | atr_fallback (n=3) | overall (n=11) |
|---|---|---|---|
| `tp_dist` (price) | **6.11** | **25.13** | 10.26 |
| TP ÷ R | **0.91** | **3.52** | 1.47 |
| `mfe ÷ tp_dist` | **0.62** | **0.22** | 0.28 |
| `mfe ÷ R` | 0.32 | 0.89 | — |
| hold bars | 0.5 | 5.0 | 1.0 |

Per-trade source assignment is in the CSV; the three structural TP hits are
`009633`, `018661`, `024560`, and the three fallback fills are `025021`,
`027041`, `034042` (all stopped).

**Sanity / reconciliation:** 11 trades in → 11 rows; mix sums to 11; 11 routed
audit rows with placement geometry. The earlier note of "9 structural / 3
fallback" described 12 *candidates*; the export's 11 *fills* split 8 / 3 — the
one-candidate difference is the unfilled candidate, which has no `tp_source` in
any export (recorded as DATA_GAP, not inferred).

---

## 4. Reading

1. **Both branches are live and neither is pathological.** 8 of 11 fills used a
   structural swing and 3 needed the fallback; there is no `none`/`unknown`.
2. **Structural TP is a near-target, high-conversion target.** Median distance
   6.1 price units at **0.91 R** — the first valid swing usually sits just
   inside one risk unit — and it converts 3 of 8. The path routinely comes
   within 0.62 of it.
3. **The fallback is a far target that is rarely reached.** Median 25.1 price
   units at **3.52 R**; 0 of 3 were hit, and path MFE reached only 0.22 of it
   (0.89 R). This is the geometric consequence of a 4×ATR target paired with an
   ATR-buffer stop, not evidence of a defect: the fallback exists precisely for
   the case where no swing qualifies, and it behaves as a wide target.
4. **No evidence that one branch is systemically wrong-sided.** Neither source
   produced a target on the wrong side of entry (all TPs are beyond entry in the
   trade direction, `tp_dist` > 0), and hold times are short in both (median 0.5
   and 5 bars).
5. **Nothing here supports a ratio lock.** Median realised TP ÷ R is 1.47 overall
   with structural at 0.91 — a forced 1:5 ESSENCE minimum would be far outside
   where structural targets actually sit and would convert nearly every trade
   into an unreachable target. It remains a benchmark only.

---

## 5. Lock interpretation (words only)

Agenda O5: `KEEP_DUAL_TP_POLICY` when both sources appear and neither is clearly
broken; `STRUCTURAL_ONLY_REVIEW` requires fallback dominance with poor
`mfe_vs_tp` **and** structural clearly better; `FALLBACK_DOMINANT_OK` when
structural is rare (it is not — 73%).

- Both sources appear in a sensible proportion (8 / 3).
- Structural converts (37.5%); the fallback is unreachable in this sample but
  its role is the "no swing qualifies" case, and its `mfe_vs_tp` of 0.22 follows
  mechanically from a 3.5 R target.
- n = 11 — far too small to separate branches.

→ **KEEP_DUAL_TP_POLICY** (also the agenda's default). No `resolve_take_profit`
change, no feed change, and **no 1:5 product RR lock**.

Observation for the Architect, explicitly not a lock: structural targets landing
at ~0.9 R mean the TP branch caps reward near one risk unit whenever a swing is
found; if that is ever revisited it needs its own dated design and a much larger
n.

---

## 6. Caveats

- n = 11 fills, one window; every share above is a count of a very small book.
- `hit_tp` is inferred from `close_kind` plus a fixed 0.05 tolerance — no
  intrabar TP-touch model.
- The 12th candidate is absent from the trade export (no fill, no `tp_source`);
  it is reported as a gap rather than assigned a source.
- Path metrics are geometry, not outcomes; PnL/PF is not computed or used.
- `sample_audit.csv` lacks `tp_source`, which is why the placement mix is read
  from the trades export; both agree on the 11 placements.

---

## 7. Return block

```text
O5_STATUS: PASS
WINDOW: exec 2025-10-01 → 2025-10-31 UTC (11 fills)
N_PLACED_OR_TRADES: 11
TP_SOURCE_MIX: {structural_swing: 8, atr_fallback: 3, none: 0, unknown: 0}
HIT_TP_BY_SOURCE: {structural_swing: 3/8 (37.5%), atr_fallback: 0/3 (0.0%)}
MEDIAN_MFE_VS_TP: {structural_swing: 0.62, atr_fallback: 0.22, overall: 0.28}
INTERPRETATION: KEEP_DUAL_TP_POLICY
PRODUCT_CODE_CHANGED: NO
NOTE_PATH: 06_RESEARCH/OPEN_DECISION_O5_TP_STRUCTURAL_VS_FALLBACK.md
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
HANDOFF_UPDATED: YES
NEXT_READY: Architect O5 reading | Open-decisions closeout / next program
```
