# INDEPENDENT QUANT AUDIT — SMC BOT (WHOLE CODEBASE)

**Date:** 2026-10-08
**Auditor:** Independent quant reviewer (Buffy/Codebuff session). Not the author of the frozen strategy.
**Directive:** "Audit the entire codebase as an independent quant expert — what we got right vs what we got wrong, where to invest time going forward, where the idea / flowchart / implementation / execution still lag."
**Method:** Read the governance sources of truth (`LOCKED_DECISIONS.md`, `PRODUCT_RUNTIME_CONTRACT.md`, `POST_V1_PLAN_OF_ACTION.md`), the audit + phase + diagnosis reports in `06_RESEARCH/`, and the actual code. Where a report is dated, I re-verified the claim against the **current** working tree, because several findings were made in September and the code has moved since.

**Evidence labels:** `[F]` fact read from code/artifact · `[I]` inference · `[R]` recommendation.

---

## 0. Executive verdict

**Translation quality: high on process, low on economics — and the economics have never been tested with the tools that would settle them.**

- The **idea** (expert SMC: HTF POI → sweep → LTF confirm → plan → manage) is encoded faithfully and with unusual governance discipline. An independent audit (`INDEPENDENT_AUDIT_V1.md`) scored process-translation **7/10**, detection 8/10, validation 9/10, backtest honesty 9/10. I concur. `[F]`
- The **implementation** is genuinely strong engineering: 18,573 LOC in `smc/`, 96 test files (17,660 LOC), **917 tests green**, byte-identical dual-run determinism over 1.77M bars, no look-ahead found in two independent audits, locked constants isolated and config-guarded. `[F]`
- The **strategy** has never been shown to have positive expectancy. The frozen V1 5-year baseline is **761 trades, PF 0.344, 25.5% win-rate, net −4.78% equity**. `[F]`
- As executed, the "8 equal POI models × 6 triggers" flowchart collapses to **one pattern (Trigger F continuation) at ~87% of flow plus a Trigger B sidecar**; C/E/D are statistical ghosts and **M8 (the expert's *preferred* setup) was structurally silent in every baseline run until the recent product-runtime change**. `[F]`
- The binding economic problem is **entry selectivity/timing**, not the exit model: 62.5% of trades never reach +1R; honest full-SL median favorable excursion is **0.23R**; F stops sit inside noise (0.82×ATR, five pre-touches, mostly wick-tag deaths). `[F]`
- The **evaluation methodology is the largest open gap**: no walk-forward, no Monte Carlo, no bootstrap confidence intervals, **no commission/slippage/swap cost model** anywhere in the code, and the headline baseline ran on **M1 execution while the shipped product runs M5**. `[F]`

**Bottom line:** this is a very well-built measurement instrument attached to a strategy whose edge is not yet demonstrated. The next investment should be *statistical validity and entry selectivity*, not more features. `[R]`

---

## 1. What we got right (hold this)

1. **Fidelity of the locked process.** Stage 0A→4 implemented once; five pillars with `UNAVAILABLE ≠ pass`; strict one-touch state machine; base-candle swing validity; ATR-relative displacement; chronological first-valid trigger routing (§12). Verified in code and by the independent audit. `[F]`
2. **Determinism as a first-class contract.** Dual-run byte-identical `trades.csv`/`report.json` on 1.77M bars ×2; a perf refactor was proven semantics-preserving by a byte-identical golden re-run. This is rare and valuable. `[F]`
3. **Look-ahead discipline.** Two audits found **no look-ahead in the decision path**; the only residuals are conservative (touch=fill at limit, SL-first same-bar) and one convention-defended suffix (`Pillar-1 _mitigated` reads `candles[active_index+1:]`, safe only because every call site trims to `as_of`). `[F]`
4. **Conservative fill model.** Fill at the limit price (no optimistic improvement), no partials, same-bar SL wins. Biases *against* the system — good for honesty. `[F]`
5. **Honest, self-critical research culture.** The project's own reports disclose the worst facts first (Phase C §10 anomalies; "diagnostic only, NOT edge" on every artifact). The chief bias channel (prompt-led threshold creep) was identified and is defended by standing bans. `[F]`
6. **Governance.** Locked constants in one module; the config loader loudly rejects attempts to override them; dated rulings; `locked_constants.py` diff empty across the whole accepted chain. `[F]`
7. **Ops layer is real.** Heartbeat + MQL5 watchdog contract mirrored and tested; identity-gated binding; operator pack; live order drill proven on the broker (place/cancel/SL-modify-preserves-TP/close, no slippage observed on 0.01 lots). Recent heartbeat/atomic-replace hardening is in place. `[F]`
8. **Recent structural improvements.** Structural TP feed (`resolve_take_profit` + `structural_tp_target`), M8 HTF provisioning via `MultiTFProductRuntime`, W1 context tier, export identity patch (`model_tags`, `pillar_path`, `disp_magnitude_atr`) — these closed several V1 holes. `[F]`

---

## 2. What we got wrong / still open (with evidence)

Severity: **C** critical to the thesis · **M** major · **m** minor.

### C1 — No demonstrated edge, and the entry side is the bottleneck (not exits)
- Baseline: 761 trades, PF 0.344, WR 25.49%, net −47.81 raw (−4.78% equity). `[F]`
- R1: median MFE **0.55R** (Phase C) / **0.23R** on honest full-SL denominators; **37.5%→17.1%** reach 1R depending on denominator; **62.5% never reach 1R**; median MAE 1.73R. `[F]`
- R2: fixed take-profits at 1.5R/2R/3R yield PF 0.011 / 0.0032 / 0.0006 — strictly worse than the BE-only baseline. **Exits are not the fix.** `[F]`
- R3/R4: 29% instant stops (zero favor) + 33% no-follow-through = 62% of trades produce ~140% of the net loss; F is 86.6% of flow with sub-ATR stops (0.72–0.85×ATR). `[F]`
- **Reading:** the pipeline is a good *detector* and a poor *entry-timer*. `[I]`

### C2 — Evaluation methodology is incomplete (no OOS, no confidence, no costs)
- **No walk-forward / Monte Carlo / bootstrap anywhere** — `grep` over `04_SRC/smc` and `06_RESEARCH/scripts` finds zero implementations. Phase E (WF/MC) is unstarted. `[F]`
- **No commission, slippage, or swap model in code.** The only cost lever is the §28.5 spread *gate* (a binary block, not a per-fill charge), and it ships `spread_price=0.0` in every baseline. Fills occur at the exact limit price. So the baseline is effectively **zero-cost**. `[F]`
- **Baseline config ran M1 execution** (`timeframe: M1` in Phase B/C configs); the shipped product runs **M5**. The headline 761-trade number is therefore **not** the product's own configuration. `[F]`
- Single instrument (XAUUSD), single 5-year window, one broker feed; the Phase C run is segmented with a **ruled-and-documented boundary limitation** (no continuous-run identity; 0 dropped positions but no cross-segment state carry). `[F]`
- No benchmark (buy-&-hold XAU, random entry, naive breakout). `[F]`
- **Consequence:** no number in the repo currently supports or refutes the concept with statistical confidence. `[I]`

### C3 — Flowchart breadth is theoretical; one pattern is the product
- Trigger share (Phase C): **F 659 / B 70 / A 29 / E 2 / C 1 / D 0**. Three of six triggers statistically absent. `[F]`
- **Trigger D is structurally unfireable**: the dataset's `volume` is 0 on every M1 row (and every tick row), so `engulfer.volume < engulfed.volume` is never true. Ruled option (a): run without D. `[F]`
- **M8 (the expert's preferred M8+Ending-Diagonal setup) emitted nothing in every baseline** — no HTF feed in the runners. Now fixed in the product runtime (`MultiTFProductRuntime` forwards D1/H4/W1 to M8), but **no fresh baseline has been run** to measure M8's contribution. `[F]`
- So "8 equal models / confluence scoring" is, in the data, a **single-pattern system** with a slow B tail. `[F]`

### M4 — Spread-grade scale mismatch (independent-audit finding, STILL PRESENT)
- `score_poi` returns `score = tag_count + M8 bonus` → **1, 2, 3, … up to 8**. `[F]`
- `SPREAD_GRADE_SCORE_THRESHOLDS = {"A+": 8, "A": 5, "B": 3, "C": 0}` — a **0–10 quality scale**. `[F]`
- Result: a 1–2 tag POI grades **C**, 3–4 grades **B**; **A and A+ tolerance are effectively unreachable** in practice. The gate is stricter than the design intends, so every spread-sensitivity conclusion is shifted down a tier. `[F]`
- This is the same bug the 2026-09-19 independent audit flagged (finding #2); it remains unfixed ~3 weeks later. `[F]`

### M5 — Risk sizing is inert because the lot cap binds
- `LOT_MAX_SAFETY = 0.10`; Phase C §10.1 records **all 761 trades at 0.10 lots** — the cap binds 100%, so the §28.7 risk-percent band (0.5–1.0%) never actually scales. Every "risk-normalized" read of the book is cap-contaminated. `[F]`
- Still true today (`LOT_MAX_SAFETY` unchanged). `[F]`

### M6 — F entries are late/chase, and stops sit inside noise
- `STOP_VS_STRUCTURE_NOTES`: F stops median **0.82×ATR**, **5 pre-touches**, **35/64 deaths by wick-tag** (price stabs through then closes back) vs 29 close-through breaks. `[F]`
- F entries are **never inside their recorded zones (0/64)** — consistent with chase entries. `[F]`
- `F_TIMING`: 65% `late_chase` (median MFE **0.00–0.23R**, 12.5–26% ≥1R) vs `mid_move` (**1.05–1.51R**, 58–62.5% ≥1R). Chase-vs-rest separation survives two independent labelings. `[F]`
- **This is the single most promising, most actionable signal in the building** — and it is explicitly *not* licensed as a gate yet (correctly, small-n/single-regime). `[F]`

### M7 — Funnel selectivity is INDETERMINATE
- Pillar 2 does ~75% of the killing; **91% of Pillar-2 kills lack FVG**; magnitude tiers (0.5/1.0 ATR) do **not** separate outcomes (hard-fail 57.7% vs twilight 52.7–54.9% reach 1R). `[F]`
- Killed zones move too much to call junk (under generous hypothetical stops) and admitted entries die too fast to call the funnel selective. Whether FVG-absence predicts failure is **untested**. `[F]`

### M8 — Version-control / durability (repo hygiene, not strategy)
- The working tree holds a large uncommitted body: **~50 untracked files and 42 modified tracked files**, including the core **`04_SRC/smc/data/` connector package**, `heartbeat_path.py`, and several live modules. The prior audit's MAJOR finding. `[F]`
- **Recommendation:** commit the code (src + tests + governance) so the audit trail is durable; the tree currently has no committed baseline for the connector. `[R]`

### m9 — Data limitations
- **Spread absent from the M1 series** (must be reconstructed from the 12.9 GB tick file; live spread is a constant 0.26 in sampled windows). `[F]`
- Volume all-zero → Trigger D dead, and any volume-based confirmation is unavailable. `[F]`
- 1,679 gaps, all classified (weekend/holiday/rollover-hour) — acceptable, but session-window logic must count bars, not wall-clock. `[F]`

### m10 — Reported headline vs product config drift
- The 6-month "new contract" funnel (30 armed / 10 routes / 3 fills / net −3.2117) is the closest thing to a product-config measurement, but n=3 and it still uses the frozen config; the 5-year baseline is M1. There is **no single 5-year M5 product-config baseline**. `[F]`

---

## 3. Scorecard (idea → flowchart → implementation → execution)

| Layer | Score | One-line |
|---|---:|---|
| Idea (expert SMC process) | 8/10 | Coherent, internally consistent, expert-backed; economic content unproven. |
| Flowchart fidelity (as coded) | 8/10 | Stages faithful; breadth collapses to F+B in practice; M8 silent in baselines. |
| Implementation (engineering) | 9/10 | Deterministic, tested (917), honest, well-governed; missing quant infra + spread-grade bug. |
| Quant methodology | 4/10 | No OOS/WF/MC/CI, no costs, one instrument, one window, no benchmark. |
| Edge evidence | 2/10 | Negative baseline; no configuration shown positive; entry side is the bottleneck. |
| Live/execution readiness (ops) | 7/10 | Identity/heartbeat/watchdog/order-drill proven; no 2-week unattended run; demo P/L ≠ validation. |
| Overall idea→money translation | **5/10** | A strong research instrument, not yet a validated strategy. |

---

## 4. Where the idea / flowchart / implementation / execution still lag

- **Idea lag:** the concept's *entry timing + selectivity* is the unproven core. The expert rules encode *where* the zone is and *what* confirms it, but the data says the system enters late (chase) and gets tagged by noise. That gap is inside the idea's translation, not outside it.
- **Flowchart lag:** the intended breadth (8 models, 6 triggers, multi-TF confluence, M8 preferred setup) is not exercised by the data. Until M8 is measured and non-F triggers produce n, the flowchart is aspiration, not evidence.
- **Implementation lag:** no statistical-validation harness (WF/MC/CI), no cost model, the spread-grade scale bug, and an inert lot cap. These are the things that would let you *trust* any result.
- **Execution lag:** live stack works, but the only real deliverable (backtest-vs-live divergence + slippage/spread measurement over a sustained window) is incomplete; the baseline was never re-run on the shipped M5 config with costs on.

---

## 5. Where to invest time going forward (prioritized)

**Tier 1 — do these first (they change the information content of everything else).**

1. **Build the confidence harness (Phase E): walk-forward + block bootstrap + Monte Carlo.** No strategy decision should be made until per-trigger expectancy has a confidence interval and an OOS split. Cheap relative to its value; the backtest harness already exists. `[R]`
2. **Add a real cost model: commission + slippage + swap, charged per fill** (not just the spread gate). Re-run the baseline with realistic XAUUSD costs and the reconstructed tick spread series. If the book is negative *before* costs, costs alone won't fix it — but until costs exist, no positive claim is credible either. `[R]`
3. **Fix (or formally re-rule) the spread-grade scale mismatch.** Either map §28.5 thresholds onto the tag-count scale or feed a true 0–10 quality score. One-hour fix, needs a dated ruling. `[R]`
4. **Produce ONE clean 5-year baseline on the shipped product config (M5 execution, M8 provisioned, structural TP).** The current headline is M1 and pre-M8. Everything downstream should reference the product's own config. `[R]`
5. **Commit the code.** Durable artifacts; the connector has no committed baseline. `[R]`

**Tier 2 — the strategy research that actually matters.**

6. **Entry-selectivity program on the F book (87% of flow).** The F-timing axis (chase vs mid-move vs swing-anchored pullback) already shows separation on honest R. Build a **swing-anchored pullback/anti-chase discriminator** as a research label, then test it walk-forward on the frozen book — demand ≥100 trades/family, ≥2 ATR regimes, CI excluding zero before it ever becomes a gate. `[R]`
7. **Stop-placement counterfactual study.** F stops die by wick-tag inside noise (0.82×ATR, 5 pre-touches). Measure, as pure observation, whether a band-aware stop outside the pre-touched range converts wick-tag deaths — but keep it a *measurement*; R2 warned stop widening is entry/redesign territory requiring a ruling. `[R]`
8. **M8 measurement.** With M8 now fed, quantify its independent contribution (does M8+Ending-Diagonal beat the F-only book?). This is the expert's preferred setup and has never been measured. `[R]`
9. **Funnel selectivity question, answered properly:** does FVG-absence predict failure? (admitted-FVG rate vs kill-FVG rate on export-patched re-runs). Currently untestable for lack of the split. `[R]`

**Tier 3 — supporting.**

10. **Benchmarks:** buy-&-hold XAU, random-entry-with-same-exit, naive BOS entry — cheap, and they calibrate what "PF 0.344" even means. `[R]`
11. **Re-express results in risk-normalized R** now that `original_sl` is exported, so the inert lot cap stops contaminating every metric. `[R]`
12. **Consider the timeframe question:** is the concept structurally an M1-entry idea or an M5 one? The baseline and the product disagree. Decide and freeze. `[R]`
13. **Data upgrade:** a volume-bearing feed (resurrect Trigger D) and a tick-derived spread series (cost realism). `[R]`
14. **Ops:** finish the ≥2-week unattended demo report with slippage/spread divergence logging; keep demo P/L strictly out of the idea-validation loop. `[R]`

**Explicit non-goals until Tier 1–2 land:** no new POI models/triggers, no threshold tuning, no live capital, no Mode B implementation, no treating demo P/L as edge, no M1/M5 window shopping. `[R]`

---

## 6. The honest one-line answers

- **What we got right:** an unusually faithful, deterministic, honestly-documented implementation of the SMC process, with excellent governance and a working live ops layer.
- **What we got wrong:** we built a great detector and never proved the entry timer or the economics — no OOS/CI/MC, no costs, one instrument, M1-vs-M5 drift, an unreachable spread-grade tier, an inert lot cap, and a flowchart that runs as one pattern.
- **Where we still lag:** statistical validity (OOS + confidence + costs) and entry selectivity (F chase/timing). Fix those two and the concept finally gets a fair test; skip them and every future number remains uninterpretable.
- **Highest-information single action:** add the confidence harness *and* a cost model, then re-run ONE clean 5-year M5 product-config baseline and read it against benchmarks. `[R]`

---

## 7. Provenance / caveats

- All numbers above are quoted from the project's own artifacts, or re-verified in the current working tree. Where a report is dated (2026-09-19/20), I flagged the ones already fixed (TP, M8 provisioning) and the ones still present (spread-grade scale, lot cap, no WF/MC/costs, M1 baseline).
- This audit changes no code, no constants, and no strategy logic — measurement and opinion only. `locked_constants.py` was not touched.
- Independence caveat: this is the same agent session that has touched the operator/live surface recently; the strategy-relevant findings are nevertheless grounded in artifacts and `grep`-reproducible code reads, and every claim is cited to a file or artifact so it can be re-verified in a fresh session.

---

```
AUDIT_STATUS: PASS_WITH_CAVEATS
SCOPE: whole codebase + reports
EDGE_EVIDENCE: NEGATIVE (no configuration shown positive; entry side is the bottleneck)
ENGINEERING: STRONG (917 tests, deterministic, no look-ahead found, well-governed)
BIGGEST_GAPS: [1. no OOS/WF/MC/bootstrap; 2. no commission/slippage/swap cost model; 3. baseline is M1 while product is M5; 4. spread-grade scale mismatch (still open); 5. inert lot cap (0.10 binds 100%); 6. flowchart collapses to Trigger F (87%); 7. M8 unmeasured]
CORRECT: detection fidelity, determinism, conservative fills, look-ahead discipline, governance, ops layer
OPEN_DEFECTS: M4 spread-grade scale, M5 lot cap, m9 data (volume/spread), m10 M1-vs-M5 drift
INVEST_NOW: [confidence harness (WF/bootstrap/MC) + cost model -> one clean 5y M5 baseline; fix spread-grade scale; commit code; then F entry-selectivity program; then M8 + benchmark measurement]
REPORT_PATH: 06_RESEARCH/QUANT_AUDIT_2026-10-08.md
LOGIC_CHANGED: NO
```
