"""Characterization tests for ``FundamentalAnalyser`` (written against the original code).

``yfinance.Ticker`` and ``requests.get`` are mocked; nothing touches the network.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest
import requests
import yfinance

from conftest import Snapshot
from EdgeQuantAI import FundamentalAnalyser

COLS = [pd.Timestamp("2024-03-31"), pd.Timestamp("2023-03-31")]


def _frame(rows: dict[str, list[float | None]]) -> pd.DataFrame:
    return pd.DataFrame(rows, index=COLS).T


INCOME = _frame({"Net Income": [200.0, 150.0], "Total Revenue": [1000.0, 900.0],
                 "Operating Income": [300.0, 250.0]})  # fmt: skip
BALANCE = _frame({"Total Stockholder Equity": [800.0, 700.0], "Total Assets": [2000.0, 1800.0],
                  "Long Term Debt": [400.0, 300.0], "Short Term Debt": [100.0, None]})  # fmt: skip
CASH = _frame({"Total Cash From Operating Activities": [250.0, 200.0],
               "Capital Expenditures": [50.0, 40.0]})  # fmt: skip
INFO = {"trailingPE": 22.5, "priceToBook": 3.1, "currentRatio": 1.4, "quickRatio": 1.1,
        "totalDebt": 555.0}  # fmt: skip


def _fin(**overrides: Any) -> dict[str, Any]:
    fin: dict[str, Any] = {"income": INCOME, "balance": BALANCE, "cashflow": CASH, "info": INFO,
                           "earnings": None}  # fmt: skip
    fin.update(overrides)
    return fin


@pytest.fixture
def fa() -> FundamentalAnalyser:
    return FundamentalAnalyser()


def test_init_defaults(fa: FundamentalAnalyser) -> None:
    assert fa.fmp_api_key is None
    assert fa.openai_key is None
    assert fa.client is None
    assert fa.exchange_suffix == ".NS"


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [(10, 2, 5.0), (10, 0, None), (10, None, None), (None, 2, None), ("x", 2, None), (0, 5, 0.0)],
)
def test_safe_div(a: Any, b: Any, expected: float | None) -> None:
    assert FundamentalAnalyser.safe_div(a, b) == expected


def test_compute_ratios_snapshot(fa: FundamentalAnalyser, snapshot: Snapshot) -> None:
    snapshot.check("fundamental_compute_ratios", fa.compute_ratios(_fin()))


def test_compute_ratios_empty(fa: FundamentalAnalyser, snapshot: Snapshot) -> None:
    snapshot.check("fundamental_compute_ratios_empty", fa.compute_ratios({}))


def test_compute_ratios_no_capex_and_info_none(fa: FundamentalAnalyser, snapshot: Snapshot) -> None:
    cash = _frame({"Total Cash From Operating Activities": [250.0, 200.0]})
    snapshot.check(
        "fundamental_compute_ratios_nocapex", fa.compute_ratios(_fin(cashflow=cash, info=None))
    )


def test_build_prompt_snapshot(fa: FundamentalAnalyser, snapshot: Snapshot) -> None:
    snapshot.check("fundamental_build_prompt", fa.build_prompt("TCS", fa.compute_ratios(_fin())))


def test_fetch_fmp_ratios_without_key(fa: FundamentalAnalyser) -> None:
    assert fa.fetch_fmp_ratios("TCS") is None


class _Resp:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def json(self) -> Any:
        return self._payload


@pytest.mark.parametrize(
    ("payload", "expected"),
    [([{"r": 1}], [{"r": 1}]), ([], None), ({"error": "x"}, None)],
)
def test_fetch_fmp_ratios_with_key(
    monkeypatch: pytest.MonkeyPatch, payload: Any, expected: Any
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_get(url: str, **kw: Any) -> _Resp:
        calls.append((url, kw))
        return _Resp(payload)

    monkeypatch.setattr(requests, "get", fake_get)
    fa = FundamentalAnalyser(fmp_api_key="KEY")
    assert fa.fetch_fmp_ratios("TCS") == expected
    assert calls == [
        ("https://financialmodelingprep.com/api/v3/ratios/TCS?apikey=KEY", {"timeout": 10})
    ]


def test_fetch_fmp_ratios_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: Any, **_k: Any) -> None:
        raise requests.ConnectionError("down")

    monkeypatch.setattr(requests, "get", boom)
    assert FundamentalAnalyser(fmp_api_key="KEY").fetch_fmp_ratios("TCS") is None


def test_call_llm_without_client(fa: FundamentalAnalyser) -> None:
    assert fa.call_llm("hello") is None


class _FakeTicker:
    instances: list[str] = []

    def __init__(self, symbol: str) -> None:
        _FakeTicker.instances.append(symbol)
        self.financials = INCOME
        self.balance_sheet = BALANCE
        self.cashflow = CASH
        self.info = INFO
        self.earnings = None


def test_fetch_yf_financials_and_analyze(
    monkeypatch: pytest.MonkeyPatch, fa: FundamentalAnalyser, snapshot: Snapshot
) -> None:
    _FakeTicker.instances = []
    monkeypatch.setattr(yfinance, "Ticker", _FakeTicker)
    fin = fa.fetch_yf_financials("TCS")
    assert list(fin) == ["income", "balance", "cashflow", "info", "earnings"]
    assert _FakeTicker.instances == ["TCS.NS"]

    result = fa.analyze("TCS")
    assert list(result) == ["symbol", "metrics", "fmp_ratios", "prompt", "llm_analysis"]
    assert result["symbol"] == "TCS"
    assert result["fmp_ratios"] is None
    assert result["llm_analysis"] is None
    assert result["prompt"] == fa.build_prompt("TCS", result["metrics"])
    snapshot.check("fundamental_analyze_metrics", result["metrics"])
