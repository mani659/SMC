# PRODUCT FOUNDATION INVENTORY — FLOWCHART / KB / ARCHIVE SCAN

**Banner: INVENTORY ONLY — NOT A CONTRACT — NOT EDGE.**

Authority: Architect 2026-10-21. Mode: READ-ONLY inventory of what exists on
disk — no strategy code was touched (`04_SRC/smc/**` edits: none),
`locked_constants.py` diff **EMPTY**, no stage was invented (absent things are
marked **MISSING**), no capture was re-run, and nothing here is a contract
text or an edge claim. Goal: map the actual foundation so the owner/expert can
draft the one-page ESSENCE CONTRACT from §7.

---

## §1 Executive finding

1. **A single authoritative flowchart exists — as text, not as a one-page trade
   story.** It is `00_LOCKED/LOCKED_DECISIONS.md` §16 ("The 5-Stage Master
   Flowchart Pipeline", FROZEN 2026-09-01, file header: "SMC POI & Flowchart
   Source of Truth"), rendered visually as **Revision 5** in
   `01_ARCHITECTURE/Flowcharts/v5_SMC_Master_Flowchart.html` (+ the architecture
   and L0–L7 workflow siblings). It is a *pipeline machinery* flowchart
   (sweep → displacement → swing gate → POI tags → pillars → triggers →
   execution), not the junior-traceable "level → sweep → confirm → entry"
   one-pager.
2. **Expert KB is present and citable.** `02_KNOWLEDGE_BASE/` holds 58 expert
   charts + a catalog README, plus dated expert sessions; the prose specs
   (`CHOCH_TYPES_AND_SWING_VALIDITY.md`, `MODEL_8_HTF_DEMAND_SUPPLY.md`,
   `SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md`) quote the expert's rules
   verbatim, and two independent marked-chart archives (2026-10-05 and
   2026-10-12) carry the operator's own flowchart-language walkthroughs.
3. **The flagship flowchart path and the shipped runtime disagree on the entry
   timeframe** — Rev 5's M8 path says D1/H4 zone → M5 approach → **M1** sniper
   trigger; the product contract (2026-09-23/26-10-06) ships **M5** execution
   with "no new M1-exec product" (§6).
4. **TP/SL policy is the other open seam:** the operator's verbatim rules
   ("TP = first swing high/low", "SL = 30 pips") are recorded **PENDING
   Architect ruling**; the locked structural-else-4×ATR TP branch is coded but
   UNFED; M8's spec says SL 2–5 pips; DUMB says fixed 2R (§4).
5. **Biggest gap for a one-page essence contract:** there is no single source
   that states the trade story (level → sweep → confirmation → entry → manage)
   as one page in the expert's own pattern vocabulary. The pointer to that
   synthesis ("NEXT: Architect flowchart synthesis",
   `06_RESEARCH/POI_CONFIRM_ENTRY_PATH_NOTE.md` §7, 2026-10-11) was **never
   consumed** — the DUMB track absorbed the flowchart work instead.
   **MISSING on disk.**

---

## §2 Source catalog

Material documents (scan roots: `00_LOCKED/`, `01_ARCHITECTURE/`,
`02_KNOWLEDGE_BASE/`, `03_REFERENCE_CODE/`, `06_RESEARCH/`, root):

| path | type | date/status | stages covered | authority |
|---|---|---|---|---|
| `00_LOCKED/LOCKED_DECISIONS.md` | **lock** | 2026-09-01, FROZEN ("single source of truth") | all (0A→4 + manage) | expert-confirmed + lock |
| `01_ARCHITECTURE/Flowcharts/v5_SMC_Master_Flowchart.html` (+ `.svg`) | **flowchart** | Rev 5, badges CURRENT/LOCKED/MODULAR | all, as §16 + rule panels | lock visualization |
| `01_ARCHITECTURE/Flowcharts/v5_SMC_Master_Architecture_Flowchart.html` (+ `.svg`) | flowchart | Rev 5 "Locked System" | overview + 5 pillars + M8 + confluence simulator | lock visualization |
| `01_ARCHITECTURE/Flowcharts/SMC_Workflow_Overview.html` | flowchart | Rev 5, 2026-09-05, L0–L7 | pipeline + bus/state infra | lock visualization |
| `01_ARCHITECTURE/Flowcharts/SMC_Pure_Entry_Models_Flowchart.{html,svg}` | flowchart | **SUPERSEDED** 2026-09-01 | entry only (3 pure models) | expert (historical) |
| `01_ARCHITECTURE/SMC_Pure_Entry_Models.md` | KB/spec | superseded 2026-09-01 | Level (prereq sweep) + Entry (3 limit models) | expert |
| `00_LOCKED/SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md` | lock/spec | 2026-08-27 COMPLETE | all (defs, 8 models, 5 pillars, 6 triggers, matrix) | expert + lock |
| `00_LOCKED/CHOCH_TYPES_AND_SWING_VALIDITY.md` | lock/expert | 2026-09-01 | sweep, confirmation (CHOCH 1/2/3, base candle, swing gate) | expert |
| `00_LOCKED/MODEL_8_HTF_DEMAND_SUPPLY.md` | lock/expert | 2026-09-01 FROZEN | Level (HTF zones), 3-step cascade, entry/SL/TP ideas | expert |
| `00_LOCKED/FOUNDATION_RESET_PLAN.md` | lock | 2026-09-21 ACTIVE (historical rulings) | R1–R9: M8 wiring, M5 exec, TP/SL routing, R7/R8/R9 | Lead Architect |
| `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` | lock | 2026-09-23 LOCKED | runtime law: H4+H1 detect / M5 exec, one driver, silent/deferred table | Lead Architect |
| `00_LOCKED/V1_1_RUNTIME_BASELINE_FREEZE.md` | lock | 2026-09-24 FROZEN | operate-and-observe; dated-ruling gate | Lead Architect + owner |
| `00_LOCKED/BASELINE_COMPLEX_V1_1_COMPARISON_POINT.md` | lock | 2026-10-21 | frozen COMPLEX comparison point | Architect |
| `00_LOCKED/DUMB_FLOWCHART_V1_DESIGN.md` · `06_RESEARCH/DUMB_FLOWCHART_V1_IMPLEMENTATION_NOTE.md` · `06_RESEARCH/DUMB_VS_COMPLEX_FLOWCHART_AUDIT.md` | lock/research | 2026-10-21 | the three-beat parallel flowchart (R1–R6) + audit | Architect |
| `02_KNOWLEDGE_BASE/README.md` (+ 58 PNGs, incl. `Expert_*` 2026-09-01/09-05 sessions) | **KB** | expert chart library | level/sweep/confirm patterns (visual) | **expert** |
| `02_KNOWLEDGE_BASE/expert_marked_examples/2026-10-12/` (2 PNGs + `INDEX.md`) | KB | 2026-10-12 QUALITATIVE_EXAMPLE | H4 FVG + H1 OB + double-bottom sweep; verbatim long logic | **expert** |
| `03_REFERENCE_CODE/expert_marked_charts/chart_{1..11}.jfif` + `06_RESEARCH/EXPERT_MARKED_CHARTS_INDEX.md` | KB/research | 2026-10-05 | operator's flowchart walk: W1 OB → D1 sweep → H4 sweep/FVG → M5/M1 confirm → entry | **expert/operator** |
| `06_RESEARCH/EXPERT_CHART_SYSTEM_MATCH_NOTE.md` | research | 2026-10-05, probe + **POLICY CAPTURE** | system-vs-chart match; verbatim TP/SL policy PENDING ruling | operator input |
| `06_RESEARCH/AS_CODED_ARCHITECTURE_FLOWCHART.md` | as-coded | 2026-09-23 | stage map 0A–5 as the code implements it | code |
| `06_RESEARCH/FLOWCHART_CODE_EVIDENCE_MAP.md` | as-coded/audit | 2026-09-20 FINAL | intended §16 ↔ modules, evidence per stage | code + audit |
| `06_RESEARCH/FLOWCHART_MATCH_NOTES.md` | research | 2026-09-20 | 13 curated charts scored vs spec; geometry-export gap | audit |
| `06_RESEARCH/FOUNDATION_RESET_QA_PACK.md` | research | 36-question audit | per-model entry/SL/TP ideas; M8 path citation (v5 SVG lines 470–502) | audit |
| `06_RESEARCH/{HTF_POI_CENSUS,POI_LINKED_SWEEP_RATE,POI_SWEPT_LTF_CONFIRM,POI_CONFIRM_ENTRY_PATH}_NOTE.md` | research | 2026-10-11 | empirical flowchart Steps 1–4 (funnel 1093→946→490→16→4→3) | audit |
| `01_ARCHITECTURE/SMC_WORKFLOW_ORCHESTRATION.md` | architecture | 2026-09-05 CANONICAL | L0–L7 event-bus design (Redis layers = intent, in-memory today) | architecture |
| `01_ARCHITECTURE/SMC_R1_MODULE_ARCHITECTURE.md` | architecture | 2026-08-27 | module layers + M4 qualification + anti-mining rule | architecture |
| `03_REFERENCE_CODE/GOLD_SMC_v25_DIAG.mq5` · `CAB_Unified_v16.4.mq5` | reference code | legacy EAs | §28 risk-constant source (v25_DIAG) | reference |

**04_SRC/smc top-level (one line each, no re-audit):** `config` frozen
thresholds/enums · `core` domain types (candle/swing/zone/poi) · `data`
parquet/MT5/resample · `detection` Stage-0A detectors (swings, liquidity,
sweeps, FVG, displacement) · `poi` M1–M8 models + confluence · `validation`
5 pillars + freshness state machine · `triggers` A–F + router + matrix ·
`orchestration` engine/multi-TF runtime glue · `risk` v25_DIAG port
(breaker/guards/BE/fill-regime) · `backtest` bar loop, fill model, runner,
orders/positions · `paper` demo runner · `live` loop/heartbeat/operator ·
`execution` MT5 orders · `logging` placeholder · `utils` ATR/timestamps/pips ·
`dumb` parallel DUMB path (new, default-OFF).

**Skipped as noise:** `01_ARCHITECTURE/N8N_*` + `SMC_Zero_Lag_Pipeline_n8n_workflow.json`
(infra tooling), `SMC_STATE.json`, old `SMC_SESSION_HANDOFF.md`, Phase 6/7
engineering design notes, `SMC_VISUALIZATION_ROADMAP.md`, `docs/`, `dist/`,
`logs/`, `ARCHIVE/`, `07_DATA/`.

---

## §3 Canonical flowchart reconstruction (strongest authorities only)

**A — the current authority: Revision 5 master pipeline**
(`LOCKED_DECISIONS.md` §16, FROZEN 2026-09-01; visually
`v5_SMC_Master_Flowchart.html`, which carries the identical stage chain):

```
STAGE 0:  Liquidity Sweep Detection (8 locked level types, wick-pierce +
          body-close-back)  →  Displacement Check (BOS + FVG + ≥1× ATR)
STAGE 0b: SWING VALIDATION GATE (Base Candle rule; two-bar reversal alone
          does NOT confirm)
STAGE 1:  POI MODEL CLASSIFICATION (M1–M8, all equal tags, confluence-scored)
STAGE 1b: CHOCH TYPE CLASSIFICATION (Rule 1 Standard / 2 Inside-Body /
          3 Inside-Wick)
STAGE 2:  POI VALIDATION — 5 Pillars (Zone Refinement ±0.5×ATR · Displacement
          ≥1×ATR · Premium/Discount 45/55 · Freshness strict 1-touch ·
          Inducement soft)
STAGE 3:  TRIGGER ROUTING — chronological first-valid trigger on M1/M5
          (matrix §15; expiries §24: A20 / B30 / C sweep+3 / D next-bar /
          E15 / F first-touch)
STAGE 4:  EXECUTION — news check → lot sizing → LIMIT order → PureRunner
          management (BE at 1.0×ATR + FVG invalidation + circuit breaker +
          same-level guard + Friday EOD)
```

**Flagship sub-flow (M8, "the expert's primary setup"):** STEP 1 HTF scan
(D1/H4: OB, FVG, Demand/Supply — single last opposing candle, full wick
range) → STEP 2 LTF approach (M5, watch only) → STEP 3 execution trigger
(**M1**; Ending Diagonal preferred; SL 2–5 pips; RR ≥ 1:5)
(`LOCKED_DECISIONS.md` §21–§22; `MODEL_8_HTF_DEMAND_SUPPLY.md` §3–4;
`FOUNDATION_RESET_QA_PACK.md` §16 citing the v5 SVG).

**B — older, superseded: the 3 Pure Entry Models**
(`01_ARCHITECTURE/SMC_Pure_Entry_Models.md` + its html/svg; superseded by the
8-POI + 6-trigger architecture on 2026-09-01, header-stamped): master
prerequisite = liquidity sweep, then Model 1 FVG 50%-midpoint limit ·
Model 2 CHOCH base-reversal limit at the zone · Model 3 OB/BOS limit at OB
edge/equilibrium. Retained as history; **not** the authority.

**C — the shipped-runtime overlay (newer than Rev 5, normative for product):**
`PRODUCT_RUNTIME_CONTRACT.md` (2026-09-23) + `LOCKED_DECISIONS.md` §4a
(2026-10-06): detection minimum **H4 + H1 required** (D1 optional → M8),
execution **M5**, one shared runtime, loud-fail on missing HTF. Where §4/§21's
TF-role tables conflict with it, §4a is normative for the product runtime; the
model/TF tables "remain the detection-model reference and are unchanged in
substance".

---

## §4 Stage ledger (Level → Manage): INTENDED / LOCKED / CODED / GAP

| Stage | INTENDED (doc + path) | LOCKED (in LOCKED_DECISIONS) | CODED | GAP |
|---|---|---|---|---|
| **1. Level / POI** | 8 equal tags M1–M8 detected on D/H4/H1/M30; M8 = raw zones on D1/H4 (single last opposing candle, full body+wicks); confluence = tag count (`SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md` §5; `QA_PACK` §C table) | §1 (equal tags), §4 + §4a (product detect min H4+H1, D1→M8 optional), §21/§22 (M8 zones, +0.10 htf_overlap bonus §26) | **COMPLEX:** all 8 models coded (`poi/models/m1–m8`); product runtime H4+H1 (+D1 to M8), M8 wired since FR-1 (was silent for 5y — `QA_PACK` §18). **DUMB:** M8 zone only, ungated | **PARTIAL** — the §4 model/TF table (M30 roles, H1 "all models") is reference-only vs the product's H4+H1 detect set; W1 has no detection (context only) |
| **2. Sweep / liquidity** | 8 locked level types (session H/L, PDH/PDL, PWH/PWL, EQH/EQL ≤4.5 pips, structural swing H/L via Base-Candle gate, POI sweeps, D&S boundary fallback, OB boundary fallback); wick pierces + body closes back (`LOCKED_DECISIONS` §2; `02_KNOWLEDGE_BASE/README.md` §7; R1 §3.5) | §2 (all 8 types + §2.7 zero-return edge), §19 (structural swing gate) | **COMPLEX:** `detection/liquidity_scanner` + `sweep_detector` (wick+close discipline) cover session/periodic/EQH/structural/POI sweeps. The **D&S/OB boundary fallback sweeps** (rules 5–6) have no confirmed dedicated emitter (`PRODUCT_RUNTIME_CONTRACT` §8: sweep-guard plumbing "dormant, no trigger emits a sweep_level"). **DUMB:** wick+close at zone extremes only | **PARTIAL** — fallback boundary-sweep classes are INTENDED + LOCKED but effectively **MISSING** in code |
| **3. Pattern confirmation** | full named pattern set (see §5): displacement BOS+FVG+1×ATR, base-candle swing validity, CHOCH 1/2/3, BOS, OB reaction, FVG, QML, EQH/EQL, double top/bottom (+neckline), RSI divergence, leading diagonal (Fib 50–61.8% W2), ending diagonal (W5 throw-under/over), two-bar engulfing + volume, BOS+OB continuation | §15 (POI×Trigger matrix, C★ preferred at M8), §17 (CHOCH types), §18/§19 (base candle / swing gate), §24 (expiries), §3 (displacement) | **COMPLEX:** triggers A/B/C/E/F coded + CHOCH classifier + base-candle gate + displacement checker; **D dead** (volume-less feed). **DUMB:** single mid-reclaim (a system-side proxy, not from the expert set) | **PARTIAL** — the expert charts' LTF confirmations (M5/M1 double top/bottom, CHOCH, Fib golden, ending diagonal) have **no same-TF ledger analogue** (`EXPERT_CHART_SYSTEM_MATCH_NOTE.md` §4.1: vocabulary gap — pipeline LTF vocabulary is trigger A–F geometry, not chart patterns) |
| **4. Entry** | LIMIT order at the confirmation level inside the POI zone, never market; two-bar = limit at 50% engulfing body; CHOCH = limit at broken level (not origin OB); F = OB proximal/50%; chronological first-valid (§9/§10/§12; R1 §7; `SMC_Pure_Entry_Models.md`) | §9, §10 (limit-not-market), §12 (first-valid), §21 (M8: limit at M1 trigger), §23 (unfilled expiry M5=12 / M1=30), §5a (seek/scan) | **COMPLEX:** limit on **every** path — intent matched (`AS_CODED` headline 3); R7/R9 band-deferral layered on. **DUMB:** market at confirm close (diagnostic only, disclosed) | **NONE** for order type; entry-**TF** conflict is itemized in §6 |
| **5. SL** | M3-class: beyond base-extreme wick − 0.3×ATR (`QA_PACK` per-model table); CHOCH: beyond the sweep extreme/head (§9); M8: **2–5 pips** beyond M1 structure (`MODEL_8` §4); operator verbatim: "**SL must always be 30 pips** below/above the small-TF entry" — PENDING ruling (`EXPERT_CHART_SYSTEM_MATCH_NOTE` §5) | §9 (sweep-extreme anchor), FR-R5 (`FOUNDATION_RESET_PLAN` §3: sweep extreme ± 0.3×ATR where stage/trigger defines a structural stop), §28 family (guards) | **COMPLEX:** FR-2 structural-else path with 0.3×ATR buffers (F/A/D/E; B/C exempt); observed honest stops ~0.82–0.89×ATR; PureRunner BE **mutates** SL (`original_sl` export added to decontaminate). **DUMB:** sweep extreme ± 0.10 ATR, immutable | **CONFLICT** — four live answers: 0.3×ATR buffer (locked intent) · 2–5 pips M1-structure (M8 spec) · 30 pips (operator, PENDING) · BE-mutated current SL (as-shipped book) |
| **6. TP / manage** | M8: RR ≥ 1:5 macro HTF target (`MODEL_8` §4); models: prior swing / opposing swing targets (`QA_PACK`); operator verbatim: "**TP must always be the first swing low/high**" — PENDING ruling (same note §5); management: PureRunner BE, FVG invalidation, breaker, same-level guard, Friday EOD (§28) | FR-R4 (`FOUNDATION_RESET_PLAN` §3: structural target if available, else 4×ATR cap), §28.1–.8 | **COMPLEX:** structural-TP branch **DESIGNED/UNFED** — no trigger emits a structural target, so the live/offline TP is the frozen 4×ATR fallback (`PRODUCT_RUNTIME_CONTRACT` §8); management coded (FVG exits only for F-routed trades). **DUMB:** fixed 2R | **CONFLICT/MISSING** — the "first swing" TP is unwired (PENDING), the structural TP is unfed by design, and three different answers coexist (4×ATR fallback / structural-else / DUMB 2R / operator first-swing pending) |

---

## §5 Named confirmation-pattern inventory (feeds the future contract's R3)

Every named pattern found in an INTENDED/LOCKED source, with its citation:

| # | pattern | one-line definition | source(s) |
|---|---|---|---|
| 1 | Liquidity sweep | wick pierces level + body closes back inside | LOCKED §2; R1 §3.5; KB README §7 |
| 2 | Displacement | BOS + FVG created + move ≥ 1× ATR (<0.5 hard fail) | LOCKED §3; R1 §6 P2 |
| 3 | Base-Candle swing validity | swing valid only if price later breaks + closes beyond the base candle's opposite extreme (two-bar reversal alone ≠ valid) | LOCKED §18/§19; CHOCH_TYPES §3 |
| 4 | BOS | candle close beyond prior swing | R1 §3.3 |
| 5 | CHOCH Rule 1 (Standard) | body close beyond the LAST swing of the trend — highest strength | LOCKED §17; CHOCH_TYPES §1; KB `choch_rule_1_standard_m15.png` |
| 6 | CHOCH Rule 2 (Inside Body) | body close beyond an intermediate level inside the correction — medium | LOCKED §17; `choch_rule_2_inside_choch_m1.png` |
| 7 | CHOCH Rule 3 (Inside Wick) | wick only beyond intermediate level — lowest, KEPT, tick-data pending | LOCKED §17; `choch_rule_3_wick_only_m1.png` |
| 8 | OB reaction / mitigation | OB = candle preceding the FVG (color irrelevant); entry on retest | R1 §3.1; KB `ob_entry_model.png` |
| 9 | FVG (3-candle imbalance) | c3.low > c1.high (bullish, mirrored bearish); entry at 50% mid | R1 §3.2; Pure Entry Model 1 |
| 10 | Quasimodo / QML | retest of the left-shoulder full-wick range after head + neckline break | LOCKED §14; R1 M4; KB `poi_model_4_quasimodo_qml_*.png` |
| 11 | Equal highs / lows (EQH/EQL) | double/triple peaks within ≤ 4.5 pips, both sides BSL/SSL | LOCKED §2; KB §7 |
| 12 | Double top/bottom — neckline retest (Model 6) | broken neckline retest | R1 M6; KB `poi_model_6_double_top_neckline_retest.png` |
| 13 | Double top/bottom + RSI divergence (Trigger E) | pattern in zone + RSI divergence; expiry 15 bars | R1 §7 E; KB `double_bottom_top_rsi_divergence.png` (KB says RSI(4/14); R1 says RSI(14) — version conflict flagged) |
| 14 | Leading diagonal (Trigger B) | 5-wave initiation; entry at Fib 50–61.8% Wave-2 pullback | R1 §7 B; KB `wave_start_of_trend.png` |
| 15 | Ending diagonal (Trigger C) | Wave-5 boundary trendline throw-under/over at the POI; **preferred at M8** (✓★) | R1 §7 C; LOCKED §15; KB `ending_diagonal_poi.png` |
| 16 | Two-bar engulfing + volume (Trigger D) | engulfing pair in zone, vol(bar2) < vol(bar1); limit at 50% body; next-bar only | LOCKED §10/§24; R1 §7 D; KB `two_bar_reversal.png` |
| 17 | BOS + OB continuation (Trigger F) | BOS confirms trend, retest of origin OB; limit at proximal/50%; first touch | R1 §7 F; KB `BOS.png` |
| 18 | In-between entry + fallback boundary sweep | trigger fires inside the zone body = in-between entry; absent → zone-extreme sweep watch | LOCKED §25 + §2 rules 5–6 |

**Expert-chart confirmation vocabulary** (operator's own markings, not yet a
locked rule set): M5 double top / double bottom, M1/M5 CHOCH, "Fibu golden"
area, ending diagonal @ H4 FVG — `03_REFERENCE_CODE/expert_marked_charts/` +
`06_RESEARCH/EXPERT_MARKED_CHARTS_INDEX.md`; H4 FVG + H1 OB + double-bottom
sweep with verbatim long logic — `02_KNOWLEDGE_BASE/expert_marked_examples/2026-10-12/INDEX.md`.

**System-side proxies (not expert patterns):** DUMB's mid-reclaim confirm
(`DUMB_FLOWCHART_V1_DESIGN.md` R3); Mode T's proof-bar mid gate
(`00_LOCKED/MODE_T_CONSOLE_MARKER_DESIGN.md`, diagnostic only).

---

## §6 Entry timeframe inventory (M1 vs M5 vs others — critical for the expert loop)

| TF | where it is INTENDED/LOCKED | status |
|---|---|---|
| **M1** | M8 Step 3 execution trigger, Ending Diagonal preferred, SL 2–5 pips (`LOCKED_DECISIONS` §21/§22; `MODEL_8_HTF_DEMAND_SUPPLY.md` §3–4; `QA_PACK` §16 "surgical execution trigger (M1)"); Trigger A "M1/M5"; §23 expiry M1=30 bars; KB `choch_m1_m5.png` ("CHOCH execution occurs strictly on the M1 or M5"); expert charts 4/6 marked M1 | **INTENT layer** — expert's sniper path; unchanged as the model reference by §4a |
| **M5** | Product execution TF: `PRODUCT_RUNTIME_CONTRACT` §1 ("M5 primary… no new M1-exec product"); `LOCKED_DECISIONS` §4a(3); §23 expiry M5=12 bars; review-chart label "LTF CONFIRMATION (M5 ENTRY, TRIGGER F)" (`CHANGELOG` 2026-09-25); Trigger A "M1/M5"; DUMB R2–R4 on M5 | **SHIPPED product runtime** |
| **M15** | Expert method only: `choch_rule_1_standard_m15.png`, the 2026-10-12 long chart ("M15 is NOT a product decision timeframe" — INDEX note); Trigger D/E list "M5 or M15" / "M15 or H1" as execution TFs (R1 §7) | reference/legacy; not product |
| **H1** | Trigger E "M15 or H1" (R1 §7); expert chart 11 "ENTRY (H1)" | reference only |

**CONFLICT (flagged, not resolved):** the flagship expert flowchart path says
the entry trigger fires on **M1** (2–4 TFs below the zone), while the locked
product runtime executes on **M5** and explicitly forbids a new M1-exec
product. §4a already rules that the M1 table "remains the model reference" —
so both are true in their layers, but a one-page essence contract must state
which TF the *trader* is told to execute on, or the contract will contradict
the runtime on its most-emphasized step.

---

## §7 What is safe to put on a one-page essence contract tomorrow

Items with a clear, dated INTENDED/LOCKED source (safe to draft from):

- **Level** = HTF demand/supply or OB/FVG zone on D1/H4 (H1 allowed): the
  single last opposing candle before a strong impulse, zone = full body+wicks,
  1-touch fresh (LOCKED §21/§22; `MODEL_8` §2b; KB §3f).
- **Sweep** = wick beyond the level + body close back inside; structural
  liquidity only; EQH/EQL ≤ 4.5 pips (LOCKED §2/§19; R1 §3.5).
- **Displacement preference** = BOS + FVG + ≥1×ATR marks institutional
  sponsorship (LOCKED §3).
- **Confirmation** = one named pattern from the §5 list at/near the zone;
  CHOCH body-close (Rule 1) is the highest-strength form; ending diagonal is
  the preferred M8 trigger; chronological first-valid wins (LOCKED §12/§15/§17).
- **Entry** = LIMIT at the confirmation level inside the zone — never market;
  two-bar = 50% of the engulfing body; CHOCH = the broken level, not the
  origin OB; unfilled orders expire (M5 = 12 bars) (LOCKED §9/§10/§23).
- **Event identity** = one validated POI + one trigger + one execution;
  no second-touch trades (strict 1-touch freshness) (LOCKED §5/§12; R1 §11).
- **Trade direction context** = HTF zone defines side; LTF pattern confirms;
  no lower layer rescues a failed higher layer (R1 §10).
- **Risk frame** = 0.5–1.0% risk, lot cap 0.10 (LOCKED §28.7) — as *policy*,
  pending the owner's live-risk decision.

**UNRESOLVED — list for owner/expert (do NOT put on the contract without a ruling):**

- **Entry TF** — M1 sniper (Rev 5 M8 / §21) vs M5 product exec (§4a /
  runtime contract): the contract must pick the trader-facing TF (§6).
- **SL rule** — 0.3×ATR buffer (FR-R5) vs 2–5 pips M1-structure (M8 spec) vs
  30-pip fixed (operator, PENDING ruling since 2026-10-05).
- **TP rule** — "first swing high/low" (operator, PENDING) vs
  structural-else-4×ATR (locked, UNFED) vs M8's 1:5 profile.
- **Mandatory vs optional confirmation set** — the matrix allows any of A–F;
  the expert charts show double top/bottom, CHOCH, Fib golden, ending
  diagonal; which are REQUIRED for the essence story? (Also: RSI(4/14) vs
  RSI(14) version conflict, item 13.)
- **Fib golden zone entry** — prominent in expert charts, has no locked rule
  (closest coded analogue: Trigger B's Fib 50–61.8% Wave-2).
- **Fallback boundary-sweep family** (LOCKED §2 rules 5–6) — locked as
  intent, MISSING in code (§4 stage 2).
- **Volume-dependent Trigger D** — locked but dead on the current feed; the
  essence page must say whether it is in or out.

---

## §8 Non-goals of this inventory

- No contract text is drafted here — §7 is the *material*, the contract is the
  owner/expert's writing task.
- No new flowchart stage was invented; absent items are marked **MISSING**
  (fallback sweep emitters; the one-page synthesis itself).
- Conflicts are **flagged, not resolved** (entry TF, SL, TP).
- Code was not re-audited: the CODED column cites the dated as-coded audits
  (`AS_CODED_ARCHITECTURE_FLOWCHART.md`, `FLOWCHART_CODE_EVIDENCE_MAP.md`) and
  the frozen runtime contract; the smc package list is one-line-per-package
  only.
- No capture, backtest, or suite run was performed; `LOGIC_CHANGED: NO`,
  `locked_constants.py` diff EMPTY.

---

## Return block

```
FOUNDATION_INV_STATUS: PASS
AUTHORITATIVE_FLOWCHART_PATH: 00_LOCKED/LOCKED_DECISIONS.md §16 (text, FROZEN 2026-09-01) + 01_ARCHITECTURE/Flowcharts/v5_SMC_Master_Flowchart.html (visual, Revision 5)
EXPERT_KB_PATHS: [02_KNOWLEDGE_BASE/README.md + 58 expert charts, 02_KNOWLEDGE_BASE/expert_marked_examples/2026-10-12/, 03_REFERENCE_CODE/expert_marked_charts/ + 06_RESEARCH/EXPERT_MARKED_CHARTS_INDEX.md, 00_LOCKED/CHOCH_TYPES_AND_SWING_VALIDITY.md, 00_LOCKED/MODEL_8_HTF_DEMAND_SUPPLY.md, 00_LOCKED/SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md]
STAGE_LEDGER_COMPLETE: YES (gaps flagged per cell: fallback sweeps MISSING; SL/TP CONFLICT; confirmation PARTIAL)
CONFIRM_PATTERNS_N: 18 (§5 core list, all cited) + expert-chart vocabulary (double top/bottom, Fib golden) + 2 system proxies
ENTRY_TF_CONFLICTS: YES — Rev-5 M8 sniper path is M1 (LOCKED §21/MODEL_8/QA_PACK §16) vs shipped product runtime M5 with "no new M1-exec product" (PRODUCT_RUNTIME_CONTRACT §1, LOCKED §4a); M15/H1 appear only as expert method or legacy trigger TFs
SAFE_FOR_CONTRACT: [HTF zone level definition (single last opposing candle, full wick, 1-touch) · sweep = wick + close-back (structural levels, EQH ≤4.5 pips) · displacement preference BOS+FVG+≥1ATR · named confirmation set (18 patterns, CHOCH-1 strongest, ending diagonal preferred at M8) · LIMIT entry at the confirmation level inside the zone, never market, chronological first-valid · one POI + one trigger + one execution · strict 1-touch freshness · HTF zone sets side, LTF confirms · risk band 0.5-1.0% / lot cap 0.10]
UNRESOLVED_FOR_OWNER: [entry TF (M1 vs M5) · SL rule (0.3xATR vs 2-5 pips vs operator 30-pip, PENDING) · TP rule (first swing PENDING vs structural-else-4ATR vs M8 1:5) · mandatory vs optional confirmation patterns (+ RSI 4/14 vs 14 conflict) · Fib golden zone entry (no locked rule) · fallback boundary-sweep family (locked intent, MISSING in code) · Trigger D on a volume-less feed (in or out)]
NOTE_PATH: 06_RESEARCH/PRODUCT_FOUNDATION_INVENTORY.md
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
NEXT_READY: Essence contract drafting (owner/expert) using §7
```

**Ledger cross-refs:** SESSION_HANDOFF 2026-10-21 (5) · CHANGELOG 2026-10-21 (5).
