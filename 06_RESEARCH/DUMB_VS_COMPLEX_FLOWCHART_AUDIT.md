# DUMB vs COMPLEX — FLOWCHART AUDIT NOTE

**Banner: DOCS ONLY — DIAGNOSTIC — NOT EDGE / NOT LIVE VALIDATION.**

Authority: Architect 2026-10-21. User question: *Why not 1:1? If DUMB is not
true essence, what is its benefit?* This note is documentation only: no
`04_SRC/smc/**` edit, `locked_constants.py` diff **EMPTY**, no re-optimisation,
no new edge claim, no capture re-run (every number below is cited from a report
already on disk). COMPLEX comparison point stays frozen at `b5e8c53`
(`00_LOCKED/BASELINE_COMPLEX_V1_1_COMPARISON_POINT.md`).

**Sources read:** `06_RESEARCH/DUMB_FLOWCHART_V1_DESIGN.md` (the R1–R6 lock) ·
`06_RESEARCH/DUMB_FLOWCHART_V1_IMPLEMENTATION_NOTE.md` (as-built + W3/W2 counts) ·
`00_LOCKED/BASELINE_COMPLEX_V1_1_COMPARISON_POINT.md` (frozen books) ·
`06_RESEARCH/AS_CODED_ARCHITECTURE_FLOWCHART.md` (COMPLEX stage map 0A–5, as coded) ·
`06_RESEARCH/FLOWCHART_CODE_EVIDENCE_MAP.md` (intended §16 pipeline ↔ code) ·
`06_RESEARCH/FLOWCHART_MATCH_NOTES.md` (prior expert chart-scoring precedent) ·
`06_RESEARCH/EXIT_ANATOMY_DIAGNOSTIC_REPORT.md` (exit-class density) ·
`06_RESEARCH/POST_DEDUP_EDGE_*` reports (stability verdicts).

**Match-column semantics for §2:** FULL = the same rule in both paths ·
PARTIAL = same flowchart idea with a shared identifiable element (same object,
sub-rule, or anchor) but materially different implementation · NONE = no shared
element in the rule itself.

---

## §1 Verdict

**DUMB is NOT 1:1 with COMPLEX — not by design and not by accident.** The two
paths share exactly one piece of DNA: **HTF POI zones** — DUMB's R1 level is
literally the product's own `M8HtfDemandSupply` zone called as a read-only
library, the same zone family that feeds COMPLEX's arm path
(`DUMB_FLOWCHART_V1_DESIGN.md` §R1; `DUMB_FLOWCHART_V1_IMPLEMENTATION_NOTE.md` §2).
Everything downstream of the zone diverges: COMPLEX gates a zone through five
pillars, a confluence/compatibility grade, a ZoneDedup arm registry, a six-
trigger matrix with per-letter expiries, a risk/ops layer, and a limit-order
placement chain (stages 0A–5 in `AS_CODED_ARCHITECTURE_FLOWCHART.md` §B), while
DUMB applies one rule per flowchart beat and stops — sweep, single mid-reclaim
confirm, market entry, sweep-anchored stop, fixed 2R. The verdict therefore is:
**same level family, different trade definition** — which is precisely why the
counts differ ~75× (§3) and why any performance comparison between them is
invalid until the trade definitions are made comparable (§6).

---

## §2 Stage-by-stage table

| Flowchart idea | COMPLEX behavior (as coded) | DUMB behavior | Match |
|---|---|---|---|
| **Level** | 8 POI families M1–M8, detected on H4+H1 (D1→M8), merged (`merge_overlapping`), five-pillar validated (session · displacement · premium/discount 45/55 · EQH/EQL · inducement; pillars 1–4 hard, 5 soft), quality-scored, then armed through the ZoneDedup registry (`AS_CODED` §B stages 1–2; `FLOWCHART_CODE_EVIDENCE_MAP` §1–2) | The **already-emitted M8 HTF zone** exactly as the product scan produces it (frozen `DISPLACEMENT_MIN_ATR`/`N_BAR_LTF` inside the reused scan) — **no pillar, no grade, no registry**; every M8 zone is a candidate from its emission bar (design §R1, §4) | **PARTIAL** — same zone object, opposite admission discipline |
| **Sweep** | Stage-0A `sweep_detector`: wick-pierce + body-close ("a candle that closes beyond the level is NOT a sweep"), feeding **displacement attribution** (BOS + FVG + 1×ATR) and trigger context — the sweep is a liquidity/displacement *input*, not an entry beat (`FLOWCHART_CODE_EVIDENCE_MAP` §2) | R2: one M5 bar, wick beyond the zone extreme + close back inside (the same discipline transposed to `zone.bottom`/`zone.top`) — standalone per zone, **no displacement requirement** (design §R2) | **PARTIAL** — identical wick/close sub-rule, different substrate and coupling |
| **Confirmation** | Pre-arm: five pillars (pass rate ~15–17%). Per-bar: trigger matrix A–F, chronological first-valid wins, per-letter expiries (`TRIGGER_A_EXPIRY=20` … `F=1`), §15 matrix tie-break, §5 freshness TESTED/VIOLATED state machine (`AS_CODED` §B stage 3) | R3: **exactly one rule** — first later M5 bar closing through the zone MID in trade direction, expiry at `DUMB_CONFIRM_MAX_BARS = 12`; CHOCH / BOS+OB / two-bar reversal surveyed and explicitly non-normative (design §R3) | **NONE** — no rule element is shared; a single price-location event replaces a pattern vocabulary |
| **Entry** | **Limit on every path**: `TriggerSignal.entry_price` → resting pending limit at the proximal/mid zone; risk-then-placement (`RiskEngine.evaluate_entry` → R7 fill-regime band → possible R9 intent deferral) (`AS_CODED` §0 headline 3 + stage 4) | R4: **market at the confirm bar's close**, admitted only while the close is still inside the zone (mid-half by construction; outside → discard, no chase) | **PARTIAL** — both anchor entry to the zone geometry after an admission event; order type, timing and deferral machinery differ |
| **SL** | Beyond the entry structure's distal side (honest stops measured at ~0.82–0.89×ATR on the F book), then **managed**: PureRunner BE moves, SameLevelGuard (0.15×ATR) / SweepGuard (0.5×ATR) block re-entries, `ATR_FLOOR_MIN_SL` compiled but never imported (`FLOWCHART_CODE_EVIDENCE_MAP` §2, `AS_CODED` §F) | R5: sweep-bar extreme ± `DUMB_SL_BUFFER_ATR (0.10)` × ATR(M5,14) — **fixed for the trade's life**, no BE, no guards (design §R5) | **PARTIAL** — "beyond the extreme" anchor shared; COMPLEX mutates and guards, DUMB never does |
| **TP** | Structural swing feed with ATR fallback (`tp_source ∈ {structural_swing, atr_fallback}`; medians 0.51R structural / 1.70–2.18R fallback in the frozen books) (`EXIT_ANATOMY_DIAGNOSTIC_REPORT` §6) | R6: **fixed 2R** from initial risk; next-opposite-swing explicitly rejected for V1 because placement is the unresolved research question (design §R6) | **NONE** — target placement shares no rule element (structure-derived vs R-multiple) |
| **Risk / ops** | Full layer: news pin, session gate, circuit breaker, spread grading, Friday EOD, lot caps, R7/R9 intent book, seek/scan postures, heartbeat + watchdog + operator console (`AS_CODED` §B stages 4–5; design §4 list) | **None** — offline books, costs sanitized to 0, no guards, no live plumbing; each omission logged once so a later realism leg cannot assume it (impl note §7.4) | **NONE** — one path has the layer, the other by design has no counterpart |

No row scores FULL — that is the table form of §1's verdict.

---

## §3 Why not 1:1 (mechanisms)

- **Extra AND gates in COMPLEX.** A zone must survive merge → five pillars →
  score → dedup-arm → per-bar trigger routing with expiries → risk gates →
  R7/R9 placement before it can even become a fill. The frozen books show the
  result: **>558 armed episodes per window → 44–75 fills (~6–14% of arm)**
  (`BASELINE_COMPLEX_V1_1_COMPARISON_POINT.md` §3), and LEG 4 measured the arm
  step alone at 2,021 passes → 30 armed, 98.52% suppressed as
  `SKIP_DEDUP_EPISODE` (`PASSED_TO_ARMED_ATTRIBUTION_REPORT.md`).
- **DUMB has a single confirm.** One mid-cross close within 12 bars, no pillar,
  no matrix, no registry (design §R3/§4). Every M8 zone is a candidate from its
  emission bar — the design deliberately removed every AND gate so a junior can
  trace the story on one chart.
- **Different entry, SL and TP.** Market-at-close vs resting limit (entry);
  sweep-wick ± 0.10 ATR never modified vs distal-structure stop with BE
  mutation and guards (SL); fixed 2R vs structural swing feed (TP) — three
  independent definitional differences, each sufficient on its own to break a
  like-for-like comparison.
- **Density consequence (~75× on W3).** Same M8 zone feed, no gates:
  **W3 4364 trades vs COMPLEX 58 = 75.2×** (setups swept 16 018 · confirmed
  7 100 · expired 8 908 · anchor updates 28 105 · outside-zone skips 2 736;
  exits SL 2958 / TP 1406) and **W2 2874 vs 44 = 65.3×**
  (`DUMB_FLOWCHART_V1_IMPLEMENTATION_NOTE.md` §4–5). Counter arithmetic
  reconciles exactly and both windows are dual-run byte-identical, so the ratio
  is a property of the rules, not of a capture artifact. Read backward: COMPLEX's
  scarcity lives in its gates, not in the level family — the same zones, given
  only sweep→confirm→entry, produce thousands of trades per 6 months.

---

## §4 Is DUMB "true essence"?

**(a) Intent alignment (sweep → confirm → entry): YES.** DUMB implements the
three-beat story literally — one normative rule per beat, each verifiable on a
chart without software (design §3/§8: R1–R6 implementable "without inventing a
second pattern"). The *narrative* the user asked for (level → sweep → reclaim →
entry with SL/TP) is exactly what the runner does and what each trade row
records.

**(b) Pattern-confirmation fidelity to the original expert flowchart: PARTIAL.**
The confirm is a **single price-location proxy** — "close through the zone mid"
— chosen because it is the minimal strictly-stronger displacement test a junior
can verify (design §R3). The expert flowchart's actual pattern vocabulary
(displacement/BOS+FVG, CHOCH, BOS+OB, two-bar reversal — the six triggers COMPLEX
routes on) was surveyed and **explicitly made non-normative** for DUMB V1. So
DUMB captures the *beat* "wait for confirmation" but not the *patterns*; if the
original flowchart's confirmations were pattern-set based, the honest reading is
PARTIAL leaning NO. Two further facts keep this at PARTIAL rather than YES: the
design's own §6.2 gate (≥70% of sampled charts PARTIAL+ on the four-item rubric)
**has never been run**, so even the proxy is unevidenced; and the prior expert
scoring precedent (`FLOWCHART_MATCH_NOTES.md`) found STRONG ratings impossible
without geometry exports — the same measurement gap applies here.

**(c) What would need to change for DUMB to claim essence — amend R3/R4 only,
candidates listed, none implemented:**

1. **R3-a · displacement on the reclaim bar** — require the confirm bar's body
   (or a paired FVG/BOS) to meet a displacement threshold, importing the
   flowchart's displacement beat (design R3's own "minimal displacement test"
   upgraded to the real one).
2. **R3-b · tighten to sweep-origin reclaim** — confirm = close back beyond the
   sweep origin/extreme rather than the mid (the design §7.1 "tighten" fork):
   "reclaimed past the liquidity event", stronger, fewer trades.
3. **R3-c · pattern-set confirm** — accept any of {CHOCH, BOS+OB (trigger-F
   shape), two-bar reversal} on M5 after the sweep, imported read-only the way
   M8 is imported; closest to the original pattern vocabulary, but drags swing
   state machines into a path built to avoid them.
4. **R3-d · multi-bar confirm** — require N consecutive qualifying closes
   instead of one, reducing the single-bar proxy's noise component.
5. **R4-a · entry style** — limit at the zone edge/mid instead of market-on-
   close (design §7.2 alternate; rejected for V1 because it decouples entry from
   confirm and needs a fill/validity book).
6. **R4-b · retest-based "near level"** — admit only if the confirm bar's trace
   returns into the zone's mid-half, enforcing nearness by retest rather than
   by construction.

Plus the evidence prerequisite (not a rule change): the **§6.2 rubric must
actually be run** — ≥70% PARTIAL+ on a fixed expert sample scored without
exits — before the word "essence" is claimed in any report. Each amendment
above is a dated design amendment, not a tuning step; none is proposed here.

---

## §5 Benefit of keeping DUMB despite (b)

- **Scarcity diagnostic:** DUMB isolates the level family from the gates — the
  same M8 zones yield 4364 sweep→confirm→entry trades where COMPLEX closes 58,
  so COMPLEX's thin 44–75 fills/window can be *attributed* to its gate stack
  rather than to a lack of opportunity at the level (§3).
- **Blame isolation:** every DUMB trade carries a flat decision trail (zone
  emit → sweep bar → confirm bar → entry/SL/TP) with counters that reconcile
  exactly, so a bad trade points at one of six rules — whereas a COMPLEX
  failure routes through the ~10-stage 0A–5 funnel (`AS_CODED` §B).
- **Expert scorability:** the four-item rubric (level / sweep / confirm / entry
  near level) is scoreable from a chart *without exits and without geometry
  exports* — the exact blocker that capped the prior study at "no STRONG
  ratings possible" (`FLOWCHART_MATCH_NOTES.md` §4–5, §8).
- **Sandbox vs frozen COMPLEX:** DUMB lives in `smc/dumb/**` with zero references
  from the rest of `smc` (test-pinned source scan) and `locked_constants.py`
  untouched, so experiments run beside the comparison point frozen at `b5e8c53`
  without risking the product path or the A/B reference.

**Explicit non-benefits:** DUMB is **not edge** — every number it produces is
DIAGNOSTIC (PnL/PF are book-internal price units, costs 0, market-at-close;
impl note §4 banner) and no expectancy claim exists anywhere in the DUMB
record; and DUMB is **not a drop-in COMPLEX replacement** — the design §4
ignore-list (pillars, matrix, dedup registry, risk/ops layer, R7/R9, broker
realism) is exactly what the product path cannot drop, so DUMB can never
substitute for COMPLEX on any live surface.

---

## §6 Comparison rules going forward

**Valid:**
1. **Count/funnel comparisons on the same window** with the same data and
   mirrored warm-up (W3 4364 vs 58; W2 2874 vs 44), with counter
   reconciliation and dual-run determinism — as reported (impl note §4).
2. **Within-path funnel tables** (setups → confirmed → entries → exits) for one
   path at a time.
3. **Chart-rubric scores** once the §6.2 leg runs — sampled, fixed rubric,
   scored blind to exits.
4. **Single-gate counterfactuals on COMPLEX** (one seam no-op'd, dated,
   pre-registered) — the LEG 5b pattern — for attributing scarcity to a named
   gate.

**Invalid:**
1. **PF / expectancy horse-race between the two books.** The trade definitions
   differ on entry (market-at-close vs resting limit), fill model (DUMB's
   bracket-at-next-bar vs limit-touch with spread/session/breaker gates), stops
   (immutable vs BE-mutated) and targets (2R vs structural) — a PF delta would
   confound admission, execution and exit rules at once, and DUMB's PnL is
   book-internal price units (impl note §4).
2. **Direct exit-mix comparison.** DUMB's SL exits are all hard stops (no BE or
   trail exists); COMPLEX's `SOFT_SL_OR_BE` class is trail-produced — 20 of
   W2's 28 stop exits closed positive (`EXIT_ANATOMY_DIAGNOSTIC_REPORT` §2).
   The classes are not the same object.
3. **Reading 75× as opportunity or validation.** The design §6 band (3–10×) is a
   *readability* criterion; counts above it "trigger tightening rather than
   celebration" — the overshoot is a finding about the rules, not a score.
4. **Cross-window or post-change comparisons against the frozen books without
   re-freezing** (`BASELINE…` §4: silent drift of the comparison point is
   forbidden).
5. **Any essence / traceability claim without the rubric run** (§4c
   prerequisite).

---

## §7 Recommended next steps (ordered options only — no execution)

1. **Amend R3 to pattern-language confirmation** (candidates R3-a/b/c/d in §4c)
   as a dated design amendment, then re-measure W3 and run the rubric — the only
   route that could move (b) from PARTIAL toward YES.
2. **Spray-control ruling** — the two measured levers: the §7.5 per-zone cap and
   the re-anchor interpretation (33 308 sweeps against busy zones; 28 105 anchor
   updates in W3), to bring the count toward the 3–10× readable band. Any change
   is a dated amendment, not tuning (impl note §5).
3. **Stratified expert sample + rubric leg** — fix the §6.2 evidence gap
   (≥70% PARTIAL+), stratified by zone TF (W3: H4 4058 / D1 306) and side;
   scores blind to exits.
4. **Leave DUMB as an unchanged diagnostic probe** (default) — COMPLEX remains
   the product, DUMB remains default-OFF; optionally capture W1/W4 for
   four-window count parity via the existing script.

---

## §8 Return block

```
DUMB_VS_COMPLEX_AUDIT_STATUS: PASS
ONE_TO_ONE: NO
SHARED_DNA: HTF_POI_ZONES
ESSENCE_FIDELITY: PARTIAL
PRIMARY_BENEFIT: scarcity diagnostic — the same M8 zone family yields ~75x the fills without COMPLEX's gates, attributing COMPLEX's 44-75 fills/window to its gate stack
PRIMARY_GAP: mid-reclaim is a single proxy confirm with no rule shared with COMPLEX's pillar/trigger vocabulary, and the >=70% chart-rubric gate has never been run
NOTE_PATH: 06_RESEARCH/DUMB_VS_COMPLEX_FLOWCHART_AUDIT.md
LOGIC_CHANGED: NO
LOCKED_CONSTANTS_DIFF: empty
NEXT_READY: Architect review of audit note
```

**Ledger cross-refs:** SESSION_HANDOFF 2026-10-21 (4) · CHANGELOG 2026-10-21 (4)
· `00_LOCKED/POST_V1_ACTIVE_TODO.md` audit entry.
