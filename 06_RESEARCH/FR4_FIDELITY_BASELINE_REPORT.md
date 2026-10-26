# FR-4 FIDELITY RE-BASELINE REPORT (post-reset machine, October 2025)

**Status:** COMPLETE 2026-09-21 · measurement + reporting only. No thresholds, no fishing, no redesign.
**Window:** 2025-10-01 → 2025-10-31 exec (M5, 6324 bars); M1 loaded 2025-09-01 → 10-31 for resample/detection context; H1/H4/D1 resampled deterministically (present-bars-only gaps).
**Config (frozen intent):** equity 10_000, risk 0.01, spread 0.0 (gates off — machine completeness, not cost realism), news dormant, all sessions, Friday EOD on; detection H4+H1 (+D1/H4 map into M8); M5 execution; FR-2 TP/SL + FR-3 zone gate live; Trigger D absent on volume-less data (A5, explained).
**Script:** `06_RESEARCH/scripts/fr4_fidelity_baseline.py` (mirrors phase_b wiring: deterministic POI ids, ZoneRegistry dedup, counting wrappers; adds scan counters, armed-fate tracking, TP/routed-M8 counters).
**Artifacts:** `06_RESEARCH/results/fr4_fidelity/run1|run2/` (trades.csv, report.json, summary.json) + `results/fr4_diag_nogate/` (diagnostic ablation, NOT evidence).
**Phase C is archived as pre-reset and incomparable** — different machine (buffered stops, TP routing, zone gate, multi-TF detection). No improvement-hunting table is offered; the only comparison made is architectural (regime labels differ).

---

## 1. Determinism pair: PASS

trades.csv byte-identical ✓ · report.json byte-identical ✓ · summary identical excluding runtime/tag ✓ (SHA-256 compared). Rerun-safe: identical funnel counts across runs (527 HTF batches, 130 scans, 8 armed, 0 routes both runs).

## 2. Funnel (every stage non-zero or explained)

| Stage | H4 | H1 | Note |
|---|---|---|---|
| HTF batches | 527 closes drive re-detection | — | cadence = every new H1 close |
| detected_raw | 4534 | 4829 | batch re-evaluations across closes (events, not uniques) |
| passed | 90 | 119 | first-failure: displacement 4877, zone_ref 327, P/D 277, PASS 209 |
| armed_unique | 3 | 5 | ZoneRegistry geometric dedup across TFs |
| armed_m8 | 4 (both runs) | — | M8 zones arm like any POI |
| scan_calls / scan_routes | 130 / 0 | — | scans run; no trigger completes (see §3) |
| routes / placed / closed | 0 / 0 / 0 | — | explained below |

Armed fates: 5 TESTED (2 same-bar — armed inside current price, instant terminality), 3 never touched (zones far from month-end price). Positions flat at window end (Friday EOD working).

## 3. Why zero routes (mechanism, proven by ablation)

A diagnostic-only ablation (`--diag-no-zone-gate`, monkeypatched in the research script, production untouched) on the identical window: **100 scans → 2 routes (both F, both M8-tagged) → 2 placed (both TP-carrying) → 2 closed (both SL)**. Therefore:
- The FR-3 zone gate is THE binding constraint in this window — without it, F (incl. M8) routes; with it, nothing does. Reported as mechanism, not a tuning proposal; the gate stands as ruled.
- The full FR-1+FR-2 machine is proven live end-to-end (M8 zone → F trigger → TP-carrying order → broker-model close) — in diag only.
- The 8 compliant armed POIs otherwise die by freshness (wide HTF zones tested within ~1–20h) faster than LTF patterns complete. No wiring bug: scans execute, triggers evaluate, patterns don't complete in-window.

## 4. Breakdowns

- **By detection TF:** H4 90 passed / 3 armed; H1 119 passed / 5 armed; M8 zones among armed: 4.
- **By trigger:** {} (compliant); diag {F: 2}.
- **Model tags on trades:** n/a (no compliant trades); M8 routes exist only in diag.
- **TP path:** compliant tp rate 0/0 (vacuous — no placements); diag 2/2 placed with TP, 0 TP closes (consistent with R2: TPs rarely hit). Backtest fill-model TP branch remains unit-proven.
- **Zone gate:** rejects unlogged by design (trigger returns None) → N/A with this mechanism documented; residual: gate-reject counter.
- **Trigger D:** 0 trades (volume-less data, A5).

## 5. Invariants (Phase B style)

Determinism ✓ · D==0 ✓ · no crash, flat book ✓ · limit-fill/SL-first/BE/expiry paths unexercised (empty book — stated, not hidden). Phase B invariant proofs on shared machinery stand (runner/fill/state machine untouched by FR-1/2/3 except SL values, TP carriage, and the F gate — all covered by FR-1/2/3 tests).

## 6. Compliance scorecard

| Check | Result |
|---|---|
| Multi-TF detection (H1+H4 in config, batches ran, per-TF counts) | YES |
| M8 observed | ARMED (4 zones); routed/traded only in diag (2/2) — SILENT in compliant routing, explained by §3 |
| TP not always None | PLACED with TP in diag (2/2); vacuous in compliant run |
| SL buffer path live | BY CONSTRUCTION (all placements flow through buffered references; unit-tested) |
| Single-TF alarm not the production path | YES — this loop hardcodes H4+H1 detection (no M1-only code path exists in the script); the `single_tf_detect_exec` flag itself is unit-proven in FR-1 |

## 7. Stretch decision

2–3 month extension SKIPPED with rationale: the gate ablation bounds expectations (~0–6 routes/quarter at this strictness); a longer zero-trade run adds no machine-completeness information beyond the diag proof. Revisit only if the gate policy is ever re-ruled.

## 8. Reset verdict: YES_WITH_RESIDUALS

Per plan success definition: (a) FR-1 exits hold on a fresh window ✓ (H4+H1 detection, M5 execution, M8>0 armed, per-TF funnel, M1-only alarm live); (b) scorecard re-run — cascade nodes now WIRED with remaining SILENT-at-routing on M8/C/E/D (explained, not hidden); (c) FR-2 implemented ✓; (d) Lead Architect acceptance pending. Residuals: empty-book limits (TP-close path, M8-route path in compliant mode, trigger mix — proven in diag/unit only); gate-reject counter missing; per-bar loop covers one month only; Phase D drill still GUI-blocked.

---

*End of report. Next: Lead Architect acceptance decision on the Reset (COMPLETE vs follow-ons). F-survivor work stays PAUSED regardless.*
