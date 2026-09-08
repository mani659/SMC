# SMC-R1 — Structural Model Formalization & Module Qualification Architecture

> **⚠️ LOCKED DECISIONS APPLIED** — This document is aligned with `SMC_RESEARCH/LOCKED_DECISIONS.md` (2026-09-01). Priority hierarchy, frozen thresholds, and model classifications are now authoritative.

**Date**: 2026-08-27
**Milestone**: SMC-R1
**Status**: COMPLETE
**Classification**: Architecture / Research-design milestone — no implementation

---

## 1. Executive Summary

SMC-R1 transforms the SMC knowledge base into a rigorous research architecture. It formalizes every structural definition into machine-testable specifications, separates observable geometry from market-story interpretation, defines the module qualification framework, and establishes the research pipeline.

**Decision: FRAMEWORK COMPLETE — READY FOR SMC-R2 EVENT EXTRACTION VALIDATION**

The framework identifies 8 POI models, 6 entry triggers, and their compatibility relationships. It separates signal models from context modules and execution modules. The anti-combination-mining rule is preserved.

---

## 2. Core Research Principle: Observable vs Interpretive

Every SMC concept must be separated into:

### Observable Price Geometry (TESTABLE)

- Swing formed (HH, HL, LL, LH)
- Liquidity sweep occurred (price pierced a defined level)
- BOS/CHOCH occurred (structural break confirmed)
- FVG exists (3-candle imbalance gap)
- Candidate OB exists (candle preceding FVG)
- First touch occurred
- RSI divergence exists
- Volume is below historical reference
- Price is in premium/discount zone
- Inducement structure present

### Market Interpretation (NOT TESTABLE ALONE)

- Institutions accumulated at this level
- Smart money distributed here
- Trapped traders provide liquidity
- Institutional limit orders remain
- Engineered liquidity was intentionally created

**Rule:** The research engine tests observable rules. Interpretations are hypotheses about WHY the observables work, not inputs to the algorithm.

---

## 3. Foundational Definitions

### 3.1 Order Block (OB)

**Formal Definition:**

```
OB = the candle whose body/wick immediately precedes the first candle
     that creates a Fair Value Gap (FVG) in the opposite direction.

Properties:
  - Candle color: IRRELEVANT (confirmed by 07_PROVEN_KNOWLEDGE)
  - Timeframe: matches the FVG detection timeframe
  - Active from: moment FVG is created
  - Zone boundaries: [candle_low, candle_high] (full wick range)
  - Alternative zone: [candle_body_low, candle_body_high] (body only — conservative)
```

**Deterministic Identification Algorithm:**

```
1. Detect FVG on timeframe T
2. FVG = gap where candle[3].low > candle[1].high (bullish)
         or candle[3].high < candle[1].low (bearish)
3. OB = candle[0] (the candle immediately before candle[1])
4. OB zone = [OB.low, OB.high]
5. OB is BULLISH if FVG is bullish (demand)
6. OB is BEARISH if FVG is bearish (supply)
```

**Ambiguity Resolution:**

| Situation | Rule |
|-----------|------|
| Multiple consecutive FVGs | Each FVG creates its own OB; the earliest unmitigated OB is primary |
| Overlapping FVGs | Use the OB associated with the largest FVG (by gap size) |
| OB body vs wick | Default: full wick [low, high]; conservative: body [body_low, body_high] |
| OB with no FVG | NOT an OB by this definition — reject |

### 3.2 Fair Value Gap (FVG)

**Formal Definition:**

```
FVG = a 3-candle pattern where:

  Bullish FVG: candle[3].low > candle[1].high
  Bearish FVG: candle[3].high < candle[1].low

Properties:
  - Gap size = |candle[3].extreme - candle[1].extreme|
  - Midpoint = (candle[1].extreme + candle[3].extreme) / 2
  - Timeframe: detection timeframe
  - Active from: candle[3] close
```

**Deterministic Identification:**

```
For each consecutive triplet (candle[i], candle[i+1], candle[i+2]):
  if candle[i+2].low > candle[i].high:
    FVG_bullish(i) = (candle[i].high, candle[i+2].low)
  if candle[i+2].high < candle[i].low:
    FVG_bearish(i) = (candle[i+2].high, candle[i].low)
```

### 3.3 Structural Break (BOS / CHOCH) — UPDATED with Expert CHOCH Types

**Formal Definition:**

```
BOS (Break of Structure):
  Bullish BOS: candle close > previous swing high
  Bearish BOS: candle close < previous swing low

CHOCH (Change of Character) — THREE TYPES (Expert NEW):

  RULE 1 — Standard CHOCH (Highest Strength):
    Bearish: in uptrend (HH, HL), candle body CLOSES below last HL
    Bullish: in downtrend (LH, LL), candle body CLOSES above last LH
    Key: The LAST SWING of the main trend is broken.

  RULE 2 — Inside CHOCH Body (Medium Strength):
    Price enters POI, intermediate structure forms inside correction.
    Candle body CLOSES beyond an INTERMEDIATE level.
    BUT the last swing of the main trend is NOT broken.
    Key: Break happens INSIDE the correction, not at the main swing.

  RULE 3 — Inside CHOCH Wick (Lowest Strength):
    Price WICKS beyond a structural level but body does NOT close beyond.
    Only wicks penetrate — no structural commitment.
    Key: Requires additional confluence for valid entry.
```

**Base Candle Definition (Expert NEW):**

```
Base Candle = the candle that creates the structural extreme at a swing point.

  Bullish: Base Candle = candle whose HIGH is the swing high
  Bearish: Base Candle = candle whose LOW is the swing low
           (Exception: if next candle wick is lower but current
            is bearish, the bearish candle is still the Base Candle)
```

**Swing Validity Gate (Expert NEW):**

```
A swing is ONLY valid if:
  1. A Base Candle is identified at the extreme
  2. Price later breaks the Base Candle's OPPOSITE extreme
  3. A candle CLOSES beyond that extreme

If step 2-3 never happens → swing is INVALID → no POI can form.
Two-bar reversal alone does NOT confirm swing validity.

Validity Decision:
  [Base Candle found] → [Price breaks opposite extreme?] → [Candle closes beyond?]
  YES+YES = VALID swing → POI can form
  YES+NO (wick only) = INVALID
  NO = INVALID
```

**Swing Point Definition:**

```
Swing High: a candle whose high is greater than both
            N candles before and N candles after
Swing Low:  a candle whose low is lower than both
            N candles before and N candles after
N = detection parameter (default: 5 for HTF, 3 for LTF)

ADDITIONAL VALIDATION (Expert NEW):
  A detected swing point must pass the Swing Validity Gate
  (Base Candle break + close) before it can generate a POI.
```

### 3.4 Dealing Range

**Formal Definition:**

```
Dealing Range:
  - Defined by the most recent confirmed Swing High and Swing Low
  - Range High = Swing High high
  - Range Low = Swing Low low
  - 50% level = (Range High + Range Low) / 2 (equilibrium midpoint)
  - Premium zone: price > 55% of range (FROZEN: bearish POIs must be here)
  - Discount zone: price < 45% of range (FROZEN: bullish POIs must be here)
  - Equilibrium exclusion: 45%–55% of range (FROZEN: REJECTED — consolidation trap)
  - CRITICAL: Dealing range MUST be same TF as POI detection (FROZEN)
```

**Active Range Update Rule:**

```
The dealing range updates when a new swing high or swing low is confirmed
(close beyond N-bar swing on the relevant timeframe).
```

### 3.5 Liquidity Sweep

**Formal Definition:**

```
Liquidity Sweep:
  Buy-Side Liquidity (BSL) sweep:
    Price wick > defined liquidity level (EQH, session high, PDH, etc.)
    AND candle closes back below the level

  Sell-Side Liquidity (SSL) sweep:
    Price wick < defined liquidity level (EQL, session low, PDL, etc.)
    AND candle closes back above the level

Liquidity Levels (Stage 0A Master Classification — LOCKED_DECISIONS.md Section 2):
  - Equal Highs/Lows (EQH/EQL): two or more swing highs/lows at the same price,
    active on BOTH top (BSL) and bottom (SSL); tolerance ≤ 4.5 pips on XAUUSD
  - Session Highs/Lows: Asia, London, New York session extremes
  - Previous Day/Week High/Low (PDH/PDL, PWH/PWL)
  - Structural swing highs/lows on HTF: ONLY structural swings qualify
    (Base Candle & Swing Validity Gate — minor non-structural noise discarded)
  - POI Level Sweeps: OB sweep or FVG sweep at a POI = liquidity sweep
  - Demand/Supply boundary fallback sweep: when no in-between entry inside
    the zone body, focus on the zone extreme sweep
  - Order Block boundary fallback sweep: when no in-between entry inside the
    OB body, wait for the OB extreme sweep

Smart Money Stop-Loss Hunting Edge (Expert — 2026-09-05):
  Smart money hunts retail stops at EQH/EQL, OB edges, and D/S boundaries
  before delivering the real move. Once retail stops are eaten at a level,
  market does NOT return to re-hunt previous sweep levels — post-sweep
  entries carry structural protection.
```

---

## 4. Freshness State Machine

```
STATE_CREATED
  ↓ (price has not returned)
STATE_FRESH (Unmitigated)
  ↓ (price touches zone boundary)
STATE_TESTED (Mitigated)
  ↓ (price closes beyond extreme boundary)
STATE_VIOLATED (Invalidated)

Also:
STATE_FRESH → STATE_VIOLATED (if price closes beyond without touching)
```

**State Transition Rules:**

| Transition | Condition | Action |
|-----------|-----------|--------|
| CREATED → FRESH | No return to zone | Zone remains active |
| FRESH → TESTED | Price wick touches zone boundary | Zone deactivated for new entries |
| TESTED → VIOLATED | Price closes beyond zone extreme | Zone permanently invalidated |
| FRESH → VIOLATED | Price closes beyond without touching | Zone permanently invalidated |

**Multiple Touches:**

```
Touch = price wick enters zone boundary [zone_low, zone_high]
First touch = STATE_FRESH → STATE_TESTED
Second touch = zone already TESTED; no new entry signal
```

**Overlapping POIs:**

```
If two POIs overlap:
  1. Use the POI with the more extreme zone boundary
  2. If identical, prefer the one created first (earlier in time)
  3. Record the overlap in the event log
```

---

## 5. The 8 POI Models — Deterministic Specifications

### Model 1: Origin Demand / Supply Base

```
STRUCTURAL PRECONDITIONS:
  1. Confirmed Swing Low (bullish) or Swing High (bearish)
  2. Price moved away from the level with BOS + FVG displacement
  3. The level has NOT been retested (STATE_FRESH)

IDENTIFICATION EVENT:
  Bullish: Swing Low → Swing Higher High (BOS) → pullback toward origin
  Bearish: Swing High → Swing Lower Low (BOS) → pullback toward origin

POI PRICE/ZONE:
  Bullish: [origin_swing_low, origin_candle_high]
  Bearish: [origin_candle_low, origin_swing_high]

DIRECTION:
  Bullish POI → buy at zone
  Bearish POI → sell at zone

INVALIDATION:
  Price closes beyond the origin swing extreme

FRESHNESS:
  STATE_FRESH until first touch

FIRST-TOUCH DEFINITION:
  Price wick enters the zone boundary for the first time after creation
```

### Model 2: RBS / SBR Breaker Flip

```
STRUCTURAL PRECONDITIONS:
  1. A swing high (bullish) or swing low (bearish) exists
  2. Price breaks beyond the swing level (BOS in opposite direction)
  3. The broken level has not been retested (STATE_FRESH)

IDENTIFICATION EVENT:
  Bullish RBS: Swing High → break above → retest from above
  Bearish SBR: Swing Low → break below → retest from below

POI PRICE/ZONE:
  Bullish: [broken_swing_high - tolerance, broken_swing_high + tolerance]
  Bearish: [broken_swing_low - tolerance, broken_swing_low + tolerance]
  (tolerance = 1-2 ATR on detection timeframe)

DIRECTION:
  Bullish RBS → buy at zone
  Bearish SBR → sell at zone

INVALIDATION:
  Price closes beyond the broken swing level by > 2× tolerance

FRESHNESS:
  STATE_FRESH until first touch

FIRST-TOUCH DEFINITION:
  Price retests the broken level from the expected direction
```

### Model 3: CHOCH Baseline Retest (3 Sub-Variants — Expert NEW)

```
STRUCTURAL PRECONDITIONS:
  1. Established trend (series of HH/HL or LH/LL)
  2. Liquidity sweep beyond the final extreme (HH for bearish, LL for bullish)
  3. CHOCH confirmed (see Rule 1/2/3 below)
  4. The broken support/resistance from the CHOCH has not been retested

THREE CHOCH TYPES:

  RULE 1 — Standard CHOCH (Body Close, Last Swing Break):
    Price breaks and candle body CLOSES beyond the LAST SWING of the main trend.
    Bearish: Uptrend → HH sweep → body close below last HL
    Bullish: Downtrend → LL sweep → body close above last LH
    STRENGTH: Highest
    ENTRY: Sell/Buy Limit at the broken last HL/LH level

  RULE 2 — Inside CHOCH Body (Body Close, NO Last Swing Break):
    Price enters POI, forms intermediate structure inside correction.
    Price breaks and candle body CLOSES beyond an INTERMEDIATE level.
    BUT the last swing of the main trend is NOT broken.
    STRENGTH: Medium
    ENTRY: Sell/Buy Limit at the broken intermediate level

  RULE 3 — Inside CHOCH Wick (Wick Only, NO Last Swing Break):
    Price WICKS beyond a structural level but body does NOT close beyond.
    Only wicks penetrate — no structural commitment.
    STRENGTH: Lowest — KEPT in the system. No extra confluence gate.
    ENTRY: At wick-pierced level. Tick-data validation pending.

CHOCH STRENGTH RANKING:
  Rule 1 (Standard) > Rule 2 (Inside Body) > Rule 3 (Inside Wick)

MODEL 3 SUB-VARIANT PRIORITY:
  3a (Rule 1) = Highest strength
  3b (Rule 2) = Medium strength
  3c (Rule 3) = Lowest strength — KEPT. No extra confluence gate. Tick-data validation pending.

POI PRICE/ZONE:
  Rule 1: [last_HL_low, last_HL_high] (broken support now resistance)
  Rule 2: [intermediate_level_low, intermediate_level_high]
  Rule 3: [wick_pierced_level ± tolerance]

DIRECTION:
  Bearish CHOCH retest → sell at zone
  Bullish CHOCH retest → buy at zone

INVALIDATION:
  Price closes beyond the sweep extreme (HH for bearish, LL for bullish)

FRESHNESS:
  STATE_FRESH until first touch

FIRST-TOUCH DEFINITION:
  Price returns to the broken level after CHOCH confirmation
```

### Model 4: Quasimodo Level (QML)

```
STRUCTURAL PRECONDITIONS:
  1. Left Shoulder (High 1 or Low 1) formed
  2. Head formed (Higher High or Lower Low beyond Left Shoulder)
  3. Price breaks below the neckline (between Left Shoulder and Head)
  4. The Left Shoulder level has not been retested

IDENTIFICATION EVENT:
  Bearish QML: LH → HH (head) → break below neckline → retest at LH level
  Bullish QML: HL → LL (head) → break above neckline → retest at HL level

POI PRICE/ZONE:
  Bearish: [left_shoulder_low, left_shoulder_high]
  Bullish: [left_shoulder_low, left_shoulder_high]

DIRECTION:
  Bearish QML → sell at Left Shoulder level
  Bullish QML → buy at Left Shoulder level

INVALIDATION:
  Price closes beyond the Head extreme

FRESHNESS:
  STATE_FRESH until first touch

FIRST-TOUCH DEFINITION:
  Price returns to the Left Shoulder horizontal level
```

### Model 5: Extreme Equal High / Supply Origin

```
STRUCTURAL PRECONDITIONS:
  1. Two or more swing highs at approximately the same level
  2. The level has not been retested after the final break
  3. The move away from the level showed BOS + FVG displacement

IDENTIFICATION EVENT:
  Bearish: Equal highs formed → break below → retest from below
  Bullish: Equal lows formed → break above → retest from above

POI PRICE/ZONE:
  Bearish: [equal_highs_low, equal_highs_high]
  Bullish: [equal_lows_low, equal_lows_high]

DIRECTION:
  Bearish equal highs → sell at zone
  Bullish equal lows → buy at zone

INVALIDATION:
  Price closes beyond the equal highs/lows extreme

FRESHNESS:
  STATE_FRESH until first touch

FIRST-TOUCH DEFINITION:
  Price returns to the equal highs/lows level after the break
```

### Model 6: SBR Double-Top Neckline Retest

```
STRUCTURAL PRECONDITIONS:
  1. Double top or double bottom pattern formed
  2. Neckline (support between the two tops / resistance between two bottoms) broken
  3. Neckline has not been retested

IDENTIFICATION EVENT:
  Bearish: Double top → neckline break below → retest from below
  Bullish: Double bottom → neckline break above → retest from above

POI PRICE/ZONE:
  Bearish: [neckline_low, neckline_high]
  Bullish: [neckline_low, neckline_high]

DIRECTION:
  Bearish neckline retest → sell
  Bullish neckline retest → buy

INVALIDATION:
  Price closes back beyond the neckline by > neck width

FRESHNESS:
  STATE_FRESH until first touch

FIRST-TOUCH DEFINITION:
  Price retests the broken neckline
```

### Model 7: Equal Resistance Shelf Retest

```
STRUCTURAL PRECONDITIONS:
  1. Sharp drop creates a resistance bounce
  2. Price breaks below the bounce low
  3. Price rallies back to the resistance bounce level
  4. The resistance level has not been retested after the break

IDENTIFICATION EVENT:
  Bearish: Drop → bounce creates resistance → break below → retest resistance
  Bullish: Rally → pullback creates support → break above → retest support

POI PRICE/ZONE:
  Bearish: [resistance_bounce_low, resistance_bounce_high]
  Bullish: [support_bounce_low, support_bounce_high]

DIRECTION:
  Bearish resistance retest → sell
  Bullish support retest → buy

INVALIDATION:
  Price closes beyond the resistance/support level by > 2× range

FRESHNESS:
  STATE_FRESH until first touch

FIRST-TOUCH DEFINITION:
  Price returns to the bounce level after the break
```

### Model 8: HTF Demand/Supply Zones (D1/H4) — NEW

```
TYPE: Multi-Timeframe Confluence Model (NOT single-timeframe structural)

HTF POI IDENTIFICATION (D1/H4):
  Scan for unmitigated zones:
  1. Order Block (OB): Last opposing candle before strong impulse
  2. Fair Value Gap (FVG): 3-candle imbalance gap
  3. Demand Zone: Single last bearish candle before strong bullish impulse. Zone = full body + wicks of that single opposing candle.
  4. Supply Zone: Single last bullish candle before strong bearish impulse. Zone = full body + wicks of that single opposing candle.

ZONE BOUNDARIES:
  Bullish (Demand): [zone_bottom, zone_top] = [last bearish candle low, last bearish candle high]
  Bearish (Supply): [zone_bottom, zone_top] = [last bullish candle low, last bullish candle high]

EXECUTION FLOW:
  Step 1: HTF Scan (D1/H4) — Identify zones, check freshness (1-touch rule)
  Step 2: LTF Approach (M5) — Price enters zone, watch structural approach
  Step 3: Execution TF (M1) — Entry trigger fires

ENTRY TRIGGER (M1):
  Any of the 6 standard triggers:
  - Ending Diagonal (PREFERRED — most common at HTF zones)
  - BOS (Break of Structure)
  - Two-Bar Reversal
  - CHOCH
  - Leading Diagonal
  - FVG entry

ENTRY:
  Limit order at M1 trigger level WITHIN the HTF zone
  NOT market order

STOP LOSS:
  Below/above M1 structure (2-5 pips typical)
  NOT based on HTF zone width

RR TARGET:
  Minimum 1:5 (tight SL → naturally high RR)

FRESHNESS:
  1-touch rule applies (same as Models 1-7)

INVALIDATION:
  Price closes beyond zone boundary (below demand zone top, above supply zone bottom)

PRIORITY:
  8 (lowest — zone-based, not structure-based)
  Does not compete with Models 1-7 for the same events
  Captures a different category of setup

SCORING BONUS:
  +10% if D1 and H4 zones overlap at the same level

KEY DISTINCTION:
  Models 1-7 = "What is the structure?" (pattern recognition)
  Model 8 = "Where is the zone?" (zone identification + LTF trigger)
```

---

## 6. The 5 POI Validation Pillars — Deterministic Rules

### Pillar 1: Zone Refinement (Frozen)

```
INPUT: structural level from POI model
CALCULATION: check for unmitigated OB or FVG overlapping the level
PASS: OB or FVG exists within ±0.5× ATR of structural level (FROZEN)
FAIL: no OB/FVG at structural level (naked level)
UNAVAILABLE: no FVG data at required timeframe
```

### Pillar 2: Displacement

```
INPUT: move away from POI origin
CALCULATION:
  1. Check for BOS (close beyond prior swing)
  2. Check for FVG at the displacement origin
  3. Measure displacement magnitude (minimum 1× ATR — FROZEN)
PASS: BOS + FVG present + displacement > 1× ATR
FAIL: no BOS, or no FVG, or displacement < 0.5× ATR
UNAVAILABLE: insufficient data for swing calculation
```

### Pillar 3: Premium / Discount (Frozen)

```
INPUT: POI price level, active dealing range (MUST be same TF as POI detection)
CALCULATION:
  range_position = (POI - Range Low) / (Range High - Range Low)
PASS (buy): range_position < 0.45 (discount — FROZEN)
PASS (sell): range_position > 0.55 (premium — FROZEN)
FAIL: 0.45 ≤ range_position ≤ 0.55 (equilibrium zone — REJECTED)
UNAVAILABLE: no confirmed dealing range
```

**CRITICAL:** The dealing range MUST be computed on the same timeframe as the POI detection. H1 POI uses H1 dealing range. H4 POI uses H4 dealing range.

### Pillar 4: Freshness (Frozen — Strict 1-Touch Only)

```
INPUT: POI zone, historical price data
CALCULATION:
  Check if price wick has entered the zone boundary since creation
PASS: STATE_FRESH (no prior touch — FROZEN: strict 1-touch only)
FAIL: STATE_TESTED or STATE_VIOLATED
UNAVAILABLE: insufficient historical data

RULE: No second-touch trades. Once touched, POI is deactivated forever.
RULE: Unfilled limit orders expire after N bars AND POI → STATE_TESTED.
```

### Pillar 5: Inducement

```
INPUT: POI zone, price structure in front of POI
CALCULATION:
  Check for EQH/EQL, trendline, or minor swing directly in front of POI
PASS: visible inducement structure present
FAIL: no inducement (reduced score, not automatic rejection)
UNAVAILABLE: insufficient structure data
```

---

## 7. The 6 Entry Triggers — Machine-Testable Hypotheses

### Trigger A: M1/M5 CHOCH Reversal

```
LOCATION REQUIREMENT:
  Price has reached a validated POI (Models 1-7) on HTF

TRIGGER:
  On M1 or M5:
  1. Price forms a local swing high/low within the POI zone
  2. CHOCH confirmed: close beyond the last swing in the POI direction
  3. Entry on retest of the CHOCH level

ENTRY PRICE:
  Limit order at the broken CHOCH level

STOP REFERENCE:
  Beyond the sweep extreme (for reversal CHOCH)

INVALIDATION:
  Price closes beyond the CHOCH origin without triggering entry

EXPIRY:
  Entry must trigger within N bars of CHOCH (default: 20 M5 bars)

TIMEFRAME:
  HTF for POI identification, M1/M5 for trigger execution

DIRECTION:
  Bullish CHOCH at bullish POI → buy
  Bearish CHOCH at bearish POI → sell
```

### Trigger B: Leading-Diagonal Initiation

```
LOCATION REQUIREMENT:
  Price has swept liquidity and reached an HTF POI

TRIGGER:
  1. 5-wave impulse structure forms out of the POI (new trend initiation)
  2. Fibonacci retracement from Wave 1 origin to Wave 5 peak
  3. Entry at Fibonacci 50%–61.8% retracement (Wave 2 pullback)

ENTRY PRICE:
  Limit order at Fibonacci 50%–61.8% zone

STOP REFERENCE:
  Below/above Wave 1 origin

INVALIDATION:
  Price closes beyond Wave 1 origin before entry triggers

EXPIRY:
  Entry must trigger within 30 bars of Wave 5 completion

TIMEFRAME:
  HTF for POI, execution timeframe for wave counting

DIRECTION:
  5 waves up from bullish POI → buy at Wave 2 pullback
  5 waves down from bearish POI → sell at Wave 2 pullback
```

### Trigger C: Ending-Diagonal Wave-5 Throw-Under/Over

```
LOCATION REQUIREMENT:
  Price has swept liquidity and reached an HTF POI at the END of a trend

TRIGGER:
  1. Contracting/expanding 5-wave diagonal forms into the POI
  2. Wave 5 pierces the boundary trendline (Throw-Under in downtrend, Throw-Over in uptrend)
  3. Entry at the Wave 5 boundary trendline sweep

ENTRY PRICE:
  Limit order at the boundary trendline sweep touch

STOP REFERENCE:
  Ultra-tight: just beyond the Wave 5 extreme wick

INVALIDATION:
  Wave count reclassified as impulse (not diagonal)

EXPIRY:
  Entry must trigger on the Wave 5 sweep candle or immediately after

TIMEFRAME:
  HTF for POI, execution timeframe for diagonal identification

DIRECTION:
  Ending diagonal at bearish POI → sell on Throw-Over
  Ending diagonal at bullish POI → buy on Throw-Under
```

### Trigger D: Two-Bar Reversal + Volume Confirmation (Frozen)

```
LOCATION REQUIREMENT:
  Price has reached a validated POI

TRIGGER:
  1. Two-candle reversal pattern (engulfing)
  2. Volume of engulfing candle < Volume of preceding candle
  3. Pattern forms within the POI zone

ENTRY PRICE:
  Limit order at 50% of engulfing body (FROZEN — not market order)

STOP REFERENCE:
  Beyond the extreme of the two-bar pattern

INVALIDATION:
  Price closes beyond the two-bar pattern extreme

EXPIRY:
  Entry on the bar immediately following the engulfing

TIMEFRAME:
  Execution timeframe (M5 or M15)

DIRECTION:
  Bullish engulfing at bullish POI → buy
  Bearish engulfing at bearish POI → sell
```

### Trigger E: Double Top/Bottom + RSI Divergence

```
LOCATION REQUIREMENT:
  Price has reached a validated POI

TRIGGER:
  1. Price forms a structural double top (bearish) or double bottom (bullish)
  2. Second peak/trough occurs within the POI zone
  3. RSI(14) shows divergence: price makes equal/higher high but RSI makes lower high
     (or price makes equal/lower low but RSI makes higher low)

ENTRY PRICE:
  Limit order at the neckline break, or at the second peak/trough

STOP REFERENCE:
  Beyond the pattern extreme (beyond the head/second peak)

INVALIDATION:
  Price closes beyond the pattern extreme without triggering

EXPIRY:
  Entry must trigger within 15 bars of pattern completion

TIMEFRAME:
  Execution timeframe (M15 or H1)

DIRECTION:
  Double bottom + bullish RSI divergence at bullish POI → buy
  Double top + bearish RSI divergence at bearish POI → sell
```

### Trigger F: BOS + OB Continuation

```
LOCATION REQUIREMENT:
  Price is in an established trend (confirmed BOS)

TRIGGER:
  1. BOS confirms trend continuation
  2. Unmitigated OB exists at the origin of the BOS impulse
  3. Price retraces to the OB zone

ENTRY PRICE:
  Limit order at OB proximal edge or 50% midpoint

STOP REFERENCE:
  Beyond the OB distal edge

INVALIDATION:
  Price closes beyond the OB without triggering

EXPIRY:
  Entry must trigger on the first touch of the OB

TIMEFRAME:
  HTF for OB identification, execution timeframe for entry

DIRECTION:
  Bullish BOS with bullish OB → buy at OB
  Bearish BOS with bearish OB → sell at OB
```

---

## 8. POI × Trigger Compatibility Matrix (Frozen per LOCKED_DECISIONS.md)

```
              CHOCH(A)  Leading(B)  Ending(C)  2-Bar(D)  RSI(E)  BOS(OB)(F)
Model 1         ✓          ✓          ✓          ✓         ✓        ✓
Model 2         ✓          ○          ○          ✓         ✓        ✓
Model 3         ✓          ○          ○          ✓         ✓        ✓
Model 4         ✓          ○          ✓          ✓         ✓        ○
Model 5         ✓          ○          ○          ✓         ✓        ✓
Model 6         ✓          ○          ○          ✓         ✓        ✓
Model 7         ✓          ○          ○          ✓         ✓        ✓
Model 8         ✓          ✓          ✓★         ✓         ✓        ✓

KEY:
  ✓ = structurally compatible
  ○ = possible but uncommon / less natural pairing
  ✓★ = PREFERRED trigger for this model (Model 8 + Ending Diagonal = expert's primary setup)
```

**Model 8 Note:** All 6 triggers are compatible, but Ending Diagonal (C) is the PREFERRED trigger at M1 when entering HTF Demand/Supply zones (per expert chart evidence).

**Interpretation (Frozen):**

- **Trigger A (CHOCH)** is universally compatible — it can follow any POI model
- **Trigger B (Leading Diagonal)** naturally pairs with Model 1 (origin retest)
- **Trigger C (Ending Diagonal)** naturally pairs with Models 4 and 5 (extreme POIs)
- **Trigger D (Two-Bar)** and **Trigger E (RSI)** are universal micro-triggers
- **Trigger F (BOS+OB)** is the natural continuation trigger for Models 1, 2, 5, 6, 7

**Modular Multi-Model Confluence:** All 8 models are equal tags. Multiple models can tag the same level. More tags = higher quality score. No model is suppressed.
**Trigger Selection:** Chronological — first valid LTF trigger wins
**Model 5 Definition:** Continuation setup (not reversal). Entry at broken equal level. Distinguished from Model 7 (reactive shelf).

---

## 9. Module Architecture

### Signal Models (generate tradeable events)

| Model | Type | Naturally Standalone? |
|-------|------|:---:|
| CHOCH Reversal (A) | Reversal | Possible |
| Leading Diagonal (B) | Trend initiation | Possible |
| Ending Diagonal (C) | Exhaustion | Possible |
| Two-Bar Reversal (D) | Micro-trigger | Module only |
| RSI Divergence (E) | Micro-trigger | Module only |
| BOS+OB Continuation (F) | Trend continuation | Possible |

### Context / Routing Modules (determine which signals are active)

| Module | Role | Standalone? |
|--------|------|:---:|
| Trend/Range State | Routes to trend vs reversal specialists | No — must condition a base |
| Dealing Range Premium/Discount | Filters POI quality | No — filter only |
| Volatility State | Adjusts expectations | No — filter only |
| Session State | Timing filter | No — filter only |
| POI Freshness | Activates/deactivates POIs | No — filter only |
| Inducement State | Validates POI quality | No — filter only |

### Execution Modules (determine HOW to execute)

| Module | Role | Standalone? |
|--------|------|:---:|
| M1/M5 CHOCH | LTF precision entry | No — needs POI |
| FVG/OB Mitigation | Entry zone refinement | No — needs POI |
| Fibonacci 50–61.8% | Retracement entry | No — needs wave count |
| Wave-5 Terminal | Diagonal sweep entry | No — needs diagonal |

---

## 10. Information Hierarchy

```
HTF Context (trend state, dealing range, session)
    ↓
POI Model (which of the 8 structural setups)
    ↓
POI Validation (5 pillars: zone, displacement, premium/discount, freshness, inducement)
    ↓
LTF Trigger (which of the 6 entry models)
    ↓
Execution (limit order placement, stop reference)
```

**Rule:** No lower layer overrides a failed higher layer.

> A beautiful M1 CHOCH cannot rescue a POI that is structurally invalid.

---

## 11. Event Identity Rules (Frozen)

```
One SMC Event = one validated POI + one LTF trigger + one execution

Multiple triggers at one POI:
  - Record each as a separate candidate event
  - But only the FIRST valid trigger (chronological) counts (FROZEN)
  - Subsequent triggers at the same POI are ignored

Multiple POIs at the same level:
  - Record all matching model tags. More independent tags = higher quality score. No model overrides another.
  - Record the overlap

Overlapping POIs (same structural level):
  - Highest priority model wins
  - Record the overlap

Failed trigger:
  - A failed trigger invalidates subsequent triggers at the same POI
  - The POI moves to STATE_VIOLATED

Unfilled limit orders:
  - Expire after N bars: M5=12 (1h), M1=30 (30min) (FROZEN)
  - POI marked STATE_TESTED (FROZEN)

News protocol:
  - Hard cancel all pending POI limit orders 15min before high-impact news (FROZEN)
  - High-impact: CPI, NFP, FOMC

New event:
  - A new event begins when a new POI is identified
  - OR when a new swing structure creates a fresh POI
```

---

## 12. Future Research Pipeline

```
SMC-R1: Structural Model Formalization ← CURRENT
    ↓
SMC-R2: Event Extraction Validation (deterministic extraction from historical data)
    ↓
SMC-R3: Standalone Event Experiments (per-model expectancy testing)
    ↓
SMC-R4: Module Qualification (M0→M1→M2→M3→M4)
    ↓
SMC-R5: Optional Interaction Hypothesis (if multiple M4 modules exist)
    ↓
SMC-R6: Combined OOS Validation
    ↓
SMC-R7: Execution/Demo Validation
    ↓
EA
```

---

## 13. Research Priority Ranking

After formalization, candidates ranked by:

| Rank | Model | Rationale |
|:---:|-------|-----------|
| 1 | BOS+OB Continuation (F) | Most objective, lowest ambiguity, clearest observable |
| 2 | CHOCH Reversal (A) | Universal, well-defined, but requires trend context |
| 3 | Two-Bar Reversal (D) | Simple, observable, but needs POI context |
| 4 | RSI Divergence (E) | Objective (RSI is computed), but indicator-dependent |
| 5 | Leading Diagonal (B) | Requires wave counting (semi-subjective) |
| 6 | Ending Diagonal (C) | Requires wave counting + diagonal identification |

---

## 14. Kill Rules

A candidate should be deprioritized or rejected if:

- Its structural definition is too discretionary
- It cannot be extracted deterministically from OHLCV data
- It depends heavily on subjective Elliott-wave labeling
- It requires future information
- It duplicates another model
- Its only justification is chart anecdotes
- Its eventual edge can only be discovered through parameter search

---

## 15. What SMC-R1 Establishes

1. Deterministic definitions for OB, FVG, BOS, CHOCH, dealing range, liquidity sweep
2. Freshness state machine with clear transitions
3. 8 POI models with machine-testable specifications
4. 5 POI validation pillars with deterministic pass/fail rules
6. 6 entry triggers as formal hypotheses
7. POI × trigger compatibility matrix
8. Module architecture (signal, context, execution)
9. Information hierarchy
10. Event identity rules
11. Future research pipeline
12. Research priority ranking

---

## 16. What SMC-R1 Does NOT Establish

1. That any SMC concept has positive expectancy
2. Any parameter values (RR, thresholds, etc.)
3. Any EA code
4. Any backtest results
5. Any strategy

---

## 17. External API calls: 0 | New data acquired: 0 | Spend: $0.00

---

*SMC-R1 is an architecture/research-design milestone. No code was written. No backtests were run. No strategies were tested.*
