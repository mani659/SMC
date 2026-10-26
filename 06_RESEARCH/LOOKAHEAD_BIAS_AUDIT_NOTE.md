# LOOK-AHEAD / NEXT-BAR BIAS — INDEPENDENT AUDIT (findings only)

**Requested:** Lead Architect, 2026-10-06 — "is it possible we introduce
look-ahead + next-bar + bias based on some statistical modeling, possibly
on our command prompt?" **No implementation. Findings for review.**
**Scope audited:** fill model, bar loop, runner ordering, adapter scan
bounds, validation pillar bounds, batch prefix trimming, HTF provisioning,
operator prompt/console/research scripts.

---

## 1. Verdict (short)

**No look-ahead bias found in the frozen decision path.** The core loop is
bar-ordered, prefix-bounded, and conservatively ordered. **Next-bar bias:
partially present by design** — "next-bar" is the *right* semantics for
limit placement, but two places let same-bar information reach a
*decision* slightly early. **Statistical-modeling bias: none implemented
in product code** — but the operator command prompt is a real, growing
surface for it, and three specific patterns are already visible at low
intensity.

---

## 2. What was verified clean (with the specific mechanisms)

| Surface | Mechanism that prevents look-ahead | Verdict |
|---|---|---|
| Bar loop | Deterministic walk, injected clock = bar timestamp; handler sees bar N with clock at N | Clean |
| Fill evaluation vs placement | Runner order per bar: **expiry → fills → entry/scan → placement**. Explicit comment + test pin: "a bar-B placement cannot fill on B: no lookahead, no retroactive fill" | Clean |
| Fill model | Touch=fill at the LIMIT price (no optimistic better-of-open, no gap-through price improvement); same-bar SL+TP → **SL wins** (worst case); entry+SL same bar → stopped | Clean, conservative |
| Trigger scans | Adapter scans prefix `[: bar_index+1]` capped at decision bar; per-POI scan cursor resumes forward-only | Clean |
| ATR/RSI folds | `values[bar] == latest_atr(candles[:bar+1])` — fold identity pinned by test | Clean |
| §27 swings | N-bar **confirmation window** (N=5 HTF / N=3 LTF) requires N bars AFTER the candidate bar *inside the prefix* — a swing is only usable N bars later, which is honest waiting, not look-ahead | Clean |
| Batch detection | Every batch call site (funnel, paper, live) trims series to `as_of` = decision bar before `run_batch`; forming bar included, future never | Clean |
| M8 displacement | Sweep→BOS measured over bars AFTER the sweep **within the trimmed series** — never reads beyond `as_of` | Clean |
| HTF provisioning | 300 bars fetched at start and re-fetched per batch (W1→2021); historical-window design, not session-birth | Clean |

---

## 3. Findings — next-bar / partial same-bar leakage (by design, but known)

These are **not defects**; they are deliberate conservative semantics with
a measurable direction of bias. Listed so the Architect can see the exact
residual.

**F1. Touch = fill (no intra-bar ordering).** A bar that touches both the
entry limit and the stop resolves SL-first — conservative (bias against
the system). The inverse error is impossible here; the risk would appear
if anyone "improves" fill realism without a tick path model.

**F2. The arm bar can carry same-bar range info.** `IN_ZONE_AT_ARM` /
`VIOLATION_AT_ARM` postures classify the arm candle itself — by the §5a
design this is *initial presence, not a terminator*, and the scan opens at
arm. This uses same-bar information the live loop would also have had
(the bar is closed when processed), so it is live-consistent — but it
means a backtest bar's HIGH/LOW (not just its close) influences an
arm-time decision. **Keep an eye on it:** any future "score tweak" using
arm-bar wick size would be a same-bar-signal pattern.

**F3. Pillar-1 mitigation suffix.** `_mitigated` reads
`candles[active_index + 1:]` — bars after the zone formed. Sound **only
because the series was trimmed to `as_of` upstream** (verified at every
batch call site: funnel h1[:cut+1], paper `build_htf_prefixes`, live
prefixes). The suffix is a suffix **of the trimmed prefix**. The day
someone calls validation on an untrimmed series, this silently becomes
look-ahead. It is defended by convention, not by an assertion.

**F4. Next-bar placement semantics (correct, but name it in reports).**
A signal completed on bar N places a limit that can fill from bar N+1 —
this is exactly right for a resting limit and matches live (order rests
after placement). Reports should keep saying "fills evaluated from
placement bar + 1" so nobody later mistakes it for a bug or "fixes" it.

---

## 4. Findings — statistical-modeling bias (none in product; prompt risk real)

Product code: no sklearn/ML/calibration anywhere; no probability outputs
feed decisions; all thresholds are frozen constants. The audit's keyword
sweep found ML vocabulary only in research scripts (calibration probes,
OCR/statistical reporting) — none imported by the strategy stack.

**The operator command prompt is the real surface.** Not by code — by
process. The audit flags three active patterns:

**P1. Findings-led iteration (active, low intensity).** Recent reports
record hypothesis-outcome mixes (SL_THEN_TP_PATH 2 / TP_REACHED 1), MFE/MAE
ratios, TP-hit-after-stop observations on **n=3**. Nothing feeds decisions
yet, but the *direction of gaze* is outcome-led. The accepted guard is
working — every one of those reports carries "diagnostic only, NOT edge" —
but the sample sizes are so small that any rule picked from them would be
pure overfit. The lead Architect's standing ruling already says so; this
audit formally records the pattern as the main bias channel.

**P1b. Threshold-adjacent diagnostics accumulate.** STRUCTURAL_TP_MIN_ATR
interim constant, gate-ceiling display mirror, posture mixes — each is
individually documented; together they form a menu a future prompt could
"optimize". The bans (R6, no threshold edits without ruling) are the only
defense.

**P2. Console/ops mirror values.** The operator board displays gate
ceilings mirrored from ATR. Display-only (verified), but if a prompt ever
asked to "act on gate_pass" from the mirror rather than the RiskEngine,
you'd have a decision-reading-display defect. The mirror is annotated as
display-only; keep it that way.

**P3. Prompt-originated parameter suggestions.** Several past prompts
contained concrete numbers ("0.25R divider", "30 pips", "±0.5×ATR band").
These were correctly treated as review metrics, not adopted — but the
channel exists: **a number appearing in an operator prompt creates a
pull toward tuning.** The 2026-10-05 policy sync codified this
(prompt numbers = review metric only); the audit confirms the channel is
real and recommends keeping the rule standing.

---

## 5. Recommendations (for review, none implemented)

1. **Cheap assertion, high value:** an explicit guard (test or runtime
   assert) that `ValidationPipeline` is only invoked on series whose last
   bar == the decision `as_of` — closing F3's convention-only defense.
   Architect decision whether to add.
2. **Report language:** keep "fills evaluated from placement bar + 1"
   language in every report (F4) — pre-empt future "fixes".
3. **Prompt hygiene rule (already standing, reaffirm):** numbers in
   operator prompts are review metrics only; adopting any requires a dated
   ruling + a locked-constant change with dual-run determinism evidence.
4. **Sample-size gate:** any future rule derived from a funnel/hypothesis
   study must state its n; n < 30 → classification only, never a rule.
5. **If statistical modeling is ever wanted:** it must live behind the
   same seams as everything else — a new module reading only honest
   prefixes, walk-forward validated, never fit on the evaluation window,
   and never in the operator prompt path. The frozen loop already gives
   you the harness for a leak-free backtest of such a model.

## 6. Bottom line

- **Look-ahead: none found** in the decision path; defenses are bar
  ordering, prefix bounds, conservative fill priority.
- **Next-bar: present and correct** (limit rests ≥ 1 bar); same-bar arm
  classification and the mitigation suffix are the only two places where
  the "next-bar" line sits closer than it looks — both are
  live-consistent and documented, but convention-defended (F3) or
  direction-of-gaze-relevant (F2).
- **Statistical bias: none in product code; the operator prompt is the
  plausible channel** — and the existing bans (findings = diagnostic only,
  prompt numbers = review metrics, locked-constant edits need dated
  rulings) are exactly the right countermeasures. Keep them standing.
