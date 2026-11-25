"""Quickstart: analyse a few NSE stocks and print an LLM-ready prompt.

Run from the project root after ``pip install -e .``::

    python examples/quickstart.py RELIANCE TCS INFY

Requires network access (data comes from Yahoo Finance via yfinance).
"""

from __future__ import annotations

import logging
import sys

import pandas as pd

from stock_technical_analyzer import StockTechnicalAnalyzer


def main(tickers: list[str]) -> int:
    """Run the pipeline for ``tickers`` and print the results."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    analyzer = StockTechnicalAnalyzer(period="1y", interval="1d", exchange_suffix=".NS")

    # 1. Single ticker, step by step -------------------------------------------
    ohlc = analyzer.fetch_ohlc(tickers[0])
    if ohlc is None:
        print(f"No data for {tickers[0]}")
        return 1
    print(f"Fetched {len(ohlc)} bars for {tickers[0]}:")
    print(ohlc.tail(3), end="\n\n")

    enriched = analyzer.add_indicators(ohlc)
    if enriched is None:
        print("Not enough history for indicators (need >= 200 bars).")
    else:
        signal = analyzer.generate_signal(enriched)
        print("Latest signal:" if signal else "No signal conditions met on the last bar.")
        for key, value in (signal or {}).items():
            print(f"  {key}: {value}")
        print()

    # 2. Whole pipeline for several tickers ------------------------------------
    summary = analyzer.main(tickers)
    if summary is None or summary.empty:
        print("No technical data available.")
        return 1
    with pd.option_context("display.width", 120, "display.max_columns", 12):
        print(summary[["Date", "Ticker", "Close", "RSI_Value", "EMA_Crossover", "Pattern"]])
    print()

    # 3. LLM prompt for the first ticker that produced a row -------------------
    first = str(summary["Ticker"].iloc[0])
    print(analyzer.build_prompt(summary, first))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["RELIANCE", "TCS", "INFY"]))
