# SMC Zero-Lag Event-Driven Pipeline — N8N Workflow Implementation Guide

**Date:** 2026-09-05  
**Canonical Workflow File:** [`SMC_Zero_Lag_Pipeline_n8n_workflow.json`](file:///d:/Gold%20Scripts/MQL5/SMC/SMC_RESEARCH/SMC_Zero_Lag_Pipeline_n8n_workflow.json)  
**Specification Sources:** [`SMC_WORKFLOW_ORCHESTRATION.md`](file:///d:/Gold%20Scripts/MQL5/SMC/SMC_RESEARCH/SMC_WORKFLOW_ORCHESTRATION.md) & [`LOCKED_DECISIONS.md`](file:///d:/Gold%20Scripts/MQL5/SMC/SMC_RESEARCH/LOCKED_DECISIONS.md)  
**Status:** PRODUCTION-READY (Passes all 17 benchmark items)

---

## 1. Overview & Quick Import

The workflow file [`SMC_Zero_Lag_Pipeline_n8n_workflow.json`](file:///d:/Gold%20Scripts/MQL5/SMC/SMC_RESEARCH/SMC_Zero_Lag_Pipeline_n8n_workflow.json) contains the complete, valid, 23-node event-driven pipeline implementing all 8 levels (L0 to L7) of the Gold SMC quantitative trading system.

### How to Import into N8N:
1. Open your **n8n UI** (local or cloud instance).
2. Go to **Workflows** &rarr; click the **`...` (Options menu)** in the top right &rarr; select **Import from File**.
3. Select [`d:\Gold Scripts\MQL5\SMC\SMC_RESEARCH\SMC_Zero_Lag_Pipeline_n8n_workflow.json`](file:///d:/Gold%20Scripts/MQL5/SMC/SMC_RESEARCH/SMC_Zero_Lag_Pipeline_n8n_workflow.json) (or copy-paste its raw JSON content).
4. All 23 nodes and their connections will render automatically on the canvas.

---

## 2. Node Graph Topology (23 Nodes Across L0–L7)

```text
[Webhook: Bar Closed]  ──┐
[Webhook: Tick Quote]  ──┼──▶ [L0 Normalizer & Dedup] ──▶ [Redis Idempotency] ──▶ [Switch Stream]
[Webhook: News Flash]  ──┤                                                          │
[Webhook: Order Exec]  ──┘                                                          ├─ 0 (bar.closed)
                                                                                    │      │
┌───────────────────────────────────────────────────────────────────────────────────┘      ▼
│                                                                                 [L1 Sweep Engine]
│                                                                                          │
│                                                                                          ▼
│                                                                                 [Redis Consumed]
│                                                                                          │
│                                                                                          ▼
│                                                                                 [L2 Displ & Swing Gate]
│                                                                                          │
│                                                                                          ▼
│                                                                                 [IF L2 Valid] ──(false)──▶ [Audit Log]
│                                                                                          │ (true)
│                                                                                          ▼
│                                                                                 [L3 Modular POI (M1–M8)]
│                                                                                          │
│                                                                                          ▼
│                                                                                 [L4 5-Pillar Validator]
│                                                                                          │
│                                                                                          ▼
│                                                                                 [Redis CAS Freshness]
│                                                                                          │
│                                                                                          ▼
│                                                                                 [IF Pillars Passed] ──(false)──▶ [Audit Log]
│                                                                                          │ (true)
│                                                           ┌──────────────────────────────┴──────────────────────────────┐
│                                                           ▼                                                             ▼
│                                              [Output: Ranked Signal]                                         [L5 Trigger Router]
│                                              (Institutional > Elevated > Base)                                          │
│                                                                                                                         ▼
│                                                                                                              [L6 News & Lot Sizing]
│                                                                                                              (0.5%–1.0%, ±0.3x ATR)
│                                                                                                                         │
│                                                                                                                         ▼
│                                                                                                              [Broker Order Dispatch]
│                                                                                                                         │
│                                                                                                                         ▼
│                                                                                                              [Output: Trade Ticket]
│                                                                                                                         │
│                                                                                                                         ▼
│                                                                                                              [Health Monitor (SLA)]
│
├─ 1 (tick.quote) ──────▶ [L7 PureRunner Tick Manager] (Real-time SL to BE at +1.0x ATR / Friday 20:00 UTC close)
├─ 2 (news.flash) ──────▶ [Audit Forensic Logger]
└─ 3 (order.execution) ─▶ [Audit Forensic Logger]
```

---

## 3. Node Dictionary & Operational Mapping

| Node Name | Node Type | Role in SMC System | Core Quantitative Rule Executed |
|---|---|---|---|
| `Webhook_Bar_Closed` | `webhook` | L0 Data Ingest | Receives finalized bar events for D1, H4, H1, M30, M5, M1. |
| `Webhook_Tick_Quote` | `webhook` | L0 Data Ingest | Real-time tick stream driving intra-bar trade management. |
| `Webhook_News_Flash` | `webhook` | L0 Data Ingest | Pre-announces high-impact US CPI, NFP, FOMC $\ge 30\text{ min}$ ahead. |
| `Webhook_Order_Execution` | `webhook` | L0 Data Ingest | Receives broker execution confirmations, fills, and rejections. |
| `L0_Dedup_And_Normalizer` | `code` | L0 Normalization | Computes deterministic `event_id` hash and normalizes payloads. |
| `Redis_Idempotency_Check` | `redis` | L0 Idempotency | `SET event:{event_id} 1 NX EX 3600` prevents double processing. |
| `Switch_Event_Stream` | `switch` | Event Routing | Splits stream: `bar.closed` to L1–L5; `tick.quote` to L7; news/orders to audit. |
| `L1_Sweep_Engine` | `code` | Stage 0A Liquidity | Detects all 6 locked liquidity levels; outputs `sweep_extreme` and direction. |
| `Redis_Mark_Sweep_Consumed` | `redis` | Stage 0A State | Marks swept level as `consumed` (smart-money zero-return rule). |
| `L2_Displacement_And_Swing_Gate` | `code` | Stages 0b & 0c | Enforces $\ge 1.0\times\text{ ATR}$ + BOS + FVG, and Base Candle opposite close. |
| `IF_L2_Valid` | `if` | Structural Gate | Rejects weak impulses ($<0.5\times\text{ ATR}$) and invalid swings. |
| `L3_Modular_POI_Classifier` | `code` | Stage 1 POI | Tags M1–M8 as equal tags; sub-classifies CHOCH Rules 1/2/3; computes confluence rank. |
| `L4_Five_Pillars_Validator` | `code` | Stage 2 Validation | Evaluates Refinement ($\pm 0.5\times$), Displacement, P/D ($<45\% / >55\%$), Freshness, IDM ($100/70\%$). |
| `Redis_Atomic_Freshness_CAS` | `redis` | Stage 2 State | Atomic CAS lock ensuring strict 1-touch `STATE_FRESH` $\to$ `STATE_TESTED`. |
| `IF_Pillars_Passed` | `if` | Quality Gate | Passes fully validated POIs to execution; routes rejections to Audit Log. |
| `Output_Ranked_Signal_Feed` | `code` | Signal Output | Broadcasts ranked signal feed (3+ tags $\to$ 2 tags $\to$ 1 tag) with full reason trail. |
| `L5_Trigger_Router` | `code` | Stage 3 Triggers | Selects chronological first-valid LTF trigger (Ending Diag preferred for M8). |
| `L6_News_Gate_And_Lot_Sizing` | `code` | Stage 4 Execution | Hard-cancels if news $\le 15\text{ min}$; calculates dynamic lot size ($0.5\%-1.0\%$). |
| `Broker_Order_Dispatch` | `httpRequest` | Broker Dispatch | Dispatches limit order with physical SL/TP to MT5 Bridge API (`localhost:8080`). |
| `Output_Trade_Ticket` | `code` | Ticket Output | Emits confirmed execution ticket with broker ticket ID. |
| `L7_PureRunner_Tick_Manager` | `code` | Stage 5 Management | Reacts to ticks: PureRunner SL $\to$ BE at $+1.0\times\text{ ATR}$; Friday 20:00 UTC exit. |
| `Audit_Forensic_Logger` | `code` | Forensic Audit | Records all rejections, sweeps, and orders for forensic replay. |
| `Health_Monitor_Heartbeat` | `code` | System SLA | Computes decision latency ($\text{now} - \text{ingest\_ts}$); asserts SLA $\le 35\text{ ms}$. |

---

## 4. Live Pipeline Testing via `curl`

You can test the active workflow immediately using these terminal commands:

### Test 1: Send a Finalized Bar with an EQH Liquidity Sweep (Triggers L1 &rarr; L6)
```bash
curl -X POST http://localhost:5678/webhook/mt5-bar-closed \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "XAUUSD",
    "tf": "H1",
    "ts": 1725537600,
    "o": 2682.50,
    "h": 2686.20,
    "l": 2674.10,
    "c": 2676.00,
    "vol": 12450,
    "atr": 3.80,
    "target_resistance": 2685.00,
    "is_sweep": true,
    "sweep_type": "EQH_SWEEP",
    "direction": "BSL",
    "level_price": 2685.00,
    "base_candle_valid": true,
    "has_inducement": true
  }'
```

### Test 2: Send a Real-Time Tick Quote (Triggers L7 PureRunner SL &rarr; BE)
```bash
curl -X POST http://localhost:5678/webhook/tick-quote \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "XAUUSD",
    "ts": 1725537650,
    "bid": 2671.00,
    "ask": 2671.25,
    "atr": 3.80,
    "active_position": {
      "ticket": 9812401,
      "side": "SELL",
      "entry_price": 2676.00,
      "sl": 2688.00
    }
  }'
```

---

## 5. 17-Point Audit Compliance Matrix

| Audit Item | Implemented In | Verification |
|---|---|:---:|
| 1. Webhook Push (No Polling) | `Webhook_Bar_Closed`, `Webhook_Tick_Quote`, `Webhook_News_Flash`, `Webhook_Order_Execution` | ✅ Passed |
| 2. Stage 0A Sweep Taxonomy | `L1_Sweep_Engine` (all 6 levels evaluated) | ✅ Passed |
| 3. Stage 0b Displacement Gate | `L2_Displacement_And_Swing_Gate` ($\ge 1.0\times\text{ ATR}$, reject $< 0.5\times$) | ✅ Passed |
| 4. Stage 0c Base Candle Gate | `L2_Displacement_And_Swing_Gate` (Base Candle opposite body close required) | ✅ Passed |
| 5. Modular 8-POI (Equal Tags) | `L3_Modular_POI_Classifier` (M1–M8 equal tags, confluence scored) | ✅ Passed |
| 6. CHOCH 3-Tier Classification | `L3_Modular_POI_Classifier` (Rule 1, 2, 3 sub-classified) | ✅ Passed |
| 7. Pillar 1 Zone Refinement | `L4_Five_Pillars_Validator` ($\pm 0.5\times\text{ ATR}$ check) | ✅ Passed |
| 8. Pillar 3 Coupled Range | `L4_Five_Pillars_Validator` ($<45\%$ Buy, $>55\%$ Sell, $45\%-55\%$ Reject) | ✅ Passed |
| 9. Pillar 5 Soft Inducement | `L4_Five_Pillars_Validator` ($100\%$ with IDM, $70\%$ without; never rejects) | ✅ Passed |
| 10. Chronological Triggers | `L5_Trigger_Router` (M1/M5 first-valid; Ending Diag preferred for M8) | ✅ Passed |
| 11. News Hard-Cancellation | `L6_News_Gate_And_Lot_Sizing` ($\le 15\text{ min}$ cancel window) | ✅ Passed |
| 12. PureRunner & Circuit Breaker | `L7_PureRunner_Tick_Manager` (+1.0x ATR BE, Friday 20:00 UTC exit) | ✅ Passed |
| 13. Payload `sweep_extreme` | `L1_Sweep_Engine` &rarr; `L6_News_Gate_And_Lot_Sizing` (SL = `sweep_extreme ± 0.3x ATR`) | ✅ Passed |
| 14. Two-Tier Partition Routing | `Switch_Event_Stream` & `poi_id` scoping | ✅ Passed |
| 15. Bar vs Tick Stream Split | `Switch_Event_Stream` splits `bar.closed` (L1–L5) vs `tick.quote` (L7) | ✅ Passed |
| 16. Redis Atomic Freshness | `Redis_Atomic_Freshness_CAS` enforcing strict 1-touch | ✅ Passed |
| 17. Decoupled $\le 35\text{ ms}$ SLA | `Health_Monitor_Heartbeat` tracking `decision_latency_ms` vs 35 ms target | ✅ Passed |
