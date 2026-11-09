# Phase 0 + F1 + F2 — Information-set fixes (execution record)

**Authority:** Lead Architect, 2026-11-09 — audit acceptance + `P0 FIX PROGRAM — Phase 0 + F1 + F2`. Scope executed exactly as written: freeze/mitigate, closed-bar HTF inputs, evaluate every newly closed confirmation bar. **No structural-TP feed, no OPT-B, no OPT-2, no tier/trigger/threshold retune.**

`LOGIC_CHANGED = YES` (F1 + F2 only, plus the F2-required window-open guard below).

---

## 0 — Freeze and mitigate (`LOGIC_CHANGED=NO`)

| Item | Value |
|---|---|
| Baseline tag | `baseline_pre_fix` (annotated, at `bf011ef`) |
| Frozen artifacts | `06_RESEARCH/results/baseline_pre_fix/` (ledger CSV + summary + run.log + tp attribution + 5 chart PNGs) — **never overwritten** |
| `plan_complement_ledger.csv` sha256 | `50cff6f440a8dcdda8978e2e7a9a9906079b854ccbce4b4d86f4c40e189b1204` |
| `plan_complement_summary.json` sha256 | `e67c6de79b3fa17acd31f4fc8c5db165127012faec32e6aff5a9b6d487145692` |
| Suite at freeze | `1382 passed, 6 skipped` |
| Live config | `config/live_demo.json` → `dry_run: true` until the Architect clears it (F3 sizing pin pending). Spread/news/session gate state unchanged and still OFF — see audit P0-6. |

**Funnel counters (F0.2, measurement only, never read by a decision):**
`ProductMenuEngine.counters()` = `detection_bars_seen`, `confirm_bars_seen`, `confirm_bars_evaluated`, `episodes_opened`, `episodes_expired`, `sweeps_total`, `sweeps_out_of_window`, `episodes_total`, `winners_total`, `active_episodes`, `armed_pois`. `MultiTFBatchReport.last_closed_ts` records the last CLOSED bar instant delivered per detection TF; `summary()` carries both. The ledger writes `menu_counters` into its summary.

---

## 1 — F1 closed-bar HTF contract (`LOGIC_CHANGED=YES`)

**Defect (audit P0-1).** `build_htf_prefixes` cut on `timestamp <= as_of`, so it included the bar still forming at the decision instant. In a resampled historical series that bar is **complete**: probe at `as_of = 2024-04-01 05:00` delivered the H4 bar opening `04:00` (closes `08:00`, 3 h of future) and the D1 bar opening `04-01 00:00` (closes `04-02 00:00`, 19 h of future), both with their completed OHLC. Live had the mirror defect: MT5's forming bar was passed to detection, so live zones repainted.

**Fix.** One contract, one helper, runtime-owned:
- `build_htf_prefixes(series, as_of)` now keeps bars with `timestamp + timeframe <= as_of` (closed only).
- `MultiTFProductRuntime.run_batch` applies the trim itself whenever `as_of` is not `None`, so research, paper and live cannot disagree and no caller can bypass it. `as_of=None` still means "caller supplied closed prefixes verbatim" (no clock invented).
- `MultiTFBatchReport.last_closed_ts` (+ `summary()`) exposes what was actually consumed.
- New `bar_close_ts(candle, tf)` helper is the single close-instant formula.

**Tests.** `04_SRC/tests/test_phase01_information_set.py`: `test_prefix_never_includes_an_unclosed_bar` (5 TFs × 11 instants incl. bar opens/mid-bar/exact closes), `test_prefix_excludes_the_forming_bar_at_a_midbar_instant` (the exact pre-fix failure), `test_run_batch_trims_to_closed_bars_and_reports_last_closed` (driver-spy: a forming bar never reaches the driver, so it can never mint a zone). Updated the two tests that encoded the old inclusive cut (`test_build_htf_prefixes_cutoff_semantics`, `test_build_htf_prefixes_last_bar_never_exceeds_as_of`).

---

## 2 — F2 confirmation completeness and order (`LOGIC_CHANGED=YES`)

**Defect (audit P0-2), with the measured fingerprint.** The non-OPT-B branch evaluated `starts = [tail]`: with batched feeds only the last closed bar was ever shown to the router, so M5 confirmations were sampled 1-in-3 and M1 1-in-15 under the harness's M15 step. Every pre-fix winner's `t_confirm` landed on the 15-minute grid (`12:30`, `14:00`, `18:00`, `20:30`, `06:45`) — the signature of tail quantisation. Same-tick cross-TF choice was tier list order (H4 prefers M5 over M15; H1 prefers M5 over M1), not "first valid wins".

**Fix.**
- `_route_for(episode, ctf)` evaluates **every** confirmation bar not yet evaluated, from the first close at/after the sweep close, in ascending order; `_evaluated[ctf]` advances monotonically. A route is returned un-consumed so the caller can order across TFs.
- `on_execution_bar` collects the first route per eligible confirmation TF and wins the one with the **earliest completion instant**, tie → lower TF minutes → route id. The key lives in `confirmation_order_key()` and mirrors `SweepEpisodeCoordinator.resolve_confirmations` (no third ordering rule).
- `_window_end_ts()` bounds eligibility to the locked one-shot window: confirmations must close at or before the detection bar at `sweep_index + expiry_bars` (expiry counts detection-TF bars, as locked).
- OPT-B branch unchanged (`same_bar_asof` default OFF).

**F2-required window-open guard (P1-2 partial, recorded).** With "evaluate every bar", a window opened on a sweep from before the current window would evaluate months-old bars and could emit a plan with stale prices; it was also a compute blow-up at step 0. `_open_episodes` now refuses to open a window whose sweep is older than `expiry_bars` detection bars at the newest closed detection bar (`sweeps_out_of_window` counter). **Remaining F5 scope:** arm timestamp (`t_arm`), and `_expire`-before-`_open_episodes` ordering with a clock argument (9 `register_armed` call sites).

**Tests.** `test_every_new_confirmation_bar_is_evaluated_not_just_the_tail` (early bar wins; the router saw every bar in order; no re-evaluation), `test_confirmation_after_the_one_shot_window_is_ineligible`, `test_confirmation_order_key_is_earliest_then_lower_tf_then_route_id`, `test_cross_tf_winner_is_the_earliest_completion_not_tier_order`, `test_old_sweep_cannot_open_an_already_closed_window`.

---

## 3 — Verification

- `PYTHONPATH=04_SRC python -m pytest -q 04_SRC/tests --ignore=04_SRC/tests/test_review_merge_smoke.py` → **1394 passed, 6 skipped** (frozen baseline: 1382/6; +12 new tests, two existing prefix tests rewritten).
- Pre-fix probe (recorded above) fails the closed-bar property; the new property test passes.
- Re-baseline run: same window (`2024-04-01 .. 2024-05-01`, warmup `2023-12-01`), same harness, **new output paths** `06_RESEARCH/results/plan_complement_ledger_post_f1f2/`; note `06_RESEARCH/PLAN_COMPLEMENT_LEDGER_POST_F1F2_NOTE.md`.

### Baseline vs re-baseline (counts only — **not an improvement claim**)

| Metric | `baseline_pre_fix` | `post_f1f2` |
|---|---|---|
| `REGISTER_ARMED` | 14 | 13 |
| `SWEEPS` | 27 | 13 |
| `N_WINNERS` / submits | 5 / 5 | **7 / 7** |
| Tiers | H4/M5 2 · H4/M15 2 · M15/M1 1 | M15/M1 6 · H4/M15 1 |
| `t_confirm` minute-of-hour | all on `:00/:15/:30/:45` | `:44, :17, :03, :39, :00, :59, :12` |
| `PCT_PLAN_COMPLETE` | 100.0 (5/5) | 100.0 (7/7) |
| `confirm_bars_evaluated` | not instrumented | 2,154 of 185,604 seen |
| `episodes_opened` / `expired` | not instrumented | 13 / 6 |

Reading: the off-grid confirm minutes are direct evidence that M1 confirmations are now evaluated per closed bar instead of once per M15 step; the tier mix moves toward the tier that was most under-sampled (M15→M1). Winner count rose 5→7 while armed POIs fell 14→13 and sweeps 27→13 (closed-bar detection + the window guard). **`PCT_PLAN_COMPLETE` is 100% in both samples by construction** (the bridge always fills entry/SL/TP) and therefore discriminates nothing — do not quote the old↔new percentage as a delta.

**Caveats.** n=7, one window, menu-submit frame only (live risk blocks not modelled); `t_arm` still unstamped; all 7 winners are `F_BOS_OB` (trigger diversity still unmeasured); `tp_source` is `atr_fallback` on all 7 (structural TP deliberately not wired). Old ledger/charts are pre-fix evidence only.

**Artifact note (honest).** The post-run `run.log` console echo printed the harness's legacy hardcoded `"LOGIC_CHANGED": "NO"` literal; the print was corrected after the run. `plan_complement_summary.json` (`logic_changed`) and this note are authoritative.

---

## 4 — Handed forward (unchanged scope)

- **F3** sizing units pin (`pip_value_per_lot` vs broker contract size; `LOT_MAX_SAFETY` masking) — live stays `dry_run: true` until pinned.
- **F4** risk envelope ruling (daily loss / max trades / DD cooldown).
- **F5** lifecycle: `t_arm`, `_expire`/`_open_episodes` ordering, `register_armed(clock)`.
- **F6/F7** §5 reconciliation and blocked-menu-candidate retry.
- Charts were **not** re-rendered; the pre-fix chart pack is frozen under `baseline_pre_fix/`.
