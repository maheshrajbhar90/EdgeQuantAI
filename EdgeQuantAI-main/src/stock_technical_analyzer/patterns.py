"""Candlestick-pattern detection using TA-Lib."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeAlias

import pandas as pd

from stock_technical_analyzer import constants as c
from stock_technical_analyzer._talib import talib

logger = logging.getLogger(__name__)

# String alias: ``pd.Series[...]`` is not subscriptable at runtime on pandas 2.
PatternFn: TypeAlias = (
    "Callable[[pd.Series[Any], pd.Series[Any], pd.Series[Any], pd.Series[Any]], pd.Series[Any]]"
)

#: ``(label, TA-Lib function)`` pairs, in evaluation order.
PATTERN_FUNCTIONS: tuple[tuple[str, PatternFn], ...] = tuple(
    (label, getattr(talib, fn_name)) for label, fn_name in c.CANDLESTICK_PATTERNS
)


def identify_candlestick_patterns(ohlc_df: pd.DataFrame) -> pd.DataFrame:
    """Tag each bar with the last matching TA-Lib candlestick pattern.

    Patterns are evaluated in :data:`PATTERN_FUNCTIONS` order; when several
    match the same bar, the later one wins. ``Pattern`` holds the label and
    ``Code`` the TA-Lib output (typically ``+100`` bullish / ``-100`` bearish).
    Both columns are created lazily, so they are absent if nothing matches.

    Args:
        ohlc_df: Frame with ``Open``, ``High``, ``Low`` and ``Close``. It is
            **modified in place**.

    Returns:
        The same ``ohlc_df`` object.
    """
    open_, high, low, close = (ohlc_df[col] for col in (c.OPEN, c.HIGH, c.LOW, c.CLOSE))
    for label, pattern_fn in PATTERN_FUNCTIONS:
        pattern = pattern_fn(open_, high, low, close)
        hits = pattern != 0
        if hits.any():
            ohlc_df.loc[hits, c.PATTERN] = label
            ohlc_df.loc[hits, c.CODE] = pattern[hits]
    return ohlc_df
