"""Classic floor-trader pivot points and support/resistance levels."""

from __future__ import annotations

import pandas as pd

from stock_technical_analyzer import constants as c


def classic_pivots(high: float, low: float, close: float) -> tuple[float, ...]:
    """Compute unrounded classic pivot levels.

    Args:
        high: Bar high.
        low: Bar low.
        close: Bar close.

    Returns:
        ``(pivot, r1, r2, r3, s1, s2, s3)``.
    """
    pivot = (high + low + close) / 3
    r1 = (2 * pivot) - low
    r2 = pivot + (high - low)
    r3 = high + 2 * (pivot - low)
    s1 = (2 * pivot) - high
    s2 = pivot - (high - low)
    s3 = low - 2 * (high - pivot)
    return pivot, r1, r2, r3, s1, s2, s3


def support_resistance_level(ohlc_day: pd.DataFrame) -> tuple[float, ...]:
    """Return pivot and S/R levels from the *last* row of ``ohlc_day``.

    Args:
        ohlc_day: Frame with ``High``, ``Low`` and ``Close`` columns.

    Returns:
        A 7-tuple of Python floats rounded to 2 decimals:
        ``(pivot, r1, r2, r3, s1, s2, s3)``.

    Raises:
        IndexError: If ``ohlc_day`` is empty.

    Example:
        >>> import pandas as pd
        >>> support_resistance_level(
        ...     pd.DataFrame({"High": [110.0], "Low": [90.0], "Close": [100.0]})
        ... )
        (100.0, 110.0, 120.0, 130.0, 90.0, 80.0, 70.0)
    """
    high = float(ohlc_day[c.HIGH].iloc[-1])
    low = float(ohlc_day[c.LOW].iloc[-1])
    close = float(ohlc_day[c.CLOSE].iloc[-1])
    return tuple(round(level, c.PRICE_DECIMALS) for level in classic_pivots(high, low, close))
