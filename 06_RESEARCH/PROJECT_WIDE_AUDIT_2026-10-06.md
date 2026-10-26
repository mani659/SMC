# PROJECT-WIDE INDEPENDENT AUDIT — SMC BOT (POST PAPER OPS)

**Directive:** Lead Architect, 2026-10-06 (audit before commit/push)
**Auditor:** Buffy (Codebuff). **Independence caveat (disclosed, not hidden):**
this is the same agent session that implemented the recent chain
(console, W1 provisioning, L2 ledger). Mitigations applied: every finding is
grounded in mechanism-level code reads, live grep sweeps, or ops artifacts —
not the implementing agent's claims; the decision-path look-ahead audit
(`06_RESEARCH/LOOKAHEAD_BIAS_AUDIT_NOTE.md`) was already produced and its
mechanisms re-verified here independently. For maximum independence the
Architect may run this report's checks again in a fresh session; the report
is written so that every claim is reproducible with one command.

**Suite:** 853 passed, 0 failed, 0 skipped/xfail (`-rs` showed no skips),
exit 0, 2.7 s.

---

## EXECUTIVE VERDICT

The product decision path is **sound, conservative, and honestly
documented**. Architecture fidelity to the flowchart (HTF POI → sweep →
LTF confirm → plan → risk → manage) is high and implemented in one frozen
composition, not parallel stacks. The governance discipline (locked
constants, dated rulings, diagnostic-only labeling) held under load: the
fastest-growing risk — prompt-driven threshold creep — was checked three
times this session and held every time. **Commit readiness: YES with
caveats** — the caveats are repository-hygiene decisions (90 MB untracked
results tree), not code defects.

---

## FINDINGS TABLE

| # | Sev | Finding | Evidence | Action |
|---|-----|---------|----------|--------|
| 1 | **Major** | `06_RESEARCH/results/` is 90 MB, 773 files (361 png, 264 json, 128 csv, 4 pdf), **untracked and never committed in HEAD** (0 files tracked). Not gitignored either — one careless `git add -A` would bloat the repo permanently. | `git ls-files 06_RESEARCH/results` = 0; du breakdown | Decide policy **in the commit prompt** (see §F) |
| 2 | Minor | F3 (look-ahead audit): Pillar-1 mitigation suffix is prefix-safe **by upstream convention only** — no assertion enforces series-trimmed-to-as_of. | `pillar_1_zone_refinement._mitigated` reads `candles[active_index+1:]`; trimming verified at all 3 batch call sites | Ruling already approves cheap hardening; **recommend include** as test-level guard in the commit sequence (post-paper condition now met) |
| 3 | Minor | Interim constant `STRUCTURAL_TP_MIN_ATR = 0.25` lives module-level in `pipeline_bridge.py`, not in `locked_constants.py` (Architect-accepted interim; pending formal § lock). | `pipeline_bridge.py`; structural TP notes | Defer — needs a dated ruling to lock; documented |
| 4 | Minor | Operator board mirrors §28.5 spread-gate ceilings with inline literals (`0.15 * atr * m` grades A+/A/B/C) — display-only, but a drift risk if §28.5 ever changes. | `run_operator._on_poll` (annotated display-only) | Defer — add "mirrors RiskEngine" comment already present; optional future dedup |
| 5 | Minor | `config/live_demo.json` and `config/live_console_dryrun.json` share `heartbeat_path` (`logs/phase_d/heartbeat.txt`) — harmless single-terminal, wrong if sessions ever overlap. | Config diff | Defer or split path in a later ops tweak |
| 6 | Info | Mixed line endings (LF/CRLF) across `04_SRC` — git warns on touch. Pre-existing, cosmetic. | `git diff` warnings | Defer |
| 7 | Info | Watchdog EA chart-attach still BLOCKED (GUI-only) — honestly recorded in every ops note; stale-heartbeat drill pending. | Phase D + paper ops notes | Owner GUI task |
| 8 | Info | Independence caveat of this audit (§ header) — reproducible checks mitigate. | This file | Optional fresh-session re-run |
| 9 | Info | `W1 = 32769` MT5 contract — verified live (300 W1 bars fetched via `copy_rates_from_pos`); enum docstring records the 32768 trap; pin strengthened. | timeframe.py + probe output | None |
| 10 | Info | Look-ahead: **no decision-path findings** beyond the accepted note (F1–F4 stand as documented; F2/F3 unchanged). Re-verified: runner order expiry→fills→scan→placement; bar-B placement cannot fill on B; prefix caps at decision bar; folds == prefix identity. | LOOKAHEAD_BIAS_AUDIT_NOTE.md + this audit's greps | None |

**Critical: 0 · Major: 1 (repo hygiene, not code) · Minor: 4 · Info: 5**

---

## A. ARCHITECTURE FIDELITY

Flowchart intent → code reality:

- **HTF POI (W1/D1/H4/H1) → sweep → LTF confirm → plan → risk → manage:**
  implemented as ONE composition (`MultiTFProductRuntime` → engine →
  adapter → runner → risk), used identically by research funnels, paper,
  and live (contract §2). No second detection stack exists — the recent
  chain (console, ledger, sweep links) extended existing seams only.
- **Modularity:** clean seams (`DetectionDriver`, `PipelineAdapter`,
  `fill_model` pure functions, `structure_console` pure snapshot+render).
  Coupling points are documented in docstrings (adapter↔runner protocol,
  engine sole §5 authority).
- **TF roles:** W1/D1/H4/H1 detection-context vs M5 execution enforced in
  code (`is_htf`, runtime required/optional sets, `check_single_tf_detect_exec`,
  loud `MissingHtfSeriesError`). M8 scans W1/D1/H4 with D1×H4 overlap pairing
  frozen (W1 excluded from scoring by design).

## B. DECISION-PATH INTEGRITY

- Look-ahead: **CONFIRMED CLEAN** — cite the existing audit note; this
  audit re-verified its four mechanisms (bar ordering, placement-after-
  fills, prefix caps, fold identity) and found nothing new.
- Sizing: single path (`sized_lots` via RiskEngine); one risk engine owns
  §28 gates; `tp_source` and posture are audit-only (test-enforced no-read).
- Fill/placement: conservative and tested (touch=fill at limit, SL-first,
  bar-B placement cannot fill on B).

## C. LIVE/OPS INTEGRITY

- Console ↔ armed: fixed (batch-change immediate rebuild) and **proven
  under live ops** (paper session 2026-10-06: 39/39 boards matched, zero
  lag); header armed counter prevents silent divergence.
- dry_run/DEMO gates: config-enforced (`require_demo`, `dry_run`);
  identity gate verified in 5 sessions this date.
- Symbol-from-config: engine requests configured symbol (verified: XAUUSDm
  while chart irrelevant).
- Watchdog: publisher healthy; EA attach BLOCKED (GUI-only) — residual
  honestly recorded, owner task.

## D. RESEARCH HONESTY

- Every diagnostic artifact reviewed carries "diagnostic only / NOT edge"
  language; n stated (n=2, n=3); no expectancy claims found in any tracked
  or untracked note sampled.
- Setup ledger human columns blank by design (script never pre-fills);
  DATA_GAP rows labeled, not inferred.
- Prompt-bias channel: controlled (numbers in prompts treated as review
  metrics; no threshold adopted without ruling). The audit's earlier
  warning stands: this remains the main bias channel — the standing rules
  are the defense.

## E. TEST & CONSTANTS DISCIPLINE

- Suite: 853/853, no skips/xfail, deterministic (~3 s).
- `locked_constants.py` diff EMPTY across the entire accepted chain
  (verified repeatedly by exit-status check).
- Thresholds outside locked_constants: `STRUCTURAL_TP_MIN_ATR` (interim,
  ruling-pending — finding #3) and the display mirror (finding #4). No
  other hardcoded trading thresholds found in `risk/`, `validation/`,
  `triggers/`, `backtest/`.
- W1=32769: code, docstring, test pin, and live MT5 fetch all agree.

## F. COMMIT READINESS — YES_WITH_CAVEATS

- **Secrets: none found** (sweep of config/, live/, .md — only a comment;
  gitignore covers `*.env`, `credentials*`, `*.key`, `*.pem`).
- **Large data:** `07_DATA/`, `logs/`, `*.parquet` ignored — good.
- **The 90 MB question (finding #1):** established practice = results/
  local-only (HEAD tracks zero results files). Recommended policy, pick
  one in the commit prompt:
  1. **(Recommended)** Add `06_RESEARCH/results/` to `.gitignore` (makes
     the existing convention explicit), commit notes/summaries that live
     OUTSIDE results/ (already the pattern), and additionally commit the
     small, high-value summaries (e.g. `setup_identification_ledger/
     summary.json`, `setups.csv` ≈ 4 KB) as a curated exception.
  2. Curated artifacts commit: results summaries + a few key PNGs only
     (no events.jsonl, no gallery HTML, no bulk CSVs).
  3. Never track results (status quo) — acceptable but leaves the trap.
- **Recommended commit split (3 commits, no monolith):**
  1. `04_SRC` product code + tests (console fix, W1=32769 + pins, W1
     provisioning seams, L1 console + sweep seams, refresh policy tests).
  2. `06_RESEARCH` notes + scripts + `06_RESEARCH/PROJECT_WIDE_AUDIT_*`
     + config `live_console_dryrun.json` (research/ops records; no bulk
     data).
  3. `00_LOCKED` governance (handoff/todo/changelog) — or fold into (2);
     keep (1) pure so a revert of docs never touches code.
- **Never commit:** `07_DATA/`, `logs/`, `02_KNOWLEDGE_BASE/`,
  `03_REFERENCE_CODE/` (proprietary), `ARCHIVE/`, `.freebuff/` — all
  already ignored.

## G. MUST-FIX BEFORE COMMIT vs CAN DEFER

| Rank | Item | Verdict |
|------|------|---------|
| 1 | Results/ policy (finding #1) | **Decide before commit** (one line in commit prompt) — blocks a clean commit |
| 2 | F3 prefix guard (finding #2) | **Include** as small pre-commit test-level hardening — Architect pre-approved ("after paper" condition met); ~20 lines + test, zero behavior change |
| 3 | W1=32769 | Already done — include in commit (1) |
| 4 | STRUCTURAL_TP_MIN_ATR lock (finding #3) | **Defer** — needs its own dated ruling |
| 5 | Gate-mirror dedup, heartbeat path split (findings #4/#5) | **Defer** — ops polish |
| 6 | Line endings (finding #6) | **Defer** — cosmetic |

---

## RETURN BLOCK

```
AUDIT_STATUS: PASS
SUITE: 853 passed / 0 failed / 0 skipped
LOOKAHEAD: CONFIRMED_CLEAN
CRITICAL: 0
MAJOR: 1 (repo hygiene: results/ 90 MB untracked-and-unignored — policy decision, not code)
COMMIT_READY: YES_WITH_CAVEATS
TOP_3_ACTIONS: [1. decide results/ tracking policy + gitignore line before commit; 2. include F3 test-level prefix guard as pre-commit hardening (ruling pre-approved); 3. 3-commit split: src+tests / research+config / governance]
REPORT_PATH: 06_RESEARCH/PROJECT_WIDE_AUDIT_2026-10-06.md
LOGIC_CHANGED: NO
```
