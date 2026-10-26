# EPISODE STORE — UNIFIED EPISODE OBJECT + LIFECYCLE (DESIGN LOCK)

**Status:** **DESIGN_LOCKED — pending Lead Architect acceptance before ANY code.** No production file changes in this task; nothing below runs today.
**Date:** 2026-10-13 · **Authority:** Lead Architect owner plan `00_LOCKED/OWNER_PLAN_MULTI_TF_TRANSLATION_2026-10-13.md` §6 **step 3**, entered after the two measurements that precede it: near-miss **PLACEMENT_NOT_PRIMARY** (`06_RESEARCH/NEAR_MISS_COUNTERFACTUAL_NOTE.md`) and coincidence **COINCIDENCE_MASS_PRESENT** (`06_RESEARCH/COINCIDENCE_COUNT_NOTE.md`).
**Composes with (does not supersede):** `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` (one-driver rule), `00_LOCKED/R9_PLACE_ON_REENTRY_DESIGN.md` (intent lifecycle, quoted verbatim as state names), `06_RESEARCH/SEEK_SCAN_CONTRACT_REDESIGN_DESIGN.md` §3 (Option B seek posture, as implemented), `LOCKED_DECISIONS` §5/§5a/§11/§23/§24, and register `06_RESEARCH/RESEARCH_PROOF_REGISTER_2026-10.md` **F-01 / F-04 / F-08**.
**`LOGIC_CHANGED: NO`** · `locked_constants.py` untouched · no gate, threshold, trigger, pillar or routing change.

---

## 1. Status, authority and non-goals

- **What this is:** engineering infrastructure for *measurement* and for a future admission rule — one queryable episode chain (thesis → validation → arm → sweep → LTF proof → route / block / fill → expiry), so studies stop re-deriving joins and the product stops losing its own memory (register F-08).
- **What this is NOT (binding):** no trading edge claim; no routing change; no pillar/trigger/TP/SL change; no gate or window widening of any kind; no `locked_constants.py` edit; no Mode B; no ML; no Redis/event-bus/distributed state in V1 (the product contract's §4 non-goal stands).
- **Acceptance gate:** the Architect accepts this document, then a separate dated implementation prompt is issued. Until then the store exists only on paper — **do not implement it in this engagement**.
- **Phase-1 constraint that keeps this safe:** in its first implementation the store is **observability-only** — every existing decision path (validation, dedup, arm, seek, risk, placement, exits) stays the decision-maker, and the frozen product run must remain byte-identical with the store switched on (§7, §8.8). A store write that could change a decision is out of scope by definition.

## 2. Problem statement (evidence-cited)

The product's memory of one episode is spread across **six stores with six key spaces**, none of which can answer "what happened to this HTF thesis?":

| # | Store | File | Holds | Keyed by |
|---|---|---|---|---|
| 1 | `POIStateMachine._states` | `smc/validation/state_machine.py` | §5 freshness (CREATED → FRESH → TESTED/VIOLATED, terminal) | `poi.id` (uuid4) |
| 2 | `ZoneDedup._zones` | `smc/orchestration/multi_tf_runtime.py` | geometric episode dedup (same direction + overlapping span, 6 dp) | list of rounded tuples |
| 3 | `PipelineEngine._episodes` / `_armed_order` | `smc/orchestration/engine.py` | `_PoiEpisode`: `arm_bar`, `posture` (SeekPosture), `arm_candle_ts`, `revalidated_bar`, `fired`, `outcome` | `poi.id` |
| 4 | `PipelineAdapter._workflows` / `_routed` / `_tested_bar` / `_scan_cursor` | `smc/backtest/pipeline_adapter.py` | route workflow, §11 one-shot, touch bookkeeping, scan cursor | `poi.id` |
| 5 | `IntentBook._intents` + `events` | `smc/backtest/intents.py` | R9 deferred placements and their lifecycle | `route_id` (fallback `poi_id\|trigger`) |
| 6 | `PendingOrderBook` / positions / risk latches | `smc/backtest/orders.py`, `positions.py`, `smc/risk/*` | resting limits, fills, BE latches | order ticket / `poi_id` |

**Measured cost of the fragmentation (all cited, no new claims):**

1. **Register F-08 (engineer-verified):** 889 raw H4 detections → 75 episodes; **1,991** dedup suppressions in the frozen 6 m run; 40× byte-identical rows in the verify books; "no persistent zone object, no lifecycle".
2. **Study cost, three times in one program:** research joins were re-derived by hand and each time produced a defect — float-vs-string identity in the 474 decomposition, aliased detector lists plus a first-touch offset stuck at 0 in the post-sweep catalog, and an arm-bar anchoring error caught mid-build in the near-miss study. Every one of those is a symptom of "no episode object", not of the analyst.
3. **A real counter defect (logged, unfixed):** `IntentBook` emits `intent_expired_no_reentry` / `dropped_portfolio_{friday,news}` while the composition counted `by_kind.get("expired")` — so every published funnel line reads *intents armed 7 / placed 3 / **expired 0*** while the run recorded **4** real terminal transitions (`POST_V1_ACTIVE_TODO.md`, exposed by the near-miss study). Two vocabularies, one reader, silently wrong.
4. **Logging that does not exist:** the 474 decomposition had to bucket `C4-scanned-no-route-unspecified` (5 rows) as "below log resolution", and no per-POI validation/arm log exists anywhere — which is why the coincidence study's `product_fate` had to be an artifact-derived approximation rather than a fact. 208 of its 250 unarmed coincidences sit on geometry the accepted packs already contain (**validated elsewhere, never armed here**) — a question the product cannot currently answer about itself.
5. **Identity is contested (register F-01):** A4 scoring found SAME 0, REFINEMENT ≈ 82 %, DIFFERENT ≈ 16 % — the armed box is usually a *tighter version of the same thesis*, not a different one. Any store that keys on `poi.id` (uuid4) or on exact-bound equality silently destroys that distinction; any store that keys on overlap alone silently fuses genuinely different zones.

6. **Latency is structural (register F-04), so the arm-bar facts must be first-class.** First touch and violation land on the arm bar itself (199/199 and 62/62 under the old contract), 72 confirmations arrive after the give-up deadline, 25 scans start after the confirmation. Those are *episode* facts — posture, first-touch time, confirmation time relative to the deadline — and every study so far had to reconstruct them from M5 bars by hand (the near-miss study's arm-bar anchoring bug was exactly this reconstruction). The store records them once, at the source.

**Conclusion (the design premise):** the missing object is not another detector or another gate — it is **one addressable episode with an append-only history**, whose identity rule is stated, whose states are named once, and whose counts are *derived from its own events* (so the `expired 0` class of error becomes structurally impossible).

## 3. Episode identity (NORMATIVE)

**3.1 Primary grain (proposed).** An episode's identity is **geometric and directional**:

```
identity = (direction, detection_tf, m8_kind_class, [zone_low, zone_high] under overlap-equivalence)
```

where

- `direction` ∈ {LONG, SHORT};
- `detection_tf` is the TF that produced the POI (H4 / H1 / D1-via-M8 / W1-via-M8) — the census groups H4 and M8-H4 separately and the store keeps them distinct (open question Q1);
- `m8_kind_class` ∈ {ob, demand_supply, fvg, n/a} — the M8 facet, `n/a` for registry POIs (M1–M7), matching `make_trigger_poi`'s composite;
- **sameness is overlap, not equality**: two same-direction, same-TF, same-kind zones whose spans overlap are **one episode** — exactly the shipped `ZoneDedup.seen()` rule (military-grade precedent: this is what already decides arm-once in production, in every run, live included);
- bounds are canonicalised at the existing **6 dp** rounding used by `ZoneDedup.register`, and the episode keeps both the **current bounds** and a `bounds_history` of the distinct boxes seen (so refinement is data, not identity churn).

**3.2 Explicit downsizing of the alternatives (what is NOT identity).**

- `poi.id` (uuid4) is **an attribute of an arm event, never identity** — it differs between runs for the same zone (research had to patch `uuid4` to a counter to get stable ids; that patch must become unnecessary).
- `route_id` (`"POI:trigger@bar"`, §11) is a **route identity**, i.e. a *child* of the episode. It is never allowed to stand in for an episode (the coincidence and near-miss studies both had to collapse routes back to `poi_id` by hand).
- Trigger letter, session, posture, `arm_bar`, wall-clock timestamps: attributes/events, never identity.
- **Float-formatted strings**: cross-artifact joins must use exact floats plus the documented 6 dp canonical key, never `str(float)`.

**3.3 Refinement policy (the A4 fact, made mechanical).** An armed POI whose box sits **inside** a census parent's box (`containment`) is a **REFINEMENT of the same episode, not a new one**:

- the episode keeps one identity; the arm event records `refinement = {parent_bounds, refined_bounds, adopted_at_bar}`;
- **adopted bounds** for all later geometry (zone bands, re-entry, R7 place guard, FVG context) are the **refined** bounds from the arm bar onward — i.e. the store *describes* the product's existing behaviour (validation refines geometry); it never changes which bounds the product uses;
- an **exact** box (rounded 6 dp equality) records no refinement;
- a **non-overlapping** box is a **different episode** — the store must never fuse them, even when they share a POI id lineage or a trigger.
- This mirrors the A4 ruling already recorded (REFINEMENT ≈ same thesis) and the Step-4 join tiers (exact / containment / none), so the store's identity outcomes are cross-checkable against published artifacts (§8.6).

**3.4 Merge authority (no second silent merge).** `ZoneDedup` remains the **single merge/arm-once authority**. The store does not implement a parallel merge: when `ZoneDedup` suppresses a re-detection, the store **appends a `redetected` fact** (batch, bounds, tags) to the **existing** episode rather than creating a second one. Consequence to state plainly: the 1,991 suppressions in the 6 m run become *facts attached to episodes*, not discarded records — the fragmentation becomes history.

## 4. Lifecycle states + transitions (NORMATIVE)

States below use the **product's existing vocabulary wherever it exists** (R9 intent statuses are quoted verbatim; §5 freshness stays §5 freshness). `posture` is the Option B seek posture (R1.2), implemented as engine bookkeeping — not a §5 state.

```
DETECTED ─┬─▶ REJECTED_PILLAR                     (terminal)
          └─▶ VALIDATED ─┬─▶ SUPPRESSED_DEDUP     (terminal — ZoneDedup decided)
                         └─▶ EXPIRED_UNARMED      (terminal — never offered to arming in-run)
                                      ...or...
                         └─▶ ARMED (posture: CLEAN_ARM | IN_ZONE_AT_ARM | VIOLATION_AT_ARM)
                               └─▶ SEEKING ─┬─▶ ROUTED
                                            ├─▶ SCAN_CLOSED   (give-up, terminal)
                                            └─▶ VIOLATED      (terminal)

SEEKING(VIOLATION_AT_ARM) ⇄ REVALIDATION   (listens from arm; routes only after a close
                                            back inside the zone — R2.3 market_reentered_zone)

ROUTED ─┬─▶ PLACED ─┬─▶ FILLED ─┬─▶ CLOSED_TP | CLOSED_SL | CLOSED_BE
        │           │           └─▶ CLOSED_PORTFOLIO | OPEN_UNRESOLVED
        │           └─▶ ORDER_EXPIRED   (§23/§24, terminal)
        ├─▶ INTENT_ARMED ─┬─▶ PLACED
        │                 ├─▶ INTENT_EXPIRED            (terminal)
        │                 ├─▶ INTENT_REPLACED           (terminal)
        │                 ├─▶ INTENT_DROPPED_POI        (terminal)
        │                 └─▶ INTENT_DROPPED_PORTFOLIO  (terminal)
        ├─▶ BLOCKED_RETRYABLE   (session / news / R7-skip — resubmitted next bar, nothing consumed)
        └─▶ BLOCKED_TERMINAL
```

**4.1 Normative state list** (minimum required; the prompt's list is mapped, not replaced):

`DETECTED` · `REJECTED_PILLAR` · `VALIDATED` · `SUPPRESSED_DEDUP` · `EXPIRED_UNARMED` · `ARMED` (carrying `posture`) · `SEEKING` · `REVALIDATION` · `ROUTED` · `BLOCKED_RETRYABLE` · `BLOCKED_TERMINAL` · `INTENT_ARMED` · `INTENT_EXPIRED` · `INTENT_REPLACED` · `INTENT_DROPPED_POI` · `INTENT_DROPPED_PORTFOLIO` · `PLACED` · `ORDER_EXPIRED` · `FILLED` · `CLOSED_TP` · `CLOSED_SL` · `CLOSED_BE` · `CLOSED_PORTFOLIO` · `OPEN_UNRESOLVED` · `SCAN_CLOSED` · `VIOLATED`.

**4.2 Terminal states** (no outgoing transition): `REJECTED_PILLAR`, `SUPPRESSED_DEDUP`, `EXPIRED_UNARMED`, `SCAN_CLOSED`, `VIOLATED`, every `INTENT_*` terminal, `ORDER_EXPIRED`, every `CLOSED_*`, `OPEN_UNRESOLVED` (terminal *for the run*, by the near-miss convention that a live path at series end is never folded into a win or a loss).

**4.3 Which transitions exist in code today vs which are new bookkeeping only** (this table is the honesty contract of the design):

| Transition | Today | Under this design |
|---|---|---|
| detected → VALIDATED / REJECTED_PILLAR | exists (`validate_multi` counts; `ValidationResult.first_failure`) | **same decision**, plus a per-episode event (closes the "no per-POI validation log" gap) |
| VALIDATED → SUPPRESSED_DEDUP | exists (`ZoneDedup`, arm-once) | same decision; recorded as an episode fact |
| VALIDATED → EXPIRED_UNARMED | **not represented anywhere** | new *bookkeeping* (no decision): an episode that was never offered to arming within the run |
| VALIDATED → ARMED (+posture) | exists (`engine.arm_at`, SeekPosture R1.2) | same decision, recorded |
| ARMED → SEEKING → ROUTED | exists (`adapter._may_route` + `router.scan`, §11 one-shot) | same decision, recorded |
| SEEKING → REVALIDATION → ROUTED | exists (Option B R2.3 `market_reentered_zone`, `revalidated_bar`) | same decision, recorded |
| SEEKING → VIOLATED / SCAN_CLOSED | exists (§5 `on_violation`; give-up backstop) | same decision, recorded |
| ROUTED → PLACED / BLOCKED_* | exists (runner risk verdict; `blocked_log` reasons) | same decision, recorded |
| ROUTED → INTENT_ARMED → … | exists (R9, statuses verbatim) | same decision, recorded; **counters derived, not hand-written** |
| PLACED → FILLED / ORDER_EXPIRED | exists (`PendingOrderBook`, §23/§24 expiry) | same decision, recorded |
| FILLED → CLOSED_* / OPEN_UNRESOLVED | exists (runner/positions; BE stop in PureRunner) | same decision, recorded |

**Nothing in this table is a new rule.** The only genuinely new objects are *facts about decisions the product already makes*.

## 5. Event log (append-only facts the store must accept)

Every state change is an **append-only event**. Required common fields: `episode_key`, `event`, `bar_index` (execution-TF bar), `ts` (bar timestamp, UTC), `tf` (context TF), and a typed payload. **No event may reference a bar later than the run's current bar** (no-lookahead is a store invariant, not a convention — §8.3).

Event vocabulary (V1):

`detected` (+bounds, tags, validation counts) · `redetected` (+batch, bounds) · `pillar_failed` (+pillar, reason) · `validated` (+score, pillar_path, disp_magnitude_atr, model_tags) · `arm_suppressed_dedup` · `armed` (+poi_id, bounds, refinement{present,parent_bounds,refined_bounds}) · `posture_classified` (+CLEAN_ARM|IN_ZONE_AT_ARM|VIOLATION_AT_ARM) · `sweep_linked` (+side, magnitude_atr, passed) · `seek_opened` (+arm_bar, horizon = `poi_give_up_bars()`) · `ltf_completion` (+trigger, completion_index) · `revalidated` (+bar) · `route_formed` (+route_id, trigger, direction, entry, sl, tp, tp_source, entry_anchor) · `blocked` (+reason: `session` | `skip_place_far_from_zone` | `news` | `spread` | …) · `intent_armed` / `intent_expired_no_reentry` / `intent_replaced` / `intent_dropped_poi` / `intent_dropped_portfolio` (R9 names verbatim) · `placed` (+ticket, limit, sl, tp, lots) · `order_expired` (+rule: §23 | §24, bars_open) · `filled` (+entry_bar, entry_price) · `closed` (+kind, exit_bar, exit_price, win, cost fields) · `violated` (+close, bar) · `gave_up` (+deadline_bar) · `pruned`.

**5.1 One vocabulary rule (the structural fix).** Event names, state names and counter names are declared **once** in the store and every reader (reports, CSV/JSON export, research scripts) reads them through those declarations. **Counters are derived by counting events** — never maintained as a second, hand-written tally. The `intent_expired_no_reentry` incident (§2.3) must be impossible by construction, and §8.7 tests exactly that.

**5.2 Query surface (read API, needed by the studies that motivated this).** `state_at(key, bar)`, `events(key)`, `funnel(as_of=None)` (counts per state), `fate(key)` (terminal state), `coincidence_hits(horizon_bars)` (proof events within H bars of `armed`/reference — the COINCIDENCE_COUNT definition expressed as a store query), `blueprint(key)` (bounds + refinement + tags + pillar path + arm_t/route_t/place_t/fill_t).

## 6. Seams and ownership (who writes what)

| Writer (existing module) | Writes | Notes |
|---|---|---|
| `MultiTFProductRuntime.run_batch` → `MultiTFDetectionDriver.validate_multi` | `detected`, `pillar_failed`, `validated`, `sweep_linked` | the one-driver rule is preserved; the store is a facade-level sink, not a second detector |
| `ZoneDedup` | `arm_suppressed_dedup`, `redetected` | **sole merge authority** (§3.4) |
| `PipelineEngine.arm_at` / `feed_bar` / `scan_route` | `armed`, `posture_classified`, `seek_opened`, `revalidated`, `violated`, `gave_up` | posture/§5 semantics untouched |
| `PipelineAdapter` | `ltf_completion`, `route_formed`, `blocked` | §11 one-shot untouched; adapter remains the only router |
| `IntentBook` | `intent_*` | R9 statuses verbatim; the store mirrors, never re-implements the clock |
| `PendingOrderBook` + runner/positions | `placed`, `order_expired`, `filled`, `closed` | §23/§24 expiry untouched |
| `RiskEngine` (optional, phase 2) | `risk_blocked`, `be_moved` | read-only consumer of episode state in V1 |

**Ownership rule:** the store owns **episode state and history**; existing machines remain the **decision authorities** until a migration is explicitly ruled (§7). In phase 1, **no decision path may read the store** — it may only write to it.

## 7. Migration / V1 scope

**V1 (the only thing a first implementation should build).**

- **In-memory, one instance per run**, shared by the backtest composition, the paper runner mirror, and (optionally) the live loop's single process — mirroring how `POIStateMachine` is a single in-process authority today.
- **Export:** end-of-run CSV + JSON in the established artifact style (`results/<study>/`, local-only/gitignored, banner-free CSVs by repo convention, `DIAGNOSTIC — NOT EDGE` carried by the note/JSON), plus a small in-process query API (§5.2) so future studies read events instead of re-joining artifacts.
- **Not in V1:** Redis, event bus, cross-process/cross-session durability, a live dashboard, any new DB, any decision-path read.
- **Byte-identity constraint (the gate for the implementation step):** with the store enabled in observability-only mode, the frozen 6 m product composition must reproduce `results/product_6m_refresh_track_b/run1` **byte-identically** (`trades.csv`, `report.json`) with an unchanged funnel (2,979 batches → 43,004 merged → 2,021 passed → 30 armed → 10 routes → 4 placed → 3 fills), exactly the fidelity gate the Step-4 and near-miss studies used. A store that changes a byte of the book has changed behaviour and is out of scope.
- **Determinism:** double run byte-identical export; insertion-ordered iteration everywhere (the existing books' determinism contract).

**Migration sketch (for the later prompt — not this task):**

1. **Phase 1 — write-only store + exporters + parity gate.** No behaviour change; §8.8 and §8.9 must pass.
2. **Phase 2 — read-only consumers.** Re-derive published studies from the store and require **0-mismatch** cross-checks: the census chain (1,093 episodes → 946 swept → 490 confirmed → 16 routed → 4 placed → 3 fills), the 474 decomposition taxonomy (A 340 / B 32 / C 102 / D 0, and the A-split 271/69), and COINCIDENCE_COUNT's primary definition (585 / 490 at H=48). Only when those hold does the store become the measurement substrate.
3. **Phase 3 (ruled separately, never big-bang) — decision-path reads.** Any store read that influences routing/risk requires its own dated design + pre-registered measure first (owner plan §6 step 4's spirit).

## 8. Acceptance tests (for the future implementation prompt — listed, not written)

1. **Identity stability under refinement:** an armed tighter box inside a census parent yields **one** episode, `refinement.present = true`, no fork; a non-overlapping box yields two.
2. **Dedup authority:** a re-detected overlapping same-direction zone produces **0 new episodes and 1 `redetected` fact**; `ZoneDedup` remains the only place that decides.
3. **No-lookahead property test:** over a 6 m replay, every event satisfies `bar_index ≤ current_bar`, and `state_at(key, bar)` never reports a later fact.
4. **One-shot invariant:** at most one `route_formed` per episode, machine-asserted (not just tested at the happy path).
5. **Coincidence query reproducibility:** the store's `coincidence_hits(48)` reproduces COINCIDENCE_COUNT exactly (585 episodes / 713 pairs; 490 at the strict sweep anchor) with **0** mismatches.
6. **Funnel reconciliation:** store-derived counts equal the frozen funnel (30 / 10 / 4 / 3) and the published chain with **0 unexplained** rows.
7. **Derived counters:** the `intent_expired_no_reentry` count equals the event count — a direct regression against the logged `expired 0` defect (assert it is **4** on the 6 m window, not 0).
8. **Observability-only parity:** frozen run byte-identical (`trades.csv` + `report.json`) with the store on.
9. **Export determinism:** double run → byte-identical CSV/JSON.
10. **Loud-fail discipline:** unknown event type, missing required field, duplicate/out-of-order timestamp, or a second route for one episode **raises** rather than being silently recorded.

## 9. Open questions for the Architect (max 5)

1. **Q1 — cross-TF identity collision.** The census treats `H4` and `M8←H4` as separate episode groups (75 vs 659). Overlapping H4-registry and M8 zones with the same direction therefore define **two** episodes today. Confirm the store keeps them distinct (proposed) rather than fusing by overlap alone.
2. **Q2 — refinement parent link.** Is the parent pointer + adopted-bounds rule **mandatory** at arm (proposed, needed for the A-split query), or an optional annotation?
3. **Q3 — VALIDATED-unarmed.** Should `EXPIRED_UNARMED` be a first-class state with its own events (proposed; it is where the coincidence study's 208 validated-but-unarmed rows live), or derived on demand from `validated` + absence of `armed`?
4. **Q4 — live persistence.** V1 is per-run in-memory. Does the live loop need the episode store to survive a session restart (a durable sink) before step 4's reactive-admission design, or is per-session in-memory + export sufficient for the next phase of measurement?
5. **Q5 — route key.** Keep `poi:trigger@bar` as the child route identity for legacy compatibility (proposed) or re-key routes as `(episode_key, trigger, completion_bar)` — noting the studies currently had to collapse this by hand.

## 10. Self-check

- Sections 1–9 complete; every state/transition mapped to an existing decision or explicitly marked *bookkeeping only* (§4.3).
- No decision changed, no constant touched, no routing/gate proposal hidden inside a "store feature".
- Identity rule is stated, finite and cross-checkable against published artifacts (§3.3/§8.5–8.6).
- Every claim in §2 cites a file or a published note; nothing is asserted about edge, PnL or expectancy.
- **`DESIGN_LOCK_STATUS: PASS`** (sections 1–9 complete, bans held — pending Architect acceptance before code).

---

**RETURN BLOCK**

```
EPISODE_STORE_DESIGN_STATUS: PASS
DESIGN_PATH: 00_LOCKED/EPISODE_STORE_DESIGN.md
IDENTITY_GRAIN_PROPOSED: (direction, detection_tf, m8_kind_class, [zone_low, zone_high] under overlap-equivalence; bounds canonicalised at 6dp, refinement adopts armed bounds, poi_id/route_id are attributes not identity)
LIFECYCLE_STATES: [DETECTED, REJECTED_PILLAR, VALIDATED, SUPPRESSED_DEDUP, EXPIRED_UNARMED, ARMED(+posture), SEEKING, REVALIDATION, ROUTED, BLOCKED_RETRYABLE, BLOCKED_TERMINAL, INTENT_ARMED, INTENT_EXPIRED, INTENT_REPLACED, INTENT_DROPPED_POI, INTENT_DROPPED_PORTFOLIO, PLACED, ORDER_EXPIRED, FILLED, CLOSED_TP, CLOSED_SL, CLOSED_BE, CLOSED_PORTFOLIO, OPEN_UNRESOLVED, SCAN_CLOSED, VIOLATED]
V1_SCOPE: in-memory+export observability-only
OPEN_QUESTIONS_N: 5
HANDOFF_UPDATED: YES
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
NEXT_READY: Architect acceptance → implement observability store | reactive-admission design
```
