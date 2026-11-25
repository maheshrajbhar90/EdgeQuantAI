"""Unit tests for the refactored internal modules and package plumbing."""

from __future__ import annotations

import ast
import builtins
import importlib
import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

import stock_technical_analyzer as sta
from conftest import FakeYF
from stock_technical_analyzer import constants as c
from stock_technical_analyzer import data, levels, patterns, prompts, signals

LEGACY_SOURCE = Path(__file__).parent / "legacy" / "EdgeQuantAI.py"


def test_public_exports() -> None:
    assert sta.__all__ == ["FundamentalAnalyser", "StockTechnicalAnalyzer", "__version__"]
    assert sta.__version__ == "0.1.0"


def test_compat_shims_resolve_to_same_objects() -> None:
    import EdgeQuantAI
    import EdgeQuantAI.EdgeQuantAI as legacy_mod
    import EdgeQuantAI.fundamental_analyzer as legacy_fa
    import stock_analyzer

    for mod in (EdgeQuantAI, stock_analyzer, legacy_mod):
        assert mod.StockTechnicalAnalyzer is sta.StockTechnicalAnalyzer
    assert legacy_fa.FundamentalAnalyser is sta.FundamentalAnalyser
    assert legacy_fa.FMP_BASE == "https://financialmodelingprep.com/api/v3"


def _legacy_pattern_dict_order() -> list[tuple[str, str]]:
    """Read the original ``pattern_functions`` dict literal, in dict-iteration order."""
    tree = ast.parse(LEGACY_SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and getattr(node.targets[0], "id", None) == "pattern_functions"
        ):
            assert isinstance(node.value, ast.Dict)
            ordered: dict[str, str] = {}
            for k, v in zip(node.value.keys, node.value.values, strict=True):
                assert isinstance(k, ast.Constant) and isinstance(v, ast.Attribute)
                ordered[k.value] = v.attr  # duplicate key keeps first position
            return list(ordered.items())
    raise AssertionError("pattern_functions not found")


def test_candlestick_pattern_order_matches_original_dict() -> None:
    assert list(c.CANDLESTICK_PATTERNS) == _legacy_pattern_dict_order()
    assert len(c.CANDLESTICK_PATTERNS) == 61
    assert len({label for label, _ in c.CANDLESTICK_PATTERNS}) == 61


def test_summary_columns_match_original() -> None:
    assert list(c.SUMMARY_COLUMNS) == [
        "Date", "Ticker", "Close", "Change%", "Volume", "VMA20", "Z_score", "Volume_Spike",
        "EMA5", "EMA9", "EMA26", "SMA50", "SMA200", "EMA_Crossover", "Pivot_point",
        "Resistance_1", "Resistance_2", "Resistance_3", "Support_1", "Support_2", "Support_3",
        "RSI_Value", "RSI>=60", "MACD_Value", "Signal_Value", "MACD_Crossover",
        "BB_Direction", "Stoch_Direction", "ATR_Direction", "ADX_Direction", "Pattern", "Code",
    ]  # fmt: skip


def test_classic_pivots_unrounded() -> None:
    assert levels.classic_pivots(110.0, 90.0, 100.0) == (
        100.0,
        110.0,
        120.0,
        130.0,
        90.0,
        80.0,
        70.0,
    )


@pytest.mark.parametrize(
    ("delta", "expected"),
    [(0.1, "Increasing"), (0.0, "Decreasing"), (-1.0, "Decreasing"), (float("nan"), "Decreasing")],
)
def test_atr_direction(delta: float, expected: str) -> None:
    assert signals.atr_direction(delta) == expected


def test_format_metrics_skips_none_keeps_nan() -> None:
    out = prompts.format_metrics({"a": 1, "b": None, "c": float("nan")})
    assert out == "     a: 1\n     c: nan"


def test_prompt_templates_have_only_expected_placeholders() -> None:
    for template in (prompts.SIMPLE_TEMPLATE, prompts.SCORING_TEMPLATE):
        assert template.format(ticker="T", metrics_text="M").count("**T**") == 1


def test_subclass_overrides_are_honoured(fake_yf: FakeYF) -> None:
    """Orchestration must route through ``self`` so overriding a step works."""

    class Custom(sta.StockTechnicalAnalyzer):
        def adx_direction(self, val: Any) -> str:
            return "X"

        def support_resistance_level(self, ohlc_day: pd.DataFrame) -> tuple[float, ...]:
            return (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0)

    a = Custom()
    df = a.fetch_ohlc("AAA")
    assert df is not None
    enriched = a.add_indicators(df)
    assert enriched is not None
    assert set(enriched["ADX_Direction"]) == {"X"}
    signal = a.generate_signal(enriched)
    assert signal is not None and signal["Pivot_point"] == 1.0


def test_pipeline_logs_instead_of_printing(
    fake_yf: FakeYF, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_yf.errors["BOOM.NS"] = RuntimeError("network down")
    with caplog.at_level(logging.DEBUG, logger="stock_technical_analyzer"):
        sta.StockTechnicalAnalyzer().main(["ZZZ", "SHORT", "BOOM"])
    messages = [r.getMessage() for r in caplog.records]
    assert "[SKIP] No data for ZZZ" in messages
    assert "[SKIP] Indicators failed for SHORT" in messages
    assert "[ERROR] BOOM: network down" in messages
    assert "[FINAL] No valid result data." in messages
    assert capsys.readouterr().out == ""


def test_prompt_is_logged_at_debug(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="stock_technical_analyzer.prompts"):
        prompt = sta.StockTechnicalAnalyzer().generate_technical_prompt("T", {"x": 1})
    assert any(prompt in r.getMessage() for r in caplog.records)


def test_library_configures_no_handlers() -> None:
    modules = ("analyzer", "data", "indicators", "patterns", "prompts", "signals", "fundamental")
    for name in ("stock_technical_analyzer", *(f"stock_technical_analyzer.{m}" for m in modules)):
        assert logging.getLogger(name).handlers == []


def test_prepare_downloaded_ohlc_none_and_missing_date(caplog: pytest.LogCaptureFixture) -> None:
    assert data.prepare_downloaded_ohlc(None, "X") is None
    no_date = pd.DataFrame({"Open": [1.0]}, index=pd.Index([0], name="when"))
    with caplog.at_level(logging.ERROR):
        assert data.prepare_downloaded_ohlc(no_date, "X") is None
    assert "Date column missing for X" in caplog.text


def test_prepare_downloaded_ohlc_unparseable_dates(caplog: pytest.LogCaptureFixture) -> None:
    bad = pd.DataFrame({"Open": [1.0]}, index=pd.Index(["not a date"], name="Date"))
    with caplog.at_level(logging.ERROR):
        assert data.prepare_downloaded_ohlc(bad, "X") is None
    assert "Date conversion failed for X" in caplog.text


def test_pattern_functions_resolved_from_talib() -> None:
    from stock_technical_analyzer._talib import talib

    assert patterns.PATTERN_FUNCTIONS[0] == ("3_inside", talib.CDL3INSIDE)


def test_missing_talib_raises_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "talib":
            raise ImportError("No module named 'talib'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.delitem(sys.modules, "stock_technical_analyzer._talib")
    with pytest.raises(ModuleNotFoundError, match="pip install") as info:
        importlib.import_module("stock_technical_analyzer._talib")
    assert info.value.name == "talib"
    assert "brew install ta-lib" in str(info.value)


def test_fmp_failure_log_does_not_leak_api_key(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import requests

    def boom(url: str, **_k: Any) -> None:
        raise requests.ConnectionError(f"Max retries exceeded with url: {url}")

    monkeypatch.setattr(requests, "get", boom)
    with caplog.at_level(logging.DEBUG):
        assert sta.FundamentalAnalyser(fmp_api_key="SECRET123").fetch_fmp_ratios("TCS") is None
    assert "SECRET123" not in caplog.text
    assert "ConnectionError" in caplog.text
