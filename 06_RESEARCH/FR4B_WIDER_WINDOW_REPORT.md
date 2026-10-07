# FR-4b — WIDER FIDELITY WINDOW (POST-FR-3.1, FROZEN CONFIG)

**Date:** 2026-09-22 · **Authority:** Lead Architect FR-4b instruction (FR-3.1 accepted; measurement only).
**Question:** with the FR-3.1 on-zone anchor live, does the chain **on-zone route → fill → SL/TP/BE close** ever complete under frozen rules on a longer window?

> **Diagnostic only. NOT edge, promotion, or capital advice.** No parameter search was performed regardless of trade count. No threshold, gate, timing, or locked-constant change of any kind. GATE_WIDENED: **NO** (gate byte-unchanged; the FR-3.1 anchor is accepted library state).

---

## 1. Configuration

| parameter | value |
|---|---|
| Window (documented default) | load 2025-08-01 (1-month M1 warm-up) · **execute 2025-09-01 → 2025-11-30 (3 months, 17,840 M5 bars)** |
| Stack | FR-1 multi-TF (H4+H1 detection, D1/H4 map into M8) · FR-2 TP/SL · FR-3 zone gate (unchanged) · **FR-3.1 on-zone anchor** · Trigger D absent (volume-less data, A5) |
| Frozen config | equity 10,000 · risk 0.01 · spread 0.0 (gates off — machine completeness, not cost realism) · news dormant · all sessions · Friday EOD on · M5 execution |
| Instrumentation | logging-only shims (scan counter, bridge counter, pass-through gate recorder) — production modules untouched; counters restored in `finally` |

## 2. Determinism pair

**PASS.** `trades.csv` and `report.json` **byte-identical** between run1/run2 (sha256 `ec885eef…` / `b0160ebf…`); `summary.json` identical ex-`tag`/`runtime_seconds`; full funnel including per-POI armed fates identical.

## 3. Funnel (run1 = run2)

| stage | H1 | H4 | total |
|---|---:|---:|---:|
| detected (raw) | 13,722 | 13,544 | 27,266 |
| pillar-passed | 439 | 270 | 709 |
| **armed unique** | 17 | 4 | **21 (15 M8)** |

| stage | count |
|---|---:|
| trigger scans (scan_route calls) | 274 |
| completed F signals | 6 |
| FR-3 gate **accepts / rejects** | **6 / 0** |
| routes created (all Trigger F) | **6** (4 on M8 POIs) |
| orders placed | **5** — all with **TP non-null (5/5)** |
| risk blocks (session) | 2 candidate events (retryable; POI one-shot survives per M4) |
| **fills** | **0** |
| trades closed | **0** |
| positions still open at window end | 0 (flat book) |

**Armed fates:** 18 TESTED · 3 FRESH at window end (never touched).

## 4. The chain answer (instructed question)

**On-zone routes form (6, gate accepts 6/6 — zero silent rejects remain), but the chain stops at the fill: 0 fills in 3 months, book flat, nothing to close.** With FR-3.1, the binding constraint moved downstream: the re-anchored limit sits at the POI zone's proximal edge while F's first-touch fires **after** the BOS push has carried price beyond it — a fill needs a retrace to the zone within the placed order's lifetime (§23: 12 M5 bars), which did not occur in this window. Exit mix is empty by definition (no trades); TP non-null rate on placed orders is **100% (5/5)** — the FR-2 profit leg is correctly live on every placement.

## 5. M8 chain (instructed metric)

**armed / routed / filled = 15 / 4 / 0.** M8 dominates arming (71% of armed POIs) and half of the routes; the fill blockage is identical (§23 window vs proximal-edge retrace), not M8-specific.

## 6. Reading (labeled, not advice)

- **Machine status: routing is unblocked and honest end-to-end** — signals, gate, placement, TP routing, determinism all proven on a 3-month window; no silent rejects anywhere in the funnel.
- **The remaining blocker is the fill regime**: F's first-touch timing (after the BOS leg) is structurally distant from the re-anchored at-zone limit under §24/§23 lifetimes. This is now the evidenced candidate for the Lead Architect's expiry/touch-logic design fork — **explicitly not F-timing work by the local agent** (banned; any change is a ruled design decision).
- **F-survivor research stays paused**: a non-empty *filled* sample still does not exist.
- Comparability caveat: FR-4b (3 months, post-FR-3.1) is not comparable to FR-4 (1 month, pre-FR-3.1) or Phase C (5 years, pre-reset); each row documents its own machine.

## 7. Artifacts & governance

- Script: `06_RESEARCH/scripts/fr4b_wider_window.py` (thin wrapper over `fr4_fidelity_baseline.py`; gate pass-through recorder; exit/anchor mix post-processor)
- Results: `06_RESEARCH/results/fr4b_wider/run{1,2}/` (`trades.csv`, `report.json`, `summary.json`)
- Governance: `00_LOCKED/SESSION_HANDOFF.md`, `00_LOCKED/POST_V1_ACTIVE_TODO.md`, `00_LOCKED/CHANGELOG.md` updated.

**No parameter changes. Diagnostic only. The chain stops at the fill — measurement, not a redesign mandate.**
