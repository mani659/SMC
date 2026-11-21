# PARALLEL BOOKS — S2 ADMISSION RULING (Architect, 2026-11-20)

**Status:** RECORDED — binding for the research programme. Docs-only; no strategy code.
**Predecessors:** `PARALLEL_BOOKS_S1_CLOSEOUT_NOTE.md` (M-4 PASS, double-lot root-caused),
`PARALLEL_BOOKS_S1B_DOUBLE_LOT_NOTE.md` (R1 implemented, double-lot FIXED, suite
1,557/7/0 xfail), `PARALLEL_BOOKS_FULL_BT_REPORT.md` (full-year research BT: FAIL, 2 gates).

---

## 1. Ruling

| Item | Decision |
|---|---|
| **Research multi-book admission** | **ADMIT: F, B, C, E, A.** **D is out** (R-K unchanged; never enable book D). |
| **Live / installer default** | `parallel_books = ()` **unchanged**. No production default flip; single-menu path stays the shipped default. |
| **S3 re-baseline** | **Authorized for the research harness only.** Not a production/live authorization. |
| **Residuals** | Product-fill gap ≈60 remains **partial** (bucketed, not fully reconciled). **No expectancy claims.** |

### Scope of "ADMIT"
Admission is **research-scope**: the five books may be run together in the research
harness (`parallel_books=["F","B","C","E","A"]` with `dry_run=true`, per R-L) for
re-baselining. It does **not** authorize:
- a non-dry-run / live multi-book stack (still gated by `allow_parallel_books_live`, R-L);
- a change to `config/live_demo.json` (stays without a `parallel_books` key → `()`);
- any promotion beyond the research harness.

### Book D
Still refused at every seam (`resolve_book_selection` / `BookConfig` / config load per
R-K). This ruling does not reopen D.

---

## 2. What S3 is authorized to do

- Re-baseline the **research harness** on the admitted set F,B,C,E,A (fresh anchor run).
- Measure, on the re-baseline: fills/routes union, cross-book duplicate skips (now
  expected **>0** under R1 where the E+F class occurs), `poi_outside_books`,
  shared-risk skips, opposite-direction coexistence, and the product-fill delta.
- Keep the R1 identity (`direction + entry limit only`) and all existing gates intact.

### S3 is NOT authorized to
- Change thresholds, gates, `locked_constants`, or the production default.
- Make expectancy/edge claims from the re-baseline.
- Promote to live or enable D.

---

## 3. Residuals carried into S3

1. **Product-fill gap (~60):** partial. Tier = 0 and cross-book dedupe = 0 are proven;
   the remainder is split between one-story-guard displacement and segment tiling and is
   **not yet per-fill reconciled**. S3's re-baseline must keep reporting the delta, and a
   precise per-fill reconciliation remains outstanding (carry as an S3 sub-item, not a
   blocker to starting).
2. **Double-lot:** FIXED under R1 (S1b). The regression suite and registry/adapter tests
   pin it. S3 should verify **zero new double-lots** on the re-baseline and surface
   `cross_book_duplicate_skips` as the positive signal that dedup now fires.
3. **No expectancy:** nothing in S1/S1b/S2 supports an expectancy or edge statement.
   Re-baseline output is descriptive only.

---

## 4. Governance state at ruling time

- Double-lot: FIXED (R1). Suite 1,557 passed / 7 skipped / 0 xfailed.
- `locked_constants` diff: empty.
- `parallel_books` default: `()` (key absent in `config/live_demo.json`).
- No S2 admission promotion to live; S3 is research-harness re-baseline only.

```text
S2_STATUS: RECORDED
ADMIT: F, B, C, E, A (D OUT)
LIVE_DEFAULT: parallel_books = () unchanged
S3_AUTH: research harness only
RESIDUALS: product-fill gap ~60 partial; no expectancy
NEXT_READY: S3 research re-baseline OR Architect-named next
```
