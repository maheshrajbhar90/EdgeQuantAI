"""Backwards-compatible import path for the original ``EdgeQuantAI`` package.

``from EdgeQuantAI import StockTechnicalAnalyzer, FundamentalAnalyser`` keeps
working. New code should import from :mod:`stock_technical_analyzer`.
"""

from stock_technical_analyzer import FundamentalAnalyser, StockTechnicalAnalyzer, __version__

__all__ = ["FundamentalAnalyser", "StockTechnicalAnalyzer", "__version__"]
