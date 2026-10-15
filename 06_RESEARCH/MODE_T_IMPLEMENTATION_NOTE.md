# MODE T + CONSOLE JUDGEMENTS + CHART MARKERS — IMPLEMENTATION NOTE

**Date:** 2026-10-15 · implements **[00_LOCKED/MODE_T_CONSOLE_MARKER_DESIGN.md]** (the NOTE wins on conflict) · baseline tag `v1.1-pre-mode-T`
**Status:** PASS — wired, tested, suite 1162 passed · `LOGIC_CHANGED: YES (Mode T seams only, per design)` · `locked_constants.py` diff empty

## 1. What was shipped (seam by seam)

### (A) Mode T — flag-gated diagnostic entry path (note §2)
| Piece | File | Notes |
|---|---|---|
| Constant home | `04_SRC/smc/live/mode_t.py` | `T_MAX_GAP_ATR=0.25`, `T_TP_ATR=1.0`, `T_REST_BARS=12`, `T_MAX_CONCURRENT=2`, `T_MAX_PER_DAY=6`, `MIN_LOT_FLOOR=0.01` — **mode_t module only**; test `test_mode_t_constants_never_leak_into_locked_constants` pins locked_constants clean |
| Banner | same | `MODE_T_BANNER` = design §2.1 string verbatim; printed ONCE at session start when the flag is on |
| Flag + knobs | `04_SRC/smc/live/operator_config.py` | `diagnostic_entries` (bool, default False), `judge_interval_s` (default 60, 0=off), `marker_enabled` (default True), `marker_path` (default "" → heartbeat dir). Mode T geometry keys still rejected (`test_config_rejects_mode_t_geometry_keys`) |
| Pure decision | `smc/live/mode_t.py :: decide_mode_t` | rule T2 with the FROZEN evaluation order: duplicate → session → spread → product tie → NO_ATR → GAP_TOO_WIDE (≤0.25) → caps → volume → PLACE. Entry = proof-bar mid `(H+L)/2`; SL = adverse extreme; TP = ±T_TP_ATR; never market |
| Ledger | `ModeTLedger` → `logs/…/mode_t_events.jsonl` | one JSON line per decision, note-verbatim §2.5 fields INCLUDING the note's own field name `anomaly_ts_iso` (appendix A). Expert scorecard placeholders `level_ok/sweep_ok/confirm_ok/timing/would_take` — blank (None), never code-filled |
| Operator book | `ModeTDirector` | one-shot per (poi, proof_bar); hard caps; 12-bar rest expiry; §5-invalidation cancel; Friday-EOD cancel (`FRIDAY_EOD_CLOSE_HOUR_UTC` reused read-only); broker rejects → `PLACE_REJECTED_<retcode>` taxonomy tail; clean-stop cancel of resting tickets |
| Live wiring | `04_SRC/smc/live/run_operator.py` | `_mode_t_on_poll` evaluates the adapter's routed-not-accepted workflows (the ONLY Stage-3 proof events visible without forking detection/§5) each poll, guarded by try/except so the product poll never breaks; `place_fn` through the existing `PaperRunner.broker.place_limit` (LIMIT only, §10 respected); **dry_run sends nothing but logs every decision** (§1.4) |
| Product wins ties | `_product_ticket_active` | broker-truth scan: any product pending/position whose comment starts `poi.id[:8]` → `PRODUCT_PATH_TAKEN`. Mode T tickets carry the `mode=T` comment prefix so the scan never confuses the two books |
| Tester config | `config/live_tester.json` (new per §5) | `diagnostic_entries: true`, `require_demo: true`, `dry_run: true` (demo caps, no real-send without the owner's explicit change), detection H4+H1, `log_dir: logs/phase_d_tester` |

### (B) Console judgement board (note §3)
| Piece | File | Notes |
|---|---|---|
| Renderer | `04_SRC/smc/live/judgement_console.py` (new) | blocks exactly `MODE / POIS / SWEEPS / SEEKING / JUDGEMENT / BOOK / HEARTBEAT`; honest empties (`JUDGEMENT: flat (…idle)`, `SWEEPS: none`, `SEEKING: none`); ASCII-only; pure function of the snapshot + Mode T records |
| Flat guarantee | `run_operator._maybe_judge` | ≥1 full board per `judge_interval_s` even with zero trades (0 disables the extra cadence); judgement lines come from the ledger tail only — plain language, no tracebacks, no desirability text |

### (C) Chart markers (note §4)
| Piece | File | Notes |
|---|---|---|
| Python writer | `04_SRC/smc/live/marker_writer.py` (new) | `smc_markers.csv`, schema header verbatim; ≤11 objects (≤8 armed zone rows, 1 sweep line ONLY when the linked armed POI's zone edge prices it — the sweep link carries no price, honest skip otherwise; 1 `entry_t` line, 1 corner label); atomic write-temp + replace with the heartbeat's rename/in-place double strategy; failure → logged False, never raises (§4.4) |
| Path policy | `_build_stack` | explicit `marker_path` wins; else the resolved heartbeat's parent dir — same MQL5/Files discipline |
| Refresh cadence | `_publish_console` + `_on_poll` | structure change / Mode T book change → rewrite (rate-limited by `console_refresh_s`) |
| MQL5 reader | `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` (+ copy at `dist/mql5/`) | new input `InpMarkerFile` (default `smc_markers.csv`); timer order frozen: `CheckHeartbeat()` FIRST, then `UpdateMarkers()`; draws/deletes ONLY `SMC_*`-prefixed `OBJ_RECTANGLE`/`OBJ_HLINE`/`OBJ_LABEL` (corner label is screen-anchored — chart-TF independent); file stale >30 s or unreadable → `DeleteAllStrategyMarkers()`; heartbeat stale → corner label `HEARTBEAT STALE` (red). ZERO trading logic; marker failure can never block the emergency path |
| Deinit cleanup | only on real departure (`REASON_REMOVE/PROGRAM/CLOSE`) — parameter changes / recompiles keep markers and re-sync on the next tick |

## 2. Honest wiring limitations (disclosed, not papered over)

1. **Proof-event visibility.** Mode T observes Stage-3 proofs through the adapter's routed-workflow chain (fired triggers / products' surviving-not-yet-accepted candidates). §5/detection is untouched by design (non-negotiable is retained), which also implies invisible-bar cases: no invented proof side-channel exists. Diagnostic activity in a live session concentrates where the product's own chain surfaces proofs (routed candidates that the risk layer has NOT yet placed — blocked, re-submitting, or dry-run-accepted earlier seeds). This is the honest reading of note §1's entry-path survey + §2.2's preconditions; silent watermark (evented scan bubbles in §5-only states) is NOT simulated.
2. **Sweep level is inferred from the linked armed POI's zone edge** (the sweep links carry side+magnitude only). Noted in the writer header; no invented price ever drawn.
3. **Mode T ledger field `anomaly_ts_iso`** is the note's own §2.5 spelling of the decision timestamp — kept verbatim (appendix A).
4. **The `.ex5` in `dist/mql5/` is the OLD binary** — the user must recompile `SMC_Safety_Watchdog.mq5` locally (MetaEditor) before the tester session; the design brief already documents that the user compiles locally.
5. **live_demo.json stays untouched** (`diagnostic_entries` absent → false; dry_run true). No production posture change.

## 3. Verification evidence

- Suite: **1162 passed** (1127 baseline + 35 new; `EXIT=0` preserved via `PIPESTATUS`). Two pre-existing `test_perm_hardening` live-path tests broke transiently mid-flight when the Mode T hook was mis-anchored inside `_on_poll` (they exercise the REAL poll; the hook ran before `state["atr"]` was set and the §28.5 mirror lost its guard). Root cause fixed by re-anchoring the hook AFTER the spread/ATR/book-state block and restoring the guard; both tests green again (14/14 in the module).
- New tests: `04_SRC/tests/test_mode_t.py` (T2 matrix: accept/gap-reject/NO_ATR/session/spread/product-tie/caps/volume/duplicate; place-rejected tail; one-shot; rest-expiry; invalidation; daily-cap reset; ledger §2.5 field contract; banner verbatim; locked-constants home rule; config surface incl. tester/demo configs) and `test_mode_t_console_markers.py` (marker header/rows/caps/heartbeat-stale/entry-line/sweep-needs-zone/never-raises; judgement flat board with MODE line; banner block; skip-reason surfaces; `judge=0` disables).
- Flat console board observed in a unit + a dry smoke (`FLAT SMOKE OK`, MODE line + banner block).
- `git diff -- 04_SRC/smc/config/locked_constants.py` → empty (Mode T numbers live in `mode_t.py` only).
- Config smoke: `live_tester.json` loads with diag True/60/True/""-path; `live_demo.json` loads with diag False.

## Appendix A — note-verbatim items

- Banner string: §2.1 exact.
- Ledger fields (§2.5): `mode, anomaly_ts_iso, poi_id, detection_tf, exec_tf:"M5", proof_bar, trigger_letter, action, entry, sl, tp, gap_atr, skip_reason, volume, cap_state_concurrent, cap_state_daily, mode_t_ticket:"T"` + placeholders. `anomaly_ts_iso` is the note's term for the decision timestamp — kept byte-for-byte, documented here rather than silently renamed.
- Marker CSV header (§4.2): `id,symbol,kind,direction,price_high,price_low,timeframe_label,text,color_role,updated_at_utc,ephemeral`.

## NEXT (outside this task)

Owner internal demo on the tester config (Mode T banner + judgement boards + markers visible; `mode_t_events.jsonl` grows) → rebuild the tester zip only after the owner accepts the run; production demo config unchanged.
