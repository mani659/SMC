# F5–F7 — MENU LIFECYCLE: arm-time integrity, §5 reconciliation, retryable winners

**Task:** Lead Architect `F5–F7 LIFECYCLE — menu causality (one PR)` (2026-11-10).
**Scope executed verbatim:** F5 `t_arm`/window integrity, F6 §5 engine reconciliation,
F7 retryable blocked menu candidates. **No structural TP, no OPT-B, no OPT-2, no
tier/trigger/threshold retune, no sizing change.** `dry_run` remains `true` in
`config/live_demo.json` (F3 live sizing pin still pending on a real terminal).

`LOGIC_CHANGED=YES` (menu causality only).

---

## 1. Defects addressed

| ID | Defect | Consequence before this change |
|----|--------|--------------------------------|
| F5 | `register_armed(poi, tf)` had no arm instant; `MenuEpisode` had no `armed_ts` | A backfilled/batched detection feed could open a one-shot window on a sweep that closed **before** the POI existed (research step 0, live startup, any HTF batch), and the winner inherited it. `product_menu.armed_ts` was always `null` (`t_arm_not_stamped` in every prior ledger row). |
| F5b | expire / open ordering was not arm-aware | An episode could be opened from a bar the arm instant had already superseded, and a pre-arm sweep could burn the POI's one shot. |
| F6 | The menu kept its own idea of POI liveness (none) | A POI that the §5 machine had already moved to VIOLATED (or that another path consumed) could still be confirmed and submitted. `_armed` also grew for the whole session: retired POIs were never dropped. |
| F7 | A menu winner was submitted **once** | If the risk engine blocked it that bar (news, session, spread, breaker, R7 distance, a broker retcode) the confirmation was destroyed even though its menu window was still open — causality inversion: the window said "live", the runner said "gone", and the window closed unplaced with no record. |

---

## 2. F5 — arm instant and window integrity

* `ProductMenuEngine.register_armed(poi, detection_tf, armed_ts=None)`.
  * `armed_ts` = the batch/research decision instant (`as_of`), i.e. the instant the
    closed-bar HTF prefixes were cut. Live: `bar.timestamp` of the execution bar the
    batch was run for — the SAME instant that already drives `run_batch(as_of=…)`.
  * `MenuEpisode` stores `armed_ts` (audit field, also stamped on the candidate).
  * **Open guard:** a detection bar opens a window only when
    `_close_ts(sweep_bar) > armed_ts`. Refusals are counted (`sweeps_pre_arm`) and
    do not consume the POI's one-shot.
  * `armed_ts=None` leaves the guard **inactive** and is counted
    (`armed_without_ts`) — never guessed. Re-arming is idempotent and the ORIGINAL
    arm instant wins; a late-supplied instant is adopted (counter decremented), so a
    POI armed without a stamp by an older caller is repaired, not re-armed.
* Call sites threaded: `LiveLoop._arm_product` (`armed_ts=bar.timestamp`),
  `LiveLoop._arm_new_pois` (`armed_ts=<newest execution bar>.timestamp`),
  `06_RESEARCH/scripts/plan_complement_ledger.py` (`armed_ts=as_of`). Old smoke
  scripts keep the `None` default (counted, not silent).
* Ordering is unchanged and still evaluated before opening (`_expire` then
  `_open_episodes`); the F2 window-open guard (`sweeps_out_of_window`) remains in
  force and is now redundant-in-depth for batched feeds rather than the only guard.

## 3. F6 — §5 reconciliation (one state store, no second copy)

* `set_state_source(resolver)` — the adapter binds `lambda poi: engine.state_machine.current(poi)`
  in `PipelineAdapter.set_menu_confirmation`, so the menu reads the pipeline's ONE
  `POIStateMachine` (never `poi.state` alone, never a copy).
* `MENU_ALLOWED_POI_STATES = {FRESH, TESTED}`:
  * FRESH — the POI is live; the menu's sweep IS its first touch.
  * TESTED — the first touch already registered; the window may still confirm.
  * CREATED is not yet validated fresh; VIOLATED is dead. Both are refused.
* Gate points: `_open_episodes` (a dead POI never opens a window) and
  `on_execution_bar` (an episode whose POI died mid-window cannot win —
  the window simply expires). Counter: `menu_blocked_by_state`.
* Unwired resolver (unit stubs, research capture) → gate OFF (`_poi_state` returns
  `None`): no invented block. A resolver fault degrades to "unknown", never to a
  block.
* `retire(poi_id)` drops the arming record and is called from
  `PipelineAdapter.prune_terminal_pois` for every engine-retired POI, so `_armed`
  is bounded by live POIs. `_consumed` is never cleared (one-shot stays one-shot).
  A consumed POI's arming record is also dropped at win time.

## 4. F7 — retryable blocked winners

* **Acceptance signal required.** `queue_menu_candidate` submits immediately (as
  before) and additionally registers the confirmation as pending **only** when the
  runner advertises `supports_candidate_outcomes`:
  * `PaperRunner` (live/paper path) → `True`, and it calls
    `adapter.notify_candidate_outcome(candidate, accepted=…, reason=…)` at every
    terminal point of `_entry_step`: risk/spread/session/etc. **block**
    (`accepted=False`), R7 deferred-to-intent (`accepted=True` — the R9 intent owns
    its own per-bar retry), dry-run placement (`accepted=True`), order rejected by
    the broker (`accepted=False`, retcode in `reason`), and a real placement
    (`accepted=True`, also via the pre-existing `on_candidate_accepted` hook).
  * Stub runners (research submit-capture) do **not** advertise it → unchanged
    single-submit semantics, no retry, no counter inflation.
* **Resubmission:** `PipelineAdapter._resubmit_menu_pending(now)` runs once at the
  top of `generate_candidates` and re-submits each pending candidate through the
  SAME `submit_entry` path (same workflow, same risk gate, same per-bar
  discipline — no bypass, no second candidate).
* **Deadline comes from the menu, never from the runner.** `MenuWinner.window_end_ts`
  is the close of the detection bar at `sweep_index + expiry_bars` when that bar
  exists, else the nominal `sweep_close_ts + expiry_bars × detection_tf.minutes`.
  It is stamped into the candidate's `product_menu` payload and parsed by the
  adapter. Unstamped candidate → no pending entry at all (no invented deadline, no
  unbounded retry); a stamp without `window_end_ts` falls back to the locked expiry
  over the stamped detection TF.
* **Claim release:** when the window closes unplaced, the pending entry is dropped,
  `menu_expired_unplaced` increments, and the POI's menu claim is released
  (`_menu_claimed_pois` / `_routed`) so the normal scan may own a still-live POI
  again. A POI retired by the engine also drops its pending entry
  (`menu_dropped_poi_retired`).
* **Counters** (`PipelineAdapter.menu_counters()`, measurement only, never read by
  a decision): `menu_submitted`, `menu_accepted`, `menu_retry_blocked`,
  `menu_resubmitted`, `menu_expired_unplaced`, `menu_dropped_poi_retired`,
  `menu_pending`. The research harness records them as `menu_retry` in its summary.

---

## 5. What did NOT change

`00_LOCKED/locked_constants.py` diff vs `baseline_pre_fix` is **empty**. Tier table
(detection TF / confirmation TFs / 20-bar expiry), trigger set, R7 band, pillar
path, risk %, sizing formula and `dry_run` are untouched. F1 closed-bar HTF and F2
full confirmation evaluation are preserved (episode/route selection code unchanged;
only the arming gate, the liveness gate and the post-confirmation retry were added).

---

## 6. Verification

Suite: `PYTHONPATH=04_SRC python -m pytest -q 04_SRC/tests --ignore=04_SRC/tests/test_review_merge_smoke.py`
→ **1437 passed, 6 skipped** (was 1413/6 at `c69d8c5`; +24 new).

New `04_SRC/tests/test_f5_f7_menu_lifecycle.py` (24):
* F5: pre-arm sweep refused + counted; post-arm sweep opens and stores `armed_ts`;
  `armed_without_ts` counted with the guard inactive; late instant adopted /
  original wins; `_armed` 3-tuple shape.
* F6: dead POI never opens (counted); POI dying mid-window cannot win while a live
  POI still can (FRESH and TESTED); unwired resolver = gate off; faulty resolver
  ≠ block; `retire` drops arming and never revives a consumed POI; adapter binds
  `engine.state_machine`; adapter prune → menu `retire`.
* F7: pending registered with the menu deadline; blocked → resubmit → accepted;
  expiry releases the claim and counts; stub runner keeps single-submit; no stamp
  → no retry; deadline fallback to the locked expiry; dead POI's pending dropped by
  prune; `PaperRunner` capability + forwarding (and optional seam for bare
  adapters); winner/candidate carry `window_end_ts`; the live ordering
  (queue → `generate_candidates` → runner drain) submits at most once per bar.

Updated existing tests for the new contracts: `test_menu_seam_integration.py`
(arming record is a 3-tuple and carries the live bar's instant) and
`test_phase01_information_set.py` (fabricated arming record uses the 3-tuple).

## 7. Optional re-run — same plan-complement window (new path only)

`PLAN_COMPLEMENT_OUT=06_RESEARCH/results/plan_complement_ledger_post_f5f7/`,
`LABEL=post_f5f7`, `LOGIC_CHANGED=YES`. `baseline_pre_fix` and
`plan_complement_ledger_post_f1f2/` were **not** touched. Diagnostic only — no
profitability or edge claim, no cross-phase improvement claim.

| metric | post_f1f2 | post_f5f7 (this run) |
|---|---:|---:|
| `REGISTER_ARMED` | 13 | 13 |
| `SWEEPS` | 13 | 13 |
| `N_WINNERS` / `N_EVENTS` | 7 / 7 | 7 / 7 |
| `PCT_PLAN_COMPLETE` | 100.0 % | 100.0 % |
| `PCT_PLAN_CONSISTENT` | 100.0 % | 100.0 % |
| `confirm_bars_evaluated` | 2154 / 185604 | 2154 / 185604 |
| `sweeps_out_of_window` | 0 | 0 |
| `sweeps_pre_arm` / `armed_without_ts` / `menu_blocked_by_state` | — | 0 / 0 / 0 |
| `armed_pois` at end | 13 | **6** |
| menu retry counters | — | `menu_submitted=7`, all retry counters 0 |

Reading (no more than the numbers support):

* **No outcome change on this window.** F5's pre-arm guard found nothing to refuse
  here (`sweeps_pre_arm=0`) and F6 never saw a dead POI
  (`menu_blocked_by_state=0`) — so the identical funnel is expected, not evidence
  that the guards are inert. The guards' behaviour is pinned by unit tests
  (`test_f5_f7_menu_lifecycle.py`), not by this window.
* **The arming book is now bounded:** `armed_pois` 13 → 6, because the 7 consumed
  winners drop their arming record (previously they lingered for the whole run).
* **F7 correctly stayed inert here:** the research harness is a submit-capture
  runner without `supports_candidate_outcomes`, so `menu_submitted=7` with every
  retry counter at 0 is the designed single-submit semantics (a live
  `PaperRunner` is the path that retries).
* **`t_arm` gap note is a harness artifact in this artifact set.** The engine now
  stamps `product_menu.armed_ts` (pinned by unit test), the harness was updated to
  read it, but this run predates that one-line reader fix, so its rows still carry
  the hardcoded `t_arm_not_stamped` annotation. The row values were not re-generated
  — re-running only to refresh a notes column was not worth another ~45 min of
  compute; the funnel numbers above are unaffected.

Artifacts (gitignored): `06_RESEARCH/results/plan_complement_ledger_post_f5f7/`
(`plan_complement_ledger.csv`, `plan_complement_summary.json`,
`PLAN_COMPLEMENT_LEDGER_POST_F5F7_NOTE.md`, `run.log`).

## 8. Known limitations / open items

* **Live pin still pending.** No MT5 terminal here; `dry_run` stays `true` until the
  first operator start prints `[sizing] PASS` (§F3 acceptance).
* F7 retry is **per execution bar**, exactly like the adapter's workflow resubmit —
  it is not an intra-bar polling loop. A confirmation blocked on every bar of its
  window ends as `menu_expired_unplaced` (now counted, previously invisible).
* The retry re-submits the SAME candidate; if the risk engine blocks for a reason
  that clears later in the window, the trade happens late inside the window. That is
  the intended F7 semantics (menu causality), not a new entry rule.
* R9 intent deferral counts as accepted: the intent path has its own retry and
  must not be double-submitted.
