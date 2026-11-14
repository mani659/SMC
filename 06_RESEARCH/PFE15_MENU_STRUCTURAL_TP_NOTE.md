# PFE-1.5 — STRUCTURAL TP ON THE MENU ENTRY PATH (P0-2 CLOSED)

**Date:** 2026-11-14 · **Program:** PFE step 1.5 · **`LOGIC_CHANGED: NO`**
(no gate, threshold, C3, §5a, ZoneDedup, SL or risk change)
**Closes:** `06_RESEARCH/PFE1_PRODUCT_VS_INTENDED_AUDIT.md` **P0-2**
(audit row N: menu winners never received a structural target).

---

## 1. Defect as found

The menu bridge built its candidate like this (`product_menu_mtf.py`, `_candidate`):

```python
base = candidate_from_route(
    route, pillar_path=PRODUCT_MENU_PILLAR_PATH, atr=atr,
    completion_price=completion_close,
)
```

`candidate_from_route` computes the TP with `resolve_take_profit(...)`, whose
structural branch only exists when a `structural_target` is supplied. The seek
adapter supplies one (`pipeline_adapter.py`, `structural_target=structural_tp_target(...)`);
the menu did not. Result: **every menu confirmation took the 4×ATR fallback**,
so §21b's "TP = first valid swing, else 4×ATR" was false on the entry law live
`PRODUCT_V1` actually runs.

## 2. Change (wiring only)

In `_candidate`, before the bridge call:

```python
structural_target = structural_tp_target(
    self._swings_for(tf),                # §19 swings of the confirmation series
    route.signal.entry_price,
    route.signal.direction,
    atr,
    placement_bar=index,                 # the completion bar
    max_age_bars=poi_give_up_bars(),     # documented CPU/age bound (existing)
)
base = candidate_from_route(
    route, pillar_path=PRODUCT_MENU_PILLAR_PATH, atr=atr,
    structural_target=structural_target,
    completion_price=completion_close,
)
```

Properties preserved deliberately:

- **One selector.** The helper is the same `smc.backtest.pipeline_bridge.structural_tp_target`
  the seek adapter imports — no second swing rule, no new TP formula.
- **Same fallback.** `resolve_take_profit` is untouched; no qualifying swing →
  `structural_target=None` → the frozen 4×ATR branch, byte-identical.
- **Lookahead ban.** `placement_bar` is the completion bar's index in the
  confirmation series, so only swings §19-confirmed *strictly before* it can be
  used (`confirmed_index < placement_bar`).
- **Selector inputs already existed.** `_swings_for(tf)` is the menu's own cached
  §19 swing detection (already used by its triggers); `atr` is the same
  `latest_atr` the bridge already received; `poi_give_up_bars()` is the existing
  age bound the seek path passes.
- **Provenance.** `candidate_from_route` already stamps `tp_source`
  (`structural_swing` when the supplied target was used verbatim, otherwise
  `atr_fallback`), so the menu path is now auditable with the same vocabulary as
  seek — no new field.

## 3. Tests

`04_SRC/tests/test_pfe15_menu_structural_tp.py` (3 tests, all green):

1. menu winner with a valid swing ≥ `STRUCTURAL_TP_MIN_ATR × ATR` beyond entry →
   `tp_source == "structural_swing"`, `tp_price` equals that swing;
2. no qualifying swing → `tp_source == "atr_fallback"` and the TP equals
   `entry ± FR2_TP_ATR_MULTIPLE × latest_atr` (fallback unchanged);
3. the bridge still calls the shared selector and the existing age bound (pins
   "no second swing rule").

Existing menu suite (`tests/test_product_menu_mtf.py`, 15 tests) unchanged and green.

## 4. Observed effect on real data (smoke, not a measurement)

Short probe, `06_RESEARCH/results/pfe15_smoke/menu10/` (exec 2025-10-01 → 10-10):
23 menu winners, 14 placed, 14 fills, `tp_source` **7 structural / 7 atr_fallback**.
Before this change the split on that path was structurally 0 / all fallback.
**This is a wiring observation, not performance evidence** — no PnL is claimed,
and the 6-month product run belongs to PFE-2.

## 5. Non-changes (explicit)

`resolve_take_profit`, `STRUCTURAL_TP_MIN_ATR`, the §19 swing definitions, the
§21b fallback multiple, every `locked_constants` value, C3, §5a seek, ZoneDedup,
the SL path and the risk gates are untouched. `git diff -- 04_SRC/smc/config/locked_constants.py`
is empty.
