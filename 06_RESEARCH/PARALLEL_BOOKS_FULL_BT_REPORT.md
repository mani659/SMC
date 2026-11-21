# PARALLEL BOOKS — FULL-YEAR RESEARCH BACKTEST REPORT (2026-11-20)

**Status:** COMPLETE, **FAIL** on two structural gates. Diagnostic only. No promotion licence.
**Run:** `parallel_books_full_bt`, books `[F,B,C,E,A]`, hypotheses `LONG` + `SHORT`.
**Window:** exec 2024-11-01 → 2025-10-31 (load 2024-09-01), 12 adjacent calendar-month
segments × 2 hypotheses = 24 runs, all five books per run.
**Runtime:** 164,114.4 s ≈ 45.6 h (≈1.9 h/run). Generated 2026-11-20T11:07:11Z.
**PID:** 11652 (dead, as expected). `EXIT_CODE.txt = 1`. `verdict.json` present, 24/24 runs.
**Artifacts (gitignored):** `06_RESEARCH/results/parallel_books_full_bt/` — `verdict.json`,
`EXIT_CODE.txt`, `heartbeat.json`, `stdout.log`, `stderr.log` (empty), 24× `run_metrics.json`.
**Report author:** agent, from `verdict.json` + per-run `run_metrics.json` (read-only, no re-run).
**Suite:** 1,555 passed / 7 skipped (unchanged; no code touched this task).
**Defaults:** unchanged (`parallel_books = ()`). `locked_constants` untouched.

---

## 1. Gate verdict (structural — never PnL)

| Check | Value | Result |
|---|---|---|
| `all_runs_present` (24/24) | 24/24, `runs_missing: []` | PASS |
| `cross_tag_leak_no` | `CROSS_TAG_LEAK: NO` | PASS |
| `unattributed_zero` | 0 unattributed fills | PASS |
| `poi_outside_books_zero` | 0 | PASS |
| `all_books_exercised` | F/B/C/E/A all true | PASS |
| `no_cross_book_double_lot` | **1 unwanted double-lot** (E+F, same long level, 2025-03-06 14:05) | **FAIL** |
| `no_product_fill_lost` | **60 missing product fills** across the 24 runs (1–6 per run) | **FAIL** |

`verdict.pass = false`. Two gates failed. Both are *instrument/composition* findings, not
strategy findings. Per the branch table in `POST_PARALLEL_BOOKS_RESEARCH_PLAN_2026-11-19.md`
§3, this outcome licenses **S1 only** — the books layer is not promotable until both are
fixed and re-measured. No promotion, no default flip, no entry-strategy conclusion follows.

---

## 2. Fills and routes (exec window — authoritative)

`verdict.fills_union = 988` (unique fills across the year). Per-book:

| Book | Fills | Routes | Trigger mix | Detection TF mix |
|---|---:|---:|---|---|
| F | 353 | 1132 | F 353 | H4 53 / M15 223 / H1 64 / D1 13 |
| B | 241 | 840 | B 241 | M15 152 / H1 59 / H4 30 |
| C | 185 | 795 | C 185 | M15 132 / H1 44 / H4 9 |
| E | 156 | 646 | E 156 | M15 97 / H1 46 / H4 13 |
| A | 53 | 358 | A 53 | H1 21 / M15 18 / H4 14 |

- **Tag purity holds**: every fill's trigger equals its book letter (no cross-tag leak).
- **Routes union 3771** (per-book route sums are not additive across books by construction;
  the union is the cross-book deduped total).
- **Direction mix** (per book, long/short): F 186/167, B 127/114, C 106/79, E 84/72, A 31/22.
- **Routes by book** are the book's own admissible-set counts; they are not comparable
  across books (different admissible sets — DUMB audit §6 rule applies unchanged).

**Measurement trap to record:** per-segment `run_metrics.json` `fills` sums to **1448**, not
988. The verdict's 988 is the exec-window *union* and is authoritative. The per-segment
counter includes warm-up-period fills (load 2024-09-01) and/or cross-segment dedup. **Do not
sum per-segment `fills` for a year total.** This is the same class of instrument error that
produced the 441/149/11 seek fingerprint confusion earlier in the project.

---

## 3. Cross-book dedup and shared envelope

- `cross_book_duplicate_skips = 0` (no cross-book duplicate plan suppressed by the durable
  registry).
- `adapter_duplicate_story_cross_book = 0` (no adapter-backstop drop).
- `cross_opposite_direction = 22588` (opposite-direction cross-book conflicts counted, not
  resolved as fills).
- `winners_by_book_raw_sum_not_year` (raw winner sums, not union): F 1374 / E 777 / B 1004 /
  C 942 / A 419. These are raw, pre-dedupe and include warm-up; do not treat as year counts.
- **Shared risk skips (year):** `circuit_breaker 198`, `session 200`,
  `skip_place_far_from_zone 17`, `same_level 15`. Per-book attribution is **not present**
  (M-4 still open) — these cannot yet be assigned to a book. This is exactly the gap S1
  closes.

---

## 4. Failure 1 — unwanted cross-book double-lot (gate `no_cross_book_double_lot`)

**What happened:** on `2025-03-06 14:05:00+00:00`, books E and F both filled a long at the
same level (`2905.155` / `2905.519052` / `2911.310756`). `verdict.unwanted_double_lots`
records this single entry.

**Why it is a gate failure, not a statistic:** the durable `CrossBookPlanRegistry` (C-1) and
the adapter backstop `_duplicate_story` (C-1 second half) are supposed to make a second book
confirming the same plan drop, not fill. The smoke (feb25, 5 trading days) showed 0 double-lots
and the adapter probe showed `cross_book_duplicates=2` suppressed. The year run shows one
slipped through.

**Candidate mechanisms (to be investigated in S1, not asserted here):**
1. The registry keys on the trigger-excluded `CrossBookPlanKey`. E and F have different
   triggers (`E` vs `F`), so if the plan key is not truly trigger-excluded on this path, a
   cross-book collision would not be caught. The smoke could not exercise this because it
   produced no identical plan.
2. The adapter backstop `_duplicate_story` keys on a LIVE claim. If the first book's claim
   was released (plan stopped being live) before the second book confirmed, the backstop
   would not fire. Timing/ordering, not logic.
3. A plan that is *similar but not identical* at key construction time (level rounding,
   direction) would not match either guard.

**What this does not imply:** it does not imply the books are broken, that dedupe is useless,
or that a live default is safe. It implies one seam was not covered by the smoke and must be
reproduced before any ruling.

---

## 5. Failure 2 — product fills lost (`no_product_fill_lost`)

**What happened:** every one of the 24 runs lost 1–6 product fills. Total ≈ 60 missing
product fills across the year. The replay produced 988 union fills but did not reproduce all
of the product's own fills in each segment.

**Why it matters:** the product is the reference. If the books layer drops product fills, then
(a) the books layer is not a strict superset of the product, and (b) any comparison of
"books vs product" is confounded by missing fills, not by book quality.

**Candidate mechanisms (S1, not asserted):**
1. The one-story guard (`one_story_per_poi` / dedupe) may suppress a product fill when a book
   claims the same plan first — i.e. the books are *stealing* product fills via cross-book
   dedupe. This would be a real composition bug, not a measurement artifact.
2. Tier coverage: M-3 refuses uncovered tiers (`poi_outside_books = 0` here, so no legacy
   seek fall-through), but a product fill whose POI is covered by a book may still be
   displaced by that book's own routing.
3. Segment boundary: a product fill whose open time falls in the warm-up of segment N+1 may
   be counted in segment N's replay but dropped from N+1's exec window, or vice versa. This
   is the same tiling artifact that makes `fills` (1448) ≠ union (988).

**What this does not imply:** it does not imply the product is better or that books add
nothing. It implies the composition is not yet a clean superset and the measurement is not
yet trustworthy.

---

## 6. What this run licenses

- **S1 (attribution closeout)** — M-4 stamp, per-book risk counters, a reproduction of the
  double-lot and of the anchor loss, and a byte-identity proof that attribution does not
  alter decisions. This is the only stage the failure licenses.
- **Nothing else.** Specifically: no admission ruling (S2), no re-baseline (S3), no entry
  representation work (S4), no perf patch (S5), no OOS (S6), no paper (S7), no promotion (S8).

## 7. What it does not license (do not do these)

- Do not widen any gate to make the double-lot or the anchor loss disappear.
- Do not claim the books "work" or "don't work" from these numbers.
- Do not treat the diagnostic PnL (§8) as performance.
- Do not run the year again before S1 fixes are in and a reproduction is captured.
- Do not enable `D`. Do not touch `locked_constants`. Do not move thresholds.

---

## 8. Diagnostic PnL (residue only — NEVER a performance claim)

Per-book `pnl_net_sum_diagnostic` (sum of diagnostic net across fills, costs per the V1
ledger, no slippage model, no expectancy claim):

| Book | Fills | Diagnostic net sum |
|---|---:|---:|
| F | 353 | −56.47 |
| B | 241 | −23.23 |
| C | 185 | −8.14 |
| E | 156 | −0.37 |
| A | 53 | −4.96 |
| **Total** | **988** | **−93.18** |

These are accounting residues on a diagnostic run. They are not expectancy, not edge, and
not a basis for promotion or rejection. They are recorded only so a later, clean run can be
compared against them.

---

## 9. Runtime and instrument notes

- Wall time 164,114.4 s ≈ 45.6 h, ≈ 1.9 h/run. This is the measured cost of a 5-book
  segmented year; continuous replay remains infeasible (2.5 bars/s collapse, menu
  quadratic).
- All five books exercised every run. No book was starved at the fill level (A is the
  smallest at 53 fills, but it is the smallest admissible set by design).
- Detection TF coverage per book is recorded in §2; F is the only book with D1 (13), which
  is consistent with F's geometry (DAY + H4 + H1 + M15). B/C/E/A are mid-only and correctly
  show no D1.
- `stderr.log` empty. No crash, no exception in the run tail. The exit code 1 is the
  harness's own gate failure, not a crash.

---

## 10. Next ready

`S1 — attribution closeout (M-4)`, per `POST_PARALLEL_BOOKS_RESEARCH_PLAN_2026-11-19.md`
§2. Concretely:

1. Reproduce the double-lot in a bounded slice and identify which of the three candidate
   mechanisms (§4) fired.
2. Reproduce the anchor loss and determine whether it is dedupe displacement, tier
   coverage, or segment tiling (§5).
3. Stamp `book_id` on `blocked_by_reason` events; add the regression test; prove
   byte-identity on a proving slice.
4. Only then: S2 (admission ruling), on structural evidence, never on the PnL in §8.

**Architect review required before S1 starts. No code change has been made by this report.**

```text
FULL_BT_STATUS: FAIL
BOOKS: [F,B,C,E,A]
FILLS_BY_BOOK: {F:353, B:241, C:185, E:156, A:53}
ROUTES_BY_BOOK: {F:1132, B:840, C:795, E:646, A:358}
CROSS_TAG_LEAK: NO
CROSS_BOOK_DOUBLE_LOT: 1 (E+F, long, 2025-03-06 14:05)
POI_OUTSIDE_BOOKS: 0
SHARED_RISK_SKIPS: {circuit_breaker:198, session:200, skip_place_far_from_zone:17, same_level:15} (not attributed per book — M-4 open)
VS_R1_NOTE: The five-book year reproduces R1's structural finding at scale: every book's
  fills carry its own trigger letter (no cross-tag leak), all five books are exercised every
  run, and POI coverage is complete (0 outside-books). But the composition is not yet a clean
  superset of the product: 60 product fills were lost across the year and one cross-book
  double-lot slipped through the durable dedupe. Both are gate failures, not statistics, and
  both must be fixed and re-measured before any admission ruling. The fill counts
  (F 353 / B 241 / C 185 / E 156 / A 53, 988 union) are measurement, not quality.
PROD_DEFAULTS_CHANGED: NO
REPORT_PATH: 06_RESEARCH/PARALLEL_BOOKS_FULL_BT_REPORT.md
HANDOFF_UPDATED: YES (this commit)
NEXT_READY: Architect review of the multi-book year (S0 intake → S1 attribution)
```
