# ENTRY QUALITY + FLOWCHART MATCH — BOOKS F AND B (post-R1 year) — 2026-11-23

**Status:** `PASS` for the study (frame, checklist, sample, charts, sidecars complete).
**Not claimed:** that F/B entries are *good* trades. This note answers one question —
do these fills look like the intended SMC story (HTF POI → interaction → LTF confirmation →
entry), or like chase / noise / wrong structure? — and hands a scored sample to the Architect.
**Authority:** `PARALLEL_BOOKS_S3_REBASELINE_NOTE.md` (post-R1 authoritative) +
`PARALLEL_BOOKS_PRODUCT_GAP_RECONCILIATION.md`. The superset ruling (`NO`) is accepted and
not re-litigated; isolation is not re-examined.
**Scope:** read-only artifact analysis + chart rendering. No replay, no threshold, no trigger,
no expectancy / PF / "edge" language. `pnl` / `pnl_net` are never used as a criterion here.

---

## 1. Frame and method

| Item | Value |
|---|---|
| Universe | Post-R1 multi-book fills, books **F** and **B** only, deduped by the harness `fill_key` |
| Size | **592** fills — **F 351, B 241** (matches the S3 verdict's per-book union exactly) |
| Window | product_1y tiling (exec 2024-11-01..2025-10-31), 12 calendar-month segments × LONG/SHORT |
| Directions | long 311 / short 281 |
| Tier mix | F: M15 222, H1 64, H4 53, DAY 12 · B: M15 152, H1 59, H4 30 (no DAY-tier B fill in this frame; the DAY tier does carry all tags) |
| Harness | `06_RESEARCH/scripts/entry_quality_f_b.py` (read-only) |
| Outputs (gitignored) | `06_RESEARCH/results/entry_quality_f_b/{universe_features.csv, sample_index.csv, charts/, summary.json}` |

Everything scored is taken from the fill's own exported record: the menu stamp inside
`signal_data_json` (`armed_ts`, `sweep_ts`, `completion_ts`, `window_end_ts`, `tier`,
`detection_tf`, `confirmation_tf`, `label_at_confirm`, `atr_at_confirm`, `completion_close`,
`zone`), plus `zone_low/zone_high`, `original_sl`, `tp`, `tp_source`, `entry_anchor`,
`model_tags`. **No geometry is inferred and nothing is invented**; fields absent from a book
(F's `entry_anchor` vs B's `fib_band`/`origin_level`/`wave5_index`) are reported as absent.

### 1.1 Checklist (mechanical, no judgement)

| Check | Test | Meaning |
|---|---|---|
| **G1** | `armed_ts <= sweep_ts` | POI existed before the interaction |
| **G2** | `sweep_ts < completion_ts <= window_end_ts` | interaction → LTF confirmation inside the window |
| **G3** | confirmation TF is the locked child of the detection tier (D1→H1, H4→M5/M15, H1→M1/M5, M15→M1) | LTF confirmation is the intended one |
| **G4** | `zone_low <= entry <= zone_high` | limit entry inside the POI zone |
| **Q4** | zone position ≤ 92 % (long) / ≥ 8 % (short) | entry not pinned at the zone's chase edge |
| **Q5** | `retrace_at_confirm >= -0.25 ATR` | filled at/inside the confirmation price, not beyond it |
| **G5** | `tp_source == structural_swing` | setup carries a structural target, not only a 4×ATR fallback |

`STRONG 7/7 · PARTIAL 6/7 · WEAK ≤5/7`. **Q4/Q5 are agent-draft entry-location proxies, not
locked rules**; the Architect may score any row differently. Stop placement, latency and
risk-in-ATR are reported descriptively and deliberately **not scored** (the locked stop is an
ATR buffer and may legitimately sit inside the HTF zone).

---

## 2. Checklist results (full universe, not just the sample)

| Check | F (351) | B (241) |
|---|---:|---:|
| G1 POI before interaction | 339 (96.6 %) | 235 (97.5 %) |
| G2 confirmation inside window | **351 (100 %)** | 230 (95.4 %) |
| G3 confirmation TF locked | **351 (100 %)** | **241 (100 %)** |
| G4 entry inside POI zone | **351 (100 %)** | 233 (96.7 %) |
| Q4 not at chase edge | 328 (93.4 %) | 225 (93.4 %) |
| Q5 at/inside confirmation price | 236 (67.2 %) | 123 (51.0 %) |
| G5 structural TP | 222 (63.2 %) | 232 (96.3 %) |

**Draft score mix**

| Book | STRONG | PARTIAL | WEAK |
|---|---:|---:|---:|
| F | 164 (46.7 %) | 113 (32.2 %) | 74 (21.1 %) |
| B | 110 (45.6 %) | 104 (43.2 %) | 27 (11.2 %) |

Reading: the pipeline emits **on-story setups** in both books — POI → interaction → locked LTF
confirmation → in-zone limit is satisfied for ~100 % of F and ~95 %+ of B. The spread in the
draft score is driven by the two entry-location proxies and by target representation, not by
missing structure.

---

## 3. Entry-location descriptors (descriptive, not scored)

| Descriptor | F | B |
|---|---:|---:|
| Retrace vs confirmation close, median | **-0.03 ATR** | **-0.25 ATR** |
| Fills beyond the confirmation close by > 0.25 ATR | 115 (32.8 %) | 118 (49.0 %) |
| Stop inside the POI zone (descriptive) | 246 (70.1 %) | 137 (56.8 %) |
| Risk / ATR, median | 1.16 | 2.90 |
| Risk > 3 ATR | 15 (4.3 %) | **114 (47.3 %)** |
| Sweep → fill, median | 1.1 h | 3.3 h |
| Sweep → fill > 24 h | 15 (4.3 %) | 21 (8.7 %) |
| Entry at zone chase edge | 23 (6.6 %) | 16 (6.6 %) |
| ATR-fallback TP | **129 (36.8 %)** | 9 (3.7 %) |
| Confirmation after window end | **0** | **11 (4.6 %)** |
| Entry outside the POI zone | **0** | **8 (3.3 %)** |

Both books carry full structural context in `signal_data_json`: F always has `bos_index` +
`ob_index` (entry anchored `ob_proximal` 332 / `zone_edge_reanchor` 19); B always has
`fib_band` + `origin_level` + `wave5_index` and **no** `entry_anchor`. That is a book-attribute
difference, not a defect.

---

## 4. F vs B failure modes

### 4.1 F — "structure yes, target weak, a few timing conventions"

1. **ATR-fallback target, 129/351 (36.8 %).** The entry is on-story and in-zone but the setup
   carries no structural target; the exit is the 4×ATR fallback. This is the single largest
   non-structural count in the whole frame and it is an *F-only* issue (B is 9/241).
2. **POI armed after the interaction, 12/351, all DAY (4) and H4 (8).** On those tiers the POI's
   origin bar closes after the sweep it is reacting to — a convention of the HTF arm stamp
   (`armed_ts` = origin bar close), not a missing POI. Flagged, not reclassified.
3. **Entry at the zone chase edge, 23/351 (6.6 %)** — limit pinned in the last 8 % of the zone
   in the trade direction (M15 15, H4 5, H1 2, DAY 1).
4. **Slow fills, 15/351 > 24 h** after the sweep (median 1.1 h overall).
5. F has **no** post-window confirmations and **no** out-of-zone entries.

### 4.2 B — "structure yes, scale and timing edges"

1. **Wide stops relative to ATR: median 2.90 ATR, 114/241 (47.3 %) above 3 ATR** vs F's 1.16.
   B's stop is anchored beyond its fib origin, so its risk unit is materially larger than F's for
   comparable zones. This is the dominant B-specific difference and a real sizing-scale question
   for the Architect, not a chase artefact.
2. **Continuation-style fills: 118/241 (49.0 %) fill more than 0.25 ATR beyond the confirmation
   close** (median -0.25 ATR), versus F at parity (median -0.03). B's limit sits at the near edge
   of its fib band, so the fill waits for price to trade *through* the confirmation level rather
   than back into it. Whether that is intended for a leading-diagonal book is an Architect call.
3. **Confirmation/order life past the menu window: 11/241 (4.6 %), F zero.** Three confirm within
   1 h of `window_end`, one within 7 h, and **seven are 30.5–39.4 h late**: nov24 `poi-000925`
   +33.7 h; feb25 `poi-009519` +30.5 h and `poi-006053`/`poi-005511`/`poi-005104` +37.0…+38.8 h;
   jul25 `poi-004236` +39.4 h; oct25 `poi-010051` +32.2 h. The order rests beyond the menu window
   and still fills, so "confirmation inside the window" is nominal on those rows.
4. **Entry outside the POI zone: 8/241 (3.3 %).** Four are ≤0.44 price units from the edge
   (re-anchored limit at the boundary, rounding-level); the other four are 1.0–2.5 units outside
   (apr25 short `poi-001770` 2.45 below the zone; jul25 longs `poi-019884` 1.03, `poi-001184`
   1.11 and `poi-003722` 1.18 above).
5. **Entry at the zone chase edge, 16/241 (6.6 %)**, and 21/241 fills > 24 h after the sweep.

### 4.3 Is it chase / noise / wrong structure?

- **Wrong structure: not indicated.** 100 % of both books have a POI, an interaction that
  precedes the confirmation, a locked-tier LTF confirmation, and (F 100 %, B 96.7 %) an in-zone
  limit. There is no cluster of fills without structure.
- **Noise: not indicated as a class.** Only 23 F + 16 B (6.6 % each) sit at the zone's chase edge,
  and slow fills stay a small tail.
- **Chase: book-specific, and only for B is it material by count** — half of B's fills trigger
  beyond the confirmation close by > 0.25 ATR, which is a property of B's fib-band geometry
  (continuation entry) rather than of individual bad rows. F fills essentially at the
  confirmation price.
- **The real mismatches are representational, not structural:** F's missing structural target
  (36.8 %) and B's stop scale (47.3 % > 3 ATR) + 11 post-window confirmations.

---

## 5. Review sample and charts

**Selection rule (deterministic, seed 20261123; per book, cap 20):**
1. **Month coverage first** — one row per calendar month, alternating the currently thinner
   direction (median-dated row of the eligible stratum).
2. **Anomaly enrichment** — earliest + median row of each anomaly class: order inversion,
   confirmation after window, entry outside zone, entry at chase edge, no pullback ≥ 0.5 ATR,
   risk > 3 ATR.
3. **Round-robin** over (month, direction) strata, then even-spacing top-up, to the cap.

**Coverage achieved:** **F 20** (all 12 months; 9 long / 11 short) and **B 20** (all 12 months;
9 long / 11 short). Draft mix in the sample is **anomaly-weighted** relative to the universe —
F 5 STRONG / 6 PARTIAL / 9 WEAK, B 4 STRONG / 8 PARTIAL / 8 WEAK — by design, so the review sees
the mismatch classes as well as typical rows.

| Artifact | Path |
|---|---|
| Sample index (one row per reviewed fill, **architect columns blank**) | `06_RESEARCH/results/entry_quality_f_b/sample_index.csv` |
| Full universe features (all 592, same columns) | `06_RESEARCH/results/entry_quality_f_b/universe_features.csv` |
| Charts (PNG, M5 candles + zone band + POI-armed / sweep / confirm / window-end markers + entry/SL/TP/exit) | `06_RESEARCH/results/entry_quality_f_b/charts/<id>.png` |
| Sidecars (same facts as JSON, blank `architect_score` / `architect_note`) | `06_RESEARCH/results/entry_quality_f_b/charts/<id>.json` |
| Distributions + selection rule | `06_RESEARCH/results/entry_quality_f_b/summary.json` |

`sample_index.csv` columns for the human: `architect_score` (STRONG / PARTIAL / WEAK / UNCLEAR),
`architect_failure_mode` (free text: chase / late-confirm / wide-stop / target / other), and
`architect_note`. The agent columns are `agent_draft_score`, `checks_passed`, the seven boolean
checks, and a semicolon-joined `flags` list.

Charts follow `trade_inspector.py`'s visual language (manual M5 candles, POI-zone band, entry/SL
lines, exit marker) with the flowchart markers that review needs added: POI-armed, sweep, LTF
confirmation and window-end verticals, plus a panel stating the seven checks, the draft score and
the flags. **I inspected 3 of the 40 charts by eye** (B apr25 `poi-025137`, B nov24 `poi-000925`,
F dec24 `poi-005220`); the other 37 were generated but not visually reviewed — that is the
Architect's task.

Hypothesis-outcome labels (`f_timing_label`, `post_exit_class`) were **not** joined: they are
outcome-side fields and this study is deliberately entry-side only.

---

## 6. Explicit statements

```text
BOOKS: F, B only (S3 admitted set); C/E/A and D not in frame.
THRESHOLDS: none changed. TRIGGERS: none added. 04_SRC: untouched.
PROD_DEFAULTS_CHANGED: NO (live/installer parallel_books stays ()).
REPLAY: NONE (existing post-R1 artifacts + canonical M1 bars for charts only).
PERFORMANCE: no expectancy / PF / edge claim; pnl fields were not used to score entries.
DRAFT LABELS: agent-draft checklist output for Architect override, not a verdict.
```

---

## 7. Return block

```text
ENTRY_FB_STATUS: PASS (study complete; sample awaiting Architect scores)
SAMPLE_N: {F:20, B:20} — all 12 months each; F 9L/11S, B 9L/11S (draft 5S/6P/9W and 4S/8P/8W in sample)
UNIVERSE_N: {F:351, B:241} = 592 (S3 union); draft STRONG/PARTIAL/WEAK F 164/113/74, B 110/104/27
CHECK_MIX (pass share): F G1 96.6 / G2 100 / G3 100 / G4 100 / Q4 93.4 / Q5 67.2 / G5 63.2 ;
                        B G1 97.5 / G2 95.4 / G3 100 / G4 96.7 / Q4 93.4 / Q5 51.0 / G5 96.3
TOP_MISMATCHES: 1) F ATR-fallback TP 129/351 (36.8%) 2) B stop scale 2.90 ATR median, 114/241 >3 ATR
  3) B 11 post-window confirmations (7 >30h late; F has 0) 4) B 49% fills >0.25 ATR beyond confirm close
  (fib-band continuation entry; F at parity) 5) B 8 entries outside zone (4 rounding-level, 4 by 1.0-2.5)
  6) F 12 POI-armed-after-sweep (DAY/H4 convention) + 23 chase-edge entries per book
VERDICT_SHAPE: structure on-story in both books (wrong structure / noise not indicated); chase is
  book-specific and material only for B (geometry, not bad rows); real gaps are target representation (F)
  and stop scale + post-window timing (B)
NOTE_PATH: 06_RESEARCH/ENTRY_QUALITY_F_B_NOTES.md
HANDOFF_UPDATED: YES
NEXT_READY: Architect review of F/B entry quality (score sample_index.csv / charts)
```
