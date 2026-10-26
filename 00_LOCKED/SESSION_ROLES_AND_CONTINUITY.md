# SESSION ROLES AND CONTINUITY — SMC BOT

**Created:** 2026-09-20 · the "who does what + where we are" card for every new session.

> **Superseded for full role detail by `00_LOCKED/LEAD_ARCHITECT_ROLE_AND_PROTOCOL.md` (ACTIVE/BINDING 2026-09-21).** This file remains the short card: roles below stay short by design — do not expand them here; amend the protocol file instead.

---

## 1. Roles

### Lead Architect (external chat — Grok)
- Sets priorities, accepts/rejects phase results
- Issues prompts for the local agent
- Makes binding rulings on gates, scope, non-goals
- Does **not** directly edit the repo in normal workflow
- Harsh quant review; no flattery; no silent redesign

### Local agent (in-repo coding agent)
- Executes one prompt at a time
- Writes code/tests/docs in the project
- Runs pytest / research scripts
- Updates TODO / handoff / changelog when instructed
- Must not change locked constants without explicit ruling
- Must not jump phases or invent scope

### User / project owner
- Runs local agent prompts
- Handles MT5 GUI actions (EA attach, Algo Trading)
- Final authority on business decisions
- Brings local-agent reports back to Lead Architect

## 2. Source-of-truth order

1. `LOCKED_DECISIONS.md`
2. `POST_V1_PLAN_OF_ACTION.md`
3. `POST_V1_ACTIVE_TODO.md`
4. `SESSION_HANDOFF.md`
5. this file
6. research reports under `06_RESEARCH/`

## 3. Current posture (2026-09-20)

- V1 build complete
- Phase A/B/C closed
- Track R diagnosis closed: entry/selection primary; fixed TP rejected
- System mostly trades Trigger F on M1
- Identity export improved (model_tags / pillar_path / disp_magnitude_atr); **original SL + zone geometry patch DONE** (suite 596 green; BE no longer corrupts placement-stop records)
- V1 trade inspector DONE (curated F/B chart set); flowchart match notes DONE (tag flicker, zero STRONG matches, BE-contamination documented with decontaminated baselines); HONEST-R recompute DONE 2026-09-20 (39 setups, honest medians, contamination bounded to BE trades — rule: original_sl only henceforth); stratified sample DONE (16 charts, chase dominates F); F-timing v1 + wider validation DONE (mid_move 61.5%/57.9% vs chase 13%/26% ≥1R, NO retune); follow-on v2 DONE (intent failed honestly, NO live gate); STOP-VS-SHELF DONE 2026-09-20 (F = noise-tag deaths on tight pre-touched stops, B = genuine breaks on wide fresh stops); FORMAL MAP DONE 2026-09-20 (durable flowchart→code→evidence record)
- Visualization roadmap: Python research charts first (V1 done); MT5 draw-only later (V3, not started)
- Phase D ops parallel only; not idea validation; EXNESS Copy terminal only
- **Active program: Product Runtime Unification (Phase 0–4, "Choice 1")** — Phase 0 contract + Phase 1/C1 one multi-TF runtime COMPLETE/PASS; Phase 2 contract tests next

## 4. Active next actions

1. **NEXT ACTION = human re-score of post-F1F2 armed + stratified charts** (Architect gate: Armed ≥50% CORRECT on re-score; dual=0; conflicts=0 already proven mechanically) — or Phase D watchdog GUI chart-attach + stale-heartbeat emergency drill (ops). F1/F2 M8 emission fix DONE 2026-10-04 (note `06_RESEARCH/F1_F2_M8_EMISSION_FIX_NOTE.md`). The V1.1 runtime baseline is FROZEN 2026-09-24 (`00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md`; no long expectancy run without a ruling). Completed foundation: Phase 0 contract + Phase 1 / C1 (one multi-TF runtime for live = paper = research) + Phase 2–4 (COMPLETE/PASS); Track A residuals COMPLETE; Phase D HTF probe PASS; R9 ACCEPTED (n=1). F-survivor work stays PAUSED (R6). Program path: "Product completion path" + "V1.1 freeze" sections in `POST_V1_ACTIVE_TODO.md`; contract `PRODUCT_RUNTIME_CONTRACT.md`.
2. **Phase D ops** in parallel (background only): order paths PROVEN live 2026-09-21 (limit/cancel/modify-preserves-TP/close, flat) + live bar-cycle clean; remaining: EA attach (GUI), emergency drill, divergence log, 2-week stability.
2. **Phase D ops** in parallel: order paths PROVEN live 2026-09-21 (limit/cancel/modify-preserves-TP/close, flat) + live bar-cycle clean; remaining: EA attach (GUI), emergency drill, divergence log, 2-week stability.
3. Open gate rulings pending in `POST_V1_ACTIVE_TODO.md` §4 (TP family, spread-grade semantics, Trigger D, M8 scope, R-multiple reporting).

## 5. Hard non-goals

- no parameter fishing
- no TP implementation track for now
- no MQL5 strategy logic
- no demo P/L as strategy proof
- no locked-constant edits without dated ruling

## 6. How to start a new session

Tell the new Lead Architect / agent:
1. Read this file
2. Read SESSION_HANDOFF current section
3. Read POST_V1_ACTIVE_TODO next-action marker
4. Continue exactly one next prompt — do not restart the project
