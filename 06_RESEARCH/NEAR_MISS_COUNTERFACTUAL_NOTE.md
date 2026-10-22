# NEAR-MISS / COUNTERFACTUAL STUDY — DID PLACEMENT GATES KILL GOOD PATHS?

> **DIAGNOSTIC — NOT EDGE.**
> Seven routed-but-untaken candidates were paper-traded under the frozen
> fill semantics (10 routes total, 3 of them the real fills). Counts of
> seven and three support no expectancy, win-rate, or profit-factor
> claim in either direction. No gate was loosened, no threshold moved,
> no product code touched, and nothing below authorizes a change.

**Date:** 2026-10-13 · **Authority:** Lead Architect owner plan
`00_LOCKED/OWNER_PLAN_MULTI_TF_TRANSLATION_2026-10-13.md` (binding ordered work, **step 1 =
this study**) and proof register `06_RESEARCH/RESEARCH_PROOF_REGISTER_2026-10.md` §B3
(**PRIMARY_NEXT**, with the §B4 recorded dissent on sequencing).
**NEAR_MISS_STATUS: PASS** (capture byte-identical to the frozen 6m run; control fills
reproduced 3/3; 27 new tests green; suite **1039**).
**Scope:** read-only measurement. `LOGIC_CHANGED: NO` — `04_SRC/smc` decision paths
untouched, `locked_constants.py` diff empty. No gate loosening, no live/paper trading,
no Mode B, no ML.

---

## 1. Question and pre-registered kill criteria

The product 6m book is thin (~30 armed → 10 routes → 4 placed → 3 fills). The question:
did placement / session / R7 (and peers) kill paths that **would have been good** under the
frozen fill semantics, or paths that were **already bad**?

Kill criteria, frozen before the run (proof register §B3):

- untaken paper outcomes **≈ or worse than** placed outcomes → stop attributing scarcity to
  placement gates; pivot weight to entry/representation;
- untaken outcomes **systematically better** → placement is a bottleneck **candidate** for a
  later dated ruling (no automatic change);
- the frozen decision rule (`evaluate_kill_criteria`, stated before running): no untaken →
  INCONCLUSIVE; **0 resolved untaken paths → PLACEMENT_NOT_PRIMARY** (a gate can only cost
  something if the path it removed would have filled *and* won); otherwise a resolved
  contrast needs n ≥ 5 resolved untaken rows and compares TP-hit rates against control.

## 2. Method (frozen before running)

| Item | Value |
|---|---|
| Window | M1 warm-up from **2025-05-01**; exec **2025-06-01 → 2025-11-30** M5 (35,725 bars) — the frozen product 6m window |
| Composition | `phase3_structure_funnel.run` **imported, not forked**, with the pilot's explicit `CostConfig` (commission 0.0 / slippage 1 pt / half-spread on / fallback 0.26) — identical to the frozen 6m refresh |
| Capture seam | logging-only class wraps, restored in `finally`: `BacktestRunner.__init__` (keeps the runner instance), `BacktestRunner._process_entries` (candidate geometry + `blocked_log` delta, order-preserving), `PendingOrderBook.place` (every accepted placement). Production modules untouched |
| Fill semantics | touch = fill **at the limit price** (inclusive), mirrored from `smc.backtest.fill_model` and test-cross-checked against it |
| Eligibility | placement runs at runner step 6 (after fills) → the placement bar is **never** fill-eligible: eligible bars are `present_bar+1 .. present_bar+rest_bars-2`, `rest_bars = rest_bars_for(detection_tf, is_m8, M5)` — **the route's own R8/§23 lifetime, one rule for all rows** |
| Anchor | placed rows: the ACTUAL `placed_bar` with the order's own lifetime; unplaced/blocked rows: the route's **first presentation bar** (blocks are retryable — one route is presented on many bars). Both disclosed, one rule each |
| Resolution | once filled, the path resolves over the series with the frozen same-bar rule (**SL before TP**, inclusive touches) and no holding cap |
| Labels (exclusive) | `TP_HIT` / `SL_HIT` / `EXPIRED_NO_FILL` / `DATA_GAP` (+ documented extension `OPEN_UNRESOLVED` — a filled path still live at series end is never folded into a win or a loss). Missing entry/SL/TP → `DATA_GAP`, never invented |
| Costs | **gross path labels only** in the primary pass (no cost model) — disclosed |
| BE stop | **NOT modelled** (PureRunner BE needs live risk state). Quantified against the control arm's real exits instead of invented — see §5.1 |
| Secondary pass | a disclosed **100-M5-bar** horizon (Track-B `H_PATH`) answering FR-4b's near-miss class: "touched, but not inside the lifetime the product would have granted" |

Script: `06_RESEARCH/scripts/near_miss_counterfactual.py` (`--analyze-only` re-reads the
saved capture, so the tables reproduce without rerunning the ~15-minute capture).

## 3. Integrity (the seam changed nothing)

| Check | Result |
|---|---|
| `trades.csv` vs frozen `run1` | **byte-identical** (SHA-256 `05a848120b6feeae…`) |
| `report.json` vs frozen `run1` | **byte-identical** |
| routes captured vs funnel | **10 / 10** |
| placements captured vs funnel | **4 / 4** |
| blocked-log events | **18** = `session 4` + `skip_place_far_from_zone 14` — exactly the frozen `report.json → blocked_by_reason` |
| control fills reproduced by the paper engine | **3 / 3** (engine fill bar == actual `entry_bar` on every control row) |

The control arms' eligible windows: `poi-014146` placed 5658 → filled 5659 (window 5659–5699);
`poi-047805` placed 18278 → filled 18296 (window 18279–18324); `poi-073511` placed 27584 →
filled 27585 (window 27585–27588, an intent-inherited 6-bar life).

## 4. Candidate census — all 10 routes (deduped by `route_id`)

| route_id | arm | trig / TF | entry | SL | TP | lifetime | presentations | first block |
|---|---|---|---|---|---|---|---|---|
| poi-014146:F@5653 | filled_control | F / D1 · M8 | 3281.298 | 3310.403 | 3271.862 | 43 (intent) | 2 | R7 far ×2 |
| poi-047805:C@18278 | filled_control | C / H4 · M8 | 3490.257 | 3493.985 | 3486.405 | 48 | 1 | — |
| poi-073511:F@27542 | filled_control | F / D1 · M8 | 4244.725 | 4177.035 | 4275.664 | 6 (intent) | 2 | R7 far ×2 |
| poi-034151:F@13349 | placed_unfilled | F / H4 · M8 | 3376.625 | 3373.416 | 3380.275 | 34 (intent) | 2 | R7 far ×2 |
| poi-079448:F@29701 | blocked_session | F / H4 · M8 | 4043.618 | 4157.473 | 3953.735 | 48 | 2 | session ×2 |
| poi-088517:F@32994 | blocked_session | F / H1 · M8 | 4158.685 | 4213.287 | 4095.449 | 48 | 2 | session ×2 |
| poi-008541:F@3427 | blocked_r7_far | F / H4 · M8 | 3404.848 | 3410.343 | 3385.348 | 48 | 2 | R7 far ×2 |
| poi-022254:F@8840 | blocked_r7_far | F / H4 · M8 | 3332.625 | 3331.112 | 3334.865 | 48 | 2 | R7 far ×2 |
| poi-068169:F@25650 | blocked_r7_far | F / D1 · M8 | 3920.485 | 3882.138 | 4034.098 | 48 | 2 | R7 far ×2 |
| poi-068170:F@25650 | blocked_r7_far | F / D1 · M8 | 3995.775 | 3960.445 | 4034.098 | 48 | 2 | R7 far ×2 |

Arm census: **control 3 · placed_unfilled 1 · blocked_session 2 · blocked_r7_far 4 ·
blocked_other 0** = 10 ✓. Every route is M8-tagged and trigger F except the one C route
(consistent with the register's F-06 texture — listed, not promoted).

**R9 already granted every R7-skipped route a full deferred clock:** 7 intents armed, 3
eventually placed, **4 expired with no re-entry** (`poi-008541`, `poi-022254`, `poi-068169`,
`poi-068170`) — i.e. the product itself already asked "would it have filled?" for the R7
population and answered *no* for 4 of 7 (before this study exists).

## 5. Outcome tables

### 5.1 Control arm — the 3 real fills (calibration, not edge)

| route_id | raw engine | actual product exit | fills reproduced | MFE_R / MAE_R (raw) | bars to outcome |
|---|---|---|---|---|---|
| poi-014146:F@5653 | SL_HIT | SL_HIT (`stop_loss`) | ✓ | 0.12 / 1.14 | 117 |
| poi-047805:C@18278 | TP_HIT | TP_HIT (`take_profit`) | ✓ | 2.03 / 0.82 | 1 |
| poi-073511:F@27542 | TP_HIT | SL_HIT (`stop_loss`, BE) | ✓ | 0.51 / 0.35 | 73 |

Raw mix TP 2 / SL 1; actual mix TP 1 / SL 2; **divergence 1/3, fully explained**:
`poi-073511` was closed by the PureRunner **BE stop** (the frozen rule moves the stop to
break-even), which the paper engine does not model — it correctly saw the ORIGINAL stop
never tagged and the TP tagged later. Consequence, stated plainly: **raw `TP_HIT` is an
upper bound on favourable outcomes for the untaken rows too**; a BE stop can convert a
would-be TP into a scratch. This is why the verdict below rests on *whether the untaken
paths could be taken at all*, not on their raw win rate.

### 5.2 Untaken arm — 7 routes

| route_id | arm | outcome | closest approach while live | touched at all (100-bar probe) | 100-bar outcome |
|---|---|---|---|---|---|
| poi-034151:F@13349 | placed_unfilled | EXPIRED_NO_FILL | **0.744** | no | EXPIRED_NO_FILL |
| poi-022254:F@8840 | blocked_r7_far | EXPIRED_NO_FILL | 2.823 | **yes — 42 bars after the lifetime ended** | **TP_HIT** |
| poi-008541:F@3427 | blocked_r7_far | EXPIRED_NO_FILL | 16.643 | no | EXPIRED_NO_FILL |
| poi-068170:F@25650 | blocked_r7_far | EXPIRED_NO_FILL | 26.590 | no | EXPIRED_NO_FILL |
| poi-088517:F@32994 | blocked_session | EXPIRED_NO_FILL | 52.390 | no | EXPIRED_NO_FILL |
| poi-079448:F@29701 | blocked_session | EXPIRED_NO_FILL | 77.403 | no | EXPIRED_NO_FILL |
| poi-068169:F@25650 | blocked_r7_far | EXPIRED_NO_FILL | 101.880 | no | EXPIRED_NO_FILL |

**Untaken outcome mix: `{EXPIRED_NO_FILL: 7}`** — resolved untaken paths **0**. Median
closest approach while live **26.59 price units** (~0.78% of price at ~3,400).

### 5.3 Extended 100-bar horizon (disclosed secondary pass)

`{EXPIRED_NO_FILL: 6, TP_HIT: 1}` — six of seven untaken routes never touch their own limit
even when granted 100 M5 bars (~8+ hours). One (`poi-022254`) is a genuine FR-4b-class
near-miss: it missed by **2.82 units while live** and first touched **42 bars after** its
48-bar clock ended, then ran to its TP.

## 6. Kill-criteria verdict

```
KILL_CRITERIA_VERDICT: PLACEMENT_NOT_PRIMARY
  n_control 3 (resolved 3, raw TP rate 0.667) | n_untaken 7 (resolved 0)
  untaken EXPIRED_NO_FILL rate 1.000, median closest approach 26.59
  reason: every untaken route never touched its own limit inside the product
          lifetime it would have been granted — the gates cut off no takeable path
```

**Reading — selection gap vs representation gap.** There is **no measurable selection gap
in the placement gates** on this window: session and R7 removed seven routes whose
zone-anchored limits the market never came back to touch, six of them not even within 100
bars. A gate that removes only untakeable paths costs nothing, and the R7 population
confirms it independently (the product's own R9 deferral already watched 4 of them die of
no-re-entry). What the numbers *do* point at is the **representation** side the owner plan
named: entries are zone-edge limits that sit far from post-impulse price (median gap ~26.6
units while live; the FR-4b/PHASE-R4 chase texture), so the binding constraint is the
entry's *representation of the setup*, not the placement window in front of it. One
lifetime-class exception exists and is named (`poi-022254` — a 48-bar clock cut a path that
a longer rest would have filled), which is a **lifetime/give-up** question for a later dated
ruling, **not** a R7/session gate question, and n = 1 here.

Per the pre-registered kill criteria: **stop attributing scarcity to the placement gates;
pivot weight to the entry-timing / entry-representation program.** No gate change is
proposed, and none is authorized by this note.

## 7. Research-instrument defect found (disclosed, not fixed here)

The frozen composition's `intents_expired` counter reads **0** on the 6m artifacts while the
run's own `IntentBook` recorded **4** real `intent_expired_no_reentry` transitions:
`phase3_structure_funnel.run` counts `by_kind.get("expired")` / `…("dropped_portfolio")`,
but the lifecycle events are named `intent_expired_no_reentry` and
`dropped_portfolio_{friday,news}`. `intents_armed` (7) and `intents_placed` (3) are correct,
so every published funnel line "intents armed 7 / placed 3 / **expired 0**" under-reports the
terminal lifetime facts. Not fixed in this task: the research script is frozen against
published artifacts, this is research instrumentation only (no `04_SRC` decision path), and
a fix should land as its own dated change with regenerated artifacts. Recorded as a residual
in `00_LOCKED/POST_V1_ACTIVE_TODO.md`.

## 8. Limitations (binding on any reuse)

- **n = 7 untaken / 3 control** — a census of one 6m window, one instrument, one feed. No
  confidence interval exists at this n; nothing here is a rate, an expectancy, or an edge.
- **Block events are 18; routes are 10** — blocks are retryable by design, so the
  route-level table is the honest denominator (census reported both).
- **BE stop and the cost ledger are out of the primary pass** (disclosed above); raw labels
  are gross-path upper bounds on the favourable side, and raw `TP_HIT` is not a P/L claim.
- **Fridays/portfolio events** could have closed a counterfactual position in the product
  even where the raw path shows no SL/TP tag; the untaken rows never filled, so this touches
  nothing here (it would matter for any future filled-path reuse).
- **Reconstruction, not replay**: the paper engine mirrors the frozen rules and is
  test-cross-checked against `fill_model`, and it reproduces the control fills 3/3 — it is
  still a reconstruction, not the runner.
- The 100-bar extended pass is a **disclosed sensitivity**, never the primary table, and
  must not be mined for thresholds.

## 9. Artifacts, governance, NEXT

- Script: `06_RESEARCH/scripts/near_miss_counterfactual.py` (imports the frozen composition
  + the pilot's cost config; forks nothing).
- Results (local-only, gitignored): `06_RESEARCH/results/near_miss_counterfactual/` —
  `candidates.csv` (10 rows), `outcomes.csv` (10 rows, primary + 100-bar columns),
  `summary.json` (banner, method, integrity, control checks, mixes, texture, verdict),
  `events.json` (the raw capture: candidates, placements, blocked log, intent lifecycle),
  `capture/` (the run's own funnel/trades/report artifacts), `BANNER.txt` (the
  `DIAGNOSTIC — NOT EDGE` stamp for the whole artifact set — every research CSV in this
  repo is a banner-free data table by convention, banner in the note/summary, so the
  stamp is carried once per directory rather than injected as a CSV comment line).
- Tests: `04_SRC/tests/test_near_miss_counterfactual.py` (27: fill-model agreement,
  eligible-window arithmetic, no-fill-on-placement-bar, SL-before-TP incl. same-bar,
  `SL_THEN_TP`, MFE/MAE in R, DATA_GAP discipline, label exclusivity, arm priority,
  kill-criteria branches, banner/logic lock). Suite **1039 passed**.
- Determinism: the capture is byte-identical to the frozen 6m run (§3) and the analysis is
  a pure function of the saved capture — re-running `--analyze-only` reproduces
  `candidates.csv` / `outcomes.csv` / `summary.json` **byte-identically**
  (`candidates.csv` `f7243c50e4b69970…`, `outcomes.csv` `31d92061ed286885…`,
  `summary.json` `ef637f8d10a3ed64…`).

```
NEAR_MISS_STATUS: PASS
WINDOW: 2025-06-01 -> 2025-11-30 M5 (35,725 bars; M1 warm-up from 2025-05-01)
N_FILLED_CONTROL: 3
N_ROUTED_UNPLACED: 6 (routed, never placed: blocked_session 2 + blocked_r7_far 4)
N_BLOCKED: 6 routes (18 block events: session 4 + R7 far 14; +1 placed_unfilled route = 7 untaken)
OUTCOME_MIX_CONTROL: {TP_HIT: 2, SL_HIT: 1} raw engine | actual {TP_HIT: 1, SL_HIT: 2} (BE divergence 1/3)
OUTCOME_MIX_UNPLACED: {EXPIRED_NO_FILL: 7}
OUTCOME_MIX_BLOCKED: {EXPIRED_NO_FILL: 6} (session 2 + R7 4); extended 100-bar adds 1 TP_HIT
KILL_CRITERIA_VERDICT: PLACEMENT_NOT_PRIMARY
NOTE_PATH: 06_RESEARCH/NEAR_MISS_COUNTERFACTUAL_NOTE.md
SUITE: 1039 passed
LOCKED_CONSTANTS_DIFF: empty
LOGIC_CHANGED: NO
HANDOFF_UPDATED: YES
NEXT_READY: coincidence count | entry-representation focus | Architect review
```
