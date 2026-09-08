# CHOCH Types, Base Candle Definition & Valid Swing Rules

**Date:** 2026-09-01
**Source:** Expert chart markup session (5 charts analyzed)
**Status:** NEW — Pending integration into locked decisions

---

## 1. The Three Types of CHOCH

Our existing specification defines only one CHOCH type (standard body close). The expert teaches **three distinct CHOCH types**, two of which are "Inside CHOCH" variants where price does NOT break the last structural swing.

### CHOCH Rule 1: Standard CHOCH (Body Close Break)

**The textbook CHOCH we already have in our specs.**

```
STRUCTURAL GEOMETRY:
  Uptrend (HH, HL sequence) →
  Price sweeps final HH (liquidity grab) →
  Displacement down →
  Candle BODY CLOSES below the last HL →
  CHOCH confirmed

CONFIRMATION: Candle body close beyond the last structural swing
STRENGTH: Highest — clean structural break
ENTRY: Sell Limit at the broken HL level (from below)

Visual Reference: choch_rule_1_standard_m15.png (XAUUSD M15)
```

**Key distinction from Rule 2 and 3:** Price actually breaks and closes beyond the LAST SWING in the trend direction. The main structural level is violated.

---

### CHOCH Rule 2: Inside CHOCH — Body Close (No Last Swing Break)

**The expert's first "Inside CHOCH" variant.**

```
STRUCTURAL GEOMETRY:
  Uptrend → Price enters POI →
  Inside the correction/consolidation, a SMALLER structure forms →
  Price breaks and CLOSES beyond an INTERMEDIATE structural level →
  But the LAST SWING of the main trend is NOT broken

CONFIRMATION: Candle body close beyond an intermediate level (NOT the last swing)
STRENGTH: Medium — structural break happens INSIDE the correction
ENTRY: Sell Limit at the broken intermediate level

Visual Reference: choch_rule_2_inside_choch_m1.png (XAUUSD M1)
```

**Key distinction from Rule 1:** The main trend's last swing (HH for bearish, LL for bullish) is NOT broken. The CHOCH happens on a smaller internal structure within the correction. Price breaks an intermediate high/low but the overall swing remains intact.

**When this occurs:** Market comes into POI and begins a correction. Within that correction, a smaller structure forms. When price breaks that smaller structure with a body close, it's a Rule 2 Inside CHOCH.

---

### CHOCH Rule 3: Inside CHOCH — Wick Only (Weakest)

**The expert's second "Inside CHOCH" variant — the weakest form. KEPT in the system.**

```
STRUCTURAL GEOMETRY:
  Uptrend → Price enters POI →
  Inside the correction, a structure forms →
  Price WICKS beyond a structural level →
  But candle BODY does NOT close beyond →
  Only wicks penetrate the level

CONFIRMATION: Wick pierce only (no body close)
STRENGTH: Lowest — KEPT as valid signal at lowest strength
ENTRY: At wick-pierced level. No extra confluence gate.
STATUS: KEPT — will be validated or invalidated later with tick-data testing.

Visual Reference: choch_rule_3_wick_only_m1.png (XAUUSD M1)
```

**Key distinction from Rule 2:** Even the intermediate level is NOT closed beyond. Only wicks penetrate. This is the weakest form of CHOCH and requires the most additional confirmation.

**When this occurs:** Market is at POI and shows indecision. Wicks probe beyond structural levels but candles close back inside. Institutions are testing the waters but haven't committed.

---

### CHOCH Strength Comparison

| Rule | Type | What Breaks | Confirmation | Strength | Entry Confidence |
|:----:|------|-------------|-------------|:--------:|:----------------:|
| **1** | Standard | Last swing of main trend | Body close | Highest | Highest |
| **2** | Inside (Body) | Intermediate level (NOT last swing) | Body close | Medium | Medium |
| **3** | Inside (Wick) | Intermediate level (NOT last swing) | Wick only | Lowest — **KEPT** | Valid signal. Tick-data validation pending. |

---

## 2. Base Candle Definition

The expert defines a **Base Candle** as the candle that creates the structural extreme (high or low) at a swing point.

### Bullish Trend — Base Candle = Candle That Creates the HIGH

```
In a bullish impulse leg:
  The BASE CANDLE is the candle whose HIGH is the swing high.

  NOT the candle before it.
  NOT the candle after it.
  The ONE candle whose high point IS the swing extreme.

Visual Reference: base_candle_bullish_valid_invalid_h1.png (XAUUSD H1)
```

**Critical insight from the chart:** One candle is labeled "This is not base candle." The reason: when price reversed from that candle's high, it did NOT break and close below the LOW of that candle. Therefore the swing is invalid (see Section 3 below).

### Bearish Trend — Base Candle = Candle That Creates the LOW

```
In a bearish impulse leg:
  The BASE CANDLE is the candle whose LOW is the swing low.

  SPECIAL RULE: A bearish candle does NOT necessarily need to
  create the low itself. If the next candle's wick creates the
  lower low, we still consider the BEARISH CANDLE as the "low"
  candle (the base candle).

  Reasoning: The bearish candle represents institutional selling.
  The next candle's wick extending lower is just a probe — the
  institutional intent is in the bearish candle.

Visual Reference: base_candle_bearish_valid_invalid_h1.png (XAUUSD H1)
```

### Base Candle Identification Algorithm

```
BULLISH BASE CANDLE:
  1. In a bullish impulse (series of higher highs, higher lows)
  2. Find the candle whose HIGH = the swing high
  3. That candle is the Base Candle
  4. Its zone = [base_candle_low, base_candle_high]

BEARISH BASE CANDLE:
  1. In a bearish impulse (series of lower lows, lower highs)
  2. Find the candle whose LOW = the swing low
  3. Special case: if the next candle's wick is lower but the
     current candle is bearish → the bearish candle is still
     the Base Candle
  4. Its zone = [base_candle_low, base_candle_high]
```

---

## 3. Valid Swing vs Invalid Swing

This is the expert's critical rule that determines whether a swing point qualifies for entry signals.

### The Core Rule

> **A swing is ONLY valid if price breaks the Base Candle's extreme and CLOSES beyond it.**
>
> **If market does not break the Base Candle's extreme and close — it is NOT a valid swing.**
>
> **An invalid swing does NOT qualify for entry.**

### Bullish Swing Validity

```
VALID BULLISH SWING (Swing Low):
  1. Price makes a low (Base Candle creates the low)
  2. Price moves UP from the low
  3. Later, price RETRACES and:
     a. BREAKS below the Base Candle's LOW
     b. And CLOSES below the Base Candle's LOW with a bearish candle
  4. NOW the swing is VALID — it has been confirmed by a break
  5. The level where the break occurred becomes a valid POI

INVALID BULLISH SWING:
  1. Price makes a low (Base Candle creates the low)
  2. Price moves UP
  3. Price retraces but:
     a. Only WICKS below the Base Candle's low, OR
     b. Never reaches the Base Candle's low at all, OR
     c. A two-bar reversal happens but the Base Candle's low
        is NOT broken and closed below
  4. The swing is INVALID — no valid entry signal
```

### Bearish Swing Validity

```
VALID BEARISH SWING (Swing High):
  1. Price makes a high (Base Candle creates the high)
  2. Price moves DOWN from the high
  3. Later, price RETRACES and:
     a. BREAKS above the Base Candle's HIGH
     b. And CLOSES above the Base Candle's HIGH with a bullish candle
  4. NOW the swing is VALID
  5. The level where the break occurred becomes a valid POI

INVALID BEARISH SWING:
  1. Price makes a high (Base Candle creates the high)
  2. Price moves DOWN
  3. Price retraces but:
     a. Only WICKS above the Base Candle's high, OR
     b. Never reaches the Base Candle's high at all, OR
     c. A two-bar reversal happens but the Base Candle's high
        is NOT broken and closed above
  4. The swing is INVALID — no valid entry signal
```

### The "Two-Bar Reversal" Trap

The expert specifically addresses a common disagreement:

> "Some experts say that if a two-bar reversal happens, then it is a valid swing. But as per my observation, until market does not break the low [or high] of the base candle and close with a [bearish/bullish] candle, it is NOT a valid swing and does NOT qualify for entry."

**Our locked rule:** Two-bar reversal alone does NOT confirm swing validity. The Base Candle's extreme MUST be broken and closed beyond.

### Swing Validity Decision Matrix

```
[SWING POINT IDENTIFIED (Base Candle found)]
         │
         ▼
[Did price later break the Base Candle's OPPOSITE extreme?]
         │
    ┌────┴────┐
    │         │
   YES       NO
    │         │
    ▼         ▼
[Did candle CLOSE beyond that extreme?]  [SWING = INVALID]
    │                                     No entry signal
    ┌────┴────┐
    │         │
   YES       NO (wick only)
    │         │
    ▼         ▼
[SWING = VALID]  [SWING = INVALID]
Entry signal     Wick-only = not confirmed
generated        No entry signal
```

---

## 4. Integration with Existing POI Framework

### How Base Candle + Swing Validity Affects POI Detection

The existing POI models (1-7) all require a "confirmed swing" as a precondition. The new rules add a validation gate:

```
EXISTING RULE:
  POI Model requires "Confirmed Swing Low/High"

NEW RULE (ADDS VALIDATION GATE):
  A swing is ONLY confirmed if:
  1. A Base Candle is identified at the extreme
  2. Price later breaks the Base Candle's OPPOSITE extreme
  3. A candle CLOSES beyond that extreme

  If step 2-3 never happens → swing is INVALID → POI cannot form
```

### How CHOCH Types Affect Model 3 (CHOCH Retest)

Model 3 (CHOCH) now has three sub-variants:

```
MODEL 3 SUB-VARIANTS:

  3a — Standard CHOCH (Rule 1):
    Price breaks last HL with body close
    Highest confidence entry
    → Highest strength

  3b — Inside CHOCH Body (Rule 2):
    Price breaks intermediate level with body close
    But last HL is NOT broken
    Medium confidence entry
    → Medium strength

  3c — Inside CHOCH Wick (Rule 3):
    Price wicks beyond intermediate level only
    Lowest strength — KEPT as valid signal
    → Lowest strength — KEPT. No extra confluence gate. Tick-data validation pending.
```

---

## 5. Impact on Flowchart

The flowchart Stage 1 (POI Model Classification) must now include:

```
STAGE 1b: SWING VALIDATION GATE (NEW)
  After identifying a potential swing point:
  1. Find the Base Candle at the extreme
  2. Check if price later broke the Base Candle's opposite extreme
  3. Check if a candle CLOSED beyond that extreme
  4. If YES → Valid swing → Proceed to POI model classification
  5. If NO → Invalid swing → REJECT (no POI can form)

STAGE 1c: CHOCH TYPE CLASSIFICATION (NEW)
  When Model 3 (CHOCH) is detected:
  1. Did price break the LAST SWING? → Rule 1 (Standard)
  2. Did price break an INTERMEDIATE level (not last swing)?
     a. With body close? → Rule 2 (Inside Body)
     b. Wick only? → Rule 3 (Inside Wick)
  3. Record CHOCH type for entry confidence scoring
```

---

## 6. Visual Reference Catalog

| File | Description |
|------|-------------|
| `choch_rule_1_standard_m15.png` | Standard CHOCH (Rule 1) — XAUUSD M15. Price breaks last HL with body close. |
| `choch_rule_2_inside_choch_m1.png` | Inside CHOCH Body (Rule 2) — XAUUSD M1. Breaks intermediate level but not last swing. |
| `choch_rule_3_wick_only_m1.png` | Inside CHOCH Wick (Rule 3) — XAUUSD M1. Only wicks penetrate structural level. |
| `base_candle_bullish_valid_invalid_h1.png` | Base Candle identification in bullish trend — XAUUSD H1. Shows valid and invalid base candles. |
| `base_candle_bearish_valid_invalid_h1.png` | Base Candle identification in bearish trend — XAUUSD H1. Shows valid and invalid base candles. |

---

*This document captures expert teachings from the chart analysis session. It must be integrated into LOCKED_DECISIONS.md and all relevant specification files.*
