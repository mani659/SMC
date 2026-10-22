# MODE T — CONFIRMATION AUDIT (READ-ONLY, FINDINGS ONLY)

**Date:** 2026-10-15 · Lead Architect confirmation audit · no strategy “improvements”, no T2/threshold/product-path changes made.
**Purpose of the audited task:** Mode T + console judgements + chart markers implemented at the candidate/limit seam, per the audit brief.
**Note:** this is the *second* governance-required audit gate. Findings-only. The only artifact written is this file (plus the standard governance sync stamps in `CHANGELOG` / `SESSION_HANDOFF` / `POST_V1_ACTIVE_TODO`). No source, config, MQL5, or tests were changed.
**Design authority:** `00_LOCKED/MODE_T_CONSOLE_MARKER_DESIGN.md` (BINDING).
**Impl note (audited claim set):** `06_RESEARCH/MODE_T_IMPLEMENTATION_NOTE.md`.
**DOC_DEFECT rule applied:** the audit brief flagged any reference to the nonexistent `MODE_T_VOLUME_BASED_ENTRY_DESIGN.md` as DOC_DEFECT. Researched: no such file has EVER existed in the repo; every tracked reference to a Mode T design (commit body, notes, changelog, handoff, TODO) points at `00_LOCKED/MODE_T_CONSOLE_MARKER_DESIGN.md`, which exists. **DOC_DEFECT: none.** (The intended item was a name *correction of an earlier case mistake in the audit prompt itself*; repository reality is consistent.)

## 1. Scope / SHAs / suite

| Item | Value |
|---|---|
| `git log --oneline -5` | `9b649d5` (feat: Mode T inbox + rhythm…) → `11b0889` (chore: governance handoff and baseline lock) → `70ca63a` (feat/baseline: pre-Mode-T product baseline) → `d46486a` → `a97baf0` |
| Mode T implementation commit | **`9b649d5`** — 13 files, +2440/−7 |
| Baseline tag verified | `v1.1-pre-mode-T` → `0a3266f` |
| Push state | `main...origin/main [ahead 1]` — **NOT pushed**; owner's call. No push performed by this audit |
| Suite | `cd 04_SRC && python -m pytest tests -q` → **1162 passed, 0 failed, EXIT=0** (exit preserved via `${PIPESTATUS[0]}`, not filtered output) |
| `locked_constants.py` diff vs baseline tag | **empty (0 lines)** — the header block lives ONLY in `mode_t.py` |
| Design file existence | `00_LOCKED/MODE_T_CONSOLE_MARKER_DESIGN.md` PRESENT (already tracked before this audit) |
| Watchdog source parity | `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` vs `dist/mql5/SMC_Safety_Watchdog.mq5`: **byte-identical** (`cmp` exit 0), both on `9b649d5` |
| `.ex5` staleness | `dist/mql5/SMC_Safety_Watchdog.ex5` dated Oct 7 vs `.mq5` dated Oct 15 — **owner must recompile in MetaEditor before the demo session** (report-only, per brief) |

## 2. Design ↔ code matrix (MANDATORY — re-derived from the binding design text, source read in full, NOT from commit lore)

### 2.A MODE T

| Design requirement (§ ref) | Code evidence | Verdict | Note |
|---|---|---|---|
| `diagnostic_entries` default false (§2.1) | `operator_config.py`: `ALLOWED_KEYS` + default false (test `test_operator_config_defaults_off`); live_demo.json absent { } | MATCH | |
| Tester config true + `require_demo` (§2.1/§5) | `config/live_tester.json` — true; `require_demo` true (test `test_tester_config_mode_t_on_and_demo`) | MATCH | |
| Exact startup banner string (§2.1) | `mode_t.py` `MODE_T_BANNER`, byte-equal check `test_banner_matches_design_verbatim`; printed once in run_operator gated on director presence | MATCH | |
| Session log records `mode:T` in session-start JSON (§2.1 final bullet) | run_operator `_run()` session-start JSON **lacks a `mode` key** (verified by reading the `json.dumps` payload: symbol/magic/dry_run/tf/terminal_path/python_pid/detection_tfs/degraded only) | **MISS (doc-grade, non-blocking)** | report-only per brief; logged posture banner + `MODE T enabled` log line exist instead; trivially fixable in a future non-diagnostic commit with owner sign-off |
| T2 only: LIMIT at proof-bar mid `(H+L)/2`, thesis direction, gate `abs(entry−close(proof))/ATR ≤ T_MAX_GAP_ATR` else skip (§2.2) | `mode_t.decide_mode_t`: `entry=(high+low)/2`, `gap_atr = abs(entry−close)/atr`, skip when `> T_MAX_GAP_ATR`; order/sizing only on PLACE | MATCH | geometry + gate exact; short side mirrored symmetrically |
| LIMIT not market (§2.3) | build-time `place_fn` calls `broker.place_limit(OrderRequest(...))` with `OrderKind.LIMIT`; no market path anywhere in the director | MATCH | |
| Product wins ties (§2.2 precondition 6) | `decide_mode_t` evaluation order puts `product_ticket_active → PRODUCT_PATH_TAKEN` BEFORE geometry (`test_product_wins_ties`); broker-truth scan `_product_ticket_active` excludes `mode=T`-commented tickets so the diagnostic book can never satisfy its own tie check | MATCH | conservative direction: an MT5 call failure reads False and demo caps still bound exposure |
| SL = proof adverse extreme; TP = entry ± 1.0 × ATR, Mode T's OWN brackets (§2.3) | `decide_mode_t`: `sl = low` (LONG) / `high` (SHORT); `tp = entry ± T_TP_ATR*atr`; `test_t2_short_brackets_mirror` | MATCH | |
| min lot floor 0.01; caps concurrent=2 / daily=6; rest 12 bars (§2.3/§2.4) | constants + tests (`test_frozen_constants_match_design`, `test_caps_fire_after_geometry` via decide, `test_director_rest_expiry_after_12_bars`, `test_director_daily_cap_resets_on_new_utc_day`) | MATCH | daily counter keyed to UTC date within the director |
| Skip taxonomy exhaustive and frozen (§2.2) | `SKIP_REASONS` frozenset has exactly the 10 fixed strings + `PLACE_REJECTED_<retcode>` via `place_rejected()`; `is_skip_reason` recognizes only these | MATCH | `directory.manage()` status reasons reuse the note's own vocabulary: REST_EXPIRED / INVALIDATED (INVALIDATED_BEFORE_PLACE) / FRIDAY_EOD / SESSION_STOP; PLACE_REJECTED tail only for broker rejects |
| One-shot per (poi, proof_bar) (§2.2) | director `_decided` dict keyed `(poi_id, proof_bar)`; `test_director_place_success_books_ticket` re-invokes with the same key and asserts `call_count == 1`, no re-send | MATCH | |
| Ledger `mode:T` / `mode_t_events.jsonl` with §2.5 fields + blank expert placeholders (§2.5) | `ModeTDecision.ledger_line` carries exactly the verbatim field list including `anomaly_ts_iso`, `cap_state_concurrent/daily`, `mode_t_ticket:"T"`, and the 5 placeholders hardwired to None; `ModeTLedger` appends JSON lines | MATCH | test `test_ledger_line_fields_per_note_2_5` asserts every field, including “anomaly_ts_iso”, and the 5始终-blank placeholders |
| dry_run still logs every decision, nothing sent (§1.4 of the prompt; implied §2.1 posture) | dry_run wiring: build-time `place_fn = None` when `cfg.dry_run` → `_send` returns `(False, "DRYRUN_NO_SEND")` → director emits a PLACE ledger line and then a `PLACE_REJECTED_DRYRUN_NO_SEND` ledger line; `_log "MODE T enabled (…dry_run=True…)"`; no broker call | MATCH (by explicit "empty place_fn" design in run_operator) | decision evidence survives; `PLACE_REJECTED_DRYRUN_NO_SEND` is honest; diary stays growable before the owner flips dry_run off |
| Mode T constants live in `mode_t.py`, not `locked_constants` (§1 style; §7 self-check) | `mode_t.py` header + `_locked_constants` import REJECTED by config (`test_config_rejects_mode_t_geometry_keys`); `git diff v1.1-pre-mode-T -- smc/config/locked_constants.py` empty | MATCH | also audited in the code directly: no T_* name anywhere in `locked_constants.py` |

### 2.B CONSOLE

| Design requirement (§ ref) | Code evidence | Verdict | Note |
|---|---|---|---|
| `judge_interval_s` knob, JSON number, default 60, `0`=off (§3.1) | config key added to `ALLOWED_KEYS` + OperatorConfig field, default 60 (`test_operator_config_defaults_off`); `judge_interval_used(0)/(None) is False` (`test_judge_knob_zero_disables`) | MATCH | |
| ≥1 full board per `judge_interval_s` EVEN WHEN FLAT (§3.1) | `run_operator._maybe_judge`: monotonic-interval check then `_publish_judgement()` in BOTH console modes; `test_flat_board_renders_with_mode_line` proves the flat renderer carries the honest idle line | MATCH | the idle branch is exercised explicitly |
| Blocks: MODE / POIS / SWEEPS / SEEKING / JUDGEMENT / BOOK / HEARTBEAT, fixed order (§3.2) | `judgement_console.render_judgement_board` pushes them in that exact order (header + MODE → POIS → SWEEPS → SEEKING → JUDGEMENT → BOOK → HEARTBEAT); block names asserted in the flat-board test | MATCH | |
| POIS/SWEEPS/SEEKING contents (direction, kind, zone_low-zone_high; sweep side/magnitude; poi_id + state/posture/trigger) (§3.2) | renderer formats each from the L1 read-only snapshot; honest empties `SWEEPS: none`, `SEEKING: none` | MATCH | |
| JUDGEMENT lines only from ledger tail, never invented (§3.2 close) | `_publish_judgement` builds lines ONLY from `director.ledger.tail(5)` rendering `{poi, proof, action, skip_reason, entry}`; empty → “JUDGEMENT: flat (no armed POI · no workflow · idle)” | MATCH | **observed wiring gap, report-only:** live JUDGEMENT currently only draws from the Mode T ledger — a PURE-PRODUCT (director None, diagnostic_entries=false) session never produces product-path judgement lines, only the flat idle line and the POIS/SWEEPS blocks. The design’s §3.2 sample shows a product-config judgement line (“SKIP: no Mode T”). Not a fill-only dead-knob; the flat guarantee still prints. Recorded as a wiring residual, not a design breach |
| Forbidden: fill-only status (§3.3) | event mode prints only queued-event reasons plus the judge board cadence; board prints when flat — never conditional on fills/MT5 errors | MATCH | `../test_mode_t_console_markers.py` shows no fill-only path |
| Forbidden: raw traceback as status (§3.3) | judgement lines built from structured dicts; tracebacks stay in events.log, deduped counts on the board | MATCH | |
| Forbidden: silent desirability inference (§3.3) | reasons come only from the frozen taxonomy or §5 state names; no “good zone” text anywhere in the renderer | MATCH | |

### 2.C MARKERS + EA

| Design requirement (§ ref) | Code evidence | Verdict | Note |
|---|---|---|---|
| Schema header verbatim (§4.2) | `MARKER_HEADER` = `id,symbol,kind,direction,price_high,price_low,timeframe_label,text,color_role,updated_at_utc,ephemeral`; asserted byte-exact in `test_writer_writes_header_and_rows_atomic` | MATCH | |
| Same directory discipline as the heartbeat (§4.1) | `_build_stack`: `marker_path` explicit wins; else heartbeat_path.parent; same rule as heartbeat | MATCH | |
| Full-rewrite atomic replace, never raise on failure (§4.1/§4.4) | `MarkerWriter.write` does write-temp + `os.replace` retries; on final failure falls back to an open/raw write with renameOf, and on write failure logs + returns False, never raises (`test_writer_never_raises_on_unwritable_dir`) | MATCH | **test-weak spot, report-only:** the never-raises test asserts a tautology (`writer.write([]) is False or writer.write([]) is True`) — the assertion never actually checks aFalse branch; it only keeps the OSError escapeGuarantee. A tightening candidate (out of scope for this audit; reference noted in residuals) |
| kinds: poi / sweep / entry_t / label (§4.2) | `_VALID_KINDS` + `snapshot_to_records` handles all four; label pair price fields 0.00 and label uses screen corner | MATCH | |
| ≤8 POI zones, 1 sweep, 1 entry_t, 1 label ⇒ total ≤11 (§4.3) | `MAX_POI_MARKERS=8`, `MAX_MARKER_OBJECTS=11`; writer slice caps at records[:11]; sweep only when snapshots name a linked armed POI (pointer never invented); `test_sweep_marker_needs_linked_zone`, `test_writer_caps_at_11_objects`, `test_writer_mode_t_entry_line` | MATCH | **pricing honesty residual from the note (carried):** the sweep hline uses the linked armed POI's zone edge as a *display* level, not a “sweep price”, because the link itself has no price; writer header discloses; honest, no invented number |
| EA safety first, markers second, failure can never disable safety (§4.1) | `OnTimer()` calls `CheckHeartbeat()` FIRST then `UpdateMarkers()`; `UpdateMarkers` is fully exception-tolerant (unknown role → clrSilver, malformed row → skip, unreadable file → `DeleteAllStrategyMarkers()`), never touches the emergency path; ZERO trading logic (verified by full `.mq5` read: only display + emergency close/delete exist) | MATCH (residual below) | |
| Stale marker file >30 s → delete all `SMC_*` (§4.4) | `MARKER_STALE_SECONDS=30` + `TimestampToEpoch` age check → `DeleteAllStrategyMarkers()`; objects only ever under prefix `SMC_` (`test`-verified ordering of safety-before-marker) | MATCH (residual below) | **residual, report-only per the same design's §4.4 wording intent:** on a FRESH-but-changed file, objects whose ids dropped out of the newest snapshot are not deleted at that tick — they are only removed by the (later) stale-clear or a `DeleteAllStrategyMarkers` pass. The design's per-id-cleanup phrasing (“stale objects whose ids are missing … DELETED on the matching timer tick”) is not implemented exactly; a stricter per-id diff is a future fix. Behavior stays safe (chart says nothing old >30 s); no trading semantics affected |
|.HEARTBEAT STALE corner label priority (§4.3/§4.4) | marker label DEgenerates: `HEARTBEAT STALE` (red) when `heartbeat_ok=False` (design priority STALE > Mode T > Mode A); `test_writer_stale_heartbeat_label` | MATCH | |
| Label object kind / corner anchoring, chart-TF independence (§4.2/§4.5) | EA `OBJ_LABEL` screens top-left via OBJPROP_CORNER + XDISTANCE/YDISTANCE (not a price anchor); rectangles carry updated_at ±1 h time window per design; no chart-TF logic | MATCH | |
| Both `.mq5` copies parity | byte-identical (cmp) | MATCH | |
| `.ex5` binary currency | **STALE** (owner must recompile; out of agent tools' scope) | N/A → owner action | report-only |

### 2.E WIRING / PRODUCT-PATH PROTECTION

| Design requirement | Code evidence | Verdict | Note |
|---|---|---|---|
| `run_operator` actually CALLS decide + console + markers on poll (not dead code) | `_on_poll` branch → `_mode_t_on_poll()` in the live poll loop (every poll, both console modes); `_maybe_judge` and `_maybe_markers` are invoked on their own cadences from the poll loop body / on console publish; the director is ONLY constructed when `cfg.diagnostic_entries` is true | MATCH | director built inside `_build_stack` under `if cfg.diagnostic_entries:`; product stack identical |
| Product path unchanged when `diagnostic_entries=false` | The entire Mode T filmmaker lives behind a flag-guarded constructor; NOTHING in the product path references the director when the flag is off (default = off = exactly the pre-Mode-T code path; the diff-vs-baseline only ADDS flag-gated branches). Verified by reading `_build_stack`, `_on_poll`, `_maybe_print_console`, `_publish_console` and the poll loop: no unconditional reference to `mode_t` symbols outside the director's constructor guard and the two POIs named in §2 | MATCH | `LOGIC_CHANGED` is effectively “YES only when the owner flips the flag; when it is off (live-demo, today) the runtime executes the pre-Mode-T code path verbatim” — a posture distinction the design itself defines (flag = the only change) |
| Mode T decision ledger engine lifestyle | Ledger path is `logs/<log_dir>/mode_t_events.jsonl`, created by the director from the operator config's `log_dir` (not hard-coded `phase_d`); no mode_t decision file writes outside this file | MATCH | |
| Product config never gets Mode T geometry via config | `operator_config` REJECTS any geometry key (`test_config_rejects_mode_t_geometry_keys`) and never stores one | MATCH | |
| Config smoke — live_demo.json loads with diag False; live_tester.json loads and honors diag ON + demo gate | `test_demo_config_diagnostic_entries_absent_or_false`, `test_tester_config_mode_t_on_and_demo` | MATCH | |

## 3. Test adequacy

**Inventory (all in `04_SRC/tests/test_mode_t.py` + `test_mode_t_console_markers.py`):**
`test_banner_matches_design_verbatim`, `test_frozen_constants_match_design`, `test_mode_t_constants_never_leak_into_locked_constants`, `test_skip_taxonomy_exhaustive_membership`, `test_t2_accept_places_limit_at_proof_mid`, `test_t2_short_brackets_mirror`, `test_t2_rejects_gap_beyond_0_25_atr`, `test_t2_gap_guard_quality_uses_small_atr_fail_closed`, `test_t2_no_atr_fails_closed_never_market`, `test_t2_session_and_spread_gates_precede_geometry`, `test_product_wins_ties`, `test_caps_fire_after_geometry`, `test_minimum_volume_error_when_broker_volume_invalid`, `test_duplicate_event_consumed`, `test_ledger_line_fields_per_note_2_5`, `test_director_place_success_books_ticket`, `test_director_place_rejected_emits_taxonomy_tail`, `test_director_rest_expiry_after_12_bars`, `test_director_invalidation_cancels`, `test_director_daily_cap_resets_on_new_utc_day`, `test_operator_config_defaults_off`, `test_tester_config_mode_t_on_and_demo`, `test_demo_config_diagnostic_entries_absent_or_false`, `test_config_rejects_mode_t_geometry_keys`, `test_ledger_tail_empty_when_missing`; `test_flat_board_renders_with_mode_line`, `test_mode_t_banner_block_when_flag_on`, `test_judgement_board_shows_skip_reasons`, `test_judge_knob_zero_disables`, `test_writer_writes_header_and_rows_atomic`, `test_writer_caps_at_11_objects`, `test_writer_stale_heartbeat_label`, `test_writer_mode_t_entry_line`, `test_sweep_marker_needs_linked_zone`, `test_writer_never_raises_on_unwritable_dir`.
35 new tests for a total of 1162; every number that the design FROZE is directly asserted.

**Gaps (report-only — none campaign-blocking, none weak-from-green):**
- `deliberate product-wins-tie at the DIRECTOR level (not just decide level)` is proven only via `test_product_wins_ties` (decide) — acceptable but the director-level branch (`_product_ticket_active` → skip) isn't separately unit-tested against a live adapter; the run-hour tests in `test_htf_post_sweep_path.py` cover the surrounding live poll seam and give full pass there (suite green), but a dedicated unit for the director+broker-truth SPREAD-gate ordering would be a gap worth noting if anything is ever tightened.
- gap guard boundary `== 0.25` accepted-skip is not separately pinned (the design freezes `<=` semantics via the `<` branch in `decide_mode_t` — implementation is exact; the test pins the `>0.25` rejection case and the compensating arbitrary-small-ATR fail-closed case instead).
- one flag exists as `judge_interval_s/logging off` in the UI → `JUDGEMENT-block zero knob disables the cadence entirely`, but no test covers the combination `judge_interval_s=0` + `_maybe_judge never publishes` on the OPERATOR object (only `judge_interval_used` unit-level).
- **Nothing was weakened to green.** The suite pass at 1162 counts; the two transient `test_perm_hardening` live-poll failures were root-fixed by re-anchoring the Mode T hook AFTER the spread/ATR/book block (the pre-existing tests were re-run green separately; re-ran the group 14/14 at implementation time). Neither assertion strength nor any test body was changed to pass.

## 4. Runtime / ops risks (no code change required, all report-only)

1. **Heartbeat vs marker path discipline:** same directory recipe (`heartbeat_path` parent, both resolved by `_build_stack`); heartbeat-MQL5 contract unchanged and check-first. No mismatch introduced from the Mode T work itself. Fold the init-time log `MARKER PATH RESOLVED` into every runbook so the operator always verifies just WHICH directory the terminal polls.
2. **Silent non-firing if proof events never reach the Mode T hook (the HONEST limitation, restated from the note):** Mode T observes ONLY `adapter.active_workflows()` (routed-not-accepted Stage-3 survivors). Anything that dies earlier (never-routed/never-swept/§5-only states) is invisible to Mode T by construction — no side-channel detection exists. Diagnostic activity will therefore ALWAYS concentrate on the product's own seen-workflow subset, exactly as §2.2's preconditions imply and as the note discloses. Not a defect; a fact the owner must internalize before reading demo results.
3. **Sweep marker level is the linked armed POI's zone edge** on the swept side (the link has no price). Display honesty carried in the writer header; no implications for decisions.
4. **`.ex5` stale + not pushed:** owner actions (recompile in MetaEditor; decide on pushing `9b649d5`).
5. **Dry-run parity note:** with `dry_run=true`, a Mode T decision emits PLACE → then a `PLACE_REJECTED_DRYRUN_NO_SEND` skip line (instead of no ledger entry). A future reader may miscount PLACEs. Accurate; disclose to the expert reading the demo ledger.
6. **Test-adequacy carry-over:** `test_writer_never_raises_on_unwritable_dir`'s double assertion is tautological (see §3); the underlying code is genuinely safe (write-temp + os.replace retries + in-place fallback + full-sweep OSError swallow), but the test proves less than its name suggests. Non-blocking hardening candidate — out of scope here.

## 5. Verdict + RETURN BLOCK

**Audit rule application:**
- PASS needs: all critical design rows MATCH; suite green; constants clean — none of the three have exceptions here, EXCEPT one doc-grade MISS (session-start `mode:"T"` JSON field) that is not in the critical list (critical = T2 geometry + flag defaults + product-off path + safety-first EA + mode=T logging + suite green). All of the critical set is verified MATCH; every single MISS or PARTIAL found is (a) non-strategy-geometry, (b) non-product-path, (c) non-safety, (d) non-threshold, and (e) documented here rather than fixed by silent code movement.
- Therefore per the brief's own verdict rules: **PASS_WITH_RESIDUALS** (residuals are doc-grade or owner-action, none blocking the design lock's promised behavior; the only path — T2 mid-entry, NO market fallback, ≤ flags/T caps — is exact).

```text
AUDIT_STATUS: PASS_WITH_RESIDUALS
DESIGN_REF: 00_LOCKED/MODE_T_CONSOLE_MARKER_DESIGN.md
COMMIT: 9b649d5
SUITE: 1162 passed (EXIT=0)
T2_MATCH: YES
CONSOLE_MATCH: YES
MARKER_EA_MATCH: YES
PRODUCT_PATH_UNCHANGED: YES
LOCKED_CONSTANTS_DIFF: empty
CRITICAL_MISS: none
RESIDUALS: run_operator session-start JSON lacks the §2.1 "mode":"T" key (doc-grade MISS, non-blocking); JS: EA per-id stale-object deletion deferred to the 30 s stale-clear instead of per-tick; live JS: live JUDGEMENT block only sources Mode T ledger events (pure-product sessions print the flat idle line only); entry_t marker line drawn in unit tests but mode_t_poi=None on the live wiring (display-only gap); .ex5 pre-recompile (owner, MetaEditor); never-raises test's assertion is tautological; posture distinctions (single-POINT rule T2 caps / dry-run PLACE→PLACE_REJECTED_DRYRUN_NO_SEND ledger geometry / product-judgement-line dry session) disclosed so no future reader miscounts.
LOGIC_CHANGED: NO
NEXT_READY: idea-vs-impl correction audit | internal demo | push
```

— End of audit. No `LOGIC_CHANGED` effects to T2 geometry, thresholds, product path, locked constants, or MQL5 safety were introduced by this session; `9b649d5` remains the sole, unpushed Mode T commit.
