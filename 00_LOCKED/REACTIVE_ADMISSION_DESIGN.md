# REACTIVE ADMISSION — DESIGN LOCK (SPECIFICATION ONLY)

> **DIAGNOSTIC / POLICY SPECIFICATION — NOT EDGE.**
> This document specifies an explicit, measurable reactive admission rule set to govern
> when an HTF thesis plus an LTF proof may become an admission candidate on the reactive path.
> No production code changes; no gate loosening; no ML brain; no threshold fishing.
> Nothing below authorizes a live execution change today.

**Status:** **DESIGN_LOCKED — pending Lead Architect acceptance before ANY code.**
**Date:** 2026-10-13  
**Authority:** Lead Architect owner plan `00_LOCKED/OWNER_PLAN_MULTI_TF_TRANSLATION_2026-10-13.md` §6 **step 4**, entered after:
1. Near-miss / counterfactual study: `KILL_CRITERIA_VERDICT: PLACEMENT_NOT_PRIMARY` (`06_RESEARCH/NEAR_MISS_COUNTERFACTUAL_NOTE.md`).
2. Coincidence count: `KILL_CRITERIA_VERDICT: COINCIDENCE_MASS_PRESENT` (`06_RESEARCH/COINCIDENCE_COUNT_NOTE.md`).
3. Episode store: `EPISODE_STORE_V1_STATUS: PASS` (`smc/orchestration/episode_store.py`, `06_RESEARCH/EPISODE_STORE_V1_IMPLEMENTATION_NOTE.md`).

**Composes with (does not supersede):** `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` (one-driver rule), `00_LOCKED/EPISODE_STORE_DESIGN.md` (§9a rulings), `00_LOCKED/LOCKED_DECISIONS.md` (§5, §5a Option B seek/scan contract, §11 one-shot, §23/§24 expiry), and `06_RESEARCH/RESEARCH_PROOF_REGISTER_2026-10.md` (F-01 through F-08).

**`LOGIC_CHANGED: NO`** · `locked_constants.py` untouched · no production code edited.

---

## 1. Status / Date / Authority / Non-Goals

- **What this is:** The architectural specification of **when** an HTF thesis + LTF proof may become an admission *candidate* (the reactive path), with an explicit pre-registered offline counterfactual measurement protocol before any production code is written.
- **What this is NOT (binding non-goals):**
  - **No gate loosening:** No widening of R7, session, spread, or give-up thresholds to manufacture sample size.
  - **No Mode B:** Mode A remains the single focus.
  - **No ML in the admission decision core:** No neural net or LLM brain deciding admissions; ML remains an optional downstream ranker only after stable proposal data exist.
  - **No automatic routing of the coincidence mass:** The 585 coincident episodes found in the coincidence study are not auto-converted into orders.
  - **No proactive placement:** Resting limit orders pre-positioned at a zone *before* a directional sweep or proof completes remain strictly out of scope in V1 admission. Proactive placement stays deferred until ruled by the Architect.
- **Acceptance gate:** Requires Lead Architect formal review and acceptance. No `04_SRC` implementation will be conducted under this prompt.

---

## 2. Problem Restatement (Evidence-Cited)

1. **Coincidence is necessary but far from sufficient:**
   In the 6-month study window, **585 out of 1,093 HTF episodes (53.5%)** coincided with at least one Stage-3 LTF completion within 48 M5 bars (`06_RESEARCH/COINCIDENCE_COUNT_NOTE.md`). However, of the 268 coincidences touching armed geometry, only **16 routed (6.0%)** and **3 filled (1.1%)**.
2. **74% of the coincidence mass sits outside current armed geometry:**
   **435 out of 585 coincidences (74.4%)** formed on theses the product never armed: 317 `never_armed` plus 118 `zone-band-only` (90 of which sat inside an armed POI's own zone band). This indicates that the bottleneck is largely an *admission and representation* gap rather than a lack of market liquidity proofs.
3. **Placement gates are protective, not the primary bottleneck:**
   The counterfactual near-miss study (`06_RESEARCH/NEAR_MISS_COUNTERFACTUAL_NOTE.md`) proved `PLACEMENT_NOT_PRIMARY`: 7 of 7 routed-but-untaken paths had `EXPIRED_NO_FILL`, with a median closest approach of 26.59 price units. Gates like session and R7 did not remove takeable winning trades; rather, the orders rested far from price action.
4. **Product identity constraint:**
   Per the owner plan (§3), Mode A is a **strict subset of the expert multi-TF process**, not a peer. Execution is M5; detection is H4 + H1. The expert sees *H4 context + H1 structure + LTF sweep + return-to-level* as one coherent composite thesis. Today, the product splits this into disconnected, sequentially fragile gates. Reactive admission must bridge this gap by explicitly translating context and timing into a selectable state.

---

## 3. Definitions

- **Reactive Admission:** An explicit architectural decision rule that, *after* a directional liquidity proof (a sweep and/or an accepted Stage-3 trigger completion) has occurred, evaluates whether the market geometry, thesis validity, and timing permit minting an actionable trade candidate.
- **Candidate vs. Route vs. Place:**
  - *Candidate:* A fully formed, risk-evaluable trade proposal `(direction, entry_price, sl, tp, anchor)` emitted by reactive admission.
  - *Route:* A candidate accepted by the adapter workflow and submitted to the runner's risk engine.
  - *Place:* A route cleared by all risk, session, and R7 gates that materializes as a resting order in the `PendingOrderBook` or an armed intent in the `IntentBook`.
  - *Admission ≠ Fill:* An admitted candidate still requires risk clearance and physical price interaction to fill.
- **Primary Mechanism Selection:**
  - **Chosen Primary Mechanism:** **Option C (Phased: Scan Continuation enabling Phase 1, followed by explicit Parallel Candidate minting in Phase 2).**
    - *Phase 1 (Immediate / Option A)*: **Scan Continuation under §5a.** When a qualifying LTF proof occurs within an active or re-entering episode, the §5a seek window is extended or re-opened from the proof bar, avoiding give-up expiration while price returns to structure.
    - *Phase 2 (Extension / Option B)*: **Parallel Research Candidate Minting.** When an LTF proof occurs on an HTF thesis that was `VALIDATED` (even if suppressed by dedup or unarmed in-run), a candidate is minted into research shadow logs to measure counterfactual fill performance.
  - *Alternative Mechanism (Option A alone)*: Restricting admission purely to modifying the `PipelineAdapter` scan cursor and give-up deadline on currently armed POIs.

---

## 4. Normative Rule Set R1–R6 (The Core)

The reactive admission engine evaluates exactly six rules ($R_{\text{thesis}}$ through $R_{\text{one\_shot}}$). All rules must evaluate to `PASS` on the evaluation bar for an admission candidate to be admitted.

```
       [HTF Thesis: R_thesis] (ARMED in Ph.1 / VALIDATED in Ph.2)
                 │
                 ▼
       [LTF Proof: R_proof] (Directional Sweep OR Stage-3 Triggers A-F)
                 │
                 ▼
       [Timing Window: R_timing] (Proof within H_proof of Thesis; Bar <= Proof + H_return)
                 │
                 ▼
       [Location Guard: R_location] (Return to Structure / In-Band: market_reentered_zone)
                 │
                 ▼
       [Exclusion Filters: R_exclusion] (No Chase, Allowed Session, Valid Spread)
                 │
                 ▼
       [One-Shot Gate: R_one_shot] (Episode-level one-shot unconsumed)
                 │
                 ▼
         ADMIT CANDIDATE
```

### R1 ($R_{\text{thesis}}$) — Required HTF Thesis State
- **Phase 1 Primary Rule:** The episode must be in state `ARMED` (or `SEEKING` / `REVALIDATION`) within the active `PipelineEngine`.
- **Phase 2 Expansion Rule:** The episode must be in state `VALIDATED` (including `SUPPRESSED_DEDUP` or `EXPIRED_UNARMED` in the `EpisodeStore`), provided its geometric zone remains unviolated by an adverse HTF close.
- **Justification:** Phase 1 preserves strict product runtime containment without expanding the set of tracked live POIs. Phase 2 unlocks the 435 validated-but-unarmed coincidences in shadow mode.

### R2 ($R_{\text{proof}}$) — Required LTF Directional Proof
- Directional alignment is mandatory:
  - Bullish admission requires a sweep of sell-side liquidity (SSL) below a key level OR a bullish Stage-3 completion (`Trigger A, B, C, D, E, F`).
  - Bearish admission requires a sweep of buy-side liquidity (BSL) above a key level OR a bearish Stage-3 completion.
- Proof letter hierarchy: Triggers `F` (BOS+OB), `A` (CHoCH), `D` (2-bar engulfing), and `C` (ending diagonal) are primary.

### R3 ($R_{\text{timing}}$) — Proof-to-Reclaim Window
- **Proof Timing:** The proof event must occur within $H_{\text{proof}} = 48$ M5 bars (~4 hours) of the thesis reference anchor (matching the coincidence study's primary horizon).
- **Return-to-Structure Timing:** The market must return to the structure entry zone within $H_{\text{return}} = 20$ M5 bars of the proof event.
- **Confronting Scan-Close Latency:** If the Stage-3 completion occurs after the initial 20-bar arm give-up deadline, the presence of the proof *re-arms the seek clock* for an additional 20 bars anchored at the proof bar.

### R4 ($R_{\text{location}}$) — Return-to-Structure Geometry
- **Geometry Requirement:** Price must satisfy `market_reentered_zone` (existing named rule from `smc/risk/fill_regime_policy.py`), using the refined 6dp bounds:
  $$\text{Price} \le \text{zone\_high} + (\text{ZONE\_REFINEMENT\_ATR} \times \text{ATR}) \quad \text{(for LONG)}$$
  $$\text{Price} \ge \text{zone\_low} - (\text{ZONE\_REFINEMENT\_ATR} \times \text{ATR}) \quad \text{(for SHORT)}$$
- **Limit Proximity Guard:** The proposed limit order entry price must sit within $1.0 \times \text{ATR}$ of current market price at presentation. This directly confronts the near-miss finding where resting orders failed to fill because the market was ~26 units away.

### R5 ($R_{\text{exclusion}}$) — Exclusion & Invalidation Filters
- An admission candidate is hard-rejected if:
  1. **Late Chase Texture:** The entry bar represents an extended chase candle (> 1.5× ATR range closing outside the zone away from entry).
  2. **Session Gate:** The current timestamp falls outside authorized trading sessions (`ASIA`, `LONDON`, `NEW_YORK`).
  3. **Adverse Invalidation:** The market has closed beyond the adverse boundary of the HTF zone (a true §5 VIOLATED condition post-arm).

### R6 ($R_{\text{one\_shot}}$) — Episode-Level One-Shot Invariant
- Admission adheres strictly to §11 one-shot semantics: **One episode $\rightarrow$ one admitted route candidate $\rightarrow$ one execution attempt.**
- If an episode has already consumed its one-shot (an order was accepted or filled), all subsequent reactive admission proposals for that `episode_id` are blocked.

---

## 5. Pre-Registered Measurement Protocol

Before writing any production routing code, the reactive admission rule set must be evaluated via an offline counterfactual study script over the frozen 6-month window (2025-06-01 to 2025-11-30, 35,725 M5 bars).

### 5.1 Target Populations (Reported Separately)
1. **Population 1 (Armed + Coincident):** The 268 coincidences sitting on armed geometry.
2. **Population 2 (Validated + Coincident):** The 208 coincidences on validated geometry that were suppressed or unarmed.
3. **Population 3 (Never Armed Coincident):** The remaining coincidences on raw census geometry.

### 5.2 Metrics to Measure
- $N_{\text{would\_admit}}$: Total candidates passing R1–R6.
- $N_{\text{overlap\_routes}}$: Number of admitted candidates matching actual product routes (baseline = 10).
- $N_{\text{overlap\_fills}}$: Number of admitted candidates matching actual product fills (baseline = 3).
- $N_{\text{new\_candidates}}$: Number of net-new admitted candidates.
- $\text{Paper\_Fill\_Rate}$: Percentage of new candidates that achieve a limit touch within their lifetime under frozen `fill_model` semantics.
- $\text{Outcome\_Mix}$: Distribution of `TP_HIT`, `SL_HIT`, `EXPIRED_NO_FILL` for paper-traded candidates.

### 5.3 Binding Kill Criteria
The reactive admission design is killed or halted if any of the following pre-registered conditions occur during the measurement:

1. **Under-Selectivity / Representation Failure:**
   If $N_{\text{would\_admit}}$ on Population 1 (Armed + Coincident) is **$< 8$**, the rule set is too restrictive or misrepresents entry geometry $\rightarrow$ **KILL / REDESIGN, DO NOT CODE.**
2. **Persistent Representation Binding (Phantom Candidates):**
   If $N_{\text{would\_admit}} \ge 25$ but the counterfactual **$\text{EXPIRED\_NO\_FILL}$ rate is $> 85\%$**, the entry representation still places orders impossibly far from the market $\rightarrow$ **KILL ADMISSION PATH; DO NOT SHIP TO LIVE.**
3. **Zero Control Overlap:**
   If the rule set achieves **$0$ overlap** with the 3 baseline control fills, it has destroyed the baseline decision path rather than generalizing it $\rightarrow$ **REJECT.**
4. **Saturation Failure:**
   If $N_{\text{would\_admit}} > 150$ in the 6-month window, the rule set acts as an indiscriminate flood gate $\rightarrow$ **KILL FOR OVER-ADMISSION.**

---

## 6. Interaction with Episode Store

The reactive admission rule engine interfaces cleanly with the `EpisodeStore` V1 infrastructure:
- **Read Surface:**
  - Queries `EpisodeStore.get(episode_id)` and `state_at(episode_id, bar)`.
  - Reads `EpisodeRecord.refinement` to obtain canonical refined bounds.
  - Queries `EpisodeStore.coincidence_hits(H=48)` to identify proof pairings.
  - Inspects `EpisodeRecord.route_ids` to enforce Rule R6 ($R_{\text{one\_shot}}$).
- **Write Surface (Observability):**
  - Emits `candidate_admitted` or `admission_rejected` facts to `EpisodeStore.record_event(...)`.
- **Architectural Boundary:**
  - V1 store remains in-memory per run/process.
  - **Zero Redis / Zero Event-Bus Dependency.**

---

## 7. Explicit Non-Changes

To maintain stability and ensure measurement integrity, the following components are strictly **untouched**:
1. **Validation Pillars 1–5:** No threshold, score, or displacement requirement changes in `ValidationPipeline`.
2. **Pillar 2 Displacement:** Thresholds (`DISPLACEMENT_MIN_ATR`, `DISPLACEMENT_PREFERRED_ATR`) remain unchanged.
3. **Session Filter:** Allowed session hours remain frozen.
4. **Risk Layer:** §28 risk sizing, lot clamping, and stop models remain unchanged.
5. **Trigger Letter Geometry:** Definitions of triggers A through F remain identical.
6. **`locked_constants.py`:** No lines added, modified, or deleted.

---

## 8. Open Questions for the Lead Architect (Max 5)

1. **Q1 — Primary Thesis Scope for Initial Code:**
   Should Phase 1 testing strictly enforce $R_{\text{thesis}}$ on `ARMED` episodes only (recommended for initial parity safety), or should it immediately admit `VALIDATED_UNARMED` episodes into shadow tracking?
2. **Q2 — Give-Up Deadline Reset:**
   When an LTF proof fires after the initial 20-bar arm give-up deadline, should the seek window reset to a full 20 M5 bars from the proof bar, or should it inherit only the remaining R8 lifetime?
3. **Q3 — Zone Boundary for Re-entry:**
   When evaluating $R_{\text{location}}$ (`market_reentered_zone`), should the threshold evaluate strictly against the refined armed box (recommended) or allow the broader census parent bounds?
4. **Q4 — M15 Proof Exclusion:**
   Confirm that M15 timeframe confirmations remain strictly excluded from product decision rules per the Mode A identity freeze (owner plan §3).
5. **Q5 — Entry Price Placement Anchor:**
   For reactive candidates, should the entry limit anchor at the zone boundary (FR-3.1) or at the origin of the LTF trigger signal (e.g. Trigger F FVG / Trigger A CHoCH level)?

---

## 9. Self-Check & Governance Audit

- **Sections 1–9 Complete:** All required sections written in exact requested sequence.
- **Rules Crisp & Testable:** Rules R1–R6 are discrete, programmatic predicates.
- **Kill Criteria Pre-Registered:** Four numerical kill bounds frozen before coding.
- **Bans Upheld:** No production code edited; no threshold fishing; no Redis; no expectancy claims.
- **`DESIGN_LOCK_STATUS: PASS`**

---

**RETURN BLOCK**

```text
REACTIVE_ADMISSION_DESIGN_STATUS: PASS
DESIGN_PATH: 00_LOCKED/REACTIVE_ADMISSION_DESIGN.md
PRIMARY_MECHANISM: C
R_RULES_N: 6
MEASURE_KILL_CRITERIA: N_admit<8 on armed-coincident OR paper EXPIRED_NO_FILL>85% OR 0 control overlap kills design
OPEN_QUESTIONS_N: 5
HANDOFF_UPDATED: YES
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
NEXT_READY: Architect acceptance → offline admission measure | store hooks | review
```
