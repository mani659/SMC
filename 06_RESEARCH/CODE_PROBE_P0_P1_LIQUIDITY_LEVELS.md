# CODE PROBE P0 + P1 — Inventory + Liquidity Level Construction

**Program:** SMC foundation reset (definition → code fidelity)  
**Authority:** Lead Architect  
**Mode:** READ-ONLY code audit — NO strategy/threshold/logic changes  
**Date:** 2026-11-10  
**Status:** PASS  

---

## 1. P0 — Module Inventory (Stages 0A / 0b / 0c / POI / Pillars / Triggers / Multi-TF)

| Concern | Package/Module path | Primary symbols (classes/fns) | Tests path(s) | Notes |
|---------|---------------------|-------------------------------|---------------|-------|
| **Session H/L** | `04_SRC/smc/detection/session_levels.py`<br/>`04_SRC/smc/utils/timestamps.py` | `detect_session_levels`, `Session`, `detect_session` | `04_SRC/tests/test_session_levels.py`<br/>`04_SRC/tests/test_liquidity_scanner.py` | Stage 0A. Uses UTC windows (Asia 00–07, London 07–13, NY 13–20). Emits `LiquidityLevel(type=SESSION)`. |
| **PDH/PDL / PWH/PWL** | `04_SRC/smc/detection/periodic_levels.py` | `detect_periodic_levels`, `_aggregate`, `_monday` | `04_SRC/tests/test_periodic_levels.py`<br/>`04_SRC/tests/test_liquidity_scanner.py` | Stage 0A. Completed UTC days (PDH/PDL) and Monday-anchored weeks (PWH/PWL). Emits `LiquidityLevel(type=PREVIOUS_DAY/WEEK)`. |
| **EQH/EQL** | `04_SRC/smc/detection/eqh_eql_detector.py` | `detect_equal_levels`, `_cluster` | `04_SRC/tests/test_eqh_eql_detector.py`<br/>`04_SRC/tests/test_liquidity_scanner.py` | Stage 0A. Clusters swings within `EQH_EQL_TOLERANCE` (4.5 pips on XAUUSD). Emits `LiquidityLevel(type=EQUAL_HIGHS_LOWS)`. |
| **Structural swings** | `04_SRC/smc/detection/structural_swing_detector.py`<br/>`04_SRC/smc/detection/base_candle.py`<br/>`04_SRC/smc/detection/swing_validator.py`<br/>`04_SRC/smc/core/swing.py` | `detect_swings`, `find_base_candle_index`, `validate_swing`, `Swing` | `04_SRC/tests/test_structural_swing_detector.py`<br/>`04_SRC/tests/test_swing_validator.py`<br/>`04_SRC/tests/test_base_candle.py` | Stage 0C / 0A. N-bar confirmation (`N_BAR_HTF=5`, `N_BAR_LTF=3`). Base candle identification (§18) + opposite extreme body close validity (§19). |
| **Sweep detection** | `04_SRC/smc/detection/sweep_detector.py`<br/>`04_SRC/smc/orchestration/product_menu_mtf.py` | `detect_sweep`, `detect_sweeps`, `SweepResult`, `_is_zone_sweep` | `04_SRC/tests/test_sweep_detector.py`<br/>`04_SRC/tests/test_product_menu_mtf.py` | Stage 0A operates on `LiquidityLevel` (wick pierce + body close back). ProductMenuEngine operates directly on `Zone`. |
| **Displacement** | `04_SRC/smc/detection/displacement_checker.py`<br/>`04_SRC/smc/detection/fvg_detector.py` | `check_displacement`, `DisplacementResult`, `detect_fvgs`, `FVG` | `04_SRC/tests/test_displacement_checker.py`<br/>`04_SRC/tests/test_fvg_detector.py` | Stage 0B. Requires BOS (close beyond prior swing) + 3-candle FVG + displacement $> 1\times$ ATR (`DISPLACEMENT_MIN_ATR = 1.0`). |
| **POI models M1–M8** | `04_SRC/smc/poi/models/` (`m1`–`m8`)<br/>`04_SRC/smc/poi/base_model.py`<br/>`04_SRC/smc/poi/model_registry.py`<br/>`04_SRC/smc/poi/confluence_scorer.py`<br/>`04_SRC/smc/poi/choch_classifier.py` | `POIModel`, `ModelRegistry`, `build_registry`, `ConfluenceScorer`, `ChochClassifier`, `M1OriginBase`...`M8HtfDemandSupply` | `04_SRC/tests/test_poi_models.py`<br/>`04_SRC/tests/test_confluence_scorer.py`<br/>`04_SRC/tests/test_choch_classifier.py` | Stage 1. 8 equal tags (M1–M8, no hierarchy). Confluence scoring (1=base, 2=elevated, 3+=institutional). CHOCH Rules 1/2/3. M8 HTF demand/supply. |
| **Pillars 1–5** | `04_SRC/smc/validation/` (`pillar_1`–`5`)<br/>`04_SRC/smc/validation/validation_pipeline.py`<br/>`04_SRC/smc/validation/state_machine.py` | `ValidationPipeline`, `POIStateMachine`, `ZoneRefinementPillar`, `DisplacementPillar`, `FreshnessPillar`, etc. | `04_SRC/tests/test_pillar_1_zone_refinement.py`...`test_pillar_5_inducement.py`<br/>`04_SRC/tests/test_state_machine.py` | Stage 2. P1: zone refinement ($\pm 0.5\times$ ATR). P2: displacement ($> 1\times$ ATR). P3: P/D ($<0.45/>0.55$). P4: 1-touch freshness (`STATE_FRESH`). P5: inducement soft score (100% vs 70%). |
| **Triggers A–F** | `04_SRC/smc/triggers/` (`trigger_a`–`f`)<br/>`04_SRC/smc/triggers/trigger_router.py`<br/>`04_SRC/smc/triggers/trigger_expiry.py` | `TriggerRouter`, `Trigger`, `TriggerSignal`, `CompatibilityMatrix`, `signal_expired`, Triggers A–F | `04_SRC/tests/test_trigger_a_choch.py`...`test_trigger_f_bos_ob.py`<br/>`04_SRC/tests/test_trigger_router.py` | Stage 3. Chronological first-valid router across LTF (M1/M5). Signal expiry (§24) enforced. |
| **Product multi-TF** | `04_SRC/smc/orchestration/multi_tf.py`<br/>`04_SRC/smc/orchestration/multi_tf_runtime.py`<br/>`04_SRC/smc/orchestration/product_menu_mtf.py`<br/>`04_SRC/smc/live/loop.py` | `MultiTFDetectionDriver`, `MultiTFProductRuntime`, `ProductMenuEngine`, `PRODUCT_MENU_TIERS`, `LiveLoop` | `04_SRC/tests/test_product_mode_detection_policy.py`<br/>`04_SRC/tests/test_product_menu_mtf.py`<br/>`04_SRC/tests/test_menu_seam_integration.py` | Multi-TF detection cascade (H4+H1 required minimum). ProductMenuEngine provides D1→H1, H4→M15/M5, H1→M5/M1, M15→M1 confirmation tiers over 20-bar detection TF window. |

### Orphans (files / symbols unused by product path)
1. **`06_RESEARCH/scripts/track_a_sweep_ledger.py` (`_zone_bound_levels`)**: Research script that synthesizes `LiquidityType.POI_LEVEL` (from FVG bounds) and `LiquidityType.ORDER_BLOCK_BOUNDARY` (from OB bounds). Not part of the production detection package `04_SRC/smc/detection/`.
2. **`04_SRC/smc/core/enums.py` Orphaned Enum Members**:
   - `LiquidityType.POI_LEVEL`
   - `LiquidityType.DEMAND_SUPPLY_BOUNDARY`
   - `LiquidityType.ORDER_BLOCK_BOUNDARY`
   - `PoolType.POI`
   - `PoolType.EXTREME_ZONE`
   - `PoolType.OB_EXTREME`
   These enum variants are declared to match LOCKED §2, but are never instantiated by any constructor in `04_SRC/smc/detection/`.

### Gaps (locked concerns with no owning production module)
1. **Stage 0A POI-linked Level Construction**: No module in `04_SRC/smc/detection/` constructs `LiquidityLevel` objects for POI Order Blocks or FVGs. `liquidity_scanner.py:11-13` explicitly notes this omission as deferred to Phase 2+.
2. **Fallback Boundary Sweep State Machine (§2 Rule 5/6 & §25)**: LOCKED §25 defines the rule: *"Boundary-only without trigger inside → no in-between → fallback boundary sweep path"*. In the code, `product_menu_mtf.py` evaluates zone boundary sweeps directly via `_is_zone_sweep(bar, zone)`, but lacks an explicit two-stage fallback transition (evaluating interior trigger first, and only falling back to boundary sweep upon failure).

---

## 2. P1 — Liquidity LEVEL Construction (Per-Level Audit)

### Level 1: Session Highs/Lows
1. **EXISTS?** YES
2. **Source file(s) + function(s):**
   - `04_SRC/smc/detection/session_levels.py` → `detect_session_levels(candles, timeframe, session=None, day=None)`
   - `04_SRC/smc/utils/timestamps.py` → `detect_session(ts)`
3. **Geometry:** Exact candle extremes: highest `high` (BSL) and lowest `low` (SSL) of all candles with bar-open timestamps inside the session window.
4. **Time rules:**
   - Asia: 00:00–07:00 UTC (start inclusive, end exclusive)
   - London: 07:00–13:00 UTC
   - NY: 13:00–20:00 UTC
   - Unassigned: 20:00–24:00 UTC belongs to no session and is skipped.
   - Grouping: UTC calendar days (`candle.timestamp.date()`).
5. **Parameters:**
   - `ASIA_START_HOUR_UTC = 0`, `ASIA_END_HOUR_UTC = 7`
   - `LONDON_START_HOUR_UTC = 7`, `LONDON_END_HOUR_UTC = 13`
   - `NY_START_HOUR_UTC = 13`, `NY_END_HOUR_UTC = 20`
   - Sourced from `04_SRC/smc/config/locked_constants.py:104-109`.
6. **Output type:** `LiquidityLevel` with:
   - `type = LiquidityType.SESSION`
   - `level = float` (max high / min low)
   - `pool = PoolType.BSL` (for high) / `PoolType.SSL` (for low)
   - `timeframe = timeframe`
   - `formed_at = datetime` (timestamp of the candle that set the extreme)
7. **Tests:**
   - `04_SRC/tests/test_session_levels.py:38-52`: asserts exactly one BSL and one SSL per (day, session) group with correct extreme prices.
   - `04_SRC/tests/test_session_levels.py:55-83`: asserts UTC boundary windows match Asia, London, NY definitions.
8. **Product path:** YES. Included in `ALL_FAMILIES = ("session", "periodic", "equal", "structural")` in `liquidity_scanner.py:34`, invoked by `DetectionDriver.stage0` in live and backtest pipelines.
9. **Verdict:** `IMPLEMENTED`
10. **Evidence:**
```python
# 04_SRC/smc/detection/session_levels.py:71-90
high_candle = max(group, key=lambda c: c.high)
low_candle = min(group, key=lambda c: c.low)
levels.append(LiquidityLevel(type=LiquidityType.SESSION, level=high_candle.high,
                             pool=PoolType.BSL, timeframe=timeframe, formed_at=high_candle.timestamp))
levels.append(LiquidityLevel(type=LiquidityType.SESSION, level=low_candle.low,
                             pool=PoolType.SSL, timeframe=timeframe, formed_at=low_candle.timestamp))
```

---

### Level 2: Previous Day High / Low (PDH / PDL)
1. **EXISTS?** YES
2. **Source file(s) + function(s):**
   - `04_SRC/smc/detection/periodic_levels.py` → `detect_periodic_levels(candles, timeframe, as_of=None)`
3. **Geometry:** Exact wick extremes: maximum `high` (BSL) and minimum `low` (SSL) across all candles of the most recent completed UTC trading day prior to `as_of`.
4. **Time rules:**
   - Completed UTC calendar days strictly before `reference.date()` (`completed_days = [d for d in daily if d < reference.date()]`).
   - Weekends/holidays without candles are skipped automatically (Monday sees Friday's levels).
5. **Parameters:** None (calendar day boundary in UTC).
6. **Output type:** `LiquidityLevel` with:
   - `type = LiquidityType.PREVIOUS_DAY`
   - `level = float`
   - `pool = PoolType.BSL` (high) / `PoolType.SSL` (low)
   - `timeframe = timeframe`
   - `formed_at = datetime` (timestamp of candle setting the extreme)
7. **Tests:**
   - `04_SRC/tests/test_periodic_levels.py:47-64`: asserts PDH and PDL match the highest high and lowest low of the previous completed UTC day.
   - `04_SRC/tests/test_periodic_levels.py:67-77`: asserts PDH/PDL remains stable intraday and does not read the current forming day.
8. **Product path:** YES. Included in `ALL_FAMILIES` via `liquidity_scanner.py` → `DetectionDriver.stage0`.
9. **Verdict:** `IMPLEMENTED`
10. **Evidence:**
```python
# 04_SRC/smc/detection/periodic_levels.py:72-97
completed_days = [d for d in daily if d < reference.date()]
day_entry = daily.get(max(completed_days)) if completed_days else None
if day_entry is not None:
    levels.append(LiquidityLevel(type=LiquidityType.PREVIOUS_DAY, level=day_entry["high"][0],
                                 pool=PoolType.BSL, timeframe=timeframe, formed_at=day_entry["high"][1]))
    levels.append(LiquidityLevel(type=LiquidityType.PREVIOUS_DAY, level=day_entry["low"][0],
                                 pool=PoolType.SSL, timeframe=timeframe, formed_at=day_entry["low"][1]))
```

---

### Level 3: Previous Week High / Low (PWH / PWL)
1. **EXISTS?** YES
2. **Source file(s) + function(s):**
   - `04_SRC/smc/detection/periodic_levels.py` → `detect_periodic_levels(candles, timeframe, as_of=None)`
3. **Geometry:** Exact wick extremes: maximum `high` (BSL) and minimum `low` (SSL) across all candles of the most recent completed week prior to `as_of`.
4. **Time rules:**
   - Weeks are Monday-anchored: `_monday(value) = value - timedelta(days=value.weekday())`.
   - Completed weeks strictly before current week: `w < _monday(reference.date())`.
5. **Parameters:** None (7-day Monday-anchored UTC week).
6. **Output type:** `LiquidityLevel` with:
   - `type = LiquidityType.PREVIOUS_WEEK`
   - `level = float`
   - `pool = PoolType.BSL` (high) / `PoolType.SSL` (low)
   - `timeframe = timeframe`
   - `formed_at = datetime`
7. **Tests:**
   - `04_SRC/tests/test_periodic_levels.py:47-64`: asserts PWH and PWL match extremes of previous completed week.
   - `04_SRC/tests/test_periodic_levels.py:80-92`: asserts PWH/PWL is omitted when less than one full completed week exists in series.
8. **Product path:** YES. Included in `ALL_FAMILIES` via `liquidity_scanner.py` → `DetectionDriver.stage0`.
9. **Verdict:** `IMPLEMENTED`
10. **Evidence:**
```python
# 04_SRC/smc/detection/periodic_levels.py:73-120
completed_weeks = [w for w in weekly if w < _monday(reference.date())]
week_entry = weekly.get(max(completed_weeks)) if completed_weeks else None
if week_entry is not None:
    levels.append(LiquidityLevel(type=LiquidityType.PREVIOUS_WEEK, level=week_entry["high"][0],
                                 pool=PoolType.BSL, timeframe=timeframe, formed_at=week_entry["high"][1]))
    levels.append(LiquidityLevel(type=LiquidityType.PREVIOUS_WEEK, level=week_entry["low"][0],
                                 pool=PoolType.SSL, timeframe=timeframe, formed_at=week_entry["low"][1]))
```

---

### Level 4: Equal Highs / Equal Lows (EQH / EQL)
1. **EXISTS?** YES
2. **Source file(s) + function(s):**
   - `04_SRC/smc/detection/eqh_eql_detector.py` → `detect_equal_levels(swings, timeframe=Timeframe.M5)`
3. **Geometry:**
   - Equal Highs (BSL): maximum high among swings in the cluster (`level_price = max(s.level for s in cluster)`).
   - Equal Lows (SSL): minimum low among swings in the cluster (`level_price = min(s.level for s in cluster)`).
   - Anchored at cheapest member; every subsequent swing must be within `tolerance` of anchor.
4. **Time rules:**
   - Evaluated on candidate swings chronologically.
   - `formed_at` stamped as `max(s.timestamp for s in cluster)`.
5. **Parameters:**
   - Frozen constant: `EQH_EQL_TOLERANCE = 4.5` (pips on XAUUSD) in `04_SRC/smc/config/locked_constants.py:98`.
   - Converted to price via `pips_to_price(EQH_EQL_TOLERANCE)` (`0.45` price units for 0.1-pip Gold convention).
   - Minimum cluster size: $\ge 2$ swings.
6. **Output type:** `LiquidityLevel` with:
   - `type = LiquidityType.EQUAL_HIGHS_LOWS`
   - `level = float` (cluster extreme)
   - `pool = PoolType.BSL` (for highs) / `PoolType.SSL` (for lows)
   - `timeframe = timeframe`
   - `formed_at = datetime`
7. **Tests:**
   - `04_SRC/tests/test_eqh_eql_detector.py:44-58`: asserts clusters form within 4.5 pips, BSL at max high, SSL at min low.
   - `04_SRC/tests/test_eqh_eql_detector.py:61-71`: asserts single swings without a match do not form an EQH/EQL level.
8. **Product path:** YES. Included in `ALL_FAMILIES` via `liquidity_scanner.py` → `DetectionDriver.stage0`.
9. **Verdict:** `IMPLEMENTED`
10. **Evidence:**
```python
# 04_SRC/smc/detection/eqh_eql_detector.py:36-96
tolerance = pips_to_price(EQH_EQL_TOLERANCE)
# ... clusters requiring len(c) >= 2 ...
level_price = max(s.level for s in cluster) if is_high else min(s.level for s in cluster)
levels.append(LiquidityLevel(type=LiquidityType.EQUAL_HIGHS_LOWS, level=level_price,
                             pool=PoolType.BSL if is_high else PoolType.SSL,
                             timeframe=timeframe, formed_at=max(s.timestamp for s in cluster)))
```

---

### Level 5: Structural Swing High / Low
1. **EXISTS?** YES
2. **Source file(s) + function(s):**
   - `04_SRC/smc/detection/structural_swing_detector.py` → `detect_swings(candles, timeframe, n=None)`
   - `04_SRC/smc/detection/base_candle.py` → `find_base_candle_index(candles, swing_index, is_high)`
   - `04_SRC/smc/detection/swing_validator.py` → `validate_swing(candles, base_index, is_high)`
   - `04_SRC/smc/detection/liquidity_scanner.py:74-86` → maps valid swings to `LiquidityLevel`
3. **Geometry:**
   - Extreme wick price (`candle.high` for swing high, `candle.low` for swing low).
   - Anchored to Base Candle: High = swing high for bullish; Low = swing low for bearish (or bearish candle if next candle wicks lower).
4. **Time rules:**
   - Candidate requires N bars on both sides.
   - Validation requires a subsequent candle to break the Base Candle's opposite extreme and **close beyond it** (body close).
5. **Parameters:**
   - Frozen constants: `N_BAR_HTF = 5` (D1/H4/H1), `N_BAR_LTF = 3` (M30/M15/M5/M1) in `04_SRC/smc/config/locked_constants.py:167-168`.
   - §18/§19 Base Candle validity: body close required; two-bar reversal without body close is rejected.
6. **Output type:**
   - `Swing(is_high=bool, level=float, candle_index=int, base_candle=Candle, is_valid=bool, confirmed_index=int)`.
   - Converted by `liquidity_scanner.py` to `LiquidityLevel(type=LiquidityType.STRUCTURAL_SWING, level=swing.level, pool=swing.pool, formed_at=swing.timestamp)`.
   - **Crucial rule:** `liquidity_scanner.py:76-77` filters `if not swing.is_valid: continue`. Only validated structural swings become liquidity levels.
7. **Tests:**
   - `04_SRC/tests/test_structural_swing_detector.py:38-55`: asserts N-bar window detection.
   - `04_SRC/tests/test_swing_validator.py:38-52`: asserts body close validates swing; wick-only does not validate.
   - `04_SRC/tests/test_liquidity_scanner.py:70-74`: asserts scanner only emits `STRUCTURAL_SWING` levels for `is_valid == True` swings.
8. **Product path:** YES. Included in `ALL_FAMILIES` via `liquidity_scanner.py` → `DetectionDriver.stage0`.
9. **Verdict:** `IMPLEMENTED`
10. **Evidence:**
```python
# 04_SRC/smc/detection/liquidity_scanner.py:74-86
if "structural" in include:
    for swing in swings:
        if not swing.is_valid:
            continue
        levels.append(LiquidityLevel(type=LiquidityType.STRUCTURAL_SWING, level=swing.level,
                                     pool=swing.pool, timeframe=timeframe, formed_at=swing.timestamp))
```

---

### Level 6: POI-Linked Levels (OB & FVG Boundaries as Liquidity)
1. **EXISTS?** PARTIAL
2. **Source file(s) + function(s):**
   - Enum declarations: `04_SRC/smc/core/enums.py:32, 63` (`LiquidityType.POI_LEVEL = "poi_level"`, `PoolType.POI = "poi"`).
   - In research scripts: `06_RESEARCH/scripts/track_a_sweep_ledger.py:140-144` constructs `LiquidityLevel(type=LiquidityType.POI_LEVEL)` from FVG top and bottom bounds.
   - In product confirmation spine: `04_SRC/smc/orchestration/product_menu_mtf.py:124-135` (`_is_zone_sweep`) checks if a closed bar sweeps a POI zone's extreme.
   - In Stage 0A pipeline: `NOT_IN_0A`. `04_SRC/smc/detection/liquidity_scanner.py:11-13` states: *"The remaining §2 level types (POI_LEVEL, DEMAND_SUPPLY_BOUNDARY, ORDER_BLOCK_BOUNDARY) depend on POI zones and are produced in Phase 2+"*.
3. **Geometry:**
   - FVG top and bottom boundaries.
   - Order block extreme wicks.
4. **Time rules:** Evaluated on detection TF series after POI creation/arming.
5. **Parameters:** None.
6. **Output type:**
   - In research scripts: `LiquidityLevel(type=LiquidityType.POI_LEVEL, level=zone.top|zone.bottom, pool=BSL|SSL)`.
   - In `ProductMenuEngine`: no `LiquidityLevel` object is emitted; it operates directly on `POI.zone: Zone` and transitions `MenuEpisode` to `ACTIVE`.
7. **Tests:**
   - `04_SRC/tests/test_track_a_sweep_ledger.py:15-25`: tests sweep of zone boundaries.
   - `04_SRC/tests/test_product_menu_mtf.py:182-194`: asserts `_is_zone_sweep` on armed POI opens one-shot episode.
8. **Product path:** In Stage 0A scanner: NO. In Stage 2.5 Multi-TF Menu confirmation: YES, but via `_is_zone_sweep(bar, zone)` directly, bypassing Stage 0A `LiquidityLevel`.
9. **Verdict:** `PARTIAL` (enum exists; research script constructs levels; product menu sweeps POI zones directly via `_is_zone_sweep`, but Stage 0A scanner does not construct them as `LiquidityLevel` pools).
10. **Evidence:**
```python
# 04_SRC/smc/detection/liquidity_scanner.py:11-13
# The remaining §2 level types (POI_LEVEL, DEMAND_SUPPLY_BOUNDARY,
# ORDER_BLOCK_BOUNDARY) depend on POI zones and are produced in Phase 2+.
# 04_SRC/smc/orchestration/product_menu_mtf.py:124-135
def _is_zone_sweep(bar: Candle, zone: Zone) -> bool:
    if zone.direction is Direction.LONG:
        return bar.low < zone.bottom and bar.close > zone.bottom
    return bar.high > zone.top and bar.close < zone.top
```

---

### Level 7: Demand/Supply or OB Boundary Extremes as Fallback Pools
1. **EXISTS?** PARTIAL
2. **Source file(s) + function(s):**
   - Enum declarations: `04_SRC/smc/core/enums.py:33-34, 64-65`:
     - `LiquidityType.DEMAND_SUPPLY_BOUNDARY = "demand_supply_boundary"`
     - `LiquidityType.ORDER_BLOCK_BOUNDARY = "order_block_boundary"`
     - `PoolType.EXTREME_ZONE = "extreme_zone"`
     - `PoolType.OB_EXTREME = "ob_extreme"`
   - In research scripts: `06_RESEARCH/scripts/track_a_sweep_ledger.py:144-145` constructs `LiquidityLevel(type=LiquidityType.ORDER_BLOCK_BOUNDARY)` from `LAST_OPPOSITE_BEFORE_BOS` bounds.
   - In product confirmation spine: `04_SRC/smc/orchestration/product_menu_mtf.py` checks sweeps of any armed POI zone (which includes M8 Demand/Supply and M1/M8 Order Blocks).
   - Discrete "in-between failed $\to$ fallback to boundary sweep" mechanism (§2 Rule 5/6 & §25): **MISSING**. The engine does not have an explicit fallback state transition.
3. **Geometry:** Full-wick extreme of the zone boundary (`zone.bottom` for demand / `zone.top` for supply).
4. **Time rules:** Monitored on detection TF bars while POI is armed.
5. **Parameters:** None.
6. **Output type:** In research script: `LiquidityLevel`. In product menu: `MenuEpisode`.
7. **Tests:**
   - `04_SRC/tests/test_track_a_sweep_ledger.py:20-25` (tests `PoolType.OB_EXTREME`).
8. **Product path:** In Stage 0A scanner: NO. In product menu: implicitly handled as general zone sweeps. Explicit §25 fallback state machine is absent.
9. **Verdict:** `PARTIAL` (enums exist; research script builds OB boundaries; product menu sweeps zone boundaries; explicit §25 fallback state switch is MISSING).
10. **Evidence:**
```python
# 04_SRC/smc/core/enums.py:33-35
DEMAND_SUPPLY_BOUNDARY = "demand_supply_boundary"  # HTF D/S zone extreme sweep
ORDER_BLOCK_BOUNDARY = "order_block_boundary"      # OB extreme wick sweep
# 06_RESEARCH/scripts/track_a_sweep_ledger.py:144-145
elif family == "ORDER_BLOCK":
    level_type = LiquidityType.ORDER_BLOCK_BOUNDARY
```

---

## 3. Summary Scoreboard

```text
LEVEL_SCOREBOARD: {IMPLEMENTED: 5, PARTIAL: 2, MISSING: 0, CONTRADICTS_LOCK: 0}
SESSION_LEVELS: IMPLEMENTED
PDH_PDL: IMPLEMENTED
PWH_PWL: IMPLEMENTED
EQH_EQL: IMPLEMENTED (tolerance constant: EQH_EQL_TOLERANCE = 4.5)
STRUCTURAL_SWINGS: IMPLEMENTED (N-bar constants: N_BAR_HTF = 5, N_BAR_LTF = 3)
POI_AS_LIQUIDITY_POOLS: PARTIAL
FALLBACK_BOUNDARY_POOLS: PARTIAL
```

---

## 4. Ranked Gaps for Lead Architect (Top 5 Only)

1. **Stage 0A Scanner Excludes POI-Derived Liquidity Levels (Levels 6 & 7)**:
   - `liquidity_scanner.py` hardcodes `ALL_FAMILIES = ("session", "periodic", "equal", "structural")`.
   - `POI_LEVEL`, `DEMAND_SUPPLY_BOUNDARY`, and `ORDER_BLOCK_BOUNDARY` are never constructed as `LiquidityLevel` objects within `04_SRC/smc/detection/`.
   - *Impact:* Stage 0A only scans market-wide levels; POI zone sweeps are only detected downstream in `product_menu_mtf.py`.
2. **Explicit §25 Fallback Boundary State Switch Missing**:
   - LOCKED §2 Rule 5/6 and §25 dictate: *"If price enters zone body without in-between mitigation entry $\to$ activate boundary sweep path"*.
   - *Impact:* The engine evaluates zone sweeps directly in `ProductMenuEngine._is_zone_sweep` upon candle close, but lacks a formal two-phase fallback switch (interior trigger first, boundary sweep second).
3. **Pool Direction Mapping Gap for Boundary Pools**:
   - Helper function `_pool_direction` in `track_a_sweep_ledger.py` only handles `PoolType.BSL` and `PoolType.SSL`, explicitly raising `ValueError("unsweepable pool")` for `PoolType.OB_EXTREME`.
   - *Impact:* Non-BSL/SSL pool types cannot be processed by standard sweep ledger tools without aliasing to BSL/SSL.
4. **Trigger D Volume Inactivity on Standard Feeds**:
   - Trigger D (Two-Bar Reversal) requires `volume(bar2) < volume(bar1)`. On tickless/volume-less broker feeds, it remains permanently dormant.
5. **Evening Session Unclassified Gap (20:00–24:00 UTC)**:
   - `detect_session` returns `None` for candles between 20:00 and 24:00 UTC per §2 session windows, meaning no session levels are formed during late NY / early Asia rollover.

---

## 5. Explicit "P2 Next" Boundary (Sweep Interaction)

The boundary between **P1 (Level Construction)** and **P2 (Sweep Interaction)** is strictly delimited:

- **P1 Scope (Completed):** What levels exist, their geometry (wick extremes, Base Candle anchors), their time bounds (UTC sessions, Monday weeks), parameters (`EQH_EQL_TOLERANCE=4.5`, `N_BAR_HTF=5`, `N_BAR_LTF=3`), and constructor output objects.
- **P2 Scope (Next Engagement):**
  1. *Sweep Mechanics:* How price interacts with levels (`c.high > level and c.close < level` vs `_is_zone_sweep`).
  2. *Causality & Temporal Filtering:* Enforcement of `formed_at` bounds to prevent immediate self-sweeps.
  3. *Post-Sweep Lifecycle:* Handling multiple touches per level, level consumption, and displacement generation after sweep.
  4. *Multi-TF Sweep Coordination:* Sweep detection on HTF (D1/H4/H1) feeding LTF confirmation windows.

