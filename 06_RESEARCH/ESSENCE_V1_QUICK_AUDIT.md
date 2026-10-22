# ESSENCE V1 — QUICK AUDIT (pre-expert-pack integrity check)

**Banner: DIAGNOSTIC / EXPERT REVIEW PACK — NOT PERFORMANCE**

**Date:** 2026-10-22 · **Scope:** read-only integrity audit of the essence slice +
export pack for the expert. No redesign, no threshold/strategy changes, no edge claims.
**Inputs audited on disk:** `00_LOCKED/ESSENCE_CONTRACT_V1.md` (§8 rubric),
`06_RESEARCH/ESSENCE_V1_SLICE_NOTE.md`,
`06_RESEARCH/results/essence_v1_slice/W3/{run1,run2}/trades.csv`,
`summary.json`, `determinism.json`, `run_meta.json`, the live git worktree.

```
AUDIT_STATUS: PASS_WITH_WARNINGS
A1_DET: PASS
A2_IDENTITY: WARN (all required fields present; export gaps closed inside the scorecard, see A2-1/A2-2)
A3_CONTRACT: PASS (band verified independently 7/7; one disclosed footnote, see A3-1)
A4_FUNNEL: PASS (numbers add up exactly, no silent drops)
A5_SUITE: 1279 passed (EXIT=0) — RE-RUN today (2026-10-22), took 7.5 s
A6_ISOLATION: PASS (one worktree-state footnote, see A6-1)
CHARTS: YES (7 M1-context charts under results/essence_v1_slice/expert_charts/)
LOGIC_CHANGED: NO
```

---

## A1 — Determinism: PASS

`W3/run1/trades.csv` and `W3/run2/trades.csv` re-hashed **fresh today**:
md5 `27f326a823e6c89b5623c391dbfee50c`, sha256 `6baa87dcd64d652f…` (identical on
both files) and exactly matching the recorded `determinism.json`
(`byte_identical: true`). Note: this is the **post-`confirm_ts`-fix** pair; the
earlier pre-fix hash (`f195768…`) is superseded. PASS.

## A2 — Trades & identity fields: WARN (export gap only)

7 trades on file. Per-trade field presence (all 7 rows checked):

| Field group | CSV columns present | Present? |
|---|---|---|
| zone bounds | `zone_low`, `zone_high`, `detection_tf`, `zone_kind`, `zone_poi_id` | YES |
| side | `direction` | YES |
| sweep flag/link | `sweep_ts`, `sweep_extreme` | YES |
| confirm type (set C) | `confirm_kind` (`c_ending_diagonal` on all 7), `confirm_ts`, `terminal_idx` | YES |
| entry | `entry_level`, `entry_ts` (M1-granular timestamps; runner is native M1) | YES |
| money | `sl_price`, `sl_pips_buffer`, `tp_price`, `target_ref`, `rr_planned`, `r_stop`, `be_applied` | YES |
| exit | `exit_ts`, `exit_price`, `close_kind`, `bars_held`, `pnl` | YES |

**A2-1 (the WARN):** there is **no per-row `entry_tf` column** — entry-timeframe
M1 is architectural (the essence runner iterates native M1 bars), not exported.
The expert scorecard adds an `entry_tf=M1` column so the §8 rubric is answerable
purely from the pack. **Export-only enrichment; no runner/logic change.**

**A2-2 (disclosed, affects label reading — no fix made to trades.csv):**
`sl_price` holds the **exit-time stop, i.e. the post-BE level when BE was
applied**. Proof in-file: on trades 4/5/7 (`be_applied=True`) `sl_price` sits
ON/above the entry side, while the initial stop is exactly reconstructable as
`entry ∓ r_stop` — verified exact against the structure anchor below (A3-1).
The scorecard therefore exports **both** `sl_initial` (= `entry ∓ r_stop`) and
`sl_at_exit` (= `sl_price`), labelled, so the expert scores the ACTUAL initial
stop placement and sees the BE move separately. Export-only.

## A3 — Contract alignment spot-check (all 7 sampled): PASS

- **Confirm set C only:** `confirm_kind = c_ending_diagonal` on all 7. Not a
  Trigger-F label, not DUMB mid-reclaim, nothing outside the wired allow-list.
- **Entry timeframe M1:** native-M1 runner (W1 of the slice), entry timestamps
  M1-granular; exported per-row in the scorecard as `entry_tf=M1`.
- **SL 2–5 pip band:** `sl_pips_buffer = 2.0` on all 7 → 0.20 price units at the
  frozen XAUUSD pip assumption (`1 pip = 0.10`), i.e. the **band floor**, inside
  the 2–5 band. **Independently verified against the M1 parquet** (read-only,
  reproducible via `06_RESEARCH/scripts/essence_v1_expert_charts.py` whose
  audit pass prints `delta = 0.2 [OK]` for all 7): the initial stop sits
  **exactly 0.20 price units beyond the deeper of {sweep extreme, ED terminal
  wick}** — the effective M1 structure extreme of the setup. Side-wise anchors:
  t1 3351.518, t2 3336.985, t4 3365.575, t5 3360.035, t7 3335.765 (LONG = the
  lower extreme), t3 3370.498, t6 3354.155 (SHORT = the higher extreme); 7/7
  delta = 0.20 exactly, no exceptions.

  **A3-1 (footnote, disclosed):** the signed pick **B** is "2–5 pips beyond the
  M1 structure" — the band applies to the *buffer beyond the structure level*
  (the ending-diagonal terminal wick, taking the deeper side of the anchor set
  above), not to the total stop distance. Total
  `r_stop` on file spans 0.73–2.29 price units (7.3–22.9 points) because the
  structure itself can sit well away from the entry. Operations reading the CSV
  should judge the **buffer** (2.0 pips everywhere), not the total distance.
  Note `XAUUSD_PIP_SIZE = 0.10` is a documented **assumption** in
  `smc/utils/pips.py` (marked NOT FROZEN, broker-verify before live); it is used
  consistently in the slice and does not change this audit's verdicts.
- **TP ≥ 1:5 (hard gate):** `rr_planned` per trade = 6.48 / 9.77 / 5.08 / 8.67 /
  9.13 / 27.14 / 6.13 — all ≥ 5.0. The four confirmations that could not reach
  1:5 were **blocked pre-entry** and never exported (they are in the funnel,
  A4); no trade was downgraded below 1:5.

## A4 — Funnel arithmetic: PASS (exact, no silent drops)

From `summary.json` (run1):

```
swept 61,422
  → breakout-invalidated 50,861 (pending killed)
  → confirmed-expired 10,508 (pending setup window elapsed)
  → ED CONFIRMED 51
      entry skipped outside zone      2   ┐
      blocked: missing target         6   │ 2+6+34+9 = 51 ✓
      blocked: RR below 1:5          34   │
      LIMIT placed                    9   ┘
           limit expired (30 bars)    1   ┐
           breakout-cancelled         1   │ 1+1+7 = 9 ✓
           FILLED                     7   ┘
                BE moves 3 · exits: 7 stop_loss → trades 7 ✓
```

Every funnel branch terminates in an accounted bucket; nothing silently drops.

## A5 — Suite: 1279 passed (EXIT=0) — RE-RUN 2026-10-22

`cd 04_SRC && python -m pytest tests -q` → `1279 passed in 7.49s`, exit 0
(1255 baseline + 24 essence). The one-off `test_perm_hardening` failure in the
prior session ran 3/3 green in isolation and is now green in the full run —
environmental, unrelated to essence.

## A6 — COMPLEX isolation: PASS (worktree-state footnote)

The essence engagement's own write-set is `04_SRC/smc/essence/**`,
`04_SRC/tests/test_essence_v1_slice.py`, the capture script, and the four
governance docs. No COMPLEX spine file was touched by it
(`COMPLEX_BASELINE_INTACT: YES`).

**A6-1 (footnote):** the git worktree also contains **pre-existing uncommitted
changes from earlier engagements** (live/operator pack: `mt5_connector.py`,
`live/*`, `test_live_*`, watchdog, `config/live_demo.json`, plus other untracked
research artifacts). Those predate this essence session (present in the
session-start change snapshot) and are NOT essence edits; they are simply part
of the same uncommitted working tree. Flagged so a future commit-scope review
does not attribute them to essence.

---

## Verdict

All four structural checks (A1–A4) verify clean; the two WARNs are
export-shape matters closed inside the scorecard itself (`entry_tf=M1` column
added; `sl_initial` + `sl_at_exit` both exported), the SL band was re-verified
against the raw M1 series 7/7, and the per-trade exhibit charts are generated
and label-clean. **No blocker for the expert pack; LOGIC_CHANGED: NO.**
