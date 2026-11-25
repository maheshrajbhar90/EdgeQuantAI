"""Backwards-compatible module path ``EdgeQuantAI.EdgeQuantAI``."""

from stock_technical_analyzer.analyzer import StockTechnicalAnalyzer
from stock_technical_analyzer.fundamental import FundamentalAnalyser

__all__ = ["FundamentalAnalyser", "StockTechnicalAnalyzer"]
