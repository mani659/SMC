# DECOMPOSED 6M EVENT LEDGER + COMBINATION TESTS (DIAGNOSTIC)

> **DIAGNOSTIC — NOT EDGE.**
> 16,281 flowchart events inventoried on the frozen 6m window without
> requiring the product chain to complete, with frozen-horizon
> post-event reads in ATR units. No gate was loosened, no threshold
> moved, no production code touched. No table below supports or refutes
> edge, authorizes live capital, or licenses any filter.

**Date:** 2026-10-11 · **Authority:** Lead Architect Tier-1 directive (accepted audit `INDEPENDENT_FUNNEL_IDEA_AUDIT_2026-10-11.md`, Part C).
**DECOMPOSED_STATUS: PASS** (ledger built, combination tested, falsifications published, 7 new tests green).
**Scope:** measurement only. `LOGIC_CHANGED: NO` for `04_SRC/smc` (research script + tests only); locked_constants diff empty.

---

## 1. Frozen design (stated before running — nothing iterated)

Window exec 2025-06-01 → 2025-11-30 M5, M1 warm-up from 2025-05-01.
Concepts (independence = no arm/route/fill required): **1.** htf-zone
(668 accepted structures, same loader rules as the Stage-3 pack) ·
**2–4.** sweep / displacement / fvg + trigger A–F completions (accepted
LTF + Stage-3 ledgers reused verbatim; the 2 LTF TRIGGER rows skipped
— they live in the Stage-3 ledger, no double count) · **5.** the 3 real
fills, listed only. htf_context frozen with zero new parameters
(relation inside→inside, retest→near, above/below→far; diagnostic
dist_to_zone_atr alongside). Reference prices frozen (single level
as-is; range midpoint; trigger entry). Horizons frozen: H_ZONE = 20 M5
(product give-up scale, zone fate) / H_PATH = 100 M5 (Track-B horizon,
excursion/path). Numeraires frozen: ATR(14) Wilder SMA-seeded on M5 at
the event bar — no hypothetical stop invented anywhere, so ATR units,
never R, for non-trade events. Zone fate frozen (any adverse close →
VIOLATED, elif touched → TOUCHED, else UNTOUCHED). Invalidation frozen
(adverse ≥ 1.0×ATR). Truncation frozen and strict (metrics empty +
note, never extrapolated). Combination rule frozen: per concept,
inside-vs-far +1ATR Wilson-95% CIs with both cells n ≥ 30 — disjoint →
separates; overlap → does_not_separate; else insufficient_n. Overall:
separates if ANY concept separates, else does_not_separate if every
decisive concept overlaps, else insufficient_n. No-look-ahead:
prefix-only accepted inputs, read-only forward scans, timestamp
resolution (run-relative bar numbers never cross books). Reuse by
import: canonical loader + resample + CandleSeries from smc,
`wilder_atr_14` from the Track-B module. Script:
`06_RESEARCH/scripts/decomposed_6m_ledger.py`.

## 2. Ledger inventory (16,281 rows)

| Concept | Rows | Source (reused, SHAs in summary) |
|---|---|---|
| htf-zone | 668 | H4 pack raw 658 + D1 subset 10 (same loader rules) |
| sweep | 5,553 | LTF ledger non-trigger rows |
| displacement | 5,553 | LTF ledger non-trigger rows |
| fvg | 4,244 | LTF ledger non-trigger rows |
| trigger-F / A / E / C / B | 204 / 31 / 7 / 4 / 17 (263) | Stage-3 ledger (ungated inventory) |
| fills (concept 5) | 3 | product 6m refresh (listed only) |

Anchor gaps: 0. Path truncations: 0 (data runs to 2026-04, events end
2025-11). Context cells that are structurally empty (ledger-construction
facts, not findings): sweep-near 0, displacement-inside 0, fvg-inside 0,
trigger-near 0 — the source ledgers' relation vocabulary never emits
those combinations, which is exactly why three concepts cannot run the
inside-vs-far contrast (verdict: insufficient_n, correctly).

Detector rows are per-bar re-detections (same setup repeats across
bars): n counts events, not setups — all rates below are
event-weighted by construction (stated, not hidden).

## 3. Zone fates (668 accepted zones, H_ZONE = 20 M5 from close)

TOUCHED 376 / VIOLATED 292 / UNTOUCHED **0** — every accepted zone is
touched or violated within 20 M5 bars of its close (consistent with the
lifecycle audit: interaction lands on/near the arm bar because zones
form where price is). 43.7% violate within the horizon: zones do not
"hold" as levels nearly half the time — a descriptive zone-quality
read, not a rule (no gate follows from it here).

## 4. Combination test (LTF events × htf_context, +1ATR over H_PATH)

| Concept × context | n | +1ATR hit rate [95% CI] | +2ATR | Med MFE_ATR | Med MAE_ATR | Inv≥1ATR | Med t_ext (bars) |
|---|---|---|---|---|---|---|---|
| sweep inside | 3,081 | 0.944 [0.935, 0.951] | 0.781 | 4.56 | 5.43 | 0.870 | 29 |
| sweep far | 2,472 | 0.952 [0.948, 0.964] | 0.795 | 4.50 | 3.91 | 0.803 | 36 |
| displacement near | 4,060 | 0.904 [0.895, 0.913] | 0.729 | 4.17 | 5.53 | 0.917 | 27 |
| displacement far | 1,493 | 0.893 [0.884, 0.914] | 0.746 | 4.42 | 3.57 | 0.820 | 42 |
| fvg near | 2,829 | 0.978 [0.972, 0.983] | 0.885 | 6.73 | 3.51 | 0.938 | 48 |
| fvg far | 1,415 | 0.972 [0.962, 0.979] | 0.871 | 7.54 | 2.98 | 0.927 | 53 |
| trigger inside | 248 | 0.968 [0.938, 0.984] | 0.944 | 8.63 | 2.59 | 0.823 | 74 |
| trigger far | 15 | 1.000 [0.796, 1.000] | 1.000 | 9.07 | 1.47 | 0.733 | 47 |

Verdicts (frozen rule): **sweep does_not_separate** (CIs overlap);
displacement / fvg / trigger **insufficient_n** (inside cell empty or
far cell n = 15 < 30). **Overall: does_not_separate** (the one decisive
concept overlaps; the rest cannot run the contrast).

Reading the verdict honestly: the +1ATR-over-100-bars metric
**saturates** (~90–98% everywhere) — 100 M5 bars of XAUUSD travel
±several ATR in *both* directions almost always (median MAE 3–5.5
alongside median MFE 4–9; invalidation rates 73–94%). A hit-rate test
at this horizon cannot separate anything; the verdict answers the
pre-registered question correctly and narrowly. The texture worth
carrying forward (described, not verdict-shopped): the **adverse**
side differs by context where the favorable side does not — sweep
inside MAE 5.43/inv 87% vs far 3.91/80%; displacement near MAE
5.53/inv 92% vs far 3.57/82% — while +1ATR rates are flat. Named
follow-on (frozen then, not now): adverse-side separation at nearer
horizons with pre-registered rules.

## 5. Falsification checks (published regardless of outcome)

**(i) HTF-context separation:** answered by §4 — does_not_separate on
the frozen contrast (with the saturation caveat above, which is itself
a finding about horizon choice, not a rescue).

**(ii) Routed (n = 2) vs unrouted (n = 261) completions:** routed 2/2
+1ATR hits (CI [0.34, 1.0], med MFE 5.39) vs unrouted 253/261 (96.9%,
CI [0.94, 0.98], med MFE 8.71) → **insufficient_n** (routed n < 30 by
the frozen rule; values published). The unrouted median exceeding the
routed median at n = 2 is meaningless — stated so nobody misreads it.
Routing selects nothing measurable here, and nothing measurable
supports the opposite either.

**(iii) Fill rate by pillar/confluence/tp_source:** the 3 product fills
(all M8; pillar PASS:1+2+3+4+5 with inducement 1.0 / 0.7 / 0.7; tp
2×atr_fallback + 1×structural_swing; exits SL / TP / SL) →
**insufficient_n** (n = 3; published, not pooled). Phase C analogue
untestable (18 columns: no pillar_path, model_tags, tp_source, or
original_sl — stated, not faked).

## 6. Binding gates (requoted from product-6m logs — never recomputed)

35,725 M5 bars → 2,979 batches → 43,004 merged → pillars
(P2:fail 37,745 · P3:fail 2,031 · P1:fail 1,207 · PASS 2,021) → 30
armed (M8 28) → 501 scanned → 10 routes (F 9, C 1) → 4 placed
(+7 R9 intents armed → 3 placed → 0 expired) → 3 fills → 3 trades.
Blocked: session 4, far-from-zone 14. Costs $2.78 (spread 0.78 +
slippage 2.00; commission 0.00; swap deferred); net −2.7317 ledger.
Death-rate arithmetic: pillars kill 95.3% of merged (P2 = 87.8%);
98.0% of scans unrouted; 60% of routes unplaced; ≥25% of placements
unfilled. Sources: `results/product_6m_refresh_track_b/` summary +
run1 funnel_summary + report.json.

## 7. Limitations (binding on any reuse of this ledger)

- Event-weighted n (per-bar re-detections); unique-setup counts are a
  different (smaller) denominator, not computed here.
- Single 6m window, single instrument, single feed; M1-exec books are
  not in this ledger (M5 resolution throughout).
- Reference prices are midpoints for ranges (frozen); sweep singles
  exact; trigger entries exact.
- Commission $0.00 by ruling — any future cost-bearing rerun shifts
  net-side reads (of which there are none here: no PnL table exists
  in this report by design).
- The saturation finding (§4) constrains horizon choice for follow-on
  work; nearer-horizon contrasts must be frozen before running, not
  mined from these cells.
- No gate, no threshold, no live rule follows from any table here.

---

**Artifacts:** `06_RESEARCH/scripts/decomposed_6m_ledger.py` (new;
imports pack loaders + Track-B ATR, forks nothing) ·
`06_RESEARCH/results/decomposed_6m_ledger/` (`decomposed_events.csv`
16,281 rows × 24 columns, `summary.json` with manifest SHAs, frozen
params, cells, verdicts, binding requote) · tests
`04_SRC/tests/test_decomposed_ledger.py` (7: context trichotomy,
level parsing, Wilson properties, ATR excursion math, zone-fate
reads incl. precedence/truncation, hash stability, frozen params).
