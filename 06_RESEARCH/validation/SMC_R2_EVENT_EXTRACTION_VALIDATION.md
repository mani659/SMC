# SMC-R2 — Event Extraction Integrity & Causal Sample Validation

**Date**: 2026-08-27
**Milestone**: SMC-R2
**Status**: COMPLETE
**Classification**: Pre-execution data / event-integrity gate

---

## 1. Executive Summary

SMC-R2 validates that the highest-priority SMC structural events can be extracted deterministically from historical XAUUSD M1 data without lookahead, duplicate inflation, or hidden discretionary choices.

**Decision: EXTRACTION VALID — READY FOR SMC-R3 EXPECTANCY TESTING**

The extraction engine produces:
- 208,621 swings (104,114 SH + 104,507 SL)
- 471,475 FVGs (239,445 bullish + 232,030 bearish)
- 471,475 OBs (one per FVG)
- 196,965 BOS events (100,507 bullish + 96,458 bearish)
- 0 lookahead issues
- 100% reproducible

---

## 2. Canonical Dataset

| Property | Value |
|----------|-------|
| Instrument | XAUUSD |
| Timeframe | M1 |
| Start | 2021-04-12 11:00:00 |
| End | 2026-04-10 20:59:00 |
| Bars | 1,768,123 |
| Duplicates | 0 |
| Source | m1_clean.csv (local MT5 export) |

---

## 3. Extraction Results

### Swings (N=5)

| Type | Count |
|------|------:|
| Swing Highs | 104,114 |
| Swing Lows | 104,507 |
| **Total** | **208,621** |

**Confirmation rule:** A swing is only recognized after N=5 bars have elapsed past the swing bar. The confirmation timestamp is strictly after the swing timestamp.

### FVGs

| Direction | Count |
|-----------|------:|
| Bullish | 239,445 |
| Bearish | 232,030 |
| **Total** | **471,475** |

**Detection rule:** candle[i+2].low > candle[i].high (bullish) or candle[i+2].high < candle[i].low (bearish). Confirmed at candle[i+2] close.

### Order Blocks

| Direction | Count |
|-----------|------:|
| Bullish | 239,445 |
| Bearish | 232,030 |
| **Total** | **471,475** |

**Definition:** OB = candle immediately preceding the FVG-creating candle. Color irrelevant. Zone = [OB.low, OB.high].

### BOS (Break of Structure)

| Direction | Count |
|-----------|------:|
| Bullish | 100,507 |
| Bearish | 96,458 |
| **Total** | **196,965** |

**Definition:** Close beyond the most recent confirmed swing high (bullish) or swing low (bearish). Recognized only after closing price confirms.

---

## 4. Lookahead Audit

**Result: 0 issues.**

| Check | Result |
|-------|--------|
| Swing confirmation > swing creation | ✅ PASS |
| FVG bar_index >= OB bar_index + 2 | ✅ PASS |
| BOS close after swing confirmation | ✅ PASS |

No future information is used in any event classification.

---

## 5. Reproducibility Test

**Result: PASS.**

| Extraction | First Run | Second Run | Match |
|-----------|----------:|----------:|:-----:|
| Swing Highs | 104,114 | 104,114 | ✅ |
| Swing Lows | 104,507 | 104,507 | ✅ |
| FVGs | 471,475 | 471,475 | ✅ |

Identical code, identical data, identical results.

---

## 6. Event Independence Assessment

### Multiple FVGs per swing

A single swing can generate multiple FVGs if there are multiple displacement candles. Each FVG creates its own OB. This is architecturally correct — each FVG represents a distinct imbalance event.

### Overlapping OBs

Multiple OBs can overlap in price. The freshness state machine handles this: each OB is tracked independently, and the first-touch rule applies per-OB.

### Sample inflation risk

The raw extraction produces large counts (471K FVGs, 197K BOS). SMC-R3 must apply structural filters (POI validation pillars) to identify high-quality events. The raw counts are the universe, not the final sample.

---

## 7. CHOCH Extraction — Deferred

CHOCH extraction requires:
1. Trend direction identification (series of HH/HL or LH/LL)
2. Liquidity sweep detection
3. Character change confirmation

This is more complex than BOS and requires the trend-state infrastructure. SMC-R2 extracts the foundational primitives (swings, FVGs, OBs, BOS) that CHOCH builds upon. Full CHOCH extraction is deferred to SMC-R3 when POI models are tested.

---

## 8. Leading/Ending Diagonal — Feasibility Assessment

**Status: DEFERRED — REQUIRES FURTHER FORMALIZATION**

Wave counting (5-wave impulse, diagonal identification) retains subjectivity even with R1 definitions. The R1 Kill Rules apply:

> "A candidate should be deprioritized if it depends heavily on subjective Elliott-wave labeling."

SMC-R3 should first validate the objective models (BOS+OB, Two-Bar, RSI Divergence) before attempting diagonal extraction.

---

## 9. Structural Redundancy Notes

| Overlap | Assessment |
|---------|-----------|
| Model 2 (RBS/SBR) vs Model 6 (Double-Top Neckline) | Both involve broken-level retests; may generate duplicate events |
| Model 3 (CHOCH Retest) vs Model 6 | Structurally similar broken-level patterns |
| BOS vs CHOCH | BOS is continuation; CHOCH is reversal; they are complementary, not redundant |
| Two-Bar + RSI Divergence | Both are micro-triggers; they can co-occur at the same POI |

These overlaps must be managed in SMC-R3 through event de-duplication rules.

---

## 10. What SMC-R2 Establishes

1. The canonical XAUUSD M1 dataset is identified and validated (1.77M bars, 2021-2026)
2. Swings, FVGs, OBs, and BOS can be extracted deterministically
3. No lookahead exists in any extraction
4. Extraction is 100% reproducible
5. The foundational event ledger is ready for POI validation and trigger testing

---

## 11. What SMC-R2 Does NOT Establish

1. That any event has positive expectancy
2. That any POI model is profitable
3. That any trigger is valid
4. Any parameter values
5. Any strategy

---

## 12. SMC-R3 Readiness

| Criterion | Status |
|-----------|--------|
| Canonical dataset identified | ✅ |
| Swings extractable | ✅ |
| FVGs extractable | ✅ |
| OBs extractable | ✅ |
| BOS extractable | ✅ |
| Lookahead-free | ✅ |
| Reproducible | ✅ |
| Event counts reasonable | ✅ |
| CHOCH extractable | ⏳ deferred to SMC-R3 |
| Diagonals extractable | ❌ deferred — needs further formalization |

**SMC-R3 is authorized to proceed with Priority 1 (BOS+OB Continuation) and Priority 3 (Two-Bar Reversal) testing.**

---

## 13. External API calls: 0 | New data acquired: 0 | Spend: $0.00

---

*SMC-R2 is a data/integrity milestone. No expectancy tests were run. No strategies were tested.*
