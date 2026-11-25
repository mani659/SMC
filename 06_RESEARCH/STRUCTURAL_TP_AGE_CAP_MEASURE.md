# STRUCTURAL TP AGE-CAP — PHASE B MEASUREMENT (OPTION C PATH)

**Date:** 2026-11-25
**Authority:** Lead Architect ruling — **OPTION C (separate constant), MEASURE ONLY**
**Contract:** `00_LOCKED/STRUCTURAL_TP_AGE_CAP_DESIGN.md` §4 (pre-registered; nothing in it changed after numbers were seen)
**Mode:** `LOGIC_CHANGED: NO` — probes only; no production wiring, no `locked_constants.py` write, no default change, no book other than F

**Artifacts**
- Harness: `06_RESEARCH/scripts/structural_tp_age_cap_measure.py`
- Results (gitignored): `06_RESEARCH/results/structural_tp_age_cap/per_fill.csv`, `summary.json`, `shards/<segment>.json` (one per segment — the run is resumable), `run.log`

---

## 0. Verdict in one paragraph

Under the pre-registered contract, **none of the probes passes cleanly enough to auto-adopt**, and the two looser candidates fail for *different* reasons. `age100` recovers **92 of 133** honest fallback fills (+69 %) but re-selects the target on **48 % of the 218 fills that already had a structural TP** — a selection change, not a pure recovery. `none` reaches **351/351** structural, but its newly-selected targets are **degenerate**: median `|TP − entry| = 0.274 ATR`, sitting on the `0.25 × ATR` noise floor, with **57 of 133** swings older than 7 days — a pre-registered `K2_STALE_CAUTION`. `b1` recovers **48 %** and is **structurally incapable** of recovering M5/M15/H1 (its caps there are ≤ 20), so it is a tightening on the higher TFs, not a widening. **Recommendation: no auto-lock; if C is locked, it must be a TF-aware window with an explicit acceptance of the selection change** (see §8).

---

## 1. Population and method

| Set | N | Source |
|---|---:|---|
| Book F year fills | **351** | `06_RESEARCH/results/entry_quality_f_b/universe_features.csv` |
| Baseline structural (probe 20) | **218** | this run |
| Baseline `atr_fallback` | **133** | this run (P4 inventory: 129 — see §2) |

**Reconstruction.** Per fill, on the segment's confirmation series only:

1. `segment_series(segment)` — the frozen harness loader/resampler (`r1_pure_tag_books.segment_series` via `lib/menu_window`), processed **one segment at a time** with its cache dropped afterwards (a single-process run over all 12 segments exceeded the machine's patience/memory and was made resumable per segment).
2. Completion bar located by its **close** stamp — the export carries `_close_ts`, not the bar open.
3. `atr = latest_atr(series[: idx + 1], 14)` — the same honest-prefix ATR the menu path uses.
4. **`swings = detect_swings(series[: idx + 1], tf)` — PLACE-TIME PREFIX ONLY.**
5. `structural_tp_target(..., placement_bar=idx, max_age_bars=cap)` — the production selector, imported; never re-implemented. A local mirror of its ranking is used only to read the winning swing's age and its level is asserted identical per row.

### 1.1 A method finding that had to be settled first

Full-series swing detection is **not** equivalent to prefix detection, and the first version of this harness failed loudly on it (`F_feb25_L_2025-02-25_poi-015315`, age20: **2953.348** full-series vs **2944.648** prefix). The cause is structural: a swing whose extreme sits 1–2 bars before the placement bar can be confirmed *before* it, yet is invisible at place time because its right-hand confirmation window (`N_BAR_LTF = 3`) is not complete. The engine has the same blind spot, so **prefix detection is the faithful method** and is what this measurement uses. Any re-use of this harness must keep the prefix bound.

### 1.2 Probe definitions (fixed before the run)

| Probe | Cap passed to `max_age_bars` | Purpose |
|---|---|---|
| `age20` | 20 (as coded) | baseline |
| `age100` | 100 | Architect probe |
| `none` | `None` | Architect probe |
| `b1` | `ceil(20 × 5 / tf_minutes)` → M1 100 / M5 20 / M15 7 / H1 2 / H4 1 / D1 1 | sensitivity column only |

---

## 2. Baseline reproduction — 218/133 vs P4's 222/129

The baseline does **not** reproduce P4 exactly, and the direction is informative:

- All **129** P4 fallback ids are inside this run's 133 — `my_fallback ⊃ P4_fallback`.
- The 4 extra rows are `F_dec24_L_2024-12-17_poi-009439`, `F_feb25_L_2025-02-12_poi-007665`, `F_apr25_L_2025-04-24_poi-025137`, `F_may25_L_2025-05-13_poi-012748` — all `M1`, all with an honest place-time prefix that yields **no** target at a 20-bar cap.
- P4 found a structural target on those 4 rows. That is the same permissiveness demonstrated in §1.1: full-series detection manufactures a target where the prefix has none.

So the honest statement is: **P4's 129 is a subset of the truth; the prefix-bounded census is 133.** P4's harness script is not on disk (the note and artifacts are), so its exact index convention cannot be re-run; `comp_idx` values in the P4 inventory are **window-relative** while this harness indexes the loaded series, which is why only 26/129 `comp_idx` values coincide. That is a coordinate difference, not a disagreement — the classification is what was compared, and it differs on 4 rows only.

Reporting rule used below: **denominator = this run's 133** (the honest one), with P4's 129 shown alongside as `on_p4_129` for continuity with the Architect's prior numbers.

---

## 3. Structural share and recovery

| Probe | structural / 351 | share | recovery of 133 | on P4's 129 |
|---|---:|---:|---:|---:|
| `age20` (baseline) | 218 | 62.11 % | 0 | 0 |
| `age100` | 310 | 88.32 % | **92 (69.17 %)** | 88 (68.22 %) |
| `none` | 351 | 100.00 % | **133 (100.0 %)** | 129 (100.0 %) |
| `b1` | 273 | 77.78 % | **64 (48.12 %)** | 60 (46.51 %) |

**Recovery by confirmation TF** (of that TF's fallback count):

| Probe | M1 (99) | M5 (23) | M15 (3) | H1 (8) |
|---|---:|---:|---:|---:|
| `age100` | 64.6 % | 78.3 % | 100 % | 87.5 % |
| `none` | 100 % | 100 % | 100 % | 100 % |
| `b1` | **64.6 %** | **0 %** | **0 %** | **0 %** |

`b1` is exactly as predicted in the design note §3: with M5 at 20, M15 at 7 and H1 at 2 it cannot recover anything above M1 — and it *tightens* M15/H1 relative to today. It is a sensitivity column, not a viable reading of C.

---

## 4. Recovery *quality* — the finding that decides this

Share of fills with a structural target is a coverage metric, not a target-quality metric. The distance of the selected target from entry (`|TP − entry| / ATR`) separates the candidates sharply:

| Probe | all structural: p10 | p50 | recovered-only: p25 / p50 / p75 | recovered min |
|---|---:|---:|---:|---:|
| `age20` | 0.368 | 0.944 | — | 0.256 |
| `age100` | 0.313 | 0.583 | 0.418 / **0.585** / 1.07 | 0.254 |
| `none` | 0.253 | **0.268** | 0.257 / **0.274** / 0.359 | 0.250 |
| `b1` | 0.314 | 0.606 | 0.387 / 0.533 / 0.998 | 0.255 |

With no cap, the selector's "nearest in price" ranking is free to pick the oldest level that happens to sit a hair above entry: the recovered median is **0.274 ATR**, and the 25th–75th range (0.257–0.359) is compressed against the `0.25 × ATR` noise guard. Those are not structural objectives in any tradeable sense; they are "nearest level above the entry" artifacts, and they would dominate the book because they are nearest in price.

`age100` does not show this pathology (recovered p50 **0.585 ATR**, p75 1.07) — its recovered targets are genuine structure. This is the single most useful distinction in the whole measurement: **the same +69 % recovery looks like a fix under 100 bars and like a degenerate artifact with no cap.**

---

## 5. Churn — recovery is not free

Of the **218** fills that already had a structural target at the 20-bar cap, how many now get a **different level** (the design note's §1.5 mechanism: nearest-in-price outranks recency):

| Probe | changed | share of 218 |
|---|---:|---:|
| `age100` | **105** | **48.17 %** |
| `none` | **205** | **94.04 %** |
| `b1` | 84 | 38.53 % |

Under `age100` the book is not "92 more structural targets"; it is **92 gained and 105 re-priced** — 197 of 351 fills (56 %) see a different plan. Under `none` essentially the whole structural book is re-priced.

---

## 6. Staleness of newly-selected swings

| Probe | newly selected | > 24 h | > 7 days | median age (wall) | max age |
|---|---:|---:|---:|---:|---:|
| `age100` | 92 | 7 (7.6 %) | **0** | 73.5 min | 5,280 min (3.7 d) |
| `none` | 133 | **104 (78.2 %)** | **57** | 7,078 min (4.9 d) | 88,283 min (61 d) |
| `b1` | 64 | 0 | 0 | 52.5 min | 100 min |

Selected-age distribution over all structural rows (bars, then wall time):

| Probe | bars p50 / p90 / max | wall p50 / p90 |
|---|---|---:|
| `age20` | 12 / 19 / 20 | 15 min / 85 min |
| `age100` | 31 / 79 / 100 | 45 min / 281 min |
| `none` | 3,822 / 56,558 / 110,138 | 7,780 min / 57,075 min |
| `b1` | 22 / 75.8 / 100 | 36 min / 82.6 min |

---

## 7. Pre-registered contract outcomes (K1–K5)

| Flag | Pre-registered rule | `age100` | `none` | `b1` |
|---|---|---|---|---|
| **K1 NULL_RECOVERY** | recovery < 25 % ⇒ NULL_RESULT | pass (69.2 %) | pass (100 %) | pass overall (48.1 %) — but **NULL by TF** on M5/M15/H1 (0 %) |
| **K2 STALE_CAUTION** | > 20 % of newly-selected > 24 h, or any > 7 d | pass (7.6 %, 0 > 7 d) | **FAIL — 78.2 % > 24 h, 57 > 7 d** | pass (0, 0) |
| **K3 SELECTION_CHANGE** | > 10 % of the 218 change level | **FAIL — 48.17 %** | **FAIL — 94.04 %** | **FAIL — 38.53 %** |
| **K4 NO_FITTING** | probes fixed before the run | pass — `{20, 100, None}` + the pre-declared `b1` only; no re-run after seeing numbers | | |
| **K5 DETERMINISM** | two runs identical | pass — `nov24` shard regenerated byte-identically (md5 `85ec2d8a…`), summary identical | | |

**K1 has no trigger anywhere as written**, but that is a property of the threshold meeting these data, not a vindication of the options: `b1`'s M5/M15/H1 recovery is 0 % by construction.

---

## 8. Recommendation to the Architect (no auto-lock)

1. **Do not lock `none`.** It is disqualified on pre-registered grounds (K2) *and* on target quality: recovered median 0.274 ATR, 57 swings older than 7 days, 94 % churn. A structural branch whose median objective is 0.27 ATR is worse than the 4×ATR fallback it replaces.
2. **Do not read `b1` as C.** It tightens M15 (7) and H1 (2) relative to today and cannot recover them; it is a wall-time-parity sensitivity, useful only to show that M1 is where the loss lives.
3. **`age100` is the only probe that survives on target quality** (recovered p50 0.585 ATR) — but it carries K3 at 48 %, which means adopting it is a **selection change on the existing structural book**, not a coverage fix. If the Architect wants it, the ruling should say so explicitly and the follow-on work should re-read the 105 re-priced plans before anything downstream is compared.
4. **Shape of the constant (C):** the data rule out "one integer for every TF" on two counts — a bare integer is TF-ambiguous (§1 of the design note), and a single value that recovers M1 (100) is 4× too loose on M5 in wall-time terms while 100 bars on H1 is 4.2 days. The measured evidence supports a **TF-aware window anchored on 100 confirmation-TF bars for the M1 layer** with an explicitly ruled value for M5/M15/H1 — but this is the Architect's choice, and it is **not locked here**.
5. **Ranking is now the live question.** Every churn number above is produced by `(dist, -candle_index)` — nearest-in-price with recency only as a tie-break. If the intent is "use older structure only when it is a *better* target", the ranking is the lever, not the window. That is outside this engagement and is flagged, not proposed.
6. **No performance claim is made or implied.** Nothing here touches PF, expectancy, win rate or R; `tp_dist` is a representation descriptor.

---

## 9. Limitations

- **Book F only** (P0 book scope); no product/superset claim.
- The 4-row baseline delta vs P4 (§2) is documented, not resolved — P4's harness script is missing from the tree, so its exact index/prefix convention cannot be re-executed.
- `none`'s 100 % recovery is **saturated by construction** (it is the P4 §4.3 finding); its informational content is entirely in §4 (distance) and §6 (staleness).
- Age is measured to the winning swing's **base candle**, matching the P4 convention.
- One confirmation series per segment is built at a time; the run is resumable per segment via `shards/` and was resumed after two process kills. Shard determinism was verified on one segment, not on all twelve.

---

## 10. Reproduce

```bash
python 06_RESEARCH/scripts/structural_tp_age_cap_measure.py
```

Resumable: existing `results/structural_tp_age_cap/shards/<segment>.json` are reused; delete a shard to recompute that segment. Exit code `3` means the run is incomplete (segments missing) — rerun, do not trust partial metrics.
