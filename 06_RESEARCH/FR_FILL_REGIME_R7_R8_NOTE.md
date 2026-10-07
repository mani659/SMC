# FR FILL-REGIME POLICY — R7 + R8 (2026-09-22)

**Status:** implemented per Lead Architect ruling; diagnostic only.
**Scope:** fill-regime policy after FR-4b (routing healthy 6/6 gate-accepts, 0 fills in 3 months) and the FR-4b unfilled-order forensic (3 September trend-runaways never returned; 2 October M8 near-misses touched only after §23 expiry).

---

## 1. Policy (as ruled)

| Ruling | Rule | Frozen inputs (none added) |
|---|---|---|
| **R7 — place guard** | At place time, if the **market reference** is outside the routed POI zone by more than the existing FR-3 band → **do not place**; machine-readable skip. | Band = `ZONE_REFINEMENT_ATR × ATR` (existing constant; asserted unchanged in tests). |
| **R8 — HTF resting bars** | Pending lifetime = `rest_bars_for(detection_tf, is_m8)` in M5-bar units, §23 inclusive convention (order placed on bar N is fill-eligible on N+1 … N+rest−1). | M30/M5/M1/unknown-LTF → execution-TF §23 default (12 on M5); **H1 → 36; H4/M8 → 48; D1 → 48**. |

`GATE_WIDENED = NO` — the FR-3 gate, `ZONE_REFINEMENT_ATR`, and all locked constants are untouched (test-asserted).

## 2. Modules & wiring (single source)

- **`smc/risk/fill_regime_policy.py`** — `zone_place_allowed(direction, zone_low, zone_high, price, atr)`, `rest_bars_for(detection_tf, is_m8, execution_tf=None)`, `give_up_backstop_bars()`. Imported by backtest runner, paper runner (no copy-paste).
- **Backtest runner** — R7 guard after risk-acceptance, before `orders.place()`; skip logged as `BlockedEntry(blocked_by="skip_place_far_from_zone")` and aggregated in `report.json → blocked_by_reason`. R8 via `rest_bars=rest_bars_for(candidate.detection_tf, candidate.is_m8, execution_tf=self.config.timeframe)`.
- **`smc/backtest/orders.py`** — `PendingOrder` gained `rest_bars` + `detection_tf`; per-order §23 expiry uses `rest_bars` (legacy path unchanged when `rest_bars is None`); give-up (20) remains an **independent** hard backstop — the book cancels at whichever threshold hits first, so HTF rest is never silently shortened below R8.
- **`smc/backtest/pipeline_bridge.py`** — `CandidateEntry` carries `detection_tf` + `is_m8` provenance from the route/POI.
- **Paper runner** — same guard in `_entry_step` (KPI `record` event `skip_place_far_from_zone`), per-pending `rest_bars` in `_TrackedPending` + `_expire_pendings` mirroring the book's independent-threshold behavior (fixed during testing: it initially max()'d the two thresholds, silently raising the frozen M5 lifetime — corrected to mirror the book exactly).

### Documented semantic decisions (within ruling bounds)

1. **"mid/ref price" = market close at place time** (the completed bar's close — the backtest proxy for mid). The order's *limit* is zone-anchored by FR-3.1 and would make the guard vacuous; the forensic's September-runaway class is distinguished by the **market**, not the limit, being far from the zone. An intermediate run using the limit as reference made R7 inert (0 skips — it skipped nothing); superseded by the market reading.
2. **R7 skip is retryable** — the one-shot burns only on accepted placement (existing M4 semantics), so an R7 skip behaves exactly like a news/session block. Documented choice per ruling §B.
3. **Fail-safe defaults** — zone missing/unlocatable → guard is dormant (allows; keeps M3-seam candidates flowing, matches module contract); `atr <= 0` → band 0 (fail closed); unknown/missing detection TF → R8 falls back to the execution TF's own §23 default (never silently shortens an M1-execution run's 30-bar default to 12).

## 3. Smoke — FR-4b window with R7+R8 (frozen config)

Window `2025-09-01 → 2025-11-30` (17,840 M5 bars), isolated out-root `results/fr7r8_smoke/run1/`; determinism pair untouched.

```text
funnel:      identical to FR-4b (htf_batches 1488, armed 21 = 17 H1 + 4 H4, M8 15,
             routes 6 = 4 M8) — routing and gate untouched
R7 skips:    10 blocked events (retryable re-proposals across bars of the 6 routed
             candidates) — reason skip_place_far_from_zone
places:      0     fills: 0     trades: 0     book flat
M8 chain:    15 armed / 4 routed / 0 filled
```

**Independent geometry verification** (from the M1 parquet; all 5 FR-4b orders were `zone_edge_reanchor` LONGs so limit = zone high):

| ticket | placed_time (UTC) | close at place | zone high (=limit) | market beyond zone | band (0.5×ATR) | verdict |
|---|---|---|---|---|---|---|
| 1 | 2025-09-01 03:10 | 3472.985 | 3414.635 | **+58.35** | 3.23 | skip |
| 2 | 2025-09-01 03:10 | 3472.985 | 3327.446 | **+145.54** | 3.23 | skip |
| 3 | 2025-09-02 16:15 | 3522.375 | 3356.871 | **+165.50** | 1.83 | skip |
| 4 | 2025-10-09 05:35 | 4036.925 | 3995.775 | **+41.15** | 1.73 | skip |
| 5 | 2025-10-20 02:15 | 4262.005 | 4247.355 | **+14.65** | 3.84 | skip |

(6th route = the one FR-4b candidate that never reached placement — session-blocked; not in the table.)

**R8 separately proven live:** in the superseded intermediate run (limit-reference reading), R8 produced the **first filled trade in the chain** — poi-014750 zone-high re-anchor entry 4247.355, filled after the HTF lifetime extension, closed by BE-stop at +0.48 after 5 bars. The mechanism works; the final market-reference R7 simply precedes it.

## 4. Residual for the Architect (D1/D2/D3 evidence — not tuned)

The September-runaway class is now stopped at place time (R7 working as ruled). But the geometry table shows the ruling as written also stops the **October M8 near-miss class R8 was designed to rescue**: at F's signal bar (BOS continuation + OB retest), the close has already run 14.65–165.50 units beyond the zone — 4–10× the frozen 0.5×ATR band — so **R7+R8 together produce zero placements in this window, and R8 never gets to act**. Fills under the current stack require the market to be near the zone when F completes, which the F-timing question (PAUSED per R6) would address. No constant was changed to bridge this; the tension is recorded here for the D1/D2/D3 ruling.

## 5. Tests

`04_SRC/tests/test_fill_regime_r7_r8.py` — 33 tests: R7 far-in/far-out/in-zone/dormant/fail-closed cases, retryability (one-shot preserved on skip), R8 table (H1=36, H4/M8/D1=48, M5/M1 defaults, execution-TF guard), inclusive expiry convention (place on N, eligible N+1..N+rest−1, expiry event at N+rest), give-up backstop independence, `ZONE_REFINEMENT_ATR`-unchanged assertion, paper-path mirror tests.

**Suite: 658 passed** (636 pre-R7/R8 + 22 net new), zero regressions. `04_SRC` touched (policy module + wiring), so the suite claim is load-bearing; FR-1/FR-2/FR-3/FR-3.1 tests intact.

## 6. Artifacts

- `results/fr7r8_smoke/run1/` — smoke summary/report/trades
- `06_RESEARCH/scripts/fr4b_wider_window.py` — unchanged wrapper (same frozen config)
- Policy module + wiring: `smc/risk/fill_regime_policy.py`, `smc/backtest/{runner,orders,pipeline_bridge}.py`, `smc/paper/runner.py`
- Governance: `00_LOCKED/FOUNDATION_RESET_PLAN.md` §8, SESSION_HANDOFF, POST_V1_ACTIVE_TODO, CHANGELOG
