# SMC-R4-CR — Decision

**Date**: 2026-08-27
**Milestone**: SMC-R4-CR
**Decision**: B — R4 VALID WITH MATERIAL LIMITATIONS

---

## Decision

The BOS+OB positive expectancy is real and survives deduplication. The result is scientifically informative but has material limitations that prevent unconditional M3 classification.

---

## What R4-CR Found

### Confirmed

1. **Positive expectancy survives deduplication**: Mean R = +1.01 bps with 123,386 unique trades (not 181,676)
2. **Stop implementation is correct**: Verified against CR2 definitions
3. **Directional symmetry is correct**: Both long (+1.31 bps) and short (+0.69 bps) are positive
4. **No lookahead**: Clean causal chain
5. **No methodology drift**: R4 matches R3/CR2 definitions (except duplicate BOS issue)
6. **OOS is positive**: +1.62 bps with 31,645 unique OOS trades

### Material Limitations

1. **Duplicate BOS entries**: R2 CSV has 31.8% duplicate bar_index values. R4 iterated over all rows without deduplication. The reported N was inflated by 32%. Mean R is unchanged.

2. **Extreme trade frequency**: 79 trades/day average, up to 117/day. Multiple trades enter on the same bar (up to 5). This suggests many trades represent repeated exposures to the same market move, not independent opportunities.

3. **Overlapping trades**: Up to 14 simultaneously open. These are not economically independent.

4. **Not fully cost-adjusted**: The fill convention (next-bar open) provides implicit cost representation, but explicit spread, slippage, and exit costs are not modeled.

5. **Effective sample size overstated**: The 123K unique trades include many correlated observations from the same market context. The true independent sample is much smaller.

---

## M3 Classification

> **M3 CONDITIONAL**

BOS+OB qualifies as an M3 Economic Candidate, but the material limitations must be documented and addressed before M4.

---

## What Must Change Before M4

1. **Deduplicate BOS entries** before event extraction (fix R2 or R4 preprocessing)
2. **Document event-level dependence** in the methodology
3. **Address cost model gap** (either add explicit costs or explicitly state the result is gross)
4. **Do NOT add filters or optimize** — M4 is about validation, not improvement

---

*This decision authorizes SMC-R5 methodology design, subject to the above requirements.*
