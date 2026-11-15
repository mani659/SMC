# ONE STORY → ONE PLAN → AT MOST ONE LIVE ORDER

**Status:** `ONE_STORY_STATUS: PASS` — design-locked and implemented 2026-11-15.
**Authority:** Lead Architect locked product rule, 2026-11-15 ("one concrete story → one
plan → at most one live trade; approve or sleep").
**LOGIC_CHANGED:** YES — uniqueness enforcement only. No trigger body, no C3/expiry/scan
width, no SL/TP/pillar definition, no threshold, no new constant.

---

## 1. Problem (measured, not assumed)

PFE-2/PFE-3 measured the product menu path spraying tickets: several POI ids whose confirmed
routes resolve to the SAME executable plan, all placed on the same bar. Re-cut from the frozen
artifacts (`06_RESEARCH/results/pfe2_6m/menu_short_*/run1/trades.csv`):

| Window | Fills | Distinct plans | Spray factor |
|---|---|---|---|
| Jun 1–10 2025 | 11 | 4 | 2.75× |
| Sep 1–10 2025 | 2 | 1 | 2.00× |
| Oct 1–10 2025 | 14 | 3 | 4.67× |
| **Total** | **27** | **8** | **3.4×** |

Every duplicate group: same direction, same trigger (F in all 27), **byte-identical entry /
SL / TP**, overlapping zones, different `poi_id`, same entry bar. The seek composition is
clean — 80 fills over 6 months, **zero** identical-plan groups — so the defect belongs to the
menu confirmation bridge (several POIs confirming off the same sweep/level), not to the seek
engine.

## 2. Normative rule

One concrete story → one plan → **at most one** live/backtest candidate order.

Many *ways to read* structure stay: every POI model, BOS/CHOCH, FVG, and trigger type keeps
producing its own story. What collapses is the exotic case where two POIs describe one plan.

### "Same story" (do not soften)

Two candidates are the SAME story iff ALL hold:

1. same symbol — implicit (single-symbol V1);
2. same direction;
3. **overlapping POI zone** — the existing `ZoneDedup` geometric rule (inclusive span
   overlap), reused through one shared implementation;
4. same trigger type;
5. same entry price (exact floats — no pip tolerance is invented);
6. same SL and same TP (exact floats as planned on the candidate).

A key that cannot be built (no entry/SL, or unknown zone bounds) is **never** treated as a
duplicate: sameness is only ever asserted from known geometry.

## 3. Seam chosen (and why)

**`PipelineAdapter` intake** — the single point both product paths pass through *before* the
runner's risk gate:

* menu winners → `queue_menu_candidate` (the `ProductMenuEngine.winner` → adapter bridge);
* seek routes → the per-POI route mint inside `generate_candidates`.

Chosen over the order-place seam because the loser must be retired at source: had the collapse
lived only at placement, the losing POI's workflow would stay alive and place the same plan
later — after the first order resolved — which is exactly the spray being fixed. Collapsing at
intake also keeps sizing, tickets, and the §11 one-shot untouched (a dropped duplicate never
reaches risk, never consumes a lot, never mints a ticket).

Ordering inside the bar is unchanged otherwise: `generate_candidates` (scan → claim check →
submit) still runs before `_process_entries` (risk → place), and R9 intents still run last.

### Claim lifecycle (explicit, not guessed)

* **claim** — recorded when a candidate is accepted for submission (unsealed).
* **seal** — a real placement (`on_candidate_accepted`) turns the claim into a book-following
  claim. From then on it is live exactly while a resting order / open position / live R9
  intent still carries that plan (`story_live_plans`).
* **release** — explicit when the candidate can no longer trade: §24 signal expiry, POI
  VIOLATED, unfilled-order expiry, menu window closed unplaced.
* **prune** — a sealed claim whose plan left the book is dropped, so an identical plan that
  re-arms **after** its trade closed is a *new* story and is allowed ("sleep and wait for
  another story").

Sealed is not a timer: a blocked-by-risk candidate keeps its claim while its workflow lives,
and a cancelled/expired order frees it.

## 4. Implementation map

| File | Change |
|---|---|
| `04_SRC/smc/risk/story_guard.py` | **new** — `StoryKey`, `story_key()`, `same_story()`, `zones_overlap()` (pure, no I/O) |
| `04_SRC/smc/orchestration/multi_tf_runtime.py` | `ZoneDedup.seen` now calls the shared `zones_overlap` — same formula, one implementation |
| `04_SRC/smc/backtest/pipeline_adapter.py` | claims + `_duplicate_story` / `_claim_story` / `seal_story` / `release_story` / `_prune_story_claims` / `_drop_duplicate_poi`; menu intake check; seek mint check; counters via `story_counters()` |
| `04_SRC/smc/backtest/runner.py` | `story_live_plans()` — orders + positions + live intents |
| `04_SRC/smc/paper/runner.py` | `story_live_plans()` + tracked-pending `entry_price/sl/tp` (paper parity: same adapter, same seam) |
| `04_SRC/tests/test_one_story_one_trade.py` | 11 tests: definition (5), overlap helper, spray collapse (Oct shape 7→1), different zone/direction still two, live-vs-after-close, seek duplicate burn |
| `04_SRC/tests/test_one_story_one_trade.py` | also covers the merged accept seam (below) |

### Defect found while wiring (fixed, minimal)

`PipelineAdapter` defined `on_candidate_accepted` **twice**; the later definition silently
shadowed the F7 menu settle, so a placed menu winner was never settled. The two are now one
method: consume one-shot + settle F7 pending + seal the story claim.

## 5. Smoke (no optimization)

Frozen PFE-2 menu window, Oct 1–10 2025 (`--composition menu`, same load/exec bounds):

| | fills | distinct plans | armed | menu winners | blocked |
|---|---|---|---|---|---|
| before (PFE-2 run 1) | 14 | 3 | 97 | 23 | 9 (7 session + 2 **circuit_breaker**) |
| after (this engagement) | **4** | 4 | 97 | 23 | 3 (3 session) |

`06_RESEARCH/results/one_story_oct/` (fills) + `one_story_oct_b/` (determinism rerun).

Command:

```
python 06_RESEARCH/scripts/phase3_structure_funnel.py --tag one_story_oct \
  --out-root 06_RESEARCH/results/one_story_oct --composition menu \
  --load-from 2025-05-01 --exec-from 2025-10-01 --exec-to 2025-10-10
```

### Result (measured, and it is NOT a clean 3)

**14 fills → 4 fills.** Three are the surviving F plans (one per duplicate group). The fourth
is **new**: `poi-006522`, trigger A, plan 3960.075 / 3964.203 / 3950.906 — a plan that did not
trade before. The mechanism is visible in the blocked logs and is honest, not mysterious:

* before — the 14 sprayed fills lost and tripped the **circuit breaker** (2 blocked entries;
  diagnostics net −20.0 on the spray);
* after — with one ticket per story the breaker never trips (0 blocked), so that A story,
  which the breaker had been sitting on, is allowed to place.

So uniqueness changes the trade SET, not just its size, through the existing risk law — no
risk rule, threshold or breaker parameter was touched. `menu_submitted` fell 23 → 7 (16
winners were dropped as duplicates of a live plan); armed and winners are unchanged (97 / 23),
confirming the rule sits at intake and does not alter detection.

This is a book-shape result on one frozen 10-day window. It is **not** a performance claim and
not a reason to re-read the diagnostics net as improvement — n=4.

**Determinism:** the window was run twice (`one_story_oct/`, `one_story_oct_b/`);
`trades.csv` is byte-identical (sha256 match), same 4 fills / same triggers / same exits.

## 6. Non-goals

* no change to trigger bodies A–F, C3, scan width, expiry, or pillar definitions;
* no seek-as-product switch, no menu-vs-seek ranking;
* no expectancy, TP/SL retune, or performance claim of any kind;
* no Mode B; no new constant (`locked_constants.py` untouched).

## 7. What this does NOT claim

Uniqueness is a **book-shape** property: 27 tickets became 8 stories on the measured windows.
It does not make any of those stories profitable, does not change the funnel's armed/route
counts, and does not validate the market read. Expert scoring (PFE-3) and paper (PFE-4) stay
the next gates.
