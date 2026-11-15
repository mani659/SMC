# POLICY — OPT-B LIVE FLAG STAYS OFF (FROZEN)

**Date:** 2026-11-07
**Authority:** Lead Architect — GO, "POLICY FREEZE — OPT-B FLAG STAYS OFF (DOCS ONLY)" (item A, ahead of research branch B)
**Status:** `POLICY_OPT_B_STATUS: PASS` · `LIVE_FLAG_RULING: NO` · `LOGIC_CHANGED: NO` (docs + governance only; zero code change)

---

## 1. Architect ruling

**`RECOMMEND_LIVE_FLAG = NO`** — the wider measure does not support enabling
OPT-B live, and this ruling is FROZEN as of 2026-11-07:

> `enable_opt_b_same_bar_confirm` **remains `false`** in
> `config/live_demo.json` and in every shipped/tester configuration.
> **Do not enable it without a NEW, DATED, SPECIFIC Architect GO.**
> No default flip, no config edit, no "trial on live" is authorised by this
> document or by anything it cites.

Verified read-only at write time (2026-11-07):
`config/live_demo.json` line 11: `"enable_opt_b_same_bar_confirm": false` — the
only config file in the repository containing the key;
`operator_config.py` dataclass default `False`; the product engine default
`same_bar_asof=False`. There are no shipped tester packs present (`dist/` was
archived pre-flag to `ARCHIVE/dist_stale/`), so nothing else ships the key.

## 2. Wider evidence summary (from `06_RESEARCH/OPT_B_WIDER_MEASURE_NOTE.md`)

Both frozen windows, OFF → ON, percentages over confirmed wins:

| window | ON_WINDOW | LATE | BEYOND_STOP_SIDE | confirmed wins |
|---|---|---|---|---|
| **W1** primary 2025-06-01→2025-11-30 | **48.33 % → 48.33 %** | 31.67 % → 25.00 % | 12 → 16 | 60 → 60 |
| **W2** secondary 2023-12-01→2025-05-31 | **48.03 % → 44.67 %** | 28.95 % → 24.67 % | 35 → 46 | 152 → 150 |
| **Combined** (count-weighted) | **48.11 % → 45.71 %** | 29.72 % → 24.76 % | 47 → 62 | 212 → 210 |

Key structure of the result:

* **The small-sample 83 % → 100 % ON_WINDOW story does not replicate.** W1 is
  flat; W2 is down 3.36 pp; combined is down 2.40 pp.
* **Combined confirmed wins are not improved** (212 → 210; wins gained 21 /
  lost 23; expiries 50 → 53).
* **The same-bar class is not intrinsically high quality:** of 39 same-bar
  wins, only 16 (41 %) are ON_WINDOW; 16 are already BEYOND_STOP_SIDE, 7 LATE.
* Of the 63 OFF LATE wins, only 11 (17 %) become ON_WINDOW under OPT-B; ON
  separately loses 13 ON_WINDOW wins to BEYOND_STOP_SIDE and 11 to expiry.
* R7 is **not observable** in the geometry harness and is unchanged; the
  adapter/P1 path is unaffected by construction.

## 3. The 8-POI primary sample is SUPERSEDED

The single-month 8-POI smoke sample (with `--exec-from 2025-10-01`; 6 confirmed
wins; OFF 83.33 % ON_WINDOW → ON 100 %) is **VOID for product justification**
and **must not be cited** as evidence for enabling the flag anywhere — new
notes, reports, handoffs or marketing. It is retained in
`06_RESEARCH/OPT_B_CONFIRM_IMPLEMENTATION_NOTE.md` only as measurement history,
and its superseded status is recorded here and in the wider-measure note §7.

## 4. OPT-B code disposition

The `enable_opt_b_same_bar_confirm` plumbing (`ProductMenuEngine.same_bar_asof`,
`operator_config` parsing, `run_operator` wiring, its 13 tests) **remains in
place for future controlled experiments only** — measured, offline, and never
as an undocumented live change. Any future enablement requires:

1. a new dated, named Architect GO, and
2. evidence from a study that actually addresses what this one could not
   (placement-aware, see §6).

## 5. Out of scope (per the freeze)

* **R7 changes** — no R7 skip loosening, retune or reinterpretation; R7 skip
  claims from the geometry harness are invalid by construction and stay out.
* **Adapter LATE fix** — explicitly out of scope; the 876-event adapter timing
  study's 77 % LATE is a fact about the path without the sweep gate and is NOT
  evidence for or against OPT-B.
* **PnL / expectancy claims** — none of the cited measurements supports any.
  These are confirmation-geometry event counts, not trades.

## 6. NEXT research (name only — NOT started by this task)

**Architect branch B: "confirm completion vs zone on the traded path."**
Design/survey only, to be commissioned by a separate prompt. This task does not
design, scope, or implement it — it only names it as the single next
research direction, per the freeze directive.

---

## Reproduce / verify

```
config flag:        Select-String -Path config\live_demo.json -Pattern opt_b   → false
default:            OperatorConfig().enable_opt_b_same_bar_confirm == False
wider measure note: 06_RESEARCH/OPT_B_WIDER_MEASURE_NOTE.md
artifacts:          06_RESEARCH/results/opt_b_confirm_wider/
```

Governance synced 2026-11-07: `SESSION_HANDOFF.md`, `POST_V1_ACTIVE_TODO.md`,
`CHANGELOG.md`. `locked_constants.py` diff empty; no `04_SRC/**` edit.
