import os
import math
import requests
import yfinance as yf
import pandas as pd
import numpy as np
from tabulate import tabulate
from openai import OpenAI

FMP_BASE = "https://financialmodelingprep.com/api/v3"


class FundamentalAnalyser:
    def __init__(self, fmp_api_key=None, openai_key=None,exchange_suffix=".NS"):
        self.fmp_api_key = fmp_api_key
        self.openai_key = openai_key
        self.client = OpenAI(api_key=openai_key) if openai_key else None
        self.exchange_suffix=exchange_suffix

    # ---------- Utils ----------
    @staticmethod
    def safe_div(a, b):
        if b in (None, 0):
            return None
        try:
            return a / b
        except Exception:
            return None

    # ---------- Data Fetch ----------
    def fetch_yf_financials(self, symbol):
        tk = yf.Ticker(symbol+self.exchange_suffix)
        return {
            "income": tk.financials,
            "balance": tk.balance_sheet,
            "cashflow": tk.cashflow,
            "info": tk.info,
            "earnings": tk.earnings,
        }

    def fetch_fmp_ratios(self, symbol):
        if not self.fmp_api_key:
            return None
        try:
            url = f"{FMP_BASE}/ratios/{symbol}?apikey={self.fmp_api_key}"
            r = requests.get(url, timeout=10)
            data = r.json()
            return data if isinstance(data, list) and data else None
        except Exception:
            return None

    # ---------- Core Computation ----------
    def compute_ratios(self, fin):
        income = fin.get("income", pd.DataFrame()).fillna(0)
        balance = fin.get("balance", pd.DataFrame()).fillna(0)
        cash = fin.get("cashflow", pd.DataFrame()).fillna(0)
        info = fin.get("info", {}) or {}

        def latest_col(df):
            return df.columns[0] if not df.empty else None

        ic, bc, cc = latest_col(income), latest_col(balance), latest_col(cash)

        net_income = income.loc["Net Income", ic] if "Net Income" in income.index else None
        revenue = income.loc["Total Revenue", ic] if "Total Revenue" in income.index else None
        ebit = income.loc["Operating Income", ic] if "Operating Income" in income.index else None

        total_equity = balance.loc["Total Stockholder Equity", bc] if "Total Stockholder Equity" in balance.index else None
        total_assets = balance.loc["Total Assets", bc] if "Total Assets" in balance.index else None

        total_debt = (
            balance.get("Long Term Debt", pd.Series()).get(bc, 0)
            + balance.get("Short Term Debt", pd.Series()).get(bc, 0)
        ) or info.get("totalDebt")

        operating_cf = cash.loc["Total Cash From Operating Activities", cc] if "Total Cash From Operating Activities" in cash.index else None
        capex = cash.loc["Capital Expenditures", cc] if "Capital Expenditures" in cash.index else None

        fcf = operating_cf - capex if operating_cf is not None and capex is not None else operating_cf

        roe = self.safe_div(net_income, total_equity)
        roce = self.safe_div(ebit, total_equity + total_debt) if ebit and total_equity and total_debt else None

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

    # ---------- Prompt ----------
    def build_prompt(self, symbol, metrics):
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

        """
    # ---------- LLM ----------
    def call_llm(self, prompt, model="gpt-4.1-nano", max_tokens=1500):
        if not self.client:
            return None
        res = self.client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": "You are an expert equity analyst."},
                {"role": "user", "content": prompt},
            ],
        )
        return res.choices[0].message.content

    # ---------- Public API ----------
    def analyze(self, symbol, use_llm=False):
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


