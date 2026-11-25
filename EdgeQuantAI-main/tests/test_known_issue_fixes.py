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
