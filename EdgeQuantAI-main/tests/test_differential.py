"""Differential tests: refactored package vs. the frozen original implementation.

``tests/legacy/`` holds byte-for-byte copies of the pre-refactor modules. Each
test feeds identical inputs to both implementations and asserts *exact*
equality: values, dtypes, column order, index, scalar types, and the type and
message of raised exceptions. Unlike the JSON golden snapshots this needs no
cross-version normalisation, because both run in the same interpreter.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pandas as pd
import pytest
import requests
import yfinance

import EdgeQuantAI as current
from conftest import FakeYF, load_raw_ohlcv, to_yf_frame

LEGACY_DIR = Path(__file__).parent / "legacy"


def divergence(issue: str, why: str) -> pytest.MarkDecorator:
    """Mark a case where the package *intentionally* differs from tests/legacy/.

    ``strict=True`` makes the test fail if old and new ever agree again, so a
    stale marker can't hide anything. The new behaviour itself is asserted in
    tests/test_known_issue_fixes.py.
    """
    return pytest.mark.xfail(
        strict=True, raises=AssertionError, reason=f"KNOWN_ISSUES {issue}: {why}"
    )


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def legacy() -> Iterator[ModuleType]:
    """Import the frozen original without leaking its sys.path / sys.modules hacks."""
    saved_path = list(sys.path)
    saved_fa = sys.modules.get("fundamental_analyzer")
    sys.modules["fundamental_analyzer"] = _load(
        "fundamental_analyzer", LEGACY_DIR / "fundamental_analyzer.py"
    )
    try:
        yield _load("legacy_edgequantai", LEGACY_DIR / "EdgeQuantAI.py")
    finally:
        sys.path[:] = saved_path
        if saved_fa is None:
            sys.modules.pop("fundamental_analyzer", None)
        else:
            sys.modules["fundamental_analyzer"] = saved_fa


@pytest.fixture
def pair(legacy: ModuleType, fake_yf: FakeYF) -> tuple[Any, Any]:
    return legacy.StockTechnicalAnalyzer(), current.StockTechnicalAnalyzer()


# --------------------------------------------------------------------------- #
# Exact comparison helpers
# --------------------------------------------------------------------------- #
def _same_scalar(a: Any, b: Any) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, float) and math.isnan(a):
        return math.isnan(b)
    try:
        return bool(pd.isna(a) and pd.isna(b)) or bool(a == b)
    except (TypeError, ValueError):
        return a is b


def assert_same(old: Any, new: Any) -> None:
    assert type(old) is type(new), (type(old), type(new))
    if isinstance(old, pd.DataFrame):
        pd.testing.assert_frame_equal(old, new, check_exact=True, check_freq=True, check_flags=True)
        assert list(old.columns) == list(new.columns)
    elif isinstance(old, pd.Series):
        pd.testing.assert_series_equal(old, new, check_exact=True)
    elif isinstance(old, dict):
        assert list(old) == list(new)
        for k in old:
            assert _same_scalar(old[k], new[k]), (k, old[k], new[k])
    elif isinstance(old, tuple):
        assert len(old) == len(new)
        for a, b in zip(old, new, strict=True):
            assert _same_scalar(a, b), (a, b)
    else:
        assert _same_scalar(old, new), (old, new)


def run_both(old: Callable[[], Any], new: Callable[[], Any]) -> None:
    """Call both; require the same result, or the same exception type and message."""
    try:
        expected = old()
    except Exception as exc:  # noqa: BLE001 - mirroring arbitrary original behaviour
        original_error: Exception | None = exc
    else:
        original_error = None
    if original_error is None:
        assert_same(expected, new())
        return
    with pytest.raises(type(original_error)) as info:
        new()
    assert str(info.value) == str(original_error)


# --------------------------------------------------------------------------- #
# StockTechnicalAnalyzer
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "ticker",
    [
        "AAA",
        "BBB",
        "ZZZ",
        pytest.param(
            "AAA.NS", marks=divergence("A1", "legacy requests AAA.NS.NS and returns None")
        ),
        "FLAT",
        "INTRA",
    ],
)
def test_fetch_ohlc(pair: tuple[Any, Any], fake_yf: FakeYF, ticker: str) -> None:
    fake_yf.register("FLAT.NS", load_raw_ohlcv(5))
    intra = load_raw_ohlcv(5)
    intra.index = pd.date_range("2024-03-01 09:15", periods=5, freq="15min", tz="Asia/Kolkata")
    fake_yf.register("INTRA.NS", to_yf_frame(intra, "INTRA.NS", index_name="Datetime"))
    old, new = pair
    run_both(lambda: old.fetch_ohlc(ticker), lambda: new.fetch_ohlc(ticker))


@pytest.fixture
def ohlc(pair: tuple[Any, Any]) -> pd.DataFrame:
    df = pair[0].fetch_ohlc("AAA")
    assert df is not None
    return df


@pytest.mark.parametrize("rows", [0, 1, 150, 199, 200, 201, 320])
def test_add_indicators(pair: tuple[Any, Any], ohlc: pd.DataFrame, rows: int) -> None:
    old, new = pair
    src = ohlc.iloc[:rows]
    run_both(lambda: old.add_indicators(src.copy()), lambda: new.add_indicators(src.copy()))


def test_add_indicators_empty_frame(pair: tuple[Any, Any]) -> None:
    old, new = pair
    run_both(lambda: old.add_indicators(pd.DataFrame()), lambda: new.add_indicators(pd.DataFrame()))


@pytest.fixture
def indicators(pair: tuple[Any, Any], ohlc: pd.DataFrame) -> pd.DataFrame:
    df = pair[0].add_indicators(ohlc)
    assert df is not None
    return df


def test_generate_signal_every_slice(pair: tuple[Any, Any], indicators: pd.DataFrame) -> None:
    old, new = pair
    for n in range(len(indicators) + 1):
        src = indicators.iloc[:n]
        run_both(
            lambda s=src: old.generate_signal(s.copy()), lambda s=src: new.generate_signal(s.copy())
        )
    run_both(lambda: old.generate_signal(None), lambda: new.generate_signal(None))


@pytest.mark.parametrize(
    "source",
    [
        "indicators",
        "ohlc",
        pytest.param(
            "ohlc_3_rows",
            marks=divergence("B1", "no pattern matches: legacy omits Pattern/Code, new adds NaN"),
        ),
    ],
)
def test_identify_candlestick_patterns(
    pair: tuple[Any, Any], indicators: pd.DataFrame, ohlc: pd.DataFrame, source: str
) -> None:
    old, new = pair
    src = {"indicators": indicators, "ohlc": ohlc, "ohlc_3_rows": ohlc.iloc[:3]}[source]
    a, b = src.copy(), src.copy()
    ra, rb = old.identify_candlestick_patterns(a), new.identify_candlestick_patterns(b)
    assert ra is a and rb is b
    assert_same(ra, rb)


@pytest.mark.parametrize("rows", [1, 2, 320])
def test_support_resistance_level(pair: tuple[Any, Any], ohlc: pd.DataFrame, rows: int) -> None:
    old, new = pair
    src = ohlc.iloc[:rows]
    run_both(lambda: old.support_resistance_level(src), lambda: new.support_resistance_level(src))


@pytest.mark.parametrize("window", [2, 5, 20, 50])
def test_z_score(pair: tuple[Any, Any], ohlc: pd.DataFrame, window: int) -> None:
    old, new = pair
    run_both(lambda: old.z_score(ohlc, window=window), lambda: new.z_score(ohlc, window=window))
    run_both(lambda: old.z_score(ohlc, window), lambda: new.z_score(ohlc, window))


def test_direction_helpers_every_row(pair: tuple[Any, Any], indicators: pd.DataFrame) -> None:
    old, new = pair
    for _, row in indicators.iterrows():
        assert old.bb_direction(row) == new.bb_direction(row)
        assert old.stoch_direction(row) == new.stoch_direction(row)
        assert old.adx_direction(row["ADX"]) == new.adx_direction(row["ADX"])
    for v in (None, float("nan"), 25, 25.0, 26, -1):
        assert old.adx_direction(v) == new.adx_direction(v)


TICKER_SETS = [
    ["AAA", "ZZZ", "SHORT", "BBB", "NOSIG", "BOOM"],
    ["NOSIG"],
    ["ZZZ"],
    [],
    ["FLAT", "NOVOL"],
]


@pytest.mark.parametrize("tickers", TICKER_SETS)
def test_pipeline(pair: tuple[Any, Any], fake_yf: FakeYF, tickers: list[str]) -> None:
    fake_yf.errors["BOOM.NS"] = RuntimeError("network down")
    fake_yf.register("FLAT.NS", load_raw_ohlcv())
    fake_yf.register(
        "NOVOL.NS", to_yf_frame(load_raw_ohlcv(), "NOVOL.NS").drop(columns="Volume", level=0)
    )
    old, new = pair
    run_both(
        lambda: old.get_latest_candlestick_patterns(tickers),
        lambda: new.get_latest_candlestick_patterns(tickers),
    )
    run_both(lambda: old.main(tickers), lambda: new.main(tickers))


@pytest.mark.parametrize("mode", ["simple", "scoring", "other"])
@pytest.mark.parametrize("ticker", ["AAA", "BBB", "NOPE"])
def test_prompts(pair: tuple[Any, Any], mode: str, ticker: str) -> None:
    old, new = pair
    df = old.main(["AAA", "BBB"])
    run_both(
        lambda: old.get_tech_data_for_ticker(df, ticker),
        lambda: new.get_tech_data_for_ticker(df, ticker),
    )
    run_both(lambda: old.build_prompt(df, ticker), lambda: new.build_prompt(df, ticker))
    data = {"Close": 1.5, "Pattern": None, "Code": float("nan"), "Flag": True, "Note": ""}
    run_both(
        lambda: old.generate_technical_prompt(ticker, data, mode=mode),
        lambda: new.generate_technical_prompt(ticker, data, mode=mode),
    )
    run_both(
        lambda: old.generate_technical_prompt(ticker, data, mode),
        lambda: new.generate_technical_prompt(ticker, data, mode),
    )


def test_init_attributes(legacy: ModuleType) -> None:
    for kwargs in (
        {},
        {"period": "1y", "interval": "1wk", "exchange_suffix": "", "fmp_api_key": "k"},
    ):
        old = legacy.StockTechnicalAnalyzer(**kwargs)
        new = current.StockTechnicalAnalyzer(**kwargs)
        for attr in ("period", "interval", "exchange_suffix"):
            assert getattr(old, attr) == getattr(new, attr)
        for attr in ("fmp_api_key", "openai_key", "client", "exchange_suffix"):
            assert getattr(old.fundamental, attr) == getattr(new.fundamental, attr)


# --------------------------------------------------------------------------- #
# FundamentalAnalyser
# --------------------------------------------------------------------------- #
def _fin() -> dict[str, Any]:
    cols = [pd.Timestamp("2024-03-31"), pd.Timestamp("2023-03-31")]
    frame = lambda rows: pd.DataFrame(rows, index=cols).T  # noqa: E731
    return {
        "income": frame({"Net Income": [200.0, 1], "Total Revenue": [1000.0, 1],
                         "Operating Income": [300.0, 1]}),
        "balance": frame({"Total Stockholder Equity": [800.0, 1], "Total Assets": [2000.0, 1]}),
        "cashflow": frame({"Total Cash From Operating Activities": [250.0, 1],
                           "Capital Expenditures": [50.0, 1]}),
        "info": {"trailingPE": 22.5, "totalDebt": 555.0},
    }  # fmt: skip


@pytest.mark.parametrize("fin", [_fin(), {}, {**_fin(), "info": None}])
def test_fundamental_compute_and_prompt(legacy: ModuleType, fin: dict[str, Any]) -> None:
    fa_old = sys.modules["fundamental_analyzer"].FundamentalAnalyser()
    fa_new = current.FundamentalAnalyser()
    run_both(lambda: fa_old.compute_ratios(fin), lambda: fa_new.compute_ratios(fin))
    m = fa_old.compute_ratios(fin)
    run_both(lambda: fa_old.build_prompt("TCS", m), lambda: fa_new.build_prompt("TCS", m))


@pytest.mark.parametrize(("a", "b"), [(1, 2), (1, 0), (None, 1), (1, None), ("a", 2), (4.0, 2)])
def test_fundamental_safe_div(legacy: ModuleType, a: Any, b: Any) -> None:
    old = sys.modules["fundamental_analyzer"].FundamentalAnalyser.safe_div
    assert_same(old(a, b), current.FundamentalAnalyser.safe_div(a, b))


def test_fundamental_fmp_and_llm(legacy: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    class Resp:
        def json(self) -> Any:
            return [{"x": 1}]

    monkeypatch.setattr(requests, "get", lambda *a, **k: Resp())
    old_cls = sys.modules["fundamental_analyzer"].FundamentalAnalyser
    for key in (None, "KEY"):
        old, new = old_cls(fmp_api_key=key), current.FundamentalAnalyser(fmp_api_key=key)
        assert_same(old.fetch_fmp_ratios("TCS"), new.fetch_fmp_ratios("TCS"))
        assert old.call_llm("p") is None and new.call_llm("p") is None


def test_fundamental_analyze(legacy: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    fin = _fin()

    class FakeTicker:
        def __init__(self, symbol: str) -> None:
            self.financials = fin["income"]
            self.balance_sheet = fin["balance"]
            self.cashflow = fin["cashflow"]
            self.info = fin["info"]
            self.earnings = None

    monkeypatch.setattr(yfinance, "Ticker", FakeTicker)
    old = sys.modules["fundamental_analyzer"].FundamentalAnalyser().analyze("TCS", use_llm=True)
    new = current.FundamentalAnalyser().analyze("TCS", use_llm=True)
    assert list(old) == list(new)
    for k in ("symbol", "fmp_ratios", "prompt", "llm_analysis"):
        assert_same(old[k], new[k])
    assert_same(old["metrics"], new["metrics"])


# --------------------------------------------------------------------------- #
# Guard: the differential comparison itself must stay strict
# --------------------------------------------------------------------------- #
# The golden-snapshot serializer (conftest.py) deliberately normalises
# object/str dtypes, datetime64 resolution and scalar module paths so that one
# snapshot works on pandas 2 and 3. These tests make sure ``assert_same`` does
# NOT inherit that leniency, so an exact dtype check always exists.
@pytest.mark.parametrize(
    ("old", "new"),
    [
        (pd.DataFrame({"a": ["x"]}, dtype=object), pd.DataFrame({"a": ["x"]}, dtype="string")),
        (
            pd.DataFrame({"t": pd.to_datetime(["2024-01-01"]).astype("datetime64[s]")}),
            pd.DataFrame({"t": pd.to_datetime(["2024-01-01"]).astype("datetime64[ns]")}),
        ),
        (pd.DataFrame({"v": [1]}, dtype="int64"), pd.DataFrame({"v": [1]}, dtype="int32")),
        (pd.DataFrame({"a": [1], "b": [2]}), pd.DataFrame({"b": [2], "a": [1]})),
    ],
    ids=["object-vs-string", "datetime-s-vs-ns", "int64-vs-int32", "column-order"],
)
def test_assert_same_is_strict_on_frames(old: pd.DataFrame, new: pd.DataFrame) -> None:
    with pytest.raises(AssertionError):
        assert_same(old, new)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ({"x": pd.Timestamp("2024-01-01")}, {"x": "2024-01-01"}),
        ({"x": 1.0}, {"x": 1}),
        ({"a": 1, "b": 2}, {"b": 2, "a": 1}),
        ((1.0, 2.0), (1.0, 2)),
    ],
    ids=["timestamp-vs-str", "float-vs-int", "key-order", "tuple-item-type"],
)
def test_assert_same_is_strict_on_scalars(old: Any, new: Any) -> None:
    with pytest.raises(AssertionError):
        assert_same(old, new)
