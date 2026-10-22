# MODE T — RESIDUAL FIXES NOTE (Part 1 of the residual-fixes engagement)

**Date:** 2026-10-15 · implements the three confirmed-audit residuals; base commit `9b649d5` · LOGIC_CHANGED: YES (observability wiring only — no T2 formula, taxonomy, caps, SL/TP, or product-path change) · `locked_constants.py` diff against `v1.1-pre-mode-T`: EMPTY (verified post-edit).

## What changed (R1–R3, exactly)

1. **R1 — entry_t marker goes LIVE.** `ModeTDirector.latest_entry_marker()` (new, read-only, [04_SRC/smc/live/mode_t.py](../04_SRC/smc/live/mode_t.py)): returns the latest PLACE decision's `{poi_id, direction(BUY/SELL), entry, text}`. Display policy mirrors the book: booked resting ticket → `Mode T LIMIT <price>`; filled → `…(filled)`; dry-run decision (nothing sent) → `…(dry-run, not sent)`; rejected / cancelled / expired / invalidated place → NO row (no phantom line the book can't corroborate). `run_operator._maybe_markers` now passes that dict as `mode_t_poi` instead of `None`, and the marker signature includes the entry line's poi/entry/text so a new dry-run decision refreshes the snapshot (no book change to piggy-back on) and fill/cancel/expiry drops or updates it. No new marker kinds; ≤11-object cap untouched.
2. **R2 — session-start JSON carries `mode` (§2.1).** `_SessionStartPayload` helper `_session_start_payload()` on `OperatorSession`; payload now has `"mode": "T" | "A"`. Source of truth is the CONFIG FLAG, not the director reference: the director is only built inside `_build_stack()` (iff the flag is true), so the flag is the posture's truth at logging time and the two can never disagree. Banner + `MODE T enabled` log lines unchanged (verbatim §2.1 string preserved).
3. **R3 — tautological writer test strengthened.** `test_writer_never_raises_on_unwritable_dir` asserted `write() is False or True` (a tautology flagged by the confirmation audit). It now constructs a REAL failure (marker parent is a file → mkdir/replace genuinely raise an OSError subclass) and asserts `write() returns exactly False` with no escape. The code path itself was independently verified safe pre-fix; only the test's assertion grew teeth.

## Tests (+5, suite 1162 → 1167, EXIT=0)

`test_entry_t_row_lives_while_ticket_is_booked` (entry_t row present, BUY/price 100.00/id prefix, via writer output), `test_entry_t_row_clears_after_cancel` (rest-expiry cancel → line off the chart), `test_entry_t_dry_run_row_is_flagged_not_sent` (SELL/(dry-run, not sent)), `test_rejected_place_never_draws_entry_t` (ledger keeps trail, chart shows nothing), `test_writer_never_raises_on_unwritable_dir` (rewritten — real failure, exact False), `test_session_start_payload_carries_mode_disriminator` (T with the flag, A without). No test was weakened; the R1/R2 lines are additive.

## Residuals still open (unchanged, for the idea-vs-impl audit)

- `.ex5` stale binary — owner must recompile `dist/mql5/SMC_Safety_Watchdog.mq5 → .ex5` in MetaEditor before the tester demo.
- EA per-id marker cleanup still deferred to the 30 s stale-clear (design §4.3 per-tick wording not implemented; behavior stays safe — chart says nothing old).
- Live JUDGEMENT block still sources only the Mode T ledger (pure-product sessions print the flat idle line; product-config sample lines of §3.2 not reconstructed).

## Return block

RESIDUAL_FIX_STATUS: PASS
ENTRY_T_LIVE: YES
SESSION_MODE_JSON: YES
SUITE: 1167
LOCKED_CONSTANTS_DIFF: empty
COMMIT: none (working tree left for the owner; previous authorization covered the Mode T implementation commit only)
