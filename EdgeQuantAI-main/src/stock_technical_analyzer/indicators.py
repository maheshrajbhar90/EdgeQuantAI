"""Technical-indicator calculations (TA-Lib + pandas).

Column insertion order is part of the public output and is preserved exactly.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeAlias

import pandas as pd

from stock_technical_analyzer import constants as c
from stock_technical_analyzer import signals
from stock_technical_analyzer._talib import talib

logger = logging.getLogger(__name__)

# String alias: ``pd.Series[...]`` is not subscriptable at runtime on pandas 2.
RowClassifier: TypeAlias = "Callable[[pd.Series[Any]], str]"
ValueClassifier: TypeAlias = Callable[[Any], str]
ZScoreFn: TypeAlias = Callable[[pd.DataFrame], pd.DataFrame]


def z_score(df: pd.DataFrame, window: int = c.ZSCORE_WINDOW) -> pd.DataFrame:
    """Return a copy of ``df`` with rolling volume mean, std and Z-score columns.

    Args:
        df: Frame containing a ``Volume`` column.
        window: Rolling window length for the mean and (sample) standard deviation.

    Returns:
        A new frame with ``vol_mean``, ``vol_std`` and ``vol_zscore`` appended.
    """
    out = df.copy()
    out[c.VOL_MEAN] = out[c.VOLUME].rolling(window).mean()
    out[c.VOL_STD] = out[c.VOLUME].rolling(window).std()
    out[c.VOL_ZSCORE] = (out[c.VOLUME] - out[c.VOL_MEAN]) / out[c.VOL_STD]
    return out


def _add_moving_averages(data: pd.DataFrame) -> None:
    close, volume = data[c.CLOSE], data[c.VOLUME]
    data[c.VMA20] = talib.SMA(volume, c.VOLUME_MA_PERIOD)
    data[c.EMA5] = talib.EMA(close, c.EMA_FAST_PERIOD)
    data[c.EMA9] = talib.EMA(close, c.EMA_SHORT_PERIOD)
    data[c.EMA26] = talib.EMA(close, c.EMA_LONG_PERIOD)
    data[c.SMA50] = talib.SMA(close, c.SMA_MEDIUM_PERIOD)
    data[c.SMA200] = talib.SMA(close, c.SMA_LONG_PERIOD)


def _add_oscillators(data: pd.DataFrame) -> None:
    close, high, low = data[c.CLOSE], data[c.HIGH], data[c.LOW]
    data[c.RSI] = talib.RSI(close, c.RSI_PERIOD)
    data[c.MACD], data[c.MACD_SIGNAL_LINE], _ = talib.MACD(
        close, c.MACD_FAST_PERIOD, c.MACD_SLOW_PERIOD, c.MACD_SIGNAL_PERIOD
    )
    # BBANDS / STOCH use TA-Lib defaults for the remaining parameters
    # (nbdev=2, matype=SMA; fastk=5, slowk=3, slowd=3).
    data[c.BB_UPPER], data[c.BB_MIDDLE], data[c.BB_LOWER] = talib.BBANDS(close, c.BBANDS_PERIOD)
    data[c.STOCH_K], data[c.STOCH_D] = talib.STOCH(high, low, close)


def _add_volatility_and_change(data: pd.DataFrame) -> None:
    close, high, low = data[c.CLOSE], data[c.HIGH], data[c.LOW]
    data[c.ATR] = talib.ATR(high, low, close, c.ATR_PERIOD)
    data[c.ADX] = talib.ADX(high, low, close, c.ADX_PERIOD)
    data[c.CHANGE] = close.pct_change()


def _add_directions(
    data: pd.DataFrame,
    bb_direction: RowClassifier,
    stoch_direction: RowClassifier,
    adx_direction: ValueClassifier,
) -> None:
    data[c.BB_DIRECTION] = data.apply(bb_direction, axis=1)
    data[c.STOCH_DIRECTION] = data.apply(stoch_direction, axis=1)
    data[c.ATR_DIRECTION] = data[c.ATR].diff().apply(signals.atr_direction)
    data[c.ADX_DIRECTION] = data[c.ADX].apply(adx_direction)


def add_indicators(
    ohlc: pd.DataFrame,
    *,
    z_score_fn: ZScoreFn = z_score,
    bb_direction: RowClassifier = signals.bb_direction,
    stoch_direction: RowClassifier = signals.stoch_direction,
    adx_direction: ValueClassifier = signals.adx_direction,
) -> pd.DataFrame | None:
    """Return a copy of ``ohlc`` with all indicator and direction columns added.

    The classifier callables are injectable so that
    :class:`~stock_technical_analyzer.StockTechnicalAnalyzer` can route them
    through its own (overridable) methods, exactly as the original did.

    Args:
        ohlc: OHLCV frame with ``Open``, ``High``, ``Low``, ``Close``, ``Volume``.
        z_score_fn: Called as ``z_score_fn(data)``; its ``vol_zscore`` column
            becomes ``Z_score``.
        bb_direction: Row-wise Bollinger Band classifier.
        stoch_direction: Row-wise Stochastic classifier.
        adx_direction: Value-wise ADX classifier.

    Returns:
        The enriched frame, or ``None`` if ``ohlc`` is empty or has fewer than
        200 rows (needed for ``SMA200``). The input is never modified.
    """
    data = ohlc.copy()
    if data.empty:
        logger.debug("add_indicators: empty frame")
        return None
    if len(data) < c.MIN_ROWS_FOR_INDICATORS:
        logger.debug("add_indicators: %d rows < %d required", len(data), c.MIN_ROWS_FOR_INDICATORS)
        return None

    _add_moving_averages(data)
    _add_oscillators(data)
    _add_volatility_and_change(data)
    data[c.Z_SCORE] = z_score_fn(data)[c.VOL_ZSCORE]
    _add_directions(data, bb_direction, stoch_direction, adx_direction)
    return data
