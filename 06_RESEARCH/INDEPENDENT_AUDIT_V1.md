# INDEPENDENT AUDIT — SMC BOT V1
**Implementation Fidelity + Quant Shortcomings + Forward Plan**
*Auditor independent of the implementation. Evidence-cited; fact / inference / recommendation labeled. Date: 2026-09-19.*

Sources inspected: `00_LOCKED/LOCKED_DECISIONS.md` (full read), `POST_V1_PLAN_OF_ACTION.md`, `SESSION_HANDOFF.md`, `CHANGELOG.md` (headers + closeouts), `SMC_R1_STRUCTURAL_MODEL_SPECIFICATIONS.md` (targeted), full `04_SRC/smc/` tree (~16k LOC across 14 packages), key modules read: `backtest/fill_model.py`, `backtest/runner.py` (fill/exit seams), `triggers/trigger_router.py`, `triggers/trigger_f_bos_ob.py`, `validation/validation_pipeline.py` + `pillar_3_premium_discount.py`, `detection/displacement_checker.py` (docstring + constants), `poi/confluence_scorer.py`, `risk/risk_engine.py` (gate order), `risk/pure_runner.py`, `risk/spread_grading.py`, `execution/lot_sizing.py`, `live/loop.py`, `paper/kpi_logger.py`, `config/locked_constants.py` (key constants). Research: `PHASE_B_FIDELITY_REPORT.md`, `PHASE_C_BASELINE_REPORT.md` (incl. §10 anomalies), `PROJECT_WIDE_AUDIT.md`, `PHASE_D_DIVERGENCES.md`, `phase_c_gate_regime_check.json`, per-trigger decomposition recomputed from `phase_c_baseline_run1/merged/trades.csv` (761 rows). `DEVELOPMENT_PLAN.md` skimmed via grep only (architecture sections not line-read) — noted per rules. No source was invented; gaps are flagged where they exist.

---

## A. Executive verdict

**Translation: strong on mechanism, weak on economics.** The pipeline faithfully encodes the locked SMC process — Stage 0/0b/1/1b/2/3/4, five-pillar hard gates with UNAVAILABLE-as-fail, chronological trigger routing, strict freshness, base-candle swing validity, ATR-relative displacement. But the exit leg of the strategy was never specified, and the code honestly reflects that hole: **`tp_price` is assigned nowhere in the codebase; TP count is 0/761 trades over five years** (Fact). Every "win" is a break-even scratch and the seven largest gains are Friday-EOD luck. Combined with a score-semantics bug that makes A/A+ spread tolerance unreachable and a hard lot cap that makes risk sizing inert, the system has been tested with **no profit mechanism and cost gates that block by regime**. **Economic evidence: negative but uninformative about the SMC idea** — it falsifies this exact rule-set+exit-model, not the underlying concept. **Main bottleneck: quant design (missing exit spec, grade semantics), not engineering.** The engineering is unusually honest; it faithfully refused to invent a profit target nobody locked.

## B. Faithfulness scorecard

| Dimension | Score | One-line justification |
|---|---|---|
| Detection fidelity | 8/10 | Sweep/displacement/base-candle machinery matches §2/§3/§18/§19 closely; volume-dependent liquidity nuance lost (A5), triggers degrade to price-only |
| POI model fidelity | 8/10 | 8 equal tags, confluence by tag count, no hierarchy — §1 verbatim; but tags exist mostly as labels, M8 structurally silent |
| Validation fidelity | 9/10 | Five pillars 1→5, hard 1–4 short-circuit, UNAVAILABLE≠pass, soft inducement — §2–§7 exactly |
| Trigger fidelity | 6/10 | Chronological first-valid + matrix tie-break is honest (§12/§15), but F=86.6% of book, D dead, C/E ≈ absent — matrix breadth is theoretical, not exercised |
| Risk/execution fidelity | 5/10 | §28 gates all present and ordered, but grade thresholds mismeasure (tag-count vs 0–10 scale) and the profit leg of risk (TP) is missing entirely |
| Backtest honesty | 9/10 | Touch-fill at limit, same-bar SL-first, no partials, no retries, dual-run byte-identity, invariants, anomalies disclosed rather than hidden |
| Live/paper readiness | 7/10 | Heartbeat/watchdog contract proven, KPI logger real, operator pack solid; HTF series unprovisioned and paper residuals (ambiguous closes, partial fills) untested live |
| **Overall idea→code translation** | **7/10** | The *process* is translated with unusual discipline; the *strategy* (entries + exits) is only half-translated, and nobody noticed for five phases |

## C. What was executed well

- **Determinism as a first-class contract**: dual-run byte-identical `trades.csv`/`report.json` over 1.77M bars ×2; golden replay pinned the perf refactor byte-for-byte (Fact, Phase C report).
- **Honest anomaly disclosure over cosmetic wins**: §10.1–10.3 of the Phase C report explicitly records the lot-cap binding, the no-TP exit model, and the `win`-column trap — the three most damning facts, self-reported (Fact).
- **No look-ahead found in the seams audited**: trigger evaluations are bar-index-bounded, ATR is pre-sweep Wilder over the honest prefix, displacement measured sweep→BOS only (Fact, code + perf-audit probes).
- **Fill model is deliberately conservative and stated as such**: touch=fill at limit price, no gap-through improvement, same-bar SL-first, entry+SL same bar → stopped (Fact, `fill_model.py` header).
- **Ops layer (Phase D) is real engineering**: heartbeat contract mirrored in MQL5, stale-edge verified at exactly 5s, watchdog EA compiled clean, identity-gated binding, spread regime finding (0.26 constant; gate = ATR-regime law) is a genuine quantitative contribution (Fact).
- **Governance discipline**: frozen constants isolated in one module; config loader *loudly rejects* attempts to override locked values; decision log with dates throughout (Fact).

## D. Critical shortcomings

1. **No take-profit exists anywhere in the system.**
   *Evidence:* `tp_price` has no assignment site in `04_SRC` (grep); trades.csv: `tp` empty on all 761, `close_kind` = {stop_loss: 754, friday_eod: 7}; wins avg +0.129 vs losses avg −0.129 → realized payoff 1.0 at 25.5% WR ⇒ negative expectancy **by construction**. The R1 spec's only RR language is the M8 "1:5" aspiration; `LOCKED_DECISIONS` has no TP rule.
   *Why it matters:* This is the single load-bearing hole. The five-year baseline measured "can a BE-latched stop survive 87% SL rate without a profit leg?" — the answer was always arithmetic.
   *Blocks research?* **YES — blocks everything downstream.** Any expectancy, walk-forward, or regime work on the current book measures the exit hole, not the entries.

2. **Spread-grade semantics bug: the grade inputs are on the wrong scale.**
   *Evidence:* §28.5 thresholds are A+≥8 / A≥5 / B≥3 / C<3 (a 0–10 quality scale); the engine feeds `request.score = candidate.score` = confluence **tag count** (1, 2, or 3, per `confluence_scorer.py`), so all trades grade A or B; nothing can ever reach A+ tolerance.
   *Why it matters:* The gate that killed 100% of 2023-regime flow is stricter than designed; every spread-sensitivity conclusion is shifted one tier.
   *Blocks research?* Yes for any spread/cost experiment; must be fixed (or explicitly re-ruled) before re-running sensitivity.

3. **Trigger concentration + dead paths make "modular confluence" untested breadth.**
   *Evidence:* F=659/761 (86.6%), B=70, A=29, E=2, C=1, D=0 (volume-null per A5); per-trigger: A PF 0.044 (hold 15.6 bars), F PF 0.397 (hold 33 bars), B WR 50% but hold 190.6 bars, PF 0.212.
   *Why it matters:* The book is effectively one strategy (F) plus a slow B tail. All model/trigger matrix claims are currently untestable claims. B's 50% WR shows directional promise that the exit hole then discards.
   *Blocks research?* No, but it dominates what any next experiment will measure.

4. **M8/HTF is a structurally silent peer.**
   *Evidence:* Backtest/paper paths construct `DetectionDriver` with **no `htf_candles`**; `Model8.detect` returns empty without D1/H4 series; M8 POIs = 0 in every run. `live/loop.py` documents the limitation (loop.py docstring, "V1 limitations").
   *Why it matters:* The expert's primary setup (M8+Ending Diagonal, §15 ✓★) has never been evaluated by this system. "8 equal models" is 7 in practice.
   *Blocks research?* No (can be scoped out or provisioned), but "SMC idea validated" claims are incomplete without it.

5. **Lot cap makes risk sizing inert; the baseline is not a 1%-risk experiment.**
   *Evidence:* §10.1: all 761 volumes = 0.10 lots; cap binds 100%. Risk-normalized P/L claims cannot be made from this book.
   *Why it matters:* Position sizing interacts with every expectancy estimate; also means live demo risk ≠ backtest risk by construction.
   *Blocks research?* No, but must be documented in every result read-out (it is).

6. **No confidence machinery on 761 trades.**
   *Evidence:* No bootstrap/CIs, no Monte Carlo, no walk-forward anywhere in `06_RESEARCH` or the plan (Phase E checkboxes are open).
   *Why it matters:* 761 correlated F-trades on one instrument, one regime family; per-trigger subsamples (n=29, 2, 1) are anecdotes. Even a *positive* result at this n would be weak; a negative one is suggestive, not probative.
   *Blocks research?* No — it is the next research work itself.

7. **No funnel/counterfactual instrumentation for POIs that never trade.**
   *Evidence:* Funnel counts exist (raw→armed→routes→placed→opened), but nothing about armed-POI outcomes had a trade occurred (unfilled expiry, give-up windows, spread-blocks as counterfactual entries).
   *Why it matters:* With TP missing, the diagnosis must come from event-level studies, and the data to run them is not currently exported.
   *Blocks research?* Partially — export schema extension needed.

*(Non-blocking hygiene, for completeness: segment-boundary carry ruled accept+document with 0 dropped positions — adequately closed; no benchmark strategies exist (buy/hold, random-entry, naive breakout) — cheap to add, should be in the next plan; segment design means wall-clock time-of-day effects are preserved but multi-year state carry is approximated — fine for V1, documented.)*

## E. Quant interpretation of current results

**Proven (Fact):** Under the exact frozen rule-set — no TP, tag-count spread grades, 0.10-lot cap, spread gate as coded — the system produces −4.8% over five years with 761 trades, 25.5% P/L-WR, PF 0.344, and the loss structure is exactly "scratch streaks punctuated by full stops." The BE latch works as designed (win rate 25.5% = the base rate of reaching +0.1×ATR before SL).

**Suggested (Inference):** The entries have *some* content: 22.7% of trades reached +1×ATR before stopping out; Trigger B reached +1×ATR first in 50% of 70 trades; 30 trades touched +4.47 R before dying (vs 10 for the inverse strategy). But suggestion is not expectancy: without a profit-taking rule these are unmonetized touch counts.

**Unknown:** Whether any TP policy (fixed R, structure-based, trail) turns the book positive; whether per-trigger TP policies differ (F vs B vs A); whether the 2023-style low-ATR regime is simply hostile to the whole concept (no regime-conditional results exist); whether M8 setups add independent value; whether spread costs in a live regime materially change the shape (Phase D says the gate passes today, but today ≠ 2023).

**Is the weak baseline expected or alarming?** **Expected — and the strongest possible argument for expecting it was self-recorded.** Phase C §10.2 states PF/WR "cannot distinguish 'no edge' from 'no exit model'." A trend-continuation entry family (F) with a stop-and-scratch exit model produces exactly this signature. The result is a successful *falsification of the exit-less configuration*, nothing more. Two explanations fit the data: (1) entries lack edge entirely; (2) entries have modest edge destroyed by the missing profit leg. Distinguishing evidence: re-run the same frozen entries under 2–3 defined TP policies and compare — that experiment does not exist yet and is the highest-information action available.

## F. Recommended next plan of action

**1. Immediate research actions (the diagnostic sprint)**
- **R1 — Exit-policy event study (top priority, no strategy code changes needed to run):** Replay the frozen entry book under 3 TP policies as *offline counterfactuals* on stored M1 bars: (a) fixed 2R, (b) fixed 5R (the M8 spec), (c) structure-based (opposing swing / dealing-range extreme), plus current BE-only as control. Metrics: expectancy per trade, per trigger, per year, PF, and robustness to TP±25%. Needs: MFE/MAE/R-multiple export per trade (extend export schema; entry/SL/timestamp already in the book).
- **R2 — Fix or re-rule the spread-grade semantics (1-hour change, must be ruled by the Lead Architect):** Either map the §28.5 thresholds onto the tag-count scale (A+≥3, A≥2, B≥1, C<1) or feed a true 0–10 quality score. Re-run the Phase C ladder arms after the fix; update the Phase D regime thresholds (A+ 1.156 / A 1.733 / B 2.476 / C 3.467 change with the mapping).
- **R3 — Trigger-family decomposition and ablation:** Per-trigger expectancy under the best R1 exit policy; ablations: F-only, no-F, B+A only, no-BE-latch, no-Friday-EOD. Kill or quarantine trigger families that remain negative under every exit policy at adequate n.
- **R4 — Armed-POI counterfactual event study:** Export every armed POI with its route/fail reason and simulate "what if the blocked/expired one had traded" — measures how much expectancy the funnel itself destroys (specificity vs scarcity).
- **R5 — Benchmarks and significance:** Random-entry-with-same-exit-model, naive-BOS-entry, and buy-and-hold-XAU baselines under identical cost/exit assumptions; block bootstrap CIs on per-trigger expectancy (761 trades, year blocks); per-year stability table.
- **R6 — Regime conditioning:** Bucket results by ATR regime (the Phase D regime law makes this natural: ATR terciles), by year, by spread regime; test entry×regime interaction before claiming any family works "everywhere."

**2. Parallel ops actions (paper/demo) — deliberately narrow**
- Continue Phase D as defined: identity, watchdog drill, order send/cancel/modify/close paths, slippage measurement on actual fills, KPI archive. Demo fills also *measure the touch-fill assumption* (fill price vs limit price distribution) — feed that into the cost model of R1/R5.
- Do NOT read demo P/L as idea validation. With no TP placed, demo trades will replicate the backtest shape by construction.

**3. Decision gates (Lead Architect rulings required)**
- **Gate 1:** Exit-model spec — choose TP policy family for research (frozen for the experiment, then re-locked only with evidence). This is a *strategy* decision nobody has made in five phases.
- **Gate 2:** Spread-grade semantics fix (R2) — approve mapping, then un-freeze/re-freeze with a dated ruling.
- **Gate 3:** M8 provisioning — either resource the D1/H4 data path or formally scope M8 out of V1 claims.
- **Gate 4:** After R1–R6: promote, modify, or kill per trigger family; criteria below.
- **Promotion criteria (proposal):** a change enters the locked system only if it improves per-trigger expectancy with bootstrap CI excluding zero at n≥100 per family, holds in ≥2 ATR regimes, and survives a walk-forward split. Kill criteria: family negative in every exit-policy variant and every regime bucket → quarantine (keep code, disable in routing config), do not delete history.

**4. 30–60 day roadmap**
- **Week 1:** R2 fix + re-run spread ladder; export schema extension (MFE/MAE/TP-counterfactual columns); Gate 1/2 rulings.
- **Week 2–3:** R1 event study (3 policies × 761 trades × 5y M1 — compute cost is hours, not days, since entries are frozen and stored); R3 decomposition + ablations.
- **Week 4:** R4 funnel counterfactuals; R5 benchmarks + bootstrap CIs; interim Lead Architect review with the promote/kill matrix.
- **Week 5–6:** R6 regime conditioning; walk-forward on the surviving configuration; decision memo: which families enter a Phase E candidate config; only then consider new feature building (M8 provisioning, sizing work).
- Phase D ops runs continuously in the background throughout (it costs no research attention once scheduled).

**5. Explicit non-goals**
- No re-optimization of locked detection/validation thresholds as a first response (ablations yes, tuning no).
- No new POI models, no new triggers, no ML overlays.
- No capital allocation discussion, no live-money anything.
- No "fix by tuning the spread gate until trades appear" — cost gates exist to bind.
- No rewrite of the backtest engine; it is the most trustworthy component in the repo.

## G. Questions the project owners must answer

1. **The exit question, explicitly:** Was the missing TP an oversight or a deliberate "measure entries only" experiment? Who owns writing the exit spec, and what RR/structure policy do you want tested first (Gate 1)?
2. **Grade semantics:** Do you approve mapping §28.5 grade thresholds to the tag-count scale, or building a true 0–10 quality score? (Gate 2 — one or the other must be ruled before any cost experiment.)
3. **Trigger D:** Given volume is structurally absent from the dataset, do you (a) keep D dead, (b) resource tick/volume data, or (c) redefine D on price-only proxy? A5 deferred this; it is now a design decision with economic consequences.
4. **M8:** Provision D1/H4 series (moderate engineering + data work) or formally scope M8 out of V1 validation claims?
5. **Kill authority:** When a trigger family fails the promotion criteria after R1–R6, is quarantine-without-deletion the accepted mechanism, and who signs the kill?
6. **Sizing reality:** With the cap binding 100% of trades, do you want the research book re-expressed in risk-normalized R-multiples (recommended) so results are cap-independent going forward?

---

**If I could force only one next research action before more feature building, it would be: run the exit-policy counterfactual event study (R1) — replay the frozen 761-trade entry book under 2–3 explicit take-profit rules on stored M1 data, because until a profit leg exists, every metric the system produces measures the missing exit, not the SMC idea.**
