# C2A — CHOCH RULE 3 LIVE-OFF (TRIGGER A)

**Date:** 2026-11-12 · **Status:** PASS · **Scope:** C2a only
**Authority:** `00_LOCKED/EXPERT_MASTER_CARD.md` (A = R1/R2 live; R3 research only),
amendment list row A1, gap plan row G07.
**`LOGIC_CHANGED: YES`** — Trigger A live eligibility only; no threshold, no geometry change.

---

## 1. What changed

| Path | Change |
|---|---|
| `04_SRC/smc/poi/choch_classifier.py` | Added `LIVE_CHOCH_RULES = (RULE_1_STANDARD, RULE_2_INSIDE_BODY)` and `is_live_choch(break_)`. Classification itself is untouched: Rule 3 is still returned for research. |
| `04_SRC/smc/triggers/trigger_a_choch.py` | After classification, `is_live_choch(choch)` gates the signal — a wick-only break returns `None`. Docstring records why. |
| `04_SRC/smc/poi/models/m3_choch_retest.py` | Same gate before emitting an M3 POI: a wick-only CHOCH no longer creates a tradeable retest zone. |
| `04_SRC/smc/poi/__init__.py` | Exports `LIVE_CHOCH_RULES` / `is_live_choch`. |

No Rule 1 / Rule 2 geometry, entry, SL or expiry behaviour changed. No numeric constant touched.

---

## 2. Rule mapping (enum → live)

| Enum | Name | Live entry |
|---|---|---|
| `ChochRule.RULE_1_STANDARD` | standard / external body close | **YES** |
| `ChochRule.RULE_2_INSIDE_BODY` | inside / intermediate body close | **YES** |
| `ChochRule.RULE_3_INSIDE_WICK` | wick-only pierce, no body close | **NO — research only** |

The classifier still emits all three; only live consumers gate.

---

## 3. Call sites audited

| Call site | Consumes `ChochBreak`? | Action |
|---|---|---|
| `smc/triggers/trigger_a_choch.py` | Yes — builds `TriggerSignal` | **Filtered** (`is_live_choch`) |
| `smc/poi/models/m3_choch_retest.py` | Yes — builds a tradeable POI | **Filtered** (same helper) |
| `smc/triggers/trigger_router.py` | No direct CHOCH rule knowledge; evaluates Trigger A | Inherits automatically |
| `smc/backtest/pipeline_adapter.py`, `smc/orchestration/product_menu_mtf.py`, `smc/orchestration/multi_tf_runtime.py` | No direct `ChochBreak` use (verified by grep) | Inherit via Trigger A |
| `smc/orchestration/coupled_mtf.py`, `smc/essence/**` | No `ChochRule` reference | Not a live CHOCH entry path |
| `smc/poi/choch_classifier.py` | Producer | Unchanged (research visibility) |

Grep evidence: the only non-classifier consumers of `classify_choch_at` / `ChochRule`
in `04_SRC/smc` are M3 and Trigger A.

---

## 4. Tests

New file `04_SRC/tests/test_c2a_choch_r3_live_off.py` (8 tests):

- helper contract: live set is exactly R1+R2; `is_live_choch` mapping (including `None`)
- **T1** Rule 1 break → Trigger A still signals
- **T2** Rule 2 break → Trigger A still signals (entry at the intermediate level)
- **T3** Rule 3 only → Trigger A returns `None`
- **T4** classifier still reports `RULE_3_INSIDE_WICK` (research path intact)
- **T5** Rule 3 produces no M3 POI; Rule 1 still produces one

Existing tests needed no weakening: `test_choch_classifier.py` already pinned Rule 3
classification, and `test_poi_models.py` already used Rule-1 geometry.

**Suite:** 1485 passed / 7 skipped (was 1477 + 8 new).

---

## 5. Explicitly not done

- No in-between containment gate (C3).
- No color-free Demand/Supply (C2b).
- No LOCKED / ESSENCE body rewrite (D0 remains separate).
- No TP/SL, risk, fill-regime, menu or boundary-sweep change.
- No constant edits (`locked_constants.py` diff empty).

---

## 6. Return block

```text
C2A_STATUS: PASS
R3_LIVE: NO
R1_R2_LIVE: YES
TRIGGER_A_PATHS: smc/triggers/trigger_a_choch.py, smc/poi/models/m3_choch_retest.py
TESTS_ADDED_OR_UPDATED: 8
SUITE: 1485/0
NOTE_PATH: 06_RESEARCH/C2A_CHOCH_R3_LIVE_OFF_NOTE.md
LOGIC_CHANGED: YES
LOCKED_CONSTANTS_DIFF: empty
HANDOFF_UPDATED: YES
NEXT_READY: C3 shared in-between containment gate
```
