# SMC PURE ENTRY MODULES SPECIFICATION

> **⚠️ LOCKED DECISIONS APPLIED** — This document is aligned with `SMC_RESEARCH/LOCKED_DECISIONS.md` (2026-09-01). The 3 original pure entry models are now superseded by the full 8 POI + 6 Trigger architecture.

This document outlines the **3 Pure Entry Models** derived strictly from our discussion, the uploaded chart images, and the expert's rules. 

**Scope:** 100% focused on **Trade Entries & Execution Triggers** (No exits, no trade management, no SL trailing, no breakeven logic).

> **Note:** These 3 models have been expanded into the full **8 POI Models + 6 LTF Entry Triggers** architecture in `SMC_RESEARCH/SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md` and `SMC_RESEARCH_ARCHIVE/13_POI_VALIDATION_FRAMEWORK.md`. Model 8 (HTF Demand/Supply) is a multi-timeframe zone model added 2026-09-01. See `LOCKED_DECISIONS.md` for all frozen parameters.

---

## Master Entry Prerequisite: Liquidity Sweep

Before any of the 3 entry models can execute, price must interact with a defined **Liquidity Pool** (full Stage 0A taxonomy per `LOCKED_DECISIONS.md` Section 2):
* **Macro Targets:** Session Highs/Lows (Asia, London, New York), Previous Day High/Low (PDH/PDL), Previous Week High/Low (PWH/PWL).
* **Micro Targets:** Equal Highs/Lows (EQH/EQL — both top & bottom, ≤ 4.5 pips), Structural Swing Highs/Lows (Base Candle gate — only structural swings count).
* **POI & Zone Sweeps:** Any OB sweep or FVG sweep at a POI is itself a liquidity sweep. If Demand/Supply or an Order Block gives no in-between entry, the engine waits for the zone/OB extreme boundary sweep.
* **The Sweep Rule:** Price must pierce the level to grab Buy-Side Liquidity (BSL) or Sell-Side Liquidity (SSL) and immediately show displacement.
* **Smart Money Edge:** Retail stops are hunted first; once eaten, market does not return to re-hunt swept levels (post-sweep entries carry structural protection).

---

## MODEL 1: FVG Imbalance Entry Model (Image 1)
*Best for: High-momentum trend continuation and fast impulse legs.*

### Execution Logic & Steps:
1. **Sweep / Trend Extension:** Price raids liquidity or breaks a local swing level.
2. **Displacement:** An aggressive impulse candle forms in the intended direction.
3. **FVG Creation:** A valid 3-candle Fair Value Gap is created:
   * **Bullish FVG:** Candle 3 Low > Candle 1 High.
   * **Bearish FVG:** Candle 3 High < Candle 1 Low.
4. **Retracement:** Price pulls back into the open FVG area.
5. **ENTRY TRIGGER:** 
   * **Buy/Sell Limit Order** placed at the **50% FVG Midpoint** (or touch of the top boundary).
   * **Order Type:** Limit Order.

---

## MODEL 2: CHOCH Base Reversal Model (Image 2)
*Best for: Major trend reversals occurring at Session/Daily/Weekly Highs and Lows.*

### Execution Logic & Steps:
1. **Exhaustion Sweep:** In an established trend (e.g., uptrend), price sweeps the final Higher High (HH).
2. **Change of Character (CHOCH):** A strong displacement move breaks below the previous Higher Low (HL) (or above the Lower High in a downtrend).
3. **Supply / Demand Zone Formation:** The origin of the CHOCH drop forms a fresh Supply Zone (or Demand Zone for longs).
4. **Retracement:** Price conducts a corrective pullback into the newly formed Supply/Demand Zone.
5. **ENTRY TRIGGER:**
   * **Sell Entry (for Bearish CHOCH)** upon price tapping into the Supply Zone.
   * **Buy Entry (for Bullish CHOCH)** upon price tapping into the Demand Zone.
   * **Order Type:** Limit Order (set & forget on first touch). Always drop to M1/M5 for LTF trigger confirmation.

---

## MODEL 3: Order Block (OB) / BOS Continuation Model (Image 3)
*Best for: Steady trending markets with clear institutional swing structure.*

### Execution Logic & Steps:
1. **Break of Structure (BOS):** Price breaks a previous swing high (in uptrend) confirming trend continuation.
2. **Order Block Isolation:** Identify the last opposing candle (e.g., last bearish candle before the bullish breakout) at the base of the impulse.
3. **Mitigation Retracement:** Price returns downward to "mitigate" (re-test) the unmitigated Order Block.
4. **ENTRY TRIGGER:**
   * **Buy Limit Order** placed at the top edge/equilibrium of the Bullish Order Block.
   * **Sell Limit Order** placed at the bottom edge/equilibrium of the Bearish Order Block.
   * **Order Type:** Limit Order on OB touch.

---

## Pure Entry Decision Matrix

| Metric | Model 1 (FVG) | Model 2 (CHOCH) | Model 3 (Order Block) |
| :--- | :--- | :--- | :--- |
| **Market Condition** | Fast Momentum & Impulse | Macro Reversals & Exhaustion | Steady Structural Trends |
| **Primary Trigger** | 3-Bar Imbalance Gap | Higher Low / Lower High Break | Swing High/Low BOS Break |
| **Execution Zone** | 50% FVG Midpoint | Supply / Demand Base Zone | Unmitigated Order Block (OB) |
| **Speed to Fill** | Fastest | Medium (Waits for full HL break) | Slower (Deep mitigation) |
| **Image Reference** | Image 1 (M15 FVG Model) | Image 2 (M15 CHOCH Model) | Image 3 (H1 OB Model) |
