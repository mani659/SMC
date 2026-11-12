# POST-C2 DIAGNOSTIC — D0 DOCS LAG + FROZEN-WINDOW MEASUREMENT

**Date:** 2026-11-12 · **Engagement:** D0 (docs, Part A) + diagnostic measurement (Part B)
**`LOGIC_CHANGED: NO`** — docs only; no `04_SRC/**` change, no constant, no threshold, no strategy edit.
**Status:** D0 PASS · MEASURE PASS (dual run, byte-identical product outputs)

> **This is a DIAGNOSTIC, not performance.** n = 11 trades. No edge claim, no
> go-live gate, no tuning was performed and none should be inferred from these
> numbers.

---

## PART A — D0 documentation lag (crate: LOGIC_CHANGED: NO)

| Doc | Change |
|---|---|
| `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` | §1 now states the shipped product detection set `(D1, H4, H1, M15)` (the menu tiers `multi_tf_runtime.py` accepts), that **M5 is execution** and **M1 is trigger/confirmation (LTF) context** — neither is a structural POI inventory TF — and adds the expert-story authority pointer (`EXPERT_MASTER_CARD.md` + `EXPERT_AMENDMENT_LIST_2026-11-12.md`) plus an explicit **boundary-sweep product emitter: NOT implemented**. |
| `00_LOCKED/ESSENCE_CONTRACT_V1.md` | Header **supersession notice only**: TP/SL/entry-catalog rows conflicting with the master card are superseded for product intent (amendment rows A3/A4/A7/A10); benchmark targets (1:5 TP, 2–5 pip SL) remain **review-only**. §5/§6 body untouched. |
| `SESSION_HANDOFF.md` / `POST_V1_ACTIVE_TODO.md` / `CHANGELOG.md` | D0 + measurement entries (docs-only). |

Verification: `git diff -- 04_SRC` empty, `locked_constants.py` diff empty,
contract contains M15, ESSENCE notice present. Full suite re-run:
**1500 passed / 7 skipped** (unchanged by D0).

---

## PART B — Measurement composition

Imported, not forked: `06_RESEARCH/scripts/post_c2_diagnostic.py` →
`frozen_funnel_6m_new_contract.run_frozen` → `phase3_structure_funnel.run`:

```
MultiTFProductRuntime.run_batch (H4+H1+D1 + injected M15)
  → PipelineEngine.arm_at (pillar/validation, §5 posture)
  → PipelineAdapter.generate_candidates (trigger scan; C2a Rule-3 filter)
  → candidate_from_route (C3 in-between gate)
  → BacktestRunner (risk → pending limits → fills → manage)
```

**Harness finding (recorded, not fixed here):** the frozen 6-month harness
supplies only H1/H4/D1, while the shipped product default also requires
**M15**. Running it unchanged produced `htf_batches=0, batch_errors=2979` —
i.e. the harness has been measuring an empty funnel since the M15 default
landed. The diagnostic probe therefore derives M15 by resampling the
harness's own M5 execution candles (closed bars up to `as_of`) and injects
it into `run_batch`; `04_SRC` is untouched. One batch still failed loudly
(`batch_errors=1`, cold-start prefix).

---

## Window (frozen)

| Item | Value |
|---|---|
| Load prefix | 2025-05-01 (same deep HTF warm-up as the 6-month family) |
| **Exec window** | **2025-10-01 → 2025-10-31 UTC** |
| Exec TF | M5 (6,324 bars) |

**Why not 6 months:** the 6-month window was attempted first and measured at
~15 bars/s by mid-window after ~50 minutes (>1 h/run including the dual run).
The October month is the directive's documented fallback window; the window
was fixed before any result was read and was not widened afterwards.

---

## Funnel (run1; run2 identical)

| Stage | Count |
|---|---|
| M5 bars processed | 6,324 |
| HTF batches | 526 (1 loud error, cold start) |
| Raw detections | M15 9,148 · H1 9,551 · D1 8,303 · H4 8,021 |
| Merged POIs | 18,677 |
| Pillar/validation pass | 1,027 |
| **Armed** | **441** (D1 205 · M15 93 · H4 78 · H1 65) |
| Armed M8 | 242 |
| Duplicates suppressed | 586 |
| POIs scanned | 8,991 |
| **Routes** | **149** — F 122 · A 15 · B 11 · C 1 (M8 POIs 87) |
| **Candidates** | **12** — F 11 · B 1 |
| **Placed** | **11** (11 with TP) |
| **Fills** | **11** — F 10 · B 1 |

### C3 in-between gate

| Probe | Value |
|---|---|
| Gate checks | 149 |
| **`not_in_between` rejects** | **137** |
| Candidates produced | 12 |

Every gate check failed closed on out-of-zone completions in this window —
the completion close sat outside the routed POI body for 92% of routes.

### C2a — CHOCH

| Probe | run1 / run2 |
|---|---|
| Rule 1 classifications | 21 / 20 |
| Rule 2 classifications | 4 / 4 |
| **Rule 3 classifications** | **10 / 9** |
| Trigger A routes | 15 |
| Trigger A candidates | 0 (all rejected by C3) |
| **`R3_LIVE_ROUTES`** | **0** |

The classifier keeps emitting Rule 3 for research (10 in October), and none
of those breaks produced a candidate entry. No candidate carries a
`signal.data["rule"]` token because no Trigger A route survived C3 in this
window.

### C2b — M8 mix on armed POIs

| Kind | Armed |
|---|---|
| non-M8 | 199 |
| ob | 66 |
| demand_supply + ob | 51 |
| demand_supply | 42 |
| fvg | 29 |
| demand_supply + fvg | 28 |
| fvg + ob | 15 |
| demand_supply + fvg + ob | 11 |

### TP source (candidates)

| Source | Count |
|---|---|
| structural_swing | 9 |
| atr_fallback | 3 |

### Outcome (DIAGNOSTIC — NOT performance)

| Item | Value |
|---|---|
| Exits | take_profit 3 · stop_loss 8 |
| Net PnL | **−2.8703** (n = 11) — **NOT performance** |

---

## Determinism

| Check | Result |
|---|---|
| `trades.csv` | byte-identical (sha256 `8039473d…bdeb874b`) |
| `report.json` | byte-identical (sha256 `dba1c668…159cc9f26`) |
| Funnel summary semantic diffs | none |
| Probe counters (product-path) | equal |
| `choch_classified` | 21/4/10 vs 20/4/9 — **informational**, one extra one-off classifier call during the first run's warm-up in a shared interpreter; product outputs are byte-identical |
| **Verdict** | **PASS** |

---

## Comparison with a pre-C2 funnel

**DATA_GAP.** The prior funnel artifacts (`06_RESEARCH/results/**`) are
gitignored and were not retained, and the anchors embedded in the harness
(3-month / phase-4 families) use different windows. No same-window pre-C2
run exists, so no delta is reported — none is fabricated.

---

## What was NOT done

- No threshold, constant, strategy or `04_SRC` edit (`git diff 04_SRC` empty).
- No re-run with tuned parameters; window fixed before reading results.
- No boundary-sweep emitter, no C2b refactor, no ftmo/risk policy change.
- No edge/PF/expectancy claim; PnL is labelled diagnostic throughout.

---

## Return block

```text
D0_STATUS: PASS
MEASURE_STATUS: PASS
CONTRACT_M15: YES
ESSENCE_NOTICE: YES
WINDOW: exec 2025-10-01 → 2025-10-31 UTC (load 2025-05-01)
ARMED: 441
ROUTES: 149
FILLS: 11
NOT_IN_BETWEEN_REJECTS: 137
R3_LIVE_ROUTES: 0
TRIGGER_MIX: {"routes": {"F": 122, "A": 15, "B": 11, "C": 1}, "fills": {"F": 10, "B": 1}}
DETERMINISM: PASS
NET_PL_DIAGNOSTIC: -2.8703 (NOT performance, n=11)
SUITE: 1500/0
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
REPORT_PATH: 06_RESEARCH/POST_C2_DIAGNOSTIC_REPORT.md
HANDOFF_UPDATED: YES
NEXT_READY: Architect review diagnostic | boundary-sweep design | formal LOCKED § edits
```
