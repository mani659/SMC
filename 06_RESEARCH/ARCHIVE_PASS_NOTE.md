# ARCHIVE PASS — LOGS + OBSOLETE ARTIFACTS (2026-11-02)

**Authority:** Lead Architect "ARCHIVE PASS — LOGS + OBSOLETE ARTIFACTS
(PRODUCT V1 BASE)". **LOGIC_CHANGED: NO** for product_v1 (zero strategy,
pillar, trigger, threshold, risk, or `locked_constants` edit — the only
config-adjacent change is location, not content).

## What moved (full detail: `ARCHIVE/MANIFEST_20261102.md`)

* **Logs: YES** — 5 stale/test-temp dirs under `logs/` (total 0.30 MB) →
  `ARCHIVE/logs/` (date-suffixed). `logs/phase_d` is **SKIPPED_LOCKED** — the
  live operator (PID 18484, `run_operator.py --config live_demo.json`,
  started 13:05) holds it open; it is the CURRENT session's output, not
  stale. Rotate it to `ARCHIVE/logs/phase_d_<date>.zip` after the session
  stops (not done here: no idle-phase assumption was made).
* **Dist: YES** — the whole 2026-10-08 stale tester pack (132 files, 1.1 MB)
  → `ARCHIVE/dist_stale/`. A tester pack must be rebuilt from product_v1
  before any future dist use; the repo-root bat never referenced it and no
  launch doc does.
* **Code: PARTIAL** — no code quarantine (strict rules: nothing on the
  product_v1 path or suite was movable without a shim; `smc.dumb.*` stays
  per the standing naming ruling). The only code-adjacent thing moved is the
  untracked one-off probe `tests/test_gn.py` →
  `ARCHIVE/research_scripts_stale/`.
* Research results tree **kept in place** (path-stability for tracked
  methodology notes; already local-only by policy — inventory documents the
  ~180 MB / 115-dir picture).

## How verified

1. Inventory first (`06_RESEARCH/ARCHIVE_INVENTORY_2026-11-02.md`), then
   moves, then full pytest: **1385 passed** — same green count as before the
   moves.
2. Product path sanity: bat line unchanged
   (`python "04_SRC\smc\live\run_operator.py" --config config\live_demo.json`),
   `OperatorConfig()` default and `load_operator_config(live_demo.json)` both
   `PRODUCT_V1`; no launch doc mentions `dist/`.
3. No silent deletion: every move is listed in the manifest; nothing was
   reverted (no import broke).

## Honesty notes

* This pass moved logs/docs/probes only — **no code was removed from the
  product**; tightened claim discipline per the directive.
* ARCHIVE/ is gitignored by established policy; moves are plain (not
  `git mv`) and no git history was rewritten.
* `logs/` still contains the live `phase_d/` session output — expected state
  while the operator is running.
