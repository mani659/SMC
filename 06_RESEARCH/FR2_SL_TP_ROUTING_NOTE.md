# FR-2 STRUCTURAL SL/TP ROUTING NOTE (implementation)

**Status:** COMPLETE 2026-09-21 · R4/R5 implemented as ruled. No thresholds, displacement, pillars, lot caps, or Monte Carlo touched.
**Tests:** `tests/test_fr2_sl_tp_routing.py` (10 new) + 3 updated stale assertions (A×1, E×2). Suite **617 passed** (607 + 10), zero regressions, FR-1 tests intact.
**Verification:** unit + integration level (candidate TP values, fill-model TP hits with SL-first kept, paper TP passthrough by code inspection). No full-window re-run — post-FR-2 books are definitionally incomparable to the frozen Phase C book; full measurement belongs to FR-4.

---

## 1. Current behavior pre-FR-2 (survey)

- `tp_price=None` hardwired at exactly one site: `pipeline_bridge.candidate_from_route` (plus `original_sl=signal.stop_reference` beside it). No other TP assignment exists — confirmed by the INDEPENDENT_AUDIT grep finding.
- SL sites: F distal OB edge, A sweep extreme (Head), D engulfing extreme, E pattern peak extreme — all raw edges, zero buffer. B Wave-1 origin and C terminal level carry wave-geometry intent.
- `TriggerSignal` is frozen (entry/sl/completion/expiry/detail/data) — FR-2 adds nothing to it; TP/ATR ride bridge kwargs.
- No 0.3×ATR / 4.0×ATR values exist in `locked_constants.py` — both are new interim numbers (see §4).
- BE semantics unchanged: `modify_sl` rebuild preserves `original_sl` (tested); risk exit reads working SL only.

## 2. What changed (modules)

| File | Change |
|------|--------|
| `triggers/base_trigger.py` | `FR2_SL_BUFFER_ATR=0.3`, `FR2_TP_ATR_MULTIPLE=4.0` (interim, marked pending formal § lock) + `structural_sl()` (LONG below / SHORT above reference; None/non-positive ATR → reference) + `context_atr()` (hints-fold read with `latest_atr` fallback; None when unknowable) |
| `trigger_{f,a,d,e}_*.py` | Stops wrapped: F distal edge, A sweep extreme, D pattern extreme, E pattern extremes (real-space-first in the mirrored LONG branch) |
| `trigger_{b,c}_*.py` | UNTOUCHED — Wave-1 origin / terminal levels are wave-geometry stops with their own standoff intent; changing them is wave-model redesign (FR-3 territory). Documented exemption per R5's exception clause |
| `backtest/pipeline_bridge.py` | `resolve_take_profit()` (structural-if-valid else 4×ATR; None only when ATR unknowable) + `atr`/`structural_target` kwargs; no structural target exists in current signal/POI data so the live path is the fallback (documented, not hidden) |
| `backtest/pipeline_adapter.py` | Passes `atr=self.current_atr(bar_index)` (0.0 pre-warmup → TP None, deterministic) |
| Paper/live | No changes needed: `OrderRequest.tp=candidate.tp_price` already flows to MT5 (`None`→0.0, float→order); `_TrackedPosition.tp` exists |

## 3. Behavioral consequences (read before comparing books)

- F/A/D/E stops widen by 0.3×ATR where ATR resolves; short fixtures (ATR None) keep raw edges via the guarded fallback.
- Candidates now carry `tp_price = entry ± 4×ATR` (backtest fill model already hits TP with SL-first kept — no fill change).
- `original_sl` now equals the BUFFERED placement SL (post-buffer = placement, by construction).
- Any post-FR-2 backtest is NOT comparable to the Phase C frozen book. Full measurement is FR-4.

## 4. Interim constants needing formal §28 lock

- `FR2_SL_BUFFER_ATR = 0.3` (`smc/triggers/base_trigger.py`)
- `FR2_TP_ATR_MULTIPLE = 4.0` (`smc/triggers/base_trigger.py`, consumed by `pipeline_bridge.resolve_take_profit`)
- Both marked in-code "pending formal § lock"; both pinned by `test_interim_constants_have_expected_values` so a future lock diff is explicit.

## 5. Tests

- D1–D3: fallback both directions, valid structural use, wrong-side/non-finite/garbage fallback, ATR-absent None.
- D4: hand-value SL math + None/zero/negative/NaN guards.
- D5: F warmed-up fixture — entry unchanged, stop == buffered expectation, buffer strictly applied.
- D6: original_sl/BE contract (pre-existing preservation tests green, unchanged).
- D7: suite 617 green; updated A/E assertions now encode buffered expectations (F/D short fixtures keep raw edges via the None-ATR fallback — documented, not accidental).

---

*End of note. Next: FR-4 fidelity re-baseline on a fresh window (Lead Architect orders it); until then no book comparisons.*
