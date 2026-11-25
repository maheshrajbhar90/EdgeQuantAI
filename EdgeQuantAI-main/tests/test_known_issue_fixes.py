"""Regression tests for fixed KNOWN_ISSUES.md items (one section per issue ID).

Each test here failed on the code before its fix.
"""

from __future__ import annotations

from typing import Any

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
