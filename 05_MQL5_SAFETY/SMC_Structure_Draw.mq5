//+------------------------------------------------------------------+
//| SMC_Structure_Draw.mq5   *** DEPRECATED 2026-10-22 — ***          |
//| *** DO NOT COMPILE OR ATTACH. Merged into SMC_Safety_Watchdog.mq5 |
//| (same folder): attach ONE EA — the watchdog now carries both the  |
//| heartbeat emergency duty AND this structure-draw duty (timer      |
//| order: safety → markers → draw). This file is kept ONLY as the    |
//| reference source of the draw routine; the live copy lives in the  |
//| watchdog (InpEnableStructureDraw/InpStructureFile/InpDrawPrefix). |
//+------------------------------------------------------------------+
//| SMC_Structure_Draw.mq5                                           |
//| STRUCTURE DRAW — DRAW-ONLY EA (design lock 2026-10-22).          |
//|                                                                  |
//| BANNER: VISUALIZATION ONLY — NOT A STRATEGY CHANGE.              |
//|                                                                  |
//| HARD ARCHITECTURE RULES (Lead Architect 2026-10-22):             |
//|   Python OWNS levels (POIs, sweeps, seek/entry marks).           |
//|   This EA ONLY DRAWS what the publisher file says.               |
//|   NO OrderSend. NO position modification. NO detection logic.    |
//|   NO thresholds, NO validation, NO entry decisions in MQL5.      |
//|   Missing/stale file → clear ALL InpPrefix objects (the chart    |
//|   says nothing rather than showing old state).                   |
//|                                                                  |
//| Input file (same MQL5/Files sandbox as the heartbeat):           |
//|   smc_structure_draw.txt, written atomically each refresh by     |
//|   smc.live.structure_publish.StructureDrawPublisher. Schema v1:  |
//|     Line 1: SMC_STRUCTURE_DRAW v1                                |
//|     Line 2: ts_utc=YYYY-MM-DDTHH:MM:SSZ symbol=XAUUSDm           |
//|     POI|id|tf|side|zlow|zhigh|state      (state ARMED|UNARMED)   |
//|     SWEEP|poi_id|side|price|atr_mult                             |
//|     SEEK|poi_id|state|posture            (armed POIs only)       |
//|     PLAN|poi_id|entry|sl|tp              (only when all 3 exist) |
//|   Publisher emits ALL POI rows BEFORE SEEK rows, so a SEEK label  |
//|   anchors to the already-seen POI zone top; unmatched → skipped.  |
//|                                                                  |
//| Drawn objects (all under InpPrefix, e.g. "SMC_SD_"):             |
//|   <id>_Z   rectangle per POI (bull/bear color)                   |
//|   <id>_L   small state text at the zone's top edge (armed)       |
//|   <id>_S   sweep level line (dotted) at the swept zone edge      |
//|   <id>_PE/_PS/_PT  plan entry / stop / target levels             |
//|   BANNER   corner label (always present while the file is fresh) |
//+------------------------------------------------------------------+
#property copyright "SMC — Structure Draw (visualization only, no strategy logic)"
#property version   "1.00"
#property strict

input string InpFileName          = "smc_structure_draw.txt"; // Publisher file (terminal Files dir)
input string InpSymbolFilter      = "";                       // Required file symbol ("" = chart symbol)
input string InpPrefix            = "SMC_SD_";                // Chart object name prefix
input int    InpMaxAgeSec         = 120;                      // File older than this → clear all objects
input int    InpTimerSeconds      = 1;                        // Timer period (seconds)
input bool   InpDrawPOI           = true;                     // Draw POI zone rectangles
input bool   InpDrawSweep         = true;                     // Draw sweep level lines
input bool   InpDrawSeek          = true;                     // Draw armed-POI state texts
input bool   InpDrawPlan          = true;                     // Draw planned entry/stop/target levels
input color  InpColorBull         = clrLimeGreen;             // Bull (BUY) zone color
input color  InpColorBear         = clrTomato;                // Bear (SELL) zone color
input color  InpColorSweep        = clrOrange;                // Sweep line color
input color  InpColorPlanEntry    = clrDeepSkyBlue;           // Plan entry level color
input color  InpColorPlanSL       = clrRed;                   // Plan stop level color
input color  InpColorPlanTP       = clrLime;                  // Plan target level color
input int    InpZoneWindowHours   = 36;                       // Rectangle time window around now (hours)

// --- session state ------------------------------------------------ //
string   g_lastDrawSymbol = "";    // chart symbol at the last pass (change → clear)
datetime g_fileEpoch      = 0;     // header ts_utc as epoch seconds (0 = none)

//+------------------------------------------------------------------+
int OnInit()
{
   EventSetTimer(MathMax(1, InpTimerSeconds));
   Print("SMC Structure Draw: VISUALIZATION ONLY — NOT A STRATEGY CHANGE ",
         "(reads ", InpFileName, "; draw-only, no trading logic here)");
   return (INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   ObjectsDeleteAll(0, InpPrefix);      // removal / parameter change / chart close
   ChartRedraw();
}

//+------------------------------------------------------------------+
void OnTimer()
{
   // Chart symbol changed → our objects are meaningless there; wipe + resync.
   if(_Symbol != g_lastDrawSymbol)
   {
      if(g_lastDrawSymbol != "")
         ObjectsDeleteAll(0, InpPrefix);
      g_lastDrawSymbol = _Symbol;
   }

   int h = FileOpen(InpFileName, FILE_READ | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      ClearAll();                       // missing/unreadable → fail-safe clear
      return;
   }
   string schema = FileIsEnding(h) ? "" : FileReadString(h);
   if(StringFind(schema, "SMC_STRUCTURE_DRAW v1") != 0)
   {
      FileClose(h);                     // unknown/foreign file → clear, no spam
      ClearAll();
      return;
   }
   string header = FileIsEnding(h) ? "" : FileReadString(h);
   FileClose(h);

   string sym       = "";
   long   fileEpoch = 0;
   if(!ParseHeader(header, sym, fileEpoch))
   {
      ClearAll();
      return;
   }
   string wantSym = (InpSymbolFilter == "") ? g_lastDrawSymbol : InpSymbolFilter;
   if(wantSym != "" && sym != wantSym)
   {
      ClearAll();                       // publisher targets another symbol
      return;
   }
   if(fileEpoch <= 0 || (TimeGMT() - fileEpoch) > InpMaxAgeSec)
   {
      ClearAll();                       // stale → chart says nothing
      return;
   }
   g_fileEpoch = (datetime)fileEpoch;

   // Records: reread past the two header lines into memory, then draw.
   h = FileOpen(InpFileName, FILE_READ | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      ClearAll();
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
      DrawBanner();
   else
      ClearAll();                       // zero records → banner alone is not a state
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
   epochOut = TimestampToEpoch(stamp);
   return (epochOut > 0);
}

//+------------------------------------------------------------------+
//| Parse "YYYY-MM-DDTHH:MM:SSZ" → UTC epoch seconds (0 on garbage). |
//+------------------------------------------------------------------+
long TimestampToEpoch(const string stamp)
{
   // Fixed UTC ISO shape — same manual parse as the safety watchdog EA.
   if(StringLen(stamp) < 19)
      return (0);
   MqlDateTime dt;
   dt.year        = (int)StringToInteger(StringSubstr(stamp, 0, 4));
   dt.mon         = (int)StringToInteger(StringSubstr(stamp, 5, 2));
   dt.day         = (int)StringToInteger(StringSubstr(stamp, 8, 2));
   dt.hour        = (int)StringToInteger(StringSubstr(stamp, 11, 2));
   dt.min         = (int)StringToInteger(StringSubstr(stamp, 14, 2));
   dt.sec         = (int)StringToInteger(StringSubstr(stamp, 17, 2));
   dt.day_of_week = 0;
   dt.day_of_year = 0;
   if(dt.year < 2020 || dt.mon < 1 || dt.mon > 12 || dt.day < 1 || dt.day > 31)
      return (0);
   return (long)(StructToTime(dt));     // UTC per terminal time settings
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
//| Draw every record; true when at least one object was drawn.      |
//| Publisher emits POI rows before SWEEP/SEEK/PLAN rows, so the     |
//| POI lookup arrays are complete before the later rows need them.  |
//+------------------------------------------------------------------+
bool DrawRecords(const string &lines[], const int count)
{
   // Display-only time window: recent past → just past now, so zones live
   // on the visible recent window and follow the chart automatically.
   datetime now    = TimeCurrent();
   // Explicit (datetime) casts on both RHS: datetime-minus-long yields long,
   // which warns C4240 when assigned back to a datetime (fixed in the merged
   // watchdog 2026-10-22; mirrored here so the reference source stays clean).
   datetime tLeft  = (datetime)(now - (long)InpZoneWindowHours * 3600);
   datetime tRight = (datetime)(now + 2 * 3600);
   bool anyDrawn = false;

   int  cap     = count > 0 ? count : 1;
   string poiId[];   ArrayResize(poiId, cap);
   double poiTop[];  ArrayResize(poiTop, cap);
   double poiBot[];  ArrayResize(poiBot, cap);
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
            poiTop[poiN] = high;
            poiBot[poiN] = low;
            poiN++;
         }
         string name = InpPrefix + pid + "_Z";
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
         string lname = InpPrefix + pid + "_L";
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
         string name = InpPrefix + pid + "_S";
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
            string zname = InpPrefix + pid + "_Z";
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
         if(DrawPlanLine(InpPrefix + pid + "_PE", entry, InpColorPlanEntry,
                         STYLE_DASH, "PLAN entry (poi " + pid + ")"))
            { AddSeen(seen, seenCount, seenMax, InpPrefix + pid + "_PE"); anyDrawn = true; }
         if(DrawPlanLine(InpPrefix + pid + "_PS", sl, InpColorPlanSL,
                         STYLE_DOT, "PLAN stop (poi " + pid + ")"))
            { AddSeen(seen, seenCount, seenMax, InpPrefix + pid + "_PS"); anyDrawn = true; }
         if(DrawPlanLine(InpPrefix + pid + "_PT", tp, InpColorPlanTP,
                         STYLE_DOT, "PLAN target (poi " + pid + ")"))
            { AddSeen(seen, seenCount, seenMax, InpPrefix + pid + "_PT"); anyDrawn = true; }
      }
   }

   // Orphan reconcile: remove prefix objects this pass did NOT see —
   // expired POIs / cleared sweeps vanish the same tick their row does.
   for(int j = ObjectsTotal(0) - 1; j >= 0; j--)
   {
      string name = ObjectName(0, j);
      if(StringFind(name, InpPrefix) != 0 || name == InpPrefix + "BANNER")
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
//| Banner corner label — the EA's only authoritative statement:      |
//| VISUALIZATION ONLY, NOT A STRATEGY CHANGE. Refreshed every pass. |
//+------------------------------------------------------------------+
void DrawBanner()
{
   const string name = InpPrefix + "BANNER";
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, 8);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, 22);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrSilver);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 9);
   ObjectSetString(0, name, OBJPROP_TEXT,
                   "SMC STRUCTURE DRAW — VISUALIZATION ONLY (NOT A STRATEGY CHANGE)");
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
}

//+------------------------------------------------------------------+
//| Clear ALL prefix objects (stale / missing / symbol mismatch).    |
//+------------------------------------------------------------------+
void ClearAll()
{
   ObjectsDeleteAll(0, InpPrefix);
   ChartRedraw();
}
//+------------------------------------------------------------------+
