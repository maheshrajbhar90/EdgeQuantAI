"""Regression tests for fixed KNOWN_ISSUES.md items (one section per issue ID).

Each test here failed on the code before its fix.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest
import yfinance

import stock_technical_analyzer as sta
from conftest import FakeYF, load_raw_ohlcv, to_yf_frame


# --------------------------------------------------------------------------- #
# A1: exchange suffix appended even when the ticker already has one
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("ticker", "expected"),
    [
        ("TCS", "TCS.NS"),
        ("TCS.NS", "TCS.NS"),
        ("tcs.ns", "tcs.ns"),
        ("TCS.BO", "TCS.BO"),
        ("tcs.Bo", "tcs.Bo"),
    ],
)
def test_a1_yahoo_symbol(ticker: str, expected: str) -> None:
    from stock_technical_analyzer.data import to_yahoo_symbol

    assert to_yahoo_symbol(ticker, ".NS") == expected


@pytest.mark.parametrize(
    ("ticker", "requested"),
    [("TCS", "TCS.NS"), ("TCS.NS", "TCS.NS"), ("tcs.ns", "tcs.ns"), ("TCS.BO", "TCS.BO")],
)
def test_a1_fetch_ohlc(fake_yf: FakeYF, ticker: str, requested: str) -> None:
    sta.StockTechnicalAnalyzer().fetch_ohlc(ticker)
    assert fake_yf.calls[-1][0] == (requested,)


@pytest.mark.parametrize(
    ("ticker", "requested"),
    [("TCS", "TCS.NS"), ("TCS.NS", "TCS.NS"), ("tcs.ns", "tcs.ns"), ("TCS.BO", "TCS.BO")],
)
def test_a1_pipeline(fake_yf: FakeYF, ticker: str, requested: str) -> None:
    sta.StockTechnicalAnalyzer().get_latest_candlestick_patterns([ticker])
    assert fake_yf.calls[-1][0] == (requested,)


def test_a1_pipeline_already_suffixed_ticker_is_analysed(fake_yf: FakeYF) -> None:
    result = sta.StockTechnicalAnalyzer().main(["AAA.NS"])
    assert result is not None
    assert list(result["Ticker"]) == ["AAA.NS"]


@pytest.mark.parametrize(
    ("ticker", "requested"),
    [("TCS", "TCS.NS"), ("TCS.NS", "TCS.NS"), ("tcs.ns", "tcs.ns"), ("TCS.BO", "TCS.BO")],
)
def test_a1_fundamental(monkeypatch: pytest.MonkeyPatch, ticker: str, requested: str) -> None:
    seen: list[str] = []

    class FakeTicker:
        def __init__(self, symbol: str) -> None:
            seen.append(symbol)
            self.financials = self.balance_sheet = self.cashflow = pd.DataFrame()
            self.info: dict[str, Any] = {}
            self.earnings = None

    monkeypatch.setattr(yfinance, "Ticker", FakeTicker)
    sta.FundamentalAnalyser().fetch_yf_financials(ticker)
    assert seen == [requested]


def test_a1_empty_suffix_unchanged(fake_yf: FakeYF) -> None:
    fake_yf.register("AAA", to_yf_frame(load_raw_ohlcv(), "AAA"))
    assert sta.StockTechnicalAnalyzer(exchange_suffix="").fetch_ohlc("AAA") is not None
    assert fake_yf.calls[-1][0] == ("AAA",)


# --------------------------------------------------------------------------- #
# B1: KeyError when no ticker has any candlestick match
# --------------------------------------------------------------------------- #
def _no_pattern_ohlcv(rows: int = 260) -> pd.DataFrame:
    """Steady uptrend of identical small candles: no TA-Lib pattern fires on any bar."""
    close = 100 + 0.05 * np.arange(rows)
    return pd.DataFrame(
        {
            "Open": close - 0.2,
            "High": close + 0.1,
            "Low": close - 0.3,
            "Close": close,
            "Volume": np.arange(rows, dtype="int64") % 7 * 1000 + 50_000,
        },
        index=pd.bdate_range("2023-01-02", periods=rows, name="Date").astype("datetime64[s]"),
    )


def test_b1_fixture_really_has_no_patterns() -> None:
    from stock_technical_analyzer.patterns import PATTERN_FUNCTIONS

    raw = _no_pattern_ohlcv()
    o, h, low, cl = (raw[col] for col in ("Open", "High", "Low", "Close"))
    assert all(not (fn(o, h, low, cl) != 0).any() for _, fn in PATTERN_FUNCTIONS)


def test_b1_identify_patterns_always_adds_columns() -> None:
    out = sta.StockTechnicalAnalyzer().identify_candlestick_patterns(_no_pattern_ohlcv())
    assert list(out.columns[-2:]) == ["Pattern", "Code"]
    assert out["Pattern"].isna().all()
    assert out["Code"].isna().all()
    assert out["Code"].dtype == "float64"


def test_b1_pipeline_without_any_pattern_match(fake_yf: FakeYF) -> None:
    fake_yf.register("FLATUP.NS", to_yf_frame(_no_pattern_ohlcv(), "FLATUP.NS"))
    analyzer = sta.StockTechnicalAnalyzer()

    merged = analyzer.get_latest_candlestick_patterns(["FLATUP"])
    assert merged is not None
    assert {"Pattern", "Code"} <= set(merged.columns)

    summary = analyzer.main(["FLATUP"])
    assert summary is not None
    assert list(summary.columns[-2:]) == ["Pattern", "Code"]
    assert list(summary["Ticker"]) == ["FLATUP"]
    assert summary["Pattern"].isna().all()
    assert summary["Code"].isna().all()


# --------------------------------------------------------------------------- #
# F1: debt lookup read columns instead of rows, so it always returned 0
# --------------------------------------------------------------------------- #
# Layout of yfinance ``Ticker.balance_sheet`` (checked against live data):
# line items are ROWS, fiscal-year end dates are COLUMNS, newest first.
_YEARS = pd.DatetimeIndex(["2026-03-31", "2025-03-31", "2024-03-31", "2023-03-31"]).astype(
    "datetime64[us]"
)


def _balance_sheet(rows: dict[str, list[float]]) -> pd.DataFrame:
    return pd.DataFrame.from_dict(rows, orient="index", columns=_YEARS)


_REAL_LAYOUT_ROWS = {
    "Net Debt": [2.1e12, 1.9e12, 1.7e12, 1.5e12],
    "Total Debt": [3.6e12, 3.4e12, 3.2e12, 3.0e12],
    "Long Term Debt And Capital Lease Obligation": [2.9e12, 2.7e12, 2.5e12, 2.3e12],
    "Long Term Debt": [2.8e12, 2.6e12, 2.4e12, 2.2e12],
    "Current Debt And Capital Lease Obligation": [7.1e11, 6.9e11, 6.5e11, 6.1e11],
    "Current Debt": [7.0e11, 6.8e11, 6.4e11, 6.0e11],
    "Total Assets": [1.9e13, 1.8e13, 1.7e13, 1.6e13],
}


def test_f1_long_term_debt_read_from_rows() -> None:
    fin = {"balance": _balance_sheet(_REAL_LAYOUT_ROWS), "info": {"totalDebt": 9.99e12}}
    metrics = sta.FundamentalAnalyser().compute_ratios(fin)
    # Latest column's "Long Term Debt" row, not the info["totalDebt"] fallback.
    assert metrics["total_debt"] == 2.8e12


def test_f1_long_and_short_term_debt_are_summed() -> None:
    rows = {"Long Term Debt": [400.0, 300.0, 0.0, 0.0], "Short Term Debt": [100.0, 50.0, 0.0, 0.0]}
    fin = {"balance": _balance_sheet(rows), "info": {"totalDebt": 555.0}}
    assert sta.FundamentalAnalyser().compute_ratios(fin)["total_debt"] == 500.0


def test_f1_falls_back_to_info_when_no_debt_rows() -> None:
    fin = {
        "balance": _balance_sheet({"Total Assets": [1.0, 1.0, 1.0, 1.0]}),
        "info": {"totalDebt": 7.0},
    }
    assert sta.FundamentalAnalyser().compute_ratios(fin)["total_debt"] == 7.0


# --------------------------------------------------------------------------- #
# C1: importing the library silenced all warnings process-wide
# --------------------------------------------------------------------------- #
# numpy, requests and yfinance each register their own narrow filters at
# import time, so they are imported first; the snapshot then isolates what
# *this* package does. Runs in a fresh interpreter (the package is already
# imported in the test process).
_FILTER_PROBE = """
import json, sys, warnings
import numpy, pandas, requests, tabulate, openai, yfinance, talib  # dependencies first
before = [repr(f) for f in warnings.filters]
import {module}
after = [repr(f) for f in warnings.filters]
print(json.dumps({{"before": before, "after": after}}))
"""


@pytest.mark.parametrize("module", ["stock_technical_analyzer", "EdgeQuantAI", "stock_analyzer"])
def test_c1_import_leaves_warning_filters_unchanged(module: str) -> None:
    import json
    import subprocess
    import sys

    out = subprocess.run(
        [sys.executable, "-P", "-c", _FILTER_PROBE.format(module=module)],
        capture_output=True,
        text=True,
        check=True,
        cwd="/",
    )
    result = json.loads(out.stdout.strip().splitlines()[-1])
    assert result["after"] == result["before"]


def test_c1_main_emits_no_warnings_and_restores_filters(fake_yf: FakeYF) -> None:
    import warnings

    before = list(warnings.filters)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        inner_before = list(warnings.filters)
        assert sta.StockTechnicalAnalyzer().main(["AAA", "BBB"]) is not None
        assert warnings.filters == inner_before  # local suppression doesn't leak
    assert [str(w.message) for w in caught] == []
    assert warnings.filters == before


def test_c1_other_warnings_still_surface() -> None:
    import warnings

    with pytest.warns(UserWarning, match="still visible"):
        warnings.warn("still visible", UserWarning, stacklevel=1)
