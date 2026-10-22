# ESSENCE v1 — W0 RULINGS (one-pager)

**Banner: ESSENCE V1 SLICE — NOT FULL COMPLEX REWRITE**

**Date:** 2026-10-21 · **Authority:** Owner Salman sign-off 2026-10-21
(`00_LOCKED/ESSENCE_CONTRACT_V1.md`) + Architect rulings in this leg.
**Source list:** `06_RESEARCH/ESSENCE_V1_CODE_MAPPING.md` — REQUIRED FOLLOW-UP
edits F1–F12. Each ruling is dated and explicit; nothing is resolved silently.

| # | Follow-up (from mapping) | Ruling 2026-10-21 | Status | Where recorded |
|---|---|---|---|---|
| F1 | M1 execution timeframe vs `PRODUCT_RUNTIME_CONTRACT` §1 | **DONE** — runtime contract amended: the "no M1-exec product" line is **superseded for the essence path only**; COMPLEX V1.1 stays M5-oriented and frozen | **RULED** | `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` §10 (dated amendment) |
| F2 | Resting window: signed 12 bars vs §23-per-TF (M1 = 30) vs R8 (48) | **DONE — per-TF frozen value stands:** the essence LIMIT rests `M1_EXPIRY_BARS = 30` M1 bars (the §23 per-execution-TF rule, exactly as the contract §4 note states); R8 interaction n/a in the slice (no seek/route stack in essence) | **RULED** | essence wiring (constant imported, not re-declared); contract §4 note |
| F3 | SL: replace "structure + 0.3×ATR" with the 2–5 pip band on the essence route | **DONE — essence-only stop:** essence computes its own stop from the ED terminal wick ± the band floor (`M8_SL_MIN_PIPS` = 2.0 pips); the 0.3×ATR rule was **never touched** (it is interim FR-2 code owned by the triggers, still frozen for COMPLEX) | **RULED** | `smc/essence/rules.py :: essence_stop` |
| F4 | TP: feed a macro/HTF target and add the hard 1:5 gate | **DONE — essence-only target source:** target = the near edge of the nearest ACTIVE opposite-direction HTF zone strictly beyond the entry; no target → blocked (`missing_target`); RR < 5.0 → blocked (`rr_below_1x5`); never downgraded. The 4×ATR fallback is untouched (COMPLEX keeps it). | **RULED** | `smc/essence/rules.py :: essence_target / rr_gate_ok`; note funnel |
| F5 | Confirm allow-list (set C; B and E excluded) | **DONE — allow-list wired:** `ESSENCE_CONFIRM_KINDS = ("c_ending_diagonal",)`. Only the §15-preferred ending diagonal completes essence entries in this slice; the signed alternates F/D/A remain in the set **on the page** but are unwired (residual); B/E can never fire. DUMB's mid-reclaim is not in the list. | **RULED (partial by design)** | `smc/essence/constants.py`; set-C allow-list test |
| F6 | Zone-sweep verdict + Pillar-2 coupling decision | **DONE (verdict) / N-A (coupling):** the essence path implements the contract §2 verdict at the zone level (wick beyond the level extreme + close back inside; close-through = breakout). There is **no pillar coupling in essence** — the pillars are not run at all (contract §7 removes them as vetoes), so the shipped sweep→displacement veto is untouched for COMPLEX | **RULED** | `smc/essence/rules.py :: is_zone_sweep / is_zone_violation` |
| F7 | Pillar relaxation (contract §7) | **DONE (by construction):** essence runs zero pillars — no relaxation flag needed; COMPLEX pillars remain untouched. | **RULED** | essence runner (no validation stack) |
| F8 | FVG invalidation: keep in v1 (put on §6 page) or scope out | **DONE — scoped out of the v1 slice:** essence has no FVG-invalidation exit; the position runs to its target or the trailing bands per §6. The COMPLEX `risk_engine` branch is untouched. The §6 page txt is unchanged (its claims are about the signed rule set, not this diagnostic slice). | **RULED (slice)** | essence runner (no such branch); residual noted |
| F9 | Risk/environment layer disclosure (session, breaker, guards, spread, sizing, Friday) | **PARTIAL — sliced:** the essence path implements **none** of the risk/environment layer (contract §7 keeps it off v1; the expert lens is the stage rubric, not ops realism). Each STACKED-for-COMPLEX rule remains where it was. The slice note lists "risk layer absent" as a declared residual so nothing is scored that was silently blocked. | **PARTIAL (declared residual)** | `06_RESEARCH/ESSENCE_V1_SLICE_NOTE.md` residuals |
| F10 | News guard: in or out of v1 | **DONE — out:** essence does not gate on news; the shipped §11 news guard for COMPLEX is untouched and stays `news_events=[]` dormant per the runtime contract §8. | **RULED (slice)** | essence runner |
| F11 | H1 level geometry (M8 does not scan H1) | **NOT RULED — residual carried:** the essence level set is M8's own W1/D1/H4; H1 stays unsigned-in-code until either an H1 M8 emitter is ruled or the level set is narrowed by amendment. Recorded, not silently closed. | **OPEN (residual)** | slice note residuals; mapping F11 |
| F12 | Trigger D: volume-free variant, or drop | **NOT RULED — carried into a later leg:** the volume-dependent two-bar pair is OUT of v1 (contract Appendix B) because the feed has no volume AND because D is unwired in the essence slice anyway. Whether a volume-free D variant joins set C is a dated owner question, not needed for the slice. | **OPEN (residual, not slice-blocking)** | slice note residuals; mapping F12 |

## Explicit exclusions carried (every leg re-states them)

* **Fallback boundary-sweep family = OUT of the v1 build** (signed "include
  later") — it enters only by a dated amendment and a new emitter; there is no
  `demand_supply_boundary`/`order_block_boundary` scan in the essence path.
* **DUMB's mid-reclaim is not confirm set C** — the essence confirm allow-list
  names patterns by their Trigger letter; the mid-cross rule is in no allow-list
  and can never complete an essence entry.
* **No COMPLEX default is "fixed" silent** — every COMPLEX threshold, branch,
  and behaviour used/mentioned in this engagement is untouched; the essence
  path is a parallel package with read-only reuse only.
* **No PF optimisation, no edge claim** anywhere in this engagement.

## Return block

```
W0_RULINGS_STATUS: DONE (F1-F8, F10 ruled; F9 partial-by-slice-declaration; F11/F12 open residuals, carried)
F1_RESULT: PASS (PRODUCT_RUNTIME_CONTRACT.md §10 amendment, dated 2026-10-21)
RUNTIME_AMENDMENT_SCOPE: essence path only (parallel package); COMPLEX baseline untouched (M5, frozen, b5e8c53)
NEXT_READY: essence implement leg already executed in this engagement (W1-W5 in ESSENCE_V1_SLICE_NOTE.md)
```
