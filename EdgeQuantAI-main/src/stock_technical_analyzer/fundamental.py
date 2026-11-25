"""Fundamental snapshot + LLM prompt (yfinance financials, optional FMP and OpenAI).

Behaviour is preserved exactly from the original ``fundamental_analyzer`` module,
including several data-mapping issues documented in KNOWN_ISSUES.md.
"""

from __future__ import annotations

import logging
from typing import Any, Final

import pandas as pd
import requests
import yfinance as yf
from openai import OpenAI
from tabulate import tabulate

from stock_technical_analyzer.constants import DEFAULT_EXCHANGE_SUFFIX
from stock_technical_analyzer.data import to_yahoo_symbol

logger = logging.getLogger(__name__)

FMP_BASE: Final = "https://financialmodelingprep.com/api/v3"
FMP_TIMEOUT_SECONDS: Final = 10
DEFAULT_LLM_MODEL: Final = "gpt-4.1-nano"
DEFAULT_MAX_TOKENS: Final = 1500
LLM_SYSTEM_PROMPT: Final = "You are an expert equity analyst."

# yfinance statement row labels read by ``compute_ratios``.
NET_INCOME: Final = "Net Income"
TOTAL_REVENUE: Final = "Total Revenue"
OPERATING_INCOME: Final = "Operating Income"
TOTAL_EQUITY: Final = "Total Stockholder Equity"
TOTAL_ASSETS: Final = "Total Assets"
LONG_TERM_DEBT: Final = "Long Term Debt"
SHORT_TERM_DEBT: Final = "Short Term Debt"
OPERATING_CASH_FLOW: Final = "Total Cash From Operating Activities"
CAPEX: Final = "Capital Expenditures"


def _latest_col(df: pd.DataFrame) -> Any:
    return df.columns[0] if not df.empty else None


def _cell(df: pd.DataFrame, row: str, col: Any) -> Any:
    return df.loc[row, col] if row in df.index else None


class FundamentalAnalyser:
    """Compute a small set of fundamental ratios and build an analyst prompt.

    Args:
        fmp_api_key: Optional Financial Modeling Prep key for :meth:`fetch_fmp_ratios`.
        openai_key: Optional OpenAI key; when given an ``OpenAI`` client is created.
        exchange_suffix: Suffix appended to symbols for yfinance lookups.

    Example:
        >>> fa = FundamentalAnalyser()
        >>> fa.safe_div(10, 4)
        2.5
    """

    def __init__(
        self,
        fmp_api_key: str | None = None,
        openai_key: str | None = None,
        exchange_suffix: str = DEFAULT_EXCHANGE_SUFFIX,
    ) -> None:
        self.fmp_api_key = fmp_api_key
        self.openai_key = openai_key
        self.client = OpenAI(api_key=openai_key) if openai_key else None
        self.exchange_suffix = exchange_suffix

    # ------------------------------------------------------------------ utils
    @staticmethod
    def safe_div(a: Any, b: Any) -> Any:
        """Return ``a / b``, or ``None`` if ``b`` is ``None``/zero or division fails.

        Args:
            a: Numerator.
            b: Denominator.

        Returns:
            The quotient, or ``None``.
        """
        if b in (None, 0):
            return None
        try:
            return a / b
        except (TypeError, ArithmeticError, ValueError):
            return None

    # -------------------------------------------------------------- data fetch
    def fetch_yf_financials(self, symbol: str) -> dict[str, Any]:
        """Fetch annual statements and ``info`` from yfinance.

        Args:
            symbol: Base symbol; :attr:`exchange_suffix` is appended unless the
                symbol is already qualified (``.NS``/``.BO``).

        Returns:
            Dict with ``income``, ``balance``, ``cashflow``, ``info``, ``earnings``.
        """
        tk = yf.Ticker(to_yahoo_symbol(symbol, self.exchange_suffix))
        return {
            "income": tk.financials,
            "balance": tk.balance_sheet,
            "cashflow": tk.cashflow,
            "info": tk.info,
            "earnings": tk.earnings,
        }

    def fetch_fmp_ratios(self, symbol: str) -> list[Any] | None:
        """Fetch ratio history from Financial Modeling Prep.

        Args:
            symbol: Symbol as FMP expects it (no suffix is added).

        Returns:
            The non-empty JSON list, or ``None`` if no API key is set, the
            request fails, or the response is not a non-empty list.
        """
        if not self.fmp_api_key:
            return None
        try:
            url = f"{FMP_BASE}/ratios/{symbol}?apikey={self.fmp_api_key}"
            response = requests.get(url, timeout=FMP_TIMEOUT_SECONDS)
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            # Log the type only: requests error messages embed the URL, which
            # carries the API key as a query parameter.
            logger.warning("FMP ratios request failed for %s (%s)", symbol, type(exc).__name__)
            return None
        return data if isinstance(data, list) and data else None

    # ------------------------------------------------------------ computation
    def compute_ratios(self, fin: dict[str, Any]) -> dict[str, Any]:
        """Derive headline metrics from the latest annual statements.

        Args:
            fin: Output of :meth:`fetch_yf_financials` (missing keys allowed).

        Returns:
            Dict of raw values and ratios; unavailable items are ``None``.
        """
        income = fin.get("income", pd.DataFrame()).fillna(0)
        balance = fin.get("balance", pd.DataFrame()).fillna(0)
        cash = fin.get("cashflow", pd.DataFrame()).fillna(0)
        info = fin.get("info", {}) or {}

        ic, bc, cc = _latest_col(income), _latest_col(balance), _latest_col(cash)

        net_income = _cell(income, NET_INCOME, ic)
        revenue = _cell(income, TOTAL_REVENUE, ic)
        ebit = _cell(income, OPERATING_INCOME, ic)
        total_equity = _cell(balance, TOTAL_EQUITY, bc)
        total_assets = _cell(balance, TOTAL_ASSETS, bc)
        # NB: DataFrame.get looks up *columns*, not rows; see KNOWN_ISSUES.md.
        total_debt = (
            balance.get(LONG_TERM_DEBT, pd.Series()).get(bc, 0)
            + balance.get(SHORT_TERM_DEBT, pd.Series()).get(bc, 0)
        ) or info.get("totalDebt")
        operating_cf = _cell(cash, OPERATING_CASH_FLOW, cc)
        capex = _cell(cash, CAPEX, cc)

        fcf = (
            operating_cf - capex if operating_cf is not None and capex is not None else operating_cf
        )
        roe = self.safe_div(net_income, total_equity)
        roce = (
            self.safe_div(ebit, total_equity + total_debt)
            if ebit and total_equity and total_debt
            else None
        )

        return {
            "net_income": net_income,
            "revenue": revenue,
            "ebit": ebit,
            "total_equity": total_equity,
            "total_debt": total_debt,
            "total_assets": total_assets,
            "operating_cf": operating_cf,
            "fcf": fcf,
            "roe": roe,
            "roce": roce,
            "pe": info.get("trailingPE"),
            "pb": info.get("priceToBook"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
        }

    # ----------------------------------------------------------------- prompt
    def build_prompt(self, symbol: str, metrics: dict[str, Any]) -> str:
        """Render the fundamental-analysis prompt (whitespace preserved verbatim).

        Args:
            symbol: Symbol shown in the prompt.
            metrics: Output of :meth:`compute_ratios`.

        Returns:
            The prompt text.
        """
        table_txt = tabulate(metrics.items(), tablefmt="github")
        return f"""
        You are an expert equity analyst. I will give you a stock symbol and some computed financial metrics.
        Symbol: {symbol}

        Below is the snapshot of computed metrics (from latest available annual data). Use the metrics,
        any reasonable assumptions, sector context, and the full fundamental framework to give a clear,
        structured analysis and a final recommendation: BUY / HOLD / SELL, with 0-100% confidence and 4-6 bullet justifications.

        Snapshot:
        {table_txt}

        Instructions:
        - Compute or reason about ROE, ROCE, margins, leverage, liquidity, cash flow quality, valuation, governance (if info given).
        - If information is missing, explicitly state which items are missing and how that affects confidence.
        - Produce sections: Profitability, Financial Health & Leverage, Cash Flow & Earnings Quality, Valuation, Shareholder Returns & Capital Allocation, Management & Governance, Final Checklist (short bullets), Recommendation (BUY/HOLD/SELL + confidence).
        - Keep the analysis actionable and concise. Use absolute dates where relevant and call out any data limitations.

        """  # noqa: E501

    # -------------------------------------------------------------------- LLM
    def call_llm(
        self, prompt: str, model: str = DEFAULT_LLM_MODEL, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> str | None:
        """Send ``prompt`` to OpenAI chat completions.

        Args:
            prompt: User message.
            model: OpenAI model name.
            max_tokens: Completion token limit.

        Returns:
            The first choice's content, or ``None`` if no client is configured.
        """
        if not self.client:
            return None
        res = self.client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return res.choices[0].message.content

    # ------------------------------------------------------------- public API
    def analyze(self, symbol: str, use_llm: bool = False) -> dict[str, Any]:
        """Run fetch -> ratios -> (FMP) -> prompt -> (LLM) for ``symbol``.

        Args:
            symbol: Base symbol.
            use_llm: Call the LLM when a client is configured.

        Returns:
            Dict with ``symbol``, ``metrics``, ``fmp_ratios``, ``prompt``, ``llm_analysis``.
        """
        fin = self.fetch_yf_financials(symbol)
        metrics = self.compute_ratios(fin)
        fmp = self.fetch_fmp_ratios(symbol)
        prompt = self.build_prompt(symbol, metrics)
        llm_output = self.call_llm(prompt) if use_llm else None
        return {
            "symbol": symbol,
            "metrics": metrics,
            "fmp_ratios": fmp,
            "prompt": prompt,
            "llm_analysis": llm_output,
        }
