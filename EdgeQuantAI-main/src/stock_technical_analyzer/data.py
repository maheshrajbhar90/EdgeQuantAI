"""Market-data access via yfinance.

Two normalisation paths exist and are intentionally kept separate because the
original implementation behaves differently in each (see KNOWN_ISSUES.md):

* :func:`fetch_ohlc` — the strict single-ticker path behind
  ``StockTechnicalAnalyzer.fetch_ohlc``.
* :func:`prepare_downloaded_ohlc` — the tolerant path used by the multi-ticker
  pipeline, which validates columns and logs why a ticker is skipped.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import yfinance as yf

from stock_technical_analyzer import constants as c

logger = logging.getLogger(__name__)


def to_yahoo_symbol(ticker: str, exchange_suffix: str) -> str:
    """Return the Yahoo Finance symbol for ``ticker``.

    ``exchange_suffix`` is appended unless the ticker already ends with a known
    exchange suffix (``.NS``, ``.BO``) or with ``exchange_suffix`` itself,
    compared case-insensitively. An already-qualified ticker is returned as is.

    Args:
        ticker: Base or already-qualified symbol, e.g. ``"TCS"`` or ``"TCS.NS"``.
        exchange_suffix: Suffix to append, e.g. ``".NS"``; may be empty.

    Returns:
        The symbol to request from yfinance.

    Example:
        >>> to_yahoo_symbol("TCS", ".NS"), to_yahoo_symbol("tcs.ns", ".NS")
        ('TCS.NS', 'tcs.ns')
        >>> to_yahoo_symbol("TCS.BO", ".NS")
        'TCS.BO'
    """
    suffixes = {s.upper() for s in c.KNOWN_EXCHANGE_SUFFIXES}
    if exchange_suffix:
        suffixes.add(exchange_suffix.upper())
    if ticker.upper().endswith(tuple(suffixes)):
        return ticker
    return ticker + exchange_suffix


def download(symbol: str, period: str, interval: str) -> pd.DataFrame:
    """Download adjusted OHLCV bars for one fully-qualified Yahoo symbol.

    Args:
        symbol: Yahoo Finance symbol including any exchange suffix, e.g. ``"TCS.NS"``.
        period: yfinance period string, e.g. ``"5y"``.
        interval: yfinance interval string, e.g. ``"1d"``.

    Returns:
        The raw frame returned by :func:`yfinance.download` (``auto_adjust=True``,
        no progress bar). It is empty when the symbol is unknown.
    """
    frame: pd.DataFrame = yf.download(
        symbol,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
    )
    return frame


def _to_local_naive(dates: pd.Series[Any], *, coerce: bool) -> pd.Series[Any]:
    """Interpret ``dates`` as UTC, convert to IST and drop the timezone."""
    if coerce:
        parsed = pd.to_datetime(dates, errors="coerce", utc=True)
    else:
        parsed = pd.to_datetime(dates, utc=True)
    return parsed.dt.tz_convert(c.LOCAL_TIMEZONE).dt.tz_localize(None)


def fetch_ohlc(
    ticker: str, *, exchange_suffix: str, period: str, interval: str
) -> pd.DataFrame | None:
    """Fetch OHLCV bars for ``ticker`` and return them indexed by local date.

    Args:
        ticker: Base symbol; ``exchange_suffix`` is appended unless the ticker
            is already qualified (see :func:`to_yahoo_symbol`).
        exchange_suffix: Suffix such as ``".NS"``.
        period: yfinance period string.
        interval: yfinance interval string.

    Returns:
        A frame indexed by naive Asia/Kolkata ``Date`` with the price columns
        and a ``Ticker`` column, or ``None`` if yfinance returned no rows.

    Raises:
        IndexError: If yfinance returns single-level columns (the second column
            level is dropped unconditionally).
    """
    symbol = to_yahoo_symbol(ticker, exchange_suffix)
    df = download(symbol, period, interval)
    if df.empty:
        logger.warning("No data returned for %s", symbol)
        return None

    df = df.droplevel(level=1, axis=1)
    df = df.reset_index()
    if c.DATETIME in df.columns:
        df = df.rename(columns={c.DATETIME: c.DATE})
    df[c.DATE] = _to_local_naive(df[c.DATE], coerce=False)
    df = df.set_index(c.DATE)
    df[c.TICKER] = ticker
    return df


def _find_date_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if col.lower() in c.DATE_COLUMN_CANDIDATES:
            return str(col)
    return None


def prepare_downloaded_ohlc(raw: pd.DataFrame | None, ticker: str) -> pd.DataFrame | None:
    """Normalise a raw yfinance frame for the multi-ticker pipeline.

    Flattens column levels, locates the date column, converts it to naive
    Asia/Kolkata time, validates the OHLCV columns and adds ``Ticker``.

    Args:
        raw: Frame returned by :func:`download` (may be ``None`` or empty).
        ticker: Base symbol to store in the ``Ticker`` column.

    Returns:
        The normalised frame, or ``None`` (with the reason logged) when the
        data is unusable.
    """
    if raw is None or raw.empty:
        logger.warning("[SKIP] No data for %s", ticker)
        return None

    df = raw
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()

    date_col = _find_date_column(df)
    if date_col is None:
        logger.error("[ERROR] Date column missing for %s", ticker)
        return None
    df = df.rename(columns={date_col: c.DATE})

    df[c.DATE] = _to_local_naive(df[c.DATE], coerce=True)
    if df[c.DATE].isna().all():
        logger.error("[ERROR] Date conversion failed for %s", ticker)
        return None
    df = df.set_index(c.DATE)

    if not all(col in df.columns for col in c.REQUIRED_OHLCV_COLUMNS):
        logger.error("[ERROR] Missing OHLC columns for %s", ticker)
        return None

    df[c.TICKER] = ticker
    return df
