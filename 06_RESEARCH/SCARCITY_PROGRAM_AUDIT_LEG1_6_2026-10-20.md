# SCARCITY PROGRAM AUDIT — LEG 1–6 + ZONEDEDUP LIFECYCLE (INDEPENDENT)

> **DIAGNOSTIC — NOT EDGE.** Findings only; no production code change, no
> threshold edit, no fix implement in this engagement. Written as an
> independent reviewer (not the leg implementer): every number below was
> re-read from on-disk artifacts, not taken from chat memory or the legs'
> own prose without cross-check.

**Date:** 2026-10-20 · **Authority:** Lead Architect request 2026-10-20 ·
**Protocol:** `00_LOCKED/LEAD_ARCHITECT_ROLE_AND_PROTOCOL.md` (source-of-truth
order §2; FAITHFUL / PARTIAL / SILENT / DRIFTED / DEFERRED classification §5).

BASELINE OF THE WORKING TREE audited: uncommitted on base commit `9b649d5`
(128 modified/untracked paths incl. this program's edits and earlier
live-ops edits — see finding M-3).

---

## Executive verdict

**AUDIT_STATUS: PASS_WITH_FINDINGS.** The claimed chain LEG 1 → LEG 6 is
coherent, every leg's headline numbers reproduce from on-disk artifacts
(no DATA_GAP found in any mandatory artifact), the ZoneDedup design →
implement fidelity is verified rule-by-rule against code, and the suite
re-runs green at **1,236 passed / EXIT=0** with an empty
`locked_constants.py` diff. No overclaim language was found in any report.
Two recorded deviations in LEG 6 (a fired pre-registered gate replaced by
an evidence-anchored counterfactual; an extended join clause) are honestly
documented but constitute methodology risk that the Architect should
re-ratify rather than wave through. Live residuals (in-memory dedup reset
on restart, unproven console/heartbeat load at 20× arm density) block any
live/paper promotion of the new class, not the research commits.

## Per-leg verification table

| Leg | Claim | Verdict | Evidence (re-read, not quotes) |
|---|---|---|---|
| **LEG 1** | `HOLD_P2_FVG` — A dominates B; funnel exact | **PASS** | `results/near_miss_p2_fvg/summary.json`: `populations A/B/C = 54/88/7`, `A∩B = A∩C = 0`, cross-TF sensitivity 40/40/6 — matches report §4 exactly; `interpretation.label = HOLD_P2_FVG`; capture `pass_events = 2021`, `event_rows = 43004`. Pre-registered rule quoted in-report §7 with the fired branch verbatim. |
| **LEG 2** | Architect R-HOLD on P2 | **PASS** | [TECHNICAL_OWNER_PLAN_POST_PROBE.md:90](00_LOCKED/TECHNICAL_OWNER_PLAN_POST_PROBE.md) `## LEG 2 — ARCHITECT RULING` `Status: [x] DONE — R-HOLD HOLD_P2_FVG`; no proposal authorized. Chain precedence enforced in every later report header. |
| **LEG 3** | `FILL_PATH_HEALTHY` (basis: 18m secondary) | **PASS** | `results/fill_takeability/summary_all.json`: `basis = secondary`, `n_placed_secondary = 14`, `secondary.fates.FILLED = 14`, `interpretation.label = FILL_PATH_HEALTHY`, all integrity zeros (`unaccounted/double_terminal = [0]`, `fill_without_touch = 0`); primary fates `{FILLED 3, TOUCHED_ONLY_AFTER_EXPIRY 1}` reported in-report §4 and reproduced. Windows never pooled; 24m abort disclosed (`secondary_24m_ABORTED.log` on disk). |
| **LEG 4** | `ARM_FILTER_IS_BOTTLENECK`, `WIRING_BUG: NO` | **PASS** | `results/passed_to_armed/summary.json`: `dispositions` ARMED 30 (1.48%), `SKIP_DEDUP_EPISODE` 1991 (98.52%), every other bucket 0 with `code_impossible_today` flags; `dedup_geometry.coverage_median = 0.460894` (= report's 0.461), age median 29.542 d / max 140.292 d; `integrity.*` all-match booleans true; bucket sum 2021. |
| **LEG 5** | Design: retire on no-obligation + (VIOLATED \| past give-up); F-1 correction | **PASS** | `results/zone_dedup_lifecycle/{run1,run2}/retire_sweeps.jsonl.gz`: **448 sweeps each**, final rows `retired_total_after 606 / live_keys_after 0` **both runs**; monotonicity check over all rows: **0 violations**, max live keys 5. Design R1–R8 sections exist verbatim in the design doc (:200–:341). F-1 treated as a documented code fact and left unchanged by design (see fidelity matrix). |
| **LEG 5b** | armed 30→606; dedup 1991→1415; retired 606; double-arm 0; suite ~1236 | **PASS** | Sweep audit above + `results/summary.json` (both runs) funnel counters: 2979/43004/2021, armed 606, duplicates_suppressed 1415, routes 219, placed 65, fills 58; `summary.retired_total = null` seam **disclosed** in the note (§3.1) with the sweep audit as authority — disclosed, not hidden. Suite re-run independently: **1236 passed EXIT=0**. `locked_constants.py` diff empty (git). |
| **LEG 6** | `NEW_ARMS_SIMILAR_TO_LEGACY` — A30/B576; Δ within ±10 pp | **PASS_WITH_FINDINGS** (methodology, M-1) | `results/post_dedup_new_arm_quality/results/summary.json`: n_A 30 / n_B 576, `cf_ids_equal_LEG4 = true` (30/30 id-set equality), `b_blocker_join_gaps = []`, join rules 573 first-match + 3 displacement + 0 unverified, double-arm 0, Δ route +2.95 pp / fill +3.05 pp; lifecycle `trades.csv` SHA re-confirmed byte-identical to 5b run1. Counterfactual capture: 30 arms / 10 routes / 4 placed / 3 fills / 0 retires — reproduces LEG 4's funnel **and** id set. |

**CHAIN_COHERENT: YES.** Each report cites its predecessor ruling correctly
(LEG 1 → LEG 2 HOLD → LEG 3 → LEG 4 → LEG 5 design → Architect ACCEPT →
LEG 5b → LEG 6 measured); owner-plan LEG sections carry dated statuses and
return-block keys; every leg uses the same frozen 6m window
(35,725 exec M5 bars, M1 load 2025-05-01) and the identical
`phase3_structure_funnel.run` composition — the shared-window funnel
(2979 / 43004 / 2021 / 30) is reproduced byte-for-byte in every capture.

## Critical / Major / Minor findings

**Critical: 0.**

**Major**
1. **(M-1, LEG 6 pre-registration discipline).** The pre-registered
   cohort-A gate ("n_A == 30 AND id set equals LEG 4's frozen set") **fired
   on its first honest evaluation** (append-only replay over the lifecycle
   stream: n_A = 25, 8 LEG 4 ids never re-arm, 3 new firsts). The final
   classification rests on two recorded amendments: (a) replacement of the
   LEG-4 anchor with an append-only **counterfactual capture** whose funnel
   (30→10→4→3) and 30-id set reproduce LEG 4 exactly — a genuinely stronger
   anchor, but created *after* the original gate failed; (b) the
   blocker-retire join extended with the displacement clause for 3 chained
   arms (poi-006662/033642/054982). Both are fully evidenced in
   `POST_DEDUP_NEW_ARM_QUALITY_REPORT.md` §2.3/§2.5 and
   `results/summary.json` retains every fired lane. **This is recorded
   honesty, not label shopping — but it is a deviation from pre-registration
   discipline, and the final `SIMILAR` label should be re-ratified by the
   Architect with the amendment trail in front of them, not accepted on the
   implementer's say-so.** No number was inverted by the amendment (all
   funnel deltas were computed identically in both the pre- and
   post-amendment form — verified by re-running the replay analysis, whose
   intact artifacts are retained as `results/summary_replay_only.json`).
2. **(M-2, live residual risk).** The lifecycle composition now arms up to
   **29.99%** of passes (vs 1.48% pre-LEG-5b). Every live-surface load test
   in the tree (console blocks, heartbeat writes, marker cadence) was
   validated against the 30-arm baseline. No soak test exists for the
   606-class density on the live/paper path, and the in-memory registry
   resets on restart (design F-7): a restarted session may re-arm
   structures that were live before the restart, and with 20× density the
   practical exposure of that residual changes class. Blocks live/paper
   promotion; **does not block research commits.**
3. **(M-3, uncommitted tree).** Every artifact this program produced,
   including the LEG 5b product code (`multi_tf_runtime.py`,
   `pipeline_adapter.py`, `runner.py`, `paper/runner.py`,
   `episode_store.py` + 3 test files) sits **uncommitted** on base
   `9b649d5`, mixed with ~110 modified/untracked paths from earlier
   programs (heartbeat/mode-T/live-ops, already separately approved).
   Nothing in this audit changes that state; the owner decides the commit
   split. Until committed, the "implement" leg exists only in the working
   tree.

**Minor**
1. `(minor-1)` `results/zone_dedup_lifecycle/{run1,run2}/summary.json`
   carries `retired_total: null` (composition imported the runtime class
   before the capture seam wrapped it; note §3.1). The sweep audit is the
   authority and both runs agree (606 each); cosmetic, disclosed.
2. `(minor-2)` [pipeline_adapter.py:463](04_SRC/smc/backtest/pipeline_adapter.py)
   — `_retire_dead_keys`'s fail-safe `except Exception: return` (design R6)
   would silently swallow a real defect inside the sweep. Counters and the
   sweep audit mitigate; consider a stdout line on unexpected failure in a
   future leg (design change required — out of this engagement's scope).
3. `(minor-3)` `06_RESEARCH/scripts/d1_f1f2_resample.py` /
   `h4_poi_confirmation.py` still call old `register(zone)` signature —
   disclosed in the note; not product code; would raise `TypeError` on next
   use.
4. `(minor-4)` LEG 3's secondary capture determinism is proven at the
   analysis level only (4.25 h capture not re-run) — disclosed in-report.
5. `(minor-5)` LEG 4's blocker *age* is age since that blocker **armed**,
   not since its episode died (report limitation §10.5) — the "dead for
   weeks" reading rests on the never-forgets code fact, correctly labelled.
6. `(minor-6)` LEG 4 §9 secondary 18m funnel is used as corroboration of
   dominance only (98.78% dedup event-rate) — correctly scoped, carries no
   coverage geometry, never pooled.

**Answering the mandatory checklist:**

1. **Numbers:** report tables vs `summary.json` — verified per-leg in the
   table above; no mismatch found (LEG-4 coverage median 0.460894 →
   "0.461", ages, dispositions, fates, medians all agree).
2. **Pre-registration:** LEG 1 (§7 rule quoted, branch fired), LEG 3
   (label rule + n≥10 gate written before runs, basis = secondary because
   primary n=4), LEG 4 (bucket + label rule fixed pre-run), LEG 5b (gates
   A–F pre-registered in the design doc), LEG 6 (rule frozen in the script
   docstring; **two recorded amendments — see M-1**).
3. **Bans:** `locked_constants.py` diff **empty** (git + audit re-run);
   no pillar/trigger/fill/expiry/zone-band edit anywhere in LEG 1–4/6;
   LEG 5b's edit surface is exactly the five files per the design.
4. **Dedup:** `seen` semantics unchanged (owner-blind 4-tuple element,
   runtime :173–183); owner required (`TypeError`, :193–196); `retire`
   idempotent, miss-counted, by stored owner string (:203–223); R9 intents
   carried as obligations in **both** runners (runner.py:654–656,
   paper/runner.py:950–952); fail-safe prune (adapter :463) with no
   handle → no-op (:430–432).
5. **Lookahead / bar order:** design line 144 is normative ("a key retired
   at bar b can first [affect] ... the next batch"); implementation
   retires in the per-bar prune step (engine first :394, registry second);
   empirically verified by the LEG 6 capture's strict event ordering —
   arm rows precede that bar's retire rows — and the lifecycle run's
   `trades.csv` byte-identity proves reads changed nothing.
6. **Counterfactual hygiene (LEG 6):** the only difference between the two
   captures is the `_retire_dead_keys` wrapper no-op'ing under
   `_MODE == "append_only"` (post_dedup_new_arm_quality.py:186–189 — the
   sole retirement seam: both `dedup.retire` call sites live inside it,
   adapter :438/:455); all seams restored in `finally`; mutual isolation is
   proven *by output*: the lifecycle capture is byte-identical to 5b run1
   `trades.csv` while the counterfactual's differs (expected — different
   arming; disclosed).
7. **Overclaim:** none found — see §"Overclaim / methodology risks".
8. **Live residual:** yes — M-2 (restart reset F-7; density load unproven).
9. **Commit readiness:** YES_WITH_CAVEATS — see §"Commit readiness".
10. **Prior external audit hazards:** all four resolved in the final tree —
    (a) mid-edit syntax: all five touched product files `py_compile` clean
    today; (b) episode_store register owner: `owner_id=...episode_id`
    passed at [episode_store.py:368](04_SRC/smc/orchestration/episode_store.py)
    and :416; (c) retire-miss spam: `_retire_sent` bookkeeping +
    test `test_retire_sent_bookkeeping_prevents_miss_spam`; (d) R9 retain:
    both runners carry alive intents.

## Dedup implement fidelity matrix (design → code → test)

| Rule | Design | Code (file:line) | Test | Verdict |
|---|---|---|---|---|
| **R1** owner-attributed key, owner required, geometry unchanged 6 dp | design :200 | [multi_tf_runtime.py:185–201](04_SRC/smc/orchestration/multi_tf_runtime.py) (`TypeError` if owner None), register sites **after successful arm only** :565 / :658 | `test_register_requires_owner_id`, `test_register_geometry_unchanged_and_owner_stored` | FAITHFUL |
| **R2** `seen` unchanged, retired keys removed (never flagged) | design :214 | :173–183 (owner-blind 4th element ignored, inclusive overlap, first match) | `test_seen_is_owner_blind_and_overlap_rule_unchanged`, `test_retire_removes_key_so_seen_frees_the_zone` | FAITHFUL |
| **R3.1** death = no live obligation AND (VIOLATED OR `bar_index > arm_bar + poi_give_up_bars()`) | design :225 | [pipeline_adapter.py:412–464](04_SRC/smc/backtest/pipeline_adapter.py): obligations `retain ∪ _workflows`; VIOLATED-past-window branch; FRESH-past-give-up branch | `test_violated_without_obligation_releases_key`, `test_violated_with_open_position_keeps_key`, `test_inside_give_up_window_never_retires_while_fresh`, `test_fresh_past_give_up_releases_key`, `test_workflow_live_tested_episode_keeps_key` | FAITHFUL |
| **R3.2** one call site in `prune_terminal_pois`, engine first, registry second | design :253 | adapter :394 comment + `_retire_dead_keys(pruned, …)` call at :394; runner/paper obligations at runner.py:654 / paper:950 | `test_retire_sent_bookkeeping_prevents_miss_spam`; sweep audit shows both sources engaged (11 engine-pruned in-window) | FAITHFUL |
| **R3.3** ordering: retire after arm batch, before next batch's scan | design :271 | prune runs in the runners' per-bar step after the arm batch; LEG 6 capture ordered events confirm | empirical (capture ordering) | FAITHFUL |
| **R3.4** handle identity — adapter retires from the runtime's registry | design :276 | adapter `bind_dedup_registry` :397–410 (different-handle rebind raises `ValueError`); runtime binds every batch | `test_runtime_binds_its_registry_onto_the_adapter`, `test_rebinding_a_different_handle_refused` | FAITHFUL |
| **R4** no float re-derivation, no new tolerance/metric | design :283 | `seen` compares unrounded query vs stored 6 dp bounds; `retire` looks up by stored owner string | design-consistency + geometry tests | FAITHFUL |
| **R5** keys shared across detection TFs (no per-TF split) | design :294 | one registry, no TF component in the key | verification: LEG 6 cross-TF blocking visible in capture | FAITHFUL (residual disclosed) |
| **R6** idempotent, misses counted, no clear-all, counters, fail-safe | design :305 | `retire` :203–223; `_retire_dead_keys` no-handle no-op + broad except :430–463 | `test_retire_idempotent_and_misses_counted`, `test_unbound_adapter_retirement_is_a_noop` | FAITHFUL (broad except = minor-2) |
| **R7** non-goals (no P2/trigger/fill/expiry/Mode T/posture change, no cap, no score) | design :325 | no such edit in the diff (git stat, this leg) | `locked_constants.py` diff empty | FAITHFUL |
| **R8** edge-touch residual (zero-area touches still suppress) | design :337 | unchanged inclusive predicate (11 in-window cases remain) | untouched by design | DEFERRED (documented residual) |

**DEDUP_FIDELITY: PASS** — no rule implemented contrary to design; R1
correction noted: the design's `_may_route(bar=None)` retention
distinction (F-1) is explicitly *not* an obligation, and the sweep
correctly receives only the runner-supplied obligation ids
([adapter :388–393](04_SRC/smc/backtest/pipeline_adapter.py)).

## Overclaim / methodology risks

* **Found overclaim language: NONE.** All six reports open with the
  `DIAGNOSTIC — NOT EDGE` banner; LEG 3's `FILL_PATH_HEALTHY` carries its
  own counter-text ("8 of 14 secondary fills stopped out; conversion not
  quality"); LEG 6 forbids PnL interpretation of "similar"; LEG 4's label
  names the loss with no prescription; LEG 1's HOLD branch is textual, not
  numeric-optimistic. No rate, expectancy, Sharpe or win-rate is claimed
  anywhere in the chain.
* **Methodology risks:** (M-1) above — post-hoc amendment in LEG 6.
  Secondary risks that are *disclosed* and bounded: LEG 6's A-membership
  relies on deterministic poi-id matching (verified exact for 22/30 cf
  spaces; 8 matched by overlap with all cf spaces claimed exactly once);
  the counterfactual is a research-harness seam (no-op inside
  `_retire_dead_keys`), not a shipped configuration; LEG 5b's armed delta
  (+576) is a designed consequence, not a validation improvement, and the
  reports never frame it as signal quality (exit mixes are reported raw).

## Commit readiness

**COMMIT_READY: YES_WITH_CAVEATS.**

* Blockers/caveats before any commit decision:
  1. **Uncommitted mixed tree** (M-3): the LEG 5b product edits must be
     committed as their own commit (audit-consistent scope: the 5 product
     files + 4 test files + the two governance note pairs); the ~110
     unrelated live-ops paths belong to earlier programs and should not
     ride along silently (base `9b649d5`).
  2. **Research artifacts are gitignored** (by convention) — the committed
     history will carry reports + scripts but not captures; results/ are
     reproducible from the scripts (documented runtimes: ~15 min per 6m
     capture, 15.3 h secondary, ≈30 min per window; correct).
  3. **Live/paper promotion is NOT ready** (M-2): F-7 restart reset +
     unproven 606-density load; the owner's demo soak and `.ex5`
     discipline from the earlier live-ops approval remain outstanding.
  4. Two `d1_f1f2_resample.py` / `h4_poi_confirmation.py` scripts will
     `TypeError` on next use (minor-3) — one-line owner argument; their
     breakage is disclosed, not a blocker.

## Recommended next actions (max 5, ordered)

1. **Architect disposition of the LEG 6 amendment trail (M-1):** ratify or
   re-open the `SIMILAR` label with the recorded deviations §2.3/§2.5 in
   front of you; the artifacts are frozen either way.
2. **Scot the live residual (M-2):** require an explicit design ruling on
   restart-reset (F-7) plus a console/heartbeat soak at lifecycle density
   on the demo composition *before* any product-mode promotion; no rule
   change is implied.
3. **Commit split (M-3):** commit the LEG 5b product + test files and the
   program docs as a dedicated commit; leave the live-ops paths for their
   own decision; push is the owner's separate authorization.
4. **Fold minor-2 into a future leg:** replace `_retire_dead_keys`'s silent
   fail-safe with a counted/logged failure path (design R6 amendment;
   requires its own dated ruling — not in this engagement).
5. **Retire the two stale research scripts' signatures** (minor-3) on their
   next-use date, so the old `register(zone)` call cannot produce a
   misleading hard error without context.

---

## Artifacts verified on disk (this audit)

`00_LOCKED/{TECHNICAL_OWNER_PLAN_POST_PROBE,SESSION_HANDOFF,CHANGELOG,POST_V1_ACTIVE_TODO,LEAD_ARCHITECT_ROLE_AND_PROTOCOL,LOCKED_DECISIONS}.md` ·
`06_RESEARCH/{NEAR_MISS_P2_FVG_COUNTERFACTUAL,FILL_TAKEABILITY,PASSED_TO_ARMED_ATTRIBUTION,ZONE_DEDUP_LIFECYCLE_DESIGN,ZONE_DEDUP_LIFECYCLE_IMPLEMENTATION_NOTE,POST_DEDUP_NEW_ARM_QUALITY}_REPORT*.md` ·
`04_SRC/smc/{orchestration/multi_tf_runtime,backtest/pipeline_adapter,backtest/runner,paper/runner,orchestration/episode_store}.py` ·
`04_SRC/tests/test_zone_dedup_lifecycle.py` (16 tests, read in full) ·
results: `near_miss_p2_fvg/summary.json`, `fill_takeability/{summary_all.json,secondary_18m/summary.json}`, `passed_to_armed/summary.json`, `zone_dedup_lifecycle/{run1,run2}/retire_sweeps.jsonl.gz`, `post_dedup_new_arm_quality/results/{summary.json,cohorts.csv}` (606 rows) ·
`06_RESEARCH/results/suite_audit_run1.log` (1,236 passed, EXIT=0).
No DATA_GAP found in a mandatory artifact.

**LOGIC_CHANGED: NO** (this audit changed no code; doc-only write).

```
AUDIT_STATUS: PASS_WITH_FINDINGS
CRITICAL: 0
MAJOR: 3
MINOR: 6
CHAIN_COHERENT: YES
DEDUP_FIDELITY: PASS
OVERCLAIM_FOUND: NO
SUITE_SPOTCHECK: 1236 passed (EXIT=0)
LOCKED_CONSTANTS_DIFF: empty
COMMIT_READY: YES_WITH_CAVEATS
TOP_BLOCKERS: [LEG6 amendment trail needs Architect re-ratification (M-1), live 20x-density soak missing + F-7 restart reset (M-2), fully uncommitted working tree on 9b649d5 (M-3)]
TOP_3_ACTIONS: [Architect disposition of the LEG 6 amendment trail, live-residual ruling (F-7 + density soak) before any product-mode promotion, dedicated commit split for the LEG 5b product+test+doc files]
LOGIC_CHANGED: NO
REPORT_PATH: 06_RESEARCH/SCARCITY_PROGRAM_AUDIT_LEG1_6_2026-10-20.md
NEXT_READY: Architect disposition of audit findings
```
