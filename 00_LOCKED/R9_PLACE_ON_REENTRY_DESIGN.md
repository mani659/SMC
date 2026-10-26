# R9 DESIGN LOCK — PLACE-ON-REENTRY INTENT (2026-09-22)

**Status:** LOCKED before implementation (Lead Architect ruling R9; instruction: "design file first, then code").
**Extends:** R7 (place guard) + R8 (HTF resting bars) — both remain coded; R9 replaces the R7 *silent drop* with a deferred placement. GATE_WIDENED = NO; `ZONE_REFINEMENT_ATR` unchanged; no new tolerance constants.

---

## 1. Problem

Post-FR-3.1 + R7, F often completes with the MARKET outside the POI band (FR-4b smoke: all 6 routes skipped — closes +14.65..+165.50 beyond zone vs band 1.73..3.84). The on-zone limit + immediate R7 skip → 0 places; R8's longer lifetimes are inert (nothing rests). R9 defers the placement instead of dropping it: arm an intent that places when the market re-enters the zone band or touches the limit, within an R8-sized clock from signal time.

## 2. Locked rule

1. A risk-accepted candidate that passes R7's band check places immediately (current path — unchanged).
2. A risk-accepted candidate that FAILS the band check (R7 skip) arms a **PlaceIntent** — no order exists yet. The intent carries the FULL accepted placement frozen at signal time (direction, FR-3.1 zone-anchored limit, FR-2 SL/TP, policy-sized lots, all identity/geometry fields) plus:
   - `signal_bar` = the arming bar (its close failed the band check);
   - `rest_bars` = `rest_bars_for(detection_tf, is_m8, execution_tf)` computed ONCE at arm (the R8 clock from signal time);
   - `expire_bar` = `signal_bar + rest_bars` — the first bar at which the intent is dead.
3. On each subsequent bar while alive: if the market **re-enters the zone band** (`zone_place_allowed(bar.close)` — same frozen geometry, same per-bar ATR source as R7) **or the bar touches the limit** (the locked fill-model touch rule: LONG `bar.low <= limit`, SHORT `bar.high >= limit`), the intent places the pending order with `rest_bars = expire_bar − placed_bar` ("order inherits remaining bars" — the blueprint default: full R8 from signal when placed at signal time, shrinking for later placements).
4. If `bar >= expire_bar` with no placement → drop the intent; machine-readable event `intent_expired_no_reentry`. No order, one-shot never consumed.

### 2a. Bar-clock convention (§23 parity, exact)

Armed on bar N; `age = current_bar − N`; alive while `age < rest_bars`; dead from `age >= rest_bars` (bar N+rest). The arming bar itself NEVER places (its close failed the band check by construction; the touch path also starts at N+1). The placed order's lifetime inherits `remaining = expire_bar − current_bar` bars under the book's `bars_open = current − placed + 1` convention.

### 2b. Minimum-viable-lifetime rule (the "minimum 1 bar" clause, derived)

An order placed on bar B with `rest_bars = remaining` is fill-eligible on `B+1 .. expire_bar − 2` — exactly `remaining − 2` fill-eligible bars (expiry cancels pre-fill on `expire_bar − 1`). Therefore:

- `remaining >= 3` → at least 1 fill-eligible bar → **place**;
- `remaining < 3` → the order would be born expired (0 fill-eligible bars) → **do not place**; the intent runs to natural expiry (`intent_expired_no_reentry`).

A "minimum 1 bar" order is DOA under the frozen convention (0 eligible bars), so the derived minimum remaining life is 3. Documented, not tuned.

### 2c. Re-entry geometry (single source)

`smc.risk.fill_regime_policy.market_reentered_zone(direction, zone_low, zone_high, limit, price, atr)`:
- band re-entry via the EXISTING `zone_place_allowed` (frozen `ZONE_REFINEMENT_ATR × ATR`, same dormancy/fail-closed rules);
- OR limit touch mirroring the locked fill-model rule (LONG `low <= limit`, SHORT `high >= limit`; inclusive) — cross-checked against `fill_model.limit_filled` by test;
- zone bounds missing → touch-only (intents are only armed when the zone was locatable, so this is a defensive fallback).

## 3. One-shot / POI semantics (exact)

- **Arm consumes nothing** — `on_candidate_accepted` is NOT called at arm; the §11 one-shot stays unburned (same spirit as the R7 retryable skip).
- **Place consumes the one-shot** — intent placement calls `on_candidate_accepted` (it IS an accepted placement).
- While the intent is alive, the adapter may re-propose the route each bar (one-shot unburned): every re-proposal re-runs the normal path — immediate place if in band, R7-skip otherwise; the skip **dedupes** against the alive intent (first intent wins, clock NEVER refreshed; the skip BlockedEntry still logs for observability).
- **One intent per route identity per run** (key = `route_id`, fallback `poi_id|trigger`): a terminal intent (placed / expired / replaced / dropped) blocks re-arming — any later in-band proposal is covered by the immediate-place path; a second intent would extend life beyond R8.
- **Cancel-on-place:** an accepted immediate placement for a route drops its alive intent (status `replaced`) — never two orders for one route.
- **Dead thesis:** `cancel_pending_for_poi(poi_id)` (POI VIOLATED) also drops the POI's alive intent — a violated zone is a dead thesis, mirroring the resting-order rule.
- **Portfolio events:** Friday EOD and §11 news hard-cancel drop ALL alive intents, mirroring the pending treatment.
- **No risk re-evaluation at re-entry:** the intent is THE accepted placement deferred, not a new evaluation — lots/entry/SL/TP frozen at signal acceptance (single sizing/decision path preserved). Consequence accepted and documented: a re-entry placement may occur in a session/news state a fresh candidate would fail; the news path still hard-cancels the resulting resting order on the following bar (both engines).

## 4. Bar-loop order (backtest; no lookahead)

```
1 day reset
2 Friday EOD      → close all, cancel pendings, DROP ALL INTENTS, return
3 news hard-cancel→ cancel pendings, DROP ALL INTENTS
3b ATR/spread feed
3c §23/§24 expiry (pendings)  → 3c-i intent expiry (age >= rest → expired_no_reentry)
4 position exits
5 fills (pendings) + physical closes
5.5 INTENT re-entry placements (insertion order; remaining >= 3; place → PLACED)
6   candidate entries: risk gate → R7 guard
      → in band: place immediately; drop alive intent for the key (REPLACED)
      → far:    blocked log (skip_place_far_from_zone) + arm intent (dedupe)
7 management
```

A bar-B placement cannot fill on bar B (fills already ran at step 5) — no lookahead, no retroactive fill. Paper mirrors: news-cancel → `_expire_pendings` → `_expire_intents` → fills/closes observe → `_manage_open_positions` → `_place_due_intents` → `_entry_step` (arm on skip; REPLACED-drop on success). Paper bar index = `self._bar_count`; ATR = the adapter's `latest_atr`; dry-run records the KPI event but consumes nothing (parity with the candidate dry-run path — the intent stays armed).

## 5. Non-goals (unchanged)

Band widen, market/chase entries, F-timing labels, displacement/pillar changes, gate edits, locked-constant edits, Monte Carlo. The intent NEVER chases: it can only place the SAME resting limit computed at signal time.

## 6. Acceptance

Unit tests: immediate place (no intent) / far → intent armed / close-band re-entry place (correct limit + inherited rest_bars) / touch-only re-entry place / natural expiry with no order / DOA boundary (remaining < 3 → no place) / dedupe + clock immutability / REPLACED on immediate place / one-shot burn only at place / dead-thesis + portfolio drops / R8 table unchanged / `ZONE_REFINEMENT_ATR` unchanged / touch-geometry cross-check vs `fill_model.limit_filled`. Paper mirror tests over the fake connector. Suite green. Smoke on the FR-4b window must show intents armed and either place-on-reentry or expiry — count reported, never tuned.

## 7. Modules

`smc/backtest/intents.py` — `PlaceIntent`, `IntentBook` (insertion-ordered, deterministic; counters + machine-readable event records). `smc/risk/fill_regime_policy.py` — `market_reentered_zone` (pure; touch geometry cross-checked against `fill_model`). Backtest runner wiring (arm/expire/place/drop + shared accepted-placement helper). Paper runner mirror. Smoke: `06_RESEARCH/scripts/r9_place_on_reentry_smoke.py` (logging-only `BacktestRunner` subclass patch on the FR-4 script namespace, restored in `finally`).