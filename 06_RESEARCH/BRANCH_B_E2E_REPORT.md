# BRANCH B — E2E REPORT (product path only)

**Verdict: `DEFER_RECOMMENDED`** (factual state: **BLOCKED** — structural, not a bug).
**`LOGIC_CHANGED: NO`** · **`CODE_CHANGED: NO`** · **B routes: 0** · **B fills: 0**
**Window:** exec 2025-09-01 → 2025-11-30 UTC (M5) — the same frozen liveness window.
**Authority:** Lead Architect *BRANCH B — E2E engineering (product path only)*.
**Phase 0 pack:** `06_RESEARCH/BRANCH_B_ROOT_CAUSE.md`.

---

## 1. One-line answer

Trigger B never reached a route because **B's entry is anchored to a 5-wave impulse,
not to the POI**, while the locked C3 gate requires the completion bar's **close to
sit inside the POI body**. In this window the 50–61.8 % fib band sat **entirely
outside** the POI for four of the five completions (and overlapped it by only
0.08 ATR for the fifth), so C3 rejected all five at plan construction. No bug, no
config to restore, no placement gate involved: the two rules are individually
intentional and geometrically incompatible for this branch.

---

## 2. Funnel — before / after

| Stage | Before (liveness, 2026-11-25) | After |
|---|---:|---:|
| D1 episodes by the completion bar | 14 (6 already traded by F) | **14 (reproduced)** |
| B completions at H1 index 1717 | 5 | **5 (reproduced exactly)** |
| C3 `not_in_between` rejects | 5 | **5** |
| Routes | **0** | **0** |
| Risk-seam submissions | 0 | 0 |
| Placed / fills | **0 / 0** | **0 / 0** |

**No re-run of the 3-month funnel was performed, and none is claimed.** The Phase-0
harness stops at the completion bar and reproduces the audited fact exactly (same 5
POIs, same bar, same C3 result, `RECONSTRUCTION_OK = true`); because nothing changed,
a full re-run would only re-measure the same composition for ~77 minutes.

The reproduction is adversarial, not circular: the first attempt produced **11**
routes and the fail-loud check rejected it, because a stubbed scan never consumed the
six D1 POIs that had already been traded by F. Running the real D1 scan — the only
tier B can use — consumed them through the engine's own `_win` and left exactly five.

---

## 3. Root cause (single statement)

> **B's fib-band entry is anchored to the impulse; C3's validity is anchored to the
> POI body.** B fires on the first close into the 50–61.8 % retracement of an impulse
> that begins at `impulse.origin_level` and runs away from the zone; for a 7.02-ATR
> impulse the band is 50–61.8 % back from the wave-5 extreme, which placed the entire
> band above the POI body for `poi-004029/-004092/-004154` (+157.6) and `poi-004759`
> (+16.0), and left only a 1.663-unit overlap for `poi-004032`. C3 requires the
> completion close inside the body, so all five were rejected before any route.

Numbers and the exact code path: `BRANCH_B_ROOT_CAUSE.md` §3–§4.

---

## 4. Code citations (the whole B path)

| Step | Where | What decided B |
|---|---|---|
| Tier membership | `product_menu_mtf.py:239-254` | B is in `_DAY_TRIGGERS` (all six) and **excluded** from `_TIER_ADF` → D1→H1 only |
| Confirmation | `ProductMenuEngine._route_for(episode, H1)` | 5 routes produced at H1 index 1717 |
| B entry rule | `trigger_b_leading_diagonal.py:14-18, 40-62` | `entry = wave5 ∓ FIB_MIN × height`; `FIB_MIN/MAX` marked **UNFROZEN** in the header |
| C3 gate | `in_between.py`; `pipeline_bridge.py:180-251` (`candidate_from_route(completion_price=…)`) | `trigger_in_between(close, zone)` → `False` ×5 |
| Reject recorded | `product_menu_mtf._win` → `_candidate` returns `None` | `rejected_H1_not_in_between`; episode stays **ACTIVE** |
| Nothing downstream | `PipelineAdapter.queue_menu_candidate`, `BacktestRunner` | never reached for B |

**C3 ≠ the far-outside-F rule.** C3 is exact completion-close containment at plan
time; the F block was R7 `skip_place_far_from_zone`, an ATR distance band at placement
time that *defers* via an R9 intent. Different stage, metric and remedy — so the
FR-3.1 zone-anchored entry cannot help a branch that never reaches placement.

---

## 5. Architect options (none implemented)

**Option 1 — ACCEPT `SIGNAL_ONLY` (recommended for this window).**
Record B as *signal-only on the product path*: it completes, and the locked C3
contract rejects an out-of-body completion. No code, no constants, no tier change.
Consequence: B stays outside any "all branches fill" claim.

**Option 2 — DEFER B.** Park the branch until a policy ruling says what B is for.
No code.

**Option 3 — Rule a B-specific entry-anchor change.** Give B a zone-anchored entry
(or a documented C3 exemption for wave-based entries). This is an **entry/edge design
change**, not a repair: it changes what B trades, must be dated, and must state
whether the fib band or the zone owns entry, SL and TP. Not implemented here.

**Option 4 — Re-rule C3's scope globally.** e.g. containment only for zone-anchored
triggers. This changes the validity contract for every branch (A/F included) and
requires a master-card §3.4 supersession. Not implemented, and explicitly not
proposed by engineering.

**Options that were refused on principle:** widening `ZONE_REFINEMENT_ATR`, deleting
or loosening C3, force-routing B so it can "fill". Each would convert a documented
contract into a fill.

---

## 6. Why no code changed

1. Both rules are class **(a)** and the failure is their *interaction*, not a
   misapplication of either (`BRANCH_B_ROOT_CAUSE.md` §5).
2. There is **no (c)** to restore: no flag, constant, allow-list or tier setting
   participates in this interaction (`ZONE_REFINEMENT_ATR` is not on the B path).
3. Changing B's anchor or C3's scope is an edge/validity decision that the task bans
   without a ruling, and the Phase-1 rule says stop when every death is policy.
4. The six D1 POIs that *did* trade in the same window were all **F** confirmations
   on the same episodes — B is not competing for them; it simply never became a plan.

No test was added because no production behaviour changed. No `04_SRC` file, no
`locked_constants.py` value and no `parallel_books` / live default was touched. The
new harness (`06_RESEARCH/scripts/branch_b_geometry.py`) is research-only and writes
gitignored artifacts.

---

## 7. What "LIVE" would require (definition kept honest)

Success was **≥1 B-attributed fill on the product path in the pre-registered
window**. B has **0 routes**, so the chain cannot complete without either moving B's
entry anchor or relaxing C3 — both policy decisions. `BLOCKED` /
`DEFER_RECOMMENDED` is reported rather than a fabricated fill.

---

## 8. Limits

- The Phase-0 harness scans **only the D1 tier** for real (B's only confirmable
  tier) and stubs the other tiers; that is sufficient for every B-visible event but
  it is not a full 3-month funnel re-run, and no determinism/byte-identity claim is
  made.
- The geometry is a single completion bar (one shared B signal over five POIs). It is
  exact for the audited window; it is **not** a claim about how often B's band could
  overlap a zone in other windows.
- The three identical-zone POIs (`poi-004029/-004092/-004154`) are nested/duplicate
  structures; the one-plan observation is recorded, not "fixed".
- No expectancy, PF, win-rate or edge statement is made.

---

## 9. Governance

- Deliverables: this report + `06_RESEARCH/BRANCH_B_ROOT_CAUSE.md` + harness
  `06_RESEARCH/scripts/branch_b_geometry.py`; artifacts
  `06_RESEARCH/results/branch_b_geometry/` (gitignored).
- `SESSION_HANDOFF.md`, `POST_V1_ACTIVE_TODO.md`, `CHANGELOG.md` updated.
- **NEXT = Architect accept B verdict → Branch C only.** A stays closed (DEFER);
  C/D/E remain frozen until their turn; F untouched.
