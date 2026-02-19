# Stock Technical Analyzer

This project provides a Python class, `StockTechnicalAnalyzer`, for performing comprehensive technical analysis on stock data. It leverages `yfinance` for data fetching and `TA-Lib` for indicator calculations, offering features like:

-   Fetching historical OHLC (Open, High, Low, Close) data for specified tickers.
-   Calculating a wide range of technical indicators (EMA, SMA, RSI, MACD, Bollinger Bands, Stochastic, ATR, ADX, Volume Z-score).
-   Identifying common candlestick patterns.
-   Generating trading signals based on indicator crossovers and other conditions.
-   Calculating Support and Resistance levels using pivot points.

## Features

-   **Data Fetching**: Seamless integration with `yfinance` to download historical stock data.
-   **Technical Indicators**: Automatically computes popular indicators.
-   **Directional Metrics**: Provides directional insights for Bollinger Bands, Stochastic Oscillator, ATR, and ADX.
-   **Candlestick Pattern Recognition**: Detects numerous candlestick patterns using `TA-Lib`.
-   **Trading Signal Generation**: Identifies potential buy/sell/hold opportunities based on a combination of indicators.
-   **Support & Resistance**: Calculates key price levels.

## Installation

To use this library, you need to install the following Python packages:

```bash
pip install yfinance pandas ta-lib
```

**Note for TA-Lib**: On some systems, `TA-Lib` might require additional steps for installation. If `pip install TA-Lib` fails, please refer to the official TA-Lib-Python documentation or install the underlying C library first. In Google Colab, you can install it using `!pip install TA-Lib`.

## Usage

Here's how to use the `StockTechnicalAnalyzer` class:

### 1. Initialize the Analyzer

```python
from stock_analyzer import StockTechnicalAnalyzer # Assuming the class is in stock_analyzer.py

analyzer = StockTechnicalAnalyzer(period="1y", interval="1d", exchange_suffix=".NS")
# period: Data period (e.g., "1y", "5y", "max")
# interval: Data interval (e.g., "1d", "1wk", "1mo")
# exchange_suffix: Suffix for the stock ticker (e.g., ".NS" for NSE, "" for NYSE)
```

### 2. Fetch OHLC Data

```python
reliance_data = analyzer.fetch_ohlc("RELIANCE")
if reliance_data is not None:
    print("Successfully fetched data for RELIANCE:")
    display(reliance_data.head())
else:
    print("Failed to fetch data for RELIANCE.")
```

### 3. Add Technical Indicators

```python
reliance_data_with_indicators = analyzer.add_indicators(reliance_data.copy())

if reliance_data_with_indicators is not None:
    print("Reliance data with indicators (Tail):")
    display(reliance_data_with_indicators.tail())
else:
    print("Failed to add indicators. Data might be insufficient.")
```

### 4. Generate Trading Signal

```python
trading_signal = analyzer.generate_signal(reliance_data_with_indicators)

if trading_signal:
    print("Generated Trading Signal:")
    for key, value in trading_signal.items():
        print(f"  {key}: {value}")
else:
    print("No trading signal generated based on current conditions.")
```

### 5. Identify Candlestick Patterns

```python
reliance_data_with_patterns = analyzer.identify_candlestick_patterns(reliance_data_with_indicators.copy())

if reliance_data_with_patterns is not None:
    print("Reliance data with identified candlestick patterns (Tail):")
    display(reliance_data_with_patterns.tail())
else:
    print("Failed to identify candlestick patterns. Data might be insufficient or empty.")
```

### 6. Perform Complete Technical Analysis for multiple tickers

The `perform_technical_analysis` method streamlines the process of fetching data, adding indicators, generating signals, and identifying patterns for a list of tickers, returning a consolidated DataFrame.

```python
tickers_to_analyze = ["RELIANCE", "TCS.NS"]
final_results_df = analyzer.perform_technical_analysis(tickers_to_analyze)

if final_results_df is not None:
    print("Complete technical analysis results:")
    display(final_results_df.head())
else:
    print("No valid data processed for the given tickers.")
```

### 7. Generate a Technical Analysis Prompt (for LLMs)

You can also use the class to generate a structured prompt suitable for Large Language Models (LLMs) to perform a qualitative technical analysis.

```python
# Assuming `final_results_df` is available from step 6 or similar
if final_results_df is not None and not final_results_df.empty:
    ticker_for_prompt = "RELIANCE"
    try:
        tech_prompt = analyzer.build_prompt(final_results_df, ticker_for_prompt)
        print(f"\nTechnical Analysis Prompt for {ticker_for_prompt}:\n")
        print(tech_prompt)
    except ValueError as e:
        print(f"Error generating prompt for {ticker_for_prompt}: {e}")
else:
    print("Cannot generate prompt: No technical analysis data available.")
```

## Class Structure

-   `__init__(self, period="3y", interval="1d", exchange_suffix=".NS")`: Initializes the analyzer with data fetching parameters.
-   `fetch_ohlc(self, ticker)`: Fetches OHLC data for a single ticker.
-   `add_indicators(self, ohlc)`: Adds various technical indicators to the OHLC DataFrame.
-   `generate_signal(self, data)`: Generates a trading signal and key metrics based on the latest data.
-   `identify_candlestick_patterns(self, ohlc_df)`: Detects candlestick patterns in the OHLC data.
-   `support_resistance_level(self, ohlc_day)`: Calculates pivot points and support/resistance levels.
-   `z_score(self, df, window=20)`: Calculates rolling volume Z-score.
-   `bb_direction(self, row)`: Determines Bollinger Bands direction.
-   `stoch_direction(self, row)`: Determines Stochastic Oscillator direction.
-   `adx_direction(self, val)`: Determines ADX trend strength.
-   `perform_technical_analysis(self, ticker: list)`: Performs a complete analysis pipeline for a list of tickers.
-   `get_tech_data_for_ticker(self, df, ticker)`: Extracts the latest technical data for a specific ticker from a results DataFrame.
-   `generate_technical_prompt(self, ticker, tech_data, mode="simple")`: Generates a prompt for an LLM based on technical data.
-   `build_prompt(self, df, ticker)`: Combines `get_tech_data_for_ticker` and `generate_technical_prompt`.

