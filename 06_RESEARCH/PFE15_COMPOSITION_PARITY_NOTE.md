# PFE-1.5 — COMPOSITION PARITY: RESEARCH CAN RUN THE MENU LAW (P0-1 CLOSED)

**Date:** 2026-11-14 · **Program:** PFE step 1.5 · **`LOGIC_CHANGED: NO`**
**Closes:** `06_RESEARCH/PFE1_PRODUCT_VS_INTENDED_AUDIT.md` **P0-1**
(audit row L: live runs menu + seek; research ran seek only).

---

## 1. What "the product" means now

| Composition | Entry law | Status |
|---|---|---|
| **`menu`** | Sweep → one-shot LTF confirmation window (`ProductMenuEngine`, `PRODUCT_POLICY_MULTI_TF_CONFIRMATION.md`, LOCKED 2026-10-26) — the law live `PRODUCT_V1` runs | **Default for expert-facing evidence and PFE-2 primary** |
| **`seek`** | `PipelineAdapter` chronological scan on the §5a contract (pre-menu product path) | **Continuity diagnostic only** — the composition behind Phase 3, `frozen_funnel_6m_*` and O1–O5; NOT "the product" |

Both laws remain shipped: live `PRODUCT_V1` constructs the menu **and** the
adapter, and the adapter skips POIs the menu covers (`menu_covers_poi`). The
research composition now offers the same choice explicitly instead of silently
implementing only the seek half.

## 2. New entry point

`06_RESEARCH/scripts/phase3_structure_funnel.py` (the shared composition; the
frozen 6-month harness delegates to it):

```
--composition seek   # default, O1–O5 continuity (byte-compatible with prior runs)
--composition menu   # shipped live PRODUCT_V1 law
--menu-same-bar-asof # menu OPT-B posture (default OFF, as shipped)
```

`06_RESEARCH/scripts/frozen_funnel_6m_post_tp.py` forwards `--composition` to the
same composition, so a 6-month dual run needs no new harness.

### How `menu` mode drives the engine (mirrors live, not an approximation)

| Live (`smc/live/loop.py`) | Research (`phase3_structure_funnel.py`) |
|---|---|
| `ProductMenuEngine(symbol=…, same_bar_asof=cfg.enable_opt_b_same_bar_confirm)` | same class, same constructor args (`--menu-same-bar-asof`) |
| `adapter.set_menu_confirmation(menu)` (via loop ctor) | `adapter.set_menu_confirmation(menu)` |
| per newly armed POI: `menu.register_armed(poi, det_tf, armed_ts=bar.timestamp)` | identical, inside the batch's `report.armed` loop |
| per closed execution bar: `as_of = bar.timestamp + tf.minutes`; `closed[tf] = _closed_at(series, as_of)`; `menu.on_execution_bar(closed, as_of=as_of)` | identical (`as_of` = bar close, closed prefixes only, 300-bar warm-up handed once then incremental) |
| winners → `adapter.queue_menu_candidate(winner.candidate)` | identical |

The only deliberate difference is stream provisioning: live fetches each TF with
`copy_rates`; research hands the already-loaded resampled series (same closed-bar
rule). M15/M5 are derived from the execution slice, so they carry no pre-window
warm-up; H1/H4/D1 carry the `load_from` warm-up. Recorded as a known limitation.

## 3. Instrumentation added

`funnel_summary.json` now carries `composition` plus menu counters:
`menu_episodes`, `menu_winners`, `menu_errors`, and the adapter's
`menu_counters()` (`menu_submitted`, `menu_accepted`, `menu_retry_blocked`,
`menu_resubmitted`, `menu_expired_unplaced`, `menu_pending`). Diagnosis only —
no decision reads them.

## 4. Smoke (both modes, one short window)

`06_RESEARCH/scripts/pfe15_composition_smoke.py` → `PASS`, artifacts in
`06_RESEARCH/results/pfe15_smoke/{seek,menu}/` (exec 2025-10-01 → 10-03):

| | bars | HTF batches | armed | routes (seek) | menu episodes | menu winners | menu errors |
|---|---|---|---|---|---|---|---|
| seek | 804 | 66 | 11 | 2 | 0 | 0 | 0 |
| menu | 804 | 66 | 11 | 0 | 4 | 4 | 0 |

`seek` provably does not touch the menu (`menu_episodes == 0`); `menu` opens
episodes and wins confirmations, with the seek scan reserved for uncovered POIs.
A 10-day menu probe (not a measurement) placed 14 fills from 23 winners — placing
works through the existing risk/order seam.

**Do not read these counts as a comparison.** The two laws differ by definition
(menu requires and consumes a sweep; seek does not), so a count difference is not
a finding and is not ranked anywhere.

## 5. Boundaries

No C3, §5a, ZoneDedup, SL, risk-threshold, constant or TP-formula change; no
Mode B; no expectancy work; no 6-month run (that is PFE-2). `seek` mode output
fields are unchanged apart from the additive composition/menu keys.
