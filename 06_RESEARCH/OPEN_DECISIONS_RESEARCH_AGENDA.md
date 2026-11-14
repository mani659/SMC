# OPEN-DECISIONS RESEARCH AGENDA (O1–O5)

**Date:** 2026-11-14 · **Status:** ACTIVE · **LOGIC_CHANGED: NO** (docs only)
**Authority:** `EXPERT_MASTER_CARD.md`, `EXPERT_AMENDMENT_LIST_2026-11-12.md`,
`LOCKED_DECISIONS.md` §0 / §4b / §21b / §25, `POST_C2_DIAGNOSTIC_REPORT.md`,
`C3_IN_BETWEEN_GATE_NOTE.md`.
**Standing Architect rule:** subjective chart knowledge → measured options →
hard boundaries. No gate flips from taste, and no gate flips from small-n PnL.

---

## 1. Purpose

The Mode A story is now fixed and shipped: **HTF zone → LTF trigger completes
inside the zone (C3) → risk shell → SL (ATR buffer) / TP (first valid swing)**.
C2a (Rule 3 research-only), C3 (in-between required) and C2b (color-free D/S)
closed the questions that were answerable from the signed card alone.

Five questions remain that the card cannot settle from principle — each needs a
measurement before any product boundary moves. This register fixes, per
question: what is asked, what data answers it, and what result would authorise a
lock. Nothing here is an implementation plan, and nothing here is a promise that
a change will be made.

*(Mode A = the current in-between entry story. Mode B is explicitly out of scope.)*

---

## 2. Standing constraints (non-negotiable during research)

1. **C3 in-between remains REQUIRED.** No pack may treat an out-of-zone
   completion as valid. An alternate path may only arrive later via a dated
   design + measurement lock that names it explicitly — never by widening the
   gate or reinterpreting "inside".
2. **C2a stands:** CHOCH Rule 3 is research-only and must never route.
3. **C2b stands:** D/S/OB identification stays color-free; width stays the
   single origin candle.
4. **Product diagnostics use the full detection set** `(D1, H4, H1, M15)` via
   `06_RESEARCH/scripts/lib/product_htf_series.py`. A funnel with an incomplete
   HTF map is not evidence.
5. **Small-n PnL is never a lock criterion.** Counts, identity, path geometry
   and reject anatomy are; "it made money in October" is not.
6. No new numeric threshold is introduced or presented as locked by any pack.
7. Frozen windows, declared before running; no re-running with tuned params.

---

## 3. Decision register

### O1 — Boundary anatomy of C3 rejects

| Field | Content |
|---|---|
| **ID** | O1 |
| **Title** | Boundary anatomy / C3 reject taxonomy |
| **Question** | Are `not_in_between` rejects mostly far-from-zone noise, or edge/boundary interactions that a *separate* boundary-sweep path might legitimately catch? |
| **Why it matters** | In the October diagnostic **137 of 149** routes were rejected by C3 (92%) — the single largest filter in the product. If most rejects are far-away noise, C3 is doing its job and nothing else is needed. If a meaningful share are boundary interactions (close just outside an edge, wick-only touch), the boundary-sweep fallback stops being hypothetical. |
| **Current product behavior** | C3 rejects any completion whose bar **close** is outside the zone's inclusive `[bottom, top]` (`smc/triggers/in_between.py`, token `not_in_between`). No boundary-sweep emitter exists; §25 records the fallback as design-only. |
| **Evidence sources** | `06_RESEARCH/results/post_c2_diagnostic/summary.json` (probe counters); a new pack under `06_RESEARCH/results/open_decisions/o1_*/`; per-reject geometry from the adapter (`zone.bottom/top`, completion close, ATR at completion, direction, trigger, POI tags). |
| **Method (outline)** | Re-run the frozen October window (dual run) with a read-only probe that records, per reject: signed distance from the nearest edge in **ATR units**, which edge, trigger letter, M8 kind, whether the completion bar wicked the zone, and bars since the POI armed. Bucket by distance (e.g. exact edge, ≤0.25 ATR, ≤0.5 ATR, >0.5 ATR); no bucketing thresholds become product rules. |
| **Metrics** | Reject count and share by distance bucket; edge (proximal vs distal vs far side); trigger mix; share whose bar **range** overlaps the zone while the close does not; share where the *entry limit* was inside the zone; armed→reject latency. |
| **Lock criteria** | **Keep status quo (no new path)** if far/never-touched rejects dominate and edge-adjacent rejects are a negligible share. **Open a boundary-sweep design** only if a material share are repeatable boundary interactions with a definable, measurable trigger condition — and then only as a **dated design** with its own gate, never as a widened C3. **Reject** any proposal that relaxes the in-between definition itself. |
| **Non-goals** | No boundary-sweep code, no C3 edit, no ATR tolerance added to the gate, no threshold chosen from the histogram, no PnL ranking. |
| **Status** | **CLOSED — KEEP_STATUS_QUO** (Architect reading, 2026-11-14); evidence `06_RESEARCH/OPEN_DECISION_O1_C3_BOUNDARY_ANATOMY.md` |
| **Suggested order** | 1st |

### O2 — HTF sweep as a hard stage vs upstream-only context

| Field | Content |
|---|---|
| **ID** | O2 |
| **Title** | HTF sweep requirement |
| **Question** | Must the *same* POI show a clear HTF sweep before the LTF seek, or is displacement / pillar context enough? |
| **Why it matters** | The card makes the sweep part of the story ("sweep of a pool is part of that story, not the trade") but Stage 2's five pillars contain **no sweep pillar**. If sweep-poor POIs behave materially worse on path quality, a hard stage might be justified; if not, adding one would silently narrow the product. |
| **Current product behavior** | Sweep is **upstream/contextual**: Stage 0 liquidity MAP + `sweep_level` plumbing exists but no trigger emits a sweep level, and the sweep guard is dormant. Pillars are Refinement / Displacement / Dealing Range / Freshness / Inducement — verified: no sweep gate in `PipelineEngine.validate`. M8/menu episodes do carry a sweep timestamp for window bookkeeping. |
| **Evidence sources** | `phase3_structure_funnel` batches; per-armed-POI sweep attribution (nearest sweep before arm per TF, distance in ATR); `06_RESEARCH/results/open_decisions/o2_*/`. |
| **Method (outline)** | Frozen October window (dual run) with a read-only classifier of each armed POI: (a) same-TF sweep within N bars before arming, (b) other-TF sweep, (c) none. Join to route/reject/fill outcomes and to MFE/MAE in ATR (path only, no expectancy claim). |
| **Metrics** | Share of armed POIs by sweep class; route rate; C3 reject rate; fill rate; path MFE/MAE distribution per class; sample sizes printed alongside every rate. |
| **Lock criteria** | **Keep upstream-only** unless sweep-poor POIs are consistently and materially worse across both a route-rate and a path metric, with sufficient n. **Adopt a hard stage** only via a dated design that names the sweep definition, the TF it is measured on, and the failure behaviour — and only if the same measurement reproduces on a second window. |
| **Non-goals** | No sweep-emitter implementation, no new pillar, no chart-taste sweep definition, no expectancy claim from MFE/MAE. |
| **Status** | **CLOSED — KEEP_UPSTREAM_ONLY** (Architect, 2026-11-14); evidence `06_RESEARCH/OPEN_DECISION_O2_HTF_SWEEP_STAGE.md` |
| **Suggested order** | 2nd |

### O3 — Multi-zone priority when D1/H4/H1/M15 overlap or conflict

| Field | Content |
|---|---|
| **ID** | O3 |
| **Title** | Overlapping multi-TF zones |
| **Question** | When D1 / H4 / H1 / M15 zones overlap or conflict, what should win — first-armed, highest TF, tightest zone, or all-as-equal-tags? |
| **Why it matters** | With M15 in the inventory set (`§4b`), overlap is now common (October: 441 armed, 242 M8, duplicates suppressed 586). Today the winner is an accident of batch order, not a stated rule. |
| **Current product behavior** | `ZoneDedup` treats **same-direction overlapping spans as one episode** (first registration owns the key, owner retired when the episode dies); different directions on the same geometry collapse in M8's episode collapse. There is **no TF priority rule** — the first batch to arm wins, and POIs from different TFs coexist when they do not overlap. |
| **Evidence sources** | `multi_tf_runtime.ZoneDedup` counters (`retired_total`, duplicates); `duplicates_suppressed` and `armed_by_tf` from the funnel summary; overlap map from the arbiter candidates in `06_RESEARCH/results/open_decisions/o3_*/`. |
| **Method (outline)** | Frozen window; for each geometric episode cluster record: TFs represented, which armed, which were suppressed, then the route/C3/fill outcome of the armed one. Compare counterfactual "highest TF wins" / "tightest zone wins" offline (no runtime change) on the same clusters. |
| **Metrics** | Overlap-cluster count by TF set; share where the armed member differs from a candidate rule; outcome difference by rule; suppressed-member counterfactuals (would it have routed / been rejected). |
| **Lock criteria** | **Keep first-armed** if cluster outcomes are indistinguishable across rules or n is too small to separate them. **Adopt a rule** only if one rule is consistently better on route validity *and* reject anatomy, is expressible in one sentence, and does not change the five-pillar or chronological-trigger rules. |
| **Non-goals** | No dedup redesign inside a pack, no TF scoring model, no removal of equal-tag confluence, no PnL-based ranking. |
| **Status** | **CLOSED — KEEP_FIRST_ARMED_STATUS_QUO** (Architect, 2026-11-14); evidence `06_RESEARCH/OPEN_DECISION_O3_MULTI_ZONE_PRIORITY.md` |
| **Suggested order** | 3rd |

### O4 — SL policy vs the expert ~30-pip benchmark

| Field | Content |
|---|---|
| **ID** | O4 |
| **Title** | Stop distance: ATR buffer vs 30-pip MAE benchmark |
| **Question** | Does the shipped ATR-buffer stop sit materially worse than the expert's ~30-pip reference on realised paths, and would a pinned-distance stop reduce avoidable stop-outs without changing entry validity? |
| **Why it matters** | The card keeps the ATR buffer as product and calls 30 pips a MAE/review benchmark. If the buffer routinely produces stops far outside the benchmark on trades that then travel favourably, that is a documented gap worth measuring — but only ever as a measurement until a dated lock. |
| **Current product behavior** | SL = structural reference ± `FR2_SL_BUFFER_ATR` × ATR (interim constant, not frozen); 30 pips and 2–5 pips are benchmarks only (`§21b`). No pinned-pip stop exists in product. |
| **Evidence sources** | Trade records (`trades.csv`: `sl_price`, `entry_price`, `close_kind`, `signal_data_json`), MAE per trade from the bar loop, `06_RESEARCH/results/open_decisions/o4_*/`. |
| **Method (outline)** | Frozen window (dual run); per trade compute stop distance in pips and ATR multiples, MAE before exit in the same units, and how many stop-outs had MAE beyond the benchmark. Path study only — no re-entry simulation, no re-pricing. |
| **Metrics** | Stop distance distribution (pips, ATR multiples); share of trades with stop > benchmark; share of stop-outs whose MAE exceeded the benchmark; MFE before stop; n printed with every share. |
| **Lock criteria** | **Keep ATR buffer** unless a benchmark-distance analysis shows a consistent, reproducible pattern with enough n to state a rule — and any change would still require a dated design naming when the pinned distance applies (never a blanket replacement). **Reject** any change whose only support is small-n PnL. |
| **Non-goals** | No threshold tuning, no per-trade optimiser, no expectancy claims, no touching `FR2_*` constants inside the pack. |
| **Status** | **MEASURED — pending Architect** (2026-11-14); pack `06_RESEARCH/OPEN_DECISION_O4_SL_MAE_BENCHMARK.md`, measurement reading KEEP_ATR_PRODUCT |
| **Suggested order** | 4th |

### O5 — TP: structural first-valid-swing vs 4×ATR fallback

| Field | Content |
|---|---|
| **ID** | O5 |
| **Title** | TP source availability and path quality |
| **Question** | How often is a structural TP available, and do structural-TP trades have different path quality than ATR-fallback trades? |
| **Why it matters** | Product TP is "first valid swing only", with the 4×ATR fallback when no swing qualifies. October's candidates were **9 structural / 3 fallback** — far too small to conclude anything, but the split is now observable. No forced 1:5 ESSENCE lock is proposed. |
| **Current product behavior** | `candidate_from_route` → `structural_tp_target` (first §19-confirmed swing on the place-time prefix, ≥0.25 ATR beyond entry) else 4×ATR fallback; `tp_source` is exported per candidate. |
| **Evidence sources** | `summary.json` probe `tp_source_mix`, `trades.csv` `tp_price`/`tp_source`, `06_RESEARCH/results/open_decisions/o5_*/`. |
| **Method (outline)** | Frozen window, ideally widened once to a documented longer window for sample size (declared before running); split trades by `tp_source`; report availability rate and path measures. No target re-optimisation. |
| **Metrics** | Structural availability rate; TP distance in ATR; time-to-TP; MFE/MAE per source; share of fallback trades where a structural swing existed *after* the decision bar (lookahead audit, not a proposal). |
| **Lock criteria** | **Keep the current rule** (structural first, fallback otherwise) unless a reproducible measurement shows the structural branch is systematically wrong-sided or the fallback is demonstrably better on path quality. A 1:5 ratio is **not** a lock candidate from this pack. |
| **Non-goals** | No new TP model, no ratio hunting, no ESSENCE 1:5 enforcement, no use of future bars as targets. |
| **Status** | OPEN |
| **Suggested order** | 4th (parallel with O4) |

---

## 4. Execution order

**O1 → O2 → O3 → O4/O5.** O1 first because C3 is the largest single filter in the
product (92% of October routes) and its reject anatomy determines whether the
boundary-sweep question is real at all. O2 then asks whether the story's sweep
stage deserves hard status before we spend effort on zone priority (O3), which
only matters once the admission set is settled. O4 and O5 are path/geometry
questions that can run in parallel afterwards and need the longest windows for
usable n.

---

## 5. Artifact conventions for future packs

- Results: `06_RESEARCH/results/open_decisions/o{N}_{topic}/run{1,2}/` + `summary.json`
  (results tree is gitignored; force-add only what a report cites).
- Reports: `06_RESEARCH/OPEN_DECISION_O{N}_{TOPIC}.md`, each ending with a return
  block and an explicit **lock recommendation** (`KEEP` / `OPEN DESIGN` /
  `REJECT`) — never a silent change.
- Dual run whenever a path is stochastic or export-based; byte-check the exports.
- Product-path packs must use `06_RESEARCH/scripts/lib/product_htf_series.py`
  (full `(D1,H4,H1,M15)` set).
- `LOGIC_CHANGED: NO` for every pack; a change is only ever a later, dated
  product lock with its own engagement.
- Every rate ships with its numerator/denominator; small-n results are labelled
  as such in the same sentence.

---

## 6. Explicitly out of agenda

Mode B, Monte-Carlo expectancy studies, re-enabling Rule 3, reopening color-coded
D/S, lot sizing from confluence score, boundary-sweep implementation, and any
threshold tuning exercise. If a future pack drifts into these, it is out of
scope and must be re-authorised.

---

## 7. Return block

```text
AGENDA_STATUS: PASS
PATH: 06_RESEARCH/OPEN_DECISIONS_RESEARCH_AGENDA.md
DECISIONS: O1 O2 O3 O4 O5
ALL_OPEN: YES
FIRST_UP: O1
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
SRC_DIFF: empty
HANDOFF_UPDATED: YES
NEXT_READY: O1 C3 reject / boundary anatomy measurement pack
```
