# P1 Chart-Contract + Wrong-Extreme Data Audit

`LOGIC_CHANGED: NO`  
Research/instrumentation only — no edits to `04_SRC/smc/**`, no `locked_constants` changes. P2 still blocked.

## 1) Method (series, period definitions, tick quantum)

- **Data:** `07_DATA/XAUUSD_M1.parquet` loaded via `plan_complement_ledger.load_m1` (warm-up 2025-03-01T00:00:00Z → exec end+1d). Exec window `2025-06-01T00:00:00Z..2025-11-30T23:59:59Z` (UTC). H4 resampled via `smc.data.resample.resample_ohlcv`.
- **Periods (locked):**
  - **PDH/PDL:** prior completed UTC calendar day before `as_of` (aggregated from M1 by bar-open date). Period = `[day_start, day_start+1d)`. True extreme = max/min over all M1 bars in that completed day.
  - **PWH/PWL:** prior completed Monday-anchored week (completed weeks = week Monday < Monday of reference). Period = `[week_monday, week_monday+7d)`. True extreme = max/min over M1 bars in that completed week.
  - **Session H/L:** per `(UTC day, session)` from `smc.utils.timestamps.detect_session` (Asia 00:00–07:00, London 07:00–13:00, NY 13:00–20:00 UTC; outside 20:00–24:00 skipped). True extreme = max/min over M1 bars in that (day,session) group.
  - **EQH/EQL:** clusters from `smc.detection.structural_swing_detector.detect_swings(h4_all, Timeframe.H4)` clustered by `smc.detection.eqh_eql_detector._cluster` (greedy, tolerance = `pips_to_price(EQH_EQL_TOLERANCE)=pips_to_price(4.5)` per locked constants). Cluster extreme = max of swing levels (BSL/EQH) / min (SSL/EQL). Period span = `[min(member.timestamp), max(member.timestamp)]` (cluster formation span). Touches = all cluster members plotted.
  - **Structural:** optional audit; treated separately (not strictly day/week/session bounded in same sense).
- **Tick/quantum:** comparisons use float equality `abs(err) <= 1e-9` for EXACT_MATCH; otherwise WRONG_EXTREME if label != true period extreme (for period-bounded families). No detector changes.

## 2) Audit counts table by family × flag

From `06_RESEARCH/results/p1_wrong_extreme_audit/summary.json`:

| Family | EXACT_MATCH | WRONG_EXTREME | OUT_OF_PERIOD | DATA_GAP | BOUNDARY_AMBIGUOUS |
|---|---|---|---|---|---|
| eqh_eql | 8 | 0 | 0 | 0 | 0 |
| pdh_pdl | 314 | 0 | 0 | 0 | 0 |
| pwh_pwl | 54 | 0 | 0 | 0 | 0 |
| session | 780 | 0 | 0 | 0 | 0 |
| structural_swing | 83 | 0 | 0 | 0 | 0 |

**WRONG_EXTREME_COUNTS:** `{EQH_EQL: 0, PDH_PDL: 0, PWH_PWL: 0, SESSION: 0, STRUCTURAL: 0}`  
**OUT_OF_PERIOD_COUNTS:** `{EQH_EQL: 0, PDH_PDL: 0, PWH_PWL: 0, SESSION: 0, STRUCTURAL: 0}`

Audit CSV: `06_RESEARCH/results/p1_wrong_extreme_audit/wrong_extreme_audit.csv` (1239 rows), deterministic dual-run PASS (SHA256 equal). Artifacts in `06_RESEARCH/results/p1_wrong_extreme_audit/` (gitignored).

## 3) WRONG_EXTREME catalog (event_id, label vs true extreme, brief cause hypothesis — no code fix)

**No WRONG_EXTREME rows found by machine period-true-extreme check.**  
If Architect’s visual scoring identified specific charts as wrong-extreme, this audit provides period boundaries + true extremes in the CSV for each row to reconcile (formed_at vs period, day/week/session boundaries). No detector fixes were made.

## 4) Chart-contract changes delivered

Contract applied to re-rendered charts (`06_RESEARCH/results/p1_wrong_extreme_audit/charts_contract/`, 38 charts rendered):
1. Horizontal level line + formed_at vertical marker (kept).
2. **Period boundaries (vertical lines):**
   - PDH/PDL: UTC midnight start/end of previous completed day (dotted orange)
   - PWH/PWL: Monday 00:00 UTC start and next Monday 00:00 UTC end of **full prior week Mon→Mon** (dotted orange). **Full-week windows enforced** (non-negotiable).
   - Session: session open/close from locked windows (dotted green)
   - EQH/EQL: cluster span [first touch, last touch] (dotted orange) + **all cluster touches plotted (red markers)**
   - Structural: context as appropriate
3. Caption includes family/side/price/formed_at/period_id/source + audit flag.
4. Windows: PDH/PDL full previous day ±context, **PWH/PWL full prior week Mon→Mon**, Session full session ±30m context, EQH/EQL all touches visible, structural kept with H4 context.

## 5) EQH cluster status (rendered / DATA_GAP)

**EQH_CLUSTER_RENDER: YES**  
All EQH/EQL rows re-rendered with cluster touches plotted; `n_touches` and `cluster_members_json` captured in audit CSV (research exporter extended in-script by re-clustering swings read-only; no `04_SRC/smc` edits). Cluster span boundaries shown.

## 6) Residual limits

- Audit compares **label vs period true extreme** on the same series the detectors use (M1 for period/session, H4 swings for EQH clusters). This is a necessary but not sufficient condition for “correct label” — visual context (wick/body, bar identity, formation semantics) still requires human review.
- “WRONG_EXTREME” flag is strict (label must equal true extreme of period). Ties/boundary cases marked EXACT_MATCH only on equality.
- Structural swings are not strictly day/week/session bounded; structural audit kept minimal per directive.
- EQH cluster membership reconstructed from production clustering logic in research code (read-only) — matches detector behavior.

## 7) Explicit: P2 still blocked; no family auto-accepted

- **P2 (pool ranking / interaction / sweep coupling) is STILL BLOCKED** pending Architect re-score of P1 after this chart-contract + wrong-extreme audit.
- No family has been auto-accepted by this audit. Machine check shows 0 period-true-extreme mismatches across all families on exported labels; Architect visual scoring may still have findings — reconcile against `wrong_extreme_audit.csv` + contract charts.
- No detector fixes applied. Bans honored: no `04_SRC/smc/**` edits, no `locked_constants` changes.

## Repro

```bash
PYTHONPATH=04_SRC python 06_RESEARCH/scripts/p1_chart_contract_wrong_extreme_audit.py
```

Artifacts: `06_RESEARCH/results/p1_wrong_extreme_audit/{wrong_extreme_audit.csv,summary.json,run.log,charts_contract/*.png}`
