# SMC-R1 — Module Architecture & Qualification Framework

**Date**: 2026-08-27
**Milestone**: SMC-R1 (supplementary document)

---

## 1. Three-Layer Module Architecture

### Layer 1: Signal Models (generate tradeable events)

These are the candidates for standalone strategies or specialist modules.

| ID | Model | Type | Naturally Standalone? | Specialist Role | Trigger Selection |
|:---:|-------|------|:---:|-----------------|:---:|
| A | CHOCH Reversal | Reversal | Possible | Reversal specialist | Chronological first-valid |
| B | Leading Diagonal | Trend initiation | Possible | Trend-start specialist | Chronological first-valid |
| C | Ending Diagonal | Exhaustion | Possible | Exhaustion specialist | Chronological first-valid |
| D | Two-Bar Reversal | Micro-trigger | Module only | Execution confirmation | Limit at 50% engulfing body |
| E | RSI Divergence | Micro-trigger | Module only | Momentum confirmation | Chronological first-valid |
| F | BOS+OB Continuation | Trend continuation | Possible | Trend-continuation specialist | Chronological first-valid |

> **Locked:** Trigger selection is chronological — first valid LTF trigger wins (per LOCKED_DECISIONS.md).

### Layer 2: Context / Routing Modules

These determine WHICH signal models are active in current market conditions.

| Module | Role | Standalone? | Economic Role |
|--------|------|:---:|---------------|
| Trend/Range State | Routes to trend vs reversal signals | No | Regime router |
| Dealing Range P/D | Filters POI quality by zone position | No | Quality filter |
| Volatility State | Adjusts expectations for move magnitude | No | Risk modifier |
| Session State | Timing filter for signal activation | No | Timing gate |
| POI Freshness | Activates/deactivates POIs | No | State manager |
| Inducement State | Validates POI quality | No | Quality filter |

### Layer 3: Execution Modules

These determine HOW to execute a validated signal.

| Module | Role | Standalone? |
|--------|------|:---:|
| M1/M5 CHOCH | LTF precision entry on CHOCH | No — needs POI |
| FVG/OB Mitigation | Entry zone refinement | No — needs POI |
| Fibonacci 50–61.8% | Retracement entry for Wave 2 | No — needs wave count |
| Wave-5 Terminal | Diagonal sweep entry | No — needs diagonal |

---

## 2. Module Qualification Requirements

### For Signal Models (A, B, C, F)

A signal model qualifies as M4 (Validated Economic Module) only if:

1. **Event extraction is deterministic** — the model can be identified from OHLCV data without discretionary judgment
2. **Standalone expectancy is positive** — the model generates positive expected value under OOS validation with realistic costs
3. **Evidence is sufficient** — enough independent events to distinguish signal from noise
4. **The model is frozen** — entry, stop, and event definition are fixed before testing

### For Context/Router Modules

A context module qualifies as M4 only if:

1. **The regime definition is independently validated** — the regime routing changes a defined economic outcome
2. **The routing rule is frozen** — which signals are active in which regimes is fixed ex ante
3. **The module has a defined economic role** — it is not merely a filter selected because it improves combined PnL

### For Execution Modules

An execution module qualifies as M4 only if:

1. **The execution logic is independently justified** — it improves the payoff of a validated signal
2. **The execution rules are frozen** — order type, placement, timing are fixed
3. **Costs are realistically modeled** — spread, slippage, and fill assumptions are documented

---

## 3. Anti-Combination-Mining Rule (Preserved)

**Forbidden:**

```
Test A + B + C + D + E + F
    → pick best PnL combination
```

**Permitted:**

```
Model A independently validated (M4)
    +
Model B independently validated (M4)
    +
Known economic interaction
    +
Interaction frozen ex ante
    +
Combined OOS test
    =
Potential EA component
```

---

## 4. Specialist Module Principle

A specialist module does NOT need to perform outside its validated environment.

```
Trend Specialist (F: BOS+OB)
    → active only in trending conditions
    → silent in ranges ✓

Reversal Specialist (A: CHOCH)
    → active only at POI with CHOCH confirmation
    → silent during trend continuation ✓
    → Modular tag M3
    → Entry at broken structural level (NOT origin OB)

Exhaustion Specialist (C: Ending Diagonal)
    → active only at trend-end POIs
    → silent during trend initiation ✓

Continuation Specialist (Model 5: Extreme Equal Highs)
    → active only when equal peaks (EQH/EQL) break and retrace
    → entry at broken equal level
    → Modular tag M5

HTF Zone Specialist (Model 8: HTF Demand/Supply)
    → active only when D1/H4 zones are identified and price enters zone
    → M5 approach monitoring → M1 execution trigger (Ending Diagonal preferred)
    → Modular tag M8 (zone-based, full peer)
    → SL: 2–5 pips (M1-based) | RR: 1:5+
```

**Required:** The regime routing rule itself must be independently validated (M4).

---

## 5. Rare-Event Compatibility

SMC events may be sparse. The research must distinguish:

- **Event frequency** — how often does this setup occur?
- **Independent evidence** — how many independent observations exist?
- **Expectancy precision** — how wide is the confidence interval?
- **Calendar exposure** — how long is the forward observation period?
- **Stability** — is the effect consistent across chronological subperiods?

A model with 50 events/year can qualify if the expectancy is genuinely positive and the evidence is sufficient.

---

## 6. Future Validation Path

```
SMC-R1: Formalization ← CURRENT
    ↓
SMC-R2: Event extraction (deterministic from historical OHLCV)
    ↓
SMC-R3: Standalone expectancy tests (per-model)
    ↓
SMC-R4: Module qualification (M0→M1→M2→M3→M4)
    ↓
SMC-R5: Interaction hypotheses (if multiple M4 modules)
    ↓
SMC-R6: Combined OOS validation
    ↓
SMC-R7: Execution/demo validation
    ↓
EA
```

No step may be skipped.
