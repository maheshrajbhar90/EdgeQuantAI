"""Named constants: defaults, indicator parameters, thresholds and column names.

Every value here is identical to the literal it replaced in the original
implementation. Changing any of them changes analysis output and is pinned by
the golden tests in ``tests/``.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# Data fetching
# --------------------------------------------------------------------------- #
DEFAULT_PERIOD: Final = "5y"
DEFAULT_INTERVAL: Final = "1d"
DEFAULT_EXCHANGE_SUFFIX: Final = ".NS"
LOCAL_TIMEZONE: Final = "Asia/Kolkata"

# --------------------------------------------------------------------------- #
# OHLCV / identifier columns
# --------------------------------------------------------------------------- #
DATE: Final = "Date"
DATETIME: Final = "Datetime"
OPEN: Final = "Open"
HIGH: Final = "High"
LOW: Final = "Low"
CLOSE: Final = "Close"
VOLUME: Final = "Volume"
TICKER: Final = "Ticker"
REQUIRED_OHLCV_COLUMNS: Final = (OPEN, HIGH, LOW, CLOSE, VOLUME)
DATE_COLUMN_CANDIDATES: Final = ("date", "datetime")

# --------------------------------------------------------------------------- #
# Indicator columns (added by ``add_indicators``, in insertion order)
# --------------------------------------------------------------------------- #
VMA20: Final = "VMA20"
EMA5: Final = "EMA5"
EMA9: Final = "EMA9"
EMA26: Final = "EMA26"
SMA50: Final = "SMA50"
SMA200: Final = "SMA200"
RSI: Final = "RSI"
MACD: Final = "MACD"
MACD_SIGNAL_LINE: Final = "Signal"
BB_UPPER: Final = "bb_upper"
BB_MIDDLE: Final = "bb_middle"
BB_LOWER: Final = "bb_lower"
STOCH_K: Final = "Stoch_k"
STOCH_D: Final = "stoch_d"
ATR: Final = "ATR"
ADX: Final = "ADX"
CHANGE: Final = "Change"
Z_SCORE: Final = "Z_score"
BB_DIRECTION: Final = "BB_Direction"
STOCH_DIRECTION: Final = "Stoch_Direction"
ATR_DIRECTION: Final = "ATR_Direction"
ADX_DIRECTION: Final = "ADX_Direction"

# Columns added by ``z_score``.
VOL_MEAN: Final = "vol_mean"
VOL_STD: Final = "vol_std"
VOL_ZSCORE: Final = "vol_zscore"

# Columns added by ``identify_candlestick_patterns``.
PATTERN: Final = "Pattern"
CODE: Final = "Code"

# --------------------------------------------------------------------------- #
# Indicator parameters
# --------------------------------------------------------------------------- #
MIN_ROWS_FOR_INDICATORS: Final = 200
VOLUME_MA_PERIOD: Final = 20
EMA_FAST_PERIOD: Final = 5
EMA_SHORT_PERIOD: Final = 9
EMA_LONG_PERIOD: Final = 26
SMA_MEDIUM_PERIOD: Final = 50
SMA_LONG_PERIOD: Final = 200
RSI_PERIOD: Final = 14
MACD_FAST_PERIOD: Final = 12
MACD_SLOW_PERIOD: Final = 26
MACD_SIGNAL_PERIOD: Final = 9
BBANDS_PERIOD: Final = 20
ATR_PERIOD: Final = 14
ADX_PERIOD: Final = 14
ZSCORE_WINDOW: Final = 20

# --------------------------------------------------------------------------- #
# Signal thresholds
# --------------------------------------------------------------------------- #
RSI_SIGNAL_THRESHOLD: Final = 60
STOCH_OVERBOUGHT: Final = 80
STOCH_OVERSOLD: Final = 20
ADX_STRONG_TREND: Final = 25
PRICE_DECIMALS: Final = 2

# --------------------------------------------------------------------------- #
# Direction labels
# --------------------------------------------------------------------------- #
NEUTRAL: Final = "Neutral"
BULLISH: Final = "Bullish"
BEARISH: Final = "Bearish"
STRONG_BULLISH: Final = "Strong Bullish"
STRONG_BEARISH: Final = "Strong Bearish"
OVERBOUGHT_BULLISH: Final = "Overbought Bullish"
OVERSOLD_BEARISH: Final = "Oversold Bearish"
STRONG_TREND: Final = "Strong Trend"
WEAK_TREND: Final = "Weak Trend"
INCREASING: Final = "Increasing"
DECREASING: Final = "Decreasing"
NO_CROSSOVER: Final = ""

# --------------------------------------------------------------------------- #
# Signal dictionary keys (``generate_signal`` output)
# --------------------------------------------------------------------------- #
CHANGE_PCT: Final = "Change%"
RSI_VALUE: Final = "RSI_Value"
RSI_ABOVE_THRESHOLD: Final = "RSI>=60"
MACD_VALUE: Final = "MACD_Value"
SIGNAL_VALUE: Final = "Signal_Value"
MACD_CROSSOVER: Final = "MACD_Crossover"
VOLUME_SPIKE: Final = "Volume_Spike"
EMA_CROSSOVER: Final = "EMA_Crossover"
PIVOT_POINT: Final = "Pivot_point"
RESISTANCE_1: Final = "Resistance_1"
RESISTANCE_2: Final = "Resistance_2"
RESISTANCE_3: Final = "Resistance_3"
SUPPORT_1: Final = "Support_1"
SUPPORT_2: Final = "Support_2"
SUPPORT_3: Final = "Support_3"

# Column order of the multi-ticker summary returned by ``main``.
SUMMARY_COLUMNS: Final = (
    DATE, TICKER, CLOSE, CHANGE_PCT, VOLUME, VMA20, Z_SCORE, VOLUME_SPIKE,
    EMA5, EMA9, EMA26, SMA50, SMA200, EMA_CROSSOVER,
    PIVOT_POINT, RESISTANCE_1, RESISTANCE_2, RESISTANCE_3, SUPPORT_1, SUPPORT_2, SUPPORT_3,
    RSI_VALUE, RSI_ABOVE_THRESHOLD, MACD_VALUE, SIGNAL_VALUE, MACD_CROSSOVER,
    BB_DIRECTION, STOCH_DIRECTION, ATR_DIRECTION, ADX_DIRECTION, PATTERN, CODE,
)  # fmt: skip

# Columns kept from the pattern frame when merging with signals.
PATTERN_MERGE_COLUMNS: Final = (DATE, PATTERN, CODE, TICKER)
MERGE_KEYS: Final = (DATE, TICKER)

# --------------------------------------------------------------------------- #
# Candlestick patterns: (output label, TA-Lib function name)
# --------------------------------------------------------------------------- #
# ORDER MATTERS. Patterns are applied in this order and a later match on the
# same bar overwrites an earlier one. The original dict literal listed six
# labels twice (ladder_bottom, on_neck, piercing, rickshaw_man,
# rise_fall_3_methods, separating_lines); a dict keeps a duplicated key at its
# *first* position, so dropping the repeats leaves evaluation order unchanged.
CANDLESTICK_PATTERNS: Final[tuple[tuple[str, str], ...]] = (
    ("3_inside", "CDL3INSIDE"),
    ("3_line_strike", "CDL3LINESTRIKE"),
    ("3_stars_in_south", "CDL3STARSINSOUTH"),
    ("3_white_soldiers", "CDL3WHITESOLDIERS"),
    ("abandoned_baby", "CDLABANDONEDBABY"),
    ("advance_block", "CDLADVANCEBLOCK"),
    ("belthold", "CDLBELTHOLD"),
    ("breakaway", "CDLBREAKAWAY"),
    ("closing_marubozu", "CDLCLOSINGMARUBOZU"),
    ("conceal_baby_wall", "CDLCONCEALBABYSWALL"),
    ("counter_attack", "CDLCOUNTERATTACK"),
    ("doji", "CDLDOJI"),
    ("doji_star", "CDLDOJISTAR"),
    ("dragonfly_doji", "CDLDRAGONFLYDOJI"),
    ("engulfing", "CDLENGULFING"),
    ("hammer", "CDLHAMMER"),
    ("harami", "CDLHARAMI"),
    ("harami_cross", "CDLHARAMICROSS"),
    ("homing_pigeon", "CDLHOMINGPIGEON"),
    ("inverted_hammer", "CDLINVERTEDHAMMER"),
    ("kicking", "CDLKICKING"),
    ("kicking_by_length", "CDLKICKINGBYLENGTH"),
    ("ladder_bottom", "CDLLADDERBOTTOM"),
    ("matching_low", "CDLMATCHINGLOW"),
    ("morning_doji_star", "CDLMORNINGDOJISTAR"),
    ("morning_star", "CDLMORNINGSTAR"),
    ("on_neck", "CDLONNECK"),
    ("piercing", "CDLPIERCING"),
    ("rickshaw_man", "CDLRICKSHAWMAN"),
    ("rise_fall_3_methods", "CDLRISEFALL3METHODS"),
    ("separating_lines", "CDLSEPARATINGLINES"),
    ("takuri", "CDLTAKURI"),
    ("tasuki_gap", "CDLTASUKIGAP"),
    ("unique_3_river", "CDLUNIQUE3RIVER"),
    ("2_crows", "CDL2CROWS"),
    ("3_black_crows", "CDL3BLACKCROWS"),
    ("3_outside", "CDL3OUTSIDE"),
    ("dark_cloud_cover", "CDLDARKCLOUDCOVER"),
    ("evening_doji_star", "CDLEVENINGDOJISTAR"),
    ("evening_star", "CDLEVENINGSTAR"),
    ("gap_side_side_white", "CDLGAPSIDESIDEWHITE"),
    ("gravestone_doji", "CDLGRAVESTONEDOJI"),
    ("hanging_man", "CDLHANGINGMAN"),
    ("high_wave", "CDLHIGHWAVE"),
    ("hikkake", "CDLHIKKAKE"),
    ("hikkake_mod", "CDLHIKKAKEMOD"),
    ("identical_3_crows", "CDLIDENTICAL3CROWS"),
    ("in_neck", "CDLINNECK"),
    ("long_legged_doji", "CDLLONGLEGGEDDOJI"),
    ("long_line", "CDLLONGLINE"),
    ("marubozu", "CDLMARUBOZU"),
    ("mathold", "CDLMATHOLD"),
    ("shooting_star", "CDLSHOOTINGSTAR"),
    ("short_line", "CDLSHORTLINE"),
    ("spinning_top", "CDLSPINNINGTOP"),
    ("stalled_pattern", "CDLSTALLEDPATTERN"),
    ("sticks_and_sandwich", "CDLSTICKSANDWICH"),
    ("thrusting", "CDLTHRUSTING"),
    ("tristar", "CDLTRISTAR"),
    ("upside_gap_2_crows", "CDLUPSIDEGAP2CROWS"),
    ("xside_gap_3_methods", "CDLXSIDEGAP3METHODS"),
)
