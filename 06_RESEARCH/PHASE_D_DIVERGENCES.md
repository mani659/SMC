# PHASE D — DIVERGENCES: LIVE/PAPER OPS vs BACKTEST ASSUMPTIONS

**Phase:** D (ops validation only — not profitability proof)
**Terminal:** `C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe` (identity-verified)
**Account:** 474608655 @ Exness-MT5Trial15 — **DEMO**, USD, leverage 2000
**Symbol:** `XAUUSDm` (Exness standard; digits=3, point=0.001, filling FOK+IOC, volume 0.01–200.0 step 0.01)
**Session date:** 2026-09-19 (Saturday — FX market closed; bar-cycle + order-send validation deferred to next open session)

---

## 1. THE headline divergence: the spread gate is an ATR-regime property

Phase C's ladder read as "the §28.5 gate kills the system at retail spread"
(0.35 constant → 0 trades on the 2023 window). Phase D's live probe reads as
"the gate passes everything" (0.26 constant, 100% pass for every grade).
**Both are correct** — because the gate is `0.15 × ATR × grade_multiplier`,
its bite depends on the ATR regime, not the spread level alone.

Measured facts (artifacts: `results/phase_d_ops/`):

| Quantity | Value | Source |
|---|---|---|
| Live spread (60 samples, 2 min) | **0.260 constant** (min=p50=max) | `spread_samples_live.csv` |
| Friday 14:00–16:00 tick spread (32,775 ticks) | p10 0.26 / p50 0.26 / p90 0.26 / p99 0.26 / max 0.26 | `phase_d_ops_session.json` |
| Friday 20:00–20:57 tick spread (5,578 ticks) | identical — 0.260 flat | `phase_d_ops_session.json` |
| Current M5 ATR(14) | **≈ 3.749** | live bars, `phase_d_ops_session.json` |
| Gate max per grade at ATR 3.749 | A+ 0.843 / A 0.562 / B 0.394 / C 0.281 | computed |
| Pass fraction at 0.26 | **1.0 for every grade** | computed |

**Regime law** (`phase_d_gate_regime_check.json`): with spread fixed at the
measured live 0.26, the gate stops passing a grade when ATR falls below:

| Grade | ATR threshold (spread 0.26) |
|---|---|
| A+ (×1.5) | **1.156** |
| A (×1.0) | **1.733** |
| B (×0.7) | **2.476** |
| C (×0.5) | **3.467** |

At **every 2023 month-end** the M5 ATR was 0.30–1.06 ⇒ gate ceiling for a
C-grade setup was **0.02–0.08** ⇒ the live 0.26 (and a fortiori the ladder's
0.35) would have blocked **every grade, all of 2023**.

**Consequences for interpretation:**

1. The Phase C ladder's "0 trades at 0.35" is a special case of this law in a
   low-ATR regime — it does NOT mean "the system cannot trade at retail
   spreads" universally, and it does NOT mean the gate is harmless.
2. In the CURRENT regime (ATR ~3.7), the gate passes everything at 0.26 —
   the operative live constraint today is elsewhere (§28.7 lot cap binds
   100% of trades per Phase C), not the spread gate.
3. Any "spread gate blocks most/all candidates" statement must therefore be
   parameterized by **(spread, ATR regime)**, never by spread alone.
4. No locked constant may be changed as a result (Phase D constraint). This
   log records the divergence; it does not propose re-locks.

---

## 2. Broker/symbol facts vs backtest assumptions

| Assumption (backtest) | Live observation | Divergence? |
|---|---|---|
| Symbol "XAUUSD variant" | `XAUUSDm` (visible); `XAUUSD247m` also exists (hidden) | Exact name differs from the default `XAUUSD.x` wiring constant — configs must pin `XAUUSDm` |
| 2-point/3-digit price grid | digits=3, point=0.001 | Consistent with Phase C data (0.001 grid) |
| Filling mode flexibility | `filling_flags=3` → **FOK and IOC both accepted** (order_check retcode 0 for both) | None at payload level; live acks pending open market |
| Volume model | min 0.01 / step 0.01 — 0.10 lots placeable | Consistent; §28.7 cap (0.10) is executable |
| Spread distribution | **Constant 0.26** in every sampled window — not stochastic | Divergent from any stochastic-spread assumption; favorable for constant-spread backtests at 0.26 |
| Trade mode | `trade_mode=4` (full) | None |

## 3. Session/loop observations (Saturday idle session)

- 60 polls in 2 min, **0 errors, 0 new bars** (market closed — expected);
  the loop's cold-start anchor worked as designed (no history replay).
- Heartbeat: 60 publishes at 1 s interval + shutdown marker (seq 61);
  `is_stale` flips exactly at the 5 s timeout (4 s fresh / 6 s stale) —
  mirrors `InpStaleTimeoutSec=5`.
- KPI counters all zero as expected (no bars → no cycles) — logger verified
  live-writable (`kpi_records.jsonl`).
- Live spread sampled every poll: constant 0.26 (logged).

## 4. Order-path status (payload-validated only — market closed)

- Pending-limit payload (BUY_LIMIT 0.10 @ bid−5.0, SL 3.0 below, TP 6.0
  above, magic 20260919): **order_check retcode 0 ("Done")**, FOK and IOC.
- NOT yet exercised against the broker (requires open market):
  place / cancel / SL-modify-preserves-TP / close.
- `trade_allowed=False`: terminal Algo Trading toggle is OFF — must be
  enabled before any order_send test (GUI step).

## 5. Watchdog deployment state

- `SMC_Safety_Watchdog.mq5` deployed to
  `<terminal data>\MQL5\Experts\` and compiled via metaeditor64:
  **0 errors, 0 warnings** (`SMC_Safety_Watchdog.ex5`, 13,402 bytes).
- Heartbeat file format round-trips to the terminal's
  `MQL5\Files\smc_heartbeat.txt` sandbox (read back identical).
- Pending GUI steps (cannot be done from the Python API):
  1. attach the EA to any XAUUSDm chart with
     `InpHeartbeatFile=smc_heartbeat.txt`, `InpSymbolFilter=XAUUSDm`,
     `InpMagicFilter=20260919`;
  2. enable Algo Trading;
  3. observed live: stale heartbeat → scoped emergency close/cancel
     (next session, with a deliberately stopped Python process).

## 6. Deferred to the next open session (Mon 2026-09-21)

| Item | Blocking condition |
|---|---|
| Bar-cycle detection→arm→risk session with live M5 bars | market open |
| Order ops place/cancel/SL-modify/close (0.10 lots, magic 20260919) | market open + Algo Trading ON |
| EA attach + stale-heartbeat emergency drill | GUI attach |
| KPI decision/ack latencies under live bars | market open |
| Follow-up spread distribution across a full trading day | market open |

## 7. Artifacts

- `results/phase_d_ops/phase_d_ops_session.json` — identity, session, spread, order-path
- `results/phase_d_ops/spread_samples_live.csv` — 60 live tick spreads
- `results/phase_d_ops/kpi_records.jsonl` — KPI logger output (empty cycle set)
- `results/phase_d_ops/order_check_results.json` — payload validation detail
- `results/phase_d_ops/phase_d_gate_regime_check.json` — ATR-regime gate law
- `results/phase_d_ops/smc_heartbeat.txt` — heartbeat file (running + shutdown states)
- `<terminal data>\MQL5\Experts\SMC_Safety_Watchdog.{mq5,ex5}` — deployed EA

## 9. HTF product-runtime probe (2026-09-24, market open, dry_run)

**Scope:** C1 contract §3.4/§5.5–5.6 infrastructure proof on the REAL EXNESS Copy terminal —
NOT strategy validation, NOT edge evidence, zero PnL interpretation. Script:
`06_RESEARCH/scripts/phase_d_htf_probe.py` (full production code, no stubs; operator config
`config/live_demo.json`, magic 20260919, `dry_run=true` throughout).

- **Identity: PASS.** Bound to `C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe`
  (dir MATCH), DEMO 474608655 @ Exness-MT5Trial15, XAUUSDm selected, `trade_allowed=True`
  (Algo Trading ON), MT5 python pkg 5.6182 (5 Sep 2026).
- **HTF probe: PASS (product mode, `allow_single_tf_degraded=False`).** Broker-side H4/H1/D1
  availability confirmed via the same `copy_rates` path the live batches use:
  **H4=300** (2026-07-20→09-24 12:00 UTC), **H1=300** (2026-09-07→09-24 12:00 UTC),
  **D1=300** (2025-10-09→09-24) — `missing_series=[]`; `LiveLoop.start()` probe returned
  True, consistent with the product contract (start would REFUSE on missing H1/H4).
- **Degraded smoke: PASS.** With the explicit opt-in flag on a fresh runtime, the batch ran
  against an empty series dict and the report carried the loud stamp:
  `degraded=True`, reason `"allow_single_tf_degraded=True (tests only) — missing: H4, H1"`,
  `missing=[H4, H1]` — never silent. (Probe-script fix during the run: `copy_rates` returns a
  numpy record array — `raw or []` raises 'truth value of an array is ambiguous'; the probe
  now uses `list(raw) if raw is not None else []`. Probe-script-only; no smc/ change.)
- **dry_run loop: PASS.** 60 s bounded window: 120 polls, 0 unhandled errors, 0 arm errors,
  heartbeat published + clean shutdown marker; 1 earlier probe run processed 1 new M5 bar with
  1 H1-cadence batch, 0 errors. 0 orders sent (dry_run), 0 KPI decisions (no signal in window).
- **Watchdog EA: BLOCKED (unchanged).** .ex5 deployed 2026-09-19; chart-attach is GUI-only and
  remains unconfirmed — stale-heartbeat emergency drill still pending.
- **Divergences vs contract: NONE found.** The product start probe, loud-fail policy, and
  degraded stamping all behaved per `PRODUCT_RUNTIME_CONTRACT.md` §3 on live broker data.
- **Artifacts:** `06_RESEARCH/results/phase_d_htf_probe/` — `identity.json`,
  `probe_summary.json` (status PASS), `events.log`, `smc_heartbeat.txt`.
- **Suite:** 737 passed (no smc/ source change in this probe).

## 8. Open-market session Mon 2026-09-21 ~10:28-10:40 UTC (first live sends)

Terminal: Copy terminal auto-launched by initialize() (main EXNESS terminal was the only running process); identity MATCH, DEMO 474608655, equity 10000.0, trade_allowed=True (Algo Trading ON � no longer a blocker). Market OPEN (live XAUUSDm 4350-4351, spread 0.26 constant).

### Order drill � full path proven live (script phase_d_order_drill.py, --live)
- Precheck flat (0 positions / 0 pendings, own magic clean).
- BUY_LIMIT 0.01 @ bid-5.0 (ticket 2410290900) -> visible -> cancel OK (10009).
- Market BUY 0.01 @ 4350.394 (deal 2227159186) -> SL/TP bracket set -> SL modify 4348.394->4349.394 with **TP preserved at 4354.394** (mirrors the M3/M4 modify-preserves-TP rule on the live broker) -> close OK -> flat (0/0).
- Backtest-assumption comparison: fills at requested price (no slippage observed on 0.01 lots); same-bar SL-first untested (no same-bar event); rejects: none (retcode 10009 throughout); IOC filling accepted.
- Log: results/phase_d_ops/order_drill_20260921T*.jsonl.

### Live bar-cycle via operator pack (dry_run, --max-seconds 360)
- 714 polls, 1 new M5 bar processed, 1 KPI decision, 0 errors, clean shutdown. First live decision logged (0 placed).
- Startup banner renders correctly on the Windows console (ASCII art verified).

### Spread x ATR, live (M5 ATR(14) = 3.851, spread 0.26)
- Gate ceilings: A+ 0.867 / A 0.578 / B 0.404 / C 0.281 � **PASS on every grade**, including C (0.26 < 0.281, thin margin 0.02).
- Regime confirmation of the ATR law (�1): high-vol regime admits retail spread at all grades today; the 2023 all-blocked finding stands for low-ATR regimes. C-grade margin is thin � spread widening past 0.29 would start blocking C first.

### Still GUI-blocked (unchanged)
- Watchdog EA .mq5/.ex5 present in terminal data dir (deployed 9/19) but chart-attach is GUI-only and unconfirmed ? stale-heartbeat emergency drill still pending.
