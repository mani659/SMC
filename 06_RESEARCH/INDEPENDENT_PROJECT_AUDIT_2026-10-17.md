# INDEPENDENT PROJECT AUDIT — 2026-10-17

## 0. Auditor identity & limits

**Role.** Independent, external, institution-grade auditor. Not a builder, not the
architect, not a contributor. No stake in endorsing prior work.

**Method.** Primary evidence only — code, tests, frozen reports, git, shipped
artifacts, live logs. Prose is a claim, not proof. Where a document and the code
disagree, **code wins** and the disagreement is recorded as drift.

**Labels.** Each material statement is tagged `FACT` (directly observed),
`INFERENCE` (reasoned from facts), or `CLAIM_UNVERIFIED` (asserted in prose, not
independently confirmed).

**Limits of this audit (what I could NOT verify).**

- **Live MT5 is not runnable in this environment.** No live connectivity, demo
  session, or chart-marker rendering could be observed. All "live" conclusions are
  from `logs/`, EA logs, and reports.
- **`.ex5` binary parity is unverifiable without MetaEditor GUI.** I can compare
  file sizes/timestamps, not compiled behaviour.
- **Research CSVs under `06_RESEARCH/results/` are gitignored** (present on disk,
  not in version control). Economic conclusions were read from the frozen report
  files, not recomputed from raw CSVs.
- **No new PnL experiment was run.** Running a campaign on live/demo books is
  banned for this engagement and would itself be an edge claim. I audit what exists.

**Hard bans honoured.** No code change, no threshold "improvement", no new strategy
rule, no invented expectancy, no rubber-stamping of prior audits, no dismissal of
scarcity without separating product flow from Mode T.

---

## 1. Executive verdict

**SOUND_WITH_RESERVATIONS.**

The engineering is genuinely strong and the *intellectual honesty is exceptional* —
the project consistently refuses to call operations "edge", marks diagnostic paths
as diagnostic, and documents what is UNFED or DEFERRED instead of implying it is
active. That is rare and it is the single most valuable thing here.

The reservations are real and specific:

1. **No economic evidence exists, and cannot exist yet** — the product funnel is
   near-empty (4 placed / 3 filled over six months, all stop-loss exits). This is
   disclosed, not hidden, but it means the *idea* is architecturally sound and
   economically unproven.
2. **The shipped tester pack is stale** — it predates the Mode T deliverable
   entirely and carries an old watchdog binary (see MAJOR-A01).
3. **Live operations were never proven** — the EA was never chart-attached and no
   unattended soak was run. The one real failure (heartbeat truncation) was found by
   forensic log reading, not by a test or a soak (see MAJOR-A03).
4. **Guard posture behind `dry_run=false`** is weaker than the surrounding narrative
   suggests (spread/news/sweep guards dormant in shipped configs) — see MAJOR-A04.

Nothing here says "stop". It says: the foundation is sound, the honesty is a real
asset, and the three items that gate an external-tester / demo claim are
**provenance, live ops, and the scarcity ceiling.**

---

## 2. Intended thesis

`FACT` — from `00_LOCKED/LOCKED_DECISIONS.md`, `POST_V1_PLAN_OF_ACTION.md`,
`PRODUCT_RUNTIME_CONTRACT.md`, `V1_1_RUNTIME_BASELINE_FREEZE.md`, the Mode design
notes.

The thesis is an SMC-style, top-down, order-flow strategy:

- **Detection (HTF):** H4 + H1 identify Points of Interest (POIs) — order blocks /
  FVG / liquidity structures — while price is *equilibrium-corrected* and passes a
  "seek" phase that arms zones only on qualifying proof.
- **Execution (LTF):** on M5, a **limit** order is placed at a structural entry
  around a confirmed POI, with a **structural stop** (beyond the reference extreme,
  buffered) and a **take-profit**.
- **Discipline:** one driver; loud-fail; the product path is *scarce by design* and
  *frozen* after freeze; `v1.1` is "operate and observe under contract", **not**
  redesign.
- **Explicit non-claims:** nothing in the freeze is an edge claim. Demo PnL never
  validates the idea. Structural TP, news calendar, and sweep-level feed are
  documented NON-active.

`FACT` — the thesis is stated with unusual discipline about what it does *not* prove.

---

## 3. As-coded thesis

`FACT` — traced through `04_SRC/smc/` (126 Python files, 19,359 LOC) and verified
against a 13-stage as-coded spine (detect → dedup → seek → confirm → entry →
risk → execute → track → exit). Highlights verified by direct read:

- **Fill model is conservative and pure.** `04_SRC/smc/backtest/fill_model.py:45`
  (`limit_filled`: touch = fill, boundaries inclusive), `:58` (fill price = limit
  price — no better-of-open), `:112` (`evaluate_position_bar`: same-bar SL+TP →
  **SL wins**; entry+SL same bar → **SL wins**). No intra-bar path reconstruction.
  `FACT`.
- **Lookahead-clean.** The as-of trim discipline was verified against the
  `MultiTFProductRuntime` seam (`04_SRC/smc/orchestration/multi_tf_runtime.py`) —
  prefixes are built from closed bars only. `FACT`.
- **One product runtime.** H4/H1 detection + M5 execution share one seam; live + paper
  wired. `FACT`.
- **Risk-sizing is a single path.** `04_SRC/smc/risk/risk_engine.py` is the only
  sizing authority; `sweep_guard.py` exists but is dormant when no `sweep_level` is
  emitted (`risk_engine.py:124,224`). `FACT`.
- **Mode T is a separate diagnostic builder** at the candidate/limit seam only
  (`04_SRC/smc/live/mode_t.py`), constants in-module (`:78-82`), no fork of
  detection/§5, dispatched after (and yields to) the product path
  (`PRODUCT_PATH_TAKEN`), tag `mode=T`, ledger `mode_t_events.jsonl`. `FACT`.
- **EA watchdog is safety-first but fail-closed:** an unreadable heartbeat drives an
  `Emergency()` that closes ALL scoped positions and deletes ALL scoped pendings
  (`05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5:147-161`). `FACT`.

---

## 4. Idea ↔ execution gap matrix

| # | Intended | As-coded | Gap | Severity |
|---|----------|----------|-----|----------|
| G1 | Structural TP | Fed by `FR2_TP_ATR_MULTIPLE = 4.0 × ATR` fallback only; no trigger emits a structural target | **UNFED by design**, documented (`V1_1_RUNTIME_BASELINE_FREEZE.md:44-45`, `pipeline_bridge.py:103-104`) | Disclosed / none |
| G2 | News guard | `news_events = []` in shipped configs → dormant | **DEFERRED** (contract §8) | Disclosed / none |
| G3 | Sweep-level feed | No trigger emits `sweep_level` → guard dormant | **DEFERRED** (contract §8) | Disclosed / none |
| G4 | Spread gate | `spread_price = 0.0` → `SPREAD_MAX_ATR` gate passes trivially | **WIRED but effectively OFF** in shipped configs | See MAJOR-A04 |
| G5 | Post-sweep continuation / reactive admission | Design-only; not in decision path | **Design ≠ code**, documented as design-only | MINOR |
| G6 | Design locks are binding | `MODE_T_*`, `MODE_A_LTF_RETURN_*, REACTIVE_ADMISSION_*` design files are **untracked** in git | Binding not versioned | MAJOR-A02 |

`INFERENCE` — the "gap" in G1–G3, G5 is not concealment: each is explicitly marked
UNFED / DEFERRED / DESIGN_ONLY in the contract and freeze. That is the correct
posture. G4 and G6 are the only two where the *record* is weaker than reality.

---

## 5. Tolerances & policy register

`FACT` — values observed in code/config:

| Policy | Value / state | Home |
|--------|---------------|------|
| Locked-constant authority | `04_SRC/smc/config/locked_constants.py` (single source of truth) | test-pinned by `test_locked_constants.py` |
| Spread-grade score scale | `{A+:3, A:2, B:1, C:0}` (§28.5, amended 2026-10-11) | `test_locked_constants.py:61` |
| FR-2 stop buffer | `FR2_SL_BUFFER_ATR = 0.3` | `triggers/base_trigger.py:44` (**not** locked_constants) |
| FR-2 TP fallback | `FR2_TP_ATR_MULTIPLE = 4.0` | `triggers/base_trigger.py:45` (**not** locked_constants) |
| Mode T gap / TP / rest | `T_MAX_GAP_ATR=0.25`, `T_TP_ATR=1.0`, `T_REST_BARS=12` | `live/mode_t.py:78-82` (in-module) |
| Mode T caps | `T_MAX_CONCURRENT=2`, `T_MAX_PER_DAY=6`, min lot 0.01 | `live/mode_t.py:81-84` |
| Trigger A expiry | 20 M5 bars | locked constants |
| Active configs | `live_demo.json` `dry_run:false`; `live_tester.json` `dry_run:true` | `config/` |

`FACT` — no locked constant drifted: `git diff --stat -- locked_constants.py` is
empty across this engagement; the only historically accepted amendment is the
spread-grade scale (recorded).

`INFERENCE` — the register is well-controlled for locked constants, but **decision-
path geometry outside `locked_constants.py`** (FR-2 buffer/TP, Mode T) relies on
module constants + tests rather than one merged table. It is test-pinned
(`test_fr2_sl_tp_routing.py:37-38`, `test_structural_tp_feed.py:189`) so it is
*traceable*, but it is not *centralised*. MINOR-A05.

---

## 6. Quality of engineering

`FACT` — measured:

- **Scale:** 126 Python files / 19,359 LOC under `04_SRC/smc/`; 120 test files;
  suite **1173 passed, EXIT=0** (up from 737 at freeze and 1167 before the 10-17
  Fix A work → **+6 targeted tests, none weakened**).
- **Test discipline:** tests pin locked values, the fill model, the as-of trim, the
  discovery/decision-boundary config gate (unknown/geometry keys rejected), the
  demo gate, and Mode T constants.
- **Recent hardening (10-17, this engagement):** heartbeat write made
  non-truncating (`heartbeat.py`, `O_BINARY` + `lseek`/write/`fsync`/`ftruncate`);
  independent heartbeat thread; MT5 auto-reconnect with backoff and give-up;
  structured console events; startup banner. All zero decision-logic change.
- **Safety boundary:** EA is intentionally dumb and fail-safe; Python holds all
  decisions. Good separation.

**Weaknesses:**

- **Provenance hygiene is the weakest link.** The build/release step
  (`AUTO_BUILD_RELEASE.py`) has not been run since 2026-10-08, so the shipped pack
  is behind the source (MAJOR-A01). Governance docs are partly untracked
  (MAJOR-A02).
- **No end-to-end integration test** drives the full detection→scan→Mode T→marker
  chain through a fake connector; loop-level tests exercise `OperatorSession.run`
  with a mocked stack (`test_perm_hardening.py:153,296,…`), which is close but not
  the whole chain. MINOR.

`INFERENCE` — engineering quality is **strong**; release/version governance is the
gap, not the algorithm code.

---

## 7. Economic / research honesty

`FACT` — frozen 6-month funnel (2025-06-01→2025-11-30 UTC, `XAUUSD_M1.parquet`):
**4 placed / 3 filled**, net **−2.73**, exit mix **all stop_loss**, decomposition
A340/B32/C102/D0, LTF confirm 490/946 @48, post-sweep catalog n=174.

- **No edge claim is made anywhere.** `V1_1_RUNTIME_BASELINE_FREEZE.md` states
  plainly that nothing in it is an edge claim and that demo PnL never validates the
  idea. `FACT`.
- **Every PnL figure carries its n and its diagnostic status.** The Phase 4/6
  reports mark n=1 (`BE-scratch +0.0715 raw`) as diagnostic only. `FACT`.
- **Root causes are catalogued** (R1 AND-chain, R2 latency, R3 amnesia, R4 chase,
  R5 lot-cap, R6 zero volume) rather than explained away. `FACT`.

`INFERENCE` — the honesty is the project's strongest asset and should be protected;
the temptation to reframe diagnostics as evidence is the main reputational risk, and
the record currently resists it.

---

## 8. Bottlenecks (ranked)

1. **Entry scarcity — R1 AND-chain (economic ceiling).** `FACT` — the product path
   produces almost no opportunities (4 placed / 6 months). Until this is addressed
   by a dated ruling, *no* economic evidence is obtainable and every downstream
   quality claim is untestable. This is the #1 bottleneck and it cannot be fixed by
   more engineering. `TOP_BOTTLENECK`.
2. **Live ops unproven (operational ceiling).** `FACT` — EA never chart-attached, no
   unattended soak; the real heartbeat defect was found by forensics. `MAJOR-A03`.
3. **Stale tester pack (release ceiling).** `FACT` — shipped pack predates Mode T and
   carries an old `.ex5`. `MAJOR-A01`.
4. **Untracked design locks (governance ceiling).** `FACT` — binding design files are
   not in git. `MAJOR-A02`.

---

## 9. Demo / external-tester readiness checklist

| Item | Status | Evidence |
|------|--------|----------|
| Runtime starts / clean shutdown | `FACT` PASS | Phase D ops session; `loop.py` start refuses without HTF (`MissingHtfSeriesError`) |
| Config gate rejects bad keys | `FACT` PASS | operator-config tests |
| Demo gate (`require_demo`) | `FACT` PASS | `test_require_demo_gate.py` |
| Heartbeat non-truncating | `FACT` PASS (post 10-17) | `test_perm_hardening.py` new tests |
| Independent heartbeat | `FACT` PASS | `test_live_phase7.py` new test |
| Auto-reconnect | `FACT` PASS (unit) | `test_perm_hardening.py:470` etc. |
| **Tester pack is current** | `FACT` **FAIL** | packed 10-08, SHA `2011d9b`, no `mode_t.py`, old `.ex5` |
| **EA chart-attach + unattended soak** | `FACT` **FAIL** | never attached; no soak evidence |
| **Design locks versioned** | `FACT` **FAIL** | untracked in git |
| `.ex5` byte-matches `.mq5` | `CLAIM_UNVERIFIED` **FAIL** | cannot compile here; repo `.ex5` (Oct-15, 20,358 B) ≠ `dist` `.ex5` (Oct-7, 13,790 B) |
| Mode T documented for testers | **FAIL** | `dist/TESTER_README.md` has no Mode T mention |

**DEMO_READY = YES_WITH_BLOCKERS.** The *runtime* is demo-ready; the *pack* and the
*operational proof* are not.

---

## 10. Next-plan assessment

`FACT` — the registered next research step is the **near-miss / counterfactual
study** (backup: coincidence count), parked pending an architect implementation
prompt; POI scarcity + Mode T enablement DEFERRED.

`INFERENCE` — the near-miss study is the **rational** next move: given the R1
scarcity ceiling, the only honest way forward without inventing edge is to study the
*marginal* misses (how close the AND-chain came) to decide whether scarcity is a
fidelity bug or a genuine thesis characteristic. This is exactly the right question.

**Conditions (why not a clean endorse):**

- It must run under a **dated ruling** and must not be reframed as expectancy.
- It must not become a back-door strategy/threshold change (banned).
- The scarcity-vs-Mode-T distinction must be preserved (product flow ≠ diagnostic
  flow) — do not let Mode T volume mask the product bottleneck.

**NEXT_PLAN_VERDICT = ENDORSE_WITH_CHANGES.**

---

## 11. Findings list

### CRITICAL
*None.* No capital-live defect was found, and the engagement ran with `LOGIC_CHANGED: NO`.

### MAJOR

- **MAJOR-A01 — Shipped tester pack is stale and pre-Mode-T.** `FACT` —
  `dist/SMC_v1.1-test.7_tester.zip` (2026-10-08), `dist/VERSION.txt` →
  build SHA `2011d9b`, built 2026-10-08; `dist/04_SRC/smc/live/` contains **no**
  `mode_t.py` (nor marker/judgement modules); `dist/mql5/SMC_Safety_Watchdog.ex5`
  is the **Oct-7** build (13,790 B) while the current repo build is **Oct-15**
  (20,358 B). The 2026-10-15 audit marked the pack **PASS** without checking
  provenance — that PASS is wrong.
- **MAJOR-A02 — Binding design-lock docs are untracked in git.** `FACT` —
  `git ls-files --error-unmatch` fails for `00_LOCKED/MODE_T_CONSOLE_MARKER_DESIGN.md`,
  `MODE_A_LTF_RETURN_ENTRY_DESIGN.md`, `REACTIVE_ADMISSION_DESIGN.md` (and
  `ENTRY_REPRESENTATION_DESIGN.md`, `EPISODE_STORE_DESIGN.md`,
  `MODE_A_LTF_RETURN_SELECTION_BREADTH_AMENDMENT.md`,
  `OWNER_PLAN_MULTI_TF_TRANSLATION_2026-10-13.md` are untracked per `git status`).
  The 2026-10-15 audit's claim that "design docs are tracked in git" is **false**.
- **MAJOR-A03 — Live ops never proven.** `FACT` — EA chart-attach is GUI-only and
  unconfirmed; no unattended soak; the heartbeat truncation bug was discovered by
  forensic reading of `logs/`, not by a test or a soak. Resilience added on 10-17 is
  **unit-tested but not live-tested**.
- **MAJOR-A04 — Guard posture behind `dry_run=false`.** `FACT` — `config/live_demo.json`
  sets `dry_run:false` while `spread_price=0.0` (spread gate passes trivially),
  `news_events=[]` (news dormant), and no `sweep_level` emitted (sweep guard
  dormant). With structural TP UNFED, a live demo send therefore relies on
  **session + pillars + circuit-breaker + same-level guard only**. This is
  documented as deferred, but the *operative* gate count is lower than the
  surrounding narrative implies. Flagged for owner awareness, not as a defect.

### MINOR

- **MINOR-A05 — Decision-path geometry lives outside `locked_constants.py`.**
  `FACT` — `FR2_SL_BUFFER_ATR`/`FR2_TP_ATR_MULTIPLE` in
  `triggers/base_trigger.py:44-45`; Mode T constants in `live/mode_t.py`. Test-pinned
  but not centralised. (Refutes the "fake constants in locked_constants" claim — they
  are simply elsewhere and are pinned.)
- **MINOR-A06 — Config `heartbeat_path` points at the legacy non-EA path.**
  `FACT` — `config/live_demo.json`/`live_tester.json` set
  `logs/phase_d/heartbeat.txt`, which is *not* the EA-readable file; the operator
  resolves the real terminal-data path at runtime. Confusing to an operator reading
  the config.
- **MINOR-A07 — `dist/TESTER_README.md` does not mention Mode T / markers.**
  `FACT` — no match for "Mode T"/"mode=T"/"diagnostic".
- **MINOR-A08 — `.ex5` not byte-identical to `.mq5`.** Disclosed residual; a
  byte-match needs MetaEditor GUI, unavailable here.

---

## 12. Return block

```
AUDIT_STATUS: COMPLETE
IDEA_QUALITY: SOUND_AS_ARCHITECTURE__EDGE_UNPROVEN
EXECUTION_QUALITY: STRONG_WITH_RELEASE_GOVERNANCE_DRIFT
INTENDED_VS_CODED: ALIGNED_ON_DECISION_LOGIC__DRIFT_IN_DOCS_AND_RELEASE
TOP_BOTTLENECK: PRODUCT_ENTRY_SCARCITY_R1_AND_CHAIN
MODE_T_ASSESSMENT: JUSTIFIED_DIAGNOSTIC
DEMO_READY: YES_WITH_BLOCKERS
BLOCKERS: STALE_TESTER_PACK__LIVE_OPS_UNPROVEN__UNTRACKED_DESIGN_LOCKS
SUITE: 1173_PASSED_EXIT_0
CRITICAL_FINDINGS: 0
MAJOR_FINDINGS: 4 (A01 stale tester pack; A02 untracked design locks; A03 live ops unproven; A04 dry_run=false guard posture)
MINOR_FINDINGS: 4 (A05 geometry constants outside locked_constants; A06 legacy heartbeat_path in config; A07 tester README lacks Mode T; A08 ex5/mq5 not byte-identical)
NEXT_PLAN_VERDICT: ENDORSE_WITH_CHANGES
TOP_3_OWNER_ACTIONS:
  1. Rebuild + re-version the tester pack from current source (include Mode T + recompiled ex5); fix VERSION SHA.
  2. Rule on the R1 scarcity track (dated ruling) — it is the ceiling on all economic evidence.
  3. Commit the untracked design-lock docs; schedule the EA chart-attach + unattended soak (only path to ops evidence).
LOGIC_CHANGED: NO
EVIDENCE_ROOTS_USED:
  00_LOCKED/ (LOCKED_DECISIONS, POST_V1_PLAN_OF_ACTION, PRODUCT_RUNTIME_CONTRACT, V1_1_RUNTIME_BASELINE_FREEZE, MODE_T_CONSOLE_MARKER_DESIGN[untracked]),
  04_SRC/smc/ (126 files / 19,359 LOC; backtest/fill_model.py, triggers/base_trigger.py, live/mode_t.py, live/loop.py, orchestration/multi_tf_runtime.py, risk/risk_engine.py),
  04_SRC/tests/ (120 files; test_locked_constants, test_fr2_sl_tp_routing, test_structural_tp_feed, test_perm_hardening, test_live_phase7, test_mode_t),
  05_MQL5_SAFETY/SMC_Safety_Watchdog.{mq5,ex5},
  dist/ (SMC_v1.1-test.7_tester.zip, VERSION.txt, mql5/*.ex5, 04_SRC/smc/live/, TESTER_README.md),
  config/ (live_demo.json, live_tester.json),
  06_RESEARCH/ (INDEPENDENT_PROJECT_AUDIT_2026-10-15.md, FROZEN_FUNNEL_6M_NEW_CONTRACT_REPORT.md, PRODUCT_BASELINE_6M_COSTS_ON_REPORT.md, HEARTBEAT_FIX_A_RECONNECT_NOTE.md, MODE_T_IDEA_VS_IMPL_AUDIT.md),
  git (tag v1.1-pre-mode-T -> 11b0889; main ahead 1 of origin/main),
  logs/ (.ex5/EA logs, events.log)
```

---

*End of audit. No code, thresholds, strategy rules, or governance files were changed
by this engagement (`LOGIC_CHANGED: NO`).*
