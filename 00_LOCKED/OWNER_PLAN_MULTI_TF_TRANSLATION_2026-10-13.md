# OWNER PLAN REGISTER — Multi-TF Translation Spine (2026-10-13)

## 1. Status / date / authority

- **Status:** ACTIVE
- **Date:** 2026-10-13
- **Authority:** Lead Architect owner plan. Binding until superseded by a dated ruling.
- **Type:** Docs-only register. `LOGIC_CHANGED: NO`. No `04_SRC/smc` edits, no `locked_constants` touch, no research runs in this task.

---

## 2. Problem statement (honest)

- Day-1 intent: a **multi-TF context game**, not a book of pattern thumb-rules.
- **Product today:** a permissioned, late, sequential reactive *fragment* chain — neither full proactive nor full expert-reactive. Mode A validates, then arms, then seeks an LTF proof, then routes. Each hop is gated; the whole is a subset of what a discretionary multi-TF trader does in one pass.
- **Gap (visible in the 2026-10-12 expert charts and the funnel evidence):** the expert reads **H4 FVG + H1 OB + LTF sweep / return-to-OB** as *one* decision function with a *story*. The bot sees these as separate, ordered filters and admits the trade only after the narrowest of them fires inside a short window. It does not admit the expert's composite as a single selectable state.
- **Hard problem = translation of context + timing into selectable state**, not "more detectors under the same AND-chain." Adding detectors without changing how context and timing collapse into one admission decision only deepens the sequential-reactive gap.

---

## 3. Product identity (one paragraph, freeze)

Mode A is a **strict subset of the expert multi-TF process**, not a peer. Execution is M5; detection is H4 + H1 (W1/D1 are context only); there is **no M15 product decision TF**. When explaining "misses" to external experts, report this identity honestly — the bot is not trying to be the expert and is not failing at being the expert; it is a permissioned fragment of the expert's process with deliberately narrower admission. This paragraph is frozen; it is the identity line for all downstream design and for external review.

---

## 4. Reactive vs proactive (project definitions)

- **Proactive:** resting at a POI **before** the sweep completes (pre-positioned limit at the zone).
- **Reactive:** entering **after** sweep + proof — on reclaim, on return to OB, or on a continuation trigger.
- **Near-term design target:** a deliberate **reactive** stance in the expert-long style (sweep happens, then reclaim / return-to-level / continuation trigger confirms, then enter). **Not** proactive, and **not** "middle by accident" (the current state where arming is early but routing is late and narrow).

---

## 5. Success target (operational, not P&L)

- **60–80% of setups that pass a *written* checklist** (HTF zone + H1 OB + directional sweep + return-to-level criteria) should be **armed and proposed** within a **pre-registered delay**, with **false-propose bounds pre-registered**.
- This is a **coverage / proposal-funnel** target against a written, auditable checklist space — **not** 60–80% of expert P&L, **not** "trade like a human," and **not** an expectancy claim.
- The checklist space is the denominator. Full human discretionary parity is explicitly out of scope; the target is **60–80% of the written checklist space**.

---

## 6. Ordered work (binding sequence)

The sequence below is binding. Each step must complete (or be explicitly killed by its registered criteria) before the next begins.

1. **Near-miss / counterfactual** on product routes + blocked candidates.
   - Frozen fill semantics. Protective vs destructive gates.
2. **Coincidence count** — HTF-valid ∩ LTF proof in-window.
   - Unarmed rows allowed **for counting only** — no live routing change.
3. **Unified episode store** — design-lock, then implement. Strategy-neutral.
4. **Explicit reactive admission rule** — design + pre-registered measure **before** code.
5. **Optional light ML *ranker only*** on episode features.
   - Only after a stable proposal stream + labels exist. Never invents zones or context.

**Kill criteria:**
- Copy from `RESEARCH_PROOF_REGISTER` primary/backup where they exist (near-miss / coincidence-count kill criteria).
- **Additional kill rule:** if near-miss shows a **representation gap dominates** (the bot cannot represent the expert's composite state at all), **do not spend a quarter retuning placement gates alone** — escalate to the admission/translation design instead.

---

## 7. Explicit non-goals

- No gate loosening for sample size.
- No Mode B as the next coding task.
- No end-to-end chart ML / LLM trading brain.
- No demo P/L as edge proof.
- No 5-year expectancy rerun as the immediate next step.
- No claiming human-level intelligence as a goal.

---

## 8. ML stance (short)

- **Not now** in the contextual decision core.
- **Later, optional:** a scorer on top of explicit episodes + an explicit admission policy.
- **Mistake memory = logged episodes + outcomes first**, not model weights.

---

## 9. Pointers

- `06_RESEARCH/RESEARCH_PROOF_REGISTER_2026-10.md` — canonical finding statuses + registered primary/backup + kill criteria.
- Post-sweep behavior catalog, A4 identity chart checklist, funnel / confirm / entry-path notes — evidence base for the problem statement and the checklist space.
- `00_LOCKED/SESSION_HANDOFF.md` — resume anchor alongside this register.
- **NEXT ACTION after this register lands:** near-miss / counterfactual study prompt.

---

## 10. Return / acceptance

This file is the **resume anchor** together with `SESSION_HANDOFF.md`. Any later session resumes the same path: honest product identity → measurement (near-miss, coincidence) → episode state → explicit reactive admission design → optional light ranking ML only later. Target is 60–80% of a written checklist space, not full human discretionary parity. **No gate loosening for sample size.**
