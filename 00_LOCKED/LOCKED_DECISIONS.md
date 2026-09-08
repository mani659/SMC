# LOCKED DECISIONS — SMC POI & Flowchart Source of Truth

**Date Locked:** 2026-09-01
**Status:** FROZEN — Do not change without explicit session authorization
**Authoritative For:** All POI detection, validation, trigger routing, and execution logic

---

## 1. Modular Multi-Model Confluence System (REPLACES old priority hierarchy)

**All 8 POI models are equal tags.** There is NO hard ranking or priority hierarchy. Multiple models can label the same price level simultaneously. The more independent models that align on one level, the higher the quality score.

### The 8 Equal POI Tags

| Tag | Model | What It Identifies |
|:---:|-------|-------------------|
| **M1** | Origin Demand/Supply Base | Simplest structural retest at origin level |
| **M2** | RBS/SBR Breaker | Generic broken level retest from opposite side |
| **M3** | CHOCH Retest | Sweep + trend shift + retest of broken level |
| **M4** | Quasimodo (QML) | Multi-swing asymmetric reversal with head/shoulder geometry |
| **M5** | Extreme Equal Highs / Supply Origin | Continuation setup at engineered liquidity extremes |
| **M6** | Neckline / Double Top-Bottom | Pattern-specific broken level retest |
| **M7** | Equal Resistance Shelf | Reactive shelf retest after expansion |
| **M8** | HTF Demand/Supply (D1/H4) | Multi-timeframe zone — OB/FVG/Demand/Supply on D1/H4 → M1 trigger |

### Confluence Scoring Rule
- Each model that independently tags a price level adds to the quality score
- **1 model tag** = base quality (tradeable)
- **2 model tags** = elevated quality (preferred)
- **3+ model tags** = highest quality (institutional-grade confluence)
- **No model is suppressed** because another model is also present
- **Model 8 is a full peer** — it can combine with any of Models 1–7

### When Multiple Models Tag the Same Level
- All tags are recorded
- Quality score = f(number of independent tags)
- Execution still uses chronological trigger selection (Section 12)
- No model "wins" or "overrides" another — they coexist as confluence

---

## 2. Master Liquidity Levels & Structural Sweep Architecture (Stage 0A Master Classification)

These are the ONLY valid liquidity levels for sweep detection in Stage 0A:

| Level Type | Structural Definition | Directional Pool | Timeframe |
|------------|-----------------------|------------------|-----------|
| **Session Highs/Lows** | Asia (00:00–07:00), London (07:00–13:00), NY (13:00–20:00 UTC) | BSL (High) / SSL (Low) | Session TF |
| **PDH/PDL** | Previous Day High/Low | BSL (High) / SSL (Low) | Daily |
| **PWH/PWL** | Previous Week High/Low | BSL (High) / SSL (Low) | Weekly |
| **EQH/EQL (Top & Bottom)** | Equal Highs (BSL) / Equal Lows (SSL) — double/triple tops/bottoms (≤ 4.5 pips tolerance on XAUUSD) | BSL & SSL Pools | Detection TF |
| **Structural Swing High/Low** | **Strictly structural swings** confirmed by Base Candle validity gate (ignoring minor non-structural noise) | Major Structural BSL / SSL | Detection TF |
| **POI Level Sweeps (OB & FVG)** | Wick sweep through POI Order Block or FVG boundary | POI Liquidity Pool | POI TF |
| **Demand & Supply Boundary Sweeps** | Fallback sweep when price does not offer an in-between mitigation entry inside the zone body | Extreme Zone Liquidity | D1 / H4 / H1 |
| **Order Block Boundary Sweeps** | Fallback sweep when price passes through OB body without internal mitigation entry | OB Extreme Liquidity | Detection TF |

### Institutional Sweep Principles & Stop-Loss Hunting Mechanics (Stage 0A Master Law)
1. **Structural Liquidity Missing at 0A Restored:** Prior models lacked explicit structural swing gating. In Stage 0A, liquidity pools are now explicitly structural, directly tied to confirmed base candles. (Expert-confirmed 2026-09-05: the 0A stage must explicitly identify structural liquidity — generic fractal levels do not qualify until Base-Candle-confirmed.)
2. **Equal Highs / Equal Lows Both Top & Bottom:** Retail stop orders cluster heavily above resistance shelves and below support floors. Both sides are tracked concurrently.
3. **Only Structural Swings Considered:** Minor internal fractals are discarded. A swing high/low only exists if the Base Candle opposite extreme was broken with a body close.
4. **POI Sweeps Count as Liquidity Sweeps:** An OB or FVG being pierced and rejected at a POI is itself classified as an institutional liquidity sweep.
5. **Demand & Supply Fallback Sweeps (No In-Between Entry):** If price approaches an HTF Demand/Supply zone and does not give a clean mitigation entry in between the zone limits, the setup is **not invalidated**. The engine shifts focus to a **boundary sweep** of the zone extreme to capture institutional reversal.
6. **Order Block Fallback Sweeps:** If price blows through the upper/lower boundary of an OB without an in-between entry, the engine monitors for the **OB sweep** (wick sweep of the extreme base candle wick).
7. **Smart Money Stop-Loss Hunting Edge:** Smart money intentionally targets retailer stops placed tightly outside obvious technical levels (EQH/EQL, OB edges, D/S zones). Once the market has "eaten all retailers," smart money has filled its institutional orders and begins the true move. Because the retail stop pool is exhausted, market will not return to hunt previously swept levels, providing high structural protection for the trade.

**EQH/EQL Tolerance:** ≤ 4.5 pips on XAUUSD (FROZEN)

### Visual Evidence (Expert Charts — 2026-09-05)
| Chart | What It Shows |
|-------|---------------|
| `liquidity_sweep_eq_high_swing_low_h1.png` | EQH sweep at top (BSL) + consecutive structural swing low sweeps at bottom (SSL) — H1 |
| `liquidity_sweep_equal_highs_h1.png` | Equal High sweep — retail stop trap above a resistance shelf — H1 |
| `liquidity_sweep_swing_highs_h1.png` | Successive structural swing high sweeps during a downtrend — H1 |
| `liquidity_sweep_major_high_h1.png` | Major structural high sweep with rejection wick — H1 |
| `liquidity_sweep_high_and_low_range_h1.png` | Top AND bottom sweeps within a range (full liquidity cleansing) — H1 |
| `liquidity_sweep_structural_swing_low_m15.png` | Structural swing low sweep — LTF validation — M15 |

All charts are in `Knowledge Base/` and cataloged in `Knowledge Base/README.md` Section 7.

---

## 3. Displacement Requirements

- **Minimum displacement:** 1× ATR
- **Required confirmations:** BOS (close beyond prior swing) + FVG (3-candle imbalance gap)
- **Hard fail threshold:** Displacement < 0.5× ATR
- **Preferred threshold:** Displacement > 1.5× ATR (strong institutional sponsorship)

---

## 4. Detection Timeframe Architecture

| Timeframe | Role | Models Detected |
|-----------|------|----------------|
| **Daily** | Macro context | Models 1, 3, 4 (major reversals) |
| **H4** | Primary workhorse | Models 1, 3, 5 (medium-term) |
| **H1** | All models | All 8 models (most events, balances granularity) |
| **M30** | Intraday | Models 2, 5, 6, 7 (faster detection, more noise) |

---

## 5. Freshness Rules

- **Strict 1-touch only:** STATE_FRESH → STATE_TESTED (deactivated forever)
- **No second-touch trades:** Once price touches a POI zone, it is deactivated for new entries
- **State machine:**
  ```
  STATE_CREATED → STATE_FRESH → STATE_TESTED → (no return)
  STATE_CREATED → STATE_FRESH → STATE_VIOLATED (if closed beyond without touching)
  ```
- **Unfilled limit orders:** Expire after N bars AND mark POI as STATE_TESTED
  - **M5 timeframe:** 12 bars (1 hour)
  - **M1 timeframe:** 30 bars (30 minutes)

---

## 6. Dealing Range / Premium-Discount

- **Coupled to POI detection TF:** If POI detected on H1, use H1 dealing range
- **Bullish POIs:** Must be in Discount zone (< 45% of dealing range)
- **Bearish POIs:** Must be in Premium zone (> 55% of dealing range)
- **Equilibrium exclusion:** 45%–55% = REJECT (consolidation trap)
- **Buys < 45%, Sells > 55%** — strictly enforced

---

## 7. Inducement Scoring

- **Soft score only** — never hard reject
- **With inducement present:** 100% score
- **Without inducement:** 70% score (still tradeable, ranked below 100%)
- **Inducement types:** EQH/EQL, trendline, or minor swing directly in front of POI

---

## 8. Model 5 Definition

- **Type:** Continuation setup (NOT reversal)
- **Entry:** At the broken equal level
- **Distinguished from Model 7:** Model 5 is proactive (extreme equal highs/lows formed first, then broken); Model 7 is reactive (bounce creates resistance shelf, then broken)
- **Model 5 = equal peaks within an extreme zone (EQH/EQL, ≤ 4.5 pips tolerance); Model 7 = equal peaks from reactive shelf formation (H2 ≈ H1, variable tolerance)**

---

## 9. CHOCH Entry Rules

- **Entry placement:** At the broken structural level (NOT the origin OB)
- **CHOCH confirmation:** Requires candle body close beyond the structural level (wick pierce alone is insufficient)
- **SL placement:** Above/below the liquidity sweep extreme (Head)

---

## 10. Two-Bar Reversal Entry

- **Order type:** Limit order at 50% of the engulfing body
- **NOT market order** — deterministic and testable

---

## 11. News Protocol

- **Hard cancel** all pending POI limit orders 15 minutes before high-impact news
- **High-impact events:** US CPI, NFP, FOMC
- **Re-evaluate:** After news dust settles (typically 30 minutes post-release)

---

## 12. Trigger Selection

- **Chronological:** First valid LTF trigger wins
- **NOT priority-based:** Whatever trigger pattern completes first in time is the one that fires
- **Event identity:** One validated POI (may have multiple model tags) + one LTF trigger + one execution

---

## 13. Zone Refinement Tolerance

- **±0.5× ATR** (adaptive, not fixed points)
- Applied to Pillar 1 of the POI Validation Pipeline

---

## 14. QML Left Shoulder Anchor

- **Full wick range:** [left_shoulder_low, left_shoulder_high]
- This captures the entire institutional zone

---

## 15. POI × Trigger Compatibility Matrix

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

---

## 16. The 5-Stage Master Flowchart Pipeline

```
STAGE 0: Liquidity Sweep Detection → Displacement Check
    ↓
STAGE 0b: SWING VALIDATION GATE (NEW — Base Candle rule)
    ↓
STAGE 1: POI Model Classification (modular tags: M1–M8, all equal, confluence scored)
    ↓
STAGE 1b: CHOCH Type Classification (Rule 1/2/3)
    ↓
STAGE 2: POI Validation (5 Pillars: Zone Refinement, Displacement, Premium/Discount, Freshness, Inducement)
    ↓
STAGE 3: Trigger Routing (chronological first-valid trigger on M1/M5)
    ↓
STAGE 4: Execution Engine (news check → lot sizing → limit order → PureRunner management)
```

---

## 17. Three Types of CHOCH (Expert — NEW)

The expert teaches three distinct CHOCH types. Two are "Inside CHOCH" variants where price does NOT break the last structural swing.

### CHOCH Rule 1: Standard CHOCH (Body Close Break)
- Price breaks and **candle body closes** beyond the **last swing** of the main trend
- Bearish: Uptrend → HH sweep → body close below last HL
- Bullish: Downtrend → LL sweep → body close above last LH
- **Strength: Highest** — clean structural break of main trend level
- **Visual:** `choch_rule_1_standard_m15.png`

### CHOCH Rule 2: Inside CHOCH — Body Close (No Last Swing Break)
- Price enters POI, forms an **intermediate structure** inside the correction
- Price breaks and **candle body closes** beyond an **intermediate level** — but the **last swing of the main trend is NOT broken**
- **Strength: Medium** — structural break happens inside the correction
- **Visual:** `choch_rule_2_inside_choch_m1.png`

### CHOCH Rule 3: Inside CHOCH — Wick Only (Weakest)
- Price enters POI, intermediate structure forms
- Price **wicks beyond** a structural level but **candle body does NOT close** beyond
- Only wicks penetrate — no structural commitment
- **Strength: Lowest — KEPT in the system.** Valid signal at lowest strength. Will be validated or invalidated later with tick-data testing.
- **Visual:** `choch_rule_3_wick_only_m1.png`

### CHOCH Strength Ranking
| Rule | Type | Breaks | Confirmation | Strength |
|:----:|------|--------|-------------|:--------:|
| 1 | Standard | Last swing | Body close | Highest |
| 2 | Inside (Body) | Intermediate level | Body close | Medium |
| 3 | Inside (Wick) | Intermediate level | Wick only | Lowest |

### Model 3 Sub-Variants (CHOCH Type Classification)
| Sub-Variant | Strength | Extra Requirements |
|:-----------:|:--------:|-------------------|
| 3a (Rule 1 — Standard) | Highest | None — standard entry |
| 3b (Rule 2 — Inside Body) | Medium | None — standard entry |
| 3c (Rule 3 — Inside Wick) | Lowest — KEPT | Valid signal at lowest strength. No extra confluence gate. Tick-data validation pending. |

---

## 18. Base Candle Definition (Expert — NEW)

A **Base Candle** is the candle that creates the structural extreme (high or low) at a swing point.

### Bullish Trend
- Base Candle = candle whose **HIGH** is the swing high
- NOT the candle before or after — the ONE candle whose high IS the extreme

### Bearish Trend
- Base Candle = candle whose **LOW** is the swing low
- **Special rule:** A bearish candle does NOT need to create the low itself. If the next candle's wick creates the lower low, we still consider the **bearish candle** as the Base Candle (institutional selling intent)

### Base Candle Identification Algorithm
```
BULLISH: Find candle whose HIGH = swing high → that is the Base Candle
BEARISH: Find candle whose LOW = swing low → Base Candle
         (exception: if next candle wick is lower but current is bearish,
          the bearish candle is still the Base Candle)
```

### Visual References
- `base_candle_bullish_valid_invalid_h1.png` — Bullish base candles with valid/invalid labels
- `base_candle_bearish_valid_invalid_h1.png` — Bearish base candles with valid/invalid labels

---

## 19. Valid Swing vs Invalid Swing (Expert — NEW)

> **CORE RULE: A swing is ONLY valid if price breaks the Base Candle's OPPOSITE extreme and CLOSES beyond it. If market does not break the Base Candle's extreme and close — it is NOT a valid swing and does NOT qualify for entry.**

### Bullish Swing Validity
- **VALID:** Price later retraces → breaks below Base Candle's LOW → candle CLOSES below that low → swing confirmed
- **INVALID:** Price only wicks below Base Candle's low (no close), OR never reaches it, OR two-bar reversal happens but Base Candle's low is NOT broken and closed below

### Bearish Swing Validity
- **VALID:** Price later retraces → breaks above Base Candle's HIGH → candle CLOSES above that high → swing confirmed
- **INVALID:** Price only wicks above Base Candle's high (no close), OR never reaches it, OR two-bar reversal happens but Base Candle's high is NOT broken and closed above

### The "Two-Bar Reversal" Trap (Expert Explicitly Addresses This)
> "Some experts say that if two-bar reversal happens then it is valid swing. But as per my observation, until market did not break low [or high] of base candle and close with bearish [or bullish] candle it is not valid swing and does not qualify for entry."

**Locked Rule:** Two-bar reversal alone does NOT confirm swing validity. Base Candle extreme MUST be broken and closed beyond.

### Swing Validity Decision Gate
```
[SWING POINT IDENTIFIED (Base Candle found)]
         │
         ▼
[Did price later break Base Candle's OPPOSITE extreme?]
         │
    ┌────┴────┐
   YES       NO → SWING = INVALID (no POI)
    │
    ▼
[Did candle CLOSE beyond that extreme?]
         │
    ┌────┴────┐
   YES       NO (wick only) → SWING = INVALID (no POI)
    │
    ▼
[SWING = VALID → POI can form]
```

---

## 20. CHOCH Entry Adjustment for Inside CHOCH (Rule 2 & 3)

For Inside CHOCH variants (Rule 2 and Rule 3), the entry placement adjusts:

- **Rule 1 (Standard):** Entry at the broken last HL/LH level (existing spec — unchanged)
- **Rule 2 (Inside Body):** Entry at the broken INTERMEDIATE level (not the last swing, since it wasn't broken)
- **Rule 3 (Inside Wick):** Entry at the wick-pierced level. Lowest strength but KEPT. Validated later with tick-data testing.

---

## 21. Model 8: HTF Demand/Supply Zones (D1/H4) — NEW

### Core Concept
Model 8 is a **Multi-Timeframe Confluence Model**. Unlike Models 1–7 (which identify POI via structural geometry on a single detection TF), Model 8 identifies POI as **raw zones on HTF (D1/H4)** and uses **LTF (M5/M1) structure** as the entry confirmation trigger.

### HTF POI Types
| Type | Timeframe | Identification |
|------|-----------|---------------|
| Order Block (OB) | D1, H4 | Last opposing candle before strong impulse |
| Fair Value Gap (FVG) | D1, H4 | 3-candle imbalance gap |
| **Demand Zone** | **D1, H4** | **The single last bearish candle before a strong bullish impulse.** Zone = full high-to-low range of that single opposing candle. (Expert — Frozen) |
| **Supply Zone** | **D1, H4** | **The single last bullish candle before a strong bearish impulse.** Zone = full high-to-low range of that single opposing candle. (Expert — Frozen) |

**Key Rule:** Demand/Supply zones are the **last opposing candles** before the impulse — NOT the impulse candles themselves. This is where institutional orders were placed.

### 3-Step Execution
```
STEP 1: HTF SCAN (D1/H4) — Identify OB, FVG, Demand/Supply zones
STEP 2: LTF APPROACH (M5) — Wait for price to enter zone, watch structural approach
STEP 3: EXECUTION TF (M1) — Entry trigger (Ending Diagonal preferred, BOS, Two-Bar, CHOCH)
```

### Timeframe Responsibilities
| Timeframe | Role |
|-----------|------|
| D1 / H4 | POI Discovery (zones only, no entry signals) |
| M5 | Approach Monitoring (price enters zone, structural signs) |
| M1 | Entry Trigger (actual signal, tight SL placement) |

### Entry Rules
- **Entry:** Limit order at M1 trigger level (within HTF zone)
- **SL:** Below/above M1 structure (2–5 pips typical)
- **RR Target:** Minimum 1:5 (tight SL → naturally high RR)
- **Freshness:** 1-touch rule applies (same as Models 1–7)
- **Zone boundaries:** Top/bottom of OB, FVG, or Demand/Supply area

### Scoring
- Same 5 pillars as Models 1–7 with HTF zone weighting
- **Bonus (quality-score only):** +0.10 added to confluence quality score if D1 and H4 Demand/Supply zones overlap at the same level (flag `htf_overlap = true`). This does NOT change position size.
- All 6 triggers compatible (Ending Diagonal preferred at M1)

### Model 8 vs Models 1–7
| Aspect | Models 1–7 | Model 8 |
|--------|-----------|---------|
| POI Source | Structural geometry on detection TF | Raw zones on HTF |
| POI Types | CHOCH, QML, EQH, Neckline, Breaker, Origin | OB, FVG, Demand/Supply |
| Detection TF | H4/H1/M30 | D1, H4 |
| Entry TF | Same or 1 TF lower | M1 (2–4 TFs lower) |
| SL Width | 10–30 pips | 2–5 pips |
| RR Profile | 1:2 to 1:4 | 1:5 to 1:10+ |

### Confluence Role
Model 8 is a **full peer** in the modular system. It can combine with any of Models 1–7 on the same price level. For example, a D1 Demand Zone (M8) overlapping with a CHOCH Retest (M3) at the same level = 2-model confluence = elevated quality score.

### Key Distinction
> Models 1–7 = "What is the structure?" (Pattern recognition on detection TF)
> Model 8 = "Where is the zone?" (Zone identification on HTF + LTF trigger)
> **All are equal tags. Confluence of multiple tags = higher quality.**

---

## 22. Formal Demand & Supply Zone Definition (Expert — Frozen)

> **This definition supersedes any previous Demand/Supply zone descriptions. Use this for all Model 8 zone identification.**

### Valid Demand Zone (Daily / H4)
- **Definition:** The **single last bearish candle** that appears just before a strong bullish impulsive move.
- **Zone Boundaries:** Drawn from the **high** to the **low** of that single opposing candle (full body + wicks).
- **NOT the bullish candles** — the demand zone is the last opposing (bearish) candle before the impulse.
- **Freshness Rule:** 1-touch only (same as all models).
- **Evidence:** 650 pip and 2400 pip buy moves from Daily demand zones.

### Valid Supply Zone (Daily / H4)
- **Definition:** The **single last bullish candle** that appears just before a strong bearish impulsive move.
- **Zone Boundaries:** Drawn from the **high** to the **low** of that single opposing candle (full body + wicks).
- **NOT the bearish candles** — the supply zone is the last opposing (bullish) candle before the impulse.
- **Freshness Rule:** 1-touch only (same as all models).

### Algorithmic Identification
```
DEMAND ZONE (Bullish):
  1. Find a strong bullish impulse move (displacement > 1× ATR)
  2. Look backward from the impulse start
  3. Identify the SINGLE last bearish candle before the impulse (not a group)
  4. Zone = [low of that single bearish candle, high of that single bearish candle]
  5. This is the institutional buy zone

SUPPLY ZONE (Bearish):
  1. Find a strong bearish impulse move (displacement > 1× ATR)
  2. Look backward from the impulse start
  3. Identify the SINGLE last bullish candle before the impulse (not a group)
  4. Zone = [low of that single bullish candle, high of that single bullish candle]
  5. This is the institutional sell zone
```

### Visual Evidence — Demand Zones
- `Expert_Demand_Zone_D1_650pips.png` — Daily demand zone → 650 pip buy move
- `Expert_Demand_Zone_D1_2400pips.png` — Daily demand zone → 2400 pip buy move
- `Expert_Demand_Zone_D1_Wide.png` — Daily demand zone (wider view)

### Visual Evidence — Supply Zones
- `Expert_Supply_Zone_H4_Single.png` — H4 supply zone with clear "supply candle" annotation
- `Expert_Supply_Zone_H4_Multiple.png` — H4 chart with 3 separate supply zones at different levels
- `Expert_Supply_Zone_H4_Retracement.png` — H4 supply zone with price retracement into zone

---

## 23. Unfilled Order Expiry (V1)

When a limit order expires unfilled, the POI is marked STATE_TESTED and deactivated.

| Timeframe | Expiry (bars) | Expiry (wall-clock) |
|-----------|---------------|---------------------|
| **M5** | 12 bars | ~1 hour |
| **M1** | 30 bars | ~30 minutes |

**Rule:** Order placed → if not filled within N bars → cancel order → POI → STATE_TESTED (no return).

---

## 24. Trigger Expiry Windows (V1 Defaults)

Each trigger has a maximum validity window. If the trigger does not fire within this window, the POI → STATE_TESTED.

| Trigger | Expiry Rule |
|---------|-------------|
| **A – CHOCH Reversal** | 20 M5 bars |
| **B – Leading Diagonal** | 30 bars after Wave 5 completion |
| **C – Ending Diagonal** | Sweep candle + 3 bars |
| **D – Two-Bar Reversal** | Bar immediately following only |
| **E – RSI Divergence** | 15 bars after pattern completion |
| **F – BOS + OB Continuation** | First touch only |

**Rule:** No trigger fires within expiry window → POI → STATE_TESTED. If trigger fires → proceed to execution.

---

## 25. In-Between Entry Definition (Default — pending possible expert revision)

An **in-between entry** exists only when BOTH conditions are met:

1. Price enters the zone body (between zone high and zone low), **AND**
2. A valid LTF trigger (any of A–F) fires while price is still inside the zone.

If price only wicks the boundary or closes beyond the zone without a trigger firing inside → treat as **no in-between entry** → activate Fallback Boundary Sweep logic (Section 2, Rule 5).

**Status:** Default — pending possible expert revision.

---

## 26. Model 8 +10% Overlap Bonus (Clarified)

- Apply as a **quality-score bonus only** — add +0.10 to the confluence quality score.
- Do NOT change position size.
- If D1 and H4 Demand/Supply zones overlap at the same level → set flag `htf_overlap = true` and add +0.10 to score.

---

## 27. Structural Swing N-bar Parameters (Frozen)

These N-bar parameters define how many bars must confirm a swing on each timeframe class:

| Timeframe Class | N |
|-----------------|---|
| Daily / H4 / H1 | 5 |
| M30 / M15 / M5 / M1 | 3 |

**Rule:** A swing is only confirmed when N bars after the swing bar have been observed and validated per the Base Candle gate (Section 19).

---

## 28. Risk Layer Thresholds (Phase 5) — LOCKED 2026-09-07

Locked by the Lead Architect on 2026-09-07 (Risk Constants Lock decision,
based on the v25_DIAG constant proposal). Source of values: proven inputs in
`03_REFERENCE_CODE/GOLD_SMC_v25_DIAG.mq5`. These are the frozen thresholds
for the Phase 5 risk layer (`smc/risk/`); they are transcribed verbatim into
`04_SRC/smc/config/locked_constants.py` §28.

### 28.1 PureRunner / Break-Even

| Constant | Value | Source (v25_DIAG) | Notes |
|----------|-------|-------------------|-------|
| `PURE_RUNNER_BE_ATR` | 1.0 | `InpBEActivRR = 1.0` | Move SL to break-even at 1.0× ATR movement. |
| `PURE_RUNNER_BE_BUFFER_ATR` | 0.10 | `InpBEBuffer = 0.10` | BE price = entry + dir × ATR × buffer (slight positive edge, not exact scratch). |

### 28.2 Circuit Breaker

| Constant | Value | Source (v25_DIAG) | Notes |
|----------|-------|-------------------|-------|
| `CIRCUIT_BREAKER_LOSS_COUNT` | 3 | `InpCBLossCount = 3` | Consecutive losses to trigger the pause (Z-score validated −2.27). |
| `CIRCUIT_BREAKER_PAUSE_HOURS` | 4 | `InpCBPauseHours = 4` | Hours to pause; counter resets on any win or on a new day. |

### 28.3 Same-Level SL Re-Entry Guard

| Constant | Value | Source (v25_DIAG) | Notes |
|----------|-------|-------------------|-------|
| `SAME_LEVEL_GUARD_ATR` | **0.15** | `InpSameSLZone = 0.15` (running default) | **DECISION RECORDED:** the actual running v25 default is 0.15; the older header comment (0.1) and DEVELOPMENT_PLAN (0.1) are superseded. New SL within 0.15× ATR of the last SL level = blocked. |
| `SAME_LEVEL_GUARD_COOLDOWN_BARS` | 4 | `InpSameSLCooldown = 4` | Bars to block re-entry after a close near the same SL. |

### 28.4 Friday EOD

| Constant | Value | Source (v25_DIAG) | Notes |
|----------|-------|-------------------|-------|
| `FRIDAY_EOD_CLOSE_HOUR_UTC` | 20 | `InpFridayCloseHour = 20` | Force-close all positions at 20:00 UTC on Friday. |

### 28.5 Spread Grading (ATR-relative, score-tiered)

| Constant | Value | Source (v25_DIAG) | Notes |
|----------|-------|-------------------|-------|
| `SPREAD_MAX_ATR` | 0.15 | `InpMaxSpreadATR = 0.15` | Max spread as a fraction of ATR, in points. |
| `SPREAD_GRADE_MULTIPLIERS` | A+: 1.5, A: 1.0, B: 0.7, C: 0.5 | v19.7 header | Spread tolerance multiplier by grade over the base `SPREAD_MAX_ATR`. **Semantics are score-tier multipliers, NOT the point bands once listed in DEVELOPMENT_PLAN (to be corrected there).** |
| `SPREAD_GRADE_SCORE_THRESHOLDS` | A+: ≥8, A: ≥5, B: ≥3, C: <3 | v19.7 header | Minimum score per grade; C = below 3. |

### 28.6 Sweep / Failed-Sweep Re-Entry Guard

| Constant | Value | Source (v25_DIAG) | Notes |
|----------|-------|-------------------|-------|
| `SWEEP_GUARD_ZONE_ATR` | 0.5 | `InpFailedSweepZone = 0.5` | ATR radius within which a new sweep counts as the same failed level. |
| `SWEEP_GUARD_COOLDOWN_BARS` | 4 | `InpPostLossCooldown = 4` | Bars to block re-entry after an SL on the same sweep level. |

### 28.7 Risk % Band and Lot Cap

| Constant | Value | Source (v25_DIAG) | Notes |
|----------|-------|-------------------|-------|
| `RISK_PCT_MIN` / `RISK_PCT_MAX` | 0.5 / 1.0 | Documented band (v25 ships `InpRiskPct = 1.0`) | **DECISION RECORDED:** keep the documented 0.5–1.0% band; the caller/risk engine chooses a value within it. |
| `LOT_MAX_SAFETY` | 0.10 | `InpMaxLotSafety = 0.10` | Absolute cap on computed lots regardless of formula. |

### 28.8 Optional / Conditional Gates (locked, port only if still needed)

| Constant | Value | Source (v25_DIAG) | Notes |
|----------|-------|-------------------|-------|
| `ADX_MIN_ENTRY` | 25.0 | Production value (`InpMinADXEntry`; v22 test default was 15.0) | ADX trend gate — block ALL entries when ADX < 25. Port only if still required after the core detection stack is proven. |
| `ATR_FLOOR_MIN_SL` | 1.0 | Production value (`InpMinSLDATR`; v22 test default was 0.6) | SLD/ATR floor — block entries when the stop distance is below 1.0× ATR. Port only if still required. |

### 28.9 Explicitly Deferred (do NOT lock yet)

- Immediate Trail parameters (`InpImmTrailATR` etc.) — out of scope for now.
- Fixed-dollar risk mode (`InpFixedRiskDollars`).
- Fixed-lot fallback (`InpFixedLot`).
- Dynamic SL buffers (`InpSLBufTrend` / `InpSLBufRange`).
- PureRunner TP in R-multiples (`InpPureRunnerRR`).

**Primary Phase 5 exit model:** PureRunner (BE at 1.0× ATR + buffer) + FVG Invalidation. Immediate Trail is out of scope for now.

---

*This document is the single source of truth. All other files must align with these locked decisions.*
