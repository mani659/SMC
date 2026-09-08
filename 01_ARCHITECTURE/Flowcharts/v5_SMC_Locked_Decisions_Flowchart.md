# SMC Master Flowchart — Revision 5: Locked Decisions

**Date:** 2026-09-01 (Updated: 2026-09-01 with Model 8 HTF Demand/Supply + CHOCH Types + Base Candle/Swing Validity)
**Status:** CURRENT — Reflects all frozen decisions from `SMC_RESEARCH/LOCKED_DECISIONS.md`
**Supersedes:** v4 (2026-08-26) — v4 did not reflect locked decisions, modular confluence system, Model 5 reclassification, or frozen thresholds.
**New in this version:** Model 8 (HTF Demand/Supply), three CHOCH types (Rule 1/2/3), Base Candle definition, Valid/Invalid Swing gate.

---

## Complete 5-Stage Pipeline

```
═══════════════════════════════════════════════════════════════════════════
              SMC MASTER FLOWCHART — REVISION 5 (LOCKED)
═══════════════════════════════════════════════════════════════════════════

[LIVE DATA STREAM: M15 / H1 / H4 / Daily]
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 0A: STRUCTURAL LIQUIDITY LEVELS & SWEEP DETECTION               │
│                                                                         │
│  Scan for price interaction with MASTER STRUCTURAL LIQUIDITY POOLS:     │
│    • Session Highs/Lows (Asia 00:00–07:00, London 07:00–13:00, NY UTC) │
│    • Periodic Extremes: PDH/PDL, PWH/PWL                               │
│    • Equal Highs / Equal Lows (EQH/EQL): Both Top (BSL) & Bottom (SSL) │
│      (Tolerance ≤ 4.5 pips on XAUUSD — FROZEN)                         │
│    • Structural Swing High / Low: Strictly structural swings confirmed │
│      by Base Candle Gate (minor intermediate noise discarded)          │
│    • POI Level Sweeps: OB Sweep or FVG Sweep at POI = Liquidity Sweep  │
│    • Demand & Supply Fallback Sweeps: If no in-between entry inside   │
│      zone, focus on extreme Demand/Supply boundary sweep               │
│    • Order Block Fallback Sweeps: If no in-between entry inside OB,    │
│      wait for OB extreme wick sweep                                    │
│                                                                         │
│  SWEEP RULE: Wick pierces structural level + candle body closes inside  │
│                                                                         │
│  SMART MONEY STOP-LOSS HUNTING PRINCIPLE:                              │
│    Smart money first hunts retailer stop losses clustered at EQH/EQL,  │
│    OBs, and Demand/Supply boundaries. Once market "eats all retailers",│
│    smart money delivers the real move. Because retail stops are eaten, │
│    market will NOT return to re-hunt previous sweep levels.            │
│                                                                         │
│  VISUALS: 6 expert charts (liquidity_sweep_*.png) - Knowledge Base/    │
│  ✗ No sweep → No event (return to data stream)                         │
│  ✓ Sweep confirmed → Track direction (BSL or SSL)                      │
└─────────────────────────┬───────────────────────────────────────────────┘
                          │ SWEEP CONFIRMED
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 0b: DISPLACEMENT CHECK (FROZEN: 1× ATR minimum)                │
│                                                                         │
│  After sweep, does aggressive impulse follow?                           │
│    ✓ BOS confirmed (close beyond prior swing)                          │
│    ✓ FVG created (3-candle imbalance gap)                              │
│    ✓ Displacement magnitude > 1× ATR (minimum — FROZEN)               │
│                                                                         │
│  ✗ No BOS or no FVG or displacement < 0.5× ATR → No event             │
│  ✓ All confirmed → Proceed to Swing Validation                         │
└─────────────────────────┬───────────────────────────────────────────────┘
                          │ SWEEP + DISPLACEMENT CONFIRMED
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 0c: SWING VALIDATION GATE (Expert — NEW)                       │
│                                                                         │
│  Before POI classification, validate the underlying swing:              │
│                                                                         │
│  1. Find the BASE CANDLE at the extreme:                                │
│     • Bullish: candle whose HIGH = swing high                          │
│     • Bearish: candle whose LOW = swing low                            │
│       (Exception: bearish candle + next wick lower = still base)       │
│                                                                         │
│  2. Did price later break the Base Candle's OPPOSITE extreme?          │
│     ✗ NO → SWING = INVALID → No POI can form                          │
│     ✓ YES → Continue                                                   │
│                                                                         │
│  3. Did a candle CLOSE beyond that extreme?                             │
│     ✗ Wick only → SWING = INVALID → No POI can form                   │
│     ✓ Body close → SWING = VALID → Proceed to POI Classification      │
│                                                                         │
│  NOTE: Two-bar reversal alone does NOT confirm swing validity.         │
│  Visuals: base_candle_bullish_valid_invalid_h1.png                     │
│           base_candle_bearish_valid_invalid_h1.png                     │
└─────────────────────────┬───────────────────────────────────────────────┘
                          │ SWING VALIDATED
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 1: POI MODEL CLASSIFICATION (MODULAR MULTI-MODEL SYSTEM)      │
│                                                                         │
│  ALL 8 MODELS ARE EQUAL TAGS — No hard ranking.                        │
│  Multiple models can tag the same price level simultaneously.           │
│  More independent tags = higher quality score.                          │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────┐       │
│  │  M3: CHOCH Retest (3 Sub-Variants)                        │       │
│  │  Rule 1 (Standard): Body close breaks LAST SWING          │       │
│  │  Rule 2 (Inside Body): Body close breaks INTERMEDIATE     │       │
│  │  Rule 3 (Inside Wick): Wick only — KEPT, lowest strength  │       │
│  │  ENTRY: At broken structural level (NOT origin OB)        │       │
│  ├────────────────────────────────────────────────────────────┤       │
│  │  M5: Extreme Equal Highs (CONTINUATION)                   │       │
│  │  Equal Highs/Lows formed → Broken → Zone unmitigated     │       │
│  │  ENTRY: At broken equal level (continuation, not reversal)│       │
│  ├────────────────────────────────────────────────────────────┤       │
│  │  M4: Quasimodo (QML)                                      │       │
│  │  Left Shoulder → Head (sweep) → Neckline break → LS free  │       │
│  │  ENTRY: Full wick range [left_shoulder_low, high]         │       │
│  ├────────────────────────────────────────────────────────────┤       │
│  │  M6: Double Top/Bottom Neckline Retest                    │       │
│  │  Double pattern formed → Neckline broken → Not retested   │       │
│  ├────────────────────────────────────────────────────────────┤       │
│  │  M7: Equal Resistance Shelf (REACTIVE)                    │       │
│  │  Sharp drop → bounce creates resistance → broken          │       │
│  ├────────────────────────────────────────────────────────────┤       │
│  │  M2: RBS/SBR Breaker Flip                                 │       │
│  │  Swing level broken → Not retested from opposite side     │       │
│  ├────────────────────────────────────────────────────────────┤       │
│  │  M1: Origin Demand/Supply Base                            │       │
│  │  Fresh swing low/high with BOS away → Deep retracement    │       │
│  ├────────────────────────────────────────────────────────────┤       │
│  │  M8: HTF Demand/Supply (D1/H4) — FULL PEER               │       │
│  │  Demand = single last bearish candle before bullish impulse│       │
│  │  Supply = single last bullish candle before bearish impulse│       │
│  │  Zone = full body + wicks of that single opposing candle  │       │
│  │  Also: OB, FVG zones on D1/H4                           │       │
│  │  LTF Approach: M5 → Execution: M1 (Ending Diag preferred) │       │
│  │  SL: 2–5 pips (M1-based) | RR: 1:5+                     │       │
│  │  +0.10 quality-score bonus if D1 + H4 zones overlap      │       │
│  │  Can combine with ANY of M1–M7 for confluence            │       │
│  └────────────────────────────────────────────────────────────┘       │
│                                                                         │
│  CONFLUENCE SCORING:                                                   │
│    1 tag = base quality (tradeable)                                    │
│    2 tags = elevated quality (preferred)                               │
│    3+ tags = highest quality (institutional-grade)                     │
│    No model is suppressed — all tags recorded                          │
│                                                                         │
│  Record: All matching model tags, zone boundaries, direction, TF      │
└─────────────────────────┬───────────────────────────────────────────────┘
                          │ POI MODEL IDENTIFIED
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 2: POI VALIDATION PIPELINE (5 PILLARS — ALL FROZEN)            │
│                                                                         │
│  PILLAR 1 — ZONE REFINEMENT (FROZEN: ±0.5× ATR)                      │
│    Does an unmitigated OB or FVG exist within ±0.5× ATR of POI?       │
│    ✗ → REJECT: Naked Level                                             │
│    ✓ → PASS                                                            │
│                                                                         │
│  PILLAR 2 — DISPLACEMENT (FROZEN: 1× ATR minimum)                     │
│    Did origin impulse produce clean BOS + FVG + displacement > 1× ATR? │
│    ✗ → REJECT: Weak Sponsorship                                        │
│    ✓ → PASS                                                            │
│                                                                         │
│  PILLAR 3 — PREMIUM / DISCOUNT (FROZEN: Coupled to detection TF)      │
│    Using SAME TF as POI detection (H1 POI → H1 range)                 │
│    Bullish POI: range_position < 0.45 (Discount — FROZEN)             │
│    Bearish POI: range_position > 0.55 (Premium — FROZEN)              │
│    0.45–0.55 → REJECT: Equilibrium Trap                                │
│    ✓ → PASS                                                            │
│                                                                         │
│  PILLAR 4 — FRESHNESS (FROZEN: Strict 1-touch only)                   │
│    Is zone STATE_FRESH (never touched since creation)?                  │
│    ✗ → REJECT: Depleted Volume (STATE_TESTED or VIOLATED)             │
│    ✓ → PASS                                                            │
│    NOTE: Unfilled limit orders expire → POI → STATE_TESTED             │
│                                                                         │
│  PILLAR 5 — INDUCEMENT (FROZEN: Soft score only)                      │
│    Is there EQH/EQL, trendline, or minor swing in front of POI?       │
│    ✗ → SCORE 70% (still tradeable, ranked lower)                      │
│    ✓ → SCORE 100%                                                      │
│    ★ Never hard reject based on inducement absence                     │
│                                                                         │
│  ★ All 5 pillars must pass (except Inducement = soft gate)            │
│  ★ POI marked ACTIVE with score and timestamp                          │
└─────────────────────────┬───────────────────────────────────────────────┘
                          │ POI VALIDATED (100% or 70%)
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 3: TRIGGER ROUTING (FROZEN: Chronological first-valid wins)    │
│                                                                         │
│  Drop to M1/M5 and scan for compatible entry trigger                   │
│  First valid trigger (chronological) wins — FROZEN                    │
│                                                                         │
│  TRIGGER A: M1/M5 CHOCH Reversal                                       │
│    Local swing forms → CHOCH confirmed (body close) → Limit at broken │
│    SL: Above/below sweep extreme | Expiry: 20 M5 bars                  │
│                                                                         │
│  TRIGGER B: Leading Diagonal (5 Waves Initiation)                       │
│    5-wave impulse out of POI → Fib 50-61.8% zone                      │
│    SL: Below Wave 1 origin | Expiry: 30 bars after Wave 5             │
│    ⚠️ Subjective — wave counting required                              │
│                                                                         │
│  TRIGGER C: Ending Diagonal (Wave 5 Throw-Under)                        │
│    5-wave diagonal into POI → Wave 5 trendline sweep                  │
│    SL: Ultra-tight beyond Wave 5 wick | Expiry: sweep candle + 3 bars │
│    ⚠️ Most subjective — manual review recommended                      │
│                                                                         │
│  TRIGGER D: Two-Bar Reversal + Volume (FROZEN: Limit at 50% body)     │
│    Engulfing in POI zone + Volume(Bar2) < Volume(Bar1)                │
│    Order: Limit at 50% of engulfing body (NOT market order)           │
│    SL: Beyond pattern extreme | Expiry: bar immediately following     │
│                                                                         │
│  TRIGGER E: Double Top/Bottom + RSI Divergence                          │
│    Pattern at POI + RSI(14) divergence                                  │
│    Limit at neckline/2nd peak | SL: Beyond pattern extreme            │
│    Expiry: 15 bars after pattern completion                             │
│                                                                         │
│  TRIGGER F: BOS + OB Continuation                                       │
│    BOS confirms trend → OB at origin → Retrace to OB                  │
│    Limit at OB edge/50% midpoint | SL: Beyond OB distal edge         │
│    Expiry: first touch only                                             │
│                                                                         │
│  ★ If no trigger fires within expiry window → POI → STATE_TESTED      │
│  ★ If trigger fires → Proceed to Execution                             │
└─────────────────────────┬───────────────────────────────────────────────┘
                          │ ENTRY TRIGGERED
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 4: EXECUTION ENGINE (FROZEN RISK CONTROLS)                     │
│                                                                         │
│  NEWS CHECK (FROZEN):                                                  │
│    Is high-impact news (CPI/NFP/FOMC) within 15 minutes?              │
│    YES → CANCEL all pending orders → Return to data stream            │
│    NO → Continue                                                       │
│                                                                         │
│  LOT SIZING (FROZEN):                                                  │
│    Lots = (Equity × Risk%) / (SL Distance × Tick Value)                │
│    Risk% = 0.5%–1.0% per trade                                        │
│                                                                         │
│  ORDER PLACEMENT (FROZEN):                                             │
│    • Limit order with physical SL + TP on broker server                │
│    • SL at structural sweep extreme ± buffer (0.3× ATR)               │
│    • TP at structural target or 4× ATR cap                             │
│                                                                         │
│  ★ Order placed → Monitor for fill                                    │
└─────────────────────────┬───────────────────────────────────────────────┘
                          │ ORDER FILLED
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 5: TRADE MANAGEMENT (PROVEN COMPONENTS)                        │
│                                                                         │
│  PURE RUNNER MODE (PROVEN):                                            │
│    • No early partials                                                 │
│    • SL → BE at 1.0× ATR favorable move                               │
│    • 100% position runs to structural TP                               │
│                                                                         │
│  FVG INVALIDATION (PROVEN):                                            │
│    If candle closes beyond FVG boundary → HARD EXIT immediately        │
│                                                                         │
│  CIRCUIT BREAKER (PROVEN):                                             │
│    3 consecutive losses → 4h trading pause                             │
│                                                                         │
│  SAME-LEVEL GUARD (PROVEN):                                            │
│    Failed sweep level → 4-bar cooldown on re-entry                    │
│                                                                         │
│  FRIDAY EOD (PROVEN):                                                  │
│    Force-close all positions at 20:00 UTC Friday                       │
│                                                                         │
│  ★ Trade closes (SL, TP, or manual exit) → Log result                 │
│  ★ Update freshness states for all POIs                                │
│  ★ Return to Stage 0 data stream                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Stage 0A Visual References (Expert Charts — 2026-09-05)
| Chart (Knowledge Base/) | What It Shows |
|------------------------|---------------|
| `liquidity_sweep_eq_high_swing_low_h1.png` | EQH sweep (top, BSL) + structural swing low sweeps (bottom, SSL) — H1 |
| `liquidity_sweep_equal_highs_h1.png` | Equal High sweep — retail stop trap above shelf — H1 |
| `liquidity_sweep_swing_highs_h1.png` | Successive structural swing high sweeps in downtrend — H1 |
| `liquidity_sweep_major_high_h1.png` | Major structural high sweep with rejection wick — H1 |
| `liquidity_sweep_high_and_low_range_h1.png` | Top AND bottom sweeps — full range cleansing — H1 |
| `liquidity_sweep_structural_swing_low_m15.png` | Structural swing low sweep — LTF validation — M15 |

---

## Detection Timeframe Architecture (Frozen)

| Timeframe | Role | Models Detected |
|-----------|------|----------------|
| **Daily** | Macro context | Models 1, 3, 4 (major reversals) |
| **H4** | Primary workhorse | Models 1, 3, 5 (medium-term) |
| **H1** | All models | All 8 models (most events, balances granularity) |
| **M30** | Intraday | Models 2, 5, 6, 7 (faster detection, more noise) |

---

## Modular Multi-Model Confluence (Frozen)

All 8 models are **equal tags**. Multiple models can tag the same price level.
More independent tags = higher quality score. No model is suppressed.

```
1 tag = base quality (tradeable)
2 tags = elevated quality (preferred)
3+ tags = highest quality (institutional-grade)
```

---

## Key Locked Thresholds Summary

| Parameter | Frozen Value | Applied At |
|-----------|-------------|------------|
| EQH/EQL Tolerance | ≤ 4.5 pips on XAUUSD | Stage 0A (Structural Sweep Detection) |
| Structural Swing Gate | Base Candle Opposite Close | Stage 0A / Stage 0c (Swing Gate) |
| POI Sweeps (OB & FVG) | Wick pierce + body close inside | Stage 0A & Stage 1/2 |
| D&S / OB Fallback Sweep | Sweep of zone extreme if no in-between entry | Stage 0A & Stage 1 (M1/M8) |
| Smart Money Protection | Zero return to swept liquidity | Stage 0A & Stage 4/5 (Execution) |
| Displacement Minimum | 1× ATR | Stage 0b (Displacement Check) |
| Zone Refinement Tolerance | ±0.5× ATR | Stage 2 (Pillar 1) |
| Premium Threshold (Buys) | < 45% of dealing range | Stage 2 (Pillar 3) |
| Discount Threshold (Sells) | > 55% of dealing range | Stage 2 (Pillar 3) |
| Equilibrium Exclusion | 45%–55% = REJECT | Stage 2 (Pillar 3) |
| Freshness | Strict 1-touch only | Stage 2 (Pillar 4) |
| Inducement Score | 100% with, 70% without | Stage 2 (Pillar 5) |
| News Cancellation | 15min before CPI/NFP/FOMC | Stage 4 (News Check) |
| Unfilled Order Expiry | M5=12 bars, M1=30 bars → STATE_TESTED | Stage 3 (Trigger Expiry) |
| CHOCH Entry | Broken structural level (not OB) | Stage 1 (Model 3) |
| Two-Bar Entry | Limit at 50% engulfing body | Stage 3 (Trigger D) |
| Trigger Selection | Chronological first-valid | Stage 3 (Trigger Routing) |
| Dealing Range Coupling | Same TF as POI detection | Stage 2 (Pillar 3) |
| QML Left Shoulder | Full wick range [low, high] | Stage 1 (Model 4) |

---

*This flowchart is the visual representation of all locked decisions. It supersedes v4. See `SMC_RESEARCH/LOCKED_DECISIONS.md` for the complete source of truth.*
