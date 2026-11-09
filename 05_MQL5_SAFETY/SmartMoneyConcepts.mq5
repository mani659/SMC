//+---------------------   ---------------------------------------------+
//|                                        SmartMoneyConcepts.mq5    |
//|                                      Copyright, Hammad Dilber    |
//|          Structure, OB, FVG, EQH/EQL + BUY/SELL Signal Arrows    |
//+------------------------------------------------------------------+
#property copyright   "Copyright, Hammad Dilber"
#property version     "3.00"
#property description "SMC: BOS/CHoCH + OB + FVG + Signals"
#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots   2

#property indicator_label1  "BUY Signal"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrLime
#property indicator_width1  2

#property indicator_label2  "SELL Signal"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrRed
#property indicator_width2  2

//+------------------------------------------------------------------+
//| INPUTS                                                            |
//+------------------------------------------------------------------+
input group           "=== Market Structure ==="
input bool            InpShowStructure   = true;
input int             InpSwingLength     = 10;            // Swing Length (bars)
input bool            InpShowSwingLabels = true;          // Show HH/HL/LH/LL
input color           InpBullColor       = clrDodgerBlue;
input color           InpBearColor       = clrRed;

input group           "=== Order Blocks ==="
input bool            InpShowOB          = true;
input int             InpMaxOB           = 5;
input int             InpOBExtend        = 20;            // OB Extend (bars)
input color           InpBullOBColor     = clrCornflowerBlue;
input color           InpBearOBColor     = clrLightCoral;

input group           "=== Fair Value Gaps ==="
input bool            InpShowFVG         = true;
input color           InpBullFVGColor    = clrMediumSeaGreen;
input color           InpBearFVGColor    = clrSalmon;
input int             InpFVGExtend       = 10;            // FVG Extend (bars)

input group           "=== Equal Highs & Lows ==="
input bool            InpShowEQHL        = true;
input int             InpEQHLLen         = 5;
input double          InpEQHLSens        = 0.5;
input color           InpEQHColor        = clrOrangeRed;
input color           InpEQLColor        = clrLimeGreen;

input group           "=== Signal Settings ==="
input bool            InpShowSignals     = true;          // Show BUY/SELL Signals
input bool            InpRequireFVG      = false;         // Require FVG near OB for signal
input bool            InpAlerts          = true;          // Popup Alerts
input bool            InpEmailAlert      = false;         // Email Alerts
input bool            InpPushAlert       = false;         // Push Notification

//+------------------------------------------------------------------+
//| STRUCTURES                                                        |
//+------------------------------------------------------------------+
struct SOrderBlock
{
   double   top;
   double   bottom;
   datetime startTime;
   datetime endTime;
   int      bias;
   bool     active;
   bool     signalGiven;
   string   name;
};

struct SFVG
{
   double   top;
   double   bottom;
   datetime startTime;
   datetime endTime;
   int      bias;
   bool     active;
   string   name;
};

//+------------------------------------------------------------------+
//| BUFFERS                                                           |
//+------------------------------------------------------------------+
double BuyBuffer[];
double SellBuffer[];

//+------------------------------------------------------------------+
//| GLOBALS                                                           |
//+------------------------------------------------------------------+
string   g_pfx       = "SMC3_";
int      g_atrHandle = INVALID_HANDLE;
double   g_atr       = 0.0;

double   g_phLevel   = 0.0;
double   g_plLevel   = 0.0;
int      g_phIdx     = -1;
int      g_plIdx     = -1;
int      g_trend     = 0;

SOrderBlock g_bullOBs[];
SOrderBlock g_bearOBs[];
SFVG        g_fvgs[];

int      g_strCnt    = 0;
int      g_swHighCnt = 0;
int      g_swLowCnt  = 0;

datetime g_lastBuyAlertTime  = 0;
datetime g_lastSellAlertTime = 0;

//+------------------------------------------------------------------+
//| OnInit                                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0, BuyBuffer,  INDICATOR_DATA);
   SetIndexBuffer(1, SellBuffer, INDICATOR_DATA);

   PlotIndexSetInteger(0, PLOT_ARROW, 233);
   PlotIndexSetInteger(1, PLOT_ARROW, 234);

   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   ArraySetAsSeries(BuyBuffer,  false);
   ArraySetAsSeries(SellBuffer, false);

   if(InpSwingLength < 2)
   {
      Alert("SMC: SwingLength must be >= 2");
      return INIT_PARAMETERS_INCORRECT;
   }

   g_atrHandle = iATR(_Symbol, _Period, 14);
   if(g_atrHandle == INVALID_HANDLE)
   {
      Alert("SMC: ATR handle failed");
      return INIT_FAILED;
   }

   CleanChart();
   Print("SMC v3 loaded on ", _Symbol, " ", EnumToString(_Period));
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   CleanChart();
   if(g_atrHandle != INVALID_HANDLE)
      IndicatorRelease(g_atrHandle);
}

//+------------------------------------------------------------------+
//| OnCalculate                                                       |
//+------------------------------------------------------------------+
int OnCalculate(const int      rates_total,
                const int      prev_calculated,
                const datetime &time[],
                const double   &open[],
                const double   &high[],
                const double   &low[],
                const double   &close[],
                const long     &tick_volume[],
                const long     &volume[],
                const int      &spread[])
{
   int minBars = InpSwingLength * 2 + 5;
   if(rates_total < minBars) return 0;

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(g_atrHandle, 0, 0, 3, atrBuf) > 0)
      g_atr = atrBuf[0];
   else
      g_atr = _Point * 50;

   if(prev_calculated <= 0)
   {
      ArrayInitialize(BuyBuffer,  EMPTY_VALUE);
      ArrayInitialize(SellBuffer, EMPTY_VALUE);
      CleanChart();

      for(int i = InpSwingLength; i < rates_total - InpSwingLength; i++)
         ProcessBar(i, time, open, high, low, close, rates_total);
   }
   else
   {
      int startBar = prev_calculated - InpSwingLength - 1;
      if(startBar < InpSwingLength) startBar = InpSwingLength;
      for(int i = startBar; i < rates_total - InpSwingLength; i++)
         ProcessBar(i, time, open, high, low, close, rates_total);
   }

   if(rates_total > 0)
   {
      for(int i = 0; i < ArraySize(g_bullOBs); i++)
         if(g_bullOBs[i].active)
         {
            datetime maxEdge = g_bullOBs[i].startTime + PeriodSeconds() * InpOBExtend;
            ObjectSetInteger(0, g_bullOBs[i].name, OBJPROP_TIME, 1, maxEdge);
         }
      for(int i = 0; i < ArraySize(g_bearOBs); i++)
         if(g_bearOBs[i].active)
         {
            datetime maxEdge = g_bearOBs[i].startTime + PeriodSeconds() * InpOBExtend;
            ObjectSetInteger(0, g_bearOBs[i].name, OBJPROP_TIME, 1, maxEdge);
         }
   }

   int last = rates_total - 1;
   MitigateOBs(high[last], low[last], close[last]);
   MitigateFVGs(high[last], low[last]);

   ChartRedraw(0);
   return rates_total;
}

//+------------------------------------------------------------------+
//| ProcessBar                                                        |
//+------------------------------------------------------------------+
void ProcessBar(int i,
                const datetime &time[],
                const double   &open[],
                const double   &high[],
                const double   &low[],
                const double   &close[],
                int total)
{
   bool ph = IsPivotHigh(i, high, total);
   bool pl = IsPivotLow( i, low,  total);

   if(ph) HandlePivotHigh(i, time, open, high, low, close, total);
   if(pl) HandlePivotLow( i, time, open, high, low, close, total);

   if(InpShowFVG)  CheckFVG( i, time, high, low, total);
   if(InpShowEQHL) CheckEQHL(i, time, high, low, total);

   if(InpShowSignals && i >= 1 && i < total - 1)
      CheckSignals(i, time, open, high, low, close, total);
}

//+------------------------------------------------------------------+
//| PIVOT DETECTION                                                   |
//+------------------------------------------------------------------+
bool IsPivotHigh(int idx, const double &high[], int total)
{
   int len = InpSwingLength;
   if(idx - len < 0 || idx + len >= total) return false;
   double p = high[idx];
   for(int k = 1; k <= len; k++)
      if(high[idx - k] >= p || high[idx + k] >= p) return false;
   return true;
}

bool IsPivotLow(int idx, const double &low[], int total)
{
   int len = InpSwingLength;
   if(idx - len < 0 || idx + len >= total) return false;
   double p = low[idx];
   for(int k = 1; k <= len; k++)
      if(low[idx - k] <= p || low[idx + k] <= p) return false;
   return true;
}

//+------------------------------------------------------------------+
//| PIVOT HIGH HANDLER                                                |
//+------------------------------------------------------------------+
void HandlePivotHigh(int idx,
                     const datetime &time[],
                     const double   &open[],
                     const double   &high[],
                     const double   &low[],
                     const double   &close[],
                     int total)
{
   double   pivPrice = high[idx];
   datetime pivTime  = time[idx];

   if(InpShowSwingLabels && g_phLevel > 0)
   {
      string tag = (pivPrice > g_phLevel) ? "HH" : "LH";
      DrawText(g_pfx + "SWH_" + IntegerToString(g_swHighCnt++),
               pivTime, pivPrice, tag, InpBearColor, ANCHOR_LOWER);
   }

   if(g_phLevel > 0 && pivPrice > g_phLevel && InpShowStructure)
   {
      string tag = (g_trend == -1) ? "CHoCH" : "BOS";
      g_strCnt++;
      datetime t1 = (g_phIdx >= 0) ? time[g_phIdx] : time[idx];
      DrawTrendLine(g_pfx + "STR_L_" + IntegerToString(g_strCnt),
                    t1, g_phLevel, pivTime, g_phLevel, InpBullColor);
      DrawText(g_pfx + "STR_T_" + IntegerToString(g_strCnt),
               t1 + (pivTime - t1) / 2, g_phLevel, tag, InpBullColor, ANCHOR_LOWER);
      g_trend = 1;

      if(InpShowOB)
         AddOB(idx, 1, time, open, high, low, close, total);
   }

   g_phLevel = pivPrice;
   g_phIdx   = idx;
}

//+------------------------------------------------------------------+
//| PIVOT LOW HANDLER                                                 |
//+------------------------------------------------------------------+
void HandlePivotLow(int idx,
                    const datetime &time[],
                    const double   &open[],
                    const double   &high[],
                    const double   &low[],
                    const double   &close[],
                    int total)
{
   double   pivPrice = low[idx];
   datetime pivTime  = time[idx];

   if(InpShowSwingLabels && g_plLevel > 0)
   {
      string tag = (pivPrice < g_plLevel) ? "LL" : "HL";
      DrawText(g_pfx + "SWL_" + IntegerToString(g_swLowCnt++),
               pivTime, pivPrice, tag, InpBullColor, ANCHOR_UPPER);
   }

   if(g_plLevel > 0 && pivPrice < g_plLevel && InpShowStructure)
   {
      string tag = (g_trend == 1) ? "CHoCH" : "BOS";
      g_strCnt++;
      datetime t1 = (g_plIdx >= 0) ? time[g_plIdx] : time[idx];
      DrawTrendLine(g_pfx + "STR_L_" + IntegerToString(g_strCnt),
                    t1, g_plLevel, pivTime, g_plLevel, InpBearColor);
      DrawText(g_pfx + "STR_T_" + IntegerToString(g_strCnt),
               t1 + (pivTime - t1) / 2, g_plLevel, tag, InpBearColor, ANCHOR_UPPER);
      g_trend = -1;

      if(InpShowOB)
         AddOB(idx, -1, time, open, high, low, close, total);
   }

   g_plLevel = pivPrice;
   g_plIdx   = idx;
}

//+------------------------------------------------------------------+
//| ADD ORDER BLOCK                                                   |
//+------------------------------------------------------------------+
void AddOB(int pivIdx, int obBias,
           const datetime &time[],
           const double   &open[],
           const double   &high[],
           const double   &low[],
           const double   &close[],
           int total)
{
   int found = -1;
   for(int k = pivIdx - 1; k >= MathMax(0, pivIdx - InpSwingLength); k--)
   {
      if(obBias == 1  && close[k] < open[k]) { found = k; break; }
      if(obBias == -1 && close[k] > open[k]) { found = k; break; }
   }
   if(found < 0) return;

   double bodyTop = MathMax(open[found], close[found]);
   double bodyBot = MathMin(open[found], close[found]);
   double bodyMid = (bodyTop + bodyBot) / 2.0;
   double obTop, obBottom;

   if(obBias == 1)
   {
      obTop    = bodyMid;
      obBottom = bodyBot;
   }
   else
   {
      obTop    = bodyTop;
      obBottom = bodyMid;
   }

   if(obTop - obBottom < _Point) return;

   if(obBias == 1)
   {
      for(int j = 0; j < ArraySize(g_bullOBs); j++)
         if(MathAbs(g_bullOBs[j].top - obTop) < g_atr * 0.3) return;
   }
   else
   {
      for(int j = 0; j < ArraySize(g_bearOBs); j++)
         if(MathAbs(g_bearOBs[j].top - obTop) < g_atr * 0.3) return;
   }

   SOrderBlock ob;
   ob.top         = obTop;
   ob.bottom      = obBottom;
   ob.startTime   = time[found];
   ob.endTime     = time[found] + PeriodSeconds() * InpOBExtend;
   ob.bias        = obBias;
   ob.active      = true;
   ob.signalGiven = false;
   ob.name        = g_pfx + "OB_" + (obBias == 1 ? "B" : "S") + "_" + IntegerToString((int)ob.startTime);

   color col = (obBias == 1) ? InpBullOBColor : InpBearOBColor;
   DrawBox(ob.name, ob.startTime, ob.endTime, ob.top, ob.bottom, col,
           (obBias == 1) ? "Bull OB" : "Bear OB");

   if(obBias == 1)
   {
      int n = ArraySize(g_bullOBs);
      if(n >= InpMaxOB) { ObjectDelete(0, g_bullOBs[0].name); ArrayRemoveOB(g_bullOBs, 0); n--; }
      ArrayResize(g_bullOBs, n + 1);
      g_bullOBs[n] = ob;
   }
   else
   {
      int n = ArraySize(g_bearOBs);
      if(n >= InpMaxOB) { ObjectDelete(0, g_bearOBs[0].name); ArrayRemoveOB(g_bearOBs, 0); n--; }
      ArrayResize(g_bearOBs, n + 1);
      g_bearOBs[n] = ob;
   }
}

//+------------------------------------------------------------------+
//| SIGNAL DETECTION                                                  |
//+------------------------------------------------------------------+
void CheckSignals(int idx,
                  const datetime &time[],
                  const double   &open[],
                  const double   &high[],
                  const double   &low[],
                  const double   &close[],
                  int total)
{
   if(idx < 1 || idx >= total) return;

   double bodySize    = MathAbs(close[idx] - open[idx]);
   bool isBullCandle  = (close[idx] > open[idx]) && (bodySize > g_atr * 0.1);
   bool isBearCandle  = (close[idx] < open[idx]) && (bodySize > g_atr * 0.1);

   if(isBullCandle)
   {
      for(int j = 0; j < ArraySize(g_bullOBs); j++)
      {
         if(!g_bullOBs[j].active)     continue;
         if(g_bullOBs[j].signalGiven) continue;
         if(time[idx] <= g_bullOBs[j].startTime) continue;

         bool inOB = (low[idx] <= g_bullOBs[j].top) &&
                     (low[idx] >= g_bullOBs[j].bottom - g_atr * 0.8);
         if(!inOB) continue;

         if(InpRequireFVG && !FVGNearby(g_bullOBs[j].top, g_bullOBs[j].bottom, 1))
            continue;

         BuyBuffer[idx] = low[idx] - g_atr * 0.3;
         g_bullOBs[j].signalGiven = true;

         if(InpAlerts && time[idx] != g_lastBuyAlertTime && idx >= total - 3)
         {
            g_lastBuyAlertTime = time[idx];
            string msg = "🟢 SMC BUY Signal | " + _Symbol + " " +
                         EnumToString(_Period) +
                         "\nEntry: " + DoubleToString(close[idx], _Digits);
            Alert(msg);
            if(InpEmailAlert) SendMail("SMC BUY — " + _Symbol, msg);
            if(InpPushAlert)  SendNotification(msg);
         }
         break;
      }
   }

   if(isBearCandle)
   {
      for(int j = 0; j < ArraySize(g_bearOBs); j++)
      {
         if(!g_bearOBs[j].active)     continue;
         if(g_bearOBs[j].signalGiven) continue;
         if(time[idx] <= g_bearOBs[j].startTime) continue;

         bool inOB = (high[idx] >= g_bearOBs[j].bottom) &&
                     (high[idx] <= g_bearOBs[j].top + g_atr * 0.8);
         if(!inOB) continue;

         if(InpRequireFVG && !FVGNearby(g_bearOBs[j].top, g_bearOBs[j].bottom, -1))
            continue;

         SellBuffer[idx] = high[idx] + g_atr * 0.3;
         g_bearOBs[j].signalGiven = true;

         if(InpAlerts && time[idx] != g_lastSellAlertTime && idx >= total - 3)
         {
            g_lastSellAlertTime = time[idx];
            string msg = "🔴 SMC SELL Signal | " + _Symbol + " " +
                         EnumToString(_Period) +
                         "\nEntry: " + DoubleToString(close[idx], _Digits);
            Alert(msg);
            if(InpEmailAlert) SendMail("SMC SELL — " + _Symbol, msg);
            if(InpPushAlert)  SendNotification(msg);
         }
         break;
      }
   }
}

//+------------------------------------------------------------------+
//| FVG CONFLUENCE CHECK                                              |
//+------------------------------------------------------------------+
bool FVGNearby(double obTop, double obBottom, int bias)
{
   for(int i = 0; i < ArraySize(g_fvgs); i++)
   {
      if(!g_fvgs[i].active)      continue;
      if(g_fvgs[i].bias != bias) continue;
      bool overlap = (g_fvgs[i].top >= obBottom - g_atr) &&
                     (g_fvgs[i].bottom <= obTop + g_atr);
      if(overlap) return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| FAIR VALUE GAP                                                    |
//+------------------------------------------------------------------+
void CheckFVG(int idx, const datetime &time[],
              const double &high[], const double &low[], int total)
{
   if(idx < 1 || idx + 1 >= total) return;

   bool bullFVG = (low[idx + 1] > high[idx - 1]);
   bool bearFVG = (high[idx + 1] < low[idx - 1]);
   if(!bullFVG && !bearFVG) return;

   double fTop, fBot;
   int    fBias;
   if(bullFVG) { fTop = low[idx + 1];  fBot = high[idx - 1]; fBias =  1; }
   else        { fTop = low[idx - 1];  fBot = high[idx + 1]; fBias = -1; }

   if(fTop - fBot < g_atr * 0.15) return;

   for(int j = 0; j < ArraySize(g_fvgs); j++)
      if(MathAbs(g_fvgs[j].top - fTop) < g_atr * 0.2 && g_fvgs[j].bias == fBias) return;

   SFVG fvg;
   fvg.top       = fTop;
   fvg.bottom    = fBot;
   fvg.startTime = time[idx];
   fvg.endTime   = time[idx] + PeriodSeconds() * InpFVGExtend;
   fvg.bias      = fBias;
   fvg.active    = true;
   fvg.name      = g_pfx + "FVG_" + (fBias == 1 ? "B" : "S") + "_" + IntegerToString((int)fvg.startTime);

   color col = (fBias == 1) ? InpBullFVGColor : InpBearFVGColor;
   DrawBox(fvg.name, fvg.startTime, fvg.endTime, fvg.top, fvg.bottom, col,
           (fBias == 1) ? "Bull FVG" : "Bear FVG");

   int n = ArraySize(g_fvgs);
   ArrayResize(g_fvgs, n + 1);
   g_fvgs[n] = fvg;
}

//+------------------------------------------------------------------+
//| EQUAL HIGHS & LOWS                                                |
//+------------------------------------------------------------------+
void CheckEQHL(int idx, const datetime &time[],
               const double &high[], const double &low[], int total)
{
   int len = InpEQHLLen;
   if(idx - len < 0 || idx + len >= total) return;

   if(IsPivotHighLen(idx, len, high, total) && g_phLevel > 0 && g_phIdx >= 0)
   {
      double diff = MathAbs(high[idx] - g_phLevel);
      if(diff > 0 && diff < InpEQHLSens * g_atr)
      {
         string lN = g_pfx + "EQH_L_" + IntegerToString((int)time[idx]);
         string tN = g_pfx + "EQH_T_" + IntegerToString((int)time[idx]);
         if(ObjectFind(0, lN) < 0)
         {
            DrawTrendLine(lN, time[g_phIdx], g_phLevel, time[idx], high[idx], InpEQHColor);
            DrawText(tN, time[idx], high[idx], "EQH", InpEQHColor, ANCHOR_LOWER);
         }
      }
   }

   if(IsPivotLowLen(idx, len, low, total) && g_plLevel > 0 && g_plIdx >= 0)
   {
      double diff = MathAbs(low[idx] - g_plLevel);
      if(diff > 0 && diff < InpEQHLSens * g_atr)
      {
         string lN = g_pfx + "EQL_L_" + IntegerToString((int)time[idx]);
         string tN = g_pfx + "EQL_T_" + IntegerToString((int)time[idx]);
         if(ObjectFind(0, lN) < 0)
         {
            DrawTrendLine(lN, time[g_plIdx], g_plLevel, time[idx], low[idx], InpEQLColor);
            DrawText(tN, time[idx], low[idx], "EQL", InpEQLColor, ANCHOR_UPPER);
         }
      }
   }
}

bool IsPivotHighLen(int idx, int len, const double &high[], int total)
{
   if(idx - len < 0 || idx + len >= total) return false;
   double p = high[idx];
   for(int k = 1; k <= len; k++)
      if(high[idx - k] >= p || high[idx + k] >= p) return false;
   return true;
}

bool IsPivotLowLen(int idx, int len, const double &low[], int total)
{
   if(idx - len < 0 || idx + len >= total) return false;
   double p = low[idx];
   for(int k = 1; k <= len; k++)
      if(low[idx - k] <= p || low[idx + k] <= p) return false;
   return true;
}

//+------------------------------------------------------------------+
//| MITIGATION                                                        |
//+------------------------------------------------------------------+
void MitigateOBs(double h, double l, double c)
{
   for(int i = 0; i < ArraySize(g_bullOBs); i++)
      if(g_bullOBs[i].active && c < g_bullOBs[i].bottom)
      {
         g_bullOBs[i].active = false;
         ObjectSetInteger(0, g_bullOBs[i].name, OBJPROP_COLOR,   clrSilver);
         ObjectSetInteger(0, g_bullOBs[i].name, OBJPROP_BGCOLOR, clrSilver);
      }
   for(int i = 0; i < ArraySize(g_bearOBs); i++)
      if(g_bearOBs[i].active && c > g_bearOBs[i].top)
      {
         g_bearOBs[i].active = false;
         ObjectSetInteger(0, g_bearOBs[i].name, OBJPROP_COLOR,   clrSilver);
         ObjectSetInteger(0, g_bearOBs[i].name, OBJPROP_BGCOLOR, clrSilver);
      }
}

void MitigateFVGs(double h, double l)
{
   for(int i = 0; i < ArraySize(g_fvgs); i++)
   {
      if(!g_fvgs[i].active) continue;
      if((g_fvgs[i].bias == 1  && l <= g_fvgs[i].top    && l >= g_fvgs[i].bottom) ||
         (g_fvgs[i].bias == -1 && h >= g_fvgs[i].bottom && h <= g_fvgs[i].top))
      {
         g_fvgs[i].active = false;
         ObjectSetInteger(0, g_fvgs[i].name, OBJPROP_COLOR,   clrSilver);
         ObjectSetInteger(0, g_fvgs[i].name, OBJPROP_BGCOLOR, clrSilver);
      }
   }
}

//+------------------------------------------------------------------+
//| DRAW HELPERS                                                      |
//+------------------------------------------------------------------+
void DrawBox(string name, datetime t1, datetime t2,
             double top, double bot, color col, string tip)
{
   if(ObjectFind(0, name) >= 0) return;
   if(top <= bot) return;
   ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, top, t2, bot);
   ObjectSetInteger(0, name, OBJPROP_COLOR,      col);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR,    col);
   ObjectSetInteger(0, name, OBJPROP_FILL,       true);
   ObjectSetInteger(0, name, OBJPROP_BACK,       true);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN,     true);
   ObjectSetString( 0, name, OBJPROP_TOOLTIP,    tip);
}

void DrawTrendLine(string name, datetime t1, double p1,
                   datetime t2, double p2, color col)
{
   if(ObjectFind(0, name) >= 0) return;
   ObjectCreate(0, name, OBJ_TREND, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, name, OBJPROP_COLOR,      col);
   ObjectSetInteger(0, name, OBJPROP_WIDTH,      1);
   ObjectSetInteger(0, name, OBJPROP_STYLE,      STYLE_DASH);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT,  false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN,     true);
}

void DrawText(string name, datetime t, double price, string txt,
              color col, ENUM_ANCHOR_POINT anchor)
{
   if(ObjectFind(0, name) >= 0) return;
   ObjectCreate(0, name, OBJ_TEXT, 0, t, price);
   ObjectSetString( 0, name, OBJPROP_TEXT,       txt);
   ObjectSetInteger(0, name, OBJPROP_COLOR,      col);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE,   9);
   ObjectSetString( 0, name, OBJPROP_FONT,       "Arial Bold");
   ObjectSetInteger(0, name, OBJPROP_ANCHOR,     anchor);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN,     true);
}

//+------------------------------------------------------------------+
//| CLEAN CHART                                                       |
//+------------------------------------------------------------------+
void CleanChart()
{
   int n = ObjectsTotal(0, 0, -1);
   for(int i = n - 1; i >= 0; i--)
   {
      string nm = ObjectName(0, i, 0, -1);
      if(StringFind(nm, g_pfx) == 0)
         ObjectDelete(0, nm);
   }
   ArrayResize(g_bullOBs, 0);
   ArrayResize(g_bearOBs, 0);
   ArrayResize(g_fvgs,    0);
   g_phLevel = 0; g_plLevel = 0;
   g_phIdx   = -1; g_plIdx  = -1;
   g_trend   = 0;
   g_strCnt  = 0; g_swHighCnt = 0; g_swLowCnt = 0;
   g_lastBuyAlertTime  = 0;
   g_lastSellAlertTime = 0;
}

void ArrayRemoveOB(SOrderBlock &arr[], int idx)
{
   int sz = ArraySize(arr);
   for(int i = idx; i < sz - 1; i++) arr[i] = arr[i + 1];
   ArrayResize(arr, sz - 1);
}
//+------------------------------------------------------------------+