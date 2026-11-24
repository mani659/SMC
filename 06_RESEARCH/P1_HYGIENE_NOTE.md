# P1 — MEASUREMENT HYGIENE + REPORTING GAP (2026-11-24)

**Status:** PASS. `LOGIC_CHANGED: NO` — measurement trust only.
**Scope:** root pytest hygiene, `entry_quality_f_b` summary reporting gap, hygiene-note
disposition, governance touch. No product code, no threshold, no strategy, no stop/TP design,
no O1–O5 reopen.

**Baseline:** `main` @ `457881f`; canonical suite **1,557 passed / 7 skipped**.
**P0 (Architect 2026-11-24):** `SUPERSET_OPEN_BOOK_SCOPE_ONLY` — book findings are book-scoped
and are not product claims.

---

## 1. Root `python -m pytest` hygiene

### Before (measured, repo root, `pytest 9.1.1`)

```
$ python -m pytest -q --collect-only
E   File ".../ARCHIVE/RECOVERY_FRAGMENTS_2026-11-08/corrupt_originals/04_SRC/tests/conftest.py", line 1
E       Read file 04_SRC/tests/conftest.py, lines 1-84
E   SyntaxError: invalid decimal literal
ERROR 04_SRC/tests - ModuleNotFoundError: No module named 'smc'
ERROR ARCHIVE/RECOVERY_FRAGMENTS_2026-11-08/corrupt_originals/04_SRC/tests - ...
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!
no tests collected, 2 errors in 1.15s
```

Two independent defects, neither a product failure:

1. **ARCHIVE was collected.** `ARCHIVE/RECOVERY_FRAGMENTS_2026-11-08/corrupt_originals/` holds
   deliberately corrupted originals (a `conftest.py` containing a transcript, not Python).
2. **`smc` was not importable.** The package lives in `04_SRC/smc`; a root run had no path to it
   (the canonical command worked only because it `cd`s and sets `PYTHONPATH=.`).

### Fix — new `pytest.ini` at the repo root

```ini
[pytest]
testpaths = 04_SRC/tests
pythonpath = 04_SRC
norecursedirs = ARCHIVE 02_KNOWLEDGE_BASE 07_DATA dist logs .* build CVS _darcs node_modules venv {arch} *.egg
```

- `testpaths` — a bare root run only looks at the product suite.
- `pythonpath` — `import smc` resolves without an exported `PYTHONPATH` (pytest ≥ 7 ini option).
- `norecursedirs` — overriding the option replaces pytest's defaults, so the defaults are kept and
  `ARCHIVE`, the data tree, `dist/` and `logs/` are added. This also protects an explicit
  `python -m pytest .` from re-collecting the fragments.

### After (measured)

| Check | Command | Result |
|---|---|---|
| Root run | `python -m pytest -q` | **1,557 passed / 7 skipped**, exit **0** |
| Root collect, ARCHIVE hits | `python -m pytest -q --collect-only \| grep -c ARCHIVE` | **0** |
| Root collect, item count | `python -m pytest -q --collect-only \| grep -c '::'` | **1561** (= 1,557 + 4 id lines from parametrised/`-q` listing; 0 ARCHIVE) |
| Canonical run (unchanged) | `cd 04_SRC && PYTHONPATH=. python -m pytest -q` | **1,557 passed / 7 skipped**, exit **0** |

The canonical command is unchanged and still correct; the root command is now the documented
"one true command" for a repo-root run. Neither collects `ARCHIVE`.

---

## 2. `entry_quality_f_b` summary reporting gap

### What was missing

`universe_features.csv` and the charts carried `window_end_source` (`bar` / `open`), but the
**summary the study is read from did not**: a reader of `summary.json` could not see that 22 of
592 fills had a window with no bar-counted upper bound. The recon measured F 20 / B 2 of 592 and
it was never surfaced where the study is consumed.

### What was added (summary only)

1. **`window_end_source` block** in `06_RESEARCH/results/entry_quality_f_b/summary.json`:

```json
"window_end_source": {
  "rule": "bar = bounded by the close of the detection bar at sweep_index+MENU_EXPIRY_BARS;
           open = that bar is at/past the end of the loaded segment series, so the engine window
           has no upper bound (never a wall-clock projection)",
  "by_book": {"F": {"bar": 331, "open": 20}, "B": {"bar": 239, "open": 2}},
  "total": {"bar": 570, "open": 22},
  "expiry_bars": 20,
  "checked_rows": 592,
  "violations": 0
}
```

2. **Fail-loud coverage invariant** (`window_coverage()` in
   `06_RESEARCH/scripts/entry_quality_f_b.py`, run before any CSV/summary is written):

   > For every row, with `I = sweep_index` of the sweep bar in the segment's detection series and
   > `N = len(series)`: a `window_end_source == "open"` row is valid **iff**
   > `I + MENU_EXPIRY_BARS >= N`; a `"bar"` row is valid **iff** `I + MENU_EXPIRY_BARS < N` and its
   > `window_end_bar_ts` equals the shared rule's end. Any mismatch raises `SystemExit` naming up
   > to 5 offending rows — the export never scores a row whose window bound the engine does not
   > share.

   Note on direction: the naive phrasing "open ⇒ `sweep_index + expiry < len`" is inverted —
   `open` means the expiry bar is *absent from the loaded series* (`>= len`). The invariant above
   is the equivalent documented rule, and it is checked in both directions (open ⇔ past the end,
   bar ⇔ strictly inside), so a short/truncated series cannot pass silently.

   It compares **bar counts and the loaded series only**; it never asserts against the stamp's
   wall-clock `window_end_ts` (the artefact class removed in `457881f`).

### Verification

- Run: `PYTHONPATH=04_SRC python 06_RESEARCH/scripts/entry_quality_f_b.py` → exit **0**,
  `universe {'F': 351, 'B': 241} total 592`, `sample {'F': 20, 'B': 20} charts 40`,
  `window end {'bar': 570, 'open': 22} coverage 592 rows / 0 violations`.
- **Draft scores byte-identical** (no score column rewrite):
  - `universe_features.csv` md5 `f547f405969f692bf9c73dc1e0d1ebe8` — unchanged.
  - `sample_index.csv` md5 `eb8ce68e074a1f5f9e23d2df9b40cb63` — unchanged; architect columns still blank.
  - `summary.json` md5 `1e34083c…` → `0e34324b…`, the only difference being the added block.
- Draft mix re-read: F 164 STRONG / 113 PARTIAL / 74 WEAK; B 115 / 104 / 22. Identical to the
  post-G2-rebase export.
- Open counts match the recon: **F 20 / B 2** of 592.

---

## 3. `REPO_HYGIENE_CANDIDATES_2026-11-16.md`

**Committed** (was untracked since 2026-11-16) under `06_RESEARCH/` as the record of the
2026-11-16 hygiene survey. It remains **analysis only** — the note itself states no file was
deleted, moved or committed, and nothing from its lists was actioned in P1. Its cost estimates
and lists stay valid as a backlog reference; the two `.py` programs inside the gitignored `logs/`
directory (`gov_ops.py`, `patch_release.py`) are still flagged there as migration candidates.

---

## 4. Governance touch (docs only)

- `00_LOCKED/POST_V1_ACTIVE_TODO.md` — P0 ruling recorded (`SUPERSET_OPEN_BOOK_SCOPE_ONLY`,
  Architect 2026-11-24); P1 recorded as done with evidence; **NEXT = P2 O-block year re-read**
  (explicitly not P3, not paper).
- `00_LOCKED/SESSION_HANDOFF.md` — P1 section at the top.
- `00_LOCKED/CHANGELOG.md` — P1 entry.

`04_SRC/smc/**`, `locked_constants.py`, `04_SRC/smc/config`, thresholds, `parallel_books`
defaults and every O1–O5 lock are untouched: `git diff -- 04_SRC` is empty.

---

## 5. Return block

```
P1_STATUS: PASS
ROOT_PYTEST: PASS (exit 0; 0 ARCHIVE paths collected; was 2 collection errors / 0 tests)
CANONICAL_SUITE: 1557 passed / 7 skipped / exit 0
SUMMARY_GAP: CLOSED (window_end_source bar 570 / open 22 = F 331/20 + B 239/2; coverage 592/592, 0 violations; CSVs md5 unchanged)
HYGIENE_NOTE: committed
LOCKED_CONSTANTS_DIFF: empty
LOGIC_CHANGED: NO
NEXT_READY: P2 O-block year re-read
```

Bans honoured: no `04_SRC` strategy/trigger/risk/pillar/threshold edit; no `parallel_books` or
live default change; no O1–O5 reopen; no stop-reference or F-filter implementation; no
expectancy/PF language; `results/` stayed gitignored (only `summary.json` inside it was
regenerated locally).
