//+------------------------------------------------------------------+
//| SMC_Safety_Watchdog.mq5                                          |
//| Phase 7 — MQL5 SAFETY WATCHDOG + MARKER + STRUCTURE DRAW         |
//| (companion-EA merge 2026-10-22: ONE EA — safety first, then paint).|
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
//|                (3) structure draw — fail-soft paint only; a bad  |
//|                draw file clears ITS OWN objects and NOTHING else |
//|                (never an emergency — merge lock 2026-10-22).     |
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
//|                                                                  |
//| Structure draw file (design lock 2026-10-22;                     |
//| smc_structure_draw.txt, same MQL5/Files sandbox): schema-v1 rows |
//| POI/SWEEP/SEEK/PLAN written by smc.live.structure_publish.       |
//| Python OWNS every level — this EA ONLY PAINTS. Missing/stale/    |
//| foreign/symbol-mismatched file → delete InpDrawPrefix objects    |
//| ONLY — NEVER an emergency, NEVER a heartbeat judgement.          |
//| Standalone SMC_Structure_Draw.mq5 is DEPRECATED (merged here):   |
//| attach ONE EA.                                                   |
//+------------------------------------------------------------------+
#property copyright "SMC — Safety Watchdog (no strategy logic)"
#property version   "1.20"
#property strict

input string InpHeartbeatFile     = "smc_heartbeat.txt"; // Heartbeat file (terminal Files dir)
input int    InpStaleTimeoutSec   = 5;                   // Stale timeout (seconds)
input int    InpTimerSeconds      = 1;                   // Timer period (seconds)
input long   InpMagicFilter       = 0;                   // 0 = all magics
input string InpSymbolFilter      = "";                  // "" = all symbols
input bool   InpClosePositions    = true;                // Emergency: close all scoped positions
input bool   InpDeletePendings    = true;                // Emergency: delete all scoped pendings
input string InpMarkerFile        = "smc_markers.csv";   // Marker file (terminal Files dir)

// --- Structure-draw duty inputs (merge lock 2026-10-22; PAINT ONLY) ------
input bool   InpEnableStructureDraw = true;              // Structure draw on/off
input string InpStructureFile       = "smc_structure_draw.txt"; // Draw file (terminal Files dir)
input string InpStructureSymbol     = "";                // Required file symbol ("" = chart symbol)
input string InpDrawPrefix          = "SMC_SD_";         // Structure object prefix (must differ from SMC_)
input int    InpMaxStructureAgeSec  = 120;               // Draw file older → clear draw objects ONLY
input bool   InpDrawPOI             = true;              // Draw POI zone rectangles
input bool   InpDrawSweep           = true;              // Draw sweep level lines
input bool   InpDrawSeek            = true;              // Draw armed-POI state texts
input bool   InpDrawPlan            = true;              // Draw planned entry/stop/target levels
input color  InpColorBull           = clrLimeGreen;      // Bull (BUY) zone color
input color  InpColorBear           = clrTomato;         // Bear (SELL) zone color
input color  InpColorSweep          = clrOrange;         // Sweep line color
input color  InpColorPlanEntry      = clrDeepSkyBlue;    // Plan entry level color
input color  InpColorPlanSL         = clrRed;            // Plan stop level color
input color  InpColorPlanTP         = clrLime;           // Plan target level color
input int    InpZoneWindowHours     = 36;                // Zone rectangle window (hours around now)

// Marker duty constants (design lock §4):
string MARKER_PREFIX          = "SMC_";
int    MARKER_STALE_SECONDS   = 30;
int    MARKER_MAX_OBJECTS     = 11;

bool     g_emergencyActive = false;
datetime g_lastEmergencyAt = 0;

// Debounce & Alert flood limits (ruling update 2026-10-19):
int      g_consecutiveBadTicks = 0;
const int UNREADABLE_DEBOUNCE_TICKS = 3; // 3 consecutive ticks at 1s timer (~3s)
datetime g_lastAlertAt = 0;
const int ALERT_FLOOD_INTERVAL_SEC = 300; // Alert at most once per 5 minutes while in emergency

// Structure-draw duty state (merge 2026-10-22):
string g_lastDrawSymbol = ""; // chart symbol at last draw pass (change → wipe)

//+------------------------------------------------------------------+
int OnInit()
{
   EventSetTimer(InpTimerSeconds);
   if(InpEnableStructureDraw)
   {
      if(InpDrawPrefix == "" || InpDrawPrefix == MARKER_PREFIX)
         Print("SMC watchdog: structure draw DISABLED — InpDrawPrefix must be "
               "non-empty and distinct from the marker prefix (", MARKER_PREFIX, ")");
      else
         PrintFormat("SMC watchdog: structure draw ON (file=%s prefix=%s maxAge=%ds) "
                     "— VISUALIZATION ONLY", InpStructureFile, InpDrawPrefix,
                     InpMaxStructureAgeSec);
   }
   return (INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   // Structure-draw objects are ALWAYS cleared (merge rule 5): removal,
   // recompile, or parameter change must never leave stale boxes behind.
   // Independent of the marker policy below (markers survive recompiles).
   if(InpEnableStructureDraw && InpDrawPrefix != "")
      ObjectsDeleteAll(0, InpDrawPrefix);
   // Strategy markers are wiped only when the EA is REALLY leaving the
   // chart (removal / program stop / chart close). Parameter changes and
   // recompiles keep them — the next timer tick re-syncs from the file.
   if(reason == REASON_REMOVE || reason == REASON_PROGRAM
      || reason == REASON_CLOSE)
      DeleteAllStrategyMarkers();
   ChartRedraw();
}

//+------------------------------------------------------------------+
void OnTimer()
{
   // SAFETY FIRST (timer order frozen in the design lock §4.1):
   CheckHeartbeat();
   // Marker duty SECOND — a marker error must never block the safety path.
   UpdateMarkers();
   // Structure draw THIRD (merge 2026-10-22) — fail-soft paint. It never
   // calls Emergency(): a bad/missing/stale draw file clears only its own
   // prefix objects. Heartbeat safety above stays untouched regardless.
   UpdateStructureDraw();
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
      g_consecutiveBadTicks++;
      PrintFormat("SMC watchdog: heartbeat unreadable on tick (consecutive=%d/%d)",
                  g_consecutiveBadTicks, UNREADABLE_DEBOUNCE_TICKS);
      if(g_consecutiveBadTicks >= UNREADABLE_DEBOUNCE_TICKS)
      {
         Emergency("unreadable");
      }
      return;
   }

   // File read succeeded — clear unreadable tick counter
   g_consecutiveBadTicks = 0;

   long age = TimeGMT() - hbSec;
   if(age < 0)
      age = 0;                          // clock-skew guard (fail safe, not fail stale)
   if(age > (long)InpStaleTimeoutSec)
   {
      Emergency(StringFormat("stale (%llds)", age));
   }
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
//| Terminal Alert() is rate-limited to at most once per 5 minutes.  |
//+------------------------------------------------------------------+
void Emergency(const string reason)
{
   datetime now = TimeCurrent();
   if(g_emergencyActive && (now - g_lastEmergencyAt) < 30)
      return;

   bool firstEmergency = !g_emergencyActive;
   g_emergencyActive = true;
   g_lastEmergencyAt = now;
   PrintFormat("SMC watchdog EMERGENCY (heartbeat %s): closing scoped positions, deleting scoped pendings", reason);

   // Alert rate-limit (P2b / P2c): alert on first entry or once every M minutes (default 5m)
   if(firstEmergency || (now - g_lastAlertAt) >= ALERT_FLOOD_INTERVAL_SEC)
   {
      g_lastAlertAt = now;
      Alert("SMC Safety Watchdog: Python heartbeat ", reason, " — emergency protection active");
   }

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
//| only — never anything the user placed themselves). Structure-draw|
//| objects (InpDrawPrefix, e.g. SMC_SD_*) are the structure duty's  |
//| EXCLUSIVE ownership — the marker wipe must skip them: SMC_ is a  |
//| prefix of SMC_SD_, so without this guard a stale marker file     |
//| would delete freshly painted zones every tick (flicker).         |
//+------------------------------------------------------------------+
void DeleteAllStrategyMarkers()
{
   for(int i = ObjectsTotal(0) - 1; i >= 0; i--)
   {
      string name = ObjectName(0, i);
      if(StringFind(name, MARKER_PREFIX) != 0)
         continue;
      if(InpDrawPrefix != "" && StringFind(name, InpDrawPrefix) == 0)
         continue;                       // structure duty owns these
      ObjectDelete(0, name);
   }
}
//+==================================================================+
//| STRUCTURE DRAW DUTY (design lock 2026-10-22; display ONLY).      |
//| Python OWNS every level — this routine only paints the schema-v1  |
//| file smc_structure_draw.txt. Hard rules:                          |
//|   * NO OrderSend / no position or order calls — NOTHING here      |
//|     can trade, ever (the emergency duties above are untouched).   |
//|   * A missing/foreign/stale/symbol-mismatched draw file clears    |
//|     ONLY InpDrawPrefix objects — NEVER an emergency, NEVER a      |
//|     heartbeat judgement (different file, different duty).         |
//+==================================================================+

//+------------------------------------------------------------------+
void UpdateStructureDraw()
{
   if(!InpEnableStructureDraw)
      return;                          // off — deinit/param change cleared objects
   if(InpDrawPrefix == "" || InpDrawPrefix == MARKER_PREFIX)
      return;                          // unusable namespace — logged at init

   // Chart symbol changed → our objects are meaningless there; wipe + resync.
   if(_Symbol != g_lastDrawSymbol)
   {
      if(g_lastDrawSymbol != "")
         ObjectsDeleteAll(0, InpDrawPrefix);
      g_lastDrawSymbol = _Symbol;
   }

   int h = FileOpen(InpStructureFile, FILE_READ | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      ClearStructureDraw();            // fail-soft: clear ONLY, never emergency
      return;
   }
   string schema = FileIsEnding(h) ? "" : FileReadString(h);
   if(StringFind(schema, "SMC_STRUCTURE_DRAW v1") != 0)
   {
      FileClose(h);                    // unknown/foreign file → clear, no spam
      ClearStructureDraw();
      return;
   }
   string header = FileIsEnding(h) ? "" : FileReadString(h);
   FileClose(h);

   string sym       = "";
   long   fileEpoch = 0;
   if(!ParseHeader(header, sym, fileEpoch))
   {
      ClearStructureDraw();
      return;
   }
   string wantSym = (InpStructureSymbol == "") ? g_lastDrawSymbol : InpStructureSymbol;
   if(wantSym != "" && sym != wantSym)
   {
      ClearStructureDraw();            // publisher targets another symbol
      return;
   }
   if(fileEpoch <= 0 || (TimeGMT() - fileEpoch) > InpMaxStructureAgeSec)
   {
      ClearStructureDraw();            // stale → chart says nothing
      return;
   }

   // Records: reread past the two header lines into memory, then paint.
   h = FileOpen(InpStructureFile, FILE_READ | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      ClearStructureDraw();
      return;
   }
   string lines[];
   int count = 0;
   FileReadString(h);                    // skip schema line
   FileReadString(h);                    // skip header line
   while(!FileIsEnding(h) && count < 128)
   {
      string line = FileReadString(h);
      if(StringLen(line) > 0 && StringFind(line, "|") > 0)
      {
         ArrayResize(lines, count + 1);
         lines[count] = line;
         count++;
      }
   }
   FileClose(h);

   bool anyDrawn = DrawRecords(lines, count);
   if(anyDrawn)
      DrawStructureBanner();
   else
      ClearStructureDraw();            // zero records → clear, not a ghost banner
   ChartRedraw();
}

//+------------------------------------------------------------------+
//| Parse header "ts_utc=... symbol=..." → stamp epoch + symbol.     |
//+------------------------------------------------------------------+
bool ParseHeader(const string header, string &symbolOut, long &epochOut)
{
   string parts[];
   int n = StringSplit(header, ' ', parts);
   if(n < 2)
      return (false);
   string stamp = "";
   symbolOut    = "";
   for(int i = 0; i < n; i++)
   {
      if(StringFind(parts[i], "ts_utc=") == 0)
         stamp = StringSubstr(parts[i], 7);
      else if(StringFind(parts[i], "symbol=") == 0)
         symbolOut = StringSubstr(parts[i], 7);
   }
   epochOut = TimestampToEpoch(stamp);   // shared manual ISO-UTC parser
   return (epochOut > 0);
}

//+------------------------------------------------------------------+
//| Common object props (never selectable/visible-in-object-list).   |
//+------------------------------------------------------------------+
void EnsureProps(const string name)
{
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
}

//+------------------------------------------------------------------+
//| Grow-on-demand seen-name tracker for orphan reconcile.           |
//+------------------------------------------------------------------+
void AddSeen(string &seen[], int &seenCount, int &seenMax, const string name)
{
   if(seenCount >= seenMax)
   {
      seenMax *= 2;
      ArrayResize(seen, seenMax);
   }
   seen[seenCount] = name;
   seenCount++;
}

//+------------------------------------------------------------------+
//| Draw every structure record; true when at least one object was   |
//| drawn. Publisher emits POI rows before SWEEP/SEEK/PLAN rows, so   |
//| the POI lookup array is complete before later rows need it.       |
//+------------------------------------------------------------------+
bool DrawRecords(const string &lines[], const int count)
{
   // Display-only time window: recent past → just past now, so zones live
   // on the visible recent window and follow the chart automatically.
   datetime now    = TimeCurrent();
   // Explicit (datetime) casts on both RHS (project style line ~423):
   // datetime-minus-long yields long, which warns C4240 "possible loss of
   // data" when assigned back to a datetime — display-only window math.
   datetime tLeft  = (datetime)(now - (long)InpZoneWindowHours * 3600);
   datetime tRight = (datetime)(now + 2 * 3600);
   bool anyDrawn = false;

   int cap = count > 0 ? count : 1;
   string poiId[]; ArrayResize(poiId, cap);
   int    poiN = 0;

   int seenMax = 64;
   string seen[];
   ArrayResize(seen, seenMax);
   int seenCount = 0;

   for(int i = 0; i < count; i++)
   {
      string f[];
      int nf = StringSplit(lines[i], '|', f);
      if(nf < 1)
         continue;                       // malformed row — skip, never crash
      string kind = f[0];

      // ---- POI|id|tf|side|zlow|zhigh|state ------------------------------
      if(kind == "POI" && InpDrawPOI && nf >= 7)
      {
         string pid  = f[1];
         double low  = StringToDouble(f[4]);
         double high = StringToDouble(f[5]);
         if(pid == "" || low <= 0 || high <= low)
            continue;
         if(poiN < cap)
         {
            poiId[poiN] = pid;
            poiN++;
         }
         string name = InpDrawPrefix + pid + "_Z";
         if(ObjectFind(0, name) < 0)
            ObjectCreate(0, name, OBJ_RECTANGLE, 0, tLeft, high, tRight, low);
         else
         {
            ObjectSetInteger(0, name, OBJPROP_TIME, 0, (long)tLeft);
            ObjectSetInteger(0, name, OBJPROP_TIME, 1, (long)tRight);
            ObjectSetDouble(0, name, OBJPROP_PRICE, 0, high);
            ObjectSetDouble(0, name, OBJPROP_PRICE, 1, low);
         }
         ObjectSetInteger(0, name, OBJPROP_COLOR,
                          (f[3] == "BULL") ? InpColorBull : InpColorBear);
         ObjectSetInteger(0, name, OBJPROP_FILL, false);
         ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
         ObjectSetString(0, name, OBJPROP_TOOLTIP,
                         f[2] + " " + f[3] + " POI " + f[6] + " (" + pid + ")");
         EnsureProps(name);
         AddSeen(seen, seenCount, seenMax, name);
         anyDrawn = true;

         // State text at the zone's top-left edge (inside the drawing window).
         string lname = InpDrawPrefix + pid + "_L";
         if(ObjectFind(0, lname) < 0)
            ObjectCreate(0, lname, OBJ_TEXT, 0, tLeft, high);
         else
            ObjectSetInteger(0, lname, OBJPROP_TIME, 0, (long)tLeft);
         ObjectSetDouble(0, lname, OBJPROP_PRICE, 0, high);
         ObjectSetInteger(0, lname, OBJPROP_COLOR,
                          (f[6] == "ARMED") ? clrGold : clrSilver);
         ObjectSetInteger(0, lname, OBJPROP_FONTSIZE, 8);
         ObjectSetString(0, lname, OBJPROP_TEXT, f[2] + " " + f[6]);
         ObjectSetString(0, lname, OBJPROP_TOOLTIP, pid);
         EnsureProps(lname);
         AddSeen(seen, seenCount, seenMax, lname);
      }
      // ---- SWEEP|poi_id|side|price|atr_mult ------------------------------
      else if(kind == "SWEEP" && InpDrawSweep && nf >= 5)
      {
         string pid   = f[1];
         double price = StringToDouble(f[3]);
         if(pid == "" || price <= 0)
            continue;
         string name = InpDrawPrefix + pid + "_S";
         if(ObjectFind(0, name) < 0)
            ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
         else
            ObjectSetDouble(0, name, OBJPROP_PRICE, price);
         ObjectSetInteger(0, name, OBJPROP_COLOR, InpColorSweep);
         ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DOT);
         ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
         ObjectSetString(0, name, OBJPROP_TOOLTIP,
                         "SWEEP " + f[2] + " @ zone edge (poi " + pid + ")");
         EnsureProps(name);
         AddSeen(seen, seenCount, seenMax, name);
         anyDrawn = true;
      }
      // ---- SEEK|poi_id|state|posture — enrich the zone tooltip only: ------
      // the state itself is already on the zone label; never invents an
      // object when the POI zone was capped or absent from this file.
      else if(kind == "SEEK" && nf >= 4)
      {
         string pid = f[1];
         if(pid == "")
            continue;
         for(int p = 0; p < poiN; p++)
         {
            if(poiId[p] != pid)
               continue;
            string zname = InpDrawPrefix + pid + "_Z";
            ObjectSetString(0, zname, OBJPROP_TOOLTIP,
                            ObjectGetString(0, zname, OBJPROP_TOOLTIP)
                            + " | " + f[2] + (f[3] == "" ? "" : " " + f[3]));
            break;
         }
      }
      // ---- PLAN|poi_id|entry|sl|tp ---------------------------------------
      else if(kind == "PLAN" && InpDrawPlan && nf >= 5)
      {
         string pid   = f[1];
         double entry = StringToDouble(f[2]);
         double sl    = StringToDouble(f[3]);
         double tp    = StringToDouble(f[4]);
         if(pid == "" || entry <= 0 || sl <= 0 || tp <= 0)
            continue;
         if(DrawPlanLine(InpDrawPrefix + pid + "_PE", entry, InpColorPlanEntry,
                         STYLE_DASH, "PLAN entry (poi " + pid + ")"))
            { AddSeen(seen, seenCount, seenMax, InpDrawPrefix + pid + "_PE"); anyDrawn = true; }
         if(DrawPlanLine(InpDrawPrefix + pid + "_PS", sl, InpColorPlanSL,
                         STYLE_DOT, "PLAN stop (poi " + pid + ")"))
            { AddSeen(seen, seenCount, seenMax, InpDrawPrefix + pid + "_PS"); anyDrawn = true; }
         if(DrawPlanLine(InpDrawPrefix + pid + "_PT", tp, InpColorPlanTP,
                         STYLE_DOT, "PLAN target (poi " + pid + ")"))
            { AddSeen(seen, seenCount, seenMax, InpDrawPrefix + pid + "_PT"); anyDrawn = true; }
      }
   }

   // Orphan reconcile: remove prefix objects this pass did NOT see —
   // expired POIs / cleared sweeps vanish the same tick their row does.
   for(int j = ObjectsTotal(0) - 1; j >= 0; j--)
   {
      string name = ObjectName(0, j);
      if(StringFind(name, InpDrawPrefix) != 0 || name == InpDrawPrefix + "BANNER")
         continue;
      bool isSeen = false;
      for(int s = 0; s < seenCount; s++)
      {
         if(seen[s] == name)
         {
            isSeen = true;
            break;
         }
      }
      if(!isSeen)
         ObjectDelete(0, name);
   }
   return (anyDrawn);
}

//+------------------------------------------------------------------+
//| Plan level line (entry / stop / target share one body).          |
//+------------------------------------------------------------------+
bool DrawPlanLine(const string name, const double price, const color clr,
                  const ENUM_LINE_STYLE style, const string tip)
{
   if(price <= 0)
      return (false);
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
   else
      ObjectSetDouble(0, name, OBJPROP_PRICE, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetString(0, name, OBJPROP_TOOLTIP, tip);
   EnsureProps(name);
   return (true);
}

//+------------------------------------------------------------------+
//| Banner corner label — VISUALIZATION ONLY, NOT A STRATEGY CHANGE. |
//| y=40: the marker duty's corner label owns y=22 — never overlap.  |
//+------------------------------------------------------------------+
void DrawStructureBanner()
{
   const string name = InpDrawPrefix + "BANNER";
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, 8);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, 40);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrSilver);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 9);
   ObjectSetString(0, name, OBJPROP_TEXT,
                   "SMC STRUCTURE DRAW — VISUALIZATION ONLY (NOT A STRATEGY CHANGE)");
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
}

//+------------------------------------------------------------------+
//| Clear ONLY the structure prefix objects (stale / missing /       |
//| mismatch). This is the ENTIRE failure surface of this duty: no   |
//| Alert(), no Emergency(), no trading call — the heartbeat safety  |
//| path above decides protection from smc_heartbeat.txt alone.      |
//+------------------------------------------------------------------+
void ClearStructureDraw()
{
   if(InpDrawPrefix == "")
      return;
   ObjectsDeleteAll(0, InpDrawPrefix);
   ChartRedraw();
}
//+------------------------------------------------------------------+
