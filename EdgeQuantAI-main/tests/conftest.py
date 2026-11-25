"""Shared fixtures: offline yfinance mock, OHLCV fixture loaders, golden snapshots.

No test in this suite touches the network. ``yfinance.download`` (and
``yfinance.Ticker`` where needed) are replaced with in-memory fakes that return
frames shaped exactly like yfinance 0.2.5x / 1.x does: a two-level column
``MultiIndex`` named ``("Price", "Ticker")`` and a ``DatetimeIndex`` named
``"Date"`` (``"Datetime"`` for intraday intervals).
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
import yfinance

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = Path(__file__).parent / "golden"
UPDATE_GOLDEN = os.environ.get("UPDATE_GOLDEN") == "1"

# yfinance >= 0.2.48 returns columns in this order.
_YF_PRICE_ORDER = ["Close", "High", "Low", "Open", "Volume"]


# --------------------------------------------------------------------------- #
# OHLCV fixtures
# --------------------------------------------------------------------------- #
def load_raw_ohlcv(rows: int | None = None) -> pd.DataFrame:
    """Return the committed fixture with a ``datetime64[s]`` index named Date."""
    df = pd.read_csv(FIXTURES / "ohlcv.csv")
    df["Date"] = pd.to_datetime(df["Date"]).astype("datetime64[s]")
    df = df.set_index("Date")
    if rows is not None:
        df = df.iloc[:rows]
    return df


def to_yf_frame(raw: pd.DataFrame, symbol: str, index_name: str = "Date") -> pd.DataFrame:
    """Shape a flat OHLCV frame the way ``yfinance.download`` returns it."""
    out = raw[_YF_PRICE_ORDER].copy()
    out.columns = pd.MultiIndex.from_product([_YF_PRICE_ORDER, [symbol]], names=["Price", "Ticker"])
    out.index.name = index_name
    return out


def empty_yf_frame(symbol: str) -> pd.DataFrame:
    """What yfinance returns for an unknown/delisted symbol."""
    cols = ["Adj Close", *_YF_PRICE_ORDER]
    return pd.DataFrame(
        columns=pd.MultiIndex.from_product([cols, [symbol]], names=["Price", "Ticker"]),
        index=pd.DatetimeIndex([], name="Date"),
    )


@dataclass
class FakeYF:
    """Registry-backed stand-in for ``yfinance.download``."""

    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    errors: dict[str, Exception] = field(default_factory=dict)
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)

    def register(self, symbol: str, frame: pd.DataFrame) -> None:
        self.frames[symbol] = frame

    def download(self, *args: Any, **kwargs: Any) -> pd.DataFrame:
        self.calls.append((args, kwargs))
        symbol = args[0] if args else kwargs["tickers"]
        if symbol in self.errors:
            raise self.errors[symbol]
        if symbol in self.frames:
            return self.frames[symbol].copy()
        return empty_yf_frame(symbol)


@pytest.fixture
def raw_ohlcv() -> pd.DataFrame:
    return load_raw_ohlcv()


@pytest.fixture
def fake_yf(monkeypatch: pytest.MonkeyPatch) -> FakeYF:
    fake = FakeYF()
    fake.register("AAA.NS", to_yf_frame(load_raw_ohlcv(), "AAA.NS"))
    fake.register("BBB.NS", to_yf_frame(load_raw_ohlcv(250), "BBB.NS"))
    fake.register("NOSIG.NS", to_yf_frame(load_raw_ohlcv(202), "NOSIG.NS"))
    fake.register("SHORT.NS", to_yf_frame(load_raw_ohlcv(150), "SHORT.NS"))
    monkeypatch.setattr(yfinance, "download", fake.download)

    def _no_network(*_a: Any, **_k: Any) -> None:
        raise AssertionError("tests must not touch the network")

    monkeypatch.setattr(yfinance, "Ticker", _no_network)
    return fake


# --------------------------------------------------------------------------- #
# Golden snapshots
# --------------------------------------------------------------------------- #
# Snapshots are stored as JSON. Floats are written with ``repr`` (Python's json
# module round-trips IEEE-754 doubles exactly), so value comparisons are exact.
#
# Snapshots must hold on every supported pandas (CI runs pandas 2.x on 3.10 and
# 3.x on newer Pythons), so three version-dependent details are normalised:
#   * string-like dtypes: pandas 3 infers ``str`` where pandas 2 uses ``object``;
#   * datetime64 resolution: pandas 2 coerces to ``[ns]``, pandas 3 keeps ``[s]``/``[us]``
#     (the timestamp *values* are still compared exactly);
#   * scalar type names use the top-level package (``pandas.Timestamp`` lives in
#     ``pandas._libs...`` on pandas 2).
# ``tests/test_differential.py`` checks exact dtypes and scalar types against the
# frozen original implementation in the same interpreter, without normalisation.
_STRINGLIKE = {"object", "str", "string"}


def _type_name(value: Any) -> str:
    t = type(value)
    return f"{t.__module__.split('.')[0]}.{t.__qualname__}"


def _scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return {"timestamp": value.isoformat()}
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        f = float(value)
        return "NaN" if math.isnan(f) else f
    if isinstance(value, str):
        return value
    raise TypeError(f"unsupported scalar in snapshot: {value!r} ({_type_name(value)})")


def _dtype(dtype: Any) -> str:
    name = str(dtype)
    if name in _STRINGLIKE:
        return "<string-like>"
    if name.startswith("datetime64["):
        return "datetime64[<unit>]"
    return name


def serialise(obj: Any) -> Any:
    """Convert a supported result into a JSON-able, order-preserving structure."""
    if obj is None:
        return {"kind": "none"}
    if isinstance(obj, pd.DataFrame):
        return {
            "kind": "frame",
            "shape": list(obj.shape),
            "columns": [str(c) for c in obj.columns],
            "dtypes": [_dtype(d) for d in obj.dtypes],
            "index_name": obj.index.name,
            "index_dtype": _dtype(obj.index.dtype),
            "index": [_scalar(v) for v in obj.index],
            "data": {str(c): [_scalar(v) for v in obj[c].tolist()] for c in obj.columns},
        }
    if isinstance(obj, dict):
        return {
            "kind": "dict",
            "items": [[k, _type_name(v), _scalar(v)] for k, v in obj.items()],
        }
    if isinstance(obj, tuple):
        return {"kind": "tuple", "items": [[_type_name(v), _scalar(v)] for v in obj]}
    raise TypeError(f"unsupported snapshot object: {type(obj)!r}")


class Snapshot:
    """``snapshot.check(name, obj)`` compares ``obj`` with ``tests/golden/<name>``."""

    def check(self, name: str, obj: Any) -> None:
        if isinstance(obj, str):
            path = GOLDEN / f"{name}.txt"
            actual = obj
        else:
            path = GOLDEN / f"{name}.json"
            actual = json.dumps(serialise(obj), indent=1, sort_keys=False) + "\n"

        if UPDATE_GOLDEN:
            path.write_text(actual, encoding="utf-8")
            return
        assert path.exists(), f"missing golden file {path}; run with UPDATE_GOLDEN=1"
        expected = path.read_text(encoding="utf-8")
        assert actual == expected, f"output differs from golden snapshot {path.name}"


@pytest.fixture
def snapshot() -> Snapshot:
    return Snapshot()


# --------------------------------------------------------------------------- #
# Small builders for branch-level tests
# --------------------------------------------------------------------------- #
def signal_frame(**overrides: list[Any]) -> pd.DataFrame:
    """Two-row frame with every column ``generate_signal`` reads.

    Defaults produce *no* signal (volume below VMA20, RSI < 60, no crossovers).
    """
    base: dict[str, list[Any]] = {
        "Open": [100.0, 101.0],
        "High": [102.0, 103.0],
        "Low": [99.0, 100.0],
        "Close": [101.0, 102.0],
        "Volume": [1000.0, 1000.0],
        "VMA20": [2000.0, 2000.0],
        "EMA5": [100.0, 100.5],
        "EMA9": [99.0, 99.5],
        "EMA26": [98.0, 98.5],
        "SMA50": [97.0, 97.0],
        "SMA200": [95.0, 95.0],
        "RSI": [50.0, 50.0],
        "MACD": [1.0, 1.0],
        "Signal": [0.5, 0.5],
        "Change": [0.0, 0.01],
        "Z_score": [0.1, 0.2],
        "BB_Direction": ["Bullish", "Bullish"],
        "Stoch_Direction": ["Bullish", "Bullish"],
        "ATR_Direction": ["Increasing", "Increasing"],
        "ADX_Direction": ["Weak Trend", "Weak Trend"],
        "Ticker": ["X", "X"],
    }
    base.update(overrides)
    idx = pd.DatetimeIndex(["2024-01-01", "2024-01-02"], name="Date")
    return pd.DataFrame(base, index=idx)


@pytest.fixture
def make_signal_frame() -> Callable[..., pd.DataFrame]:
    return signal_frame
