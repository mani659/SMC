# MENU WINDOW STAMP RECONCILIATION — why 11 B fills look "past the window" (F: 0)

**Status:** PASS (read-only; no replay, no logic/threshold change)
**Scope:** books F and B, post-R1 union, S3 re-baseline artifacts (`06_RESEARCH/results/parallel_books_s3_rerun/`, 592 fills)
**Question:** the F/B entry-quality study reported 11 B fills whose `completion_ts` is later than their own `window_end_ts` (seven by 30.5–39.4 h, F zero). Is the menu window being breached — and if not, which mechanism writes that stamp?

**Answer:** `window_end_ts` is a **wall-clock projection** (`sweep_close + 20 × detection-bar minutes`), written only when the engine's bar-counted window has not yet materialised. Eligibility is **bar-counted** (`sweep_index + 20` detection bars). The two diverge wherever the detection series has a market closure (weekend/holiday) — and all 11 confirmations are inside the bar-counted window. **No window was breached.** Measured: 11/11 inside, 0 past the bar window, 0 fills extended by the adapter retry or the R8 resting clock.

---

## 1. What `window_end_ts` actually is

The stamp is written in `_win` at candidate-build time (`04_SRC/smc/orchestration/product_menu_mtf.py:887-903`):

```python
window_end = self._window_end_ts(episode)
if window_end is None:
    # The window's last detection bar has not closed yet: stamp the
    # window's nominal end (enough detection-TF bars after the sweep).
    # F7 uses it only to bound resubmission of an unaccepted winner.
    window_end = episode.sweep_close_ts + timedelta(
        minutes=episode.tier.detection_tf.minutes * episode.tier.expiry_bars
    )
```

`_window_end_ts` (`product_menu_mtf.py:788-802`) can only answer with a real bar close:

```python
end_index = episode.sweep_index + episode.tier.expiry_bars
if 0 <= end_index < len(det):
    return _close_ts(det[end_index])
return None
```

`MENU_EXPIRY_BARS = 20` (`product_menu_mtf.py:97`) is the expiry of **every** shipped tier (`:246-249`, DAY/H4/H1/M15), so the nominal projection is `sweep_close + 20 × det_minutes` — 21 h on H1, 84 h on H4, 5.25 h on M15.

Two properties follow, and both were verified on the whole frame (assertions in the harness):

- **592/592** stamps equal the nominal projection exactly. The stamp is *always* the wall-clock form; it only coincides with the true bar close when the detection series has no gap.
- The nominal projection counts **minutes**, while `_expire` (`:621-638`) and `_route_for` (`:804-844`) count **detection bars**. The M1 base has no Saturday bars and only Sunday 23:00+ (weekday census: Mon–Fri plus 25,475 Sunday M1 bars), so 20 H1 bars routinely span 3 calendar days.

## 2. What eligibility actually is (bar count, not wall clock)

| Gate | Code | Basis |
|---|---|---|
| Episode expiry | `product_menu_mtf.py:635` `if index > episode.sweep_index + episode.tier.expiry_bars` | new detection-bar index |
| Confirmation bound | `product_menu_mtf.py:840-841` `if end_ts is not None: upper = min(upper, bisect_right(self._closes[ctf], end_ts))` | close of the bar at `sweep_index + 20` — and **no bound at all** while that bar has not closed (`end_ts is None`) |
| Window-open guard | `product_menu_mtf.py:685` `if index < indexes[-1] - tier.expiry_bars` | detection-bar index |
| Expiry constant | `product_menu_mtf.py:97` `MENU_EXPIRY_BARS = 20` | detection bars |

So while a Friday-evening window waits out the weekend, `_window_end_ts` is `None`, `_route_for` legitimately evaluates every confirmation bar as it closes, and `_expire` cannot fire (no new detection bars exist). A confirmation on Monday morning is **inside** the 20-bar window; the stamp written at that moment is Saturday afternoon. That is the whole mechanism.

## 3. The 11 rows (exact)

`gap` = bar-count window end − stamped window end. `depth` = detection bars fully closed between the sweep bar and the confirmation (0 = the bar right after the sweep; ≤19 = inside).

| POI | run | dir | tier | sweep (UTC) | stamped end | bar-count end | gap | confirm | depth | late vs stamp | late vs bar window | fill lag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| poi-004236 | jul25/LONG | short | H1 (H1/M1) | 2025-07-11 14:00 | 07-12 11:00 | 07-14 12:00 | 49 h | 07-14 02:26 | 10 | +39.43 h | −9.57 h | +4 min |
| poi-006053 | feb25/LONG | long | H1 (H1/M1) | 2025-02-07 13:00 | 02-08 10:00 | 02-10 11:00 | 49 h | 02-10 00:45 | 9 | +38.75 h | −10.25 h | 0 |
| poi-005511 | feb25/LONG | short | H1 (H1/M1) | 2025-02-07 16:00 | 02-08 13:00 | 02-10 14:00 | 49 h | 02-10 02:00 | 8 | +37.00 h | −12.00 h | 0 |
| poi-005104 | feb25/SHORT | short | H1 (H1/M1) | 2025-02-07 16:00 | 02-08 13:00 | 02-10 14:00 | 49 h | 02-10 02:00 | 8 | +37.00 h | −12.00 h | 0 |
| poi-000925 | nov24/LONG | long | H1 (H1/M5) | 2024-11-22 18:00 | 11-23 15:00 | 11-25 16:00 | 49 h | 11-25 00:40 | 4 | +33.67 h | −15.33 h | 0 |
| poi-010051 | oct25/LONG | long | H1 (H1/M5) | 2025-10-10 19:00 | 10-11 16:00 | 10-13 17:00 | 49 h | 10-13 00:10 | 3 | +32.17 h | −16.83 h | 0 |
| poi-009519 | feb25/LONG | long | H4 (H4/M15) | 2025-02-12 12:00 | 02-16 00:00 | 02-17 20:00 | 44 h | 02-17 06:30 | 16 | +30.50 h | −13.50 h | 0 |
| poi-016097 | may25/LONG | short | H4 (H4/M5) | 2025-05-15 20:00 | 05-19 08:00 | 05-21 04:00 | 44 h | 05-19 14:50 | 10 | +6.83 h | −37.17 h | 0 |
| poi-012919 | sep25/SHORT | short | M15 (M15/M1) | 2025-09-11 18:00 | 09-11 23:15 | 09-12 00:15 | 1 h | 09-12 00:05 | 19 | +0.83 h | −0.17 h | 0 |
| poi-033071 | oct25/SHORT | short | M15 (M15/M1) | 2025-10-30 20:15 | 10-31 01:30 | 10-31 02:30 | 1 h | 10-31 02:20 | 19 | +0.83 h | −0.17 h | 0 |
| poi-015710 | jun25/LONG | long | H1 (H1/M1) | 2025-06-16 14:00 | 06-17 11:00 | 06-17 12:00 | 1 h | 06-17 11:13 | 19 | +0.22 h | −0.78 h | +2 min |

Reading: seven rows sit in weekend-crossing windows (49 h H1 / 44 h H4 gaps — Fri-evening sweeps confirming Monday). The four small ones sit on 1 h holes in the detection series (79 H1 and 34 M15 one-hour gaps exist in the frame), where a single missing bar is enough to push the bar-count close past the projected minute count. The last column shows no fill was delayed: nine fills are on their confirmation bar, two on the next limit touch (+2 / +4 min).

## 4. Why B and not F

The stamp code is shared; the difference is **how deep into its own window each book confirms**:

| Book | depth of confirmation (bars closed after the sweep) | windows spanning a data gap |
|---|---|---|
| F (351) | p50 **0**, p90 4, max 18 | 106 |
| B (241) | p50 **5**, p90 15, max 20 | 77 |

F resolves on the bar immediately after the interaction (BOS/OB), so it never approaches the window tail — 106 F windows span a gap and none produced a post-stamp confirmation. B's leading diagonal needs the five-wave structure, so its confirmations cluster late (p90 15 of 20); when such a window also crosses a weekend, the confirmation lands after the projected stamp. This is a property of B's *completion latency*, not of a B-specific code path.

## 5. The other two clocks (adapter resubmission, R8 resting/expiry)

Both were checked because either could move a fill past the window; **neither did in this frame**.

**F7 adapter resubmission** (`04_SRC/smc/backtest/pipeline_adapter.py`):

- `queue_menu_candidate` (`:506`) registers a pending entry only for runners that report outcomes, with `deadline = self._menu_deadline(candidate)` (`:535`, stored `:543`).
- `_menu_deadline` (`:569-600`) reads `stamp["window_end_ts"]` **first** (`:579`); only if absent does it fall back to `sweep_ts + MENU_EXPIRY_BARS × det_minutes + det_minutes` (`:593-597`).
- `_resubmit_menu_pending` (`:635-660`) resubmits one attempt per bar and drops the slot on `now > deadline` (`:642`), counting `menu_expired_unplaced` (`:644`) and releasing the story claim.

Consequence: the retry clock is the **nominal** stamp, so on a gap-spanning window it expires up to 49 h (H1) / 44 h (H4) / 1 h (M15) before the menu's own window closes. That asymmetry is real but **latent**: all 11 were accepted on their confirmation bar (fill lag 0–4 min), so no pending slot ever existed for them. 183 of 592 fills (F 106 / B 77) carry such a window, so the exposure is not small — a risk-blocked winner on one of those would stop being retried while the menu still had valid bars left.

**R8 resting bars / §23 expiry** (`04_SRC/smc/risk/fill_regime_policy.py`, `04_SRC/smc/backtest/orders.py`):

- `rest_bars_for` (`fill_regime_policy.py:152-180`): H1 → **36**, H4/M8/D1 → **48**, else the execution-TF default (12 on M5); constants at `:55-56`. Runner passes it at placement (`runner.py:564`, `orders.py:97`).
- `expired_by_section23` (`orders.py:181-208`) and `expired_by_give_up` (`orders.py:211-231`) measure life as `bars_open = current_bar - order.placed_bar + 1` — **runner (M5) bars from placement**, with no reference to `window_end_ts`.

So an order placed inside a window may legally rest 3 h (H1-detected) or 4 h (H4) past its confirmation, i.e. up to 48 M5 bars beyond the window tail, and fill there. Measured: **0 rows** of the 592 have an in-window confirmation and a fill after the stamped window (the 11 post-stamp fills are exactly the late confirmations, all filled on their own bar). The mechanism can only bite a book whose confirmation sits on the last eligible bar; B does reach depth 20, so it is a boundary to keep, not a live defect.

**Segment boundary note.** 22 fills (F 20 / B 2) carry a window whose 21st detection bar lies past the harness' month-tiled series, so `bar_end` never materialises (`window_truncated_by_segment` in `window_bounds_all_rows.csv`); all 22 confirmed well inside their nominal stamp. Consistent with the same root cause — a window end that exists as wall clock but not as a bar — truncated instead of gapped.

## 6. Consequences for the audit (no code change)

1. **`WINDOW_BREACH: NO`.** "Confirmation outside the menu window" is **0/592** when measured against the engine's own bar-counted bound. The 11 rows are a **stamp artefact**.
2. The entry-quality checklist item **G2** (`sweep_ts < completion_ts <= window_end_ts`) uses the stamp, so it under-reports window compliance on gap-spanning windows. B's "11 post-window confirmations (4.6 %)" in `ENTRY_QUALITY_F_B_NOTES.md` should be read as "11 confirmations after the *projected* window end, 0 after the real one"; that note now carries the correction.
3. Two clocks exist for the same event: the **menu's** (detection-bar count) and the **adapter's** (`window_end_ts`, wall clock). Today they agree except across closures. Whether the stamp should carry the real bar close (or be renamed `window_end_nominal_ts`) is an **Architect ruling** — this note changes nothing.

## 7. Reproduction

```
python 06_RESEARCH/scripts/menu_window_stamp_recon.py
```

Deterministic, fail-loud assertions: universe 592; post-stamp confirmations == 11 and all in book B; all 592 stamps equal the nominal projection; 0 confirmations past the bar-count window; no post-stamp row has a truncated window. Artifacts (gitignored): `06_RESEARCH/results/menu_window_stamp_recon/{post_window_fills.csv,window_bounds_all_rows.csv,summary.json}`.

---

## RETURN BLOCK

```
TASK: menu window stamp reconciliation (11 B "post-window" fills)
FRAME: post-R1 S3 union, 592 fills (F 351 / B 241), read-only
POST_STAMP_CONFIRMATIONS: 11 (B 11, F 0) — 7 >= 30 h, max +39.43 h
CONFIRMATIONS_PAST_BAR_COUNT_WINDOW: 0 / 592
STAMP_EQUALS_NOMINAL_PROJECTION: 592 / 592
WINDOWS_SPANNING_A_DATA_GAP: 183 (F 106 / B 77); gaps 1 h .. 49 h (H1 49 h x22, H4 44 h x38)
MECHANISM: product_menu_mtf._win stamps sweep_close + 20 x det_minutes when _window_end_ts
           is None (21st detection bar not yet closed); eligibility is bar-counted
           (_expire :635, _route_for :840-841), so the confirmation is legal
F7_RESUBMISSION: deadline reads the same nominal stamp (:579); latent early expiry
                 (<=49 h on H1 gap windows), causal for 0 of the 11 (all accepted same bar)
R8_ORDER_LIFE: 36/48 M5 bars from placement (fill_regime_policy:152-180, orders:181-231),
               independent of window_end; 0 fills extended past the window by it
F0_EXPLANATION: F depth p50 0 / p90 4 vs B p50 5 / p90 15 — completion latency, same stamp path
WINDOW_BREACH: NO
LOGIC_CHANGED: NO — no 04_SRC, locked_constants, config or S3 artifact edited
DOC: 06_RESEARCH/MENU_WINDOW_STAMP_RECONCILIATION.md
HARNESS: 06_RESEARCH/scripts/menu_window_stamp_recon.py (deterministic, asserts)
ENTRY_QUALITY_NOTE: corrected — G2 measured on the stamp over-reports; real count 0
NEXT: Architect ruling on the stamp (real bar close vs nominal), then as previously ruled
```
