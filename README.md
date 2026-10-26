# SMC — Smart Money Concepts Trading System (Gold / XAUUSD)

A quantitative research and execution system for **Smart Money Concepts (SMC)** trading on **XAUUSD (Gold)**, built in Python with an MQL5 deployment target.

The project spans the full lifecycle: scientific research with strict out-of-sample discipline, a deterministic backtest engine, and a live MT5 execution layer — all governed by a formal milestone and qualification framework.

---

## Project Structure

```
SMC/
├── 00_LOCKED/            Frozen specifications, locked decisions, development plan, changelog
├── 01_ARCHITECTURE/      System architecture docs, state tracking, session handoffs, n8n workflows
├── 02_KNOWLEDGE_BASE/    Visual chart library (POI models, OB/FVG, CHOCH, sweeps) — reference material (not in git)
├── 03_REFERENCE_CODE/    Legacy/reference MQL5 expert advisors and helper scripts
├── 04_SRC/               Main Python source: smc/ package + test suite
├── 05_MQL5_SAFETY/       MQL5 Safety Watchdog EA (heartbeat + emergency flatten only)
├── 06_RESEARCH/          Research results, experiments, validation artifacts, methodology records
└── ARCHIVE/              Historical artifacts: old reports, superseded docs, MQL5 history (not in git)
```

### Source layout (`04_SRC/smc/`)

| Package        | Responsibility |
|----------------|----------------|
| `core/`        | Core types, enums, locked constants |
| `data/`        | Market data feeds, multi-timeframe feed handling |
| `detection/`   | Structural detection: swings, BOS/CHOCH, FVG, order blocks, liquidity sweeps, RSI, ATR |
| `poi/`         | Point-of-Interest (POI) models 1–8, freshness state machine, zone refinement |
| `triggers/`    | Entry triggers A–F (CHOCH, diagonals, two-bar, RSI divergence, BOS+OB) and routing |
| `validation/`  | Validation pipeline: displacement, premium/discount, inducement, confluence, guards |
| `orchestration/` | `PipelineEngine` — detection → validation → trigger routing |
| `risk/`        | Risk engine: entry gating, lot sizing, circuit breaker |
| `execution/`   | Order manager, position manager, session filter, news guard |
| `backtest/`    | Deterministic backtest: clock, data feed, fill model, orders, positions, bar loop, runner |
| `live/`        | MT5 connector and live integration |
| `paper/`       | Paper trading runner |
| `logging/`     | Structured logging |
| `config/`      | Configuration |
| `utils/`       | Shared utilities |

Tests live in `04_SRC/tests/` (pytest).

---

## Research Programme

The research side follows a strict qualification hierarchy — no module reaches deployment without passing each level:

```
Level 1: Scientific Effect      — does the phenomenon exist?
Level 2: Economic Candidate (M3) — E[R_net] > 0 after costs
Level 3: Validated Module (M4)   — out-of-sample validation
Level 4: Deployment Candidate
```

Completed research cycles (see `01_ARCHITECTURE/SMC_STATE.json` and `06_RESEARCH/`):

- **BOS+OB**: gross +1.01 bps/event over 123,386 events — failed M4 qualification (net < 0 under M1 cost architecture). Programme closed (R1–R7).
- **CHOCH**: gross +0.89 bps/event over 7,483 events — failed M3 qualification. Cycle closed (R8–R9-CR).
- **R10/R11**: qualification framework and rare-event module governance established.

Key preserved findings and governance rules are documented in `01_ARCHITECTURE/SMC_SESSION_HANDOFF.md`.

### Canonical dataset

- Instrument: XAUUSD, Timeframe: M1, Timezone: UTC
- Source: `m1_clean.csv` — 1,768,123 bars, 2021-04-12 → 2026-04-10

---

## Development Phases (Current Cycle)

Implementation proceeds through locked milestones (see `00_LOCKED/DEVELOPMENT_PLAN.md`):

| Phase | Scope |
|-------|-------|
| Phase 0–5 | Core types, detection, POI models, triggers, validation, risk, backtest engine — frozen |
| Phase 6 M1–M3 | Multi-TF feed, pipeline detection, backtest runner — accepted (458 tests green) |
| Phase 6 M4 | PipelineEngine → backtest integration: real detection → risk-gated pending limits, POI/trigger identity, FVG capture (467 tests green) |
| Phase 6 M5 | Core reports: trade list, metrics (PF/DD/win-rate), per-trigger & per-POI breakdowns, blocked-entry counts, CSV/JSON export (481 tests green) |
| Phase 6 M6 | Paper runner + broker adapter + operational KPI logging over the live execution layer (496 tests green) |
| Phase 7 | Live readiness: `smc/live/` (LiveConfig, heartbeat publisher + watchdog decision, `LiveLoop` over the full stack) + `05_MQL5_SAFETY/SMC_Safety_Watchdog.mq5` (heartbeat monitor + emergency flatten only) — 519 tests green |

---

## Getting Started

### Prerequisites

- Python 3.11+ (3.12 recommended)
- pytest
- MetaTrader 5 (only for the `live/` path — backtests are MT5-free and deterministic)

### Run tests

The test suite bootstraps `04_SRC` onto `sys.path` itself, so no package install is required:

```bash
cd 04_SRC
pytest tests/ -q
```

### Using the package in code

Add `04_SRC` to `sys.path` (or set `PYTHONPATH=04_SRC`) and import as `smc.*`:

```python
from smc.orchestration.engine import PipelineEngine
```

---

## Design Principles

1. **Determinism first** — backtests are reproducible bar-for-bar; injected clock, no wall-time dependence.
2. **MT5-free backtests** — the backtest path never touches live MT5; execution is simulated by the fill model.
3. **Locked decisions** — frozen specifications in `00_LOCKED/` are not reopened without a documented reason.
4. **Honest data** — if context (e.g., FVG geometry) cannot be derived honestly, it is left absent rather than invented.
5. **Responsibility separation** — Pipeline finds/validates/routes, RiskEngine gates/sizes/manages, backtest stores apply fills and closes.

---

## Notes

- `02_KNOWLEDGE_BASE/` (chart image library) and `ARCHIVE/` are excluded from version control to keep the repository lean; they remain part of the local project workspace.
- Large research data files (e.g., per-trade CSVs, raw extraction dumps) are also excluded — see `.gitignore`.
