# R1 — PURE SINGLE-TAG CONFIRMATION BOOKS (B, C, E mandatory; A, F controls)

**Status: measurement only — `LOGIC_CHANGED: NO` for production defaults.**
Research-only harness; every shipped default untouched; `locked_constants.py`
diff empty. No edge claim, no SL program, no parallel engine shipped.

---

## 1. R0 admission map (summary)

Full code-cited map: `06_RESEARCH/R0_TRIGGER_ADMISSION_MAP.md`.

| Tier | Detection TF | Confirmation TF(s) | Confirm menu (as-coded) |
|---|---|---|---|
| `DAY` | D1 | H1 | **A, B, C, D, E, F** |
| `H4` | H4 | M5, M15 | **A, D, F** |
| `H1` | H1 | M5, M1 | **A, D, F** |
| `M15` | M15 | M1 | **A, D, F** |

- **B / C / E are confirmable on the DAY tier only** — every M15/H1/H4-detected
  POI is structurally excluded from them (`MENU_TIER_EXCLUDED`), which is the
  measured dominant starvation gate (`BCE_STARVATION_PROBE_REPORT.md`: B 144/185,
  C 10/12, E 19/21; 0 B/C/E H1 confirmations all year).
- Cross-tag race: chronological first-valid + one-shot POI consumption; the
  §15 grade is a same-bar tie-break only.
- One-story guard lives at the `PipelineAdapter` intake (after the menu, before
  risk); the menu itself does not run it. R1 keeps it **AS-CODED**.

## 2. Method

### 2.1 Harness isolation (research-only, runtime injection)

`06_RESEARCH/scripts/r1_pure_tag_books.py` replays the product_1y armed
universe through the real menu + adapter + runner seam. For each run tag T, a
`TierInjection` context manager patches, **inside the worker process only**:

- `ProductMenuEngine.__init__` to construct the engine with injected tiers
  (`MenuTier(..., trigger_types=(T,))`),
- the module map `_TIER_BY_DETECTION` to contain only the injected tiers,

and restores the original state on exit. Production files
(`product_menu_mtf.py` tier table, `locked_constants.py`) are never edited;
the live demo path is untouched. Per hypothesis the trigger mix on routed /
filled trades must be `{T: 100%}` — any other letter aborts the run
(fail-loud cross-tag-leak check in-worker and in aggregation).

### 2.2 Variants

- **R1-D1**: ONLY the DAY tier (D1 detection → H1 confirmation), pure T.
- **R1-MID**: ONLY the mid tiers (M15 conf M1 / H1 conf M5+M1 /
  H4 conf M5+M15), pure T — the counterfactual to `MENU_TIER_EXCLUDED`.
- Controls: T=A and T=F run the same variants (A = as-coded workhorse,
  F = BOS/OB workhorse) as the comparison baseline.
- PROD anchor: production tiers unmodified, replayed per direction hypothesis.

### 2.3 Window, universe, seam fidelity

- Exec window: **2024-11-01 → 2025-10-31 UTC**, load from 2024-09-01
  (fail-loud if the canonical dataset lacks the window) — identical to
  Scan 1 / product_1y. 12 monthly segments, processed in parallel workers.
- Armed universe: product_1y `run1/<seg>/armed_records.json` reused verbatim
  (3,731 armed POIs; zone bounds, model tags, armed_bar, detection TF).
  Detection is tier-injection-invariant (menu tiers gate confirmation only),
  so no detection re-run is needed — this is the fast seam replay.
- Per-M5-bar loop mirrors phase3's menu composition minus detection batches:
  arm-due (`engine.arm_at` + `menu.register_armed` at the armed bar) →
  `menu.on_execution_bar` (closed-prefix streams, `MENU_WARMUP_BARS=300`
  cursor mirror) → winners → `adapter.queue_menu_candidate` →
  `runner.on_bar` (production `BacktestRunner`, `RunnerConfig` and
  `CostConfig()` verbatim from phase3). No stop redesign; SL/TP attach
  as-coded; PnL diagnostic only.
- §5 state: `adapter.set_menu_confirmation` wires the menu to the real
  `PipelineEngine` state machine (production wiring); reconstructed POIs are
  armed into a real engine, so the adapter's per-bar §5 feed evolves
  FRESH → TESTED → VIOLATED exactly as the product does — the
  `MENU_ALLOWED_POI_STATES` gate operates on real state. One-story guard
  AS-CODED (its `duplicate_story_*` counters are reported per run).

### 2.4 Direction handling and the anchor rule

Armed records export no direction. Filled POIs (239 across the year, 236
unique POIs) carry their TRUE product direction (from product_1y trades.csv);
every other POI runs under BOTH direction hypotheses (LONG / SHORT — the
Scan 1B convention). A price-at-arm vs zone-bounds direction heuristic was
tested and REJECTED: only 97.7% accurate on outside-zone knowns and 67/239
fills sit inside the zone at arm (unresolvable).

**ANCHOR RULE**: every product_1y fill per segment must appear in the UNION of
the LONG and SHORT PROD replays (plan identity: poi_id + trigger + entry_at +
entry_price + direction). A fill missing from BOTH hypotheses, or missing from
a hypothesis whose replay shows the POI never even WON its window, is a
machinery divergence → FAIL LOUD. Per-hypothesis misses are attributed to
direction artifacts (extra artifact fills can trip the as-coded circuit
breaker / one-story guard — expected and documented per segment).

### 2.5 Bans honored

- No production default menu change; no matrix grade fishing.
- No stop-loss redesign (SL/TP attachment as-coded).
- `locked_constants.py` diff empty (verified pre-commit).
- No expectancy language in this report; PnL is diagnostic only.

## 3. Results matrix

Full year, 12 segments, both direction hypotheses per run; `routes`/`fills`
are UNIQUE unions across hypotheses and segments (plan identity). Trigger mix
on filled trades is `{T: 100%}` in every book — **CROSS_TAG_LEAK: NO**
(fail-loud check enforced in-worker and in aggregation; all runs passed).

| Book | armed | scans (episodes) | completions (wins) | routes (uniq) | fills (uniq) | detection-TF mix of fills | median hold bars |
|---|---|---|---|---|---|---|---|
| B / D1 | 2,118 | 270 | 0 | 0 | 0 | — | — |
| B / MID | 5,344 | 3,051 | 1,005 | 838 | **264** | M15 168 / H1 67 / H4 29 | 1 |
| C / D1 | 2,118 | 270 | 0 | 0 | 0 | — | — |
| C / MID | 5,344 | 3,188 | 945 | 795 | **219** | M15 156 / H1 54 / H4 9 | 0 |
| E / D1 | 2,118 | 270 | 0 | 0 | 0 | — | — |
| E / MID | 5,344 | 3,642 | 780 | 646 | **183** | M15 116 / H1 54 / H4 13 | 1 |
| A / D1 | 2,118 | 270 | 21 | 21 | 0 | — | — |
| A / MID | 5,344 | 4,772 | 422 | 358 | **64** | M15 26 / H1 22 / H4 16 | 2 |
| F / D1 | 2,118 | 270 | 107 | 98 | 14 | D1 14 | 6 |
| F / MID | 5,344 | 2,619 | 1,270 | 1,034 | **374** | M15 250 / H1 70 / H4 54 | 0 |

Definitions (counters from the stack's own instruments, nothing invented):
- **armed** — POIs armed into the injected-tier menu (sum of per-run
  `armed_pois`; ×2 for the two direction hypotheses).
- **scans** — one-shot confirmation windows opened by R2 sweeps
  (sum of `menu_episodes`).
- **completions** — windows WON by the pure tag (sum of `menu_winners`).
- **routes / fills** — unique unions across direction hypotheses and segments
  (`(poi, trigger, sweep_ts)` for routes; plan identity incl. entry/SL/TP
  floats and direction for fills).

Reading notes:
- Fill counts are **upper bounds against a single-direction reality**: each
  non-filled POI runs under BOTH hypotheses, and the union keeps both
  directions' artifact fills (documented §2.4). The claim they support is
  EXISTENCE (the tag produces confirms/routes/fills when alone), not a
  production-equivalent count.
- Wins do not all reach fills: the as-coded one-story guard is the biggest
  absorber in the MID books (B 582 / C 566 / E 452 / A 302 / F 616
  `duplicate_story_menu` drops summed over hypotheses), then session blocks
  (39-58 per book), `skip_place_far_from_zone` and the circuit breaker
  (per-run `blocked_by_reason` / `story_counters` in
  `results/r1_pure_tag/_runs/<seg>/<run>/summary.json`).
- The D1 tier (full alphabet as-coded) never completes B/C/E on its H1
  confirmation window in this year (0 wins in 270 windows); A completes 21
  windows but 0 fills; F completes 107 and fills 14.

## 4. Readout

1. **The production starvation is admission-gated, not signal-absence.**
   B/C/E — zero routes and zero fills in the production mix all year — produce
   1,005 / 945 / 780 window wins and 264 / 219 / 183 unique fills when the
   menu carries ONLY that letter on the mid tiers. The tags are confirmable;
   the shipped per-tier menu (`_TIER_ADF`) is what excludes them.
2. **The D1/DAY tier is not the starved tags' fix.** Even with the full
   alphabet as-coded, DAY-tier windows complete B/C/E ZERO times in the year
   (270 windows) — H1 confirmation on D1-detected zones rarely produces
   diagonal/divergence completions in this data. The mid tiers are where the
   tags live (their fill detection-TF mix is M15-heavy: B 168, C 156,
   E 116 of their fills).
3. **Controls behave consistently with production.** A/MID fills 64 vs the
   production mix's 13 A fills; F/MID fills 374 vs 226 production F fills
   (both inflated by the two-hypothesis union, as above). F remains the
   dominant completer (1,270 wins), A the rarest mid-tier completer (422)
   with the fewest fills per win.
4. **One-story guard interactions are material and as-coded.** e.g. A/MID
   wins 422 windows but only 358 unique routes / 64 fills; guard
   `duplicate_story_menu` drops, session blocks and zone-place skips absorb
   most of the gap. Any future parallel-book design must specify whether the
   guard stays GLOBAL (one shared book) or becomes per-book — that is a
   design ruling, not measured here.
5. **Anchor fidelity (machinery gate).** Every one of the 239 product fills
   is reproduced by the replay seam up to the menu machinery: 237/239 appear
   in the LONG∪SHORT PROD replay union as FILLS; ZERO fills are
   missing-without-window-win — no machinery divergence in the
   menu/confirmation layer. The remaining 2 (aug25 F fills
   `poi-005876`, `poi-022439`) WON their windows in both hypotheses and were
   blocked DOWNSTREAM of the menu by replay-only state, measured
   per-candidate by the blocked-entry probe
   (`06_RESEARCH/results/r1_pure_tag/_probe/blocked_probe.json`):
   - `poi-005876` — blocked by the as-coded **circuit breaker** at its
     submission bar (13:40) in both hypotheses; the breaker was tripped by
     hypothesis-direction artifact losses that cannot exist in production
     (its replay completion is also 5 M1 bars late, `F@13531` vs
     production `F@13526`).
   - `poi-022439` — LONG: circuit-breaker block (19:50); SHORT: an artifact
     POI (`poi-007098`, non-filled in production) produced the IDENTICAL
     executable plan (same direction/trigger/entry/SL/TP floats, same
     instant) and consumed the one-story slot — the plan was reproduced,
     attributed to a different POI id by queue order.
   The one earlier union violation (may25 `poi-005013`) was a TRUTH-MAP BUG
   (cross-segment POI-id collision in the direction map), fixed by scoping
   truth per segment; its segment re-ran and its anchor passes.

## 5. Implications for FUTURE parallel dedicated paths (recommendations only)

- **Evidence basis exists**: a parallel per-tag book would carry confirmable
  tags that the single blended menu structurally excludes. R1's pure books
  are the feasibility measurement; nothing here ships.
- **Open design questions an architect ruling must settle** (not measured
  here): per-book vs shared one-story guard; portfolio-level risk seams
  (circuit breaker, daily loss, same-level) shared vs per-book; capital
  split and ticket sizing across books; duplicate-plan collision across
  books (the story rule is plan-identity — two books confirming the SAME
  POI's plan would double-place without a cross-book guard).
- **Observed runtime hazard**: the MID variant's M1-confirmation rescan is
  super-linear in active episodes (single runs up to 14,500 s; the A/E MID
  books dominated the 18.9-h wall). A parallel-path implementation must
  budget for this cost profile or fix the swing-recompute caching seam.
- **Direction data gap**: armed records export no direction; R1 inferred it
  per hypothesis. A production parallel path needs direction exported at
  the arm seam (or an authoritative direction resolver) — a small, targeted
  product-side data change, out of scope here.

## 6. Explicit non-goals

- **No edge claim** — these books are counterfactual measurements, not
  strategies; no expectancy is computed or asserted.
- **No SL program** — SL/TP attachment is as-coded; the 40-60 style P/L
  deep-dive stays deferred per owner intent.
- **No parallel engine shipped this engagement** — R1 isolates tags so a
  future parallel-book design is evidence-based; nothing here changes the
  product path.
- **One-story guard not redesigned** — kept AS-CODED; interactions are
  reported, not resolved.
- NEXT = Architect review → parallel-path design ruling OR product flag
  work; Scan 2 deferred per owner.
