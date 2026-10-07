# FOUNDATION RESET Q&A PACK — FLOWCHART / LOCKED RULES / IMPLEMENTATION FIDELITY AUDIT

**Date:** 2026-09-21  
**Author:** AI Pair Programmer (Advanced Agentic Architecture Audit)  
**Authority:** Lead Architect Foundation Fidelity Reset  
**Status:** COMPLETE — Evidence & Document Extraction Only (No strategy-code changes, no threshold changes, no Monte Carlo, no TP implementation)  
**Output Target:** `06_RESEARCH/FOUNDATION_RESET_QA_PACK.md`

---

## Executive Summary & Audit Mandate

This document answers the Lead Architect's foundation fidelity audit. It systematically reconstructs what **Revision 5** of the Smart Money Concepts (SMC) Master Architecture actually specified, what **V1** implemented in the Python codebase, and what **empirical evidence** (from the Phase C 5-year baseline, Track R diagnostics, and research trade inspector) reveals.

Research into surviving paths (such as refining Trigger F timing discriminators) is officially paused. The data unequivocally proves that optimizing the surviving sub-path attempts to polish an emergent distortion: the traded book is not trading the intended multi-timeframe SMC architecture.

---

## Audit Metadata & Source Manifest

### Mandatory Sources Read & Verified
1. **Architecture & Flowchart:**
   - `01_ARCHITECTURE/Flowcharts/v5_SMC_Master_Architecture_Flowchart.svg` (93 KB master vector flowchart)
   - `01_ARCHITECTURE/Flowcharts/v5_SMC_Master_Architecture_Flowchart.html` (interactive viewer & confluence simulator)
   - `01_ARCHITECTURE/Flowcharts/v5_SMC_Locked_Decisions_Flowchart.md` (text-based pipeline specification)
   - `01_ARCHITECTURE/Flowcharts/SMC_Pure_Entry_Models_Flowchart.html` / `.svg`
2. **Locked Decisions & Plans:**
   - `00_LOCKED/LOCKED_DECISIONS.md` (Revision 5, frozen 2026-09-01)
   - `00_LOCKED/DEVELOPMENT_PLAN.md` (Option A locked)
   - `00_LOCKED/POST_V1_PLAN_OF_ACTION.md` (binding post-V1 phases A–E)
   - `00_LOCKED/POST_V1_ACTIVE_TODO.md` (operational checklist)
   - `00_LOCKED/SESSION_HANDOFF.md` (living project state)
   - `00_LOCKED/SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md` (1062-line formal structural spec)
   - `00_LOCKED/CHOCH_TYPES_AND_SWING_VALIDITY.md` (Rule 1/2/3 and base candle gates)
   - `00_LOCKED/MODEL_8_HTF_DEMAND_SUPPLY.md` (HTF zone specification)
3. **Evidence Produced:**
   - `06_RESEARCH/FLOWCHART_CODE_EVIDENCE_MAP.md` (binding flowchart-to-code map)
   - `06_RESEARCH/POST_BASELINE_DIAGNOSIS.md` (Track R closeout memo)
   - `06_RESEARCH/PHASE_C_BASELINE_REPORT.md` (5-year 761-trade baseline)
   - `06_RESEARCH/FLOWCHART_MATCH_NOTES.md` (curated trade inspector match notes)
   - `06_RESEARCH/PHASE_HONEST_R_RECOMPUTE_REPORT.md` (original SL decontamination)
   - `06_RESEARCH/F_TIMING_DISCRIMINATOR_NOTES.md` & `F_TIMING_WIDER_VALIDATION.md`
   - `06_RESEARCH/STOP_VS_STRUCTURE_NOTES.md` (SL-in-noise vs structural breaks)
4. **Code Surface Inspected:**
   - `04_SRC/smc/detection/` (all 10 modules: base candle, displacement, levels, swings, sweeps)
   - `04_SRC/smc/poi/` & `poi/models/` (base model, registry, classifier, models M1–M8)
   - `04_SRC/smc/validation/` (5 pillars, pipeline, state machine)
   - `04_SRC/smc/triggers/` (triggers A–F, router, expiry, wave structure)
   - `04_SRC/smc/risk/` (pure runner, circuit breaker, guards, spread, sizing)
   - `04_SRC/smc/orchestration/` (detection driver, pipeline engine)
   - `04_SRC/smc/backtest/` (runner, pipeline bridge, fill model)
   - `04_SRC/smc/live/` (loop, run operator, heartbeat)

**Missing Sources:** NONE. All mandatory documents exist and were analyzed.

---

## Section A: Intended Cascade

### 1. What is the official end-to-end order of stages in Rev 5?
*Citation:* `01_ARCHITECTURE/Flowcharts/v5_SMC_Locked_Decisions_Flowchart.md` (lines 10–264), `00_LOCKED/LOCKED_DECISIONS.md` §16, `v5_SMC_Master_Architecture_Flowchart.svg` (lines 108–1163).

**FACT:** The official Rev 5 architectural sequence consists of 7 sequential stages:
1. **Stage 0A: Structural Liquidity Levels & Sweep Detection** — Identification of master structural liquidity pools (Session H/L, PDH/PDL, PWH/PWL, EQH/EQL, Structural Swings, POI/OB/FVG sweeps, D&S/OB fallback boundary sweeps). Sweep requires a wick piercing the level with candle body closing back inside.
2. **Stage 0b: Displacement Check** — Post-sweep institutional impulse verification requiring BOS (candle body close) + FVG (3-candle imbalance gap) + displacement magnitude $\ge 1.0\times$ ATR ($<0.5\times$ ATR is a hard reject).
3. **Stage 0c (Swing Validation Gate):** — Base Candle identification at swing extreme and mandatory verification that price broke and candle body closed beyond the Base Candle's opposite extreme. (Two-bar reversal alone is an explicit hard fail).
4. **Stage 1 & 1b: Modular POI Classification & CHOCH Typing** — Modular tagging across 8 equal POI models (M1–M8) with confluence scoring (1 tag = base, 2 tags = elevated, 3+ = institutional). CHOCH classified into Rule 1 (Standard), Rule 2 (Inside Body), Rule 3 (Inside Wick).
5. **Stage 2: POI Validation Pipeline (5 Quantitative Pillars)** — Pillar 1 (Zone Refinement $\pm 0.5\times$ ATR), Pillar 2 (Displacement $\ge 1.0\times$ ATR), Pillar 3 (Dealing Range coupled to detection TF: Buys $<45\%$, Sells $>55\%$), Pillar 4 (Strict 1-touch Freshness: STATE_FRESH $\to$ STATE_TESTED), Pillar 5 (Inducement soft score: 100% with, 70% without).
6. **Stage 3: Lower-Timeframe Surgical Trigger Routing** — Drop to M5/M1 upon POI touch. Chronological first-valid trigger wins among Triggers A–F (CHOCH, Leading Diagonal, Ending Diagonal, 2-Bar Engulfing + Volume, RSI Divergence, BOS+OB Continuation). Per-trigger expiry windows enforced.
7. **Stage 4 & 5: Execution Engine & Trade Management** — News hard-cancel (15m before CPI/NFP/FOMC), dynamic lot sizing (0.5%–1.0%), broker limit order placement with physical SL ($\text{sweep extreme} \pm 0.3\times\text{ATR}$) and structural TP (or $4\times\text{ATR}$ cap). Stage 5 management: PureRunner (BE move at $1.0\times\text{ATR}$ favorable excursion $+ 0.1\times\text{ATR}$ buffer; $100\%$ runs to structural TP), FVG Invalidation hard exit, Circuit Breaker (3 consecutive losses $\to$ 4h pause), Same-level guard (4 bars), Friday EOD force-close (20:00 UTC).

### 2. What does “identify POI → sweep POI → LTF confirm → entry” map to in the flowchart stages?
*Citation:* `01_ARCHITECTURE/Flowcharts/v5_SMC_Locked_Decisions_Flowchart.md` (lines 30–35, 126, 180–237); `00_LOCKED/LOCKED_DECISIONS.md` §2, §16.

**FACT:** In classical discretionary SMC literature, traders speak of "identify POI $\to$ sweep POI $\to$ LTF confirm $\to$ entry". In the Rev 5 quantitative flowchart, this maps across distinct decoupled stages:
- **Identify POI:** Maps to **Stage 1** (discovering structural zones M1–M7 or HTF zones M8) using validated Stage 0c swings.
- **Sweep POI:** Maps to **Stage 0A / Stage 1 Fallback** ("OB Sweep or FVG Sweep at POI = Liquidity Sweep"; "D&S fallback sweep when price does not offer an in-between mitigation entry inside the zone body, shifting focus to extreme boundary sweep"). It also maps to the arrival sequence in **Stage 3** where price pierces the POI boundary and performs a local liquidity sweep.
- **LTF confirm:** Maps to **Stage 3** (dropping to M1/M5 and waiting for surgical triggers A–F to form a local structural shift, exhaustion volume, or wave structure).
- **Entry:** Maps to **Stage 4** (placing a deterministic broker limit order at the trigger's designated price level, e.g., broken structural shelf, 50% engulfing body, or OB proximal edge).

*Critical Architectural Distinction:* Rev 5 formalizes sweeps at *both* macro levels (Stage 0A drives structural leg qualification before POIs exist) and local levels (Stage 3 triggers confirm POI rejection).

### 3. What are the frozen detection TF roles (D1/H4/H1/M30) and execution TF rule (drop 2–4 TFs)?
*Citation:* `01_ARCHITECTURE/Flowcharts/v5_SMC_Locked_Decisions_Flowchart.md` (lines 280–289), `00_LOCKED/LOCKED_DECISIONS.md` §4, `v5_SMC_Master_Architecture_Flowchart.svg` (lines 144–152).

**FACT:** The frozen detection timeframe architecture assigns explicit, non-overlapping roles:
- **Daily (D1):** Macro Context & Major Reversals. Detects Models 1, 3, 4 + Model 8 HTF Zone Scan.
- **H4:** Primary Workhorse / Core Swing. Detects Models 1, 3, 5 + Model 8 HTF Zone Scan.
- **H1:** Universal Model Engine. Detects all 8 models (M1–M8); optimal balance of granularity and signal density.
- **M30:** Fast Intraday Formations. Detects Models 2, 5, 6, 7 (rapid reactive flips, higher noise).

**Execution Timeframe Rule:**
"Execution TF: Strictly dropped to M5 / M1 (2–4 TFs lower than detection)."
- D1 / H4 detections $\to$ execute on M5 or M1 (drop 2–4 TFs).
- H1 detections $\to$ execute on M5 or M1 (drop 2–3 TFs).
- M30 detections $\to$ execute on M1 (drop 2 TFs).

### 4. Is M1-only detection+execution compliant with the flowchart? Yes/No + why.
*Citation:* `01_ARCHITECTURE/Flowcharts/v5_SMC_Locked_Decisions_Flowchart.md` §Detection Timeframe Architecture; `04_SRC/smc/orchestration/detection_driver.py` (lines 105–118); `06_RESEARCH/scripts/phase_c_baseline_backtest.py` (line 216).

**FACT:** **NO.** It is completely non-compliant.  
**Why:**
1. The flowchart explicitly forbids detecting macro POI structures on execution timeframes. M1 is strictly an *execution/trigger* timeframe (Stage 3), never a detection timeframe.
2. In the V1 backtest and live runners, `DetectionDriver(Timeframe.M1)` runs both detection (Stage 0/1/2) and execution (Stage 3/4) on M1 candles alone.
3. Detecting on M1 collapses the macro structural framework into micro-noise: swings, order blocks, dealing ranges, and displacement impulses become 1-minute fluctuations rather than institutional liquidity pools.
4. It eliminates the 2–4 timeframe drop, erasing the core premise of SMC: capturing high-timeframe institutional imbalances with low-timeframe surgical risk.

---

## Section B: Stage 0 / 0b (Liquidity, Sweeps, Displacement & Swings)

### 5. What liquidity pools are mandatory?
*Citation:* `01_ARCHITECTURE/Flowcharts/v5_SMC_Locked_Decisions_Flowchart.md` (lines 23–35), `00_LOCKED/LOCKED_DECISIONS.md` §2.

**FACT:** Stage 0A mandates tracking the **Master Structural Liquidity Set** consisting of 7 distinct pool types:
1. **Session Highs / Lows:** Asia (00:00–07:00 UTC), London (07:00–13:00 UTC), New York (13:00–20:00 UTC).
2. **Periodic Extremes:** Previous Day High/Low (PDH/PDL), Previous Week High/Low (PWH/PWL).
3. **Equal Highs / Equal Lows (EQH/EQL):** Both Buy-Side Liquidity (BSL, top) and Sell-Side Liquidity (SSL, bottom) with frozen tolerance $\le 4.5\text{ pips}$ on XAUUSD.
4. **Structural Swing Highs / Lows:** Swings confirmed strictly by the Base Candle opposite-close gate (discarding minor internal fractal noise).
5. **POI Level Sweeps:** Order Block sweep or FVG sweep at an identified POI.
6. **Demand & Supply Boundary Sweeps:** Fallback extreme wick sweep when price enters a zone without providing an in-between mitigation entry.
7. **Order Block Boundary Sweeps:** Fallback extreme wick sweep when price passes through an OB body.

### 6. Exact sweep definition.
*Citation:* `01_ARCHITECTURE/Flowcharts/v5_SMC_Locked_Decisions_Flowchart.md` (line 36), `v5_SMC_Master_Architecture_Flowchart.svg` (line 128), `00_LOCKED/LOCKED_DECISIONS.md` §2.

**FACT:**
> **"SWEEP RULE: Wick pierces structural level + candle body closes inside (back within the level)."**

*Institutional Principle:* Smart money hunts retail stop-losses clustered tightly outside obvious structural points. Once retail orders are absorbed ("market eats all retailers"), institutional orders are filled and price aggressively departs. Because retail liquidity is cleansed, price will not return to re-hunt that level, creating structural invalidation protection.

### 7. Displacement thresholds and required structural proof (BOS/FVG).
*Citation:* `01_ARCHITECTURE/Flowcharts/v5_SMC_Locked_Decisions_Flowchart.md` (lines 51–59), `00_LOCKED/LOCKED_DECISIONS.md` §3, `v5_SMC_Master_Architecture_Flowchart.svg` (lines 132–140).

**FACT:**
- **Minimum Displacement Threshold:** $\ge 1.0\times$ ATR expansion impulse from the sweep pivot (FROZEN).
- **Hard Fail Filter:** Displacement $< 0.5\times$ ATR = HARD REJECT (insufficient institutional sponsorship).
- **Preferred Target:** Displacement $> 1.5\times$ ATR.
- **Required Structural Proof:**
  1. **BOS (Break of Structure):** Candle body close beyond prior swing extreme.
  2. **FVG (Fair Value Gap):** 3-candle imbalance gap (Candle 3 low $>$ Candle 1 high for bullish; Candle 3 high $<$ Candle 1 low for bearish).

### 8. Base-candle and valid-swing rules.
*Citation:* `01_ARCHITECTURE/Flowcharts/v5_SMC_Locked_Decisions_Flowchart.md` (lines 64–84), `00_LOCKED/LOCKED_DECISIONS.md` §18, §19, `00_LOCKED/CHOCH_TYPES_AND_SWING_VALIDITY.md`.

**FACT:**
- **Base Candle Definition:** The single candle creating the structural extreme:
  - *Bullish Trend:* The single candle whose **HIGH** is the swing high.
  - *Bearish Trend:* The single candle whose **LOW** is the swing low.
  - *Bearish Exception:* If a bearish candle exists and the next candle's wick makes a lower low, the bearish candle remains the Base Candle (demonstrating institutional selling intent).
- **Valid Swing Gate:**
  - A swing is **VALID** if and only if price later retraces, breaks the Base Candle's opposite extreme, and a candle **BODY CLOSES** beyond it.
  - *Bullish:* Candle body closes below Base Candle LOW.
  - *Bearish:* Candle body closes above Base Candle HIGH.
  - *Invalid Swing:* Wick-only pierce without body close, or failure to reach the extreme. An invalid swing is discarded—**NO POI CAN FORM**.
- **Two-Bar Reversal Trap:** Expert mandate explicitly declares that a two-bar reversal alone does NOT validate a swing point. Body close beyond the Base Candle extreme is mandatory.

### 9. Are these implemented in code modules? Which files?
*Citation:* `06_RESEARCH/FLOWCHART_CODE_EVIDENCE_MAP.md` (lines 18–21); `04_SRC/smc/detection/`.

**FACT:** Yes, implemented across 10 modules in `04_SRC/smc/detection/`:
- Session levels: `smc/detection/session_levels.py`
- Periodic levels (PDH/PDL, PWH/PWL): `smc/detection/periodic_levels.py`
- EQH/EQL detection ($\le 4.5$ pips): `smc/detection/eqh_eql_detector.py`
- Structural sweeps: `smc/detection/sweep_detector.py`
- Displacement & BOS: `smc/detection/displacement_checker.py`
- FVG detection: `smc/detection/fvg_detector.py`
- Base Candle discovery: `smc/detection/base_candle.py`
- Structural swing detection ($N=5$ HTF, $N=3$ LTF): `smc/detection/structural_swing_detector.py`
- Swing validity gate: `smc/detection/swing_validator.py`
- Master scanner aggregation: `smc/detection/liquidity_scanner.py`

*Fidelity Caveat:* While the modules exist, the Stage 0A fallback boundary sweep routines (monitoring zone extremes when no in-between entry occurs) are not separated as distinct fallback listeners in `sweep_detector.py`.

---

## Section C: POI Models M1–M8

For each model M1 to M8, the intended specification vs V1 code and evidence is detailed below:

| Model | 10. Detection TF Intent | 11. Entry Idea | 12. SL Idea | 13. Target Idea | 14. Code Module Path | 15. Empirical Evidence Status |
|---|---|---|---|---|---|---|
| **M1: Origin Demand / Supply Base** | Daily / H4 / H1 | Buy/Sell limit at base unmitigated OB/FVG ($\pm 0.5\times$ ATR) on deep retracement | Beyond base extreme wick $- 0.3\times$ ATR buffer | Prior Swing High / opposing swing / $4\times$ ATR cap | `04_SRC/smc/poi/models/m1_origin_base.py` | **ACTIVE** (Observed in curated inspector setups L1, L2a; heavy in raw model tagging) |
| **M2: RBS / SBR Breaker Flip** | H1 / M30 | Flip limit at exact broken horizontal level aligned with nested FVG | Beyond breaker pivot wick / impulse candle base | Next Structural High / Liquidity Pool | `04_SRC/smc/poi/models/m2_rbs_sbr_breaker.py` | **RARE** (Emits in Phase B; low representation in R4 kills and Phase C book) |
| **M3: CHOCH Shift Retest** | Daily / H4 / H1 | Limit at broken structural level (Rule 1/2/3; NOT at origin OB) | Above/below liquidity sweep extreme (Head) $\pm 0.3\times$ ATR | HTF Demand Zone / Opposing Swing Low | `04_SRC/smc/poi/models/m3_choch_retest.py` (+ `choch_classifier.py`) | **RARE / SILENT** as POI model tag (R4 kills: M3=1 of 335; distinct from Trigger A which fired 29 times) |
| **M4: Quasimodo (QML)** | Daily / H1 / M15 | QML limit at Left Shoulder full wick range `[low, high]` | Strictly beyond Head sweep peak $+ 0.3\times$ ATR | Origin Base / Target ($1:3$ to $1:6$ RR) | `04_SRC/smc/poi/models/m4_quasimodo.py` | **ACTIVE** in kills (heavy in R4), but shows **tag flicker/mismatch** (tags with-trend continuation runs without reversal geometry) |
| **M5: Extreme Equal Highs (Cont.)** | H4 / H1 / M30 | Limit at broken equal level in continuation direction | Above/below reaction bounce peak $+ 5\text{–}10\text{ pts}$ | Continuation Target / Liquidity Expansion | `04_SRC/smc/poi/models/m5_extreme_equal_highs.py` | **ACTIVE** (Dominant in R4 kills: 29% of kills; observed on continuation and shelf charts) |
| **M6: Double Top Neckline SBR** | H1 / M30 | Neckline SBR limit at broken neckline shelf | Above/below reaction bounce high beyond intervening swing | Measured Double Top Height Projection / SSL | `04_SRC/smc/poi/models/m6_neckline_retest.py` | **ACTIVE** in kills (heavy in R4 kills alongside M4/M5); observed on shelf structures |
| **M7: Equal Resistance Shelf** | H1 / M30 | Ceiling limit at horizontal resistance shelf ($H_2 \approx H_1 \le 4.5\text{ pips}$) | Buffer above ceiling $+ 0.3\times$ ATR | Major Structural Low / Liquidity Target | `04_SRC/smc/poi/models/m7_equal_resistance.py` | **ACTIVE** in raw tags (observed in curated charts for tickets 78, 90, 91, and L2a) |
| **M8: HTF Demand / Supply** | D1 / H4 | 3-step pipeline: D1/H4 zone $\to$ M5 approach $\to$ M1 sniper trigger (Trigger C preferred) | Micro SL: $2\text{–}5\text{ pips}$ beyond M1 structure | Macro HTF Targets ($1:5$ to $1:15+\text{ RR}$) | `04_SRC/smc/poi/models/m8_htf_demand_supply.py` | **SILENT** (Zero representation across 5 years in Phase C, Phase B, and live demo runs) |

---

## Section D: Multi-TF / Model 8 Path

### 16. Exact M8 path in flowchart (D1/H4 zone → M5 approach → M1 trigger).
*Citation:* `v5_SMC_Master_Architecture_Flowchart.svg` (lines 470–502, 1023–1039); `00_LOCKED/LOCKED_DECISIONS.md` §21, §22; `00_LOCKED/MODEL_8_HTF_DEMAND_SUPPLY.md`.

**FACT:** Model 8 is the primary institutional sniper setup in Rev 5, characterized by a 3-step timeframe cascade:
1. **Step 1: HTF Zone Discovery (Daily / H4):**  
   Raw zone detection without requiring micro-swings. Scans for:
   - *Valid Demand Zone:* The single last bearish candle before an aggressive bullish displacement impulse ($>1\times$ ATR). Zone = full high-to-low range of that single candle.
   - *Valid Supply Zone:* The single last bullish candle before an aggressive bearish displacement impulse ($>1\times$ ATR). Zone = full high-to-low range of that single candle.
   - *Order Blocks & FVGs* on D1/H4.
   - If D1 and H4 zones overlap, flag `htf_overlap = true` (+0.10 confluence score bonus).
2. **Step 2: LTF Approach Monitoring (M5):**  
   Price approaches and penetrates the D1/H4 zone. The engine monitors structural deceleration into the zone.
3. **Step 3: Surgical Execution Trigger (M1):**  
   Execution is handed to M1 triggers inside the HTF zone.  
   - *Preferred Trigger:* **Trigger C (Ending Diagonal Wave 5 Throw-Under)**. Provides a sniper entry with zero CHOCH lag (saving 50–60 pips on Gold).
   - *Risk/Reward Profile:* Micro SL $2\text{–}5\text{ pips}$ beyond M1 structure; Target: Macro HTF opposing liquidity ($1:5$ to $1:15+\text{ RR}$). Model 8 can combine with any of M1–M7 for confluence.

### 17. Is HTF series fed in backtest/live today?
*Citation:* `04_SRC/smc/orchestration/detection_driver.py` (lines 108, 114); `04_SRC/smc/live/run_operator.py` (line 227); `06_RESEARCH/scripts/phase_c_baseline_backtest.py` (line 216); `00_LOCKED/POST_V1_PLAN_OF_ACTION.md` §9 line 156.

**FACT:** **NO.**  
In the Phase C 5-year baseline runner (`phase_c_baseline_backtest.py`), the Phase B runner, and the live operator runner (`run_operator.py`), `DetectionDriver` is instantiated with only a single timeframe:
```python
driver = DetectionDriver(Timeframe.M1)  # in backtest
driver = DetectionDriver(Timeframe.M5)  # in live demo test
```
The parameter `htf_candles` defaults to `None` (which sets `self.htf_candles = {}`). No Daily or H4 historical or live bars are ever passed to the detection engine.

### 18. If not, is M8 effectively non-evaluable?
*Citation:* `04_SRC/smc/poi/models/m8_htf_demand_supply.py` (lines 60–64); `06_RESEARCH/FLOWCHART_CODE_EVIDENCE_MAP.md` §4.

**FACT:** **YES.**  
`M8HtfDemandSupply.detect` executes:
```python
for tf in (Timeframe.D1, Timeframe.H4):
    series = self.htf_candles.get(tf)
    if not series:
        continue
    pois.extend(self._scan_timeframe(series, tf))
```
When `htf_candles` is empty, `series` is `None`, the loop executes `continue`, and M8 emits an empty list `[]`. Consequently, M8 emitted **0 POIs and 0 trades across the entire 1,768,123 bars of Phase C**. It is structurally dead in the runtime pipeline and completely un-evaluated.

---

## Section E: Validation Pillars

### 19. Pillar 1–5 definitions and hard/soft behavior.
*Citation:* `v5_SMC_Master_Architecture_Flowchart.svg` (lines 509–577); `00_LOCKED/LOCKED_DECISIONS.md` §16; `04_SRC/smc/validation/`.

**FACT:**
- **Pillar 1: Zone Refinement (HARD GATE):**  
  An unmitigated OB or FVG must align within $\pm 0.5\times$ ATR of the POI level.  
  *Behavior:* ✗ No OB/FVG within band $\to$ REJECT ("Naked Level"). ✓ PASS.
- **Pillar 2: Displacement Verification (HARD GATE):**  
  Origin move must produce clean BOS body close + 3-candle FVG gap + displacement impulse $\ge 1.0\times$ ATR.  
  *Behavior:* ✗ Impulse $<0.5\times$ ATR or no BOS/FVG $\to$ REJECT ("Weak Sponsorship"). ✓ $\ge 1.0\times$ ATR $\to$ PASS.
- **Pillar 3: Dealing Range Coupling (HARD GATE):**  
  Coupled to detection TF. Bullish POI must sit in Discount ($<45\%$ of dealing range); Bearish POI must sit in Premium ($>55\%$).  
  *Behavior:* ✗ $45\%\text{–}55\% \to$ REJECT ("Equilibrium Trap"). ✓ PASS.
- **Pillar 4: Strict 1-Touch Freshness (HARD GATE):**  
  Zone must be in `STATE_FRESH`. Upon first touch, transitions to `STATE_TESTED`. Unfilled limit order expiry deactivates POI.  
  *Behavior:* ✗ 2nd/3rd touch or violated $\to$ REJECT ("Depleted Volume"). ✓ 1st touch $\to$ PASS.
- **Pillar 5: Inducement (SOFT SCORE ONLY):**  
  Presence of EQH/EQL, trendline liquidity, or minor swing directly in front of POI.  
  *Behavior:* ○ Without Inducement $\to$ SCORE 70% (Tradeable). ✓ With Inducement $\to$ SCORE 100% (Preferred).  
  *Hard Rule:* **NEVER hard-reject based on inducement absence.**

### 20. Which pillar dominates failures in evidence?
*Citation:* `06_RESEARCH/PHASE_C_BASELINE_REPORT.md` §4 (line 84); `06_RESEARCH/POST_BASELINE_DIAGNOSIS.md` §5; `06_RESEARCH/FLOWCHART_CODE_EVIDENCE_MAP.md` line 26.

**FACT:** **Pillar 2 (Displacement)** overwhelmingly dominates all validation failures.
- In the Phase C 5-year baseline, of 5,327,791 first-failure events recorded in the funnel:
  - **Pillar 2 failed 4,777,402 times (89.7% of all first failures)**.
  - Pillar 3 failed 427,314 times (8.0%).
  - Pillar 1 failed 123,040 times (2.3%).
- In the Track R4 entry selectivity audit (analyzing the full population of 335 candidate kills):
  - **91% of Pillar 2 kills failed specifically because of FVG absence**, while 78% of those killed candidates had a confirmed BOS present.
  - The binding sub-constraint of the entire validation funnel is FVG presence.

### 21. Does pillar behavior preserve POI-first cascade or reshape pattern vocabulary?
*Citation:* `06_RESEARCH/FLOWCHART_CODE_EVIDENCE_MAP.md` §5 item 2; `06_RESEARCH/POST_BASELINE_DIAGNOSIS.md` §5, §6; `06_RESEARCH/FLOWCHART_MATCH_NOTES.md` §5.

**FACT:** It **drastically reshapes the pattern vocabulary**.  
Instead of acting as a quality filter that preserves POI identity, Pillar 2 acts as an indiscriminate bottleneck:
1. Candidate POIs generated by Stage 1 reflect diverse structural patterns (M4 Quasimodo, M5 Equal Highs, M6 Double Tops).
2. Pillar 2 eliminates ~85–90% of them, predominantly discarding setups lacking a 3-candle FVG in the micro-window.
3. The small minority of POIs that survive are predominantly generic momentum continuation legs.
4. When passed to Stage 3, the chronological first-valid trigger router stamps them with **Trigger F (BOS continuation)**.
5. Consequently, the pattern language of candidate kills (M5/M4/M6) and the pattern language of the traded book (Trigger F continuations) barely overlap. The POI-first cascade is dismantled by the validation funnel.

---

## Section F: Triggers (A–F)

### 22–25. Trigger Evaluation Table

*Citations:* `01_ARCHITECTURE/Flowcharts/v5_SMC_Locked_Decisions_Flowchart.md` (lines 180–216), `v5_SMC_Master_Architecture_Flowchart.svg` (lines 606–795, 1040–1148), `04_SRC/smc/triggers/`, `06_RESEARCH/PHASE_C_BASELINE_REPORT.md` §6.2.

| Trigger | 22. Confirmation Meaning | 23. Flowchart Entry / SL / Target Language | 24. Code Path | 25. Empirical Share (Phase C) |
|---|---|---|---|---|
| **A: M1/M5 CHOCH Reversal** | Price pierces POI $\to$ local sweep $\to$ BOS body close breaks structure $\to$ pullback | **Entry:** Limit at broken structural level (NOT origin OB).<br>**SL:** Beyond local sweep wick ($4\text{–}8\text{ pips}$).<br>**Target:** HTF POI Target / $1.0\times$ ATR BE Trail. Expiry: 20 M5 bars. | `04_SRC/smc/triggers/trigger_a_choch.py` | **29 trades (3.8%)**<br>7 W / 22 L, WR 24.1%<br>Net: $-2.77\text{ R}$ |
| **B: Leading Diagonal (5 Waves)** | 5-wave impulse emerges from POI confirming new trend; Wave 2 corrective pullback | **Entry:** Limit at Fib 50.0%–61.8% Golden Zone.<br>**SL:** Below/above origin base of Wave 1.<br>**Target:** Wave 3 Expansion Target (161.8% Fib). Expiry: 30 bars after W5. | `04_SRC/smc/triggers/trigger_b_leading_diagonal.py`<br>(+ `wave_structure.py`) | **70 trades (9.2%)**<br>35 W / 35 L, WR 50.0%<br>Net: $-12.17\text{ R}$ |
| **C: Ending Diagonal (Wave 5)** | Dying wedge enters POI $\to$ 5th wave pierces trendline boundary (Throw-Under) | **Entry:** Trendline Touch Sniper (zero CHOCH lag).<br>**SL:** Ultra-tight: $2\text{–}5\text{ pips}$ beyond Wave 5 wick.<br>**Target:** Diagonal Origin (W1) $\to$ HTF Macro Target ($1:5\text{–}1:15+\text{ RR}$). | `04_SRC/smc/triggers/trigger_c_ending_diagonal.py`<br>(+ `wave_structure.py`) | **1 trade (0.1%)**<br>1 W / 0 L, WR 100%<br>Net: $+0.089\text{ R}$ |
| **D: Two-Bar Reversal + Vol** | Bar 2 engulfs Bar 1 at POI + mandatory $\text{Volume}(\text{Bar 2}) < \text{Volume}(\text{Bar 1})$ (absorption proof) | **Entry:** Limit at 50% of engulfing body (NOT market order).<br>**SL:** Beyond pattern extreme wick.<br>**Target:** HTF Structural Target / PureRunner BE. | `04_SRC/smc/triggers/trigger_d_two_bar.py` | **0 trades (0.0%)**<br>*(Structurally dead per A5 ruling due to all-zero volume)* |
| **E: RSI Divergence** | Double Top/Bottom at POI + RSI(14) prints divergence (slope $>15^\circ$) | **Entry:** Limit at 2nd Peak/Bottom or neckline.<br>**SL:** Beyond double bottom wick $+ 0.3\times$ ATR.<br>**Target:** Pattern Measured Move / HTF Target. | `04_SRC/smc/triggers/trigger_e_rsi_divergence.py` | **2 trades (0.3%)**<br>0 W / 2 L, WR 0.0%<br>Net: $-0.204\text{ R}$ |
| **F: BOS + OB Continuation** | BOS body close confirms trend $\to$ OB candle preceding FVG $\to$ retrace to OB | **Entry:** Limit at 50% FVG / OB midpoint (proximal edge in V1).<br>**SL:** Beyond origin OB distal edge.<br>**Target:** Next Structural BOS / Trend Expansion. Expiry: 1st touch. | `04_SRC/smc/triggers/trigger_f_bos_ob.py` | **659 trades (86.6%)**<br>151 W / 508 L, WR 22.9%<br>Net: $-32.76\text{ R}$ |

### 26. Is chronological first-valid causing monoculture risk?
*Citation:* `00_LOCKED/LOCKED_DECISIONS.md` §12; `06_RESEARCH/FLOWCHART_CODE_EVIDENCE_MAP.md` §3, §4; `06_RESEARCH/PHASE_C_BASELINE_REPORT.md` §6.2.

**FACT:** **YES.**  
Revision 5 locked rule §12 specifies: *"Trigger Selection: Chronological — First valid LTF trigger wins. Not priority-based."*  
- **Mechanism of Failure:** Trigger F requires only a single BOS break and a first touch of the nearest opposing candle. It evaluates and completes almost instantaneously upon any micro-breakout. In contrast, Triggers A, B, C, and E require multi-candle structural development (swing failure, 5-wave Elliott sequences, or double-top RSI decoupling).
- **Resulting Monoculture:** Because Trigger F completes faster in time, it fires first chronologically on almost every armed POI. Once Trigger F fires, the POI state machine transitions to `STATE_TESTED` (Pillar 4), extinguishing the POI and preventing Triggers A, B, C, or E from ever evaluating. Trigger F captured **86.6% (659 of 761 trades)** of the 5-year baseline, creating severe strategy monoculture.

---

## Section G: Stops, Targets & Management

### 27. Flowchart SL philosophy by model/trigger vs V1 runtime behavior.
*Citation:* `v5_SMC_Master_Architecture_Flowchart.svg` (lines 231–235, 836, 890–1034); `04_SRC/smc/triggers/trigger_f_bos_ob.py` (lines 70–73); `06_RESEARCH/STOP_VS_STRUCTURE_NOTES.md` §1.

**FACT:**
- **Flowchart Specification:** Stop losses must be anchored to structural swing extremes with an explicit adaptive buffer:
  - Master rule: $\text{SL} = \text{Structural Sweep Extreme} \pm 0.3\times\text{ATR}$ buffer ($5\text{–}10\text{ points}$).
  - M1: Beyond base extreme $- 0.3\times\text{ATR}$.
  - M3 / Trigger A: Above/below sweep Head $\pm 0.3\times\text{ATR}$.
  - Trigger F: Beyond origin OB distal edge.
- **V1 Runtime Behavior:**
  - `trigger_f_bos_ob.py` sets: `entry, stop = (top, bottom)` for long and `(bottom, top)` for short. The stop is set exactly at the high or low of a *single M1 candle*, with **zero buffer**.
  - In `stop_vs_structure.py`, analysis of 64 Trigger F setups revealed:
    - Median stop distance was only **$0.82\times$ ATR**.
    - The stop price level had been **pre-touched a median of 5.0 times** in the preceding 30 bars!
    - **35 of 64 exits were wick-tag deaths** (price wicked through the tight stop and immediately reversed in the intended direction). The stop sat inside normal market noise rather than beyond structure.

### 28. Flowchart target philosophy vs absence of TP path in V1.
*Citation:* `v5_SMC_Master_Architecture_Flowchart.svg` (Matrix Take Profit column, lines 891–1144); `04_SRC/smc/backtest/pipeline_bridge.py` (line 112); `00_LOCKED/POST_V1_PLAN_OF_ACTION.md` §1 line 17; `06_RESEARCH/PHASE_R2_TP_COUNTERFACTUAL_REPORT.md`.

**FACT:**
- **Flowchart Specification:** Every model and trigger explicitly defines take-profit targets:
  - M1/M2/M5/M7: Opposing structural swings, liquidity pools, or a $4.0\times\text{ATR}$ cap.
  - M4: Ratio $1:3$ to $1:6$.
  - M8: Macro HTF targets ($1:5$ to $1:15+\text{ RR}$).
  - Trigger B: 161.8% Wave 3 Fib projection ($1:4$ to $1:8\text{ RR}$).
  - Trigger F: Next structural BOS / trend expansion.
- **V1 Runtime Reality:**
  - `pipeline_bridge.py` hardwired: `CandidateEntry(..., tp_price=None)`.
  - In all 761 trades of the Phase C baseline, **0 trades closed at take profit** (754 closed at SL, 7 closed at Friday EOD).
  - *Critical Track R Finding:* When R2 simulated counterfactual fixed take-profits (1.5R, 2R, 3R), the strategy did NOT recover. Fixed TP at 1.5R converted only 11 trades and yielded a PF of 0.011 (30× worse than the baseline). Entries die from bad location and chase timing before reaching 1R (62.5% never reach 1R). The absence of TP was an implementation omission, but lack of TP is not why the bot lost money.

### 29. PureRunner BE definition vs structural target language.
*Citation:* `v5_SMC_Master_Architecture_Flowchart.svg` (lines 841–850); `00_LOCKED/LOCKED_DECISIONS.md` §28.1; `04_SRC/smc/risk/pure_runner.py`.

**FACT:**
- **PureRunner Definition:** At $1.0\times\text{ATR}$ favorable excursion, SL moves to Break-Even $+ 0.10\times\text{ATR}$ buffer (`PURE_RUNNER_BE_BUFFER_ATR = 0.10`). Zero early partials. $100\%$ of position runs to structural target.
- **Contradiction with Runtime:** Because `tp_price = None` and trailing stops were deferred (§28.9), the position has no mechanism to exit profitably except hitting the $+0.10\times\text{ATR}$ BE buffer when price retraces.
- Across 187 BE-modified trades in Phase C, PureRunner harvested a total of **$+2.14\text{ raw units}$** (averaging $+0.011$ per trade). PureRunner was designed to protect runners to institutional targets; in V1 it functioned as a "scratch dispenser".

### 30. What is adjustable rule vs architectural sequence?
*Citation:* `00_LOCKED/LOCKED_DECISIONS.md` preamble & §16, §28; `01_ARCHITECTURE/Flowcharts/v5_SMC_Locked_Decisions_Flowchart.md`.

**FACT:**
- **Architectural Sequence (Non-negotiable Framework):**
  - The 5-stage pipeline order: Stage 0 (Macro sweeps & displacement) $\to$ Stage 0b (Base candle & swing validation) $\to$ Stage 1 (Multi-model tagging & confluence) $\to$ Stage 2 (5-pillar validation) $\to$ Stage 3 (LTF surgical triggers) $\to$ Stage 4 (Execution & sizing) $\to$ Stage 5 (Risk management).
  - Multi-timeframe structure: HTF detection (D1/H4/H1/M30) dropped 2–4 TFs to LTF execution (M5/M1).
  - Strict 1-touch state machine (`STATE_FRESH` $\to$ `STATE_TESTED`).
  - News hard-cancel protocol and circuit breakers.
- **Adjustable Rules / Numerical Thresholds (Frozen for baseline, parameterizable in Phase E):**
  - EQH/EQL tolerance ($\le 4.5\text{ pips}$).
  - Displacement threshold ($1.0\times\text{ATR}$ min, $0.5\times$ hard fail).
  - Zone refinement tolerance ($\pm 0.5\times\text{ATR}$).
  - Dealing range bands ($45\% / 55\%$).
  - Break-Even trigger ($1.0\times\text{ATR}$) and buffer ($0.10\times\text{ATR}$).
  - Order expiry windows (M5=12 bars, M1=30 bars).
  - Equity risk fraction ($0.5\%\text{–}1.0\%$).

---

## Section H: Drift Findings Already Known

### 31. Summary of known drifts from research:
*Citation:* `06_RESEARCH/FLOWCHART_CODE_EVIDENCE_MAP.md` §4, §5; `06_RESEARCH/FLOWCHART_MATCH_NOTES.md` §0, §5; `06_RESEARCH/POST_BASELINE_DIAGNOSIS.md` §3, §6.

1. **Trigger F Monopoly:** Trigger F represents 86.6% (659 of 761) of all trades in Phase C due to chronological first-valid preemption.
2. **Model 8 Silence:** M8 emitted 0 POIs and 0 trades across 5 years because HTF candle series were never supplied to `DetectionDriver`.
3. **Trigger D Structurally Dead:** Trigger D generated 0 trades because the canonical parquet dataset has all-zero tick volume, making `Volume(Bar 2) < Volume(Bar 1)` unfireable (A5 ruling).
4. **Tag Flicker:** Identical price geometry re-detected across successive bars receives shifting model tags (e.g., M1+M7 $\to$ M4 $\to$ M5). Tags are detection-path-dependent rather than geometry-intrinsic.
5. **Zone / Entry Divergence:** 10 of 11 inspected trades entered 1 to 4 zone-heights outside the recorded POI zone bounds (widest-zone retention artifact).
6. **BE-Contaminated SL History:** Exported `sl` in early Phase C / R1–R3 was the post-BE modified SL rather than the placement SL, creating inflated R-multiples (showcase trades showing 10–13R were actually 0.4–0.8R honest excursion). Resolved by the `original_sl` export patch.

### 32. Separation of drifts into categories:

#### A. Deferred by Design (Documented in locked plans / rulings)
- **M8 HTF series feeding:** Explicitly deferred to V1.1 in `DEVELOPMENT_PLAN.md` line 150 and `POST_V1_PLAN_OF_ACTION.md` line 27.
- **Trigger D volume dependency:** Explicitly ruled Option (a) on 2026-09-09 in `POST_V1_PLAN_OF_ACTION.md` §3 (A5 ruling) to accept volume-less dataset and defer vendor re-sourcing.
- **Take-profit target execution & trailing stops:** Explicitly deferred in `LOCKED_DECISIONS.md` §28.9.
- **ADX, Kalman, and ATR-floor gates:** Explicitly deferred in `LOCKED_DECISIONS.md` §28.8 / §28.9 (no code modules created).
- **News hard-cancel calendar:** Engine code exists, but calendar was left empty by default (§11).

#### B. Emergent Selection (Mathematical consequence of interaction between rules)
- **Trigger F Monopoly:** Emerged from the interaction of chronological first-valid routing (§12) with the simplicity of Trigger F's single-BOS condition vs multi-bar reversal triggers.
- **Triggers C and E Silence:** Emerged because Ending Diagonals (C) and RSI Divergences (E) rarely complete within tight expiry windows before price touches the POI and expires.
- **Pillar 2 Filter Dominance:** Emerged because 3-candle FVG formation is rare on low-displacement micro-bars, causing FVG-absence to eliminate 91% of candidates.
- **PureRunner Scratch Trap:** Emerged from setting BE activation at $1.0\times\text{ATR}$ without a structural TP or trailing stop, forcing all favorable trades to retrace into the BE buffer.

#### C. True Fidelity Drift (Implementation diverges from Revision 5 specification)
- **Single-TF Detection:** `DetectionDriver` running detection on M1 instead of D1/H4/H1/M30 directly violates the detection TF matrix.
- **Hardwired `tp_price = None`:** `pipeline_bridge.py` hardcoded `tp_price = None`, discarding all structural targets specified in the flowchart matrix.
- **Missing Stop Buffer:** Setting Trigger F stop loss at the exact raw OB candle edge without the specified $0.3\times\text{ATR}$ structural buffer, causing stops inside noise.
- **M4 Tagging Continuation Flow:** Quasimodo model tagging with-trend continuation runs rather than asymmetric head/shoulders reversals.
- **Spread Gate Scale Bug:** Setting spread score thresholds to a $0\text{–}10$ scale while the confluence scorer produced tag counts of $1\text{–}3$, making A/A+ spread tolerances unreachable.

---

## Section I: Foundation Reset Questions for the Lead Architect

### 33. Top 10 mismatches between flowchart and dominant live path:

| # | Flowchart Revision 5 Specification | Dominant Live Path (V1 Backtest / Paper) | Architectural Impact |
|---|---|---|---|
| **1** | Multi-TF architecture: Detection on D1/H4/H1/M30; Execution on M5/M1 | Detection and execution both run on M1 only | Erases macro context; converts swing setups into micro-scalps |
| **2** | 8 equal modular models combining for confluence scoring | 86.6% Trigger F trend continuation on M1 | Complete strategy monoculture; multi-model confluence inert |
| **3** | Model 8 (HTF D1/H4 zones $\to$ M1 sniper) is the flagship setup | Model 8 is completely silent (0 POIs, 0 trades) | Highest R:R setup ($1:5$ to $1:15+$) never evaluated |
| **4** | Structural TPs (prior highs, opposing liquidity, $4\times$ ATR cap) | `tp_price = None` hardwired in pipeline bridge | Zero trades ever hit take-profit; exits only via SL or Friday |
| **5** | SL at structural sweep extreme $\pm 0.3\times$ ATR buffer | Raw single M1 candle distal edge ($0.82\times$ ATR), 0 buffer | Stops placed inside pre-tested noise; 55% wick-tag deaths |
| **6** | Entry on clean pullbacks into unmitigated origin zones | 62% of entries are late chases ($>80\%$ of 30-bar range) | Entries enter at exhaustion points; 62.5% never reach 1R |
| **7** | Chronological trigger routing intended as deterministic tie-break | Chronological routing creates F preemption monopoly | Simplest trigger starves and extinguishes all reversal triggers |
| **8** | Entry strictly at or inside the POI zone boundaries | 10 of 11 inspected trades entered 1–4 zone-heights outside zone | Entry execution disconnected from underlying POI geometry |
| **9** | Distinct geometric patterns (e.g. QML asymmetric reversal) | M4 tags continuation runs; identical zones flicker tags | Model tag labels do not reflect observable chart geometry |
| **10** | PureRunner lets 100% of position run to macro structural TP | PureRunner operates as a $+0.10\times$ ATR scratch dispenser | Banks $+2.14$ across 187 trades; average win equals average loss |

### 34. Which modules must be re-validated before any optimization?
1. **`smc/orchestration/detection_driver.py` & `smc/poi/model_registry.py`:**  
   Must be re-architected to ingest multi-timeframe series (D1, H4, H1) and run detection on the intended timeframes before passing zones to LTF execution.
2. **`smc/poi/models/m8_htf_demand_supply.py`:**  
   Must be validated with actual Daily and H4 candles to test the flagship HTF demand/supply zone logic.
3. **`smc/backtest/pipeline_bridge.py` & `smc/triggers/base_trigger.py`:**  
   Must compute and route structural target prices (`tp_price`) rather than hardwiring `tp_price = None`.
4. **`smc/triggers/trigger_f_bos_ob.py`:**  
   Must enforce genuine pullback depth, verify zone containment, and anchor stops beyond structural pivots with an adaptive ATR buffer.
5. **`smc/triggers/trigger_router.py`:**  
   Must prevent Trigger F from immediately extinguishing POIs when higher-timeframe reversal triggers (A, B, C, E) are actively forming.
6. **`smc/poi/models/m4_quasimodo.py`:**  
   Must be audited to ensure QML geometry requires a true higher high (sweep) followed by a structural lower low break before tagging.
7. **`smc/validation/pillar_2_displacement.py`:**  
   Must be evaluated to determine whether FVG absence on micro-bars is an appropriate hard filter.
8. **`smc/risk/spread_grading.py`:**  
   Must align score-tier thresholds with the actual confluence score range.

### 35. Which work should stop immediately?
1. **STOP all Trigger F survivor optimization:**  
   Cease tuning F-timing discriminators (v1/v2/v3 rules), chase-position thresholds, or pullback heuristics as a standalone strategy. Polishing Trigger F on M1 optimizes a distorted sub-path that was never the intended architecture.
2. **STOP all Monte Carlo and Walk-Forward analysis:**  
   Do not run statistical resampling or walk-forward parameter sweeps on the Phase C baseline book. Resampling a book with hardwired `tp_price = None` and M1-only detection produces meaningless confidence intervals.
3. **STOP synthetic take-profit curve-fitting:**  
   Do not attempt to rescue the existing trade book by searching for fixed-R profit targets. Track R2 proved that entries fail due to poor location and chasing, not exit math.
4. **STOP treating paper trading P/L as strategy evidence:**  
   Phase D demo trading tests operational infrastructure (MetaTrader 5 API, live polling, MQL5 watchdog heartbeat). It cannot validate SMC strategy logic while running on a single-timeframe M5 loop without HTF feeds.

---

### 36. Proposed Fidelity Scorecard Template

The following standardized scorecard must be used for all future foundation fidelity audits:

| Flowchart Node / Concept | Revision 5 Intended Specification | V1 Code Implementation Module | Fed in Backtest / Live Run? | Empirical Evidence Status | Fidelity Classification (`FAITHFUL` / `PARTIAL` / `SILENT` / `DRIFTED`) |
|---|---|---|---|---|---|
| **Macro TF Detection** | D1/H4/H1 detection dropped to M5/M1 execution | `orchestration/detection_driver.py` | NO (fed M1/M5 only) | 0 HTF detections in 5y book | **DRIFTED** |
| **Session / Periodic Pools** | Asia/Lon/NY, PDH/PDL, PWH/PWL | `detection/{session,periodic}_levels.py` | YES | 0 off-session entries; sweeps fire | **FAITHFUL** |
| **EQH / EQL Detection** | Top & bottom pools, $\le 4.5$ pips tolerance | `detection/eqh_eql_detector.py` | YES | Observed in shelf charts (B1, B2) | **FAITHFUL** |
| **Sweep Rule** | Wick pierces level + body closes inside | `detection/sweep_detector.py` | YES | Confirmed on inspector charts | **FAITHFUL** |
| **Displacement Gate** | BOS + FVG + impulse $\ge 1.0\times$ ATR | `detection/displacement_checker.py` | YES | Kills 89.7% of funnel (FVG bound) | **FAITHFUL** (mechanics) / **DRIFTED** (cascade) |
| **Base Candle & Swing Gate** | Extreme candle; body close breaks opposite | `detection/{base_candle,swing_validator}.py`| YES | 2-bar trap honored; swings validated | **FAITHFUL** |
| **Model 1 (Origin Base)** | Retest of origin accumulation base | `poi/models/m1_origin_base.py` | YES | Active in raw tags (L1 setup) | **FAITHFUL** |
| **Model 2 (Breaker Flip)** | Role reversal retest of broken swing | `poi/models/m2_rbs_sbr_breaker.py` | YES | Rare in book | **PARTIAL** |
| **Model 3 (CHOCH Retest)** | Rule 1/2/3 retest at broken level | `poi/models/m3_choch_retest.py` | YES | Silent as POI tag (1 kill in R4) | **PARTIAL** |
| **Model 4 (Quasimodo QML)** | Asymmetric reversal head/shoulder trap | `poi/models/m4_quasimodo.py` | YES | Tags with-trend continuation runs | **DRIFTED** |
| **Model 5 (Equal Highs)** | Continuation setup at broken equal peaks | `poi/models/m5_extreme_equal_highs.py`| YES | Dominant kill tag (29% in R4) | **FAITHFUL** |
| **Model 6 (Neckline SBR)** | Double top/bottom neckline breakdown | `poi/models/m6_neckline_retest.py` | YES | Active in kills | **FAITHFUL** |
| **Model 7 (Resistance Shelf)**| Reactive horizontal resistance ceiling | `poi/models/m7_equal_resistance.py` | YES | Active in shelf setups (B1/B2) | **FAITHFUL** |
| **Model 8 (HTF D&S Zones)** | D1/H4 single opposing candle $\to$ M1 sniper | `poi/models/m8_htf_demand_supply.py`| **NO** (`htf_candles={}`) | 0 POIs, 0 trades across 5 years | **SILENT** |
| **Confluence Scoring** | Modular equal tags; quality score bonus | `poi/confluence_scorer.py` | YES | Tag scores flow; scale bug vs spread | **PARTIAL** |
| **Pillar 1 (Refinement)** | Unmitigated OB/FVG within $\pm 0.5\times$ ATR | `validation/pillar_1_zone_refinement.py`| YES | Enforced (2.3% of first kills) | **FAITHFUL** |
| **Pillar 2 (Displacement)** | BOS + FVG + $>1\times$ ATR | `validation/pillar_2_displacement.py` | YES | Enforced (89.7% of first kills) | **FAITHFUL** |
| **Pillar 3 (Dealing Range)** | Coupled TF: Buys $<45\%$, Sells $>55\%$ | `validation/pillar_3_premium_discount.py`| YES | Enforced (8.0% of first kills) | **FAITHFUL** |
| **Pillar 4 (Freshness)** | Strict 1-touch; STATE_FRESH $\to$ TESTED | `validation/pillar_4_freshness.py` | YES | Invariants verified $\times 2$ runs | **FAITHFUL** |
| **Pillar 5 (Inducement)** | Soft score: 100% with, 70% without | `validation/pillar_5_inducement.py` | YES | Never hard rejects; scores correctly | **FAITHFUL** |
| **Trigger Router** | Chronological first-valid on M1/M5 | `triggers/trigger_router.py` | YES | F monopoly (86.6% of flow) | **DRIFTED** (causes preemption) |
| **Trigger A (CHOCH)** | M1/M5 structural reversal flip | `triggers/trigger_a_choch.py` | YES | 29 trades in Phase C | **FAITHFUL** |
| **Trigger B (Leading Diag)**| 5 waves initiation $\to$ Fib 50–61.8% | `triggers/trigger_b_leading_diagonal.py`| YES | 70 trades; wide fresh stops | **PARTIAL** (wave unverified) |
| **Trigger C (Ending Diag)** | Wave 5 throw-under sniper entry | `triggers/trigger_c_ending_diagonal.py` | YES | 1 trade in 5 years | **SILENT** |
| **Trigger D (Two-Bar Vol)** | 50% engulf body + Vol Bar 2 < Vol Bar 1 | `triggers/trigger_d_two_bar.py` | **NO** (dataset volume=0) | 0 trades (structurally dead) | **SILENT** |
| **Trigger E (RSI Div)** | Double pattern + RSI divergence $>15^\circ$| `triggers/trigger_e_rsi_divergence.py` | YES | 2 trades in 5 years | **SILENT** |
| **Trigger F (BOS+OB Cont)** | BOS $\to$ origin OB proximal touch | `triggers/trigger_f_bos_ob.py` | YES | 659 trades (86.6% monopoly) | **DRIFTED** (stop in noise) |
| **Take-Profit Routing** | Structural target / $4\times$ ATR cap | `backtest/pipeline_bridge.py` | **NO** (`tp_price=None`) | 0 TP exits in 761 trades | **DRIFTED** |
| **Stop Loss Placement** | Sweep extreme $\pm 0.3\times$ ATR buffer | `triggers/trigger_f_bos_ob.py` | YES | Raw candle edge; 55% wick tags | **DRIFTED** |
| **PureRunner Management** | BE at $1\times$ ATR $+ 0.1$ buffer; run to TP | `risk/pure_runner.py` | YES | 187 BE scratches; $+2.14$ dust | **PARTIAL** (no TP to run to) |
| **Circuit Breakers** | 3 consecutive losses $\to$ 4h pause | `risk/circuit_breaker.py` | YES | Blocked 266 entries in Phase C | **FAITHFUL** |
| **Friday EOD Close** | Force-close at 20:00 UTC Friday | `risk/friday_eod.py` | YES | 7 closes ($+22.93$ profit) | **FAITHFUL** |
| **Safety Watchdog EA** | Heartbeat monitor + emergency flatten | `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5`| YES (Phase D demo) | Compiles clean, heartbeat verified | **FAITHFUL** |

---

## Conclusion & Next Step for Lead Architect

The foundation audit is unequivocal: **V1 is not trading the Revision 5 architecture.**  
Instead of an 8-model multi-timeframe confluence engine that snipers high-timeframe demand/supply zones (Model 8) with low-timeframe surgical entries running to macro structural targets, V1 operates as an **M1-only trend-chase engine dominated by Trigger F with stops placed inside noise and zero take-profit capability**.

All further research into optimizing Trigger F parameters or survivors must halt. The Lead Architect can now use this QA Pack to direct the foundation reset, prioritizing multi-timeframe series feeding, Model 8 provisioning, structural target routing, and proper stop-buffer placement.
