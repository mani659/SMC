# MODE T — IDEA-vs-IMPL CORRECTION AUDIT (READ-ONLY; owner decision required for any correction)

**Date:** 2026-10-15 · second audit of the engagement · runs AFTER Part 1 residual fixes (suite 1167 green) · findings-first; nothing implemented in this Part · `LOCKED_CONSTANTS` untouched; `LOGIC_CHANGED_PART2: NO` · base commit `9b649d5` + uncommitted Part 1 working tree.

**Sources read:** `00_LOCKED/MODE_T_CONSOLE_MARKER_DESIGN.md` (binding), `06_RESEARCH/MODE_T_IMPLEMENTATION_NOTE.md`, `06_RESEARCH/MODE_T_RESIDUAL_FIXES_NOTE.md`, `06_RESEARCH/MODE_T_CONFIRMATION_AUDIT.md`, `smc/live/mode_t.py` (decide path + director + new `latest_entry_marker`), `run_operator.py` hook/publish code, `pipeline_adapter.active_workflows()`, `judgement_console.py`, `marker_writer.py`, watchdog `.mq5`.

## 1. Intent recap (what the owner wanted — 5 bullets, from the design posture statement)

1. **Tester mindset, not strategy claim:** visible activity + labelable demo tickets under hard caps; no edge/expectancy wording anywhere.
2. **Early/late feedback loop:** the expert watches the bot "think" in real time and can grade `level_ok / sweep_ok / confirm_ok / timing` afterwards.
3. **Visible bot thinking with ZERO fills:** console judgement blocks guaranteed even flat; banner; corner label.
4. **Naked-eye chart check:** armed zones + sweep line + entry line readable on the chart without reading Python.
5. **Product identity protected:** Mode A stays frozen/scarce; Mode T never blends into the product path; `mode=T` on everything diagnostic.

## 2. Impl behavior recap

- **Rule T2 as implemented:** fires per poll (`poll_interval_s`) over `adapter.active_workflows()` — the ROUTED-not-terminated candidates (one-shot §11 book). A decision exists for the routed (poi, proof-bar) event only once. Order placement needs: session gate, spread gate, no product ticket for the POI, ATR present, `gap=|mid−close|/ATR ≤ 0.25` of the PROOF BAR's own close, caps. Geometry: entry = proof-bar mid, SL = proof adverse extreme, TP = entry ± 1.0 ATR, min-lot volume, LIMIT only.
- **Skip recording is complete:** every non-PLACE emits the taxonomy line to `mode_t_events.jsonl` — the LATE/CHASE/FAR cases DO get logged evidence (that nuance matters for Q1).
- **Visibility seams:** flat-guaranteed judge board per `judge_interval_s`; POIS/SWEEPS/SEEKING from the L1 snapshot; BOOK product-vs-T split; corner label + `HEARTBEAT STALE` priority; markers ≤11 objects (zones/sweep/entry_t post-R1/label); judged entry_t line now actually drawn (Part 1 R1) including the dry-run flag.

## 3. Q1–Q6 with evidence

**Q1 — Sampling bias: YES, value-side; no, evidence-side.**
- The GAP gate compares the proof-bar mid against the proof-bar CLOSE: only proofs whose close is within 0.25 ATR of their own mid place. That is, by construction, an "already tight / momentum-quiet completion" sample — sharp retests, whisk-away chases, and far-close proofs can never PLACE. This is what Q1 fears and it is real for TICKETS (impl: `decide_mode_t` gap branch; test `test_t2_rejects_gap_beyond_0_25_atr`).
- Counterweight the researcher must not overlook: the skipped late/chase cases are NOT invisible — they are the densest part of the ledger (`GAP_TOO_WIDE` lines), so early/late grading CAN happen from data, just without a ticket.
- **Silence window estimate (market condition × gaps):** quiet ranging tape (e.g., Asia-hour consolidation, no HTF sweep, no displacement — typical dead FX sessions) produces no routed candidates for days → Mode T 100 % silent. Also silent on days when every armed POI's tie was taken by the product (`PRODUCT_PATH_TAKEN`), or when proofs finish >0.25 ATR from close (all logged as skips).

**Q2 — Confirmation quality: NARROWER than the owner's "vague LTF confirm → review ticket" intent.**
- Stage-3 proof completion REQUIRES the product's own routing path (armed H4/H1 + trigger letter + §11 one-shot registry). The `latest_entry_marker`/hook code inflers nothing; a §5-only or never-routed internal bar never becomes a decision. Honest conclusion: what T2 grades is "routing-stage confirmation quality at close", NOT "was any LTF return structure visible" — that narrower scope matches the non-goals (§2.6) but should be spelled out to the expert filling the scorecard.
- **Evidence:** hook docstring (`_mode_t_on_poll` — routed-but-not-terminated workflows ONLY, and the confirmation audit §2 row 4 agreed); no detection/§5 fork in the diff.

**Q3 — Visibility promise (post-R1): YES.**
- A non-coder with the chart open gets: banner + judge board at start (≤ `judge_interval_s`, default 60 s, even flat), corner label at once, zones within the next structure refresh, entry_t the cycle after a PLACE (R1), and BOOK lines product-vs-T. Board-per-cadence proof: `_maybe_judge` runs in BOTH console modes. Console/EA marker tests + flat-board unit green.
- Residual visibility gap, doc-confirmed: live JUDGEMENT lines come only from the Mode T ledger — a session where every decision is a product tie prints the flat idle line (Part 2 residual, correction-option table row C2).

**Q4 — False product story risk: LOW (with wording drills).**
- Your "what if tester adopts T2 mid-entry as Mode A" fear is structurally fenced: the T2 geometry is a proof-bar mid with 1.0-ATR brackets, while Mode A entry remains whatever the product path computes (FR-3.1/derived edges per prior locks) and its stop is FR-2-distal, NOT the Mode T adverse-extreme/±1.0-ATR box. Confusing them requires someone reading ONLY the Mode T ticket and ignoring the mode=T comment, the `diagnostic only NOT a strategy claim` banner, and the judge-board A/T posture; ALL mode-T ledger lines carry `"mode":"T"`.
- The strongest fence is negative-space: the product config can't enable T2 (`diagnostic_entries` absent → false), and the two paths never share an entry builder (Mode T is a second builder at the seam).
- **Risk grade: LOW**, with the owner-action recommendation of a README one-tester-page (see C1) because the banner alone doesn't prevent a lazy screenshot narrative.

**Q5 — Scorecard readiness: YES (durable), with a manual gap.**
- `level_ok / sweep_ok / confirm_ok / timing / would_take` are hardwired None in the §2.5 ledger line; appended to the same JSONL as the decision, durable on disk. Nothing can misremember them later.
- Gap: there is no helper that presents the ledger for hand-grading (expert must open a raw JSONL). Correction option; no implement now.

**Q6 — Correction options (DO NOT implement; owner picks)**

| # | Tension | Option A (RECOMMENDED) | Option B (DEFER / needs owner rule) |
|---|---|---|---|
| C1 | Q4 — lazy-screen risk in the tester | Ship the README one-pager with the next tester zip: what mode=T means, why the brackets differ from product, scorecard filler workflow | None (any code-side change here would break the frozen banner) |
| C2 | Q2/Q3 — pure-product sessions never show workflow judgement lines | Leave product lines OFF (product judge lines would drift toward "second product console"; flat idle + POIS/SWEEPS is already honest) | Owner-ruled separate enhancement: surface product-plan lines from the read-only snapshot too (docs-first, its own dated amendment — NOT this audit's call) |
| C3 | Q5 — scorecard grading harness | Ship with C1 an offline note template for the expert (fill `level_ok…` per ledger line; no code) | A future second task: a read-only JSONL→CSV grader script (no change to the live path) |
| C4 | Q1 — “want the late/chase tickets too” | Do NOT widen the gap: T2 as-is is the design-frozen frame, and the SKIP ledger already carries the late/chase evidence for grading | Widening `T_MAX_GAP_ATR` for Mode T only, OR widening the sampled workflow set (e.g. §5-only states): both need a dated design amendment + owner rule first; neither is a residual fix |
| C5 | entry_t after a dry-run day | Keep (dry-run) + (rejected) honesty labels as shipped in R1 | Agree a “hide dry-run line” config toggle if the tester finds them noisy (config-only addition, owner rule) |

## 4. Impl vs intent verdict

| Owner intent | Delivered | Aligned? |
|---|---|---|
| Tester mindset, visible wrap on tickets | `mode=T` everywhere; demo caps; no claims in any artifact | YES |
| Early/late grader data | Full skip + decision JSONL with blank placeholders; **but late/chase proofs can never produce tickets, only logs** | ALIGNED_WITH_GAPS |
| Zero-fill visibility | Flat judge board + corner label + zones + post-R1 entry_t | YES |
| Naked-eye chart check | ≤11-object caps honored; `HEARTBEAT STALE` priority; chart-TF independent | YES |
| Product identity untouched | Flag-default-off; second builder only; no locked_constants change | YES |

**Verdict: ALIGNED_WITH_GAPS** — the implementation faithfully executes the locked design and never invents beyond it; the gaps are design-frozen choices (the 0.25 ATR mid sample and routing-only visibility) that were on the table at design-lock time, not drift. The researcher must grade Mode T against what it actually observes; nothing implementation-side is blocking the demo.

## 5. Return block

```text
IDEA_IMPL_STATUS: ALIGNED_WITH_GAPS
T2_SAMPLES_WHAT: routed Stage-3 survivors of an armed H4/H1 POI whose proof-bar close sits within 0.25 ATR of the proof mid (i.e., momentum-quiet completions; late/chase completions are still logged as skips but never ticked).
VISIBILITY_OK: YES (post-R1; flat-board + corner label + zones + entry_t incl. dry-run)
FALSE_PRODUCT_RISK: LOW (T2 geometry ≠ product brackets; product configs can never enable it; README still recommended)
CORRECTIONS_PENDING_OWNER: C1 README one-pager (recommended, ship with demo zip); C3 offline scorecard grading template combo with C1 (recommended); C4 gap widening = dated design amendment only, DEFER; C2 product judgement lines = separate enhancement, DEFER; C5 dry-run line toggle = optional, owner rule only.
SUITE: 1167 (Part 1 tree; no Part 2 code change)
LOGIC_CHANGED_PART2: NO
NEXT_READY: owner picks corrections | internal demo | tester zip | push
```

— End of Part 2. Read-only; no T2/taxonomy/GAP/caps/product-path edit made here; the frozen §2.6 stance survives intact (no family reopened, no expectancy claim anywhere in this audit).
