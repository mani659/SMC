# Layered Fidelity Research Plan (L1–L5)

## 1. Status
- **Status:** ACTIVE (as of **2026-11-10**)
- **Authority:** Lead Architect
- **Nature:** Method restart (layered verification), **not** a greenfield rewrite of the codebase or engine.
- **Stage-success retained (bounded evidence):** the product menu path can arm, fill, and close on the 1-month menu funnel (`06_RESEARCH/MENU_TRADE_FUNNEL_1M_NOTE.md`: 9 fills / 9 closes, 2024-04-01→2024-05-01, explained stages). **This is stage success only — not proof of the idea, not proof of flowchart quality, and not an edge claim.**
- **Quality baseline (current):** human score **0 CORRECT / 5 PARTIAL / 4 WRONG** on those 9 closed trades (`06_RESEARCH/MENU_TRADE_SCORECARD_1M.md`); flowchart/geometry quality is **not validated**.

## 2. Problem statement
The pipeline produces countable trades, but human scoring shows 0 CORRECT, so edge cannot be answered yet. The root issue is integration/trade-level scoring before independent HTF sweep fidelity and independent HTF pattern/POI fidelity are established against the locked definitions, making failures ambiguous (HTF event, pattern, wiring, or geometry).

## 3. Binding order (non-negotiable)
Phases are strictly sequential; no phase may start until the prior phase has a written **PASS/FAIL** outcome and, where required below, a **human score gate** recorded.

- **Phase L1 — HTF sweep fidelity** (per TF, independent; no LTF, no orders)
- **Phase L2 — HTF pattern/POI fidelity** (OB / demand-supply / FVG etc. vs locked model cards; no trade path required)
- **Phase L3 — Wiring HTF → LTF** (only on human-accepted HTF events; confirm timing + trigger family; no PnL)
- **Phase L4 — Entry geometry** (only wiring-pass sample; entry/SL/TP vs zone)
- **Phase L5 — Edge / expectancy** (only after L1–L4 honest pass or an explicit Architect waiver)

**Rule:** L2 depends on L1; L3 depends on accepted L1/L2 HTF events; L4 depends on a wiring-pass sample; L5 is blocked until L1–L4 pass honestly or the Architect records an explicit waiver.

## 4. Phase cards

### L1 — HTF sweep fidelity
- **Goal:** Verify, per HTF independently, that detected sweeps match the locked sweep definition (timing, level, wick/close-back semantics) — observation only, no downstream trade logic.
- **In-scope:** Per-TF sweep event sampling and human scoring against locked definitions; event identity, swept level, bar/index/timestamp, and rule-true classification evidence.
- **Out-of-scope:** LTF confirmation, orders, candidates, PnL, expectancy, trigger retune, threshold/constant edits, and any coupling to menu/order paths.
- **Primary TF order:** **H4 first**, then **D1**, then **H1**. **M15** is in-scope only if the Architect explicitly rules M15 a structure TF for this layer (not assumed).
- **Pass/fail criteria:** Scored sweep sample vs the locked sweep definition with a **CORRECT-rate threshold set by the Architect after the first L1 pack** (not invented now). Output is a written PASS/FAIL with the scored sample and rationale.
- **Artifacts path convention:** `06_RESEARCH/results/layered_fidelity/L1/<tf>/` (charts/samples/ledgers, gitignored as research artifacts) with a committed note `06_RESEARCH/L1_<TF>_SWEEP_FIDELITY_NOTE.md` (or a single consolidated L1 note if the Architect directs) recording method, sample, scores, and verdict.

### L2 — HTF pattern/POI fidelity
- **Goal:** Verify HTF POI/pattern instances (OB, demand/supply, FVG, and other locked model types as applicable) against locked model cards — geometry and identification fidelity, independent of any trade path.
- **In-scope:** POI/zone identification samples per relevant HTF; bounds/origin/type/direction checks vs locked model cards; reuse of prior emission lessons (episode uniqueness, origin bounds) as measurement discipline.
- **Out-of-scope:** Any trade/order/confirm path, PnL, expectancy, threshold/tier/trigger retune, and silent dual-tag acceptance.
- **Primary TF order:** Follow the locked model-card scope per family (HTF context first, consistent with L1 evidence); document the TF/family actually sampled. No trade-path requirement.
- **Pass/fail criteria:** Human-scored sample against the locked model cards with explicit mismatch categories; **no dual-tag silent pass**. PASS/FAIL written with evidence; acceptance threshold for the sample is Architect-set/reviewed (not invented here).
- **Artifacts path convention:** `06_RESEARCH/results/layered_fidelity/L2/<family_or_tf>/` (gitignored) with a committed note `06_RESEARCH/L2_PATTERN_POI_FIDELITY_NOTE.md` recording samples, scores, and verdict.

### L3 — Wiring HTF → LTF
- **Goal:** Verify that only human-accepted HTF events from L1/L2 propagate into the correct LTF confirmation window with the expected confirm timing and trigger family — wiring/timing fidelity, not outcome quality.
- **In-scope:** Linking **accepted** HTF events to LTF confirmations within the seek/confirmation window; measuring lag and miss rate; confirming trigger family/tier routing matches the intended menu/tier contract on that sample.
- **Out-of-scope:** PnL, expectancy, fills-as-quality, threshold/tier/trigger retune, and running on unaccepted HTF events.
- **Primary TF order:** The LTF confirmation TFs implied by the accepted HTF tier/menu paths under test (per locked tier/menu contracts), sampled from L1/L2-accepted events only.
- **Pass/fail criteria:** For the accepted-event sample: linkage rate, lag distribution, and miss reasons are measured and human-reviewed; PASS requires the wiring to faithfully realize the intended HTF→LTF contract on that sample (written verdict). No PnL gate.
- **Artifacts path convention:** `06_RESEARCH/results/layered_fidelity/L3/` (gitignored) with committed note `06_RESEARCH/L3_HTF_LTF_WIRING_NOTE.md`.

### L4 — Entry geometry
- **Goal:** On a wiring-pass sample only, measure whether entry, SL, and TP geometry relate correctly to the zone/plan (placement quality), without changing behavior.
- **In-scope:** Entry/SL/TP vs zone and stop-distance relations on the L3 wiring-pass sample (or the accepted subset); quantification of tight/noise/structural stop geometry (building on the existing 1m measurement precedent, e.g. `06_RESEARCH/MENU_TRADE_SCORECARD_1M.md`).
- **Out-of-scope:** Any threshold change, retune, OPT fishing, or structural-TP/feed changes inside L4 — **measure only** unless the Architect explicitly opens a design/implementation change.
- **Primary TF order:** Same sample provenance as the L3 wiring-pass set (no new population invented).
- **Pass/fail criteria:** Written measurement report with per-sample geometry classification and an honest PASS/FAIL (or “not yet viable”) verdict on plan geometry; no PnL/edge inference.
- **Artifacts path convention:** `06_RESEARCH/results/layered_fidelity/L4/` (gitignored) with committed note `06_RESEARCH/L4_ENTRY_GEOMETRY_NOTE.md`.

### L5 — Edge / expectancy
- **Goal:** Assess expectancy/edge only after upstream fidelity is honest.
- **In-scope:** Frozen window, cost/spread policy, and expectancy-style evaluation — defined only when this phase is opened.
- **Out-of-scope:** Opening L5 early; substituting PnL on an unvalidated stack for fidelity.
- **Primary TF order:** TBD by Architect when opened (frozen, declared in advance).
- **Pass/fail criteria:** **TBD** — to be defined only when L5 is opened, after L1–L4 honest pass or an explicit Architect waiver. Any window/cost policy is TBD until then.
- **Artifacts path convention:** `06_RESEARCH/results/layered_fidelity/L5/` (gitignored) with a committed note `06_RESEARCH/L5_EDGE_EXPECTANCY_NOTE.md` (only when opened).

## 5. Explicit non-goals
- Rewrite the engine from zero.
- Treat the 9-trade 1m scorecard (`06_RESEARCH/MENU_TRADE_SCORECARD_1M.md`) as an optimization target.
- Use structural TP, OPT-2, or risk retune as a substitute for L1–L3 fidelity.
- Make any multi-year (or broad) edge claim before L4 is honestly passed (and L5 properly opened).

## 6. Relationship to existing work
- **Keep (foundations/evidence machinery):** F1/F2 information-set work, F3 sizing-pin code (safety), F5–F7 lifecycle/causality fixes, and the menu trade funnel/chart/scorecard harnesses and their committed notes — as instruments and repaired plumbing, not as proof of idea quality.
- **Demote:** trade PnL and planned-R on the current 1m sample as decision inputs (diagnostic only; 0/5/4 quality stands).
- **Evidence, not competing “next product”:** `baseline_pre_fix`, `post_f1f2`, `post_f5f7`, and `menu_trade_funnel_1m` remain recorded evidence/baselines — they do not compete as the next product direction and do not override this layered order.
- **Locked references (cite, do not reinvent):** sweep/POI and level definitions — `00_LOCKED/LOCKED_DECISIONS.md` (e.g. liquidity levels/sweep classification, POI/zone rules), `00_LOCKED/SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md`, `00_LOCKED/MODEL_8_HTF_DEMAND_SUPPLY.md`; policy/runtime/tier contracts — `00_LOCKED/PRODUCT_POLICY_MULTI_TF_CONFIRMATION.md`, `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md`; plan/reset context — `00_LOCKED/FOUNDATION_RESET_PLAN.md`, `06_RESEARCH/FOUNDATION_RESET_QA_PACK.md`. Prior flowchart/architecture mapping remains reference material (`06_RESEARCH/FLOWCHART_CODE_EVIDENCE_MAP.md`, `06_RESEARCH/AS_CODED_ARCHITECTURE_FLOWCHART.md`) — not a fidelity verdict.

## 7. Immediate next action (single)
- **NEXT = Phase L1 H4 sweep-only fidelity pack** (prompt to follow from Architect).
- **Not:** 3-month edge run, live `dry_run=false` / size-on, entry/threshold constant edits, OPT-2/structural-TP/risk retune, or starting L2–L5.

## 8. Return block
```text
PLAN_LOCK_STATUS: PASS
PATH: 06_RESEARCH/LAYERED_FIDELITY_PLAN.md
BINDING_ORDER: L1→L2→L3→L4→L5
NEXT: L1 H4 sweep-only
LOGIC_CHANGED: NO
```
