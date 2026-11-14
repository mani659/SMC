# PFE-2 — FROZEN SIX-MONTH PRODUCT BACKTEST (MENU PRIMARY + SEEK SECONDARY)

**Date:** 2026-11-14 · **Program:** PFE step 2 · **`LOGIC_CHANGED: NO`**
**Status:** PASS **with a documented menu-window limitation** (see §1.1)
**Mode:** diagnostic evidence for expert validation. **NOT PERFORMANCE.** Any
PnL figure below is an unranked diagnostic at small n.

**Compositions:** `06_RESEARCH/scripts/phase3_structure_funnel.py
--composition {menu,seek}` (PFE-1.5; contract §11). Menu = shipped live
`PRODUCT_V1` law; seek = O1–O5 continuity.
**Artifacts:** `06_RESEARCH/results/pfe2_6m/` (gitignored results tree).
**Banners:** every trade in this pack is a **DIAGNOSTIC SAMPLE**, not edge.

---

## 1. Window and entry points

| Run | Composition | Exec window | Load | Bars (M5) |
|---|---|---|---|---|
| **A1/A2** | `menu` | 2025-10-01 → 2025-10-31 | 2025-05-01 | — (attempted, see §1.1) |
| **A1/A2 (final)** | `menu` | **2025-10-01 → 2025-10-10** | 2025-05-01 | 2,184 |
| A3/A4 | `menu` | 2025-06-01 → 2025-06-10 | 2025-05-01 | 1,956 |
| A5/A6 | `menu` | 2025-09-01 → 2025-09-10 | 2025-05-01 | 2,178 |
| **B1/B2** | `seek` | **2025-05-01 → 2025-10-31** | 2025-05-01 | 36,269 |
| C | `seek` | 2025-10-01 → 2025-10-31 (fingerprint) | 2025-05-01 | 6,324 |

Pre-registered before any funnel was read: window above, the two composition
names, and the rule that menu and seek are never ranked against each other.
Full product HTF set via `ensure_product_detection_frames` (D1/H4/H1/M15);
M1 parquet present and non-empty (fails loud otherwise).

### 1.1 Documented deviation — menu window (decided before reading any menu funnel)

The continuous **menu** 6-month run (`exec 2025-05-01 → 2025-10-31`, 36,269
bars, two parallel attempts) does **not** complete in practical time. Observed
before any menu result was inspected: 30.8 bars/s to bar 2,000, then 9.7 bars/s
at bar 4,000, then **< 2 bars/s** and no progress for >10 min while CPU-bound;
a *single-month* menu attempt also stalled at bar 2,000 of 6,324 (14.7 → < 2
bars/s) and was stopped. Cause is in the menu engine's bookkeeping, not in the
data: per-call full-series `detect_swings` on the M1/M5 confirmation streams
(cache keyed on series length, so it misses on every bar) plus per-detection-bar
scans of armed POIs × episodes. Live is unaffected (bounded 300-bar windows);
research at multi-month scale is quadratic. **No product code was changed to
work around it.**

Consequence, applied consistently: menu evidence is **three continuous
10-day windows inside the same six months**, each dual-run, and the full
six-month sample is the **seek** composition. This is weaker than the directive's
primary design and is the main residual for PFE-3 (§8).

---

## 2. Menu funnel (primary law — bounded windows)

| Metric | Jun 1–10 | Sep 1–10 | **Oct 1–10 (primary)** |
|---|---|---|---|
| HTF batches / errors | 162 / 1 | 181 / 1 | 181 / 1 |
| Armed POIs | 60 | 170 | **97** |
| Menu episodes opened | 22 | 25 | **30** |
| Menu winners | 18 | 3 | **23** |
| Menu errors | 0 | 0 | **0** |
| Placed | 11 | 2 | **14** |
| Placed with TP | 11 | 2 | **14** |
| Fills = trades | 11 | 2 | **14** |
| Trigger mix | F 11 | F 2 | **F 14** |
| Close mix | SL 11 | TP 2 | **SL 14** |
| Median hold (M5 bars) | 0 | 0 | 1 |
| Net PnL (diagnostic) | −1.4220 | +0.3040 | **−20.0151** |

Read as counts of a boundary sample, not as a rate forecast: menu conversion
varies sharply by window (episodes→winners 82% / 12% / 77%; armed→winners
30% / 2% / 24%). The menu is exercised in every window (`menu_errors 0`), and
the seek scan is dormant throughout (`routes 0` — menu-covered POIs are never
double-routed).

**Observation (no action proposed):** all 27 menu fills across the three
windows are Trigger F; A/D (and the DAY tier) never produced a winner in this
sample. Whether that is tier geometry or sample luck is a PFE-3 labelling
question, **not** a licence to change the menu's trigger subsets.

## 3. Seek funnel (secondary — continuity, full six months)

| Metric | B1 run1 | B2 run2 |
|---|---|---|
| Exec bars (M5) | 36,269 | 36,269 |
| HTF batches | 3,001 | 3,001 |
| Batch errors | 23 | 23 |
| Duplicates suppressed | 3,438 | 3,438 |
| Armed POIs | 1,865 | 1,865 |
| Routes | 670 | 670 |
| Placed | 81 | 81 |
| Fills = trades | 80 | 80 |
| Trigger mix | F 65 · B 10 · A 2 · E 2 · C 1 | identical |
| Close mix | TP 36 · SL 44 | identical |
| Net PnL (diagnostic) | −2.4038 | identical |
| Wall clock | 3,985.7 s | 3,976.4 s |

Route→placement conversion 12.1% (81/670); placed→fill 98.8%. The 23 batch
errors are early (cold start against a load window that begins at the exec
window's first day — see §8).

### October fingerprint (continuity check, run C)

`seek`, exec Oct 1–31, single run: **armed 441 · routes 149 · placed 11 · fills 11
· duplicates 586 · HTF batches 526 · batch_errors 1** — an exact reproduction of
the O1–O5 / post-C2 fingerprint, with `tp_source` 8 structural / 3 fallback and
exits 3 TP / 8 SL. **`menu_episodes == 0`** confirms seek mode does not touch the
menu. Continuity is intact; the PFE-1.5 changes are additive.

---

## 4. `tp_source` mix

| Scope | n | structural_swing | atr_fallback | none |
|---|---|---|---|---|
| Seek 6-month | 80 | **55 (68.8%)** | 25 (31.3%) | 0 |
| Seek Oct fingerprint | 11 | 8 | 3 | 0 |
| Menu Oct 1–10 | 14 | **7 (50%)** | 7 (50%) | 0 |
| Menu Jun 1–10 | 11 | 8 | 3 | 0 |
| Menu Sep 1–10 | 2 | 2 | 0 | 0 |
| **Menu total (3 windows)** | **27** | **17 (63.0%)** | **10 (37.0%)** | **0** |

Structural TP is now genuinely present on both bridges (PFE-1.5); the seek
six-month share (68.8%) is materially higher than the 30-day seek share measured
in O5 (8/11), which is exactly the kind of sampling variation that forbids
reading either number as a policy constant.

---

## 5. Determinism

| Composition | Pair | Result |
|---|---|---|
| Menu Jun 1–10 | run1 vs run2 | **PASS** — `trades.csv` + `report.json` byte-identical |
| Menu Sep 1–10 | run1 vs run2 | **PASS** — byte-identical |
| Menu Oct 1–10 | run1 vs run2 | **PASS** — byte-identical |
| Seek 6-month | run1 vs run2 | **PASS** — `trades.csv` (`S` identical) + `report.json` byte-identical |

Trades CSV SHA-256 (Oct menu pair): `7f26f82474d5…`; (Jun pair) identical within
pair; (Sep pair) identical within pair; seek pair identical. Determinism holds
across parallel and sequential execution ordering.

---

## 6. What expert validation may claim after this run

- The **menu law is runnable in research** and its funnel is observable end to
  end: armed → sweep episodes → LTF confirmations → winners → placements →
  fills, with structural/fallback TP provenance on every placement.
- On the sampled windows the shipped law produced **reviewable setups**
  (14 in ten October days, 11 in ten June days, 2 in ten September days) — enough
  to start a chart-level structure review, **not** enough to characterise a rate.
- On the six-month seek composition, the product funnel is **stable and
  reproducible** (1,865 armed, 670 routes, 80 fills, zero gaps in the sample
  audit) and October reconciles exactly with the frozen O1–O5 evidence.
- Every trade carries the labels an expert pack needs: trigger, model tags,
  pillar path, zone bounds, entry anchor, `tp_source`, close kind, timing label.

## 7. What it must NOT claim

- **No edge.** No expectancy, PF, viability or "works" claim at n=80 (seek) or
  n=27 (menu), all on one data source with zero spread/news modelling.
- **No cross-composition verdict.** Menu vs seek differ by definition (a sweep
  must occur and is consumed); menu n is a 10-day boundary sample and seek n is
  six months — comparing their net PnL would be a category error and is not done
  anywhere in this pack.
- **No trading-rate conclusion.** Menu armed→winner varied 2%–30% across three
  ten-day windows; that is a measurement of variance, not a defect and not a
  reason to touch C3, the sweep stage, ZoneDedup, SL or TP.
- **No 30-pip / 1:5 product rule** from these numbers; O4/O5 stand.
- No inference that the menu path is "better" because October's seek book was
  net negative and September's two menu trades were positive.

---

## 8. Residuals

1. **Menu six-month continuous run not produced** (performance, §1.1): menu
   evidence is three 10-day windows; the six-month volume sample is seek. A full
   menu 6m run needs a performance-only engagement (swing-cache incrementality,
   episode indexes) with its own tests before it can be trusted.
2. **Warm-up asymmetry:** D1/H4/H1 carry `load_from` warm-up; M15/M5 (and M1 in
   the menu streams) begin at the exec window, so early batches see thin
   confirmation history. Seek 6m shows this as **23 batch errors in the first
   hours** (vs 1 when the load window precedes the exec month, as in every
   prior October run).
3. **Queue at window end:** a short window can end with accepted-but-unprocessed
   queued entries (the 3-day smoke had 0 placements; the 10-day windows place
   normally). Read counts from windows that end on a settled day.
4. **Menu state resets per window:** the three menu windows start fresh
   (no POIs armed before the window), so cross-window spanning setups are not
   represented. Documented, not inferred.
5. **Diagnostic configuration unchanged:** spread 0.0, news dormant, all
   sessions, zero-cost close unless a cost hook is passed — completeness, not
   realism.
6. **n is small everywhere**; per-window menu counts (2, 11, 14) must not be
   averaged into a "monthly rate".

---

## 9. Return block

```text
PFE2_STATUS: PASS (with documented menu-window limitation)
WINDOW: seek exec 2025-05-01 → 2025-10-31 (36,269 M5 bars); menu exec 10-day windows Jun/Sep/Oct 2025 (Oct primary)
MENU_ARMED: 97 (Oct 1-10; Jun 60, Sep 170)
MENU_ROUTES: 0 (menu-covered; scan dormant)
MENU_FILLS: 14 (Oct 1-10; Jun 11, Sep 2)
MENU_TRADES: 14 (Oct; total 27 across three windows)
MENU_TP_SOURCE_MIX: Oct {structural_swing: 7, atr_fallback: 7}; all three {17, 10}
SEEK_ARMED: 1865
SEEK_ROUTES: 670
SEEK_FILLS: 80
SEEK_TRADES: 80
DETERMINISM_MENU: PASS (3 window pairs byte-identical)
DETERMINISM_SEEK: PASS (6m pair byte-identical)
NET_PL_MENU_DIAGNOSTIC: -20.0151 (n=14, Oct window; NOT performance)
NET_PL_SEEK_DIAGNOSTIC: -2.4038 (n=80; NOT performance)
REPORT_PATH: 06_RESEARCH/PFE2_SIX_MONTH_PRODUCT_BACKTEST.md
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
HANDOFF_UPDATED: YES
NEXT_READY: Architect review → PFE-3 expert pack
```
