"""Technical analysis for equities: indicators, candlestick patterns, signals and LLM prompts.

Example:
    >>> from stock_technical_analyzer import StockTechnicalAnalyzer
    >>> analyzer = StockTechnicalAnalyzer(period="1y")
    >>> summary = analyzer.main(["RELIANCE"])  # doctest: +SKIP
"""

from __future__ import annotations

import warnings

# Preserved from the original implementation: importing the library silences
# *all* Python warnings process-wide. This is a known issue (KNOWN_ISSUES.md)
# kept only to honour the zero-behaviour-change refactor.
warnings.filterwarnings("ignore")

from stock_technical_analyzer.analyzer import StockTechnicalAnalyzer  # noqa: E402
from stock_technical_analyzer.fundamental import FundamentalAnalyser  # noqa: E402

__version__ = "0.1.0"

__all__ = ["FundamentalAnalyser", "StockTechnicalAnalyzer", "__version__"]
