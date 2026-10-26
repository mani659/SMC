# LTF CONFIRMATION ON SWEPT POIs — FLOWCHART STEP 3 (READ-ONLY NOTE)

> **DIAGNOSTIC — NOT EDGE.**
> Of 946 swept POI episodes, 490 show a Stage-3 trigger completion
> within 48 M5 bars after the first sweep. No threshold was changed,
> no gate follows, no production code was touched. No table supports
> or refutes edge or licenses any filter.

**Date:** 2026-10-11 · **Authority:** Lead Architect Step-3 directive (after POI_LINKED_SWEEP_RATE_NOTE.md).
**LTF_CONFIRM_STATUS: PASS** (script + artifacts + 5 new tests green).
**LOGIC_CHANGED: NO** (triggers only EVALUATED in scan mode, under `04_SRC` + research tests).

---

## 1. Method (one line)

Same evaluation mode as `stage3_trigger_visibility.scan_inventory`
(one `SeriesState(M5)` per bar, `TriggerRouter` matrix-eligible
triggers evaluated directly with episode zone+bounds+direction in
`TriggerContext`, EVERY completion recorded ungated) — only the window
moves: structure close → first-sweep bar, horizon → +48 M5 bars max
(single pass; nested horizons derived, never re-run). POI models mirror
product compatibility (m1m7 tag unions; M8 + facet exactly as the
visibility pack). Link rule frozen: sweep_bar < completion_bar ≤
sweep_bar + H for H in {5, 12, 20, 48} (H = 20 reuses the locked
give-up scale; strict-greater excludes same-timestamp ambiguity).
M15 skipped by design (product evaluates triggers on M5 only).

## 2. Confirm rate @ each H (946 swept episodes; 147 unswept = n only)

| Horizon (M5 bars) | Confirmed | Rate |
|---|---|---|
| 5 | 65 | **6.9%** |
| 12 | 149 | **15.8%** |
| 20 (give-up scale) | 282 | **29.8%** |
| 48 | 490 | **51.8%** |

605 total completions over the 490 confirmed episodes (≤4 per
episode); median 19 M5 bars (~95 min) from sweep to first confirm
(min 1, max 48).

## 3. By trigger (first confirmation) and by group

First-confirm mix: **F 393 / A 47 / B 44 / E 5 / C 1** — F is 80% of
first confirmations (same family dominance as every prior pack; D
absent structurally as ruled).

Confirm @48 by group: H4 22/56 (**39.3%**) / H1 86/163 (**52.8%**) /
M8-H4 314/605 (**51.9%**) / M8-D1 61/106 (**57.5%**) / M8-W1 7/16
(**43.8%**) — no group dominates or collapses.

Confirm @48 by kind: M1 50.6% / M2 53.4% / M4 41.5% / M7 48.3% /
M8-ds 55.5% / M8-fvg 47.2% / M8-ob 54.1% (M3 1/1, M5/M6 n ≤ 3) —
**kind does not separate confirm rates** (41–58% band across all
families with n; descriptive, not a finding of equality).

## 4. Reading (descriptive only — DIAGNOSTIC)

About half of swept POIs confirm within ~4 hours, overwhelmingly via
F, at similar rates across TFs and zone kinds. Against the product
funnel (10 routes from 501 scans → 3 fills), the gap between 490
confirmed episodes and single-digit routes is the router + placement
chain (chronological-first, §24 windows, R7 proximity, sessions,
one-shot), not missing geometry — the same conclusion as the
visibility pack, now anchored at swept POIs instead of structures.
Unswept episodes (147) never enter any denominator above.

## 5. Verification

- 5 new tests (window edges both sides, nested monotonicity,
  letter normalization across 3 shapes, earliest-confirm order with
  tie-break, episode-POI model mapping incl. M8 facet).
- `locked_constants.py` diff empty; no `04_SRC/smc` change.
- Rerun byte-identity check below (repo practice for ledgers).

## 6. Limitations (binding on Step 4 — DIAGNOSTIC)

- Completion bars index this script's M5 series (canonical pipeline —
  same grid as the packs).
- Trigger-internal zone/direction gates run as coded (no new linking
  tolerance); same-bar completions excluded by the strict-greater rule.
- Episodes sweeping within 48 M5 bars of series end read short
  windows honestly (flags reflect observed bars only).
- No gate, no threshold, no live rule follows.

## 7. Pointer: NEXT = Step 4 entry path on confirmed swept POIs

`confirm_per_episode.csv` (946 rows: flags ×4, first trigger,
bars-to-confirm, completion counts) joined to Step-1 bounds and
Step-2 sweep timestamps is the input: of confirmed episodes, what the
entry path (route → place → fill) admits — then outcome only.

---

**Artifacts:** `06_RESEARCH/scripts/poi_swept_ltf_confirm.py` (new) ·
`06_RESEARCH/results/poi_swept_ltf_confirm/` (`confirm_per_episode.csv`
946 rows, `summary.json` with frozen rules + rates + mixes) · tests
`04_SRC/tests/test_poi_swept_ltf_confirm.py` (5).
