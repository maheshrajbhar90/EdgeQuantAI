"""Public ``StockTechnicalAnalyzer`` facade.

The class is thin orchestration over :mod:`~stock_technical_analyzer.data`,
:mod:`~stock_technical_analyzer.indicators`, :mod:`~stock_technical_analyzer.patterns`,
:mod:`~stock_technical_analyzer.signals`, :mod:`~stock_technical_analyzer.levels`
and :mod:`~stock_technical_analyzer.prompts`. Internal calls go through ``self``
(e.g. ``self.add_indicators``) so subclasses can override any step, as in the
original implementation.
"""

from __future__ import annotations

import logging
import warnings
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from stock_technical_analyzer import constants as c
from stock_technical_analyzer import data, indicators, levels, patterns, prompts, signals
from stock_technical_analyzer.fundamental import FundamentalAnalyser

logger = logging.getLogger(__name__)


class StockTechnicalAnalyzer:
    """Technical-analysis engine: indicators, candlestick patterns, signals, S/R, LLM prompts.

    Args:
        period: yfinance period for downloads (e.g. ``"1y"``, ``"5y"``, ``"max"``).
        interval: yfinance bar interval (e.g. ``"1d"``, ``"1wk"``, ``"15m"``).
        exchange_suffix: Appended to every ticker, e.g. ``".NS"`` for NSE or
            ``""`` for US listings.
        fmp_api_key: Optional Financial Modeling Prep key for :attr:`fundamental`.
        openai_key: Optional OpenAI key for :attr:`fundamental`.

    Attributes:
        fundamental: A :class:`FundamentalAnalyser` (always uses the ``".NS"``
            suffix; ``exchange_suffix`` is not forwarded).

    Example:
        >>> analyzer = StockTechnicalAnalyzer(period="1y")
        >>> summary = analyzer.main(["RELIANCE", "TCS"])  # doctest: +SKIP
        >>> print(analyzer.build_prompt(summary, "RELIANCE"))  # doctest: +SKIP
    """

    def __init__(
        self,
        period: str = c.DEFAULT_PERIOD,
        interval: str = c.DEFAULT_INTERVAL,
        exchange_suffix: str = c.DEFAULT_EXCHANGE_SUFFIX,
        fmp_api_key: str | None = None,
        openai_key: str | None = None,
    ) -> None:
        self.fundamental = FundamentalAnalyser(fmp_api_key=fmp_api_key, openai_key=openai_key)
        self.period = period
        self.interval = interval
        self.exchange_suffix = exchange_suffix

    # ------------------------------------------------------------------ data
    def fetch_ohlc(self, ticker: str) -> pd.DataFrame | None:
        """Download OHLCV bars for one ticker.

        Args:
            ticker: Symbol, e.g. ``"RELIANCE"``. The exchange suffix is appended
                unless the ticker already ends with ``.NS``/``.BO`` (any case).

        Returns:
            Frame indexed by naive Asia/Kolkata ``Date`` with ``Close``, ``High``,
            ``Low``, ``Open``, ``Volume`` and ``Ticker``; ``None`` if no data.

        Raises:
            IndexError: If yfinance returns single-level columns.

        Example:
            >>> df = StockTechnicalAnalyzer().fetch_ohlc("RELIANCE")  # doctest: +SKIP
            >>> print(df.tail())  # doctest: +SKIP
        """
        return data.fetch_ohlc(
            ticker, exchange_suffix=self.exchange_suffix, period=self.period, interval=self.interval
        )

    # ------------------------------------------------------------ indicators
    def add_indicators(self, ohlc: pd.DataFrame) -> pd.DataFrame | None:
        """Return a copy of ``ohlc`` with indicator and direction columns.

        Adds ``VMA20, EMA5, EMA9, EMA26, SMA50, SMA200, RSI, MACD, Signal,
        bb_upper, bb_middle, bb_lower, Stoch_k, stoch_d, ATR, ADX, Change,
        Z_score, BB_Direction, Stoch_Direction, ATR_Direction, ADX_Direction``.

        Args:
            ohlc: OHLCV frame (e.g. from :meth:`fetch_ohlc`).

        Returns:
            The enriched copy, or ``None`` if empty or shorter than 200 rows.

        Example:
            >>> enriched = analyzer.add_indicators(df)  # doctest: +SKIP
        """
        return indicators.add_indicators(
            ohlc,
            z_score_fn=self.z_score,
            bb_direction=self.bb_direction,
            stoch_direction=self.stoch_direction,
            adx_direction=self.adx_direction,
        )

    def z_score(self, df: pd.DataFrame, window: int = c.ZSCORE_WINDOW) -> pd.DataFrame:
        """Return a copy of ``df`` with ``vol_mean``, ``vol_std`` and ``vol_zscore``.

        Args:
            df: Frame with a ``Volume`` column.
            window: Rolling window length.

        Returns:
            New frame with the three columns appended.

        Example:
            >>> analyzer.z_score(df, window=10)["vol_zscore"].tail()  # doctest: +SKIP
        """
        return indicators.z_score(df, window=window)

    def bb_direction(self, row: pd.Series[Any]) -> str:
        """Classify close vs. Bollinger Bands (see :func:`signals.bb_direction`).

        Args:
            row: Row with ``Close``, ``bb_upper``, ``bb_middle``, ``bb_lower``.

        Returns:
            ``Neutral``, ``Strong Bullish``, ``Bullish``, ``Bearish`` or ``Strong Bearish``.

        Example:
            >>> import pandas as pd
            >>> StockTechnicalAnalyzer().bb_direction(
            ...     pd.Series({"Close": 10, "bb_upper": 9, "bb_middle": 5, "bb_lower": 1})
            ... )
            'Strong Bullish'
        """
        return signals.bb_direction(row)

    def stoch_direction(self, row: pd.Series[Any]) -> str:
        """Classify the Stochastic oscillator (see :func:`signals.stoch_direction`).

        Args:
            row: Row with ``Stoch_k`` and ``stoch_d``.

        Returns:
            ``Neutral``, ``Overbought Bullish``, ``Bullish``, ``Bearish`` or ``Oversold Bearish``.

        Example:
            >>> import pandas as pd
            >>> StockTechnicalAnalyzer().stoch_direction(pd.Series({"Stoch_k": 90, "stoch_d": 85}))
            'Overbought Bullish'
        """
        return signals.stoch_direction(row)

    def adx_direction(self, val: Any) -> str:
        """Classify ADX trend strength (> 25 is strong).

        Args:
            val: ADX value; NaN/None gives ``Neutral``.

        Returns:
            ``Neutral``, ``Strong Trend`` or ``Weak Trend``.

        Example:
            >>> StockTechnicalAnalyzer().adx_direction(30.0)
            'Strong Trend'
        """
        return signals.adx_direction(val)

    # --------------------------------------------------------------- signals
    def support_resistance_level(self, ohlc_day: pd.DataFrame) -> tuple[float, ...]:
        """Classic pivot point and S/R levels from the last row.

        Args:
            ohlc_day: Frame with ``High``, ``Low``, ``Close``.

        Returns:
            ``(pivot, r1, r2, r3, s1, s2, s3)`` rounded to 2 decimals.

        Raises:
            IndexError: If ``ohlc_day`` is empty.

        Example:
            >>> import pandas as pd
            >>> StockTechnicalAnalyzer().support_resistance_level(
            ...     pd.DataFrame({"High": [110.0], "Low": [90.0], "Close": [100.0]})
            ... )
            (100.0, 110.0, 120.0, 130.0, 90.0, 80.0, 70.0)
        """
        return levels.support_resistance_level(ohlc_day)

    def generate_signal(self, data: pd.DataFrame | None) -> dict[str, Any] | None:
        """Summarise the last bar when a volume, RSI, EMA or MACD condition fires.

        Args:
            data: Output of :meth:`add_indicators`.

        Returns:
            Ordered metrics dict (see README for keys), or ``None`` when
            ``data`` is ``None``, has < 2 rows, or no condition is met.

        Example:
            >>> signal = analyzer.generate_signal(enriched)  # doctest: +SKIP
            >>> signal["EMA_Crossover"]  # doctest: +SKIP
            'Bullish'
        """
        return signals.generate_signal(data, support_resistance=self.support_resistance_level)

    # -------------------------------------------------------------- patterns
    def identify_candlestick_patterns(self, ohlc_df: pd.DataFrame) -> pd.DataFrame:
        """Add ``Pattern`` / ``Code`` columns for TA-Lib candlestick matches.

        Args:
            ohlc_df: Frame with ``Open``, ``High``, ``Low``, ``Close``.
                **Modified in place.**

        Returns:
            The same frame object.

        Example:
            >>> tagged = analyzer.identify_candlestick_patterns(enriched.copy())  # doctest: +SKIP
        """
        return patterns.identify_candlestick_patterns(ohlc_df)

    # -------------------------------------------------------------- pipeline
    def _analyze_ticker(
        self, tick: str, period: str, interval: str
    ) -> tuple[pd.DataFrame, dict[str, Any] | None] | None:
        """Run download -> indicators -> signal -> patterns for one ticker.

        Returns ``(latest_pattern_row, signal_or_None)``, or ``None`` if the
        ticker is skipped (reason logged). Exceptions propagate to the caller.
        """
        raw = data.download(data.to_yahoo_symbol(tick, self.exchange_suffix), period, interval)
        ohlc_df = data.prepare_downloaded_ohlc(raw, tick)
        if ohlc_df is None:
            return None

        with_indicators = self.add_indicators(ohlc_df)
        if with_indicators is None or with_indicators.empty:
            logger.warning("[SKIP] Indicators failed for %s", tick)
            return None

        signal = self.generate_signal(with_indicators)
        tagged = self.identify_candlestick_patterns(with_indicators.copy())
        if tagged is None or tagged.empty:
            logger.warning("[SKIP] Pattern detection failed for %s", tick)
            return None

        latest = tagged.iloc[-1:].reset_index()
        if latest.empty:
            return None
        return latest, signal

    @staticmethod
    def _merge_patterns_and_signals(
        pattern_rows: list[pd.DataFrame], signal_rows: list[dict[str, Any]]
    ) -> pd.DataFrame | None:
        if not pattern_rows:
            logger.warning("[FINAL] No valid result data.")
            return None

        final_result_df = pd.concat(pattern_rows, ignore_index=True)
        if not signal_rows:
            logger.info("[INFO] No signal data found. Returning pattern data only.")
            return final_result_df

        final_pattern_df = pd.DataFrame(signal_rows)
        if c.DATE not in final_pattern_df.columns:
            logger.error("[ERROR] Signal data missing Date column.")
            return final_result_df

        final_pattern_df[c.DATE] = pd.to_datetime(final_pattern_df[c.DATE])
        final_result_df[c.DATE] = pd.to_datetime(final_result_df[c.DATE])
        return pd.merge(
            final_pattern_df,
            final_result_df[list(c.PATTERN_MERGE_COLUMNS)],
            on=list(c.MERGE_KEYS),
            how="left",
        )

    def get_latest_candlestick_patterns(
        self,
        symbols: Sequence[str],
        periods: str | None = None,
        interval: str | None = None,
    ) -> pd.DataFrame | None:
        """Analyse several tickers and merge each one's signal with its latest pattern.

        Per-ticker failures (no data, too short, missing columns, any exception)
        are logged and the ticker is skipped.

        Args:
            symbols: Base symbols.
            periods: Override for :attr:`period` (falsy -> use the default).
            interval: Override for :attr:`interval` (falsy -> use the default).

        Returns:
            One row per ticker that produced a signal, with ``Pattern``/``Code``
            from its latest bar; if no ticker produced a signal, the latest
            pattern rows themselves; ``None`` if every ticker was skipped.

        Example:
            >>> analyzer.get_latest_candlestick_patterns(["INFY", "TCS"])  # doctest: +SKIP
        """
        period = periods or self.period
        intervals = interval or self.interval
        pattern_rows: list[pd.DataFrame] = []
        signal_rows: list[dict[str, Any]] = []

        for tick in symbols:
            # Broad on purpose: this is the per-ticker isolation boundary and
            # yfinance / TA-Lib / pandas raise open-ended exception types.
            try:
                result = self._analyze_ticker(tick, period, intervals)
            except Exception as exc:
                logger.error("[ERROR] %s: %s", tick, exc, exc_info=True)
                continue
            if result is None:
                continue
            latest, signal = result
            pattern_rows.append(latest)
            if signal:
                signal_rows.append(signal)

        return self._merge_patterns_and_signals(pattern_rows, signal_rows)

    def main(self, ticker: Sequence[str]) -> pd.DataFrame | None:
        """Full multi-ticker pipeline returning the tidy summary table.

        Wraps :meth:`get_latest_candlestick_patterns`, reorders/limits columns
        to the summary layout (missing columns become NaN) and rounds numbers
        to 2 decimals.

        Args:
            ticker: Base symbols, e.g. ``["RELIANCE", "TCS"]``.

        Returns:
            The summary frame, or ``None`` if no ticker could be processed.

        Example:
            >>> summary = StockTechnicalAnalyzer().main(["RELIANCE"])  # doctest: +SKIP
            >>> print(summary.T)  # doctest: +SKIP
        """
        final_result = self.get_latest_candlestick_patterns(ticker)
        if final_result is None:
            logger.warning(
                "No valid data to process after fetching candlestick patterns. "
                "Check the log for per-ticker errors."
            )
            return None
        final_result = final_result.reindex(columns=list(c.SUMMARY_COLUMNS))
        # DataFrame.round warns that it can't round the datetime ``Date`` column.
        # Hide exactly that warning, for this call only (KNOWN_ISSUES C1; the
        # underlying B4 is still open).
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message=r"obj\.round has no effect with datetime", category=UserWarning
            )
            return final_result.round(c.PRICE_DECIMALS)

    # --------------------------------------------------------------- prompts
    def get_tech_data_for_ticker(self, df: pd.DataFrame, ticker: str) -> dict[Any, Any]:
        """Return the last row for ``ticker`` in ``df`` as a dict.

        Args:
            df: Summary frame from :meth:`main`.
            ticker: Ticker to select.

        Returns:
            ``{column: value}`` in column order.

        Raises:
            ValueError: If ``ticker`` is not present.

        Example:
            >>> analyzer.get_tech_data_for_ticker(summary, "RELIANCE")[
            ...     "RSI_Value"
            ... ]  # doctest: +SKIP
        """
        return prompts.get_tech_data_for_ticker(df, ticker)

    def generate_technical_prompt(
        self, ticker: Any, tech_data: Mapping[Any, Any], mode: str = "simple"
    ) -> str:
        """Build an LLM technical-analysis prompt.

        Args:
            ticker: Ticker shown in the prompt.
            tech_data: Metrics mapping; ``None`` values are omitted.
            mode: ``"scoring"`` for the scoring framework, anything else for
                the narrative prompt.

        Returns:
            The prompt text.

        Example:
            >>> p = StockTechnicalAnalyzer().generate_technical_prompt("TCS", {"RSI_Value": 61.2})
            >>> p.splitlines()[0].startswith("You are an expert Technical Analyst")
            True
        """
        return prompts.generate_technical_prompt(ticker, tech_data, mode)

    def build_prompt(self, df: pd.DataFrame, ticker: str) -> str:
        """Select ``ticker``'s latest row from ``df`` and build the default prompt.

        Args:
            df: Summary frame from :meth:`main`.
            ticker: Ticker to select.

        Returns:
            The prompt text (``"simple"`` mode).

        Raises:
            ValueError: If ``ticker`` is not present.

        Example:
            >>> print(analyzer.build_prompt(summary, "RELIANCE"))  # doctest: +SKIP
        """
        tech_data = self.get_tech_data_for_ticker(df, ticker)
        return self.generate_technical_prompt(ticker, tech_data)
