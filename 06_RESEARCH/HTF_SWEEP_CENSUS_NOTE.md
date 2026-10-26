# HTF SWEEP CENSUS (H4 + H1) — READ-ONLY NOTE

> **DIAGNOSTIC — NOT EDGE.**
> Counts only. No threshold was changed, no gate follows, no production
> code was touched. Read this before quoting any sweep number: §5
> explains what the older figures actually counted.

**Date:** 2026-10-11 · **Authority:** Lead Architect directive (count only).
**HTF_SWEEP_STATUS: PASS** (script + artifacts + 7 new tests green; byte-identical rerun).
**LOGIC_CHANGED: NO** (detectors only CALLED with frozen params, under `04_SRC` + research tests).

---

## 1. Method (one line)

`liquidity_scanner.scan()` builds levels on each TF series, then
`sweep_detector.detect_sweep()` enumerates every sweep per level (first
+ re-fires by advancing start_index — the identical wick-pierce +
close-back predicate the product evaluates: BSL = high > level and
close < level; SSL = low < level and close > level; `formed_at` bounds
respected so a level can never sweep itself at formation).

Window exec 2025-06-01 → 2025-11-30 (sweep candle inside); M1 warm-up
from 2025-05-01 (level/swing formation history). Script:
`06_RESEARCH/scripts/htf_sweep_census.py`.

## 2. Counts (the clean numbers)

| TF | Sweeps (events) | Unique levels | Re-fires | BSL (bias SHORT) | SSL (bias LONG) |
|---|---|---|---|---|---|
| **H4** | **9,139** | **759** | 8,380 | 4,645 | 4,494 |
| **H1** | **23,482** | **783** | 22,699 | 12,424 | 11,058 |

Direction bias is a reporting convention on pools (fade the swept
extreme), not a trade signal; the detector itself is pool-based (only
BSL/SSL pools occur on these TFs — no exotic pools).

By level family (swept events):

| TF | session | structural_swing | equal_highs_lows | periodic |
|---|---|---|---|---|
| H4 | 8,322 (91%) | 772 | 45 | 0 |
| H1 | 15,976 (68%) | 6,867 | 639 | 0 |

Session H/L dominate because they form every day around current price
(by construction, not a finding about edge); periodic PDH/PDL/PWH/PWL
levels exist (2+2 per TF in the load window) but were never swept in
the exec window. Levels formed (load-window dependent): H4 1,032 / H1
1,391 — of which 74% / 56% were swept at least once in-window.

## 3. Zone linkage + touch proximity (descriptive only)

Accepted set: 658 H4 pack zones + 10 D1 subset (same loader rules).
Zone first-touch bars: 599 (from the decomposed ledger; first-touch
only — later touches uncounted, conservative undercount).

| TF | Linked (level inside ≥1 zone) | Within ±20 M5 of a zone touch |
|---|---|---|
| H4 | 9,139 (100%) | 6,422 (70.3%) |
| H1 | 23,482 (100%) | 13,193 (56.2%) |

Two disclosures that keep these numbers honest:

1. **Linkage saturates and therefore discriminates nothing.** The 658
   accepted zones overlap so densely (median width $15.87) that their
   union covers **99.9%** of the traded price span — nearly every level
   falls inside some zone by construction. "Linked" here means "inside
   the accepted-zone blanket," not selective linkage. (This is a fact
   about the accepted zone set, discovered by the join — not a flaw in
   the census.)
2. **Touch proximity is near base rate.** 599 touch bars over 35,725 M5
   bars admit up to ~69% coverage at ±20 bars; observed 70.3% / 56.2%
   is at-or-below that ceiling. At this radius, proximity follows from
   both distributions being dense where price is — no selectivity read
   is licensed.

## 4. Verification

- Mechanical predicate spot-check: **821/821** sampled rows satisfy
  wick-pierce + close-back on their own TF bar.
- `formed_at` respected on every row (formation ≤ sweep bar).
- Window containment: first sweep 2025-06-01, last 2025-11-30 (no
  pre-window leakage, no truncation).
- Determinism: full rerun byte-identical (CSV + summary SHA match).
- 7 unit tests (`04_SRC/tests/test_htf_sweep_census.py`): bias map,
  unique identity, proximity bisect incl. signed offsets, exact
  containment (boundary-inclusive), re-fire enumeration against the
  real predicate (first + repeat + never-swept), hash stability,
  frozen window/radius params.

## 5. What the older figures actually counted (do not mix these up)

- **Decomposed ledger "sweep" 5,553** = sweep-tagged rows of the LTF
  confirmation pack (structure-linked, M5/M15 detection path) — NOT an
  H4/H1 census. Different detector invocation, different universe.
- **H4 POI pack 658** = raw H4 *structures* (OB/demand/supply/FVG
  zones), not sweeps.
- **This note: H4 9,139 / H1 23,482** = pure per-TF sweep-detector
  census (this window). **Start the HTF story from these numbers.**
- Product funnel 30 armed → 3 fills = post-chain survivors, a
  different object again.

## 6. Limitations (binding on reuse)

- Per-bar enumeration: re-fires of one level count separately
  (unique-level counts alongside for the setup-level read).
- Session-level dominance is constructional (daily levels near price).
- Touch proximity is first-touch-only and near base rate at ±20 bars.
- Direction bias is reporting convention, not signal.
- Single 6m window, single feed; no PnL, no edge, no gate follows.

---

**Artifacts:** `06_RESEARCH/scripts/htf_sweep_census.py` (new) ·
`06_RESEARCH/results/htf_sweep_census/` (`sweeps_h4.csv` 9,139 rows,
`sweeps_h1.csv` 23,482 rows, `summary.json`) · tests
`04_SRC/tests/test_htf_sweep_census.py` (7).
