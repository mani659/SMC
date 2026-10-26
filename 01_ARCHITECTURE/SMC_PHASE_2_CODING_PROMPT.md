# Phase 2 — Coding Prompt

```
Lead Architect Instruction — Phase 2: POI Classification

Phase 0 (Foundations) and Phase 1 (Core Detection) are complete and locked
(92/92 tests). Begin Phase 2.

### Goal
Implement Stage 1 (POI Model Classification — M1–M8 modular tags) and
Stage 1b (CHOCH Rule 1/2/3 classification) inside `04_SRC/smc/poi/`,
together with the model registry, confluence scorer, deal-range
premium/discount utilities, and per-model acceptance fixtures.

### Strict Rules
1. Every numeric threshold must come from `smc.config.locked_constants`.
   Do not invent numbers. Where the specs reference a NON-frozen tolerance
   band (e.g. R1's "1–2 ATR" zone padding), you may not hardcode it in
   `locked_constants.py`; use a clearly-labeled module-level "UNFROZEN V1"
   constant with a one-line rationale, and list it under ambiguities so it
   can be locked before live use.
2. Definitions are frozen in:
   - `00_LOCKED/LOCKED_DECISIONS.md` — §1 (8 EQUAL tags, confluence tiers),
     §4 (detection TF per model), §6 (dealing range P/D), §8 (M5 vs M7),
     §9/§17/§20 (CHOCH entry + Rule 1/2/3), §13 (zone refinement — Pillar 1),
     §21/§22/§26 (Model 8 zones, overlap bonus), §2/§3 (inputs).
   - `00_LOCKED/SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md` §5 — per-model
     machine geometry (the authoritative pattern definitions).
   - `00_LOCKED/DEVELOPMENT_PLAN.md` Phase 2 — module responsibilities.
   NOTE: R1 §8/§11 text mentioning a "model priority hierarchy" or
   "highest priority model wins" is SUPERSEDED by LOCKED_DECISIONS §1:
   all 8 models are equal tags, none is suppressed, none overrides another.
3. Use the Phase 0 core types and Phase 1 outputs: `Candle`, `Swing`,
   `Zone`, `LiquidityLevel`, `POI`, `ModelType`, `Direction`, enums, and
   `smc.detection` (`detect_swings`, `detect_equal_levels`, `detect_fvgs`,
   `scan`, displacement checker). Consume them; do not re-implement.
4. Python 3.10+; type hints + short docstrings on every public class/method.
5. Unit tests with synthetic OHLCV for every module, plus an acceptance
   fixture per model (M1–M8) that reproduces the canonical R1 §5 pattern.
6. Do NOT implement triggers (A–F), 5-pillar validation, execution, or risk
   yet. Pillar 3's premium/discount PASS/FAIL gate is Phase 3 — Phase 2 only
   provides the dealing-range + region utilities it will consume.
7. After finishing, update `00_LOCKED/TODO.md` (check off Phase 2 items) and
   add an entry to `00_LOCKED/CHANGELOG.md`.

### Modules to Build (exact list)

```
smc/poi/
├── __init__.py
├── base_model.py                  # Abstract base class for all POI models
├── model_registry.py              # Registry: ModelType -> model instance
├── confluence_scorer.py           # Independent-tag count, quality tiers,
│                                  #   overlap grouping/merge, M8 +0.10 bonus
├── choch_classifier.py            # CHOCH Rule 1/2/3 classification (§17)
├── deal_range.py                  # Dealing range + premium/discount (§6, §3.4)
├── models/
│   ├── __init__.py
│   ├── m1_origin_base.py          # Origin Demand/Supply Base
│   ├── m2_rbs_sbr_breaker.py      # RBS/SBR Breaker Flip
│   ├── m3_choch_retest.py         # CHOCH Retest (3 sub-variants 3a/3b/3c)
│   ├── m4_quasimodo.py            # Quasimodo (QML)
│   ├── m5_extreme_equal_highs.py  # Extreme Equal Highs / Supply Origin
│   ├── m6_neckline_retest.py      # Neckline / Double Top-Bottom
│   ├── m7_equal_resistance.py     # Equal Resistance Shelf (reactive)
│   └── m8_htf_demand_supply.py    # HTF D1/H4 zones (OB/FVG/Demand/Supply)
```

### Key Behaviour Requirements

**Model interface (base_model.py)**
- Abstract `POIModel` with `detect(self, candles, swings, liquidity_levels)
  -> list[POI]` (per DEVELOPMENT_PLAN). Each returned POI carries its OWN
  single model tag in `models` (e.g. `[ModelType.M3]`), a concrete `Zone`
  (top/bottom/direction/timeframe), and `state=POIState.CREATED`.
- Models are configured with their supported detection timeframes per §4;
  a model called on an unsupported timeframe raises or logs a clear error.
- Multi-timeframe models (M8) take their HTF candle series via constructor
  (registry configuration), keeping `detect()`'s signature stable.

**Model geometry (per R1 §5 — implement deterministically)**
| Model | Formation | POI zone source | Direction |
|---|---|---|---|
| M1 | Validated swing origin → BOS+FVG displacement away → no retest | `[origin_swing_low, origin_candle_high]` (bull) / mirror (bear) | with origin |
| M2 | Validated swing broken by opposite BOS → no retest | broken swing level zone | flip side |
| M3 | Trend + sweep of final extreme + CHOCH Rule 1/2/3 | broken level per rule (§9/§20) | vs trend |
| M4 | LS → Head → neckline break → no LS retest | `[left_shoulder_low, left_shoulder_high]` full wick (§14) | vs Head |
| M5 | EQH/EQL cluster formed FIRST, then broken (proactive, §8) | equal-cluster wick range | vs cluster |
| M6 | Double top/bottom + neckline break | broken neckline zone | vs pattern |
| M7 | Reactive bounce shelf after drop, then broken (§8 vs M5) | bounce wick range | vs shelf |
| M8 | HTF (D1/H4) OB/FVG/Demand/Supply per §21/§22 | last opposing candle full wick, or FVG gap | zone direction |

Where a zone references a bare "level", derive the zone from the underlying
candles' full wick range or the frozen tolerance; where R1 gives a
non-frozen band, apply the "UNFROZEN V1" module constant (rule 1).

**CHOCH classifier (§17/§20)**
- Rule 1: body close beyond the LAST SWING of the main trend (highest).
- Rule 2: body close beyond an INTERMEDIATE level, last swing NOT broken.
- Rule 3: wick only beyond a structural level, no body close (kept; lowest).
- Returns classification + the exact broken/pierced level each rule uses for
  entry placement (§20), and a strength ranking 1 > 2 > 3.
- Model 3 must produce sub-variant POIs (3a/3b/3c) from these outputs.

**Dealing range + premium/discount (deal_range.py)**
- Per R1 §3.4: range defined by confirmed structural swings on the POI
  detection TF (use Phase 1 §19-valid swings from the supplied window);
  range position `(price - low) / (high - low)`; classify price as
  PREMIUM (> PREMIUM_THRESHOLD), DISCOUNT (< DISCOUNT_THRESHOLD), or
  EQUILIBRIUM (45–55% band) — thresholds from locked constants.
- Provide the utility + region enum only; the §6 reject gate runs in
  Phase 3 Pillar 3. Document the range-update semantics you implement
  (see ambiguities).

**Confluence scorer (§1)**
- Quality tiers from independent tag count: 1 = base, 2 = elevated,
  3+ = institutional-grade (frozen). No tag suppresses another.
- Group POIs whose zones overlap (non-empty intersection) into one POI with
  the union of model tags; recompute tier; apply `M8_HTF_OVERLAP_BONUS`
  (+0.10, quality-score only — never position size) when Model 8 tags a
  zone flagged `htf_overlap=True` (§21/§26).

**Model 8 (m8_htf_demand_supply.py)**
- Zone identification ONLY on D1/H4 (Step 1 of §21): OB = candle before the
  first FVG candle (R1 §3.1), FVG zones from `detect_fvgs`, Demand/Supply =
  the SINGLE last opposing candle before a strong impulse (§22, impulse =
  displacement ≥ 1× ATR per §3). No M5/M1 approach or trigger logic yet.
- Set `htf_overlap=True` when a D1 and an H4 zone overlap at the same level.

### Testing Requirements

- Unit tests for: `base_model` contract, `model_registry`, CHOCH
  Rule 1/2/3 classification (incl. intermediate vs last-swing cases),
  `deal_range` (premium/discount/equilibrium boundaries, frozen thresholds),
  `confluence_scorer` (tiers 1/2/3+, overlap merge, M8 +0.10 bonus).
- **M1–M8 acceptance fixtures**: for each model, one synthetic OHLCV pattern
  reproducing its canonical R1 §5 geometry asserting the emitted POI
  (zone bounds, direction, model tag), and one decoy pattern asserting NO
  emission. Name them `04_SRC/tests/test_model_m1_origin_base.py` … 
  `test_model_m8_htf_demand_supply.py` (one file per model).
- Every detector test must use synthetic candles via the shared
  `candle_factory` fixture in `04_SRC/tests/conftest.py`.

### Deliverable
When finished, report:
1. Final list of files created/updated under `04_SRC/smc/poi/` + tests.
2. Number of new unit tests and total pass count (run
   `python -m pytest tests` from `04_SRC/`).
3. Every ambiguity/edge case encountered, including:
   - each "UNFROZEN V1" module constant you had to introduce and why,
   - dealing-range update semantics chosen,
   - zone representation for level-based models,
   - M5 (proactive) vs M7 (reactive) disambiguation on real geometry,
   - lookback-window handling (window inputs are caller-supplied).
4. Confirmation that TODO.md Phase 2 items are checked and CHANGELOG.md has
   the new entry.

Begin Phase 2 now.
```
