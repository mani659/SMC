# Stage 0A — Code ↔ Flowchart Map (Audit)

**Date:** 2026-11-10  
**Authority:** Lead Architect / Design Architect; layered plan `06_RESEARCH/LAYERED_FIDELITY_PLAN.md` (L1 before L2–L5).  
**Scope:** level-by-level audit of core Stage 0A principles independently. No expectancy, no LTF wiring, no entry/SL/TP tuning, no OPT-*. **LOGIC_CHANGED: NO** (read-only use of existing detectors/scanners/POI emitters; research/docs only).  
**Related:** `06_RESEARCH/L1_H4_SWEEP_FIDELITY_NOTE.md`, `06_RESEARCH/LAYERED_FIDELITY_PLAN.md`.

---

## 1) Flowchart Stage 0A intent (3 blocks + POI spine)

Source: `01_ARCHITECTURE/Flowcharts/v5_SMC_Locked_Decisions_Flowchart.md` (Revision 5, 2026-09-01).

| Block | Intent (flowchart, condensed) |
|---|---|
| **Stage 0A — Structural liquidity levels & sweep detection** | Scan master structural liquidity pools (session highs/lows Asia/London/NY; PDH/PDL, PWH/PWL; EQH/EQL, tolerance ≤ 4.5 pips XAUUSD frozen; structural swing H/L confirmed by Base Candle Gate; POI-level sweeps OB/FVG at POI = liquidity sweep; D&S/OB fallback boundary sweeps). **Sweep rule:** wick pierces structural level + candle body closes inside. No sweep → no event. |
| **Stage 0b — Displacement check** | After sweep, aggressive impulse: BOS confirmed (close beyond prior swing) + FVG created (3-candle imbalance) + displacement magnitude > 1× ATR minimum (frozen). No BOS/no FVG/<0.5× ATR → no event. |
| **Stage 0c — Swing validation gate** | Validate underlying swing before POI classification: base candle at extreme; price later breaks base candle opposite extreme by **body close** → VALID swing (wick-only/invalid → no POI). |

**POI spine (main pillar, downstream of 0A–0c):** Stage 1 POI model classification (M1–M8, modular equal tags/confluence) → Stage 2 validation pillars → triggers/execution. Flowchart lists M8 HTF Demand/Supply as full peer (OB/FVG/D&S zones on D1/H4; D1+H4 overlap bonus) and states POI is the spine; sweep alone is not the product. Stage 0A-level families named in flowchart also include POI/OB/FVG/D&S boundary sweeps (see §3, §6 gaps).

**Locked text cross-references:** `00_LOCKED/LOCKED_DECISIONS.md` §2 (Master Liquidity Levels & Structural Sweep Architecture, Stage 0A), §3 (Displacement Requirements), §4/§4a (Detection TF roles/policy), §21–§22/§26 (Model 8 HTF Demand/Supply, overlap). `00_LOCKED/SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md` references liquidity levels (Stage 0A master classification). `00_LOCKED/FOUNDATION_RESET_PLAN.md` / `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` govern multi-TF/runtime wiring (context), not redefined here.

---

## 2) Code inventory table

| Flowchart concept | Module/symbol | What it emits | Filters applied (as-coded) | Frozen constant names (as-coded/cited) |
|---|---|---|---|---|
| Master structural liquidity pools (Phase 1 families) | `smc.detection.liquidity_scanner.scan` (`04_SRC/smc/detection/liquidity_scanner.py`), `ALL_FAMILIES=("session","periodic","equal","structural")` | `list[LiquidityLevel]` in §2 family order; structural only when swing `is_valid` | Family filter via `include`; structural gated by `swing.is_valid` (scanner). Swings from `detect_swings` (Base Candle / §19 gate in structural swing path) | `N_BAR_LTF` (used by swing detector window per implementation), `EQH_EQL_TOLERANCE_PIPS` (equal-level detector), session/periodic windows per their detectors — **exact constant names live in `smc.config.locked_constants` / detector modules**; scanner itself does not take ATR/tolerance params |
| Session highs/lows | `smc.detection.session_levels.detect_session_levels` (called by scanner) | Session `LiquidityLevel`s (BSL/SSL by side) | Session definitions/windowing as implemented | Session constants per `smc.config.locked_constants` / module (see §3; **NOT IN CODE** exhaustively enumerated in scanner) |
| PDH/PDL, PWH/PWL | `smc.detection.periodic_levels.detect_periodic_levels` | Periodic `LiquidityLevel`s | As implemented | Periodic constants per module/locked config |
| EQH/EQL clusters | `smc.detection.eqh_eql_detector.detect_equal_levels` (fed by `detect_swings`) | Equal-high/low `LiquidityLevel`s | Tolerance per locked constant used by detector | `EQH_EQL_TOLERANCE_PIPS` (`smc.config.locked_constants`, frozen ≤4.5 pips XAUUSD per flowchart/LOCKED_DECISIONS) |
| Structural swing pools | `smc.detection.structural_swing_detector.detect_swings` → scanner emits `LiquidityType.STRUCTURAL_SWING` for valid swings | `LiquidityLevel(type=STRUCTURAL_SWING, level, pool, timeframe, formed_at)` | `is_valid` swings only; Base-Candle/swing validity per detector/validator | Swing/validity constants per `structural_swing_detector` / `swing_validator` / locked constants (see §4, §7) |
| Liquidity sweep discovery (wick-pierce + close-back) | `smc.detection.sweep_detector.detect_sweep`, `detect_sweeps` (`04_SRC/smc/detection/sweep_detector.py`) | `SweepResult(level, candle_index, candle)`; first confirmed sweep per level, candle-ordered | BSL: `high > level and close < level`; SSL: `low < level and close > level`; scan only after `formed_at` (when set) / `start_index`; breakout-close beyond level excluded by rule | **None named as thresholds** in sweep rule (geometric wick/body vs level) |
| Displacement (BOS + FVG + magnitude) | `smc.detection.displacement_checker.check_displacement` (`04_SRC/smc/detection/displacement_checker.py`); `DisplacementResult` | `DisplacementResult(direction, bos, fvg, magnitude, magnitude_atr, atr, passed, hard_fail, is_preferred, bos_index)` | `bos_index` = first close beyond `bos_level` after `sweep_index`; directional FVG in [sweep_index, bos_index] via `smc.detection.fvg_detector.detect_fvgs`; magnitude = sweep extreme → BOS close (or best close if no BOS) vs **pre-sweep** ATR `latest_atr(candles[:sweep_index])`; pass requires `bos and fvg and magnitude_atr >= DISPLACEMENT_MIN_ATR` | `DISPLACEMENT_MIN_ATR`, `DISPLACEMENT_HARD_FAIL`, `DISPLACEMENT_PREFERRED_ATR` (`smc.config.locked_constants`, imported by checker) |
| FVG (3-candle imbalance) | `smc.detection.fvg_detector.detect_fvgs`, `FVG` (`04_SRC/smc/detection/fvg_detector.py`) | `list[FVG]` with `zone`, `start_index` (first of 3-candle set) | Bullish: `third.low > first.high`; Bearish: `third.high < first.low`; chronological | **NOT IN CODE** as named frozen constant beyond geometric definition (3-candle set) |
| Stage 0→displacement→POI attribution (product/research driver path) | `smc.orchestration.detection_driver.DetectionDriver.stage0/_displacement_for_sweep/attribute_displacement/validate_window/run` (`04_SRC/smc/orchestration/detection_driver.py`) | `DetectionRun` (swings, liquidity_levels, sweeps, per-sweep `(sweep_index, DisplacementResult)`), displacement_map `poi_id -> DisplacementResult`, validated/armed POIs via `PipelineEngine` | Displacement evaluated per sweep with BOS level = most recent prior swing extreme of move direction before sweep (SSL→LONG/prior swing low, BSL→SHORT/prior swing high); **no** displacement if no prior extreme; attribution = most recent same-direction displacement per POI; models that raise are skipped (recorded) | ATR period arg/default (indicator param, e.g. 14) — **not a frozen displacement threshold** |
| Pillar 2 (displacement validation) | `smc.validation.pillar_2_displacement` / `smc.validation.pillar` (`04_SRC/smc/validation/*`, engine pipeline) | Validation pass/reject based on supplied displacement in context (UNAVAILABLE → reject per driver honesty) | Engine expects per-POI displacement map; missing → Pillar 2 rejects (driver contract) | Threshold semantics enforced via `DisplacementResult.passed/hard_fail` derived from frozen constants above |
| POI emission (M8 HTF D/S/OB/FVG zones) | `smc.poi.models.m8_htf_demand_supply.M8HtfDemandSupply` (`04_SRC/smc/poi/models/m8_htf_demand_supply.py`) | `list[POI]` (zone + `models=[M8]`, `m8_kind` in {`ob`,`demand_supply`,`fvg`}, `htf_overlap`) per HTF timeframe scanned | Scans `HTF_TIMEFRAMES=(W1,D1,H4)` (as-coded) over supplied `htf_candles`; per-kind keeps most recent `(direction, kind)` per TF scan result path; episode collapse by geometric key with kind priority (`ob > demand_supply > fvg`); D1×H4 same-direction zone overlap sets `htf_overlap=True` (W1 not paired) | `DISPLACEMENT_MIN_ATR`, `N_BAR_LTF` (demand/supply impulse window in `_zones`) |
| POI emission (general models M1–M8) | `smc.poi.base_model.POIModel`, `smc.poi.model_registry.build_registry` (`04_SRC/smc/poi/*.py`, `models/*.py`) | `list[POI]` per model.detect(candles, swings, liquidity_levels) | Registry/model-specific; driver runs all registered models, skips on exception | Model/geometry constants vary by model (inspect per model for claims) |
| POI core / tags / state | `smc.core.poi.POI` (`04_SRC/smc/core/poi.py`), `smc.core.zone.Zone`, `smc.core.enums` | POI dataclass: zone, models, score, state, touch_count, htf_overlap, id, m8_kind | Equal-weight tags (deduped on add); freshness/state machine applied in validation/engine flows | POI states/freshness rules per `LOCKED_DECISIONS` §5 and `smc.validation.state_machine` |

---

## 3) Liquidity pool families

### 3.1 Families emitted by the Phase 1 scanner (`smc.detection.liquidity_scanner.scan`)

| Emitted family (scanner key) | `LiquidityType` | Pool semantics (enum) | Master structural pool? (vs flowchart Stage 0A language) |
|---|---|---|---|
| `session` | `SESSION` | `BSL`/`SSL` (directional, per detector) | **PARTIAL** — flowchart names session highs/lows as master structural liquidity pools; `liquidity_scanner` doc states Phase 1 families currently produced; session is a defined §2 family but "structural swing confirmed by Base Candle Gate" is the explicit structural gate language primarily attached to `STRUCTURAL_SWING` in flowchart. |
| `periodic` | `PREVIOUS_DAY` / `PREVIOUS_WEEK` (per periodic detector) | `BSL`/`SSL` | **PARTIAL** — flowchart includes PDH/PDL, PWH/PWL as master pools; periodic extremes are §2 levels but not Base-Candle structural swings. |
| `equal` | `EQUAL_HIGHS_LOWS` | `BSL`/`SSL` | **PARTIAL** — flowchart includes EQH/EQL as master pool family with frozen tolerance; equality is cluster-derived (from swings) rather than a Base-Candle swing gate itself. |
| `structural` | `STRUCTURAL_SWING` | typically `MAJOR_STRUCTURAL` / directional pool per level (see `LiquidityLevel` construction) | **YES (closest match)** — flowchart: "Structural Swing High / Low: Strictly structural swings confirmed by Base Candle Gate (minor intermediate noise discarded)"; scanner emits **only** swings with `is_valid` true. |

**Other `LiquidityType` values defined but not emitted by Phase 1 `scan`:** `POI_LEVEL`, `DEMAND_SUPPLY_BOUNDARY`, `ORDER_BLOCK_BOUNDARY` exist in `smc.core.enums.LiquidityType` (and flowchart §0A names POI/OB/FVG/D&S boundary sweeps conceptually). `liquidity_scanner` doc: "The remaining §2 level types (POI_LEVEL, DEMAND_SUPPLY_BOUNDARY, ORDER_BLOCK_BOUNDARY) depend on POI zones and are produced in Phase 2+." **No Phase 1 emission path found in scanner for these.**

**Multi-label readiness:** scanner preserves overlapping levels across families (same price region can carry session/equal/structural tags) — dedup/confluence delegated to POI/validation layers (scanner docstring). Honesty: overlap of `LiquidityLevel` records is not the same as merged POI confluence scoring.

---

## 4) Sweep rule (as-coded) vs flowchart "liquidity sweep discovery"

| Aspect | Flowchart (v5 Stage 0A) | As-coded (`smc.detection.sweep_detector`) | Match |
|---|---|---|---|
| Confirmation | "Wick pierces structural level + candle body closes inside" | `detect_sweep`: BSL pool → `c.high > level.level and c.close < level.level`; SSL pool → `c.low < level.level and c.close > level.level` (single candle, wick-pierce + body-close-back) | **Aligned in mechanics** (level pierced by wick, body rejects/closes back on protected side) |
| Breakout exclusion | Implicit (sweep vs continuation) | Close beyond level = NOT a sweep (docstring: "A candle that closes beyond the level (a genuine breakout) is NOT a sweep.") | **Aligned** |
| Timing/formation | Sweep of formed pools | Scans only after `formed_at` when set (`_first_after`), else from `start_index`; cannot sweep at creating bar when `formed_at` enforced | **Aligned with anti-self-sweep intent** (when formed_at provided) |
| Cardinality | Event discovery | First confirmed sweep per level (`detect_sweep` returns first); `detect_sweeps` collects per level and sorts by candle index | **As-coded behavior** (one sweep result per level max) |
| Pool coverage | Master structural pools incl. POI/D&S/OB boundary notions in text | Operates on any `LiquidityLevel` passed in (pool BSL/SSL logic); scanner Phase 1 supplies session/periodic/equal/structural only | **PARTIAL** — rule applies generically, but POI/D&S/OB boundary **levels** are not Phase 1-scanned (see §3, §7) |

---

## 5) Displacement rule (as-coded)

Source: `smc.detection.displacement_checker.check_displacement`, `DisplacementResult` (`04_SRC/smc/detection/displacement_checker.py`).

| Item | As-coded |
|---|---|
| **Inputs** | `candles` (chronological series), `direction` (LONG after SSL sweep, SHORT after BSL sweep), `sweep_index`, `bos_level` (prior swing extreme: prior swing low for LONG, prior swing high for SHORT), `atr_period` (default 14), optional precomputed `atr` (pre-sweep, bars strictly before sweep), optional precomputed `fvgs` for same candles |
| **BOS** | `bos=True` when first candle after `sweep_index` closes beyond `bos_level` in move direction (`close > bos_level` for LONG, `<` for SHORT); records `bos_index` |
| **FVG confirmation** | Searches FVGs with `f.start_index >= sweep_index and <= bos_index` and `f.zone.direction == direction` (uses supplied `fvgs` or `detect_fvgs(candles)`); `fvg=True` if any match |
| **Magnitude measurement (V1, documented in module)** | `sweep extreme → BOS close` when BOS exists; else sweep extreme → best close after sweep (max for LONG, min for SHORT) if any; `None` if no bars after sweep. Compared against **PRE-SWEEP Wilder ATR** (`latest_atr(candles[:sweep_index])` or supplied `atr`) — impulse does not inflate its own reference |
| **Magnitude/ATR fields** | `magnitude` (price), `magnitude_atr` (price/ATR), `atr` (pre-move) |
| **Pass/fail flags** | `passed = bos_index is not None and fvg and magnitude_atr is not None and magnitude_atr >= DISPLACEMENT_MIN_ATR`; `hard_fail = magnitude_atr is not None and magnitude_atr < DISPLACEMENT_HARD_FAIL`; `is_preferred = magnitude_atr is not None and magnitude_atr > DISPLACEMENT_PREFERRED_ATR` |
| **Frozen constant names** | `DISPLACEMENT_MIN_ATR` (1× ATR minimum), `DISPLACEMENT_HARD_FAIL` (0.5× ATR), `DISPLACEMENT_PREFERRED_ATR` (1.5× ATR) — `smc.config.locked_constants` (LOCKED_DECISIONS §3) |
| **When it runs relative to sweep (product driver)** | `DetectionDriver.stage0` runs sweeps, then for **each** sweep calls `_displacement_for_sweep` → `check_displacement(...)` (post-sweep evaluation over subsequent candles); `attribute_displacement` assigns most recent same-direction displacement to POIs. So displacement is evaluated **after** each sweep event in the same Stage 0/1 pass, not before sweep detection. |

**Flowchart 0b alignment:** requires BOS + FVG + magnitude > 1× ATR and rejects <0.5× ATR / missing BOS/FVG — consistent with `passed`/`hard_fail`/component flags, subject to how `bos_level` is chosen by caller (driver uses prior swing extreme of move direction).

---

## 6) POI link

### 6.1 As implemented (observed in code paths read)

| Mechanism | Where | Association basis | Notes |
|---|---|---|---|
| **Displacement → POI (directional, recency)** | `DetectionDriver.attribute_displacement` (`04_SRC/smc/orchestration/detection_driver.py`) | Most recent `DisplacementResult` (by sweep index order processed) whose **direction** matches `poi.zone.direction` (LONG POI ↔ latest SSL-sweep impulse, SHORT ↔ latest BSL-sweep impulse). Produces `displacement_map[poi.id]`. | **No** per-POI geometric join to a specific swept level/zone/bar beyond direction + recency of sweep direction. POI with no matching-direction displacement gets **no entry** → Pillar 2 rejects (UNAVAILABLE) per driver contract. |
| **Sweep/level → POI geometry** | **NOT IN CODE** as an explicit hard join in `DetectionDriver`/sweep path read above. POIs are emitted by models from `(candles, swings, liquidity_levels)`; M8 emits zones from HTF candle structure (OB/FVG/demand_supply episodes) independently of `SweepResult` objects. | — | A swept `LiquidityLevel.level` may fall inside/outside some POI zone, but the driver does not compute or persist that relationship. |
| **POI/OB/FVG boundary as liquidity levels** | `LiquidityType.POI_LEVEL/DEMAND_SUPPLY_BOUNDARY/ORDER_BLOCK_BOUNDARY` defined in enum; scanner states Phase 2+ | Would be level objects if produced | **Phase 1 scanner does not emit them**; no code path in `liquidity_scanner.scan` produces these families. |

### 6.2 Classification (honest)

- **Displacement attribution to POIs:** **IMPLICIT_ONLY / DIRECTIONAL** (same-direction, most-recent sweep impulse) — not a hard link to a specific sweep event or specific POI zone geometry.
- **Sweep event → specific POI zone:** **ORPHAN_SWEEP (with respect to hard join)** in the Stage 0/1 driver path read: sweeps are recorded in `DetectionRun.sweeps`, but there is no persisted `sweep_id ↔ poi_id` link and no zone-containment join. POIs may exist without any swept level reference attached.
- **POI without attributable displacement:** treated as lacking displacement input (→ Pillar 2 UNAVAILABLE/reject) in the driver; this is a validation consequence, not a sweep-link record.

---

## 7) Gaps list (numbered)

1. **POI/D&S/OB boundary liquidity families not in Phase 1 scan:** `LiquidityType.POI_LEVEL`, `DEMAND_SUPPLY_BOUNDARY`, `ORDER_BLOCK_BOUNDARY` are defined (`smc.core.enums`) and named in flowchart/LOCKED_DECISIONS intent, but `liquidity_scanner.scan` (Phase 1) emits only `session/periodic/equal/structural` and explicitly defers those to Phase 2+. Stage 0A "POI Level Sweeps / fallback boundary sweeps" as scanner-produced levels are **not present** in Phase 1 code path.
2. **No hard sweep↔POI join:** `DetectionDriver` records sweeps and per-sweep displacements but attributes displacement to POIs only by **direction + recency** (`attribute_displacement`), not by swept level identity, bar equality with POI origin, or zone containment. Enriched chain measurement must define explicit join rules (see Part B) because none are codified for this linkage.
3. **Ordering nuance vs flowchart 0A→0b→0c:** Flowchart depicts sweep → displacement → swing validation gate → POI classification. In code, `DetectionDriver.stage0` computes swings, scans levels, detects sweeps, then evaluates displacement per sweep (using prior swings for BOS level) in one pass; POI models consume candles/swings/liquidity_levels. Swing validity is embedded in swing detection/validation (`is_valid`) feeding levels/models rather than a separate named "Stage 0c gate object" after displacement — **implementation ordering differs from flowchart block diagram** (audit observation; no code change proposed).
4. **M8 HTF scan set vs flowchart text:** Flowchart Stage 1/M8 text states "OB, FVG zones on D1/H4" (and LTF approach context). `M8HtfDemandSupply.HTF_TIMEFRAMES = (W1, D1, H4)` scans W1/D1/H4 when provided (`04_SRC/smc/poi/models/m8_htf_demand_supply.py`), with D1×H4 overlap pairing only. **Partial mismatch** in documented TF enumeration vs flowchart prose (W1 present in code; pairing rule narrower).
5. **Definition scope of "master structural liquidity pools":** Scanner includes session/periodic/equal alongside Base-Candle-gated structural swings; flowchart emphasizes "strictly structural swings confirmed by Base Candle Gate" and also lists other master pools. Mapping is **mixed** (see §3) — "master structural" as a single gate applies cleanly to `STRUCTURAL_SWING` emissions but is weaker/implicit for other Phase 1 families.
6. **Displacement BOS level choice is caller-dependent:** `check_displacement` requires `bos_level` (prior swing extreme). Driver derives it from most recent prior swing of move direction before sweep (`most_recent_swing`); a different caller could supply a different `bos_level`. "As-coded" in checker is parameterized; "as-used" in driver is swing-extreme based — must be cited when interpreting results.
7. **FVG definition source:** 3-candle imbalance implemented in `smc.detection.fvg_detector.detect_fvgs` (geometric). Flowchart/locked text state "FVG created (3-candle imbalance gap)"; numeric gap tolerance beyond geometry is **NOT IN CODE** as a separate named constant in detector.

---

## 8) Non-goals and Architect decision inputs

**Non-goals (this task):** no threshold proposals that change code; no edits to `04_SRC/smc` decision paths or `locked_constants.py`; no expectancy, no LTF wiring, no entry/SL/TP tuning, no OPT-*; no new ATR bands invented for joining.

**Architect decision inputs (design options, non-binding, no code change implied):** (a) whether Phase 2+ POI/D&S/OB boundary `LiquidityLevel` emission should be brought into Stage 0A scans for parity with flowchart boundary-sweep language; (b) whether a persisted hard join `sweep_id/level_id ↔ poi_id` (bar/level/zone containment) is required to move from `ORPHAN_SWEEP/IMPLICIT_ONLY` attribution to traceable FULL_0A chains; (c) clarify "master structural pool" membership for session/periodic/equal vs structural-only in reporting; (d) reconcile flowchart 0a/0b/0c block ordering with driver pass ordering in future specs (observation only). All require Architect ruling; this map records current as-coded state only.

---

*Every claim above is cited to a repo path/symbol or marked **NOT IN CODE** where applicable.*