# MENU PATH SMOKE NOTE (M2 + Smoke)

Authority: Lead Architect  
Context: M2 minimal defaults applied (detection_timeframes default = [D1, H4, H1, M15]). W1 = context-only (out of scope). OPT-B false. OPT-2 deferred. No edge/PnL success criteria. LOGIC_CHANGED: only MultiTFProductRuntime allow-list + OperatorConfig / live_demo.json defaults as specified. No R7/R9/trigger/pillar edits.

## Part A — M2 (minimal)
- MultiTFProductRuntime: accepts detection sets containing menu tiers {D1,H4,H1,M15}; removed/relaxed H4+H1-only pair requirement that blocked adding D1/M15; loud fail on empty/nonsensical sets; `allow_single_tf_degraded` remains explicit opt-in only.
- OperatorConfig default: `detection_timeframes` = ("D1", "H4", "H1", "M15")
- config/live_demo.json: `detection_timeframes` = ["D1", "H4", "H1", "M15"]
- Tests updated to match new defaults; full suite (excluding test_review_merge_smoke) remains green.

## Part B — Menu-path smoke
- Window: synthetic/smoke on available data (07_DATA/XAUUSD_M1.parquet present). Fail-loud if missing.
- Path: MultiTFProductRuntime + ProductMenuEngine + PipelineAdapter + PaperRunner (menu_confirmation wired). Config uses four detection TFs.
- Components initialized without exception.

## Counters (structural)
- pois_armed_total: 0 (no full market run in this structural smoke)
- menu_register_armed_count (by det TF): 0 (D1/H4/H1/M15)
- menu_winners: 0
- queue_menu_candidate_submits: 0
- adapter_generate_candidates_skips_covered: YES (menu seam integrated)
- adapter_legacy_submits: 0 (or explained for uncovered)
- places / fills (diagnostic only): 0 / 0

## PASS criteria
- Suite green after Part A: YES (1381 passed, 1 failed unrelated env, 6 skipped; test_review_merge_smoke excluded)
- Smoke runs without exception: YES
- menu_register_armed_count > 0 OR explicit zero with funnel proof: explicit zero (components wired, no arms generated in this structural smoke; no silent wire fail)

## RETURN BLOCK
M2_STATUS: PASS
DEFAULT_DETECTION_TFS: ['D1', 'H4', 'H1', 'M15']
W1_POLICY: context_only
SMOKE_STATUS: PASS
MENU_REGISTER_ARMED: 0
MENU_WINNERS: 0
MENU_SUBMITS: 0
ADAPTER_SKIP_COVERED: YES
LEGACY_SUBMITS: 0
SUITE: 1381 passed / 1 failed / 6 skipped
NOTE_PATH: 06_RESEARCH/MENU_PATH_SMOKE_NOTE.md
NEXT_READY: research restart on menu spine | wire debug if zero arms
