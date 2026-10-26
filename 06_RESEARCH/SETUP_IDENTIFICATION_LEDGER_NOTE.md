# SETUP IDENTIFICATION LEDGER — NOTE (Milestone L2)

**Directive:** Lead Architect, 2026-10-06 — Task 2 (after the live-console
dry-run PASS)
**Status:** PASS — research + export analytics only; no trading threshold
changes; no expectancy claims
**Script:** `06_RESEARCH/scripts/setup_identification_ledger.py`
**Outputs:** `06_RESEARCH/results/setup_identification_ledger/setups.csv`
(30 rows) + `summary.json`

---

## 1. What this is (and is not)

A human-reviewable ledger of the setups the frozen engine **identified** on
the frozen 6m window, for identification validation (count + quality
scoring by a reviewer). It is **not** a PnL/edge artifact: no expectancy
claim, no threshold change, nothing fed back into decisions.

## 2. Primary scope executed (offline)

Source: the frozen **6m post-TP funnel artifacts** —
`06_RESEARCH/results/frozen_funnel_6m_post_tp/run1/`:

- `armed_records.json` — the 30 armed setups (the identification layer:
  passed all five pillars + arming + geometry dedup).
- `funnel_summary.json` — window/counts provenance
  (tag `funnel_6m_post_tp`).
- Join: `06_RESEARCH/results/hypothesis_outcome/trades_hypothesis.csv`
  (run_label `6m_post_tp_run1`) — filled **only** where a setup routed AND
  filled a trade (3 setups).

**Double-run determinism: byte-identical** (`setups.csv` SHA-256
`5388635e…` on both runs; sorted rows, no wall clock; input file SHA-256s
recorded in `summary.json` for provenance).

## 3. Schema (one row per armed setup)

Identity: `setup_index, poi_id, detection_tf, kind, direction, zone_low,
zone_high, zone_mid, armed_bar, pillar_path, disp_magnitude_atr, posture,
routed, trigger, entry, original_sl, tp, entry_anchor, tp_source`.

Human-scoring columns (Directive): **`verdict`** (CORRECT / PARTIAL /
WRONG / UNCLEAR), **`timing`** (EARLY / ON_TIME / LATE / N_A), **`notes`**
— **blank by design**: the script never pre-fills a judgement; that is the
reviewer's step (same convention as the structure-ledger human-label packs).

Optional join columns (populated only when the setup filled): `ticket,
close_kind, pnl, hypothesis_outcome, mfe_units, mae_units`.

## 4. Results (window 2025-06-01T22:00Z → 2025-11-30T23:55Z, exec M5)

| Metric | Value |
|---|---|
| Setups (armed) | **30** |
| By TF | H4 19 · H1 6 · D1 5 |
| Routed | 3 (all 3 with full plan: entry + SL + TP) |
| Hypothesis-outcome join | **YES** — 3 rows: SL_THEN_TP_PATH 2 · TP_REACHED 1 |
| tp_source at trade level | atr_fallback 2 · structural_swing 1 |

Matches the accepted 6m post-TP funnel counts exactly (armed 30 {H4 19/H1
6/D1 5}, routes 10 → placed 4 → fills 3 — the ledger's routed_n=3 counts
armed setups whose funnel record carries `routed=true` AND complete
plan fields; the route/plan distinction is per-record, not a new funnel).

## 5. Honest gaps (documented, never invented)

- **`direction`** — the funnel harness does not export the zone direction;
  it is populated **only** where the trade-level join carries it (3 rows).
  Never inferred from zone geometry.
- **`posture`** — arm posture is not instrumented in the funnel export
  (the 6m post-TP report records the posture mix as UNKNOWN); column kept
  with `UNKNOWN` for schema parity with the future paper export.
- **`kind`** — model tags only (`M8`); the `m8_kind` sub-kind is not
  exported by the funnel harness.
- **`tp_source`** — exists at trade level only (via the join).

## 6. Paper path (documented; NOT required for PASS)

A future paper session feeds the SAME schema by exporting, per armed POI
snapshot + routed candidate: `poi_id, detection_tf, kind(model tags /
m8_kind), direction, zone bounds, arm bar/posture, pillar_path,
disp_magnitude_atr, routed, trigger, entry, original_sl, tp, entry_anchor,
tp_source` — all of which already exist on the live objects
(`engine.tracked_pois()`, `PipelineAdapter.active_workflows()`, batch
report `displacements`, trade records). The natural seam is the operator
KPI/`console_mirror` artifact stream; the ledger loader accepts any CSV
with the same column names, so no paper run is needed to validate the
schema.

## 7. Bans honored

No SL/TP/pillar/trigger threshold changes; `locked_constants.py` diff
**empty**; no expectancy claims (pnl columns are join provenance, not
performance reporting); no `04_SRC/smc/**` edit.

## RETURN BLOCK

```
L2_STATUS: PASS
SETUPS_N: 30
WINDOW: 2025-06-01T22:00:00+00:00 .. 2025-11-30T23:55:00+00:00 (exec M5, 6m post-TP funnel)
HUMAN_COLUMNS: [verdict, timing, notes]
HYP_OUTCOME_JOIN: YES
SUITE: 849 passed
LOCKED_CONSTANTS_DIFF: empty
NOTE_PATH: 06_RESEARCH/SETUP_IDENTIFICATION_LEDGER_NOTE.md
HANDOFF_UPDATED: YES
NEXT_READY: Architect review | paper ops
```
