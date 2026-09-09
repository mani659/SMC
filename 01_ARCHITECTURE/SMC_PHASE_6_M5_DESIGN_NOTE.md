# Phase 6 — Milestone 5 Design Note: Core Reports

Status: COMPLETE — full suite **481 passed** (467 pre-existing + 14 new M5 tests). Deterministic, MT5-free, reporting consumes results and never owns the loop.

---

## 1. New / modified files

| File | Change |
| --- | --- |
| `04_SRC/smc/backtest/reports.py` | NEW — `TradeRecord`, `CoreMetrics`, `GroupMetrics`, `BacktestReport`, `build_report` (pure projection) |
| `04_SRC/smc/backtest/export.py` | NEW — `to_csv` (trade list) + `to_json` (full report), deterministic serialization |
| `04_SRC/smc/backtest/runner.py` | MODIFIED — `RunnerResult` snapshot dataclass, `runner.result()` collection method, §11 `route_id` captured at placement → fill ticket → closed-tickets map |
| `04_SRC/tests/test_backtest_reports.py` | NEW — 14 tests (metrics, breakdowns, empty run, determinism, exports, integrated path) |

---

## 2. Metrics definitions (V1, frozen)

* **win** — the close record's own flag (SL → loss, TP → win; runner-driven closes derive it price-symmetrically in the store).
* **P/L** — `ClosedPosition.realized_pnl` verbatim: `(exit − entry) × direction_sign × volume` in raw V1 price units (no contract-size conversion anywhere in M2–M5).
* **win_rate** — wins / trades; **0.0 on an empty run** (defined zero).
* **gross_profit / gross_loss** — sum of winning / losing P/L; the loss side is a POSITIVE magnitude. A P/L of exactly 0 counts as a loss (no fabricated break-even bucket).
* **profit_factor** — gross_profit / gross_loss. **Zero-loss case (explicit): `None`** — an infinite PF is not representable in V1 JSON; empty runs and all-winner runs yield `None`. All-loser runs yield `0.0` (GP = 0 over positive GL).
* **net_pnl** — sum of all P/L.
* **max_drawdown** — peak-to-trough on the closed-trade equity curve (cumulative P/L in close order, starting equity 0); ≥ 0, `0.0` when equity never dips below its running peak. Intrabar MAE/MFE out of V1 scope.
* **avg_win / avg_loss** — gross_profit / wins, gross_loss / losses; `None` when that side has no trades.

Breakdown groups use the same semantics (`GroupMetrics`), plus win/loss counts.

---

## 3. Identity fields used for breakdowns

* **Per trigger** — the trade's normalized trigger value string (the frozen single-letter enum values: `"A"`…`"F"`); `None` → the `"unattributed"` bucket (e.g. M3-seam candidates with no trigger).
* **Per POI** — the trade's `poi_id`; `None` → `"unattributed"`.
* **`route_id`** — the §11 event identity (`"{poi_id}:{trigger}@{completion_bar}"`), surfaced per trade. The M4 pipeline path records it (order `comment` → fill ticket → closed map); trades entered through the plain M3 seam simply have `None` — never invented.
* **Model tags are NOT available on closed positions** (they live on the POI object, which reporting must not reach into), so there is no per-model section — per-POI grouping is the best honest mapping. Nothing is fabricated.

---

## 4. Runner seam (kept tiny, per guidance)

`runner.result()` returns one frozen `RunnerResult(closed, blocked, route_ids)`:

* `closed` — the position store's `ClosedPosition` list (close order);
* `blocked` — the runner's `BlockedEntry` log (occurrence order);
* `route_ids` — closed ticket → §11 identity (identity-absent trades are simply not keyed; the dict is `None`-free).

Reporting is a pure read over this snapshot — the runner remains fully usable without reports.

---

## 5. Optional visibility + exports

* **blocked_by_reason** — counts keyed by the risk engine's block reason (`news`, `session`, `circuit_breaker`, `same_level`, `sweep`, `spread`, `min_lots`), straight from the log; empty dict on an empty run.
* **Cancelled/expired pendings are NOT counted** — the M2 stores do not track cancellation events; nothing is fabricated.
* **CSV** — trade list only (fixed 18-column header; `None` → empty cell, enums/datetimes `str()`-normalized).
* **JSON** — full report (metrics + both breakdowns + blocked counts + trade list), `sort_keys=True`, byte-identical for identical reports (asserted in tests).

---

## 6. Empty-run behaviour

`build_report` on a run with zero trades returns defined zeros/`None`s — never a crash: `win_rate 0.0`, `gross_* 0.0`, `profit_factor None`, `net_pnl 0.0`, `max_drawdown 0.0`, `avg_win/avg_loss None`, empty breakdown dicts, empty trade tuple.

---

## 7. Determinism

No wall clock, no MT5, pure functions over the snapshot; breakdown dicts are built in sorted-key order. Identical inputs produce equal `BacktestReport` objects and byte-identical JSON (both asserted).

---

## 8. Blocking open questions

None blocking M5. Two notes for M6 (paper trading):

1. `route_id` currently reaches reports only via the runner's in-memory map — if the paper runner persists closes, persist the identity alongside to keep the trade log self-contained.
2. If per-model breakdowns become mandatory later, the honest fix is carrying model tags onto `BacktestPosition` at fill (pipeline change), not reconstructing them in reporting.
