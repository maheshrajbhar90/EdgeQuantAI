"""Backwards-compatible import path: ``from stock_analyzer import StockTechnicalAnalyzer``.

New code should import from :mod:`stock_technical_analyzer`.
"""

from stock_technical_analyzer import FundamentalAnalyser, StockTechnicalAnalyzer, __version__

__all__ = ["FundamentalAnalyser", "StockTechnicalAnalyzer", "__version__"]
