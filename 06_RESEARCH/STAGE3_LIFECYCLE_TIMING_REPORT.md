# STAGE 3 LIFECYCLE TIMING AUDIT — completions vs armed-POI scan window

**Status: PASS** · suite **780 passed** (772 + 8 new) · `locked_constants.py` diff empty · double-run ledger + summary byte-identical · sanity: the 2 `route_would_form=yes` rows land in `OPEN_SCAN`.
**Scope:** identification / measurement only. No `04_SRC/smc/**` edit, no §5/§23/§24 window widening, no new thresholds or filters, no what-if expiry reruns, no expectancy/PnL/edge claims (`LOGIC_CHANGED: NO`).

---

## 1. Method

For each of the **263** Stage 3 completions already recorded in
`06_RESEARCH/results/stage3_trigger_visibility/events_stage3_triggers.csv`,
recover its parent HTF structure and the product lifecycle events using the
**same product rules the runner uses** — the accepted §5-mirrored replay
(`stage3_trigger_visibility.observe_routes_instrumented`, the instrumented
copy of the accepted LTF-pack route replay: arm at structure close →
`feed_bar` state machine → first-touch +1 scan gate → violation / give-up /
route retirement). Nothing was regenerated: inputs (Stage 3 ledger, accepted
H4/D1 packs, canonical M1 parquet, LTF-pack detector markers) were reused
from disk.

Cross-checks on the run: recomputed inventory = **263** (matches the source
ledger), bucket counts **199 touch-gate / 62 violation** match the accepted
Stage 3 pack's route funnel exactly, 0 unclassified, 0 causal-order
violations.

Lifecycle columns written per completion: `structure_close_ts`, `arm_ts`,
`first_touch_ts`, `scan_close_ts`, `scan_close_event_ts`,
`scan_close_reason`, `stage3_completion_ts`, four bar deltas, four minute
deltas, `bucket`.

### Join rules

- `related_htf_event_id` → `poi_raw.event_id` in the accepted H4 pack
  (`events_h4_poi.csv`, in-window) + D1 subset (≤10, same loader rules as
  the Stage 3 pack). **263/263 joined — DATA_GAP = 0, NEVER_ARMED = 0.**
- `structure_close_ts` = HTF open ts + timeframe (H4 +4h / D1 +24h) — the
  product's arm anchor (identical to the `structure_close` recorded in the
  Stage 3 ledger notes).
- `arm_ts` = first M5 bar at/after structure close (the replay arms on that
  bar; **in bar terms arm coincides with structure close for all 263 rows**;
  11 rows show minute-level gaps because the close fell in a weekend
  non-trading span and the arm moved to the first tradable bar, e.g.
  Sat 2025-07-12 00:00 close → arm Sun 2025-07-13 22:00).
- `first_touch_ts` = first M5 bar whose `feed_bar` reports `TESTED`
  (null = never reported TESTED).
- `scan_close_ts` = timestamp of the **last bar the §5 scan was open**
  (inclusive close boundary — visibility = `completion ≤ scan_close`);
  `scan_close_event_ts` = the pop/retire bar itself; `scan_close_reason` ∈
  {first_touch_gate, zone_violation, give_up, route_retire, never_opened}.
  Using the inclusive boundary guarantees "would be visible to product"
  never counts the bar on which the gate fired (the scan does not run on
  the pop bar).

## 2. Bucket counts

| Bucket | Count | % of all |
|---|---:|---:|
| **OPEN_SCAN** (visible to product) | **2** | **0.76%** |
| **CLOSED_TOUCH** (after first-touch +1 gate) | **199** | 75.67% |
| **CLOSED_VIOL** (after zone violation) | **62** | 23.57% |
| NEVER_ARMED | 0 | 0% |
| DATA_GAP | 0 | 0% |
| *(unclassified / defect)* | *0* | *0%* |
| **Total** | **263** | 100% |

### Counts per trigger type × bucket

| Type | OPEN_SCAN | CLOSED_TOUCH | CLOSED_VIOL | NEVER_ARMED | DATA_GAP | Total |
|---|---:|---:|---:|---:|---:|---:|
| A | 0 | 22 | 9 | 0 | 0 | 31 |
| B | 0 | 11 | 6 | 0 | 0 | 17 |
| C | 0 | 4 | 0 | 0 | 0 | 4 |
| D | 0 | 0 | 0 | 0 | 0 | 0 (structurally unreachable) |
| E | 0 | 7 | 0 | 0 | 0 | 7 |
| F | **2** | 155 | 47 | 0 | 0 | 204 |
| **Total** | **2** | **199** | **62** | **0** | **0** | **263** |

- **% of all completions that are OPEN_SCAN: 0.76%**
- **% of F completions that are OPEN_SCAN: 0.98%** (2/204)
- Sanity: the 2 routed rows (`s3-F-evt-ec41701aca47-25836`,
  `s3-F-evt-499a786ac28b-46505`) both classify **OPEN_SCAN → PASS**.

## 3. Distributions (M5 bars)

`completion − event` in bars; negative = completed while the event's window
was still open. Null-safe (`n_null` reported; nulls are the 62 never-opened
violation scans for touch/scan-close metrics — timestamps marked "or null"
in the directive, never invented).

| Group | Metric | n_used | n_null | p25 | median | p75 |
|---|---|---:|---:|---:|---:|---:|
| OPEN_SCAN (n=2) | completion − first_touch | 2 | 0 | 0.25 | **0.5** | 0.75 |
| OPEN_SCAN (n=2) | completion − scan_close | 2 | 0 | 0.0 | **0.0** | 0.0 |
| OTHERS (n=261) | completion − first_touch | 199 | 62 | 5.5 | **11.0** | 14.5 |
| OTHERS (n=261) | completion − scan_close | 199 | 62 | 4.5 | **10.0** | 13.5 |

- **Median completion − scan_close: 10 bars (all, n_used 201) / 10 bars (F only, n_used 157).**
- Both OPEN_SCAN rows complete **exactly on the last open scan bar**
  (delta 0), first touch 1 bar before (`arm+1` / `arm+2`).
- Closed completions arrive **1–19 bars after scan close** (median 10);
  all completions sit **2–20 bars after structure close**, inside the
  locked `poi_give_up_bars()=20` horizon (no window was widened to obtain
  any of these numbers).

## 4. Structural observations from the join (facts, not opinions)

1. **Arm is immediate:** the product arms on the structure-close bar for
   every completion row (bar deltas `completion − close` and
   `completion − arm` are identical across all 263 rows).
2. **First touch lands on the arm bar for all 199 touch-closed
   structures** (`first_touch_ts == arm_ts`, 199/199): the zone already
   contains price when the HTF structure closes, so the §5 seek's live
   span is `[arm, arm+1]` — two bars — before the first-touch +1 gate ends
   it.
3. **All 62 violations fire on the arm bar too** (`scan_close_event_ts ==
   arm_ts`, 62/62): price closed beyond the zone at arming, the scan never
   opened (`first_touch_ts` and `scan_close_ts` are null by rule), and the
   completions still formed inside the 20-bar inventory window afterwards.
4. **Nothing was missed while a scan was open:** OPEN_SCAN = 2 = exactly
   the 2 routed rows; combined with the accepted pack's funnel
   (`scanned_not_routed = 0`), every in-scan completion became a route and
   no in-scan completion was left unrouted.
5. Cross-pack consistency: bucket counts reproduce the Stage 3 pack's
   funnel (199 touch-gate / 62 violation) with an independent
   classification path.

## 5. Decision inputs (observations only — no recommendation, no code change)

**a) Keep contract.** Under the current arming + one-touch contract the
product-visible share of formed Stage 3 geometry is **2/263 = 0.76%**; 100%
of visible completions are the two F routes, each completing on the scan's
last open bar. For this window the contract's effective seek span is two
bars per structure (observation 2) or zero (violation at arm, observation
3). These are the numbers that describe what "keep" sustains.

**b) Redesign seek window.** **261/263 (99.24%)** completions completed
after scan close: 199 after the first-touch +1 gate, 62 with no open scan
at all (violation at arm). Timing against the close boundary: median
**+10 bars** (p25 4.5 / p75 13.5); against first touch: median **+11 bars**
(p25 5.5 / p75 14.5); all within the locked 20-bar horizon (range +1…+19
bars past close). This is the measured arrival distribution any seek-window
redesign would be evaluated against — no alternative window was run or
simulated here.

**c) Further F filtering.** F contributes **204/263 (77.6%)** of all
completions and **202/261 (97.3%)** of closed ones (155 touch / 47
violation); its OPEN_SCAN rate (0.98%) is statistically indistinguishable
from the all-type rate (0.76%) at these counts. Any additional F-side
filtering would act predominantly on rows that are already outside the
contract's visibility — where the completion volume sits, stated as a
measurement; no filter was designed, tuned or tested.

## 6. Explicit non-claims

- No expectancy, PnL, win-rate, edge, or trade-quality claims; no
  threshold, expiry, or window was altered, and no what-if reruns were
  performed (locked constants untouched, diff empty).
- No recommendation: sections 5a–c are decision inputs only; the contract
  is unchanged and no redesign is proposed or implemented.
- `route_would_form` remains a pre-pillar router signal (pillars / risk /
  execution not run); OPEN_SCAN = visibility to that replay, not a fill or
  a trade.
- Distributions over `first_touch` / `scan_close` exclude the 62
  never-opened violation rows by construction (null-safe, `n_null`
  reported); they are not zeros.

---

**Artifacts:** `06_RESEARCH/results/stage3_lifecycle_timing/`
(`events_lifecycle.csv` 263 rows × 23 columns, `summary.json`, `charts/` 3
illustrative panels — one per populated bucket: `001` OPEN_SCAN,
`002` CLOSED_TOUCH, `003` CLOSED_VIOL, rendered with the existing Stage 3
panel helper and lifecycle facts in the caption) ·
script `06_RESEARCH/scripts/stage3_lifecycle_timing.py` ·
tests `04_SRC/tests/test_stage3_lifecycle_timing.py` (8) ·
inputs reused: `results/stage3_trigger_visibility/`, `results/h4_poi_confirmation/`,
`results/d1_f1f2_resample/`, `results/ltf_confirmation/`, `07_DATA/XAUUSD_M1.parquet`.
