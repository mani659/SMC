# STAGE 3 TRIGGER VISIBILITY + CONVERSION AUDIT

**Status: PASS** · suite **772 passed** (762 + 10 new) · `locked_constants.py` diff empty · double-run ledger + summary byte-identical.
**Scope:** identification / visibility only. No locked constant, pillar, trigger definition, risk, TP/SL or lot logic changed; no trigger count tuning; existing trigger implementations reused in evaluation / scan mode only (`LOGIC_CHANGED: NO`).

---

## 1. What was measured

| Item | Value |
|---|---|
| Window | exec 2025-06-01 00:00 → 2025-11-30 23:59 UTC (warm-up 2025-03-01, M1 parquet) |
| HTF source | accepted post-F1F2 packs: `events_h4_poi.csv` raw **658** + D1 subset **10** = **668 structures** |
| Scan horizon | `[structure close, close + poi_give_up_bars() = 20 M5 bars]` — existing constant, identical rule for every structure (same horizon as the accepted LTF pack; **not** tuned) |
| Pass 1 — product route | instrumented copy of the accepted §5-mirrored arm/feed/`scan_route` replay → `route_would_form` per completion (pre-pillar; verified to reproduce the LTF pack's same 2 routes) |
| Pass 2 — visibility inventory | one `SeriesState(M5)` per bar; **every matrix-eligible trigger evaluated directly** in every window; **every completion recorded**, ungated by §5 state so formed geometry is never hidden behind first-trigger-wins routing |
| Detector context / negatives | sourced from the accepted LTF pack ledger (15,350 non-trigger link rows, same window/linking rule) — no stage-0 re-run |
| trigger_tf | **M5 only.** Trigger code never reads a timeframe and the product wires triggers to the M5 execution path only; an M1 scan would duplicate TF-agnostic code on a hypothetical path (double-counting). `counts_by_tf = {M5: 263, M1: 0}` with reason in `summary.json` |

## 2. Trigger counts by type

**Total completed Stage 3 triggers: 263** (all linked to an accepted HTF structure: `triggers_with_htf_link = 263`, `triggers_without_htf_link = 0` — **by construction**: the scan universe is the accepted H4/D1 packs; an unlinked completion outside every structure's window cannot be found without inventing POI geometry, which is banned — disclosed, not hidden).

| Type | Trigger | Count | Note |
|---|---|---|---|
| **A** | CHOCH Reversal | **31** | fires freely (direction + swings only) |
| **B** | Leading Diagonal | **17** | needs full 6-point impulse chain + Fib band test |
| **C** | Ending Diagonal | **4** | zone-band gate (terminal within 0.5×ATR of zone) |
| **D** | Two-Bar Reversal | **0** | **structurally unable to fire**: frozen rule `engulfer.volume < engulfed.volume` vs the canonical parquet's all-zero volume column (0 of 1,768,123 nonzero) — documented A5 ruling; honest zero, not a scan failure |
| **E** | RSI Divergence | **7** | double pattern + zone band + RSI divergence |
| **F** | BOS + OB Continuation | **204** | dominant: entry is zone-anchored, so the FR-3 in-zone gate passes almost by construction once BOS + first OB touch exist |

- **232 of 668 structures** produced ≥1 completion; completions-per-structure ≤4 (only 2 structures exceed 3).
- Product routes (`route_would_form = yes`): **2**, both F — `evt-ec41701aca47` (2025-07-13 22:10) and `evt-499a786ac28b` (2025-10-26 22:10) — **the same 2 routes the accepted LTF pack found** (cross-pack consistency, 0 discrepancies between the two passes).

## 3. Conversion observation (activity → Stage 3)

Funnel on the frozen window:

```
15,350 zone-linked detector rows (sweep / displacement+BOS / FVG, M15+M5)
        │  → 263 completed Stage 3 trigger geometries ........ 1.71 %
        │       → 2 product-routable completions ............. 0.08 % of detector links
```

- **623 of 668** structures carried ≥1 zone-interacting detector link (retest|inside); **215 of those (34.5 %)** produced ≥1 completed Stage 3 trigger. Detector activity near a zone is the *ingredient* surface; the locked pattern + zone/direction gates convert roughly one in three active structures into ≥1 completed trigger, and roughly **1 in 58 detector links**.
- **Stage 3 formed → Stage 3 routed (the real bottleneck): 263 → 2.** Instrumented §5 replay shows every completion classified with zero anomalies (`scanned_not_routed = 0`, `suppressed_other = 0`):
  - **261 completed AFTER the armed-POI scan had already closed** — **199** by the zone first-touch rule (`TESTED` → scan only at touch bar and the next), **62** by zone violation (`VIOLATED` kills the scan);
  - **2 completed while the scan was open → both became routes (100 % conversion inside the open scan).**
- Interpretation (observation, not recommendation): the Stage 3 geometry **does form** — 263 times — but the product's armed-POI lifecycle (FRESH → first touch +1 → seek ends, give-up 20 bars) closes **before** the trigger completes in 99.2 % of cases. The flowchart's Stage 3 box fires against an *armed* POI; the arming/seek lifecycle is the conversion gate, not the absence of trigger geometry.

## 4. Visual findings (can a human see the surgical entry?)

**36 panels** rendered (`06_RESEARCH/results/stage3_trigger_visibility/charts/`), budget = 40 cap:

- **30 trigger panels** (`chart_plan = {trigger_panels: 30, context_panels: 0, negative_panels: 6}` — over the ≤30 rule, so a deterministic sample: earliest row of every present type seeded, then even-in-time spread → **all 5 present types visible (A, B, C, E, F), June → November**).
- Each trigger panel shows, beyond generic displacement lines:
  - **completion bar** (solid red vline), **entry** (dashed) and **stop ref** (dotted) from the signal;
  - **trigger-specific geometry from `signal.data`**: F → BOS + OB-candle markers, E → peak 1 / peak 2 markers, C → diagonal-terminal marker + boundary line, B → Wave 5 + wave-1-origin + Fib band, A → sweep/broken-level;
  - HTF zone band + structure-close marker, nearest detector links as dashed context lines, plain title (`TRIGGER F — BOS + OB CONTINUATION | M5 | 2025-10-09 14:00 | LONG` style), correct `detection_tf / chart_tf` subtitle, footer **"Stage 3 trigger visibility — NOT a trade claim"**.
- **6 negative-example panels** (`NO STAGE 3 TRIGGER — detector activity only`): highest-detector-activity structures with zero completions (e.g. `evt-01bb30a6888f` with **113 detector links in window, 20 drawn, 0 trigger geometry**) — the contrast makes "ingredients" vs "surgical entry" immediately distinguishable.
- Human answer: **yes** — the trigger panel reads as an entry recipe (where the pattern completed, where entry/stop sit relative to the zone), while the negative panel shows the same ingredient vocabulary with no completion bar, no entry and no geometry markers.

## 5. Gaps vs flowchart Stage 3

1. **M1 leg not wired.** Flowchart Stage 3 = M1/M5; the machine runs triggers on M5 only (no code path evaluates them on M1). Honest zero in `counts_by_tf`.
2. **Trigger D unreachable on shipped data** (volume-less parquet + frozen volume rule, A5) — the flowchart's six-box stage can currently execute five.
3. **Funnel shape:** detector activity is abundant, Stage 3 completions exist (263), but the armed-POI 1-touch/violation lifecycle suppresses 261 of them (§3) — the visible flowchart arrow "armed POI → trigger" hides a near-closed gate in practice.
4. **Horizon coupling:** scan horizon = `poi_give_up_bars() = 20`, while `TRIGGER_B_EXPIRY = 30` — a wave-5 completing near the horizon end whose band test falls beyond bar +20 is unreachable *by product rules*; not measured here (outside the frozen horizon by definition), recorded as a structural note only.
5. **First-trigger-wins:** 263 formed geometries vs 2 routes also reflects LOCKED chronology (first valid LTF trigger wins, one trigger per event) — inventory > routes is by design, not double-counting.

## 6. Explicit non-claims

- No expectancy, PnL, win-rate, edge, timing or Monte Carlo claims. No threshold, filter or trigger-count tuning; the 263 count is a measurement of locked behavior at the frozen horizon, not an optimization target.
- `route_would_form` is a **pre-pillar** router signal (pillars / risk / execution not run); it is not a fill, not a trade.
- No production (`04_SRC/smc/**`) edit: `LOGIC_CHANGED: NO`. New files: research script + tests only.
- Chart sample is a review sample (≤30 of 263) — the **ledger lists every completion**; absence from charts is budget, not absence from measurement.
- `triggers_without_htf_link = 0` is a **scan-universe property** (accepted packs only), not proof that no unlinked trigger exists in the window.

---

**Artifacts:** `06_RESEARCH/results/stage3_trigger_visibility/` (`events_stage3_triggers.csv` 263 rows × 14 columns, `summary.json`, `charts/` 36 PNGs) · script `06_RESEARCH/scripts/stage3_trigger_visibility.py` · tests `04_SRC/tests/test_stage3_visibility_pack.py` (10) · companion pack `06_RESEARCH/results/ltf_confirmation/` (read-only input).
