# C2b — COLOR-FREE DEMAND / SUPPLY IDENTIFICATION

**Date:** 2026-11-12 · **Status:** PASS · **Scope:** C2b only
**Authority:** master card (OB / Demand-Supply = color-free; width = single origin
candle, full OHLC + wicks), amendment row A2, gap plan G08/G09.
Prerequisites C2a and C3 remain PASS and untouched.
**`LOGIC_CHANGED: YES`** — Demand/Supply identification only.

---

## 1. Pre-rule vs post-rule (exact)

**Pre-C2b (color as the selection predicate)** — `M8HtfDemandSupply._zones`:

```
if candle.is_bearish:            # LONG demand required a BEARISH candle
    rise = max(high[i+1 .. i+N]) - candle.low
    if rise >= DISPLACEMENT_MIN_ATR * ATR:  -> LONG zone (candle high/low)
elif candle.is_bullish:          # SHORT supply required a BULLISH candle
    fall = candle.high - min(low[i+1 .. i+N])
    if fall >= DISPLACEMENT_MIN_ATR * ATR:  -> SHORT zone (candle high/low)
```

A doji emitted nothing; a bullish candle could never anchor demand and a
bearish candle could never anchor supply, regardless of the impulse.

**Post-C2b (color-free)**

```
threshold = DISPLACEMENT_MIN_ATR * ATR                 (frozen, unchanged)
rise = max(high[i+1 .. i+N]) - candle.low             (unmodified measure)
fall = candle.high - min(low[i+1 .. i+N])             (unmodified measure)
rose, fell = rise >= threshold, fall >= threshold
if neither: no zone                                   (fail closed)
direction = LONG if rose and rise >= fall else SHORT  (larger leg wins; LONG on tie)
if the candle's own close-to-close move already runs WITH that leg by
   >= threshold: skip it                              (origin must pre-date the move)
zone = that candle's full high-low (wicks), direction as above
```

No candle color is read anywhere in the Demand/Supply path.

---

## 2. Origin-selection definition (one line)

> The origin is the candle at INDEX `i` whose following `N_BAR_LTF` window
> clears `DISPLACEMENT_MIN_ATR × ATR`, provided the candle's own
> close-to-close move has not already run with that impulse.

Direction comes from which leg moved (larger leg wins on a both-legs bar,
LONG on an exact tie so the result is deterministic and one origin still
yields at most one zone — exactly the cardinality color enforced).

---

## 3. Files / symbols changed

| Path | Change |
|---|---|
| `04_SRC/smc/poi/models/m8_htf_demand_supply.py` | `M8HtfDemandSupply._zones`: removed `candle.is_bearish` / `candle.is_bullish` branching; direction now from the measured impulse legs; added the origin-pre-dates-displacement guard. Module docstring updated. |

Nothing else changed: `zone_for_candle` (full wick range), `collapse_episodes`,
`_scan_timeframe`, `_flag_overlaps`, width and impulse thresholds are untouched.
The OB-from-FVG path (`ob_index = fvg.start_index - 1` → `zone_for_candle`) was
already color-free and is bit-stable.

---

## 4. Call sites audited (grep `is_bullish` / `is_bearish`)

| Site | Verdict |
|---|---|
| `smc/poi/models/m8_htf_demand_supply.py:156,161` | The only D/S color predicate — **removed**. |
| `smc/core/candle.py` (`is_bullish` / `is_bearish` properties) | Definition only. |
| `smc/detection/base_candle.py:63` | §18 bearish *Base Candle* swing rule (a swing-extreme detector), not a D/S zone selection. **Intentionally untouched** — changing it is a swing-model change outside C2b. |
| All other models (M1–M7) | No color-gated zone emitters. |

No other module selects a Demand/Supply or OB zone by candle color.

---

## 5. Measurement (read-only, synthetic — not a gate)

Raw Demand/Supply origins yielded per scan, old color rule vs new color-free
rule, same series and same frozen thresholds (script counted origins before
`collapse_episodes`, not POIs):

| Fixture | Old (color) | New (color-free) |
|---|---|---|
| M8 acceptance fixture (24 H4 bars, one dump) | 5 | 7 |
| Monotone drift + 3-bar dump legs (52 H4 bars) | 3 | 27 |

The drift case shows the expected expansion: every bar of a slow up-run now
qualifies as a demand origin (the old rule could never fire without a bearish
candle). Emitted POI volume stays bounded regardless — `_scan_timeframe`
keeps the most recent zone per `(direction, kind)`, so at most two
Demand/Supply POIs exist per scanned timeframe. No threshold, width or
ranking was added to suppress this.

---

## 6. Tests

New `04_SRC/tests/test_c2b_color_free_ds.py` (7):

- **T1** bullish-bodied origin still yields a LONG demand zone, width = full
  origin high–low.
- **T2** bearish-bodied origin still yields a SHORT supply zone (mirror).
- **T3** inverting the origin body (same high/low, same spine) produces the
  SAME bounds — proves color is not the predicate.
- **T4** fail closed: no origin index exists → no zone; a candle that is
  already the displacement cannot claim the zone.
- **T5** OB-from-FVG path still emits the pre-FVG candle's full range
  (color-free regression).
- **T6** smoke: C3 rejects an out-of-zone close; C2a Rule 3 still not live.

Existing `test_poi_models.py::test_m8_htf_zones_acceptance_single_timeframe`
and `test_m8_zone_width.py` keep their pinned zones (idx19 supply =
201.2/200.6) and pass unmodified — their assertions are geometric, not
color-based.

**Suite:** 1500 passed / 7 skipped (1493 + 7). No skips added.

---

## 7. What was NOT changed

- Width: still the single origin candle's full high–low — no cap, no ATR
  width filter, no multi-candle envelope.
- Impulse thresholds (`DISPLACEMENT_MIN_ATR`, `N_BAR_LTF`), FVG/OB detection,
  episode collapse and overlap flagging.
- C3 completion definition, C2a Rule-3 policy, TP/SL/risk/R7/R9/menu.
- `locked_constants.py` — diff empty.
- No boundary-sweep emitter, no LOCKED/ESSENCE body rewrite, no expectancy
  claim, no drive-by refactor.

---

## 8. Return block

```text
C2B_STATUS: PASS
COLOR_FREE_DS: YES
ORIGIN_RULE: origin = candle index i whose next N_BAR_LTF window clears 1xATR in one direction, and whose own close-to-close move has not already run with that impulse
MODULES_CHANGED: 04_SRC/smc/poi/models/m8_htf_demand_supply.py
OB_PATH_PRESERVED: YES
TESTS_ADDED_OR_UPDATED: 7
SUITE: 1500/0
NOTE_PATH: 06_RESEARCH/C2B_COLOR_FREE_DS_NOTE.md
LOGIC_CHANGED: YES
LOCKED_CONSTANTS_DIFF: empty
HANDOFF_UPDATED: YES
NEXT_READY: D0 docs | measurement pack | Architect pick
```
