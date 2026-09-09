//+------------------------------------------------------------------+
//| SMC_Safety_Watchdog.mq5                                          |
//| Phase 7 — MQL5 SAFETY WATCHDOG ONLY (Option A).                  |
//|                                                                  |
//| HARD ARCHITECTURE RULES (Lead Architect, Phase 7):               |
//|   MAY:   monitor the Python heartbeat; when stale — close ALL    |
//|          scoped positions at market, cancel ALL scoped pending   |
//|          orders, log/alert.                                      |
//|   MUST NOT: detect POIs, validate setups, place normal entries,  |
//|          manage PureRunner/FVG exits, implement session/news/    |
//|          risk policy, size lots, or run any strategy logic.      |
//|                                                                  |
//| Python (smc.live.heartbeat) writes a plain-text file:            |
//|     <unix_epoch_seconds> <sequence>                              |
//|     state=<running|shutdown>                                     |
//| The EA parses LINE 1 ONLY and compares against TimeGMT() (UTC    |
//| epoch). Missing/unreadable/garbage file == stale (FAIL-CLOSED).  |
//| This EA implements exactly the tested Python decision in         |
//| smc.live.heartbeat.evaluate_watchdog — keep them in sync.        |
//+------------------------------------------------------------------+
#property copyright "SMC — Safety Watchdog (no strategy logic)"
#property version   "1.00"
#property strict

input string InpHeartbeatFile     = "smc_heartbeat.txt"; // Heartbeat file (terminal Files dir)
input int    InpStaleTimeoutSec   = 5;                   // Stale timeout (seconds)
input int    InpTimerSeconds      = 1;                   // Timer period (seconds)
input long   InpMagicFilter       = 0;                   // 0 = all magics
input string InpSymbolFilter      = "";                  // "" = all symbols
input bool   InpClosePositions    = true;                // Emergency: close all scoped positions
input bool   InpDeletePendings    = true;                // Emergency: delete all scoped pendings

bool     g_emergencyActive = false;
datetime g_lastEmergencyAt = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   EventSetTimer(InpTimerSeconds);
   return (INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
}

//+------------------------------------------------------------------+
void OnTimer()
{
   CheckHeartbeat();
}

//+------------------------------------------------------------------+
//| Watchdog decision — mirrors smc.live.heartbeat.evaluate_watchdog |
//+------------------------------------------------------------------+
void CheckHeartbeat()
{
   long hbSec = -1;
   long seq   = -1;

   if(!ReadHeartbeat(InpHeartbeatFile, hbSec, seq))
   {
      // Unreadable / missing / garbage → fail-closed: treat as dead.
      Emergency("heartbeat unreadable");
      return;
   }

   long age = TimeGMT() - hbSec;
   if(age < 0)
      age = 0;                          // clock-skew guard (fail safe, not fail stale)
   if(age > (long)InpStaleTimeoutSec)
      Emergency(StringFormat("heartbeat stale (%llds)", age));
   else
   {
      if(g_emergencyActive)
         PrintFormat("SMC watchdog: heartbeat healthy again (seq %lld) — normal operation", seq);
      g_emergencyActive = false;
   }
}

//+------------------------------------------------------------------+
//| Parse line 1: "<unix_epoch_seconds> <sequence>"                  |
//+------------------------------------------------------------------+
bool ReadHeartbeat(const string fileName, long &hbSec, long &seq)
{
   int h = FileOpen(fileName, FILE_READ | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE)
      return (false);

   if(FileIsEnding(h))
   {
      FileClose(h);
      return (false);
   }
   string line = FileReadString(h);
   FileClose(h);

   string parts[];
   int n = StringSplit(line, ' ', parts);
   if(n < 2)
      return (false);
   long parsedSec = StringToInteger(parts[0]);
   if(parsedSec <= 0)
      return (false);
   hbSec = parsedSec;
   seq   = StringToInteger(parts[1]);
   return (true);
}

//+------------------------------------------------------------------+
//| Emergency: close scoped positions + delete scoped pendings.      |
//| Re-asserts at most every 30s while the heartbeat stays stale     |
//| (covers broker rejects / re-fills without spamming every tick).  |
//+------------------------------------------------------------------+
void Emergency(const string reason)
{
   if(g_emergencyActive && (TimeCurrent() - g_lastEmergencyAt) < 30)
      return;

   g_emergencyActive = true;
   g_lastEmergencyAt = TimeCurrent();
   PrintFormat("SMC watchdog EMERGENCY (%s): closing scoped positions, deleting scoped pendings", reason);
   Alert("SMC Safety Watchdog: Python heartbeat ", reason, " — emergency protection active");

   if(InpClosePositions)
      CloseAllPositions();
   if(InpDeletePendings)
      DeleteAllPendings();
}

//+------------------------------------------------------------------+
bool PositionInScope(const string symbol, const long magic)
{
   if(InpSymbolFilter != "" && symbol != InpSymbolFilter)
      return (false);
   if(InpMagicFilter != 0 && magic != InpMagicFilter)
      return (false);
   return (true);
}

//+------------------------------------------------------------------+
void CloseAllPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(!PositionSelectByTicket(ticket))
         continue;

      string symbol = PositionGetString(POSITION_SYMBOL);
      long   magic  = PositionGetInteger(POSITION_MAGIC);
      if(!PositionInScope(symbol, magic))
         continue;

      long   type   = PositionGetInteger(POSITION_TYPE);
      double volume = PositionGetDouble(POSITION_VOLUME);

      MqlTradeRequest req = {};
      req.action   = TRADE_ACTION_DEAL;
      req.symbol   = symbol;
      req.volume   = volume;
      req.type     = (type == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
      req.deviation = 50;
      req.magic    = (ulong)magic;

      MqlTradeResult res;
      if(OrderSend(req, res))
         PrintFormat("SMC watchdog: closed %s %s %.2f lots (position %I64u)",
                     symbol, (type == POSITION_TYPE_BUY) ? "SELL" : "BUY", volume, ticket);
      else
         PrintFormat("SMC watchdog: close FAILED %s retcode=%u", symbol, res.retcode);
   }
}

//+------------------------------------------------------------------+
void DeleteAllPendings()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0)
         continue;
      if(!OrderSelect(ticket))
         continue;

      string symbol = OrderGetString(ORDER_SYMBOL);
      long   magic  = OrderGetInteger(ORDER_MAGIC);
      if(!PositionInScope(symbol, magic))
         continue;

      MqlTradeRequest req = {};
      req.action = TRADE_ACTION_REMOVE;
      req.order  = ticket;

      MqlTradeResult res;
      if(OrderSend(req, res))
         PrintFormat("SMC watchdog: deleted pending order %I64u", ticket);
      else
         PrintFormat("SMC watchdog: delete pending FAILED %I64u retcode=%u", ticket, res.retcode);
   }
}
//+------------------------------------------------------------------+