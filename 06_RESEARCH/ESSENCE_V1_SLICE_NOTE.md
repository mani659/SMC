# ESSENCE CONTRACT V1 — SLICE NOTE (W1–W5 implemented; diagnostic)

**Banner: ESSENCE V1 SLICE — NOT FULL COMPLEX REWRITE**

**Date:** 2026-10-21 · **Authority:** Owner Salman sign-off 2026-10-21
(`00_LOCKED/ESSENCE_CONTRACT_V1.md`, SIGNED) + Architect F1 ruling recorded in
`00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` §10 · **W0 rulings:**
`06_RESEARCH/ESSENCE_V1_W0_RULINGS.md` (F1–F12: 9 ruled, 3 carried as
residuals) · **Mapping:** `06_RESEARCH/ESSENCE_V1_CODE_MAPPING.md`.

**Scope of this engagement:** the smallest vertical slice that **opens and
manages one trade type** under the signed rules for expert weekly stage
scoring — as a PARALLEL product path in a new `04_SRC/smc/essence/**` package.
**COMPLEX is untouched** (no file in `smc/**` outside `smc/essence/**` changed;
the frozen comparison point stays at `00_LOCKED/BASELINE_COMPLEX_V1_1_COMPARISON_POINT.md`,
`b5e8c53`). **No PF optimisation, no edge claim anywhere**; PnL below is
book-internal price units, **DIAGNOSTIC ONLY**.

---

## 1. What ships (the code)

| Package file | Contents (signed stage served) |
|---|---|
| `smc/essence/constants.py` | The signed numbers **wired, not re-declared**: `M8_SL_MIN/MAX_PIPS` (2.0/5.0) · `M8_MIN_RR` (5.0) · `M1_EXPIRY_BARS` (30) · `PURE_RUNNER_BE_ATR/BUFFER` (1.0/0.10) · `TRIGGER_C_EXPIRY_EXTRA` (3) · `ZONE_REFINEMENT_ATR` (0.5 band) — all imported from `locked_constants`, which is **UNCHANGED** (an isolation test pins the six values). Essence-owned only: ATR period 14 and the confirm **allow-list**. |
| `smc/essence/rules.py` | Pure signed-stage rules: **§2** `is_zone_sweep` (wick beyond the level extreme + body close back inside; close-through = `is_zone_violation`, never a sweep) · **§3** set-C allow-list (`ESSENCE_CONFIRM_KINDS = ("c_ending_diagonal",)`) + `find_ed_confirm` — a read-only port of the shipped Trigger C semantics (`wave_structure.find_ending_diagonal` + frozen terminal-expiry 3 + the frozen §13 zone band + the first-reclaim-close rule) on the M1 series · **§5** `essence_stop` (terminal wick ± band floor = 2.0 pips) · **§6** `essence_target` (near edge of the nearest ACTIVE **opposite-direction** HTF zone beyond the entry; none → blocked) + `risk_reward`/`rr_gate_ok` (hard 1:5, `M8_MIN_RR`). |
| `smc/essence/runner.py` | The bar loop over **native M1** with the two feeds: `EssenceZoneFeed` (read-only honest-prefix reuse of the product's `M8HtfDemandSupply` — same pattern as the accepted DUMB feed, supersession retires + reports removals) and per-zone state `UNSWEPT → SWEPT → CONFIRMED → LIMIT RESTING → OPEN → closed`. Limit fill + exits via the **locked conservative fill model** (`limit_filled` = touch, fill price = the limit, same-bar SL+*anything* → SL wins). BE via the **locked `PureRunner`** §28.1 with the per-trade latch. |
| `smc/essence/types.py` | `EssenceTrade` — the full expert-scoring identity (zone+TF / sweep ts+extreme / confirm kind+boundary+terminal / entry LIMIT level+ts / stop pips / target ref+RR / BE flag / exit). |
| `04_SRC/tests/test_essence_v1_slice.py` | 24 tests: RFC-notes §2 sweep/breakout both directions · set-C allow-list (B/E can never fire) · constant wiring parity with the lock · ED confirm (first-reclaim / band / stale-terminal / earlier-reclaim) · SL band math · target selection + hard gate · the full one-trade integration on a hand-built 5-swing M1 path (sweep → confirm → LIMIT fill → BE → stop at the BE level) · same-bar entry+SL → SL wins · BE never rescues its own bar · 30-bar limit expiry · breakout cancel · determinism · **isolation battery** (no essence reference outside `essence/**`, no essence names in `locked_constants.py`, no `smc.dumb` import from essence, COMPLEX smoke import). |

**Stage coverage = exact signed picks:** entry TF **A (M1)** ✓ wired (native M1
series, M1 ATR(14), M1 N=3 swings §27-causal) · LIMIT style inside the zone ✓ ·
confirm set **C** primary (ending diagonal) ✓ wired; F/D/A alternates remain in
the signed set on the page but are **unwired in this slice** (declared
residual; B/E excluded by the allow-list test) · SL **B** (2–5 pips beyond the
M1 structure — the wave-5 terminal wick) ✓ · TP **D** (macro HTF target, hard
1:5 gate — trades are **blocked**, never downgraded) ✓ · PureRunner BE **ON**
1.0 × ATR, 100 % runner ✓ · fallback sweep family **OUT** ✓ (no such scan
exists in essence) · DUMB mid-reclaim ≠ confirm ✓ (not in any allow-list).
Pillars/news/risk layer/session/route stacks: **none run** in essence (§7 keep
them out of v1; declared residuals, not silent).

## 2. Fidelity interpretation choices (disclosed, each is a residual unless later ruled)

1. **Zone-level sweep.** The contract §2 sweep ("wick pierces the level and
   the candle closes back inside") is applied to the **HTF zone itself** (the
   signed level of §1) — the same zone-level transposition the accepted DUMB
   design used. The locked liquidity-level sweep families remain untouched.
2. **Sweep bar = anchor, confirm ≤ 3 M1 bars after the throw** (frozen
   Trigger-C `TRIGGER_C_EXPIRY_EXTRA`), with the setup-level window = the frozen
   `M1_EXPIRY_BARS` (30, the §23 per-TF rule the contract's note states).
3. **Swing causality:** M1 swings are precomputed once by the product's
   `detect_swings` (frozen §27 N=3) and a swing is eligible only from
   `base_index + N`; the per-scan view is capped to the most recent 120 swings
   (provably identical for the backward alternating-chain walk — perf fix
   only, no semantic change).
4. **Conservative same-bar ordering:** exits evaluate with the current bracket
   BEFORE the BE probe each bar (no same-bar rescue), and the fill bar itself
   is subject to the locked same-bar SL-wins rule.
5. **Target source:** nearest active opposite-direction M8 zone edge beyond
   the entry. This is the slice's macro-target stand-in; the operator's
   first-swing rule stays PENDING and unfed in COMPLEX, untouched.
6. **One trade per zone, ever** (§0 anti-spray): a zone busy with a resting
   open/trade skips new sweeps; re-sweeps re-anchor only a live pending setup.

## 3. W1 — the M1 dry-read answer (counts only, diagnostic)

The frozen-window capture IS the W1 evidence run plus the full slice: the M1
series loads natively from parquet, honest-prefix M8 zones re-scan, and
**ending diagonals DO appear on M8 zones on M1** —

```
ESSENCE_V1_SLICE — DIAGNOSTIC FUNNEL, W3 (load 2025-05-01, exec 2025-06-01 → 2025-11-30)
M1 bars 210,068 · HTF rescans 1,163 · zones activated 957 (superseded 941)
swept 61,422 → breakout-invalidated 50,861 · confirmed-expired 10,508
→ ED CONFIRMED 51 (all c_ending_diagonal)
   entry skipped outside zone 2 (§4 gate)
   blocked: missing target 6 · RR below 1:5 34 (§6 hard gate — 71 % of
        confirmations could not reach 1:5; the gate visibly binds)
   LIMIT placed 9
      limit expired (30 M1 bars unfilled) 1 · breakout-cancelled 1
      FILLED 7 → BE moves 3 (PureRunner §28.1 fired per-trade)
      exits: stop_loss 7 (take_profit 0 · end_of_data 0)
   TRADES 7 (H 5 / S 2 — all H4 zones; by kind: demand_supply 4 · ob 1 · fvg 2)
Book-internal PnL sum: −4.58 price units — DIAGNOSTIC ONLY, no edge claim.
```

* **Determinism:** run1 = run2 **byte-identical** on `trades.csv`
  (md5 `27f326a823e6c89b5623c391dbfee50c`); recorded in
  `results/essence_v1_slice/determinism.json`.
* **Scale note:** COMPLEX's same-window baseline is 58 fills from >558 armed;
  essence's signed rule set admits **7 trades** — the scarcity lives in the
  signed contract itself (M1 ED confirms + the 1:5 gate), not in hidden gates.
  The two books are **different trade definitions** — no horse-race (DUMB
  audit §6 comparison rules apply).
* **Expert-scoreable identity exported:** zone+TF, sweep ts/extreme, confirm
  kind/boundary/terminal, entry level/ts (TF=M1), stop pips, target ref+planned
  RR, BE flag, exit — every §8 stage is answerable per trade.

## 4. What is NOT in the slice (stage-complete residuals, carried)

| Residual | From | Status |
|---|---|---|
| H1 as a level TF | mapping F11 | OPEN — M8 has no H1 emitter; essence level set = M8's W1/D1/H4 |
| Alternates F/D/A wired into the confirm path | mapping F5 (partial by design) | OPEN — page stays ahead of the slice; alternates join by a dated leg |
| Volume-free Trigger D variant | mapping F12 | OPEN — owner question, not slice-blocking |
| Risk/environment layer (session, breaker, guards, spread, sizing, Friday) | mapping F9 | DECLARED absent in essence (§7 keeps it out of v1) |
| FVG invalidation exit | mapping F8 | Scoped OUT of the slice; COMPLEX branch untouched |
| News gating | mapping F10 | OUT of the slice; shipped COMPLEX guard untouched/dormant |
| Broker realism (spread/slippage/costs) | this leg | PnL is book-internal, costs 0 — diagnostic only |
| Rider: W2 window repetition | this leg | W3 only (6m); W1/W2/W4 captures are a separate cheap leg |

## 5. Governance & verification

* **Runtime amendment:** `00_LOCKED/PRODUCT_RUNTIME_CONTRACT.md` §10
  (2026-10-21) — M1 execution for the essence path ONLY; COMPLEX V1.1 stays
  M5-oriented and frozen (`b5e8c53`).
* **W0 rulings:** `06_RESEARCH/ESSENCE_V1_W0_RULINGS.md` — F1–F8 + F10 ruled;
  F9 partial-by-declaration; F11/F12 open residuals; the fallback family and
  the DUMB mid-reclaim ban re-stated.
* **Suite:** `cd 04_SRC && python -m pytest tests -q` → **1279 passed
  (EXIT=0)** = the 1255 baseline + 24 essence tests — COMPLEX baseline intact.
* **`locked_constants.py`: diff EMPTY** — the six signed values the wiring
  relies on are asserted by an isolation test; nothing added, nothing edited.
* **Capture artifacts (gitignored policy):**
  `06_RESEARCH/results/essence_v1_slice/W3/run{1,2}/trades.csv` +
  `run_meta.json`, `W3/summary.json`, `determinism.json`;
  script `06_RESEARCH/scripts/essence_v1_slice_capture.py`.

## Return block

```
ESSENCE_SLICE_STATUS: PASS (slice complete end-to-end; diagnostic only)
W0_DOCS: PASS (runtime amendment §10 + W0 rulings; F11/F12 carried open)
W1_M1_DRY: PASS — M1 series loads natively, M8 zones re-scan on M1 cadence, ED confirms exist: 51 on the frozen 6m window
W2_SET_C: PASS — allow-list wired (ED only); B/E can never fire (unit-pinned)
W3_ZONE_SWEEP: PASS — §2 verdict at zone level, wick+close-back; close-through = breakout (tests both directions)
W4_MONEY: PASS — SL 2–5 pip band (floor 2.0 wired), macro target + hard 1:5 gate (blocked, never downgraded), PureRunner BE 1.0×ATR ON with per-trade latch
W5_OPEN_MANAGE: PASS — 7 trades opened and managed end-to-end on M1 (LIMIT touch fills, same-bar SL-wins, BE on 3, exits via the locked fill model)
N_TRADES_DIAGNOSTIC: 7 (all H4 zones; 5 LONG / 2 SHORT; exits 7 stop_loss, 3 with BE applied; book-internal PnL −4.58 price units — DIAGNOSTIC ONLY)
SUITE: 1279 passed (1255 baseline + 24 essence; EXIT=0)
COMPLEX_BASELINE_INTACT: YES (no file outside smc/essence changed; frozen point b5e8c53)
LOCKED_CONSTANTS_DIFF: empty (values wired read-only; wiring asserted by test)
NOTE_PATH: 06_RESEARCH/ESSENCE_V1_SLICE_NOTE.md
NEXT_READY: Expert paper week (score the 7-trade sample with the §8 rubric) | residual gaps list (H1 emitter, F/D/A wiring, volume-free D, risk-layer decision)
```
