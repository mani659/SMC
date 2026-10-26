# POLICY_TP_SL_PARTIAL — status snapshot 2026-10-05

> Docs-only capture of the operator's TP/SL policy statements and the
> Lead Architect's standing rulings before the structural-TP feed track
> started. This file is a status snapshot, not a strategy or live rule.

## What this file captures

1. The operator's policy statements received with the expert charts
   (read from chart red text / attachments).
2. The Lead Architect's standing rulings A–E recorded at the 2026-10-05
   docs-only policy sync.
3. The post-implementation status of ruling A (structural TP feed).

## Source

Operator policy statements + Architect rulings: see the 2026-10-05
docs-only sync recorded in `00_LOCKED/SESSION_HANDOFF.md`
("Standing rulings + accepted state (2026-10-05)") and the prior
`POST_V1_ACTIVE_TODO.md` policy-record item. Expert charts:
`06_RESEARCH/EXPERT_MARKED_CHARTS_INDEX.md` and
`06_RESEARCH/EXPERT_CHART_SYSTEM_MATCH_NOTE.md`. Seek/scan contract:
`00_LOCKED/LOCKED_DECISIONS.md` §5a. Frozen funnels (diagnostic only):
3m `06_RESEARCH/FROZEN_FUNNEL_NEW_CONTRACT_REPORT.md`;
6m `06_RESEARCH/FROZEN_FUNNEL_6M_NEW_CONTRACT_REPORT.md`.

## Operator's policy statements (as received)

(a) TP must always be the first swing low/high.
(b) SL must always be 30 pips below/above the small-TF entry.

These are operator intent, recorded for Architect ruling. They are
NOT implemented as live rules in this task.

## Lead Architect rulings (2026-10-05)

- **(A)** TP = first swing low/high MAY be fed via the existing
  `structural_else_4ATR` branch (previously UNFED). Design + implement
  is the NEXT coding track after this docs sync. **Status 2026-10-06:
  IMPLEMENTED** — structural first-swing feed live; see
  `06_RESEARCH/STRUCTURAL_TP_FEED_DESIGN.md`,
  `06_RESEARCH/STRUCTURAL_TP_FEED_IMPLEMENTATION_NOTE.md`, and the
  current-phase line in `00_LOCKED/SESSION_HANDOFF.md`.
- **(B)** SL stays current ATR / structural stops. Fixed 30-pip stop is
  NOT adopted. Unchanged.
- **(C)** Expert "30 pips below/above LTF entry": REVIEW METRIC ONLY —
  post-trade MAE / entry-precision yardstick. Not a live stop rule.
  Unchanged.
- **(D)** PARTIAL findings (standing guidance): WRONG → never trade;
  CORRECT → full path (existing gates); PARTIAL → allowed in principle,
  must eventually carry a quality tag; default degradation direction =
  log + half risk until a dated size rule is locked. Policy posture
  only — not implemented in code yet.
- **(E)** Pattern vocabulary gaps (double top/bottom, Fib golden,
  ending diagonal, W1 OB, etc.) documented from the expert match note —
  research backlog, not silent scope expansion this session.

## Bans (unchanged)

No threshold fishing; no F-survivor / F-timing optimization (R6);
Monte Carlo PAUSED; demo PnL never idea validation; no locked-constant
edits without a dated ruling; **do not claim expectancy or promote the
PARTIAL degradation posture into code without a dated ruling.**

## What this file does NOT say

It does not claim the structural TP feed produces an edge, expectancy,
or any performance verdict. The 3-month post-feed measurement is
diagnostic n=2 and is recorded in the implementation note, not here.
