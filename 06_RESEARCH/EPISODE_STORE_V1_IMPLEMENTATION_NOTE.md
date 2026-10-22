# EPISODE STORE V1 — IMPLEMENTATION NOTE
**Date:** 2026-10-13  
**Status:** COMPLETE (V1 Observability-Only)  
**Authority:** `00_LOCKED/EPISODE_STORE_DESIGN.md` + §9a Architect rulings  
**LOGIC_CHANGED:** NO (all decision paths unchanged)  

---

## 1. Executive Summary

This note documents the implementation of `EpisodeStore` V1 in `smc/orchestration/episode_store.py`.
The store provides unified in-memory, append-only lifecycle event tracking and query infrastructure without changing any product arm/scan/route/risk/execution decision paths.

All Section 9a mandatory rulings are fully satisfied:
1. **Geometric Identity**: `(direction, detection_tf, m8_kind_class, [zone_low, zone_high] under ZoneDedup overlap-equivalence, 6dp bounds)`. `poi_id` and `route_id` are attributes and lookup keys, never identity.
2. **H4 vs M8←H4 Separation**: Treated as separate episodes due to distinct `detection_tf` / `m8_kind_class`. Overlap records mutual `related_episode` links without forced merging.
3. **Refinement Adoption**: Tighter armed box inside parent geometry is the *same episode*, adopting the refined bounds and establishing mandatory parent linking.
4. **ZoneDedup Sole Merge Authority**: Store does not create parallel dedup logic; suppressions by `ZoneDedup` are recorded as facts on the existing episode.
5. **EXPIRED_UNARMED**: Represented as a first-class terminal state for POIs that passed validation but were never armed in-run.
6. **V1 Scope**: In-memory per run/process, loud-fail on missing fields / clock regressions, no Redis, zero decision-path reads.

---

## 2. Modules & Seams Shipped

### 2.1 Core Module: `smc/orchestration/episode_store.py`
- `EpisodeState` enum (normative 25 states per Design §4.1).
- `EpisodeEventKind` enum (append-only event types).
- `EpisodeIdentityKey` (canonical geometric grain, 6dp rounded, normalized direction/tf/m8).
- `EpisodeEvent` (frozen dataclass: episode_id, kind, ts (UTC), bar_index, tf, data dict).
- `EpisodeRecord` (mutable aggregate maintaining state, bounds history, refinement, and events).
- `EpisodeStore`:
  - `resolve_identity(...)` using `ZoneDedup` overlap predicate.
  - `record_event(...)` with loud validation and no-lookahead assertions.
  - Query API: `get`, `get_by_poi`, `get_by_route`, `state_at(id, bar)`, `events_for`, `fate`, `funnel()`, `coincidence_hits(H)`, `blueprint(id)`.
  - Export API: `to_rows()`, `export_events_rows()`, `write_csv(path)`, `write_json(path)`.

### 2.2 Integration Hooks (Default OFF / None)
- `MultiTFProductRuntime.__init__(..., episode_store=None)` and `_arm_passed`:
  - When `episode_store` is provided, records `validated`, `rejected_pillar`, `suppressed_dedup`, and `armed`.
  - Wrapped in exception guards so store failures never disrupt batch processing.
- `PipelineEngine.__init__(..., episode_store=None)` and `arm_at`:
  - When `episode_store` is provided, records `armed` and `posture_classified`.
- `phase3_structure_funnel.py`:
  - Accepts optional `episode_store` on `args`, passing it through to `PipelineEngine` and `MultiTFProductRuntime`.

---

## 3. Parity & Invariance Proof

1. **Short Window Parity Proof**:
   Ran `phase3_structure_funnel` over a 5-day verification window with `episode_store=None` vs `episode_store=EpisodeStore()`:
   - `trades.csv`: **BYTE-IDENTICAL** (`TRADES_BYTE_IDENTICAL: True`).
   - `report.json`: **SEMANTICALLY IDENTICAL** (`REPORT_EQUAL: True`, zero trade differences, identical funnel).
2. **Determinism**:
   Column orders for CSV and JSON exports are fixed and canonical. Double run exports produce deterministic outputs.
3. **Derived Counters & Defect Fix**:
   Derived counters in `EpisodeStore.funnel()` count real event instances (e.g. `intent_expired_no_reentry`), structurally eliminating the prior `expired 0` defect.

---

## 4. Test Suite Verification

- 11 dedicated unit and integration tests in `04_SRC/tests/test_episode_store_v1.py` covering:
  - H4 vs M8←H4 separation with related links.
  - Refinement parent bounds adoption.
  - ZoneDedup suppression recording.
  - EXPIRED_UNARMED transition.
  - Stable export ordering (CSV/JSON).
  - Absence of decision APIs (`should_arm`, etc.).
  - One-shot route invariant.
  - No-lookahead causal state queries (`state_at`).
  - Derived counters reconciliation.
  - Runtime integration hook and parity test.
- Full test suite: **1,062 tests passed** (0 failures).
- `locked_constants.py`: **Untouched** (clean diff relative to starting state).

---

## 5. Residuals & Next Steps

Remaining hook points documented for follow-up wiring:
- Hooking `PipelineAdapter.generate_candidates` for `route_formed`, `scan_closed`, `ltf_completion`.
- Hooking `BacktestRunner` / `IntentBook` for `intent_*`, `placed`, `filled`, `closed_*`.
- Next ready: Architect review / Reactive-admission design.
