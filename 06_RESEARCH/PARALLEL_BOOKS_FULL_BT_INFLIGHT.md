# PARALLEL BOOKS — FULL RESEARCH BACKTEST (IN FLIGHT)

**Status:** `IN_FLIGHT` — launched detached 2026-11-18T13:28:47Z, harness
`06_RESEARCH/scripts/parallel_books_full_bt.py`, python PID **11652**
(launcher `cmd.exe` PID 17504, parented under WmiPrvSE so it survives IDE
reloads / terminal closure).

**What is running (Architect promote ruling, measurement only)**

| Item | Value |
|---|---|
| Books | `F, B, C, E, A` (`D` excluded — R-K) |
| Geometry | design/spike presets: `F` = DAY+H4+H1+M15; `B/C/E/A` = mid tiers (H4/H1/M15); each book `trigger_types=(T,)` only |
| Path | `ParallelBookMenu` / `resolve_book_selection` (same seam the spike and smoke measured) |
| Window | exec **2024-11-01 → 2025-10-31 UTC**, load warm-up **2024-09-01** (product_1y `run1` armed universe + truth, per segment) |
| Shape | **12 adjacent calendar-month segments** tiling the year — the continuous single-menu year replay is documented infeasible (`PRODUCT_1Y_ONE_STORY_DIAGNOSTIC_REPORT.md` §1.1: 26.1 → 2.5 bars/s by bar 6,000, killed at the 45-min budget) |
| Runs | 12 segments × 2 direction hypotheses = **24** (all five books in ONE pass per run, so per-book and union metrics come from the same replay) |
| Envelope | shared risk envelope (one `RiskEngine` per run), cross-book dedupe ON, one story PER BOOK |

**Artifacts (all gitignored)**

```
06_RESEARCH/results/parallel_books_full_bt/
  pid.txt            harness PID (11652)
  launcher.log       detach receipt (WMI PIDs, log paths)
  stdout.log         per-run lines: fills, per-book split, dedupe count, runtime
  stderr.log         expected empty unless fatal
  heartbeat.json     {phase, run, runs_done/runs_total, utc, alive} — refreshed every 20 s
  progress.json      start/finish record + books/segments/window
  <seg>/books_F-B-C-E-A_<HYP>/     summary.json, fills.csv, winners.json, run_metrics.json, .done
  verdict.json       written by the last run: union + per-book metrics, checks, pass
  EXIT_CODE.txt      written on process exit (0 = all checks passed)
  traceback.log      only if the process died
```

**How to resume (do not re-run a finished run)**

- The harness is **resumable**: each finished run has a `.done` file and is
  skipped on re-launch. Relaunch with the same command:

```
cd 06_RESEARCH/scripts
PYTHONPATH=../../04_SRC:. python parallel_books_full_bt.py --books F,B,C,E,A \
    --out 06_RESEARCH/results/parallel_books_full_bt
```

  or re-run the detached launcher, which refuses to start while PID 11652 is
  alive:

```
powershell -NoProfile -ExecutionPolicy Bypass -File 06_RESEARCH/scripts/parallel_books_full_bt_launch.ps1
```

- **Check without disturbing it:** `heartbeat.json` (`alive`, `runs_done`),
  `tail stdout.log`, `ls */books_*/.done`.
- **Complete when:** `verdict.json` exists and `EXIT_CODE.txt` reads `0`.
  Then write `06_RESEARCH/PARALLEL_BOOKS_FULL_BT_REPORT.md` and the governance
  entries and return the resume block — do not re-run.

**Checks the verdict gates on (fail loud)**

`CROSS_TAG_LEAK: NO` (each book's filled trigger mix is exactly its own
letter) · 0 unattributed fills · 0 cross-book double-lots (no executable plan
filled by two books at the same instant) · `poi_outside_books == 0` (book `F`
carries every tier, so no POI may leave the books) · all five books exercised
(≥ 1 fill over the year) · **no product_1y fill lost** (per-segment anchor vs
that segment's `trades.csv`).

**Honest limits (known before the result)**

- Segmented tiling, not one continuous replay: armed/episode counts restart per
  month and are reported per segment, never summed as a year total; fills are
  unique-timestamp events so fill sums do add (same merge rule as product_1y).
- Anchor loss is gated but the anchor compares *identity* only; it is not a
  performance claim.
- `pnl_net_sum_diagnostic` is an accounting residue labelled **NOT
  performance**; no expectancy/edge language belongs in the report.
- Risk-block reasons are the **shared envelope's** (`blocked_by_reason`), not
  attributable per book — that is audit finding **M-4**, still open.
- Cross-book dedupe fired 0 times on the feb25 smoke; whether identical plans
  arise on a year of data is exactly what this run measures (honest count, not
  a pass/fail on zero).
- Harness-side fix found while preflighting: the spike's trimmed anchor filter
  compares ISO strings and `" " < "T"`, so same-day later product fills leaked
  into a trimmed slice's anchor. This harness normalises the separator; the
  smoke's parity verdict is unaffected (both arms used the same filter).
- No MT5, no order placement, no installer/default change: the replay uses a
  counting order book. `PROD_DEFAULTS_CHANGED: NO` — the harness fails loud if
  `config/live_demo.json` ever carries books.
