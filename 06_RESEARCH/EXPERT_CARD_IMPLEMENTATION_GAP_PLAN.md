# EXPERT CARD IMPLEMENTATION GAP PLAN

**Date:** 2026-11-12 · **Type:** docs + read-only code survey · **Status:** PLAN ONLY (no code changes)
**Authority:** `00_LOCKED/EXPERT_MASTER_CARD.md` (accepted) + `00_LOCKED/EXPERT_AMENDMENT_LIST_2026-11-12.md`
**Context:** `06_RESEARCH/EXPERT_DOCS_ALIGNMENT_AUDIT.md`

---

## 1. Executive summary

- The card is **accepted authority**; this plan measures the distance from the current code, not a claim that the card is live.
- 9 of 18 rows are ALIGNED, 5 PARTIAL, 1 MISSING, 3 CONFLICT.
- **M15 is already wired**: `Timeframe.M15` exists, the runtime default is `(D1, H4, H1, M15)`, and both `OperatorConfig` and `config/live_demo.json` carry the same set. The binding `PRODUCT_RUNTIME_CONTRACT.md` §1 text (H4+H1) is the lagging artifact, not the code.
- **TP is shared across paths**: the adapter and the menu both flow through `candidate_from_route` → `structural_tp_target` (first §19-confirmed swing) with a 4×ATR fallback. `coupled_mtf.py` is a stub, not a second TP path.
- The two behavioural conflicts are **CHOCH Rule 3 routing** (Trigger A accepts any `ChochBreak`, including `RULE_3_INSIDE_WICK`) and **color-defined Demand/Supply** in M8 (`candle.is_bearish` → demand, `candle.is_bullish` → supply).
- The in-between gate is the biggest structural gap: the card makes it the entry validity rule, but no path enforces "trigger completed while price is inside zone high–low". The menu anchors its window on a zone sweep and records edge distance; the adapter has no containment check at all.
- Boundary-sweep fallback has **no product emitter** (only DUMB and the essence research module reference boundary sweeps).
- Work order: a docs-only phase (D0) can run in parallel with C2 (R3 off), but the in-between gate (C3) must land before any measurement pack is meaningful.

**Recommended order:** D0 → C1 (docs reconciliation) → C2a (R3 live-off) → C3 (in-between gate) → C2b (color-free D/S) → C4 (naming/plane/map docs) → C5 (boundary-sweep fallback, separate design) → C6 (measurement + regression).

---

## 2. Method

**Read (code):** `smc/config/timeframe.py`, `smc/live/operator_config.py`, `config/live_demo.json`,
`smc/orchestration/multi_tf_runtime.py`, `smc/orchestration/multi_tf.py`, `smc/orchestration/engine.py`,
`smc/orchestration/product_menu_mtf.py`, `smc/orchestration/coupled_mtf.py`,
`smc/backtest/pipeline_adapter.py`, `smc/backtest/pipeline_bridge.py`,
`smc/poi/choch_classifier.py`, `smc/poi/deal_range.py`, `smc/poi/models/m5_extreme_equal_highs.py`,
`smc/poi/models/m7_equal_resistance.py`, `smc/poi/models/m8_htf_demand_supply.py`,
`smc/triggers/trigger_a_choch.py`, `smc/triggers/trigger_e_rsi_divergence.py`,
`smc/triggers/trigger_router.py`, `smc/triggers/trigger_c_ending_diagonal.py`,
`smc/validation/validation_pipeline.py`, `smc/validation/pillar_*.py`,
`smc/live/run_operator.py`, `smc/live/loop.py`, `smc/paper/runner.py`.

**Read (docs):** master card, amendment list, audit, `PRODUCT_RUNTIME_CONTRACT.md`,
`V1_1_RUNTIME_BASELINE_FREEZE.md`, `LOCKED_DECISIONS.md` §16/§17/§20/§22/§24.

**DATA_GAP:** `smc/orchestration/coupled_mtf.py` is a lazy-export stub (`__getattr__`), so there is no
coupled TP/confirm path to classify. No other file was missing.

**Method note:** classification is per card requirement, not per docs. A row is CONFLICT only where code
actively implements a superseded rule; PARTIAL where the mechanism exists but is optional, mis-bound, or
present on one path only.

---

## 3. Gap matrix (G01–G18)

| ID | Card requirement | As-built evidence (path + fact) | Status | Impact | Disposition | Notes |
|---|---|---|---|---|---|---|
| **G01** | POI TFs include M15 (+H1/H4/D1; W1 optional) | `config/timeframe.py:37` `M15 = 15`; `operator_config.py:183` default `("D1","H4","H1","M15")` | ALIGNED | — | ALREADY_DONE | W1 optional via `optional_timeframes` |
| **G02** | Runtime detection set matches the card POI set, not H4+H1-only | `multi_tf_runtime.py:326` default `(D1, H4, H1, M15)`; `run_operator.py:474` passes `cfg.detection_timeframes` | ALIGNED | — | DOCS_§_EDIT | `PRODUCT_RUNTIME_CONTRACT.md` §1 still says H4+H1 required → doc lag (G18) |
| **G03** | M1/M5 confirm only; must not create structural POIs | Defaults exclude M1/M5; menu uses them only as confirmation TFs (`product_menu_mtf.py:243-247`) | PARTIAL | MED | CODE_IMPL (guard) | `detection_timeframes` accepts `"M1"/"M5"` names from config — a config could create LTF POIs; add a validation reject |
| **G04** | No dual HTF→LTF confirmation chain | Single chain: HTF validate → arm (`engine.arm_at`) → LTF route (`TriggerRouter.scan`) | ALIGNED | — | ALREADY_DONE | Only the ESSENCE §0/§4 wording implies a double chain (A9) |
| **G05** | In-between binary gate (inside zone AND trigger completes inside) | Menu: window opens on `_is_zone_sweep` (`product_menu_mtf.py:124-137`), `distance_at_confirm_atr` recorded (936) but not gated; adapter: no containment check in `generate_candidates`/`_may_route` | PARTIAL | **HIGH** | CODE_IMPL | Must be one shared predicate; today it is implicit at best |
| **G06** | Boundary-sweep fallback path exists and is reachable | Only `smc/dumb/*` and `smc/essence/rules.py` reference boundary sweeps; no product emitter | MISSING | MED | DEFER + RESEARCH_ONLY | Prior docs already say "include later"; needs its own detector design |
| **G07** | CHOCH R3 not live; R1/R2 body-close live | `choch_classifier.py:203-217` returns `RULE_3_INSIDE_WICK`; `trigger_a_choch.py:46` accepts any `ChochBreak`, no rule filter | **CONFLICT** | **HIGH** | CODE_IMPL | Smallest, highest-value fix: filter `rule is not RULE_3` in Trigger A (and any other consumer) |
| **G08** | Color-free OB / Demand-Supply | `m8_htf_demand_supply.py:156/161` `candle.is_bearish` → demand, `is_bullish` → supply; OB is derived from the FVG candle (color-free by construction) | **CONFLICT** | **HIGH** | CODE_IMPL + RESEARCH_ONLY | Direction must come from the impulse/displacement side; needs a measure before swap |
| **G09** | Single origin-candle width | `zone_for_candle(candle, ...)` uses one candle's full range for OB and D/S | ALIGNED | — | ALREADY_DONE | Keep width when G08 changes identification |
| **G10** | Letter map A–F matches the card | `core/enums.py:16-21` A CHOCH, B leading diag, C ending diag, D two-bar, E RSI, F BOS+OB; Trigger E is DT/DB+RSI (`trigger_e_...:1`) | PARTIAL | MED | CODE_IMPL (A filter) | Everything matches except A includes R3; names/labels otherwise correct |
| **G11** | Trigger C live and routable | `trigger_c_ending_diagonal.py` present; `default_triggers()` includes it; menu tier `_TIER_ADF` for H4/H1/M15 | ALIGNED | — | ALREADY_DONE | DAY tier uses its own trigger tuple (`_DAY_TRIGGERS`) — verify card intent there |
| **G12** | TP = first valid swing on all entry paths; fallback only when none | `pipeline_bridge.structural_tp_target` = first §19-confirmed favorable swing; else `resolve_take_profit` 4×ATR; adapter feeds it at `pipeline_adapter.py:441`; menu shares `candidate_from_route` | ALIGNED | — | ALREADY_DONE | No 1:5 gate in the product path (ESSENCE gate is a separate module) |
| **G13** | SL = ATR buffer; 30-pip/2–5 pip not product | Trigger SL built from structure ± `context_atr` (`trigger_a_choch.py:67`); no 30-pip path in `smc/risk` or adapter | ALIGNED | — | ALREADY_DONE | Benchmarks stay documentation-only |
| **G14** | Pillar 3 = Dealing Range (alias Premium/Discount) | `validation/validation_pipeline.py:97-104` `default_pillars()` returns `PremiumDiscountPillar`; `poi/deal_range.py` computes dealing range | PARTIAL | MED | DOCS_§_EDIT + CODE_IMPL (rename) | Role is dealing range; only the class/module/label name lags; no behavior change |
| **G15** | Five pillars only; no sixth | `default_pillars()` returns exactly 5 | ALIGNED | — | ALREADY_DONE | Liquidity is Stage 0, not a pillar |
| **G16** | M5 vs M7 distinct (continuation vs shelf / FLIP) | `m5_extreme_equal_highs.py` proactive cluster; `m7_equal_resistance.py` reactive shelf; both docstrings separate them | PARTIAL | LOW | DOCS_§_EDIT | "Plane FLIP" wording absent; no "flip" concept in the M7 module |
| **G17** | Confluence never drives lot size | No `quality_score`/`confluence` reference in `smc/risk`, `smc/paper`, `smc/execution`; `spread_grading` maps score → grade only | ALIGNED | — | ALREADY_DONE | Sizing reads risk fraction + broker units |
| **G18** | Formal LOCKED/ESSENCE text still conflicts with the card | `LOCKED §16` Premium/Discount; §17/§20 Rule 3 live; §22 color zones; `ESSENCE §5/§6` 2–5 pips / 1:5; `PRODUCT_RUNTIME_CONTRACT §1` H4+H1 | **CONFLICT** | MED | DOCS_§_EDIT | Does not block code survey; blocks "docs = card" claim |

**Counts:** ALIGNED 9 · PARTIAL 5 · MISSING 1 · CONFLICT 3 (HIGH: G05, G07, G08).

---

## 4. Path split (Adapter vs Menu vs Live defaults)

| Aspect | Classic product (Adapter → BacktestRunner) | Menu / coupled MTF | Live defaults |
|---|---|---|---|
| Detection TFs | caller-supplied; runtime default `D1/H4/H1/M15` | menu tiers `D1, H4, H1, M15` (`PRODUCT_MENU_TIERS`) | `cfg.detection_timeframes` = `D1/H4/H1/M15`; M5 execution |
| Confirmation TFs | trigger scan on execution stream | `D1→H1`, `H4→M5/M15`, `H1→M5/M1`, `M15→M1` | same as classic |
| Trigger set | `DEFAULT_TRIGGERS` A–F | `_TIER_ADF` (A/D/F) on H4/H1/M15, day-tier tuple on D1 | A–F |
| In-between gate | **absent** (only §5 state + REVALIDATION latch) | window anchored on `_is_zone_sweep`; distance measured, not gated | inherited from whichever path is active |
| TP | structural first swing → 4×ATR fallback | same `candidate_from_route` path | same |
| SL | structure ± ATR buffer | same | same |
| Coupled path | n/a | `coupled_mtf.py` is a stub — no TP/confirm code to audit | n/a |

**Key divergence:** the menu has a zone-sweep anchor the adapter lacks, but neither enforces "trigger completed while price is inside the zone". That is the single most important shared gap (G05).

---

## 5. Proposed phased plan

| Phase | Content | Type | Depends on | Exit gate |
|---|---|---|---|---|
| **D0** | Formal LOCKED § edits (§16/§17/§20/§22/§24) + ESSENCE header notice from the amendment list | Docs only | Architect acceptance (done) | Reviewable diff, no code change |
| **C1** | Reconcile `PRODUCT_RUNTIME_CONTRACT` §1 with the card (M15 in, W1 optional); add config guard rejecting M1/M5 as detection TFs (G03) | Docs + small guard | D0 | Guard test + doc row updated |
| **C2a** | CHOCH R3 live-off: Trigger A rejects `RULE_3_INSIDE_WICK`; classifier stays intact for research (G07) | Code, small | none | New test: R3 never routes; R1/R2 still route |
| **C3** | In-between hard gate: one shared predicate (price inside zone at trigger completion) enforced at `generate_candidates` and menu `_route_for`; distance remains telemetry (G05) | Code | C2a | Tests: inside→route, boundary-wick→no in-between route |
| **C2b** | Color-free D/S identification with a pre-registered measure before/after; single-origin-candle width unchanged (G08/G09) | Research + code | C3 preferred | Measure pack; no blind swap |
| **C4** | Naming/plane/map cleanup: Pillar 3 label, M7 "FLIP" wording, letter-map documentation (G10/G14/G16) | Docs (+ label-only code) | D0 | Docs match card |
| **C5** | Boundary-sweep fallback design → emitter (G06) | Research design first | C3 | Separate design lock; no code in this plan |
| **C6** | Verification pack: TP-first-swing on both paths, SL ATR, no 1:5 in product, R3 never fires, in-between gate behaviour | Measurement | C1–C4 | Frozen-window pack + determinism |

No phase in this plan is authorized by this document; each needs its own implementation prompt.

---

## 6. Non-goals

- No threshold tuning, no optimization, no expectancy/PF/win-rate claim.
- No full Mode B product, no new model, no new pillar, no new pip constant.
- No automatic merge of ESSENCE rows into code; the card governs, but implementation is phased.
- No rewrite of `LOCKED_DECISIONS.md` or `ESSENCE_CONTRACT_V1.md` bodies in this engagement.
- No coupled-MTF build-out — the module is a stub and is out of scope here.
- No change to the risk shell, news/breaker/Friday behaviour, or the sizing path.

---

## 7. Return block

```text
GAP_PLAN_STATUS: PASS
PATH: 06_RESEARCH/EXPERT_CARD_IMPLEMENTATION_GAP_PLAN.md
ALIGNED: 9
PARTIAL: 5
MISSING: 1
CONFLICT: 3
TOP_BLOCKER: No in-between containment gate on either path, and Trigger A still routes CHOCH Rule 3
M15_RUNTIME: WIRED
TP_ALL_PATHS: YES
R3_LIVE: YES
COLOR_FREE_DS: NO
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
HANDOFF_UPDATED: YES
NEXT_READY: Architect prioritize phases → issue first implementation prompt
```
