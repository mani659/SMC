"""Frozen thresholds — single source of truth.

Every value in this module comes from ``00_LOCKED/LOCKED_DECISIONS.md``
(Rev 5, frozen 2026-09-01). Section references are cited inline as §N.
**Do not invent numbers and do not edit these values** without explicit
session authorization (see the header of LOCKED_DECISIONS.md).

Constants are grouped by the locked section they come from. The exact
names from ``00_LOCKED/TODO.md`` Phase 0 are used verbatim so that the
unit tests can assert their presence and value.
"""

# ---------------------------------------------------------------------------
# §28 — RISK LAYER THRESHOLDS (Phase 5) — LOCKED 2026-09-07
# ---------------------------------------------------------------------------
# The v25_DIAG risk thresholds were formally locked by the Lead Architect on
# 2026-09-07 (Risk Constants Lock) and are transcribed in the §28 group at
# the bottom of this module, mirroring LOCKED_DECISIONS.md §28. ADX gate and
# ATR floor are locked but conditional (port only if still needed). Items
# still deliberately deferred (not in this module yet): Immediate Trail,
# fixed-dollar risk mode, fixed-lot fallback, dynamic SL buffers (trend/
# range), PureRunner TP RR. See the note at the bottom of this file.
# ---------------------------------------------------------------------------

__all__ = [
    # §2 — EQH/EQL
    "EQH_EQL_TOLERANCE",
    # §2 — Session windows (UTC)
    "ASIA_START_HOUR_UTC",
    "ASIA_END_HOUR_UTC",
    "LONDON_START_HOUR_UTC",
    "LONDON_END_HOUR_UTC",
    "NY_START_HOUR_UTC",
    "NY_END_HOUR_UTC",
    # §1 — Confluence scoring
    "CONFLUENCE_BASE_TAGS",
    "CONFLUENCE_ELEVATED_TAGS",
    "CONFLUENCE_INSTITUTIONAL_TAGS",
    # §3 — Displacement
    "DISPLACEMENT_MIN_ATR",
    "DISPLACEMENT_PREFERRED_ATR",
    "DISPLACEMENT_HARD_FAIL",
    # §13 — Zone refinement
    "ZONE_REFINEMENT_ATR",
    # §6 — Dealing range / Premium-Discount
    "DISCOUNT_THRESHOLD",
    "PREMIUM_THRESHOLD",
    "EQUILIBRIUM_MIN",
    "EQUILIBRIUM_MAX",
    # §5 / §23 — Unfilled order expiry
    "M5_EXPIRY_BARS",
    "M1_EXPIRY_BARS",
    # §7 — Inducement scoring
    "INDUCEMENT_WITH_SCORE",
    "INDUCEMENT_WITHOUT_SCORE",
    # §11 — News protocol
    "NEWS_HARD_CANCEL_MINUTES",
    "NEWS_RE_EVALUATE_MINUTES",
    # §21 / §26 — Model 8
    "M8_HTF_OVERLAP_BONUS",
    "M8_MIN_RR",
    "M8_SL_MIN_PIPS",
    "M8_SL_MAX_PIPS",
    # §27 — Structural swing N-bar confirmation
    "N_BAR_HTF",
    "N_BAR_LTF",
    # §24 — Trigger expiry windows
    "TRIGGER_A_EXPIRY",
    "TRIGGER_B_EXPIRY",
    "TRIGGER_C_EXPIRY_EXTRA",
    "TRIGGER_D_EXPIRY",
    "TRIGGER_E_EXPIRY",
    "TRIGGER_F_EXPIRY",
    "TRIGGER_D_ENGULFING_FILL",
    # §28 — Risk layer thresholds (Phase 5)
    "PURE_RUNNER_BE_ATR",
    "PURE_RUNNER_BE_BUFFER_ATR",
    "CIRCUIT_BREAKER_LOSS_COUNT",
    "CIRCUIT_BREAKER_PAUSE_HOURS",
    "SAME_LEVEL_GUARD_ATR",
    "SAME_LEVEL_GUARD_COOLDOWN_BARS",
    "FRIDAY_EOD_CLOSE_HOUR_UTC",
    "SPREAD_MAX_ATR",
    "SPREAD_GRADE_MULTIPLIERS",
    "SPREAD_GRADE_SCORE_THRESHOLDS",
    "SWEEP_GUARD_ZONE_ATR",
    "SWEEP_GUARD_COOLDOWN_BARS",
    "RISK_PCT_MIN",
    "RISK_PCT_MAX",
    "LOT_MAX_SAFETY",
    "ADX_MIN_ENTRY",
    "ATR_FLOOR_MIN_SL",
]

# ---------------------------------------------------------------------------
# §2 — EQH/EQL tolerance (XAUUSD)
# ---------------------------------------------------------------------------
EQH_EQL_TOLERANCE = 4.5  # pips, FROZEN (§2: "≤ 4.5 pips tolerance on XAUUSD")

# ---------------------------------------------------------------------------
# §2 — Session windows (UTC). Asia 00:00–07:00, London 07:00–13:00,
# NY 13:00–20:00 UTC. Hours are inclusive-of-start / exclusive-of-end.
# ---------------------------------------------------------------------------
ASIA_START_HOUR_UTC = 0
ASIA_END_HOUR_UTC = 7
LONDON_START_HOUR_UTC = 7
LONDON_END_HOUR_UTC = 13
NY_START_HOUR_UTC = 13
NY_END_HOUR_UTC = 20

# ---------------------------------------------------------------------------
# §1 — Confluence scoring ("1 tag = base, 2 = elevated, 3+ = institutional")
# ---------------------------------------------------------------------------
CONFLUENCE_BASE_TAGS = 1
CONFLUENCE_ELEVATED_TAGS = 2
CONFLUENCE_INSTITUTIONAL_TAGS = 3

# ---------------------------------------------------------------------------
# §3 — Displacement requirements
# ---------------------------------------------------------------------------
DISPLACEMENT_MIN_ATR = 1.0        # Minimum displacement: 1× ATR
DISPLACEMENT_PREFERRED_ATR = 1.5  # Preferred: > 1.5× ATR (institutional sponsorship)
DISPLACEMENT_HARD_FAIL = 0.5      # Hard fail: displacement < 0.5× ATR

# ---------------------------------------------------------------------------
# §13 — Zone refinement tolerance (Pillar 1, adaptive)
# ---------------------------------------------------------------------------
ZONE_REFINEMENT_ATR = 0.5  # ±0.5× ATR

# ---------------------------------------------------------------------------
# §6 — Dealing range / Premium-Discount (coupled to POI detection TF)
# ---------------------------------------------------------------------------
DISCOUNT_THRESHOLD = 0.45  # Bullish POIs must be below 45% of dealing range
PREMIUM_THRESHOLD = 0.55   # Bearish POIs must be above 55% of dealing range
EQUILIBRIUM_MIN = 0.45     # 45%–55% band = REJECT (consolidation trap)
EQUILIBRIUM_MAX = 0.55

# ---------------------------------------------------------------------------
# §5 / §23 — Unfilled order expiry (bars on the order timeframe)
# ---------------------------------------------------------------------------
M5_EXPIRY_BARS = 12  # M5: 12 bars (~1 hour)
M1_EXPIRY_BARS = 30  # M1: 30 bars (~30 minutes)

# ---------------------------------------------------------------------------
# §7 — Inducement scoring (soft gate, never hard reject)
# ---------------------------------------------------------------------------
INDUCEMENT_WITH_SCORE = 1.0     # Inducement present → 100% score
INDUCEMENT_WITHOUT_SCORE = 0.7  # No inducement → 70% score (still tradeable)

# ---------------------------------------------------------------------------
# §11 — News protocol (high-impact: US CPI, NFP, FOMC)
# ---------------------------------------------------------------------------
NEWS_HARD_CANCEL_MINUTES = 15  # Hard-cancel pending POI limits before event
NEWS_RE_EVALUATE_MINUTES = 30  # Re-evaluate after release

# ---------------------------------------------------------------------------
# §21 / §26 — Model 8: HTF Demand/Supply (D1/H4)
# ---------------------------------------------------------------------------
M8_HTF_OVERLAP_BONUS = 0.10  # +0.10 quality-score bonus if D1+H4 zones overlap
M8_MIN_RR = 5.0              # Minimum risk:reward target 1:5
M8_SL_MIN_PIPS = 2.0         # Typical SL width range (2–5 pips)
M8_SL_MAX_PIPS = 5.0

# ---------------------------------------------------------------------------
# §27 — Structural swing N-bar confirmation parameters (FROZEN)
# ---------------------------------------------------------------------------
N_BAR_HTF = 5  # Daily / H4 / H1
N_BAR_LTF = 3  # M30 / M15 / M5 / M1

# ---------------------------------------------------------------------------
# §24 — Trigger expiry windows (V1 defaults)
# ---------------------------------------------------------------------------
TRIGGER_A_EXPIRY = 20  # A – CHOCH Reversal: 20 M5 bars
TRIGGER_B_EXPIRY = 30  # B – Leading Diagonal: 30 bars after Wave 5 completion
TRIGGER_C_EXPIRY_EXTRA = 3  # C – Ending Diagonal: sweep candle + 3 bars
TRIGGER_D_EXPIRY = 1    # D – Two-Bar Reversal: bar immediately following only
TRIGGER_E_EXPIRY = 15   # E – RSI Divergence: 15 bars after pattern completion
TRIGGER_F_EXPIRY = 1    # F – BOS + OB Continuation: first touch only

# ---------------------------------------------------------------------------
# §10 — Two-Bar Reversal entry (frozen; transcribed at Phase 4 kickoff per the
# Phase 0 audit note "it belongs with Trigger D and should be added as a named
# constant when Phase 4 begins")
# ---------------------------------------------------------------------------
TRIGGER_D_ENGULFING_FILL = 0.5  # Limit order at 50% of the engulfing body (NOT market)

# ---------------------------------------------------------------------------
# §28 — Risk layer thresholds (Phase 5) — LOCKED 2026-09-07
# ---------------------------------------------------------------------------
# Formally locked by the Lead Architect on 2026-09-07 (Risk Constants Lock,
# based on the v25_DIAG constant proposal). Source: GOLD_SMC_v25_DIAG.mq5
# proven inputs; authoritative record in LOCKED_DECISIONS.md §28. These are
# consumed by `smc/risk/` components ported in Phase 5.
# ---------------------------------------------------------------------------

# --- PureRunner / break-even management (v24 RC2: BE independent of PureRunner) ---
PURE_RUNNER_BE_ATR = 1.0      # Move SL to break-even at 1.0× ATR movement (InpBEActivRR)
PURE_RUNNER_BE_BUFFER_ATR = 0.10  # BE price = entry + dir × ATR × this buffer (InpBEBuffer)

# --- Circuit breaker: 3 consecutive losses → 4h pause (Z-score validated) ---
CIRCUIT_BREAKER_LOSS_COUNT = 3   # Consecutive losses to trigger the pause (InpCBLossCount)
CIRCUIT_BREAKER_PAUSE_HOURS = 4  # Hours to pause; resets on any win or new day (InpCBPauseHours)

# --- Same-level SL re-entry guard ---
SAME_LEVEL_GUARD_ATR = 0.15  # New SL within this × ATR of last SL = blocked (InpSameSLZone; LOCKED 0.15 = running default, not the outdated 0.1 comment)
SAME_LEVEL_GUARD_COOLDOWN_BARS = 4  # Bars to block re-entry (InpSameSLCooldown)

# --- Friday EOD force-close ---
FRIDAY_EOD_CLOSE_HOUR_UTC = 20  # Force-close all positions at 20:00 UTC Friday (InpFridayCloseHour)

# --- Spread grading (ATR-relative, score-tiered — v25 semantics, not point bands) ---
SPREAD_MAX_ATR = 0.15  # Max spread as fraction of ATR, in points (InpMaxSpreadATR)
SPREAD_GRADE_MULTIPLIERS = {"A+": 1.5, "A": 1.0, "B": 0.7, "C": 0.5}  # × base spread by grade (v19.7)
SPREAD_GRADE_SCORE_THRESHOLDS = {"A+": 8, "A": 5, "B": 3, "C": 0}  # Min score per grade (C = below 3)

# --- Sweep / failed-sweep re-entry guard ---
SWEEP_GUARD_ZONE_ATR = 0.5  # ATR radius to consider the same sweep level (InpFailedSweepZone)
SWEEP_GUARD_COOLDOWN_BARS = 4  # Bars to block after SL on same sweep level (InpPostLossCooldown)

# --- Risk % band (documented 0.5–1.0%; caller/risk engine chooses within) ---
RISK_PCT_MIN = 0.5  # Minimum risk % of equity per trade
RISK_PCT_MAX = 1.0  # Maximum risk % of equity per trade

# --- Lot safety cap ---
LOT_MAX_SAFETY = 0.10  # Absolute cap on computed lots regardless of formula (InpMaxLotSafety)

# --- Optional / conditional gates (locked; port only if still needed per TODO Phase 5) ---
ADX_MIN_ENTRY = 25.0  # ADX trend gate: block ALL entries when ADX < this (production value)
ATR_FLOOR_MIN_SL = 1.0  # SLD/ATR floor: block entry when stop distance < this × ATR (production value)

# ---------------------------------------------------------------------------
# NOTE — Phase 5 risk parameters still deferred (v25_DIAG port scope)
# ---------------------------------------------------------------------------
# Still deliberately excluded (per the Risk Constants Lock decision — do not
# add without authorization): Immediate Trail (InpImmTrailATR/Buffer),
# fixed-dollar risk mode (InpFixedRiskDollars), fixed-lot fallback
# (InpFixedLot), dynamic SL buffers (InpSLBufTrend/InpSLBufRange), and
# PureRunner TP in R-multiples (InpPureRunnerRR). Primary Phase 5 exit model:
# PureRunner (BE at 1.0× ATR + buffer) + FVG Invalidation.