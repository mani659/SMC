# F3 — SIZING PINNED TO THE BROKER (money safety)

**Status: PASS (code + tests). Live acceptance pending the next operator start.**
Authority: Lead Architect, `F3 — PIN SIZING TO BROKER`, 2026-11-09, on top of
`bfbb6c9` (F1/F2). `LOGIC_CHANGED: NO` for research geometry; the only decision
change is the live **start gate** (refuse to run on a unit mismatch) plus the
plumbing that lets the operator's value actually reach the sizing path.

---

## 1. Defect (as audited)

The §28.7 formula is `lots = (equity × risk%) / (sl_distance × unit_value)`.
`unit_value` must be **account currency per 1.0 PRICE unit per 1.0 lot**. The
live path never received one: `LiveConfig`/`PaperConfig` defaulted to `10.0`
and `OperatorConfig` did not even have the key, so the live run silently used
the paper default. For a standard XAUUSD contract (100 oz) the true value is
`100.00`, i.e. the configured value was **10× too small** and would size 10×
too large if the cap ever stopped masking it.

Worked example (equity 10,000, 1 % risk, gold at 100.00/price-unit/lot):

| SL distance | Correct units (100.0) | Pre-F3 (10.0) |
|---|---|---|
| $5   | 0.10 lots capped from 0.20 → **real risk 0.50 %** | 0.10 lots, reported 0.05 %, **real 0.50 %** |
| $20  | 0.05 lots → **1.00 %** | 0.10 capped, reported 0.20 %, **real 2.00 %** |
| $50  | 0.02 lots → **1.00 %** | 0.10 capped, reported 0.50 %, **real 5.00 %** |

Read the last two rows: pre-F3 the book carried 2–5 % risk while the code
believed it carried 0.2–0.5 %. That is the 10× error the audit suspected, and
it is invisible in `risk_fraction` alone.

## 2. Derivation (`04_SRC/smc/risk/broker_units.py`)

Pure module, no MetaTrader5 import; any object exposing `symbol_info` fields
works. Nothing is guessed — there is no per-symbol table and no gold default.

1. **Tick path (preferred):** `trade_tick_value_loss / trade_tick_size`
   (loss side first — that is the side a stop is charged on), else
   `trade_tick_value`, else `trade_tick_value_profit`. MT5 already reports
   these in account currency, so no FX assumption is introduced.
   Gold 100 oz: `1.00 / 0.01 = 100.00`.
2. **Contract path (fallback):** `trade_contract_size`, accepted **only** when
   `currency_profit` equals the account currency; a different profit currency
   is refused because the conversion is missing.
3. **Nothing usable → refuse.** `symbol_info=None`, zero tick size/value and
   zero contract size all raise `BrokerUnitsError`; sizing without a verified
   unit is exactly the defect this task closes.

## 3. Pin (start gate)

`check_sizing_pin(configured, units)` compares the configured value with the
derived one; **tolerance 1 % relative** (`SIZING_PIN_TOLERANCE_REL`). A unit
error is 900 %, so 1 % is tight without being brittle against broker rounding.

`OperatorSession.identity_check()` now calls `_verify_sizing_pin` after
`symbol_select` and before anything can size a trade:

* **mismatch / unreadable spec → `SystemExit`** with both numbers and the
  derivation (`ABORT: SIZING PIN MISMATCH: configured=10 derived=100 …`);
* **pass →** `SIZING PIN OK: …` in `events.log`, a `[sizing] PASS — …` console
  line, a machine-readable `logs/<run>/sizing_pin.json`, and
  `state["sizing_pin"]`;
* **nothing is overwritten.** A wrong configured value stays visible in the
  repo config and blocks the session; there is no auto-correct and no bypass
  flag, and it applies in `dry_run` too (a dry run with wrong units teaches the
  wrong lesson).

## 4. Plumbing

| File | Change |
|---|---|
| `smc/live/operator_config.py` | `pip_value_per_lot` is an ALLOWED key (documented as a broker fact, not a threshold) with positive-number validation; live default `100.0` (standard XAUUSD contract) replacing the inherited `10.0`. |
| `smc/live/run_operator.py` | start gate `_verify_sizing_pin`; `PaperConfig(pip_value_per_lot=cfg.pip_value_per_lot)` — previously `cfg` was ignored here. |
| `config/live_demo.json` | `"pip_value_per_lot": 100.0` declared explicitly (verified against the terminal at start; refusal if the broker disagrees). |
| `smc/risk/lot_sizing.py` | `sized_lots_detail` — the ONE computation now also returns `uncapped_lots`, `capped`, `effective_risk_fraction`; `sized_lots` is a thin reader of it (no second formula, no second cap). |
| `smc/risk/risk_engine.py` | `EntryDecision` carries `sizing_capped`, `effective_risk_fraction`, `uncapped_lots` (logging only, never read by a later gate). |
| `smc/paper/runner.py` | `_record_sizing` at the accepted-size choke point + `sizing_kpi()`; KPI event `entry_sized` carries `lots`, `uncapped_lots`, `sizing_capped`, `effective_risk_pct`. |

Research/backtest defaults are untouched (`RunnerConfig.pip_value_per_lot =
10.0` stays, so the frozen baseline keeps its exact numerics and is not
re-explained by this task).

### Incidental fix required for pin evidence

The operator logger name was `smc.operator.{id(self)}`; CPython recycles `id()`
of freed sessions, so a later session could inherit an earlier session's file
handler and never create its own `events.log` (the pin line would land in a
stale file). The logger name is now sequence-based (`_SESSION_LOGGER_SEQ`), so
every session owns its handler. Found because the new F3 tests construct
several sessions in one process.

## 5. Tests (`04_SRC/tests/test_f3_sizing_pin.py`, 19)

Derivation: gold 100 oz → 100.00 via the tick path; loss-side tick value
preferred; contract fallback with matching currency; refusal on currency
mismatch / unknown account currency / unusable spec / `None` info.
Pin: pass on exact and at the 1 % edge; refuse the 10× error with both values
in the message; refuse 1.5 % and non-positive.
Sizing KPI: cap-binding case (`0.20 → 0.10`, real risk 0.50 %), uncapped case
(1.00 %), `sized_lots == sized_lots_detail().lots`, `RiskEngine` decision
fields, runner aggregation + `entry_sized` payload.
Config/gate: key accepted and validated; `identity_check` refuses on mismatch
(log contains `SIZING PIN MISMATCH`) and writes `sizing_pin.json` on pass;
refuses when `symbol_info` is unreadable.

Suite: **1413 passed, 6 skipped** (`--ignore=test_review_merge_smoke.py`; was
1394/6).

## 6. Not done / open

* **No live terminal in this session** — the pin has not run against the real
  `XAUUSDm` spec yet. `dry_run: true` stays until the operator starts once and
  `sizing_pin.json` shows `ok: true` (that start is the live acceptance
  evidence; a mismatch is the intended, loud refusal).
* `LOT_MAX_SAFETY` (0.10) still binds on tight stops, so effective risk can sit
  **below** the 0.5 % band floor (0.50 % at a $5 stop). That is a §28.7 policy
  question (risk envelope = F4), not a units bug — now visible in the KPI
  instead of hidden.
* FX/cross-currency symbols rely on MT5's tick values; a symbol with no tick
  value and a non-account profit currency refuses (never converted by guess).
* F4 risk envelope, F5 `t_arm`/expire ordering, F6 §5 gate, F7 menu retry all
  remain open; structural TP on the menu and paper expectancy stay on hold.
