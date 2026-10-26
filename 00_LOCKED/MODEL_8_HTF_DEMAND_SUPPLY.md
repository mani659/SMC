# MODEL 8: HTF DEMAND/SUPPLY ZONES (D1/H4)

**Status:** FROZEN — Locked Decision  
**Date Added:** September 1, 2026  
**Source:** Expert chart analysis (5 charts)  
**Priority in Hierarchy:** 8 (lowest — HTF zone model, not structural swing model)

---

## 1. Core Concept

Models 1–7 identify POI based on **structural geometry** (swing breaks, equal highs, quasimodo, etc.) on the detection timeframe. 

**Model 8 is fundamentally different.** It identifies POI on **HTF (D1/H4)** as raw demand/supply zones, order blocks, or FVGs — then uses **LTF (M5/M1) structure** as the entry confirmation trigger. This is a **Multi-Timeframe Confluence Model**, not a single-timeframe structural model.

### Why Model 8 Exists

When price approaches a D1/H4 POI zone, the market does NOT always give a clean structural setup on the detection TF. Instead, price may:
- Wick into the zone and reverse
- Consolidate inside the zone before continuing
- Show entry signals only on much lower timeframes (M5/M1)

Model 8 captures these situations where the **zone itself is the POI** and the **LTF structure is the trigger**.

---

## 2. HTF POI Identification (D1/H4)

### What Counts as HTF POI

| POI Type | Timeframe | Identification |
|----------|-----------|---------------|
| **Order Block (OB)** | D1, H4 | Last opposing candle before a strong impulse move. Bullish = last bearish candle before rally. Supply = last bullish candle before drop. |
| **Fair Value Gap (FVG)** | D1, H4 | 3-candle imbalance where candle 1's high < candle 3's low (bearish) or candle 1's low > candle 3's high (bullish). |
| **Demand Zone** | D1, H4 | **The single last bearish candle before a strong bullish impulsive move.** Zone drawn from high to low of that single opposing candle (full body + wicks). Same as OB but specifically in bullish context. |
| **Supply Zone** | D1, H4 | **The single last bullish candle before a strong bearish impulsive move.** Zone drawn from high to low of that single opposing candle (full body + wicks). Same as OB but specifically in bearish context. |

### Zone Boundaries (Expert — Frozen)

| Element | Bullish (Demand) | Bearish (Supply) |
|---------|-----------------|-----------------|
| **Zone Top** | High of the last bearish candle (base candle) | High of the impulse candle |
| **Zone Bottom** | Low of the last bearish candle (base candle) | Low of the last bullish candle (base candle) |
| **Zone Width** | Full body + wicks of the opposing candle | Full body + wicks of the opposing candle |
| **Preferred Entry** | Upper 50% of zone (closer to top) | Lower 50% of zone (closer to bottom) |

**Key Rule:** The demand zone is NOT the bullish impulse candles — it is the **last opposing (bearish) candle** before the impulse. This is where institutional buy orders were placed. Same logic inverted for supply zones.

### Freshness Rules

- **1-touch rule applies** — same as Models 1–7
- First touch of HTF zone = FRESH
- After price enters zone and exits = TESTED (deactivated)
- Zone is NOT re-activated on subsequent touches

---

## 2b. Formal Demand & Supply Zone Definition (Expert — Frozen)

> **This is the precise, expert-validated definition. Must be used for all Model 8 zone identification.**

### Valid Demand Zone (Daily / H4)
- **Definition:** The **single last bearish candle** that appears just before a strong bullish impulsive move.
- **Zone Boundaries:** Drawn from the **high** to the **low** of that single opposing candle (full body + wicks).
- **NOT the bullish candles** — the demand zone is the last opposing (bearish) candle before the impulse.
- **Freshness Rule:** 1-touch only (same as all models).
- **Result Examples:** 650 pips, 2400 pips buy moves from Daily demand zones.

### Valid Supply Zone (Daily / H4)
- **Definition:** The **single last bullish candle** that appears just before a strong bearish impulsive move.
- **Zone Boundaries:** Drawn from the **high** to the **low** of that single opposing candle (full body + wicks).
- **NOT the bearish candles** — the supply zone is the last opposing (bullish) candle before the impulse.
- **Freshness Rule:** 1-touch only (same as all models).

### Visual Evidence — Demand Zones
- `Expert_Demand_Zone_D1_650pips.png` — Daily demand zone → 650 pip buy move
- `Expert_Demand_Zone_D1_2400pips.png` — Daily demand zone → 2400 pip buy move
- `Expert_Demand_Zone_D1_Wide.png` — Daily demand zone (wider view)

### Visual Evidence — Supply Zones
- `Expert_Supply_Zone_H4_Single.png` — H4 supply zone with clear "supply candle" annotation. Price returned and dropped.
- `Expert_Supply_Zone_H4_Multiple.png` — H4 chart with 3 separate supply zones at different levels. Shows supply zones forming during downtrend.
- `Expert_Supply_Zone_H4_Retracement.png` — H4 supply zone with price retracement into zone and drop.

### Algorithmic Identification
```
DEMAND ZONE (Bullish):
  1. Find a strong bullish impulse move (displacement > 1× ATR)
  2. Look backward from the impulse start
  3. Identify the last bearish candle before the impulse
  4. Zone = [low of that bearish candle, high of that bearish candle]
  5. This is the institutional buy zone

SUPPLY ZONE (Bearish):
  1. Find a strong bearish impulse move (displacement > 1× ATR)
  2. Look backward from the impulse start
  3. Identify the last bullish candle before the impulse
  4. Zone = [low of that bullish candle, high of that bullish candle]
  5. This is the institutional sell zone
```

---

## 3. Multi-Timeframe Execution Flow

### The 3-Step Process

```
STEP 1: HTF SCAN (D1 or H4)
    → Identify OB, FVG, Demand/Supply zones
    → Mark zone boundaries (top/bottom)
    → Check freshness (1-touch rule)
    → Confirm zone is FRESH
         │
         ▼
STEP 2: LTF APPROACH (M5)
    → Wait for price to enter the HTF zone
    → Watch for structural signs on M5:
       • Price reaching zone top/bottom
       • M5 showing momentum slowing
       • M5 starting to form structure (higher lows in demand, lower highs in supply)
    → DO NOT enter yet — this is the "approach" phase
         │
         ▼
STEP 3: EXECUTION TF TRIGGER (M1)
    → Look for entry confirmation:
       • Ending Diagonal completion (5-wave wedge)
       • BOS (Break of Structure) on M1
       • Two-Bar Reversal at zone level
       • CHOCH on M1 confirming reversal
    → Entry at trigger point
    → SL below/above the M1 structure (very tight)
```

### Timeframe Responsibilities

| Timeframe | Role | What It Does |
|-----------|------|-------------|
| **D1 / H4** | **POI Discovery** | Identifies zones (OB, FVG, Demand/Supply). Does NOT generate entry signals. |
| **M5** | **Approach Monitoring** | Watches price enter the zone. Identifies structural approach. Does NOT generate entry signals. |
| **M1** | **Entry Trigger** | Generates the actual entry signal (Ending Diagonal, BOS, Two-Bar, CHOCH). Tight SL placement. |

---

## 4. Entry and Risk Management

### Entry Rules

| Parameter | Rule |
|-----------|------|
| **Entry Type** | Limit order at trigger level (NOT market order) |
| **Entry Trigger** | M1 structural confirmation (Ending Diagonal, BOS, Two-Bar, CHOCH) |
| **Entry Zone** | Within the D1/H4 marked zone (OB/FVG/Demand/Supply) |
| **SL Placement** | Below M1 structure (for buys) / Above M1 structure (for sells) — TIGHT |
| **SL Width** | Typically 2-5 pips (M1-based, not HTF-based) |
| **RR Target** | Minimum 1:3 (because SL is so tight, RR is naturally high) |

### Why This Model Excels

| Advantage | Explanation |
|-----------|-------------|
| **Tight SL** | SL is based on M1 structure, not D1/H4 zone width. A D1 OB might be 50+ pips wide, but M1 SL is 2-5 pips. |
| **High RR** | Tight SL + HTF target = naturally high risk-reward ratio |
| **Zone Confluence** | Entry is backed by HTF institutional interest (OB/FVG/Demand/Supply) |
| **Precise Timing** | M1 trigger eliminates guesswork about "when" to enter the zone |

### Risk Considerations

| Risk | Mitigation |
|------|-----------|
| **False M1 signals** | Only take M1 triggers that occur WITHIN the HTF zone (not outside) |
| **Zone penetration** | If price closes beyond zone bottom (demand) or zone top (supply), zone is invalidated |
| **News events** | Hard cancel all pending limits 15 min before high-impact news |
| **Multiple HTF zones** | If D1 and H4 zones overlap → highest confluence. If zones conflict → no trade. |

---

## 5. Model 8 vs Models 1–7

| Aspect | Models 1–7 | Model 8 |
|--------|-----------|---------|
| **POI Source** | Structural geometry on detection TF | Raw zones on HTF (D1/H4) |
| **POI Types** | CHOCH, QML, Equal Highs, Neckline, Breaker, Origin | OB, FVG, Demand/Supply |
| **Detection TF** | H4/H1/M30 (frozen per locked decisions) | D1, H4 |
| **Entry TF** | Same as detection TF or 1 TF lower | M1 (2-4 TFs lower) |
| **SL Basis** | Structure on detection TF | Structure on M1 |
| **SL Width** | 10-30 pips typical | 2-5 pips typical |
| **RR Profile** | 1:2 to 1:4 typical | 1:5 to 1:10+ typical |
| **Subjectivity** | Moderate (pattern recognition) | Low on HTF (zones are objective), moderate on M1 (trigger selection) |

---

## 6. Trigger Compatibility

Model 8 uses the **same 6 triggers** as Models 1–7, but ONLY on M1:

| Trigger | Compatible with Model 8 | Notes |
|---------|:-----------------------:|-------|
| **A: Leading Diagonal** | ✅ | 5-wave wedge completion at HTF zone |
| **B: Ending Diagonal** | ✅ | PREFERRED — most common M1 trigger at HTF zone (shown in expert chart) |
| **C: Two-Bar Reversal** | ✅ | Limit at 50% of engulfing body |
| **D: BOS** | ✅ | M1 break of structure within zone |
| **E: CHOCH** | ✅ | M1 CHOCH at zone level |
| **F: Fair Value Gap** | ✅ | M1 FVG entry within HTF zone |

---

## 7. Scoring

Model 8 scores on the same 5 pillars but with HTF zone weighting:

| Pillar | Weight | Scoring |
|--------|:------:|---------|
| 1. Zone Tolerance | 25% | Price within ±0.5× ATR of zone center |
| 2. Premium/Discount | 20% | Buys < 45% of zone, Sells > 55% of zone |
| 3. M1 Trigger Quality | 25% | Which M1 trigger fired (B highest, A/C/D/E/F standard) |
| 4. HTF Zone Freshness | 15% | 1-touch only (same as all models) |
| 5. Inducement | 15% | Soft score — 100% with inducement, 70% without |

**Model 8 scoring bonus:** +10% if D1 and H4 zones overlap at the same level.

---

## 8. Detection Algorithm

```python
# Model 8: HTF Demand/Supply Detection

def detect_model_8(d1_data, h4_data, current_price):
    """
    Detect HTF Demand/Supply zones on D1 and H4.
    Returns list of fresh zones with boundaries.
    """
    zones = []
    
    # Scan D1 for OB, FVG, Demand/Supply
    d1_zones = scan_htf_zones(d1_data, timeframe="D1")
    
    # Scan H4 for OB, FVG, Demand/Supply
    h4_zones = scan_htf_zones(h4_data, timeframe="H4")
    
    # Combine and check freshness
    all_zones = d1_zones + h4_zones
    
    for zone in all_zones:
        if zone.touch_count == 0:  # FRESH
            zones.append(zone)
    
    return zones

def scan_htf_zones(data, timeframe):
    """
    Identify OB, FVG, Demand/Supply zones on given timeframe.
    """
    zones = []
    
    # Order Block detection
    obs = detect_order_blocks(data)
    zones.extend(obs)
    
    # FVG detection
    fvgs = detect_fvgs(data)
    zones.extend(fvgs)
    
    # Demand/Supply zone detection
    ds_zones = detect_demand_supply(data)
    zones.extend(ds_zones)
    
    return zones

def detect_order_blocks(data):
    """
    OB = Last opposing candle before strong impulse.
    Bullish OB = Last bearish candle before bullish impulse.
    Bearish OB = Last bullish candle before bearish impulse.
    """
    obs = []
    for i in range(2, len(data)):
        # Bullish OB: bearish candle followed by strong bullish move
        if (data[i-1].close < data[i-1].open and  # bearish candle
            data[i].close > data[i].open and        # bullish candle
            data[i].body > 2 * data[i-1].body):     # impulse
            obs.append({
                "type": "bullish_ob",
                "top": data[i-1].high,
                "bottom": data[i-1].low,
                "timeframe": timeframe
            })
        
        # Bearish OB: bullish candle followed by strong bearish move
        if (data[i-1].close > data[i-1].open and  # bullish candle
            data[i].close < data[i].open and        # bearish candle
            data[i].body > 2 * data[i-1].body):     # impulse
            obs.append({
                "type": "bearish_ob",
                "top": data[i-1].high,
                "bottom": data[i-1].low,
                "timeframe": timeframe
            })
    
    return obs

def detect_demand_supply(data):
    """
    Demand Zone = Last bearish candle before strong bullish impulse.
    Supply Zone = Last bullish candle before strong bearish impulse.
    Zone = full body + wicks of the opposing candle.
    """
    zones = []
    for i in range(1, len(data)):
        # Demand: bearish candle followed by strong bullish impulse
        if (data[i-1].close < data[i-1].open and  # bearish candle
            data[i].close > data[i].open and        # bullish candle
            data[i].body > 1.5 * atr(data, i)):     # strong impulse
            zones.append({
                "type": "demand",
                "top": data[i-1].high,   # high of bearish candle
                "bottom": data[i-1].low,  # low of bearish candle
                "timeframe": timeframe
            })
        
        # Supply: bullish candle followed by strong bearish impulse
        if (data[i-1].close > data[i-1].open and  # bullish candle
            data[i].close < data[i].open and        # bearish candle
            data[i].body > 1.5 * atr(data, i)):     # strong impulse
            zones.append({
                "type": "supply",
                "top": data[i-1].high,   # high of bullish candle
                "bottom": data[i-1].low,  # low of bullish candle
                "timeframe": timeframe
            })
    
    return zones
```

---

## 9. Expert Chart Evidence

| Chart | TF | What It Shows | Model 8 Element |
|-------|-----|---------------|-----------------|
| D1 Overview | D1 | Multiple OBs and a Demand zone marked with orange boxes | HTF POI identification |
| D1 FVG Detail | D1 | Specific FVG with blue lines showing gap boundaries | FVG as HTF POI |
| M5 Approach | M5 | Price approaching the HTF zone with horizontal lines marking zone boundaries | Step 2: LTF approach monitoring |
| M1 Trigger | M1 | Ending Diagonal (waves 1-5) completing at the HTF zone | Step 3: Execution trigger |
| H4 Zones | H4 | Multiple OBs and Supply/Demand zones marked | Secondary HTF scanning timeframe |
| D1 Demand 650pips | D1 | Last bearish candle before bullish impulse → 650 pip buy move | Formal Demand Zone definition |
| D1 Demand 2400pips | D1 | Last bearish candle before bullish impulse → 2400 pip buy move | Formal Demand Zone definition |
| D1 Demand Wide | D1 | Wider view of Daily demand zone structure | Formal Demand Zone definition |
| H4 Supply Single | H4 | Last bullish candle before bearish impulse — single zone | Formal Supply Zone definition |
| H4 Supply Multiple | H4 | 3 separate supply zones at different levels during downtrend | Formal Supply Zone definition |
| H4 Supply Retracement | H4 | Supply zone with price retracement into zone and drop | Formal Supply Zone definition |

---

## 10. Key Distinction from Existing Models

> **Models 1–7 = "What is the structure?"** (Pattern recognition on detection TF)  
> **Model 8 = "Where is the zone?"** (Zone identification on HTF + LTF trigger)

Model 8 does NOT require any structural pattern to form on the HTF. It only requires:
1. A valid zone exists on D1/H4
2. The zone is fresh (1-touch rule)
3. Price enters the zone
4. M1 shows a structural trigger

This makes Model 8 the most **zone-based** and least **pattern-based** of all 8 models.
