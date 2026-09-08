# Combined Independent Audit — Phases 0, 1 & 2 (Foundations, Core Detection, POI Classification)

**Audit date:** 2026-09-06
**Auditor:** Independent audit (Buffy), performed per request; no code modified.
**Authority chain used:** `00_LOCKED/LOCKED_DECISIONS.md` (Rev 5, frozen 2026-09-01) → `00_LOCKED/SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md` (§3–§5) → `00_LOCKED/DEVELOPMENT_PLAN.md` → `01_ARCHITECTURE/SMC_PHASE_2_CODING_PROMPT.md`.
**Method:** Every source file under `04_SRC/smc/` read in full; every value traced to LOCKED_DECISIONS; test suite executed; test counts recomputed from source; TODO.md/CHANGELOG.md claims cross-checked against reality.

---

## Executive Verdict

| Phase | Scope | Verdict | Findings |
|-------|-------|---------|----------|
| 0 — Foundations | Package tree, types, constants, data, utils | **PASS** | F0-1 (low), F0-2 (info) |
| 1 — Core Detection | Stage 0A/0b/0c — 10 modules | **PASS** | F1-1 (low), F1-2 (low), F1-3 (info) |
| 2 — POI Classification | Stage 1/1b — 12 modules + scorer/deal-range | **PASS** | F2-1 (medium), F2-2 (low-medium), F2-3 (low) |
| **Combined** | **28 modules, 21 test files** | **PASS** | **133/133 tests pass; no invented thresholds found** |

**Bottom line:** The implemented code faithfully matches LOCKED_DECISIONS.md and the R1 specifications. No frozen threshold is invented, hardcoded, or drifted. All per-model R1 §5 geometries match. The 133-test claim is true. TODO.md and CHANGELOG.md accurately reflect reality. All findings are documentation/process gaps, none of which affect detection correctness.

---

## 1. Phase 0 — Foundations

### 1.1 Frozen constants (`smc/config/locked_constants.py`) — ✅ NO INVENTED NUMBERS

All 36 exported constants were compared value-by-value against LOCKED_DECISIONS.md:

| Group | Constants | Source | Match |
|-------|-----------|--------|-------|
| EQH/EQL | `EQH_EQL_TOLERANCE = 4.5` | §2 (FROZEN) | ✓ |
| Sessions | Asia 0–7, London 7–13, NY 13–20 UTC | §2 | ✓ |
| Confluence | tiers 1 / 2 / 3+ | §1 | ✓ |
| Displacement | 1.0 / 1.5 / 0.5× ATR | §3 | ✓ |
| Zone refinement | 0.5× ATR | §13 | ✓ |
| Premium/Discount | 0.55 / 0.45 (equilibrium 0.45–0.55) | §6 | ✓ |
| Expiry | M5=12, M1=30 bars | §5/§23 | ✓ |
| Inducement | 1.0 / 0.7 | §7 | ✓ |
| News | 15 / 30 min | §11 | ✓ |
| Model 8 | +0.10 bonus, RR 1:5, SL 2–5 pips | §21/§26 | ✓ |
| N-bar | HTF=5, LTF=3 | §27 | ✓ |
| Triggers A–F | 20 / 30 / 3 / 1 / 15 / 1 | §24 | ✓ |

Two deliberate exclusions are correctly handled:
- **v25_DIAG risk thresholds** (BE 1×ATR, circuit breaker 3→4h, same-level 0.1×ATR, Friday EOD 20:00, ADX ≥ 25, ATR floor) are **not present** — correctly excluded because they are proven-but-unfrozen; a comment block documents the exclusion and the Phase 5 plan.
- **§10 two-bar-reversal 50%-of-body** is not present — Phase 0 audit already flagged it as a Phase 4 item. Still outstanding (carried below as F0-1).

### 1.2 Core types (`smc/core/`) — ✅ MATCH

- `Candle` — frozen/slots dataclass, OHLCV + UTC timestamp + timeframe; bullish/bearish/body/wick properties correct.
- `Swing` — carries `base_candle`, `is_valid` (False until §19 confirmation), `confirmed_index`; `pool` property derives BSL/SSL per §2.
- `Zone` — validates `top >= bottom`; height/midpoint/contains/distance_from correct.
- `LiquidityLevel` — 8 §2 types enumerable in `LiquidityType`; `swept_at` mutable for detectors.
- `POI` — `models: list[ModelType]` (equal tags, §1), `state=POIState.CREATED` default, `htf_overlap` flag (§21/§26), duplicate `add_model` ignored.
- `enums.py` — `POIState` matches §5 machine (CREATED→FRESH→TESTED/VIOLATED, both terminal); `TriggerType` A–F per §12/§24.
- `Event` — envelope matches DEVELOPMENT_PLAN Phase 0.

### 1.3 Data + utils — ✅ MATCH

- `mt5_connector.py` — thin lazy-import facade; no connection at import (CI/test safe); methods mirror the MT5 API contract (`copy_rates_from_pos`, `order_send`, `order_check`, `account_info`, `positions_get`); Timeframe values ARE the MT5 `TIMEFRAME_*` integers so no mapping table. cab_watcher reusable patterns documented in the docstring as the TODO requires.
- `csv_loader.py` — stdlib only; flexible headers; ISO-8601/unix-s/munix-ms timestamps; OHLC sanity validation per row. (`load_tradelog` from the plan is not implemented — deferred until a trade-log format exists; see F0-2.)
- `redis_store.py` — **correctly absent** (OPTIONAL for V1, decision still open in TODO "Blocked/Waiting").
- `atr.py` — Wilder RMA with simple-average seed; matches MT5 `iATR` convention; correct `None` warm-up.
- `timestamps.py` — session windows read from locked constants; start-inclusive/end-exclusive; 20:00–24:00 → no session.
- `pips.py` — 1 pip = 0.1 price units with a loud NOT-FROZEN broker-dependency warning block (verify before Phase 4/7). The 4.5-pip frozen tolerance flows only through `pips_to_price`.
- `timeframe.py` — MT5-compatible IntEnum; §27 helpers `is_htf/is_ltf/n_bar_confirmation` correct.
- `model_type.py` — M1–M8 equal tags, no ranking (§1).

### 1.4 Phase 0 tests — ✅ (36)

`test_core_types` (7) + `test_enums` (8) + `test_locked_constants` (3, asserting every frozen name/value incl. `__all__` export) + `test_mt5_connector` (12, mocked) + `test_atr` (6) = **36**. The constants test is a genuine drift tripwire: any value change fails CI.

---

## 2. Phase 1 — Core Detection

### 2.1 §18 Base Candle (`base_candle.py`) — ✅ MATCH

- Swing high → the candle whose HIGH is the extreme (always `extreme_index`). §18 exact.
- Swing low → the candle whose LOW is the extreme, with the §18 bearish exception: previous bearish candle stays Base Candle when the next candle's wick makes the lower low and closes back at/above its low. Implemented exactly as §18's "if next candle wick is lower but current is bearish".
- Correctly **no** symmetric exception for swing highs (§18 does not define one) — documented in the module docstring.

### 2.2 §19 Swing Validity Gate (`swing_validator.py`) — ✅ MATCH

- Valid iff a later candle BODY-CLOSES beyond the Base Candle's opposite extreme (wick-pierce alone → invalid). Tracks `pierce_index` and `confirm_index` separately, which is precisely the §19 wick-vs-body distinction.
- Two-bar-reversal trap handled: no break+close → `is_valid=False`. §19 "Locked Rule" satisfied.

### 2.3 §27 Structural swings (`structural_swing_detector.py`) — ✅ MATCH

- N-bar fractal with N from `Timeframe.n_bar_confirmation` (HTF=5 / LTF=3, frozen).
- Plateau-safe: strict left / non-strict right comparisons resolve ties to the first plateau bar.
- Every candidate anchored via §18 and gated via §19; unconfirmed candidates returned with `is_valid=False` (consistent with §2's "structural liquidity — generic fractals do not qualify until Base-Candle-confirmed").

### 2.4 §2 Sweep detection (`sweep_detector.py`) — ✅ MATCH

- BSL: `high > level and close < level`; SSL: `low < level and close > level` — wick-pierce + body-close-back, matching §2/R1 §3.5. Breakouts correctly rejected.
- Levels cannot self-sweep: scan starts strictly after `formed_at`.

### 2.5 §2 EQH/EQL (`eqh_eql_detector.py`) — ✅ MATCH

- Frozen 4.5-pip tolerance via `pips_to_price`; anchor-bound greedy clustering (a cluster can never exceed the tolerance span — prevents tolerance-drift chaining).
- Level price = cluster extreme (highest high / lowest low), matching "Extreme Equal Highs" and §8; both BSL and SSL tracked concurrently (§2 rule 2).
- Works on swing candidates regardless of §19 validity — correct, since a liquidity pool exists at formation (documented in CHANGELOG notes).

### 2.6 §3 FVG + Displacement (`fvg_detector.py`, `displacement_checker.py`) — ✅ MATCH

- FVG: `low(c3) > high(c1)` bullish / `high(c3) < low(c1)` bearish, zone `[high(c1), low(c3)]` / `[high(c3), low(c1)]` — identical to R1 §3.2.
- Displacement: BOS close + directional FVG + magnitude ≥ `DISPLACEMENT_MIN_ATR` (1.0); hard fail < 0.5; preferred > 1.5 — all three §3 thresholds honored. V1 measurement definition (sweep extreme → BOS close vs pre-sweep ATR, so the impulse never inflates its own reference) is a documented measurement choice, not a threshold — no invented number.

### 2.7 §2 Session/Periodic levels + scanner (`session_levels.py`, `periodic_levels.py`, `liquidity_scanner.py`) — ✅ MATCH

- Session windows exactly §2 (Asia 00–07, London 07–13, NY 13–20 UTC), inclusive/exclusive boundaries consistent with `timestamps.py`.
- PDH/PDL/PWH/PWL from most recent **completed** trading day/week; weekend/holiday days skipped (Monday sees Friday). Monday-anchored weeks.
- Scanner emits 4 of the §2 families; POI_LEVEL / DEMAND_SUPPLY_BOUNDARY / ORDER_BLOCK_BOUNDARY correctly deferred to Phase 2+ (they need POI zones). Multi-label co-existence preserved per §1.

### 2.8 Phase 1 tests — ✅ (56)

10 files × (5–6 tests): base_candle 6, swing_validator 6, structural_swing 6, eqh_eql 6, sweep 6, fvg 5, displacement 6, session 5, periodic 5, scanner 5 = **56**. Synthetic OHLCV throughout via `candle_factory`.

---

## 3. Phase 2 — POI Classification (re-verified, unchanged from the prior Phase 2 audit)

### 3.1 Thresholds — ✅ no invented numbers
All numerics trace to `locked_constants.py`; the only literals in `smc/poi/` are the ATR period 14 (indicator parameter) and comments. The non-frozen R1 "1–2 ATR" M2 band was correctly NOT hardcoded.

### 3.2 R1 §5 geometry — ✅ 8/8 match

| Model | R1 §5 zone | Implementation | Fixture asserts |
|-------|-----------|----------------|-----------------|
| M1 | `[origin_swing_low, origin_candle_high]` | base-candle full range | 99.2/98.6 ✓ |
| M2 | broken level ± tolerance | broken-swing candle wick range | 100.0/99.6 ✓ |
| M3 | broken level per rule §9/§20 | Rule 1/2/3 level; zone from matching swing or ±0.5×ATR band | 99.6/99.0 ✓ |
| M4 | `[LS_low, LS_high]` full wick (§14) | LS base-candle range | 101.6/100.8 ✓ |
| M5 | equal-cluster wick range | full-wick union of both members | 101.5/100.2 ✓ |
| M6 | `[neckline_low, neckline_high]` | neck base-candle range | 100.8/100.0 ✓ |
| M7 | bounce wick range | shelf base-candle range | 110.6/109.8 ✓ |
| M8 | §3.1 OB / §3.2 FVG / §22 last opposing candle | OB = pre-FVG candle; §22 zone = opposing candle full range | ✓ |

CHOCH classifier matches §17/§20 (sweep pre-condition, strength 1>2>3, entry level per rule, Rule 3 kept). Deal range uses `(price − low)/(high − low)` on frozen 0.45/0.55; §6 gate correctly deferred to Phase 3. Confluence follows §1 equal-tags + tiers 1/2/3+; merge = union zone + union tags + earliest id; M8 +0.10 bonus applied to score only, never size.

### 3.3 Phase 2 tests — ✅ (41)

registry 5 + choch_classifier 6 + deal_range 5 + confluence 8 + poi_models 17 (8 acceptance + 8 decoy + M8 multi-TF/no-HTF cases) = **41**. Every acceptance fixture's asserted zone bounds were re-derived by hand and match the R1 §5 geometry.

---

## 4. Test totals — ✅ 133/133 EXECUTED

```
python -m pytest tests   (from 04_SRC/)
============================= 133 passed in 0.43s =============================
```

Independent recomputation by counting `def test_` per file across all 21 test files sums to exactly **133** = 36 (Phase 0) + 56 (Phase 1) + 41 (Phase 2). The claims in TODO.md and CHANGELOG.md are true.

---

## 5. TODO.md / CHANGELOG.md accuracy — ✅ with gaps noted

- TODO Phase 0: every checked item corresponds to a real file (only `redis_store.py` unchecked, matching the explicit deferral). ✓
- TODO Phase 1: all 10 modules checked off exist with the described behavior; "56 tests / 92 total" was true at the time and remains arithmetically consistent. ✓
- TODO Phase 2: all 16 checked items exist; registry path note (`model_registry.py` not `models/`) is accurate; "41 tests / 133 total" verified. ✓
- CHANGELOG entries for Phases 0, 0-audit, 1, 2 and the planning artifact are faithful; "no triggers/pillars/execution implemented" verified — `smc/validation`, `smc/triggers`, `smc/execution`, `smc/risk` etc. are empty placeholder packages, as claimed. ✓
- Phase table shows Phase 3 as next; consistent with the codebase state. ✓

---

## 6. Findings (none block Phase 3)

### Phase 0
- **F0-1 (low):** §10's frozen "limit order at 50% of the engulfing body" is still not a named constant in `locked_constants.py`. It belongs with Trigger D (Phase 4) and was already flagged in the Phase 0 audit entry; it remains open. *Action: add when Phase 4 begins.*
- **F0-2 (info):** DEVELOPMENT_PLAN's `load_tradelog` is not implemented (no trade-log schema exists yet). Acceptable for Phases 0–2; needed by Phase 6.

### Phase 1
- **F1-1 (low):** "Session timezone handling" from DEVELOPMENT_PLAN's missing-decisions list is handled by convention only — `to_utc` assumes naive datetimes are already UTC and the actual MT5 server-time → UTC conversion is deferred to the data boundary. No conversion layer exists yet. *Action: decide before Phase 6 backtesting with real MT5 exports.*
- **F1-2 (low):** `detect_swings` uses `min()/max()` comparisons on right windows (non-strict on the right, strict on the left) — plateau ties resolve to the FIRST bar. This is deterministic and documented, but a plateau's §18 base-candle anchor may differ from what the §18 special rule would pick if the extreme candle were chosen differently. Behavior is covered by tests; just be aware when reading plateau-heavy data. *Action: none required for V1; revisit if expert revises plateau semantics.*
- **F1-3 (info):** Displacement's V1 measurement definition (sweep extreme → BOS close vs pre-sweep ATR) is documented in-code and in SESSION_HANDOFF but is not restated in the ambiguities section of the CHANGELOG the way Phase 2's choices are. Cosmetic.

### Phase 2 (from the earlier audit, unchanged)
- **F2-1 (medium):** §4 detection-timeframe restriction is advisory only — `supported_timeframes` defaults to all timeframes and no model raises/logs on an unsupported TF, contrary to the coding prompt's "raise or log a clear error" requirement. The deviation is documented in code but was not listed in the CHANGELOG ambiguities as the prompt requires. *Action: either enforce §4 in `POIModel.__init__`/`detect` or add the deviation to the ambiguities record.*
- **F2-2 (low-medium):** Per-model test files were specified as `test_model_m1_origin_base.py` … `test_model_m8_htf_demand_supply.py`; actual coverage lives in a single `test_poi_models.py`. Coverage complete; organization deviates from the prompt's naming.
- **F2-3 (low):** M8 reuses `N_BAR_LTF` (§27's swing-confirmation count) as its impulse-lookahead horizon — a frozen number in a new role, undocumented in the ambiguities list (unlike the recorded 0.5×ATR half-width reuse). M8 also emits only the latest zone per (kind, direction) rather than all unmitigated zones, and no dedicated `base_model` contract test exists (e.g. `POIState.CREATED` never asserted).

---

## 7. Conclusion

**Phases 0–2 are faithfully implemented against LOCKED_DECISIONS.md (Rev 5), the R1 specifications, and the Phase 2 coding prompt.**

1. **No invented thresholds** — verified by full-value comparison of `locked_constants.py` (36 constants) against LOCKED_DECISIONS, plus a literal-scan of all 28 source modules. Unfrozen choices (0.5×ATR band half-width, M5 cluster zone, displacement measurement definition) are labeled UNFROZEN V1 and kept out of the frozen module.
2. **All R1 §5 geometries match** — 8/8 models, each backed by an acceptance fixture whose asserted zone bounds were hand-re-derived.
3. **All 133 tests pass** — executed and independently recounted (36 + 56 + 41).
4. **TODO/CHANGELOG reflect reality** — every checked item maps to a real file with the described behavior; the six findings above are process/documentation gaps (one medium: §4 TF enforcement in Phase 2), none affecting detection correctness.

Recommended before starting Phase 3: resolve F2-1 (§4 timeframe enforcement) and record F2-3's M8 lookahead choice in the ambiguities log.
