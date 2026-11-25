"""Characterization ("golden") tests for ``StockTechnicalAnalyzer``.

These tests were written and their snapshots generated against the ORIGINAL,
pre-refactor implementation (commit 811823c). They pin current behaviour,
including behaviour that looks like a bug (see KNOWN_ISSUES.md). They must not
be edited as part of a refactor; if one fails, the refactor changed behaviour.

They import through the legacy ``EdgeQuantAI`` path on purpose, which also
proves the backwards-compatibility shim keeps working.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
import pandas as pd
import pytest

from conftest import FakeYF, Snapshot, load_raw_ohlcv, to_yf_frame
from EdgeQuantAI import FundamentalAnalyser, StockTechnicalAnalyzer


@pytest.fixture
def analyzer() -> StockTechnicalAnalyzer:
    return StockTechnicalAnalyzer()


@pytest.fixture
def ohlc(analyzer: StockTechnicalAnalyzer, fake_yf: FakeYF) -> pd.DataFrame:
    df = analyzer.fetch_ohlc("AAA")
    assert df is not None
    return df


@pytest.fixture
def with_indicators(analyzer: StockTechnicalAnalyzer, ohlc: pd.DataFrame) -> pd.DataFrame:
    df = analyzer.add_indicators(ohlc)
    assert df is not None
    return df


# --------------------------------------------------------------------------- #
# __init__
# --------------------------------------------------------------------------- #
def test_init_defaults(analyzer: StockTechnicalAnalyzer) -> None:
    assert analyzer.period == "5y"
    assert analyzer.interval == "1d"
    assert analyzer.exchange_suffix == ".NS"
    # Compared by name: the original loads fundamental_analyzer twice under two
    # module names (see KNOWN_ISSUES.md), so class identity is not stable.
    assert type(analyzer.fundamental).__name__ == FundamentalAnalyser.__name__
    assert analyzer.fundamental.client is None
    assert analyzer.fundamental.fmp_api_key is None
    # Note: the technical analyzer's suffix is NOT forwarded to the fundamental one.
    assert analyzer.fundamental.exchange_suffix == ".NS"


def test_init_custom() -> None:
    a = StockTechnicalAnalyzer(period="1y", interval="1wk", exchange_suffix="", fmp_api_key="k")
    assert (a.period, a.interval, a.exchange_suffix) == ("1y", "1wk", "")
    assert a.fundamental.fmp_api_key == "k"
    assert a.fundamental.exchange_suffix == ".NS"


# --------------------------------------------------------------------------- #
# fetch_ohlc
# --------------------------------------------------------------------------- #
def test_fetch_ohlc_snapshot(ohlc: pd.DataFrame, fake_yf: FakeYF, snapshot: Snapshot) -> None:
    snapshot.check("fetch_ohlc", ohlc)
    assert fake_yf.calls[-1] == (
        ("AAA.NS",),
        {"period": "5y", "interval": "1d", "auto_adjust": True, "progress": False},
    )


def test_fetch_ohlc_daily_dates_shift_to_0530(ohlc: pd.DataFrame) -> None:
    # Naive daily dates are treated as UTC and converted to IST.
    assert ohlc.index[0] == pd.Timestamp("2023-01-02 05:30:00")
    assert ohlc.index.tz is None


def test_fetch_ohlc_unknown_ticker_returns_none(
    analyzer: StockTechnicalAnalyzer, fake_yf: FakeYF
) -> None:
    assert analyzer.fetch_ohlc("ZZZ") is None


def test_fetch_ohlc_appends_suffix_even_if_present(
    analyzer: StockTechnicalAnalyzer, fake_yf: FakeYF
) -> None:
    # KNOWN_ISSUES A1 (fixed): was `is None` after requesting "AAA.NS.NS".
    assert analyzer.fetch_ohlc("AAA.NS") is not None
    assert fake_yf.calls[-1][0] == ("AAA.NS",)


def test_fetch_ohlc_intraday_datetime_column(
    analyzer: StockTechnicalAnalyzer, fake_yf: FakeYF, snapshot: Snapshot
) -> None:
    raw = load_raw_ohlcv(5)
    raw.index = pd.date_range("2024-03-01 09:15", periods=5, freq="15min", tz="Asia/Kolkata")
    fake_yf.register("INTRA.NS", to_yf_frame(raw, "INTRA.NS", index_name="Datetime"))
    df = analyzer.fetch_ohlc("INTRA")
    snapshot.check("fetch_ohlc_intraday", df)


def test_fetch_ohlc_flat_columns_raises(analyzer: StockTechnicalAnalyzer, fake_yf: FakeYF) -> None:
    fake_yf.register("FLAT.NS", load_raw_ohlcv(5))
    with pytest.raises(IndexError, match="Too many levels"):
        analyzer.fetch_ohlc("FLAT")


# --------------------------------------------------------------------------- #
# add_indicators
# --------------------------------------------------------------------------- #
def test_add_indicators_snapshot(with_indicators: pd.DataFrame, snapshot: Snapshot) -> None:
    snapshot.check("add_indicators", with_indicators)


def test_add_indicators_does_not_mutate_input(
    analyzer: StockTechnicalAnalyzer, ohlc: pd.DataFrame
) -> None:
    before = ohlc.copy()
    analyzer.add_indicators(ohlc)
    pd.testing.assert_frame_equal(ohlc, before)


def test_add_indicators_empty_returns_none(analyzer: StockTechnicalAnalyzer) -> None:
    assert analyzer.add_indicators(pd.DataFrame()) is None


def test_add_indicators_199_rows_returns_none(
    analyzer: StockTechnicalAnalyzer, ohlc: pd.DataFrame
) -> None:
    assert analyzer.add_indicators(ohlc.iloc[:199]) is None


def test_add_indicators_200_rows_ok(analyzer: StockTechnicalAnalyzer, ohlc: pd.DataFrame) -> None:
    out = analyzer.add_indicators(ohlc.iloc[:200])
    assert out is not None and len(out) == 200


# --------------------------------------------------------------------------- #
# generate_signal
# --------------------------------------------------------------------------- #
def test_generate_signal_snapshot(
    analyzer: StockTechnicalAnalyzer, with_indicators: pd.DataFrame, snapshot: Snapshot
) -> None:
    snapshot.check("generate_signal", analyzer.generate_signal(with_indicators))


@pytest.mark.parametrize(
    ("rows", "name"),
    [
        (212, "generate_signal_ema_bullish"),
        (246, "generate_signal_ema_bearish"),
        (210, "generate_signal_macd_bullish"),
        (234, "generate_signal_macd_bearish"),
    ],
)
def test_generate_signal_crossovers(
    analyzer: StockTechnicalAnalyzer,
    with_indicators: pd.DataFrame,
    snapshot: Snapshot,
    rows: int,
    name: str,
) -> None:
    snapshot.check(name, analyzer.generate_signal(with_indicators.iloc[:rows]))


def test_generate_signal_no_condition_returns_none(
    analyzer: StockTechnicalAnalyzer, with_indicators: pd.DataFrame
) -> None:
    assert analyzer.generate_signal(with_indicators.iloc[:202]) is None


def test_generate_signal_none_and_short(
    analyzer: StockTechnicalAnalyzer, with_indicators: pd.DataFrame
) -> None:
    assert analyzer.generate_signal(None) is None
    assert analyzer.generate_signal(with_indicators.iloc[:1]) is None
    assert analyzer.generate_signal(with_indicators.iloc[:0]) is None


@pytest.mark.parametrize(
    ("overrides", "ema", "macd", "spike", "rsi"),
    [
        ({}, None, None, None, None),
        ({"Volume": [1.0, 2001.0]}, "", "", True, False),
        ({"Volume": [1.0, 2000.0]}, None, None, None, None),  # strictly greater
        ({"RSI": [10.0, 60.0]}, "", "", False, True),  # >= 60
        ({"RSI": [10.0, 59.999]}, None, None, None, None),
        ({"EMA9": [1.0, 3.0], "EMA26": [2.0, 2.0]}, "Bullish", "", False, False),
        ({"EMA9": [3.0, 1.0], "EMA26": [2.0, 2.0]}, "Bearish", "", False, False),
        ({"EMA9": [2.0, 3.0], "EMA26": [2.0, 2.0]}, None, None, None, None),  # prev equal
        ({"MACD": [0.0, 2.0], "Signal": [1.0, 1.0]}, "", "Bullish", False, False),
        ({"MACD": [2.0, 0.0], "Signal": [1.0, 1.0]}, "", "Bearish", False, False),
        ({"MACD": [2.0, 1.0], "Signal": [1.0, 1.0]}, None, None, None, None),  # last equal
    ],
)
def test_generate_signal_branches(
    analyzer: StockTechnicalAnalyzer,
    make_signal_frame: Callable[..., pd.DataFrame],
    overrides: dict[str, list[float]],
    ema: str | None,
    macd: str | None,
    spike: bool | None,
    rsi: bool | None,
) -> None:
    result = analyzer.generate_signal(make_signal_frame(**overrides))
    if ema is None:
        assert result is None
        return
    assert result is not None
    assert result["EMA_Crossover"] == ema
    assert result["MACD_Crossover"] == macd
    assert result["Volume_Spike"] == spike
    assert result["RSI>=60"] == rsi


def test_generate_signal_key_order(
    analyzer: StockTechnicalAnalyzer, make_signal_frame: Callable[..., pd.DataFrame]
) -> None:
    result = analyzer.generate_signal(make_signal_frame(RSI=[10.0, 70.0]))
    assert result is not None
    assert list(result) == [
        "Date", "Ticker", "Close", "Change%", "Volume", "VMA20", "RSI_Value", "RSI>=60",
        "MACD_Value", "Signal_Value", "MACD_Crossover", "Volume_Spike", "Z_score",
        "BB_Direction", "Stoch_Direction", "ATR_Direction", "ADX_Direction", "EMA5", "EMA9",
        "EMA26", "SMA50", "SMA200", "EMA_Crossover", "Pivot_point", "Resistance_1",
        "Resistance_2", "Resistance_3", "Support_1", "Support_2", "Support_3",
    ]  # fmt: skip


# --------------------------------------------------------------------------- #
# identify_candlestick_patterns
# --------------------------------------------------------------------------- #
def test_identify_candlestick_patterns_snapshot(
    analyzer: StockTechnicalAnalyzer, with_indicators: pd.DataFrame, snapshot: Snapshot
) -> None:
    out = analyzer.identify_candlestick_patterns(with_indicators.copy())
    snapshot.check("identify_candlestick_patterns", out)


def test_identify_candlestick_patterns_raw_ohlc(
    analyzer: StockTechnicalAnalyzer, ohlc: pd.DataFrame, snapshot: Snapshot
) -> None:
    out = analyzer.identify_candlestick_patterns(ohlc.copy())
    snapshot.check("identify_candlestick_patterns_raw", out)


def test_identify_candlestick_patterns_mutates_and_returns_same_object(
    analyzer: StockTechnicalAnalyzer, ohlc: pd.DataFrame
) -> None:
    df = ohlc.copy()
    out = analyzer.identify_candlestick_patterns(df)
    assert out is df
    assert "Pattern" in df.columns and "Code" in df.columns


def test_identify_candlestick_patterns_no_match_adds_no_columns(
    analyzer: StockTechnicalAnalyzer,
) -> None:
    df = pd.DataFrame({"Open": [1.0] * 3, "High": [1.0] * 3, "Low": [1.0] * 3, "Close": [1.0] * 3})
    flat = analyzer.identify_candlestick_patterns(df.copy())
    # Flat bars still register as dojis etc.; capture exactly what columns exist.
    assert list(flat.columns)[:4] == ["Open", "High", "Low", "Close"]
    tiny = pd.DataFrame({"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5]})
    tiny_out = analyzer.identify_candlestick_patterns(tiny.copy())
    assert list(tiny_out.columns) == ["Open", "High", "Low", "Close"]


# --------------------------------------------------------------------------- #
# support_resistance_level
# --------------------------------------------------------------------------- #
def test_support_resistance_level_snapshot(
    analyzer: StockTechnicalAnalyzer, ohlc: pd.DataFrame, snapshot: Snapshot
) -> None:
    snapshot.check("support_resistance_level", analyzer.support_resistance_level(ohlc))


def test_support_resistance_level_known_values(analyzer: StockTechnicalAnalyzer) -> None:
    df = pd.DataFrame({"High": [0.0, 110.0], "Low": [0.0, 90.0], "Close": [0.0, 100.0]})
    result = analyzer.support_resistance_level(df)
    assert result == (100.0, 110.0, 120.0, 130.0, 90.0, 80.0, 70.0)
    assert all(type(v) is float for v in result)


# --------------------------------------------------------------------------- #
# z_score
# --------------------------------------------------------------------------- #
def test_z_score_snapshot(
    analyzer: StockTechnicalAnalyzer, ohlc: pd.DataFrame, snapshot: Snapshot
) -> None:
    snapshot.check("z_score", analyzer.z_score(ohlc))


def test_z_score_window_and_no_mutation(
    analyzer: StockTechnicalAnalyzer, ohlc: pd.DataFrame, snapshot: Snapshot
) -> None:
    before = ohlc.copy()
    out = analyzer.z_score(ohlc, window=5)
    pd.testing.assert_frame_equal(ohlc, before)
    snapshot.check("z_score_window5", out.iloc[:30])


# --------------------------------------------------------------------------- #
# Direction helpers
# --------------------------------------------------------------------------- #
NAN = float("nan")


@pytest.mark.parametrize(
    ("close", "upper", "middle", "lower", "expected"),
    [
        (10, NAN, 5, 1, "Neutral"),
        (10, 9, NAN, 1, "Neutral"),
        (10, 9, 5, NAN, "Neutral"),
        (10, 9, 5, 1, "Strong Bullish"),
        (9, 9, 5, 1, "Strong Bullish"),
        (6, 9, 5, 1, "Bullish"),
        (5, 9, 5, 1, "Bearish"),  # equal to middle -> bearish branch
        (2, 9, 5, 1, "Bearish"),
        (1, 9, 5, 1, "Strong Bearish"),
        (0, 9, 5, 1, "Strong Bearish"),
        (NAN, 9, 5, 1, "Bearish"),  # NaN close compares False
    ],
)
def test_bb_direction(
    analyzer: StockTechnicalAnalyzer,
    close: float,
    upper: float,
    middle: float,
    lower: float,
    expected: str,
) -> None:
    row = pd.Series({"Close": close, "bb_upper": upper, "bb_middle": middle, "bb_lower": lower})
    assert analyzer.bb_direction(row) == expected


@pytest.mark.parametrize(
    ("k", "d", "expected"),
    [
        (NAN, 50, "Neutral"),
        (50, NAN, "Neutral"),
        (90, 85, "Overbought Bullish"),
        (80, 70, "Bullish"),  # strictly > 80
        (60, 50, "Bullish"),
        (50, 50, "Bearish"),  # equal -> bearish branch
        (40, 50, "Bearish"),
        (20, 30, "Bearish"),  # strictly < 20
        (10, 30, "Oversold Bearish"),
    ],
)
def test_stoch_direction(
    analyzer: StockTechnicalAnalyzer, k: float, d: float, expected: str
) -> None:
    assert analyzer.stoch_direction(pd.Series({"Stoch_k": k, "stoch_d": d})) == expected


@pytest.mark.parametrize(
    ("val", "expected"),
    [
        (NAN, "Neutral"),
        (None, "Neutral"),
        (np.float64("nan"), "Neutral"),
        (25.0, "Weak Trend"),
        (25.0001, "Strong Trend"),
        (10, "Weak Trend"),
        (40, "Strong Trend"),
    ],
)
def test_adx_direction(analyzer: StockTechnicalAnalyzer, val: float | None, expected: str) -> None:
    assert analyzer.adx_direction(val) == expected


def test_atr_direction_first_row_is_decreasing(with_indicators: pd.DataFrame) -> None:
    # diff() of the first row is NaN and ``NaN > 0`` is False.
    assert with_indicators["ATR_Direction"].iloc[0] == "Decreasing"


# --------------------------------------------------------------------------- #
# Multi-ticker pipeline (get_latest_candlestick_patterns / main)
# --------------------------------------------------------------------------- #
TICKERS = ["AAA", "ZZZ", "SHORT", "BBB", "NOSIG", "BOOM"]


def test_get_latest_candlestick_patterns_snapshot(
    analyzer: StockTechnicalAnalyzer, fake_yf: FakeYF, snapshot: Snapshot
) -> None:
    fake_yf.errors["BOOM.NS"] = RuntimeError("network down")
    out = analyzer.get_latest_candlestick_patterns(TICKERS)
    snapshot.check("get_latest_candlestick_patterns", out)


def test_get_latest_candlestick_patterns_period_override(
    analyzer: StockTechnicalAnalyzer, fake_yf: FakeYF
) -> None:
    analyzer.get_latest_candlestick_patterns(["AAA"], periods="1y", interval="1wk")
    assert fake_yf.calls[-1][1]["period"] == "1y"
    assert fake_yf.calls[-1][1]["interval"] == "1wk"


def test_get_latest_candlestick_patterns_all_fail_returns_none(
    analyzer: StockTechnicalAnalyzer, fake_yf: FakeYF
) -> None:
    assert analyzer.get_latest_candlestick_patterns(["ZZZ", "SHORT"]) is None
    assert analyzer.get_latest_candlestick_patterns([]) is None


def test_get_latest_candlestick_patterns_no_signal_returns_pattern_rows(
    analyzer: StockTechnicalAnalyzer, fake_yf: FakeYF, snapshot: Snapshot
) -> None:
    out = analyzer.get_latest_candlestick_patterns(["NOSIG"])
    snapshot.check("get_latest_candlestick_patterns_nosignal", out)


def test_get_latest_candlestick_patterns_missing_columns(
    analyzer: StockTechnicalAnalyzer, fake_yf: FakeYF
) -> None:
    frame = to_yf_frame(load_raw_ohlcv(), "NOVOL.NS").drop(columns="Volume", level=0)
    fake_yf.register("NOVOL.NS", frame)
    assert analyzer.get_latest_candlestick_patterns(["NOVOL"]) is None


def test_get_latest_candlestick_patterns_flat_columns_ok(
    analyzer: StockTechnicalAnalyzer, fake_yf: FakeYF, snapshot: Snapshot
) -> None:
    # Unlike fetch_ohlc, this path tolerates single-level columns.
    fake_yf.register("FLAT.NS", load_raw_ohlcv())
    out = analyzer.get_latest_candlestick_patterns(["FLAT"])
    snapshot.check("get_latest_candlestick_patterns_flat", out)


def test_main_snapshot(
    analyzer: StockTechnicalAnalyzer, fake_yf: FakeYF, snapshot: Snapshot
) -> None:
    fake_yf.errors["BOOM.NS"] = RuntimeError("network down")
    snapshot.check("main", analyzer.main(TICKERS))


def test_main_no_signal(
    analyzer: StockTechnicalAnalyzer, fake_yf: FakeYF, snapshot: Snapshot
) -> None:
    snapshot.check("main_nosignal", analyzer.main(["NOSIG"]))


def test_main_all_fail_returns_none(analyzer: StockTechnicalAnalyzer, fake_yf: FakeYF) -> None:
    assert analyzer.main(["ZZZ"]) is None


# --------------------------------------------------------------------------- #
# Prompt building
# --------------------------------------------------------------------------- #
@pytest.fixture
def main_df(analyzer: StockTechnicalAnalyzer, fake_yf: FakeYF) -> pd.DataFrame:
    df = analyzer.main(["AAA", "BBB"])
    assert df is not None
    return df


def test_get_tech_data_for_ticker_snapshot(
    analyzer: StockTechnicalAnalyzer, main_df: pd.DataFrame, snapshot: Snapshot
) -> None:
    snapshot.check("get_tech_data_for_ticker", analyzer.get_tech_data_for_ticker(main_df, "AAA"))


def test_get_tech_data_for_ticker_takes_last_row(analyzer: StockTechnicalAnalyzer) -> None:
    df = pd.DataFrame({"Ticker": ["A", "B", "A"], "x": [1, 2, 3]})
    assert analyzer.get_tech_data_for_ticker(df, "A") == {"Ticker": "A", "x": 3}


def test_get_tech_data_for_ticker_unknown_raises(
    analyzer: StockTechnicalAnalyzer, main_df: pd.DataFrame
) -> None:
    with pytest.raises(ValueError, match=r"^No data found for ticker: NOPE$"):
        analyzer.get_tech_data_for_ticker(main_df, "NOPE")


def test_build_prompt_snapshot(
    analyzer: StockTechnicalAnalyzer, main_df: pd.DataFrame, snapshot: Snapshot
) -> None:
    snapshot.check("build_prompt_AAA", analyzer.build_prompt(main_df, "AAA"))


def test_generate_technical_prompt_scoring_snapshot(
    analyzer: StockTechnicalAnalyzer, main_df: pd.DataFrame, snapshot: Snapshot
) -> None:
    data = analyzer.get_tech_data_for_ticker(main_df, "BBB")
    out = analyzer.generate_technical_prompt("BBB", data, mode="scoring")
    snapshot.check("generate_technical_prompt_scoring_BBB", out)


def test_generate_technical_prompt_filters_none_and_unknown_mode(
    analyzer: StockTechnicalAnalyzer, snapshot: Snapshot
) -> None:
    data = {"Close": 10.5, "Pattern": None, "Code": math.nan, "Flag": True}
    simple = analyzer.generate_technical_prompt("XYZ", data)
    assert analyzer.generate_technical_prompt("XYZ", data, mode="anything-else") == simple
    assert "     Pattern:" not in simple
    assert "\nCode: nan\n" in simple
    snapshot.check("generate_technical_prompt_simple_XYZ", simple)
