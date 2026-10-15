//+------------------------------------------------------------------+
//| SMC_Safety_Watchdog.mq5                                          |
//| Phase 7 — MQL5 SAFETY WATCHDOG + MARKER PRINTER (Option A).      |
//|                                                                  |
//| HARD ARCHITECTURE RULES (Lead Architect, Phase 7 + Mode T lock): |
//|   MAY:   monitor the Python heartbeat; when stale — close ALL    |
//|          scoped positions at market, cancel ALL scoped pending   |
//|          orders, log/alert.                                      |
//|   MAY:   draw CHART MARKERS showing Python's structure state     |
//|          (zones / sweep line / Mode T entry line / corner label) |
//|          by parsing smc_markers.csv — DISPLAY ONLY.              |
//|   MUST NOT: detect POIs, validate setups, place normal entries,  |
//|          manage PureRunner/FVG exits, implement session/news/    |
//|          risk policy, size lots, or run any strategy logic.      |
//|   TIMER ORDER: (1) heartbeat SAFETY — unchanged, always first;   |
//|                (2) marker refresh — marker failure can NEVER     |
//|                disable safety (each duty independent).           |
//|                                                                  |
//| Python heartbeat path (smc.live.heartbeat): a plain-text file:   |
//|     <unix_epoch_seconds> <sequence>                              |
//|     state=<running|shutdown>                                     |
//| The EA parses LINE 1 ONLY and compares against TimeGMT() (UTC    |
//| epoch). Missing/unreadable/garbage file == stale (FAIL-CLOSED).  |
//| This EA implements exactly the tested Python decision in         |
//| smc.live.heartbeat.evaluate_watchdog — keep them in sync.        |
//|                                                                  |
//| Marker file (Mode T design lock §4, smc_markers.csv in the same  |
//| MQL5/Files sandbox): CSV header + one record per line            |
//|   id,symbol,kind,direction,price_high,price_low,timeframe_label, |
//|   text,color_role,updated_at_utc,ephemeral                       |
//| kind ∈ {poi|sweep|entry_t|label}. Stale file (>30 s old per      |
//| updated_at_utc) or unreadable → ALL SMC_* strategy markers are   |
//| DELETED (the chart says nothing rather than showing old state).  |
//| Safety behavior is unchanged at all times.                       |
//+------------------------------------------------------------------+
#property copyright "SMC — Safety Watchdog (no strategy logic)"
#property version   "1.10"
#property strict

input string InpHeartbeatFile     = "smc_heartbeat.txt"; // Heartbeat file (terminal Files dir)
input int    InpStaleTimeoutSec   = 5;                   // Stale timeout (seconds)
input int    InpTimerSeconds      = 1;                   // Timer period (seconds)
input long   InpMagicFilter       = 0;                   // 0 = all magics
input string InpSymbolFilter      = "";                  // "" = all symbols
input bool   InpClosePositions    = true;                // Emergency: close all scoped positions
input bool   InpDeletePendings    = true;                // Emergency: delete all scoped pendings
input string InpMarkerFile        = "smc_markers.csv";   // Marker file (terminal Files dir)

// Marker duty constants (design lock §4):
string MARKER_PREFIX          = "SMC_";
int    MARKER_STALE_SECONDS   = 30;
int    MARKER_MAX_OBJECTS     = 11;

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
   // Strategy markers are wiped only when the EA is REALLY leaving the
   // chart (removal / program stop / chart close). Parameter changes and
   // recompiles keep them — the next timer tick re-syncs from the file.
   if(reason == REASON_REMOVE || reason == REASON_PROGRAM
      || reason == REASON_CLOSE)
      DeleteAllStrategyMarkers();
}

//+------------------------------------------------------------------+
void OnTimer()
{
   // SAFETY FIRST (timer order frozen in the design lock §4.1):
   CheckHeartbeat();
   // Marker duty SECOND — a marker error must never block the safety path.
   UpdateMarkers();
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

//+==================================================================+
//| MARKER PRINTER DUTY (design lock 00_LOCKED/ … §4; display ONLY). |
//| Zero trading logic. A marker failure logs and returns — the      |
//| safety decision above is NEVER gated by this code.               |
//+==================================================================+

//+------------------------------------------------------------------+
//| Parse updated_at_utc "YYYY-MM-DDTHH:MM:SSZ" → epoch seconds.      |
//+------------------------------------------------------------------+
long TimestampToEpoch(const string stamp)
{
   // MQL5 without extra libs: manual parse of the fixed UTC ISO shape.
   if(StringLen(stamp) < 19)
      return (0);
   int y  = (int)StringToInteger(StringSubstr(stamp, 0, 4));
   int mo = (int)StringToInteger(StringSubstr(stamp, 5, 2));
   int d  = (int)StringToInteger(StringSubstr(stamp, 8, 2));
   int h  = (int)StringToInteger(StringSubstr(stamp, 11, 2));
   int mi = (int)StringToInteger(StringSubstr(stamp, 14, 2));
   int s  = (int)StringToInteger(StringSubstr(stamp, 17, 2));
   MqlDateTime dt;
   dt.year  = y;  dt.mon  = mo; dt.day     = d;
   dt.hour  = h;  dt.min  = mi; dt.sec     = s;
   dt.day_of_week = 0; dt.day_of_year = 0;
   return (StructToTime(dt));    // UTC per terminal time settings
}

//+------------------------------------------------------------------+
//| color_role → chart color. Unknown role = gray (never a crash).   |
//+------------------------------------------------------------------+
color RoleToColor(const string role)
{
   if(role == "bull_green")    return (clrLimeGreen);
   if(role == "bear_red")      return (clrRed);
   if(role == "mode_T_orange") return (clrOrange);
   if(role == "stale_red")     return (clrRed);
   return (clrSilver);
}

//+------------------------------------------------------------------+
//| Minute marker duty: read CSV → draw/delete exactly what it says. |
//+------------------------------------------------------------------+
void UpdateMarkers()
{
   if(InpMarkerFile == "")
      return;                          // markers off in this attach

   int h = FileOpen(InpMarkerFile, FILE_READ | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      // Unreadable marker file is NOT an emergency (design §4.4): the
      // chart simply says nothing. The safety path above already ran.
      DeleteAllStrategyMarkers();
      return;
   }

   string lines[];
   int count = 0;
   while(!FileIsEnding(h) && count < 64)
   {
      string line = FileReadString(h);
      if(StringLen(line) > 0)
      {
         ArrayResize(lines, count + 1);
         lines[count] = line;
         count++;
      }
   }
   FileClose(h);

   if(count < 2)                       // header only / empty → stale enough
   {
      DeleteAllStrategyMarkers();
      return;
   }

   string latestStamp = "";
   bool   anyDrawn    = false;

   for(int i = 1; i < count; i++)       // skip header row (index 0)
   {
      string fields[];
      int nf = StringSplit(lines[i], ',', fields);
      if(nf < 11)
         continue;                      // malformed row — skip, never crash

      string id        = fields[0];
      string kind      = fields[2];
      string direction = fields[3];
      double high      = StringToDouble(fields[4]);
      double low       = StringToDouble(fields[5]);
      string text      = fields[7];
      string role      = fields[8];
      string stamp     = fields[9];

      long epoch = TimestampToEpoch(stamp);
      if(StringLen(latestStamp) == 0 || epoch > TimestampToEpoch(latestStamp))
         latestStamp = stamp;

      if(id == "")
         continue;                       // malformed row — skip, never crash

      string name = MARKER_PREFIX + id;
      color  clr  = RoleToColor(role);

      if(kind == "poi" && high > low)
      {
         datetime t1 = (datetime)epoch - 3600;
         datetime t2 = (datetime)epoch + 3600;
         if(ObjectFind(0, name) < 0)
            ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, high, t2, low);
         else
         {
            ObjectSetInteger(0, name, OBJPROP_TIME, 0, (long)t1);
            ObjectSetInteger(0, name, OBJPROP_TIME, 1, (long)t2);
            ObjectSetDouble(0, name, OBJPROP_PRICE, 0, high);
            ObjectSetDouble(0, name, OBJPROP_PRICE, 1, low);
         }
         ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
         ObjectSetInteger(0, name, OBJPROP_FILL, false);
         ObjectSetInteger(0, name, OBJPROP_BACK, true);
         ObjectSetString(0, name, OBJPROP_TOOLTIP, text);
         anyDrawn = true;
      }
      else if((kind == "sweep" || kind == "entry_t") && high > 0)
      {
         if(ObjectFind(0, name) < 0)
            ObjectCreate(0, name, OBJ_HLINE, 0, 0, high);
         else
            ObjectSetDouble(0, name, OBJPROP_PRICE, high);
         ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
         ObjectSetInteger(0, name, OBJPROP_STYLE,
                          (kind == "sweep") ? STYLE_DOT : STYLE_SOLID);
         ObjectSetString(0, name, OBJPROP_TOOLTIP, text);
         anyDrawn = true;
      }
      else if(kind == "label")
      {
         // Corner label (top-left, screen-anchored — price-independent so a
         // chart-TF change never changes semantics, design §4.5).
         string shown = text;
         if(g_emergencyActive)
            shown = "HEARTBEAT STALE";     // safety info wins over marker text
         if(ObjectFind(0, name) < 0)
            ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
         ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
         ObjectSetInteger(0, name, OBJPROP_XDISTANCE, 8);
         ObjectSetInteger(0, name, OBJPROP_YDISTANCE, 22);
         ObjectSetInteger(0, name, OBJPROP_COLOR,
                          g_emergencyActive ? clrRed : clr);
         ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 10);
         ObjectSetString(0, name, OBJPROP_TEXT, shown);
         anyDrawn = true;
      }
   }

   // Staleness: the writer's freshest row older than the budget → clear all
   // strategy markers (chart says nothing rather than showing old structure;
   // design §4.2). The safety path above is UNTOUCHED regardless.
   long fileAge = TimeGMT() - TimestampToEpoch(latestStamp);
   bool stale = (TimestampToEpoch(latestStamp) <= 0)
                || (fileAge > MARKER_STALE_SECONDS);
   if(stale || !anyDrawn)
      DeleteAllStrategyMarkers();
}

//+------------------------------------------------------------------+
//| Delete every chart object under the SMC_ prefix (strategy markers|
//| only — never anything the user placed themselves).               |
//+------------------------------------------------------------------+
void DeleteAllStrategyMarkers()
{
   for(int i = ObjectsTotal(0) - 1; i >= 0; i--)
   {
      string name = ObjectName(0, i);
      if(StringFind(name, MARKER_PREFIX) == 0)
         ObjectDelete(0, name);
   }
}
//+------------------------------------------------------------------+
