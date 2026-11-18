# PARALLEL BOOKS — INTEGRATED DRY-RUN SMOKE

**Status: SMOKE PASS on a 5-trading-day frozen slice. `LOGIC_CHANGED: NO`,
`PROD_DEFAULTS_CHANGED: NO`.** No full-year backtest, no threshold/SL/TP or edge
work, no live/paper session, no MT5 interaction, no installer/default change.
`locked_constants` values untouched.

Parent documents: `06_RESEARCH/PARALLEL_BOOKS_DESIGN_IMPL_AUDIT.md` (findings),
`06_RESEARCH/PARALLEL_BOOKS_AUDIT_FIXES_NOTE.md` (C-1/M-1/M-2/M-3/M-5 fixes),
`06_RESEARCH/PARALLEL_BOOK_SPIKE_NOTE.md` (feb25 measurement).

Harness: `06_RESEARCH/scripts/parallel_books_smoke.py` (new, research-only;
reuses the spike's real menu → adapter → runner replay seam). Artifacts:
gitignored `06_RESEARCH/results/parallel_books_smoke/` (`verdict.json`, parity
JSONs, per-run `summary.json` / `fills.csv` / `winners.json`, `run.log`).

---

## 1. Window (honest limits)

| Item | Value |
|---|---|
| Segment | `feb25` (product_1y exec 2025-02-01 → 2025-02-28 UTC) |
| Slice | **first 5 trading days, END-trimmed** — `anchor_until` `2025-02-10T03:55:00+00:00` |
| M5 bars replayed | 1,440 |
| Armed POIs in slice | 59 |
| Hypotheses | LONG **and** SHORT (direction is not exported; filled POIs use the product truth direction, the rest the hypothesis — same rule as the spike) |

This is a **short frozen slice, not a month and not a year**. It proves the
wiring, the guards and the funnels; it says nothing about flow across feb25,
nothing about the full year, and nothing about edge/expectancy. The earlier
spike's full-month feb25 numbers (union fills B 25 / F 29) remain the flow
reference and are **not re-measured here**.

## 2. PROD parity (shipped menu vs `parallel_books=["PROD"]`)

Same process, same bars, same armed universe; winner identity, fill identity
and the product-fill anchor compared exactly (`spike-note` method, trimmed
window so only fills inside the slice are anchors).

| Hypothesis | Winners plain / PROD | Fills plain / PROD | Winners identical | Fills identical | Anchor identical |
|---|---|---|---|---|---|
| LONG | 8 / 8 | 6 / 6 | YES | YES | YES |
| SHORT | 8 / 8 | 6 / 6 | YES | YES | YES |

**PROD_PARITY_SMOKE: PASS.** The dead-by-default book list path is
behaviourally identical to the shipped single menu on this slice — no
regression from the C-1/M-2 re-keying.

## 3. F+B multi-book, dry-run

`parallel_books=["F","B"]`, `dry_run=true` (the config default — the R-L flag
was **not** set and was **not required**).

| Check | LONG | SHORT |
|---|---|---|
| Winners by book | B 9 / F 8 | B 13 / F 8 |
| Fills by book | B 5 / F 5 | B 5 / F 5 |
| CROSS_TAG_LEAK | NO (B→{B}, F→{F}) | NO (B→{B}, F→{F}) |
| Unattributed fills | 0 | 0 |
| Books exercised | YES (both) | YES (both) |
| Cross-book duplicate lots **suppressed** | 0 | 0 |
| Adapter `duplicate_story_cross_book` | 0 | 0 |
| **Unwanted double-lots** (same direction/entry/SL/TP filled by 2 books) | **0** | **0** |
| `poi_outside_books` (legacy seek outside tiers) | **0** | **0** |
| Shared-envelope skips (`blocked_by_reason`) | circuit_breaker 2, session 1 | circuit_breaker 2, session 2 |
| Opposite-direction coexistence (counted, R-B) | 9 | 4 |
| Runtime | 34.1 s | 31.6 s |

Notes on the readings:

- **CROSS_TAG_LEAK: NO** — single-tag purity was also enforced in-process by
  `ParallelBookMenu.assert_tag_purity()` (fail-loud); it did not fire, and the
  per-book fill trigger mix is exactly the book's own letter.
- **Double-lot:** no plan was admitted twice (the slice happens to produce no
  identical cross-book plan, as on the full feb25 month), so the C-1 registry
  and the adapter backstop had nothing to suppress — `cross_book_duplicates = 0`
  is an honest zero, not an unexercised pass. The gate itself is unit- and
  probe-proven (see the fixes note, probes 2 and 3). There are also **zero
  unwanted** doubles: no executable plan was filled by two books.
- **`poi_outside_books = 0`** — F carries all four shipped tiers, so B+F covers
  every detection tier in the slice: no POI was routed outside the books and
  none reached the archived legacy seek path. (The mid-only case, where the M-3
  guard must fire, is unit-proven in `test_m3_mid_only_books_never_seek_a_D1_poi`.)
- **Shared risk** — one `RiskEngine`/runner/order store for both books, no
  crash; the envelope skipped 3 (LONG) and 4 (SHORT) candidates by reason, and
  those skips are accounted for in `blocked_by_reason`.
- `dry_run=true` needs no posture flag, as required (see §4).

## 4. R-L guardrail (loud refusal, no run)

| Seam | Input | Result |
|---|---|---|
| `load_operator_config` | `{"parallel_books": ["F","B"], "dry_run": false}` | `ConfigError`: "config.parallel_books with dry_run=false is refused (R-L) …" |
| `OperatorSession._build_stack` (config built in code, fake connector) | `OperatorConfig(parallel_books=("F","B"), dry_run=False)` | `SystemExit`: "ABORT: parallel_books with dry_run=false is refused (R-L) …" |
| `load_operator_config` | `{"parallel_books": ["F","B"], "dry_run": true}` | loads; `allow_parallel_books_live = False` — **no flag required** |
| shipped `config/live_demo.json` | — | no `parallel_books` key → `()` → shipped single menu |

**GUARDRAIL_REFUSE: PASS** at both the file and code seams; the guard fires
before any connection or order path (the probe used a connector that raises on
any call — it was never called).

## 5. Verification

```text
cd 06_RESEARCH/scripts && PYTHONPATH=../../04_SRC:. python parallel_books_smoke.py --days 5
verdict.pass = true  (parity true / fb true / guardrail true)  runtime 446.7 s

cd 04_SRC && PYTHONPATH=. python -m pytest -q
1555 passed, 7 skipped in 8.06s      (unchanged; no test edited)

git diff -- 00_LOCKED/locked_constants.py 04_SRC/smc/config
(empty)
```

## 6. What this does NOT establish

- No year (or month) backtest: the slice is 5 trading days / 1,440 M5 bars.
- No live/paper session, no MT5, no installer or default enablement:
  `parallel_books` stays `()` in the shipped config; multi-book live still
  needs `allow_parallel_books_live=true` plus the promote ruling.
- Zero data firings of the C-1 dedupe on this slice (none arose) — the guard
  remains probe/unit-proven, not data-proven.
- M-4 (per-book risk attribution) and the audit minors remain OPEN.
- No expectancy, PnL or edge claim of any kind; the runs are diagnostic.

## 7. Next

1. Architect: promote ruling for `['F','B']` (dry-run demo flag vs stay off).
2. Then the research BT on the full year with `[F,B,C,E,A]` (runtime budget
   R-G, cross-book counters, `poi_outside_books` on mid-only coverage).
3. M-4 + minors before any installer/default discussion.
