# BASELINE_COMPLEX_V1_1 — COMPARISON POINT (FROZEN)

**Banner: COMPARISON POINT ONLY — NOT A DESIGN TRACK — NO EDGE CLAIM.**

Authority: Architect 2026-10-21 (Part 0 of the DUMB FLOWCHART V1 engagement —
freeze the current complex baseline before a simple parallel path is designed).

This document freezes, by citation rather than re-measurement, what
`COMPLEX_V1_1` was **at the moment a simpler design track was first
considered**, so that any later A/B comparison has a dated, fixed reference.
No capture was re-run; every number below cites the report that already
measured it.

---

## 1. Git / product identity

| item | value |
|---|---|
| **Name** | `COMPLEX_V1_1` — multi-TF (H4+H1 detect, D1→M8) + ZoneDedup retire lifecycle (episode-owned keys) + structural TP feed + seek/scan posture stack + full five-pillar validation + trigger matrix A–F |
| **Tagged commit (frozen)** | `b5e8c53` — *docs(locked): record scarcity-stack commit SHAs in handoff and changelog* (`main`) |
| **Scarcity-stack SHAs that produced the measured book** | `e1d1893` feat(orchestration): ZoneDedup retire with episode lifecycle (LEG 5b) · `14967bd` docs(research): LEG 1–6 · `0130081` docs(locked) · `51dee42` ops(demo) · `7e3288b` fix: commit `smc.backtest.cost_model` |
| **Working tree at freeze** | `main` @ `b5e8c53` + the 2026-10-20/21 *unstaged* research/locked/live-residual files (documented, deliberately uncommitted; see SESSION_HANDOFF 2026-10-20 (7)). Strategy files relevant to the frozen book (`multi_tf_runtime.py`, `pipeline_adapter.py`, `runner.py`, `positions.py`, `locked_constants.py`) match the committed freezes of the scarcity stack. |
| **Product tree flags at freeze** | `zone_dedup_retire=true`, `retire_result_probe=1`, `register_requires_owner=true`, product H4+H1 (Phase-D ops preflight, 2026-10-20) |

*Product identity statement:* COMPLEX is the whole current stack — nothing in
it is switched off, and this freeze does **not** imply any part of it is
retired. `LOGIC_CHANGED: NO` applies to the strategy code between the tagged
scarcity commit `e1d1893` and this freeze (verified: `locked_constants.py`
diff empty; no `04_SRC/smc/**` edit on the working tree since `b5e8c53`).

---

## 2. Frozen diagnostic windows already measured

All four windows were measured with the *same* composition and the *same*
frozen metric helpers; W2/W3 are byte-stable books reused across legs.

| window | range | n | principal reports |
|---|---|---|---|
| **W1** | `2024-06-01 → 2024-11-30` | 75 | `06_RESEARCH/TP_DISTANCE_EXIT_CLASS_CORRELATION_REPORT.md` (new capture `tp_distance_exit_class/W1/run{1,2}`, trades.csv md5 `b9044a19…`) |
| **W2** (= prior Window B) | `2024-12-01 → 2025-05-31` | 44 | `POST_DEDUP_EDGE_STABILITY_REPORT.md` (book `post_dedup_edge_stability/run1`, `f74eba39…`) · `EXIT_ANATOMY_DIAGNOSTIC_REPORT.md` (Window B) |
| **W3** (= prior Window A) | `2025-06-01 → 2025-11-30` | 58 | `POST_DEDUP_EDGE_DIAGNOSTIC_REPORT.md` (book `zone_dedup_lifecycle/run1/…`, `47688425…`) · `EXIT_ANATOMY_DIAGNOSTIC_REPORT.md` (Window A) |
| **W4** | `2025-12-01 → 2026-03-31` | 55 | `TP_DISTANCE_EXIT_CLASS_CORRELATION_REPORT.md` (new capture `tp_distance_exit_class/W4/run{1,2}`, trades.csv md5 `8254c468…`) |

Pointers: `06_RESEARCH/POST_DEDUP_EDGE_*` · `06_RESEARCH/EXIT_ANATOMY_DIAGNOSTIC_REPORT.md` ·
`06_RESEARCH/TP_DISTANCE_EXIT_CLASS_CORRELATION_REPORT.md`. Every artifact cited here
carries the banner **DIAGNOSTIC — NOT EDGE / NOT LIVE VALIDATION**.

---

## 3. Headline facts for later comparison (diagnostic only)

- **Thin fills.** Roughly 40–75 closed trades per 6-month window class
  (44 / 58 / 75 / 55 observed) out of >558 armed episodes per window — a
  ~6–14 % fill rate over arm, reached through the full pillar + trigger +
  skip_place funnel. Any successor path must be judged against this count
  class, not against an expectation of continuity.
- **Mixed paths, UNSTABLE exit shape.** The A/B pair verdict is
  `UNSTABLE_SHAPE` (dominant close_kind flipped TP→SL; dominant hypothesis
  bucket flipped `TP_REACHED`→`SL_THEN_TP_PATH`); exit anatomy showed the
  stop-dominance is *trailing-heavy, not loss-heavy* (20/28 of W2's stop
  exits closed positive).
- **TP distance tracks exit class within windows.** Four-window leg: pooled
  bucket TARGET rates 0.615 (≤0.75R) / 0.364 (0.75–1.25R) / 0.101 (>1.25R),
  monotone in **every** window; window-level median distance does **not**
  order the windows by TARGET share (Spearman −0.6, orders disagree) — the
  discriminating quantity is placement, not the median. Structural targets
  sat at 1.000R in W2 vs 0.449–0.508R in W1/W3/W4 — a **W2-specific
  condition**, not a general law.
- **No live edge claim.** No diagnostic above asserts expectancy, edge, or
  promote/demote evidence; `pair_stability`, `exit anatomy`, and the four-window
  correlation are all explicitly non-edge. COMPLEX's fill class is what it is
  and the instruments ("DEMO-GATED", `dry_run=true` ops documents) are what
  they are.

---

## 4. Explicit statement

> **`COMPLEX_V1_1` remains frozen for A/B comparison. `DUMB_FLOWCHART_V1` is a
> parallel design track. Neither replaces the other until a dated Architect
> promotion ruling.**

- This freeze is a *documentation* act: no `04_SRC/smc/**` strategy code, no
  `locked_constants.py` threshold, and no product flag is touched by it.
- The comparison point is `main` @ `b5e8c53` + the four frozen books listed in §2.
- If either track changes (constants, detection, funnel seams), the freeze must
  be re-dated with a new SHA before an A/B comparison is run against it —
  silent drift of the comparison point is forbidden.

---

**Ledger cross-refs:** SESSION_HANDOFF 2026-10-21 (2) — baseline freeze +
DUMB design lock · CHANGELOG 2026-10-21 (2) — docs only ·
`00_LOCKED/POST_V1_ACTIVE_TODO.md` — DUMB design lock entry.
