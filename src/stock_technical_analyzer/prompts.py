"""LLM prompt construction from the latest technical snapshot of a ticker.

The two prompt templates below are copied byte-for-byte from the original
implementation, **including their 8/12-space indentation**. That whitespace is
load-bearing: the metrics block is interpolated *before* ``textwrap.dedent``
runs, so the common margin that dedent strips depends on both the template
indentation and the metrics lines. Re-indenting a template changes the prompt
text (pinned by ``tests/golden/*.txt``). See KNOWN_ISSUES.md.
"""

from __future__ import annotations

import logging
import textwrap
from collections.abc import Mapping
from typing import Any, Final

import pandas as pd

from stock_technical_analyzer import constants as c

logger = logging.getLogger(__name__)

SCORING_MODE: Final = "scoring"
_METRIC_LINE_PREFIX: Final = "     "

# fmt: off
SIMPLE_TEMPLATE: Final = """
        You are an expert Technical Analyst specializing in stock chart analysis for Indian equities.

        Analyze the stock **{ticker}** using the technical indicators provided below.
        Focus on price action, trend structure, indicators, candlestick patterns,support–resistance
        levels, volume behavior and indicator confluence.

        --You ARE allowed to include recent news, earnings, guidance, or company performance
        ONLY if it directly impacts the short-term technical outlook (momentum, volume, trend strength).

        You MAY include fundamentals ONLY if they directly influence short-term price
        action, such as:
        - Recent earnings (EPS beat/miss, margins, revenue trends)
        - Management guidance
        - Major company events (buybacks, dividends, splits, promoter activity)
        - FPI/DII flows, block/bulk deals
        - Order wins or regulatory announcements affecting momentum or volatility

        DO NOT use long-term fundamentals (ROE, ROCE, PE, Balance Sheet, etc.).
        DO NOT include macroeconomic commentary unrelated to price action.

        ----------------------------------------
        ### Technical Data Provided:
        {metrics_text}
        ----------------------------------------

        ### Your Task:

        1. **Trend Analysis**
        - Evaluate short-term trend (EMA/SMA 5, 10, 20)
        - Evaluate medium-term trend (EMA/SMA 50)
        - Evaluate long-term trend (EMA/SMA 200)
        - Identify higher-high / higher-low or lower-high / lower-low structure
        - Decide if the stock is in an uptrend, downtrend, or consolidation

        2. **Momentum Analysis**
        - Interpret RSI (overbought/oversold/neutral)
        - Analyze MACD direction + crossover
        - Interpret Stochastic.
        - Identify signs of momentum strength or exhaustion

        3. **Volume & Volatility**
        - Check for abnormal volume using Z-score
        - Identify volume spikes and whether they confirm or weaken the move
        - Analyze ATR direction (volatility rising or falling)

        4. **Candlestick Pattern Analysis**
        - Identify reversal or continuation patterns
        - Evaluate pattern strength
        - Confirm with volume when possible

        5. **Support & Resistance**
        - Identify nearest support levels
        - Identify nearest resistance levels
        - Determine if price is testing, rejecting, or breaking these zones

        6. **Entry / Exit Decision**
        Provide:
        - A clear BUY / SELL / HOLD recommendation
        - A suggested entry price (if applicable)
        - A technical stop-loss level
        - Short-term and medium-term targets
        7. **Key Reasoning** (2-3 bullet points maximum):
        - [Primary reason for recommendation]
        - [Supporting factor]
        - [Risk consideration]
        ----------------------------------------
        ### Requirements:
        - Base your judgment mainly on the technical metrics supplied.
        - You MAY include short-term news only when it influences momentum or price reaction.
        - The final answer MUST contain a clear BUY / SELL / HOLD rating with justification.
        ----------------------------------------

        Now generate your full technical analysis.
        """

SCORING_TEMPLATE: Final = """

        You are an expert Technical Analyst. Analyze **{ticker}** using this systematic framework:

        ----------------------------------------
            ### Technical Data Provided:
            {metrics_text}
        ----------------------------------------

        ### PHASE 1: INDICATOR ASSESSMENT (Assign Individual Scores)
        For each category, score as Bullish (+1), Neutral (0), or Bearish (-1):

        1. **Trend Score** (Short/Medium/Long EMA/SMA alignment)
        2. **Momentum Score** (RSI, MACD, Stochastic combined)
        3. **Volume Score** (Z-score, volume spike, trend confirmation)
        4. **Volatility Score** (ATR direction, BB squeeze/expansion)
        5. **Support/Resistance Score** (Price position relative to key levels)

        **Total Technical Score**: Sum all scores (Range: -5 to +5)

        ### PHASE 2: CONFLUENCE CHECK
        - How many indicators point in the same direction?
        - Are there critical contradictions? (e.g., bullish trend but bearish divergence)
        - Which signals are most reliable given current market structure?

        ### PHASE 3: ENTRY CRITERIA VALIDATION
        A valid BUY signal requires:
        - ✓ Technical Score ≥ +3
        - ✓ Volume confirmation (Z-score > 1.5 OR volume spike = True)
        - ✓ Price above key support OR near bounce zone
        - ✓ Risk-reward ratio ≥ 1:2

        If any criterion fails, explain why and suggest HOLD or WAIT.

        ### PHASE 4: RISK-REWARD CALCULATION
        - **Entry Price**: [Specify based on current setup]
        - **Stop-Loss**: [Based on ATR or key support - maximum 3-5% risk]
        - **Target 1**: [Conservative - nearest resistance]
        - **Target 2**: [Aggressive - extended resistance]
        - **Risk-Reward Ratio**: [Calculate explicitly]
        - **Position Size**: [Based on volatility - lower size if ATR increasing]

        ### PHASE 5: CONTEXTUAL FACTORS
        - **Recent News/Events** (Only if directly impacts short-term price action)
        - **Pattern Strength**: Evaluate candlestick pattern reliability
        - **Market Structure**: Is this a breakout, pullback, or reversal setup?

        ### PHASE 6: FINAL DECISION (Use This Exact Format)

        **RECOMMENDATION**: [STRONG BUY / BUY / HOLD / SELL]
        **CONFIDENCE LEVEL**: [HIGH / MEDIUM / LOW]
        **TECHNICAL SCORE**: [X/5]

        **Entry Strategy**:
        - Primary Entry: [Price]
        - Alternative Entry: [Better price if available]

        **Exit Strategy**:
        - Stop-Loss: [Price] (X% risk)
        - Target 1: [Price] - Exit 50% position
        - Target 2: [Price] - Exit remaining 50%
        - Trailing Stop: [Activate when price reaches X%]

        **Trade Invalidation**: [Conditions that void this setup]

        **Key Reasoning** (2-3 bullet points maximum):
        - [Primary reason for recommendation]
        - [Supporting factor]
        - [Risk consideration]

        ### RULES:
        - Never recommend BUY if risk-reward < 1:1.5
        - If indicators conflict (score between -1 to +2), recommend HOLD
        - Cite specific data points from the provided metrics
        - Keep final reasoning concise and actionable

        """
# fmt: on


def get_tech_data_for_ticker(df: pd.DataFrame, ticker: str) -> dict[Any, Any]:
    """Return the most recent row for ``ticker`` as a dict.

    Args:
        df: Summary frame with a ``Ticker`` column (e.g. the output of
            ``StockTechnicalAnalyzer.main``).
        ticker: Ticker to select (exact match).

    Returns:
        ``{column: value}`` for the last matching row, in column order.

    Raises:
        ValueError: If no row matches ``ticker``.
    """
    data = df[df[c.TICKER] == ticker]
    if data.empty:
        raise ValueError(f"No data found for ticker: {ticker}")
    return data.iloc[-1].to_dict()


def format_metrics(tech_data: Mapping[Any, Any]) -> str:
    """Render ``key: value`` lines, skipping ``None`` values (NaN is kept)."""
    return "\n".join(
        f"{_METRIC_LINE_PREFIX}{key}: {value}"
        for key, value in tech_data.items()
        if value is not None
    )


def generate_technical_prompt(
    ticker: Any, tech_data: Mapping[Any, Any], mode: str = "simple"
) -> str:
    """Build the LLM prompt for ``ticker``.

    Args:
        ticker: Ticker shown in the prompt.
        tech_data: Metric name -> value mapping; ``None`` values are omitted.
        mode: ``"scoring"`` selects the scoring-framework prompt; any other
            value selects the default narrative prompt.

    Returns:
        The prompt text (dedented and stripped).
    """
    template = SCORING_TEMPLATE if mode == SCORING_MODE else SIMPLE_TEMPLATE
    prompt = textwrap.dedent(
        template.format(ticker=ticker, metrics_text=format_metrics(tech_data))
    ).strip()
    logger.debug("Generated %s prompt for %s:\n%s", mode, ticker, prompt)
    return prompt
