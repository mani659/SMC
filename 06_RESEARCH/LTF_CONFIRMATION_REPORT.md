# LTF CONFIRMATION REPORT — identification only, NOT a trade claim

**Status: PASS** · dual=0 (per source pack) · direction_conflicts=0 · suite **762 passed** (754 pre-existing + 8 new) · double-run byte-identical.
**Program:** what the current machine (post-F1F2 emission, accepted H4/D1 packs) sees on **M15/M5 after an accepted H4 or D1 structure exists** — sweep, displacement (+BOS), FVG, trigger routes. Observation and reporting only: no thresholds, no filters, no PnL, no edge claims.

---

## 1. Window, sources, look-ahead (same for every structure)

| Item | Value |
|---|---|
| Exec window | 2025-06-01 00:00 → 2025-11-30 23:59 UTC (warm-up from 2025-03-01, M1 parquet) |
| Series | H4 1203 · D1 235 · M15 17,788 · M5 53,358 bars |
| HTF source | `events_h4_poi.csv` raw rows **658** (H4) + D1 subset **10** (≤10 labeled, optional) = **668 structures** |
| Kinds | ob 177 · demand_supply 307 · fvg 184 (H4 177/304/177 + D1 subset 0/3/7) |
| Look-ahead | **M5 = 20 bars** (`poi_give_up_bars()` = TRIGGER_A_EXPIRY, LOCKED §24) · **M15 = 7 bars** (`ceil(20×5/15)`, derived, ≥ wall-clock 105 min ≥ 100 min) — identical rule for every structure; only disclosed clamp: series end and exec end |
| Anchor rule | Look-ahead + router arm start at the origin bar's **CLOSE** (H4 origin +4h, D1 origin +24h). The forming bar is not yet a present structure — its own sub-bars must not self-link |
| Activity definition | ≥1 in-window link that **interacts with the zone** (relation `retest`/`inside`) **or** the structure's own router trigger. Time-nearby `above`/`below` links are recorded honestly but do **not** make a structure active |
| Routing | **pre-pillar observation** (detection → `SeriesState` → `arm_at` → `feed_bar` → `scan_route`, pillars/execution not run). `route_would_form` = would a router signal exist before pillars — a documented approximation, not a product fill |

## 2. What the machine sees (counts)

- **Stage-0 events (full-prefix pass):** M15 **13,474** · M5 **37,015** — sweeps, displacements(+BOS), FVGs across the exec window.
- **Ledger:** `events_ltf_confirmation.csv` — **15,352 rows** (668 structures × in-window links + explicit `NONE` rows for silent structures).
- **Link relations:** retest **6,889** · inside **3,083** · below **2,700** · above **2,680** · none 0 (excluded by rule).
- **Activity vs silent:** **624 active / 44 silent** (93.4% / 6.6%). An accepted HTF zone almost always gets *some* zone-interacting M15/M5 traffic within ~1h40m of its close; 44 structures show nothing at the zone in-window.
- **Trigger mix (A–F):** **`{"F": 2}`** — two pre-pillar Trigger-F routes (BOS + first touch of origin OB), both at zone relation `inside`:
  - `evt-ec41701aca47` DEMAND ZONE (H4) — F at 2025-07-13 22:10 UTC (detail: BOS at bar 25835; first touch of origin OB at bar 25836)
  - `evt-499a786ac28b` SUPPLY ZONE (H4) — F at 2025-10-26 22:10 UTC (BOS at bar 46504; first touch of origin OB at bar 46505)
  - Mix `{}` was explicitly allowed; the run legitimately produces only F — eligible types for M8 POIs include all six, and `evaluate_at` returns `None` (honest no-signal), never exceptions.
- **Cross-ref to the accepted product ledger:** 1 structure (`evt-12e83610e3c8`, H4 FVG 2025-06-16 08:00, SHORT) carries `actual_product_route=F@2025-06-18T07:35` — **44h after its close, outside the 100-minute identification window**, hence `route_would_form=no` on its rows (two different questions: "route within the identification window" vs "product eventually routed from this structure"). None of the 10 product `route_ltf` timestamps overlap this replay's 2 observed routes — expected: different arm/scan context (product = full pipeline; this = simplified full-prefix observation at close-anchor). Neither set is declared correct here.

## 3. Review sample (deterministic)

- Selection interleaves classes (active, silent, active, silent…) so both appear under the panel cap; full panel sets only (never partial); ts-sorted spread within class. Caps: ≤12 active, ≤8 silent, ≤40 panels.
- **Sampled: 13 structures = 7 active + 6 silent · 39 panels (13 HTF_CONTEXT + 13 M15 + 13 M5)** — all caps honored.
- M5 panel emitted when any in-window M5 row exists (including `above`/`below` ambient rows for silent structures — shown honestly with the zone band so distance is visible).
- Plain tags only: `SWEEP (M5)` 3,822 · `DISPLACEMENT (M5) + BOS (M5)` 3,716 · `FAIR VALUE GAP (M5)` 3,031 · `SWEEP (M15)` 1,731 · `DISPLACEMENT (M15) + BOS (M15)` 1,680 · `FAIR VALUE GAP (M15)` 1,213 · `DISPLACEMENT (M5)` 106 · `DISPLACEMENT (M15)` 51 · `TRIGGER F (M5)` 2. Never module paths; every label TF-suffixed. Subtitles show true detection_tf/chart_tf per panel (H4/D1/M15/M5 as rendered).
- Every chart footer: "structure / confirmation identification — NOT a trade claim".
- Determinism: full double-run → CSV **byte-identical**, summary.json identical (deterministic POI ids + geometry-derived structure ids).

## 4. Gates

| Gate | Result |
|---|---|
| `dual_exact_bounds_count` (per source pack) | **0** |
| `direction_conflict_count` (per source pack) | **0** |
| Look-ahead consistency | M5=20, M15=7, same rule every structure (tests) |
| Suite | **762 passed**, `locked_constants` diff empty |
| Status | **PASS** |

Cross-TF coincidence note: one H4 geometry equals one D1-subset geometry (`evt-6a8455eea149` ≡ `evt-bbf35c6dc170`, 3683.365–3691.895). Each pack individually proved dual=0; a cross-pack geometric tie is not a dual emission of either pack — the gate is therefore computed per source pack and documented (first run failed 1 dual on this exact tie before the rule was corrected).

## 5. Residuals (explicit, human/Architect side)

- **Human gates:** structure/confirmation role + direction scoring on the 39 sampled panels not run in this pack (identification surfaces only).
- **Armed-quality gates** on original H4/D1 armed charts remain open and were not blocked by this pack.
- The 0→2 route count and the `{F}`-only mix are observations of a simplified pre-pillar replay, not a statement about product route frequency (product: 10 `route_ltf` rows in the same window).
- Silent=44 structures: activity rule is zone-interaction; a structure with only `above`/`below` traffic counts silent by definition — reviewer may disagree with the threshold (no threshold is tunable here; it is a disclosed classification, not a filter).

## 6. Non-claims

No expectancy, PF, win-rate, or edge claims. No timing study, no Monte Carlo. No locked constant, pillar, trigger, risk, TP/SL or selection threshold was changed (pinned in tests). Product code untouched: `LOGIC_CHANGED: NO` — the only edit to an existing file this engagement is a **render-only subtitle fix** in `06_RESEARCH/scripts/generate_d1_poi_pack.py` (D1-hardcoded `detection_tf: D1 | chart_tf: D1` now reads the row's real values; H4 charts re-rendered, CSV byte-identical).

---

**Artifacts:** `06_RESEARCH/results/ltf_confirmation/` (`events_ltf_confirmation.csv`, `summary.json`, `charts/` 39 PNGs) · script `06_RESEARCH/scripts/ltf_confirmation_pack.py` · tests `04_SRC/tests/test_ltf_confirmation_pack.py` (8) · note `06_RESEARCH/LTF_CONFIRMATION_NOTE.md`.
