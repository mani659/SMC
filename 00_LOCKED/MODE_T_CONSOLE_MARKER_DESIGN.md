# MODE T + CONSOLE JUDGEMENTS + CHART-MARKER CONTRACT — DESIGN LOCK

**Status:** BINDING DESIGN LOCK · docs-only · pending implementation prompt
**Date:** 2026-10-15
**Baseline:** tag `v1.1-pre-mode-T` (revert point)
**Mode T posture:** DIAGNOSTIC ONLY — visible activity + labelable tickets; NOT a claim that entry representation is fixed; NOT Mode A production entry identity; NOT Mode B; NOT threshold fishing on retired families.
**Entry-rep families (proximal-edge FR-3.1, RL-1/2/3, reactive R1–R6, LTF-return coverage):** remain RETIRED — this design reopens none of them; Mode T's proof-close/mid placement is an *observed* benchmark placement for labelling, not a resurrected representation rule and never blent with any verdict.
**Authoritative order:** LOCKED_DECISIONS → POST_V1_PLAN_OF_ACTION → LEAD_ARCHITECT_ROLE_AND_PROTOCOL → PRODUCT_RUNTIME_CONTRACT → this note → SESSION_HANDOFF.

---

## §1 CURRENT BEHAVIOR SURVEY (files + what exists today)

| Seam | File | Current behavior |
|---|---|---|
| Operator entrypoint | `04_SRC/smc/live/run_operator.py` | identity check (terminal dir + require_demo) → stack build (PipelineEngine → PipelineAdapter → PaperRunner + RiskEngine + OrderManager/PositionManager over LiveLoop) → poll loop. Console: event mode prints the full board only on queued events (new bar, HTF batch, flow/KPI change, new error, shutdown) + one short alive line per `alive_interval_s` (300 s default). No judgement lines, no flat-cadence board, nothing chart-facing except the heartbeat file. |
| Status board | `04_SRC/smc/live/operator_console.py` | `render_startup_banner` / `render_status_board` / `render_alive_line` (pure renderers over session state). |
| Structure console | `04_SRC/smc/live/structure_console.py` | L1 read-only snapshot + render: POIS (W1/D1/H4/H1), SWEEPS, SEEKING, PLAN. ASCII-only, refresh on batch change (immediate) or new bar (rate-limited by `console_refresh_s`). Honest empties. |
| Operator config | `04_SRC/smc/live/operator_config.py` | strict whitelist `ALLOWED_KEYS`; unknown keys + locked quantities rejected loud. Keys today: terminal_path, symbol, magic, dry_run, require_demo, risk_fraction, timeframe, detection_timeframes, allow_single_tf_degraded, allowed_sessions, heartbeat_path, heartbeat_interval_s, poll_interval_s, console_refresh_s, console_mode, alive_interval_s, log_dir. |
| Heartbeat (Python) | `04_SRC/smc/live/heartbeat.py` + `heartbeat_path.py` | writes `<unix_epoch_seconds> <sequence>` + `state=<running|shutdown>` every `heartbeat_interval_s` (1 s); path candidates ordered terminal data folder → install-dir derivation → config → project-local; write-probed at startup; heartbeat failure fails the session loudly. |
| Heartbeat (EA) | `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` | inputs: InpHeartbeatFile (`smc_heartbeat.txt`), InpStaleTimeoutSec (5), InpTimerSeconds (1), InpMagicFilter, InpSymbolFilter, InpClosePositions, InpDeletePendings. 1 s timer reads line 1; stale/unreadable → emergency (close + delete scoped) re-asserted ≤ every 30 s. NO strategy logic, NO chart drawing today. |
| Entry placement path | `04_SRC/smc/orchestration/engine.py` → `04_SRC/smc/backtest/pipeline_adapter.py` (active_workflows / build_limit_request) → `04_SRC/smc/backtest/pipeline_bridge.py` (`candidate_from_route`) → paper/runner → `04_SRC/smc/execution/order_manager.py` | product path: armed POI → §5 seek → Stage-3 proof → trigger route → limit request. §10 frozen: ALL trigger entries are LIMIT orders (`place_limit`); `place_market` reachable only from risk exits. Mode T must branch at the **candidate/limit seam** (a second builder after the route), never fork detection/seek/risk. |

**Console gaps vs this design:** no MODE line; no judgement line; no guaranteed print while flat (event mode can stay silent for the whole interval); no chart visibility. **EA gaps:** no marker reader, no object drawing, no marker-file input.

---

## §2 MODE T — NORMATIVE RULES (all values frozen)

### 2.1 Flag + banner
- **Config key:** `diagnostic_entries` (JSON **bool**, default **false**). Forbidden from `LOCKED_FORBIDDEN_KEYS` (it is a posture flag, not a locked quantity); added to `ALLOWED_KEYS` at implementation.
- **Product configs (`config/live_demo.json`, any future live config):** default OFF; the key is absent → OFF. Never edited "for convenience".
- **Tester config (`config/live_tester.json`, new):** `"diagnostic_entries": true` + `"require_demo": true` recommended default.
- **Startup banner when ON (exact string, printed once to stdout + console mirror):**
  ```
  [MODE T] DIAGNOSTIC ENTRY PATH ACTIVE — every order logs mode=T; product Mode A path unchanged; diagnostic only, NOT a strategy claim
  ```
- Session log line additionally records `mode=T` in the SESSION START JSON (`"mode": "T"` vs `"A"`).

### 2.2 When Mode T may propose an entry (ONE primary rule, frozen: **T2**)
Preconditions (ALL must hold, evaluated in order):
1. `diagnostic_entries` is true (banner printed);
2. an HTF POI (H4/H1) is **armed** with a classified §5 arm posture on the current engine state;
3. **Stage-3 proof completion on the M5 execution series**: the proof bar has closed (no mid-bar decisions — the proposal is built strictly after `bar close` of the completion bar);
4. session gate passes (reuse the config's `allowed_sessions` unchanged);
5. spread/quality gate passes (the existing §28.5 grade gate enforced by the risk layer, unchanged — Mode T never bypasses it; a block is logged, not bypassed);
6. no product-path candidate exists for the SAME POI + completion bar (product wins; Mode T logs skip and stands down).

**Primary rule T2:** place ONE pending **LIMIT** order at the **mid of the proof bar**, `entry = (high(proof) + low(proof)) / 2`, in the thesis direction of the POI (bullish → BUY_LIMIT, bearish → SELL_LIMIT), **iff**
`abs(entry − close(proof)) / ATR(M5) <= T_MAX_GAP_ATR = 0.25`;
otherwise log `skip_reason=GAP_TOO_WIDE` and place nothing.

- Exactly ONE Mode T order per POI per proof-completion event (episode-keyed one-shot: POI id + completion bar index).
- If `ATR(M5)` is unavailable/non-positive → `skip_reason=NO_ATR` (fail-closed, never a market fallback).
- Forbidden shapes (restated): any confirm→market-in path; any placement derived from the HTF zone proximal edge (retired family); any retry/second chance after a skip.

**Skip taxonomy (frozen, exhaustive; anything outside these strings is an implementation bug):**
`GAP_TOO_WIDE | NO_ATR | NO_SESSION | SPREAD_GATE | DUPLICATE_EPISODE | PRODUCT_PATH_TAKEN | CAP_CONCURRENT | CAP_DAILY | MINIMUM_VOLUME_ERROR | INVALIDATED_BEFORE_PLACE | PLACE_REJECTED_<retcode>`

### 2.3 Order type, SL/TP, sizing, caps (all frozen; no silent inherit)
- **Order type:** LIMIT only (`OrderManager.place_limit` × `OrderKind.LIMIT`). Market entries for Mode T are forbidden; lower anchors reused verbatim.
- **SL (Mode T diagnostic):** adverse extreme of the proof bar (LONG → `low(proof)`; SHORT → `high(proof)`).
- **TP (Mode T diagnostic):** `entry ± T_TP_ATR × ATR`, `T_TP_ATR = 1.0` (direction-favorable). Mode T does NOT inherit FR-2 / structural TP / product stop geometry — its brackets are deliberately its own so diagnostic tickets are recognizably non-product. (FR-2 remains untouched for the product path.)
- **Volume:** session minimum lot (connector `volume_min`, floor 0.01). Fixed micro risk; NO risk_percent sizing.
- **Caps (hard):** `T_MAX_CONCURRENT = 2` open Mode T positions; `T_MAX_PER_DAY = 6` new Mode T entries per trading day (date-based counter); exceed → skip reasons `CAP_CONCURRENT` / `CAP_DAILY`.
- **Identifiability:** every Mode T order carries comment prefix `mode=T` (product keeps its existing route comment); the console/BOOK and marker layer tag accordingly. Diagnostic tickets remain inside the watchdog scope (they are demo tickets; emergency close/delete applies to them too).

### 2.4 Expiry / cancel
- **Resting lifetime:** `T_REST_BARS = 12` M5 bars unfilled → cancel by the operator layer, skip/status `EXPIRED` logged (12 bars, distinct from any product lifetime constant — Mode T does not set or reuse product R8 lifetime).
- **Cancel on POI §5 invalidation** (engine state transitions to VIOLATED/SCAN_CLOSED for the linked POI) → cancel the resting limit, status `INVALIDATED`.
- **Friday EOD:** all Mode T pendings + positions force-cancelled at `FRIDAY_EOD_CLOSE_HOUR_UTC` (existing §28.4 behavior, reused verbatim).
- **News:** V1 diagnostic has no news-event feed on the live path → **no separate news cancel**; the heartbeat watchdog + session stop remain the kill switches. Stated honestly, not papered over.
- **Session stop / Ctrl+C:** clean shutdown cancels resting Mode T limits like any pendings; open diagnostic positions are left to the static watchdog (safety EA) exactly as product tickets would be.

### 2.5 Logging (required per ticket + per decision)
Every Mode T decision (place OR skip) emits one structured JSON line to `logs/phase_d/` (`mode_t_events.jsonl`) with EXACTLY these fields:
`mode:"T", anomaly_ts_iso, poi_id, detection_tf, exec_tf:"M5", proof_bar, trigger_letter (product §5 route letter or "T2"), action:"PLACE"|"SKIP", entry, sl, tp (null on SKIP), gap_atr (null on SKIP), skip_reason (null on PLACE), volume, cap_state_concurrent, cap_state_daily, mode_t_ticket:"T"`.
Expert-scorecard placeholders (appended to the same line, V1 BLANK — filled later by human/measure rounds, never by code):
`level_ok: null, sweep_ok: null, confirm_ok: null, timing: null ("early|ok|late" space reserved), would_take: null`.
The live console exposes the same fields on the JUDGEMENT/BOOK lines.

### 2.6 Explicit non-goals
- NOT production Mode A entry identity; Mode A stays scarce/frozen exactly as locked.
- NOT Mode B mid-TF strategy.
- NOT threshold fishing on retired families (no proximal-edge return, no LTF-return R&D reopened, no reinterpretation of the FAIL_COVERAGE verdict).
- No expectancy/PF claims in any Mode T artifact; the only success metrics are VISIBLE ACTIVITY + labelable tickets + `mode=T` tag on all of them.

---

## §3 CONSOLE JUDGEMENTS — CONTRACT

### 3.1 Cadence (knob named)
- New config key: `judge_interval_s` (JSON number, default **60.0**, `0` = off). Implementation: `ALLOWED_KEYS` + `OperatorConfig` field.
- Guaranteed minimum: ONE full judgement board at least once per `judge_interval_s` **even when flat / zero trades** — event mode's "no event → no print" rule is superseded for this block; the alive ping remains the short liveness line.
- Additionally the judgement board rides every structure refresh (batch-change immediate; new-bar refresh `console_refresh_s`-limited) exactly as the L1 snapshot does today.

### 3.2 Required blocks (fixed order; plain language)
```
MODE:        A    (or)   A + [MODE T] banner line
POIS:        per-TF counts W1/D1/H4/H1 (armed n / detected n); the top armed zone per live TF:
             direction, kind, zone_low-zone_high
SWEEPS:      last/active sweep per armed POI (side, magnitude_atr) or SWEEPS: none
SEEKING:     poi_id + §5 state + posture (+ target trigger letter) or SEEKING: none
JUDGEMENT:   one line per live workflow, e.g.
               "POI H4 2650-2655 bull · sweep yes · proof F pending · SKIP: no Mode T"   (product config)
               "POI H4 · proof F done · gap 0.31 > 0.25 · SKIP: GAP_TOO_WIDE"            (Mode T)
               "POI H4 · proof F done · Mode T LIMIT 2651.8 · reason proof_close-mid"    (Mode T placed)
BOOK:        open positions / pendings count, each product-or-T tagged, product first
HEARTBEAT:   seq / age_s / EA-path readability hint (steady reading of existing hb state + fallback flag)
```
- `JUDGEMENT` lines are built from the same read-only snapshot + the Mode T decision ledger (`mode_t_events.jsonl` tail) — never from invented state; a stale/empty reason over a flat session prints `JUDGEMENT: flat (no armed POI · no workflow · idle)`.

### 3.3 Forbidden
- Only printing when a fill happens or when an MT5 error appears.
- Dumping raw Python tracebacks as the operator-visible "status" (tracebacks stay in events.log; the board shows the deduped error counter).
- Any judgement content that silently infers trade desirability (no "good zone" language; reasons come from the named skip taxonomy or state names).

---

## §4 CHART-MARKER CONTRACT (Safety EA + marker printer)

### 4.1 Architecture (frozen)
- One EA attach remains: `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` gains a marker-printer DUTY on the SAME 1 s timer (`OnTimer` → `CheckHeartbeat()` then `UpdateMarkers()`), same symbol/magic scope inputs, ZERO trading logic beyond the existing emergency behavior. Safety first, markers second, marker failure can never disable safety (each duty wrapped; marker exceptions logged and skipped).
- Python writes ONE marker snapshot file with the SAME directory discipline as the heartbeat — resolved by the same `heartbeat_path_candidates` recipe with the marker filename, write-probed at startup; every snapshot is a FULL REWRITE via write-temp + atomic replace (mirroring the heartbeat publisher's strategy).
- **Filename (default):** `smc_markers.csv`, config key `marker_path` (JSON string; empty/unset → same EA-readable directory as the heartbeat, `smc_markers.csv`);
  **new key `marker_enabled`** (JSON bool, default **true**; false → Python writes no markers and the EA clears them on staleness).
- **EA input:** `input string InpMarkerFile = "smc_markers.csv";` (alongside existing `InpHeartbeatFile`, `InpSymbolFilter`, `InpMagicFilter`).

### 4.2 Schema (normative — CSV, header + one record per line)
```
id,symbol,kind,direction,price_high,price_low,timeframe_label,text,color_role,updated_at_utc,ephemeral
poi-abc12345,XAUUSDm,poi,BULL,2655.10,2650.20,H4,H4 demand armed,bull_green,2026-10-15T09:30:00Z,false
sweep-abc12345,XAUUSDm,sweep,SELL,2650.00,2650.00,H4,sweep last (SSL),bear_red,2026-10-15T09:30:00Z,false
entry-t-abc12345,XAUUSDm,entry_t,SELL,2651.80,2651.80,M5,Mode T LIMIT 2651.8 gap 0.31 skipped,mode_T_orange,2026-10-15T09:30:00Z,false
label-session,XAUUSDm,label,NONE,0.00,0.00,,SMC Mode T · live,label_gray,2026-10-15T09:30:00Z,false
```
- Field rules: `kind ∈ {poi, sweep, entry_t, label}`; `direction ∈ {BULL, BEAR, SELL, BUY, NONE}` (poi/sweep/respectively); zero prices (`0.00`) mean "draw at price 0" is FORBIDDEN — the label row carries prices 0.0 and the EA anchors `OBJ_TEXT` in screen corner, never on price; `ephemeral=true` rows are cleared by the next snapshot regardless of age.
- **No header row is parsed by the EA beyond line 1 skip; records after the max cap are ignored by the EA (writer stops before the cap anyway).**
- **Chart-TF independence:** every drawn coordinate is a PRICE (and for rectangles a price band + no time binding — MQL5 `OBJ_RECTANGLE` gets anchor time from the file's `updated_at_utc`-1h forward window). Chart timeframe selection changes nothing in logic — D4.5 non-goal.

### 4.3 What to draw (V1 lean, caps frozen)
- **Armed POI zones:** `OBJ_RECTANGLE` per armed POI, capped at the newest **8** (`MAX_POI_MARKERS`); id `SMC_zone_<marker_id>`.
- **Sweep line:** ONE `OBJ_HLINE` at the last sweep price of any armed POI (`SMC_sweep`).
- **Mode T entry line:** ONE `OBJ_HLINE` for the latest Mode T decision price — placed `entry` or the skipped entry (text carries the skip reason)(`SMC_entry_t`).
- **Corner label:** ONE `OBJ_TEXT` in the top-left corner: `SMC Mode A` | `SMC Mode T` | `HEARTBEAT STALE` (priority: STALE > Mode T > Mode A).
- **Total object cap: 11** (8 + 1 + 1 + 1). Anything beyond is never drawn, and stale objects whose ids are missing from the current file are DELETED on the matching timer tick — the chart mirrors the last good snapshot exactly, nothing more.

### 4.4 Staleness + safety unchanged
- **Marker file staleness:** if the marker file is missing/unreadable OR its `updated_at_utc` is older than `MARKER_STALE_S = 30` s, the EA **deletes all `SMC_*` objects** (chart says nothing rather than drawing old structure).
- **Heartbeat staleness:** unchanged behavior — emergency close/delete scoped positions + pendings per existing policy; the corner label switches to `HEARTBEAT STALE`.
- **Safety unchanged:** heartbeat check runs FIRST on every timer tick; a marker read/draw failure (bad file, bad row, ObjectCreate failure) logs to the Experts tab and RETURNS without touching the safety path. No new EA input changes the watchdog behavior.
- **EA duties (frozen):** create/move/delete `OBJ_RECTANGLE` / `OBJ_HLINE` / `OBJ_TEXT` matching the scoped symbol only. MUST remain: no triggers, no sizing, no "should enter", no strategy logic of any kind.

### 4.5 Non-goals
- No full dashboard GUI (no panels, buttons, tables).
- No EA-side signal generation or judgement text beyond the schema's `text` field verbatim.
- No dependency on the user's selected chart timeframe for any logic.

---

## §5 CONFIG / RELEASE SURFACE (exact keys)

### `config/live_tester.json` (new; recommended tester defaults)
```json
{
  "terminal_path": "<tester terminal exe path>",
  "symbol": "XAUUSDm",
  "magic": 20260919,
  "dry_run": true,
  "require_demo": true,
  "risk_fraction": 0.01,
  "timeframe": "M5",
  "allowed_sessions": null,
  "heartbeat_path": "logs/phase_d/heartbeat.txt",
  "heartbeat_interval_s": 1.0,
  "poll_interval_s": 0.5,
  "console_refresh_s": 30.0,
  "console_mode": "event",
  "alive_interval_s": 300.0,
  "log_dir": "logs/phase_d_tester",
  "diagnostic_entries": true,
  "judge_interval_s": 60.0,
  "marker_enabled": true,
  "marker_path": ""
}
```
### `config/live_demo.json` (product demo — Mode T caller-visible state: stays OFF)
- Same keys as today; `diagnostic_entries` ABSENT (defaults false) — never added "for convenience"; `judge_interval_s`, `marker_enabled`, `marker_path` added as observability keys (Mode-A console/judgement blocks are posture-independent and stay on).
- `dry_run` remains `true`.

### Mode T design constants (NOT locked_constants; NOT operator-tunable)
Implementation home: a new `04_SRC/smc/live/mode_t.py` header (module constants, tests pin them):
`T_MAX_GAP_ATR = 0.25 · T_TP_ATR = 1.0 · T_REST_BARS = 12 · T_MAX_CONCURRENT = 2 · T_MAX_PER_DAY = 6`

### Release-document duties (next tester zip)
1. Mode T ON in the tester config (§5 above) + `require_demo: true`.
2. Marker file path aligned to the terminal data folder (same recipe as heartbeat; README states the EA reads `MQL5/Files/smc_markers.csv`).
3. README one-pager: zone colors, sweep/entry line semantics, `HEARTBEAT STALE` corner state, and the level/early-late scorecard placeholders the expert will fill (`level_ok / sweep_ok / confirm_ok / timing`).

---

## §6 VERDICT / SUCCESS (pre-registered)

- **Design-lock success (THIS task):** the note is complete with no "vague confirm"; all three seams carry file/config names + frozen values; implementation can start without inventing rules mid-code.
- **Runtime success (LATER, separate implementation task):** the expert sees the corner label + at least one zone marker and/or console judgement lines within minutes of session start; Mode T produces diagnostic tickets under demo caps on real activity; EVERY such ticket/log carries `mode=T`; the product path remains identifiable (comment/marker `kind` separation; product tickets never carry `mode=T`).
- Not a claim and never read as: edge, expectancy, or entry-representation repair.

---

## §7 SELF-CHECK (per task directive)

- [x] Detection / pillars / seek §5a / risk §28 / product TF roles unchanged — only the candidate/limit seam gains a second, flag-gated builder (§2.2 precondition 6 makes product strictly win ties).
- [x] MQL5 draws + protects only — marker duties + emergency path enumerated; §4.4.
- [x] Mode T default OFF product / ON tester — §2.1 + §5 matrix.
- [x] Every Mode T decision/order tagged `mode=T` — §2.3 + §2.5.
- [x] No expectancy/PF claims — §2.6 + §6.
- [x] HTF-edge / LTF-return R&D not reopened — header stance + §2.6; the proof-close/mid entry is diagnostic-only and never blended with any verdict.
- [x] Chart-TF display-only — §4.2 + §4.5.
- [x] Heartbeat path stays EA-readable — marker file reuses the same discipline; no heartbeat change.
- [x] Skip taxonomy + gap guard — §2.2; no "always market in".
- [x] LOGIC_CHANGED: NO (docs-only); `locked_constants.py` untouched by this design (Mode T constants named for the FUTURE implementation module, not that file).

---

## §8 DELIVERABLES / NEXT

- Design lock: THIS file, `00_LOCKED/MODE_T_CONSOLE_MARKER_DESIGN.md`.
- Governance synced: `SESSION_HANDOFF.md`, `POST_V1_ACTIVE_TODO.md`, `00_LOCKED/CHANGELOG.md` (2026-10-15 entry; docs-only).
- NEXT READY: **implementation prompt** — the operator-flag Mode T builder at the candidate/limit seam (~§2), console judgement blocks (`judge_interval_s` + flat guarantee, ~§3), marker file writer (Python) + watchdog EA marker-reader duties (MQL5 only draws/protects, ~§4), config keys per §5, tests pinning every frozen constant + skip taxonomy. Baseline revert point: tag `v1.1-pre-mode-T`.
