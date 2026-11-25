"""Signal generation and indicator-direction classifiers."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeAlias

import pandas as pd

from stock_technical_analyzer import constants as c
from stock_technical_analyzer import levels

logger = logging.getLogger(__name__)

SupportResistanceFn: TypeAlias = Callable[[pd.DataFrame], tuple[float, ...]]


# --------------------------------------------------------------------------- #
# Direction classifiers
# --------------------------------------------------------------------------- #
def bb_direction(row: pd.Series[Any]) -> str:
    """Classify the close relative to the Bollinger Bands.

    Args:
        row: Row with ``Close``, ``bb_upper``, ``bb_middle`` and ``bb_lower``.

    Returns:
        ``"Neutral"`` if any band is NaN; otherwise ``"Strong Bullish"``
        (close >= upper), ``"Bullish"`` (close > middle), ``"Strong Bearish"``
        (close <= lower) or ``"Bearish"``. A close equal to the middle band is
        bearish.
    """
    if pd.isna(row[c.BB_UPPER]) or pd.isna(row[c.BB_MIDDLE]) or pd.isna(row[c.BB_LOWER]):
        return c.NEUTRAL
    if row[c.CLOSE] > row[c.BB_MIDDLE]:
        return c.STRONG_BULLISH if row[c.CLOSE] >= row[c.BB_UPPER] else c.BULLISH
    return c.STRONG_BEARISH if row[c.CLOSE] <= row[c.BB_LOWER] else c.BEARISH


def stoch_direction(row: pd.Series[Any]) -> str:
    """Classify the Stochastic oscillator.

    Args:
        row: Row with ``Stoch_k`` and ``stoch_d``.

    Returns:
        ``"Neutral"`` if either value is NaN; if %K > %D, ``"Overbought Bullish"``
        when %K > 80 else ``"Bullish"``; otherwise ``"Oversold Bearish"`` when
        %K < 20 else ``"Bearish"``.
    """
    if pd.isna(row[c.STOCH_K]) or pd.isna(row[c.STOCH_D]):
        return c.NEUTRAL
    if row[c.STOCH_K] > row[c.STOCH_D]:
        return c.OVERBOUGHT_BULLISH if row[c.STOCH_K] > c.STOCH_OVERBOUGHT else c.BULLISH
    return c.OVERSOLD_BEARISH if row[c.STOCH_K] < c.STOCH_OVERSOLD else c.BEARISH


def adx_direction(val: Any) -> str:
    """Classify ADX trend strength.

    Args:
        val: ADX value (may be NaN/None).

    Returns:
        ``"Neutral"`` for missing values, ``"Strong Trend"`` when ADX > 25,
        otherwise ``"Weak Trend"``.
    """
    if pd.isna(val):
        return c.NEUTRAL
    return c.STRONG_TREND if val > c.ADX_STRONG_TREND else c.WEAK_TREND


def atr_direction(delta: Any) -> str:
    """Classify a one-bar ATR change; NaN (first bar) counts as decreasing."""
    return c.INCREASING if delta > 0 else c.DECREASING


# --------------------------------------------------------------------------- #
# Signal generation
# --------------------------------------------------------------------------- #
def _crossovers(
    prev: pd.Series[Any], last: pd.Series[Any], fast: str, slow: str
) -> tuple[Any, Any]:
    """Return ``(bullish, bearish)`` crossover flags of ``fast`` over ``slow``."""
    bullish = prev[fast] < prev[slow] and last[fast] > last[slow]
    bearish = prev[fast] > prev[slow] and last[fast] < last[slow]
    return bullish, bearish


def _cross_label(bullish: Any, bearish: Any) -> str:
    return c.BULLISH if bullish else c.BEARISH if bearish else c.NO_CROSSOVER


def generate_signal(
    data: pd.DataFrame | None,
    *,
    support_resistance: SupportResistanceFn = levels.support_resistance_level,
) -> dict[str, Any] | None:
    """Summarise the latest bar if any signal condition is met.

    A signal is emitted when at least one of these holds on the last bar:
    volume > VMA20, RSI >= 60, an EMA9/EMA26 crossover, or a MACD/signal-line
    crossover (comparing the last two bars).

    Args:
        data: Output of :func:`~stock_technical_analyzer.indicators.add_indicators`.
        support_resistance: Called with the last bar (as a one-row frame) to
            compute pivot levels.

    Returns:
        An ordered dict of the latest metrics, or ``None`` when ``data`` is
        ``None``, has fewer than two rows, or no condition is met.
    """
    if data is None or len(data) < 2:
        return None

    last = data.iloc[-1]
    prev = data.iloc[-2]
    pivot, r1, r2, r3, s1, s2, s3 = support_resistance(last.to_frame().T)

    # Evaluation order mirrors the original so a missing column raises the same KeyError.
    cond_volume = last[c.VOLUME] > last[c.VMA20]
    ema_bullish, ema_bearish = _crossovers(prev, last, c.EMA9, c.EMA26)
    cond_rsi = last[c.RSI] >= c.RSI_SIGNAL_THRESHOLD
    macd_bullish, macd_bearish = _crossovers(prev, last, c.MACD, c.MACD_SIGNAL_LINE)

    if not (cond_volume or ema_bullish or ema_bearish or cond_rsi or macd_bullish or macd_bearish):
        return None

    return {
        c.DATE: last.name,
        c.TICKER: last[c.TICKER],
        c.CLOSE: last[c.CLOSE],
        c.CHANGE_PCT: last[c.CHANGE],
        c.VOLUME: last[c.VOLUME],
        c.VMA20: last[c.VMA20],
        c.RSI_VALUE: last[c.RSI],
        c.RSI_ABOVE_THRESHOLD: cond_rsi,
        c.MACD_VALUE: last[c.MACD],
        c.SIGNAL_VALUE: last[c.MACD_SIGNAL_LINE],
        c.MACD_CROSSOVER: _cross_label(macd_bullish, macd_bearish),
        c.VOLUME_SPIKE: cond_volume,
        c.Z_SCORE: last[c.Z_SCORE],
        c.BB_DIRECTION: last[c.BB_DIRECTION],
        c.STOCH_DIRECTION: last[c.STOCH_DIRECTION],
        c.ATR_DIRECTION: last[c.ATR_DIRECTION],
        c.ADX_DIRECTION: last[c.ADX_DIRECTION],
        c.EMA5: last[c.EMA5],
        c.EMA9: last[c.EMA9],
        c.EMA26: last[c.EMA26],
        c.SMA50: last[c.SMA50],
        c.SMA200: last[c.SMA200],
        c.EMA_CROSSOVER: _cross_label(ema_bullish, ema_bearish),
        c.PIVOT_POINT: pivot,
        c.RESISTANCE_1: r1,
        c.RESISTANCE_2: r2,
        c.RESISTANCE_3: r3,
        c.SUPPORT_1: s1,
        c.SUPPORT_2: s2,
        c.SUPPORT_3: s3,
    }
