# FR-4b UNFILLED-ORDER FORENSIC — WHY THE 5 RESTING LIMITS NEVER FILLED

**Date:** 2026-09-22 · **Authority:** Lead Architect forensic brief (facts only — no expiry, gate, timing, or threshold change; fill model untouched).
**Method:** the FR-4b window was re-run under the **identical frozen config** with a logging-only recording order book (same instrumentation seam as the FR-4 diag/fate scripts). The forensic run **reproduced run1 byte-exactly** (`trades.csv` + `report.json` sha256 match), so the recorded events are the run1 events. Touch analysis mirrors `fill_model.limit_filled` exactly (inclusive limit-touch) over the fill-eligible window implied by the locked runner operation order.

---

## 1. The exact live window (derived, stated once)

The runner places orders at step 6 (**after** step-5 fills) and expires at step 3 (**before** step-5 fills). With §23 M5 = 12 bars (`bars_open >= 12`, placement bar counts), an order placed on bar N is **fill-eligible on bars N+1 … N+10**; on N+11 it is removed pre-fill. All 5 orders ended `expired/section23` at exactly N+11 — runner behavior and this reconstruction agree 5/5 (zero `touched_while_live` anomalies ⇒ no contradiction between touch analysis and the fill model).

## 2. Per-order forensic table (all 5 placed orders)

| tkt | dir | limit | POI (tags) | anchor | placed (bar / UTC) | min dist live | end | touch after expiry |
|---:|---|---:|---|---|---|---:|---|---|
| 1 | long | 3414.635 | poi-000067 (M1+M7+M8) | re-anchor | 38 · 09-01 03:10 | **54.70** | §23 @49 | no (window end) |
| 2 | long | 3327.446 | poi-000069 (M4) | re-anchor | 38 · 09-01 03:10 | **141.89** | §23 @49 | no (window end) |
| 3 | long | 3356.871 | poi-000671 (M1) | re-anchor | 441 · 09-02 16:15 | **162.80** | §23 @452 | no (window end) |
| 4 | long | 3995.775 | poi-011779 (M8) | re-anchor | 7765 · 10-09 05:35 | **35.62** | §23 @7776 | **yes — +121 bars (10-09 16:35)** |
| 5 | long | 4247.355 | poi-014750 (M8) | re-anchor | 9657 · 10-20 02:15 | **4.43** | §23 @9668 | **yes — +26 bars (10-20 05:20)** |

Every placed order in the window was a **re-anchored** entry (`entry_anchor = zone_edge_reanchor`, 5/5 — no `ob_proximal` placement occurred); all were LONG buy-limits sitting below the post-BOS market.

## 3. Pivots

**By fate class:** `never_touched_in_life` **3** · `touched_only_after_expiry` **2** · `touched_while_live_unfilled_ANOMALY` **0** · `data_gap` **0** · `filled` 0 (consistent with the run: 0 trades).

**By M8:** M8 = 3 orders → 1 never-touched / **2 touched-after-expiry**; non-M8 = 2 orders → 2 never-touched.

**Distance & timing:** median closest approach while live **54.70** price units (range 4.43 → 162.80); median bars from expiry to eventual touch (touched subset) **73.5** (26 and 121).

## 4. The clear answer (instructed question)

**Mixed by population, structured by mechanism — no anomaly.**

- **(a) Never returned — 3 orders (1 M8 + 2 non-M8, all September):** price ran away from the re-anchored at-zone limits after the BOS impulse and never came within 54–163 units for the rest of the 3-month window. These zones were left behind by trend, not postponed.
- **(b) Returned after expiry — 2 orders (both M8, both October):** price retraced to the zone edge **after** the 12-bar §23 window — +26 bars (~2 hours) and +121 bars (~10 hours). **Ticket 5 is the decisive near-miss: closest approach 4.43 units (≈0.10% of price) during its 10 eligible bars, first touch 26 bars after expiry.** The fill regime came within a whisker and the lifetime, not the geometry, cut it off.
- **(c) Touched-but-unfilled anomaly: none** — the fill model and the recorded order lifecycle are mutually consistent on every order.

Facts for the pending D1/D2/D3 ruling (unlabeled notes only, per brief): both touched-after-expiry orders are the same zones the FR-4 fate report identified (zone highs 3995.775 / 4247.355); the near-miss margins are 4.43 and 35.62 units against a 12-bar lifetime with touches at +26 and +121 bars; the never-touched population is dominated by September trend-runaway, where a longer lifetime alone would not have produced fills.

## 5. Artifacts

- Script: `06_RESEARCH/scripts/fr4b_unfilled_forensic.py` (recording book on the instrumentation seam; byte-identity cross-check vs run1 enforced in-output)
- Data: `06_RESEARCH/results/fr4b_wider/unfilled_forensic.csv` · `unfilled_forensic_summary.json` · forensic run under `results/fr4b_wider/forensic_run/` (kept separate from the determinism pair)
- Baseline evidence (unchanged): `06_RESEARCH/FR4B_WIDER_WINDOW_REPORT.md`, `results/fr4b_wider/run{1,2}/`

**No strategy code changed (`04_SRC/smc/` untouched). No edge claim. Diagnostic facts only — the D1/D2/D3 decision is the Lead Architect's.**
