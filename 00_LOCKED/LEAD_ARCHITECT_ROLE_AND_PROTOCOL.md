# Lead Architect Role, Verification Protocol & Session Continuity

**Status:** ACTIVE / BINDING for all agents
**Date:** 2026-09-21
**Authority rank:** subordinate only to `00_LOCKED/LOCKED_DECISIONS.md`; peers with `00_LOCKED/POST_V1_PLAN_OF_ACTION.md` for process; overrides informal chat memory.
**Replaces for full role detail:** `00_LOCKED/SESSION_ROLES_AND_CONTINUITY.md` (kept as the short card; must not contradict this file).

---

## 1. Role definitions (hard boundaries)

### Lead Architect (external — Grok / command session)
- Owns: priorities, phase sequencing, acceptance/rejection of local-agent results, gate rulings, foundation-reset direction.
- Verifies: every local audit/report against locked docs + research artifacts (never trusts chat memory alone).
- Issues: one prompt at a time for the local agent.
- Does NOT: directly edit `04_SRC/smc/` strategy logic in the normal workflow; does NOT tune thresholds without a dated ruling recorded in the plan.
- Must be harsh/quant-honest: no flattery, no silent redesign.

### Local agent (in-repo coding agent)
- Executes exactly one prompt scope.
- May write code/tests/docs only inside that scope.
- Must run pytest when code changes; report pass counts.
- Must update TODO / handoff / changelog when the prompt says so.
- Must NOT: change `locked_constants.py` / LOCKED_DECISIONS without explicit ruling; jump phases; invent scope; "helpfully" resume F-survivor optimization.

### User / project owner
- Runs local-agent prompts.
- Handles MT5 GUI (EA attach, Algo Trading).
- Final business authority.
- Brings local-agent reports back to Lead Architect for verification.

---

## 2. Source-of-truth order (binding)

1. `00_LOCKED/LOCKED_DECISIONS.md`
2. `00_LOCKED/POST_V1_PLAN_OF_ACTION.md`
3. `00_LOCKED/LEAD_ARCHITECT_ROLE_AND_PROTOCOL.md` (this file — process)
4. `00_LOCKED/POST_V1_ACTIVE_TODO.md`
5. `00_LOCKED/SESSION_HANDOFF.md`
6. `00_LOCKED/SESSION_ROLES_AND_CONTINUITY.md` (pointer / short card; must not contradict this file)
7. Architecture docs under `01_ARCHITECTURE/` (flowchart, orchestration) — intent
8. Research reports under `06_RESEARCH/` — evidence only, never override locked law

## 3. Anti-drift rules (the reason this file exists)

- Chat summaries are NOT authority. Locked files + artifacts are.
- "Module exists" ≠ "architecture expressed." Status must be tracked as:
  - CODED | WIRED | OBSERVED | DRIFTED | SILENT | DEFERRED
- After every major milestone, require a path audit: intended cascade vs dominant live path (trade-share / funnel), not only unit tests.
- No optimization track may run while a foundation DRIFT remains open on: multi-TF detection roles, M8 silence-by-accident, hardwired `tp_price=None`, M1-only detect+exec (per FOUNDATION_RESET_QA_PACK).
- Phase D demo/ops is infrastructure proof only — never strategy validation while cascade is non-compliant.

## 4. Current program (matches handoff 2026-09-23)

- **ACTIVE PROGRAM:** **V1.1 RUNTIME BASELINE FROZEN (2026-09-24 — `00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md`)** — default posture: operate and observe under contract. Completed foundation: Product Runtime Unification (owner "Choice 1") — research, paper, and live share ONE multi-TF detection → M5 execution runtime (Phase 0 contract + Phase 1 / C1 + Phase 2 layer contracts + Phase 3 funnel + Phase 4 frozen backtest, all **COMPLETE/PASS**), plus Track A residuals and the Phase D HTF probe (ops PASS). **Next = Phase D watchdog GUI attach + stale-heartbeat emergency drill, or a dated research ruling.**
- **PAUSED:** Trigger F survivor optimization / chase discriminators as main track (R6); Monte Carlo.
- **PARALLEL ONLY:** Phase D ops on EXNESS Copy terminal (infrastructure proof — never idea validation).
- **CLOSED (reference only):** Phase A/B/C baseline; Track R measurement R1–R5; Foundation Fidelity Reset (FR-1→R9) as a completed prerequisite.
- Product contract: `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` (Locked 2026-09-23).
- Product completion path (Phase 0–4): `00_LOCKED/POST_V1_ACTIVE_TODO.md` ("Product completion path").
- Fidelity evidence pack: `06_RESEARCH/FOUNDATION_RESET_QA_PACK.md`; Foundation Reset rulings record: `00_LOCKED/FOUNDATION_RESET_PLAN.md` (historical, R1–R9 in §8).

## 5. Lead Architect verification protocol (how audits are checked)

Whenever the local agent delivers an audit or status block, the Lead Architect (or a new session acting as Lead Architect) must:
1. Re-read the relevant locked section (not the agent's paraphrase).
2. Check claims against named files/paths in `04_SRC/` or `06_RESEARCH/`.
3. Classify each finding: FAITHFUL / PARTIAL / SILENT / DRIFTED / DEFERRED.
4. Accept, reject, or rescope — never "assume fixed".
5. Issue the next single prompt only after acceptance.

## 6. Local agent report contract

Every coding/research prompt return must include:
- STATUS: PASS/FAIL/BLOCKED
- FILES touched (paths)
- SUITE: pytest count if code changed, or "docs-only"
- EVIDENCE paths (reports/artifacts)
- HANDOFF_UPDATED: YES/NO
- What was NOT done (scope boundary)

## 7. Startup protocol for ANY new session

1. Read THIS file.
2. Read `SESSION_HANDOFF.md` current section.
3. Read `POST_V1_ACTIVE_TODO.md` next-action marker.
4. Read the active program contract (`PRODUCT_RUNTIME_CONTRACT.md`) and the "Product completion path" in `POST_V1_ACTIVE_TODO.md` (historical rulings: `FOUNDATION_RESET_PLAN.md`).
5. Continue ONE next prompt — do not restart the project, do not reopen closed Track R gates without Lead Architect order.

## 8. Cloud / project folder note

This file is the durable role anchor for the project folder (and any cloud mirror of `00_LOCKED/`). When knowledge-base or locked docs are synced to cloud, **this file must be included** so Lead Architect sessions never rely on chat history alone.
