"""Technical analysis for equities: indicators, candlestick patterns, signals and LLM prompts.

Example:
    >>> from stock_technical_analyzer import StockTechnicalAnalyzer
    >>> analyzer = StockTechnicalAnalyzer(period="1y")
    >>> summary = analyzer.main(["RELIANCE"])  # doctest: +SKIP
"""

from __future__ import annotations

from stock_technical_analyzer.analyzer import StockTechnicalAnalyzer
from stock_technical_analyzer.fundamental import FundamentalAnalyser

__version__ = "0.1.0"

__all__ = ["FundamentalAnalyser", "StockTechnicalAnalyzer", "__version__"]
