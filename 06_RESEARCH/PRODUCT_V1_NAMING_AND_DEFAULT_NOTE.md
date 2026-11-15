# PRODUCT V1 NAMING + DEFAULT LAUNCH (2026-11-02)

**Authority:** Lead Architect "PRODUCT V1 NAMING + DEFAULT LAUNCH (RETIRE 'DUMB'
FROM PRODUCT SURFACE)" (GO)
**Scope:** renames, config defaults, console strings, launch wiring.
`LOGIC_CHANGED: NO` (no trading math / pillars / triggers / thresholds / SL-TP /
risk; `locked_constants` diff empty).

---

## 1. Survey (Part 0 — read-only, done before any edit)

Grep of `04_SRC`, `config/`, repo-root `run_live.bat`, `dist/`:

* `strategy_mode` exists ONLY in the live layer: `operator_config.py`
  (whitelist, normalize/validate, dataclass default), `run_operator.py`
  (adapter/feed selection branches, mode-note selection,
  `_session_start_payload`), plus the JSON configs. No usage outside the live
  layer.
* User/config `DUMB_*` occurrences at edit time: `config/live_demo.json`
  (`"strategy_mode": "DUMB_MTF_H4"`), the normalize/validation block + comments
  in `operator_config.py`, mode-note constants + branch comparisons in
  `run_operator.py`, the Console V2 builder (`build_dumb_mtf_snapshot`) and its
  tests (then `test_console_v2_dumb_console.py`).
* Which mode actually runs what:
  * default/internal **COMPLEX** path = the REAL product multi-TF path —
    `MultiTFProductRuntime` batches on every H1 close, `htf_batches` counting,
    engine armed book → Console V2 SCAN/ARMED. Product default detection
    timeframes already `("H4", "H1")`.
  * `DUMB_MTF_H4` = isolated H4 zone-book slice machine (`DumbMtfH4Feed` +
    `DumbMtfPaperAdapter`); `LiveLoop` gets `runtime=None`, so product batches
    never run and `htf_batches` stays 0 (probe finding of the bat-wire task).
  * `POLICY_MTF_H4` = the demoted tight H4-only freeze path (same isolated
    feed shape).
  * `COUPLED_MTF` = research/diagnostic full-menu family (unchanged).
* `dist/` = 2026-10-08 tester pack, STALE, never referenced by the repo-root
  bat → not rebuilt here; must not be a bat target.

## 2. Naming table (Part 1 — normative)

| Internal token (uppercase, validated) | Config value (lowercase accepted) | runs product MTF batches? | role |
|---|---|---|---|
| `PRODUCT_V1` (was `COMPLEX`) | `product_v1` | **YES** — H1 cadence, `MultiTFProductRuntime` | **DEFAULT**: live product baseline |
| `ARCHIVE_TIGHT_HTF` (was `POLICY_MTF_H4`) | `archive_tight_htf` | no (isolated feed) | demoted tight freeze — archived, **NOT** a live baseline (frequency/edge failed) |
| `RESEARCH_H4_ZONE_BOOK` (was `DUMB_MTF_H4`) | `research_h4_zone_book` | no (isolated slice; `htf batches may stay 0`) | research only; owns the H4 zone-book slice machine, NOT the product engine |
| `COUPLED_MTF` (unchanged) | `coupled_mtf` | no (isolated feed) | research/diagnostic family |

**Judgement MODE letters (A/T) stay as-is.** Map, documented here and in
`_session_start_payload`: the session-start JSON discriminates `T`
(`diagnostic_entries=true`) else `A`; `RESEARCH_H4_ZONE_BOOK` now labels the
mode field `RESEARCH_H4_ZONE_BOOK` explicitly (was the `DUMB_MTF_H4` string).
Judgement board block list untouched (design lock §3.1).

**Alias policy (chosen: map + one-time deprecation warning).** Legacy config
values `COMPLEX`, `DUMB_MTF_H4`, `POLICY_MTF_H4` map at config load to
`PRODUCT_V1`, `RESEARCH_H4_ZONE_BOOK`, `ARCHIVE_TIGHT_HTF` respectively, with a
ONE-time notice per legacy value (stdout `[config] DEPRECATION: ...` +
`logging.warning`; our wording never prints the nickname — only the
professional target id). Legacy ids are accepted THIS RELEASE ONLY; the next
release rejects them. Runtime never sees a legacy token.

**Internal symbol renames — DEFERRED (explicitly, per ruling).** Package/class
renames `smc.dumb.*` (`DumbMtfH4Feed`, `DumbMtfPaperAdapter`, `DumbMtf*`, …)
and local identifiers (`dumb_mtf_feed`, `_drive_dumb_mtf`) are internal only
and touch many research scripts + tests; NOT cost-bounded for this task.
Everything user-facing, config-facing and console-rendered is renamed NOW.

## 3. What changed

1. `04_SRC/smc/live/operator_config.py` — canonical mode set
   `STRATEGY_MODES`, legacy alias table + one-time deprecation notice at load,
   dataclass default `strategy_mode = "PRODUCT_V1"`, all validation sites
   (M5 constraint for `research_h4_zone_book`, `=["H4"]` lock for
   `archive_tight_htf`, diagnostic-entries conflicts) speak the new ids; the
   unknown-id error lists the four new product ids.
2. `04_SRC/smc/live/run_operator.py` — branch comparisons/mode tokens renamed
   (`RESEARCH_H4_ZONE_BOOK` / `ARCHIVE_TIGHT_HTF`); note constants renamed:
   `_PRODUCT_NOTE_STATUS` = "PRODUCT V1 (multi-TF) - HTF batches drive
   SCAN/ARMED; waiting for first HTF batch - …" (auto-clears when batches
   flow), `_RESEARCH_NOTE_STATUS` = "RESEARCH H4 zone-book (not product
   batches; htf batches may stay 0)", `_RESEARCH_SNAPSHOT_NOTE` (research
   slice book vs product locked-Pillar engine book), `_ARCHIVE_NOTE_STATUS`
   for archive/diagnostic feed modes; error-state string and comments
   de-named; imports of the renamed builder.
3. `04_SRC/smc/live/structure_console.py` — `build_dumb_mtf_snapshot` →
   `build_research_h4_zone_book_snapshot`, `DUMB_ACTIVE_STATUS_NAMES` →
   `RESEARCH_SLICE_ACTIVE_STATUS_NAMES`, docstrings rewritten; **neutral
   display id**: research zone-book rows now render `zb-<8-hex-digest>`
   (stable sha1 prefix of the internal poi id) so NO package-prefix string
   (∴ no nickname) can appear on the board; internal poi_id strings untouched.
4. `config/live_demo.json` — `"strategy_mode": "product_v1"` +
   explicit `"detection_timeframes": ["H4", "H1"]` (product default). Ops
   fields left as the operator last chose (`dry_run: false`,
   `require_demo: true`).
5. `run_live.bat` — top comment "Default: PRODUCT V1 multi-TF
   (config\live_demo.json -> product_v1; HTF batches drive SCAN/ARMED once
   the first batch lands)". Entry shape unchanged (correct tree & entrypoint).
6. Tests — old console test renamed to
   `04_SRC/tests/test_research_h4_zone_book_console.py` (11 tests: research
   zone-book console family + naming suite: product_v1 default, canonical &
   lowercase ids, legacy map + one-time warning, unknown id fails loud,
   case-insensitive no-"dumb" render check across all console surfaces,
   product mode drives `MultiTFProductRuntime` batches via the `LiveLoop`
   seam while isolated slice modes get `runtime=None`). `test_operator_pack.py`,
   `test_policy_mtf_h4.py`, `test_coupled_mtf.py` updated to the new ids.
   `config/live_policy_h4.json` (untracked, another session's file) left
   as-is — loads via the alias map (accept-one-release policy).

## 4. Default launch is REAL product wiring — not a label

`product_v1` maps to the former `COMPLEX` internal path, which is the
**real** loop wiring: `_build_stack` constructs one `MultiTFProductRuntime`
for the session and passes it to `LiveLoop`; without an isolated feed the
loop keeps `runtime` → product batches run, `htf_batches` counts up after the
first H1 close, `_refresh_mtf_board` publishes the MTF block and
`_maybe_refresh_structure` builds the product SCAN/ARMED book from the batch
report. Pinned by `test_product_mode_invokes_the_multi_tf_runtime_batches`.

## 5. Tight-path demotion rationale (documented per Part 1)

The tight H4(+H1)-only freeze path failed on trade frequency/edge as a live
baseline in prior studies (governance 2026-11-01 (3) fill-leg study: F/A
family split; gave-back cut REJECTED the ≥1R-back exit change at 73.1%
adverse exposure). `ARCHIVE_TIGHT_HTF` is retained, demoted, never a default
and never shown as a success baseline. No archive code deleted.

## 6. How to verify (ops recipe)

```text
1) notepad config\live_demo.json     -> strategy_mode "product_v1",
                                        detection_timeframes ["H4","H1"]
2) run_live.bat
   -> banner + [console] note "PRODUCT V1 (multi-TF) - HTF batches drive
      SCAN/ARMED; waiting for first HTF batch..."
   -> after the first H1 close: htf batches >= 1; status board mtf: block;
      STRUCTURE console SCAN/ARMED from the product batch report
3) case-insensitive check: grep the console mirror for "dumb" -> zero hits
   in NEW renders
4) legacy config still loads this release: value maps once, prints ONE
   [config] DEPRECATION line, and lands in the mapped canonical mode
5) run_live.bat NEVER targets dist\ (stale 2026-10-08 pack — rebuild is a
   separate task)
```

## 7. Bans honoured / status

* No SL/TP/pillar/threshold/risk change; `04_SRC/smc/config/locked_constants.py`
  diff EMPTY.
* No archive code deleted (tight path demoted to `ARCHIVE_TIGHT_HTF` only).
* No edge/expectancy claims; console copy is posture/status language only.
* Test suite at edit time: **1385 passed** (`$env:PYTHONPATH="04_SRC"; python
  -X utf8 -m pytest -q 04_SRC\tests`).
* Live-operator context: a live session (`run_operator.py --config
  config\live_demo.json`, `dry_run=false`) may still be running (PID seen
  2026-11-02); do NOT launch a second session — the new default activates at
  the next `run_live.bat` restart.
