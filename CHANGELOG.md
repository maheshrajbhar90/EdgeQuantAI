# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Behaviour changes
Intentional output changes compared with 0.1.0 (and the original 0.0.0.1 code).
Each one is tracked by a regression test in `tests/test_known_issue_fixes.py`
and a strict `divergence(...)` marker or an updated expectation.

- **A1: exchange suffix ([KNOWN_ISSUES A1](KNOWN_ISSUES.md#a1))**
  - *Before:* the suffix was always appended. `fetch_ohlc("TCS.NS")` requested
    `TCS.NS.NS` and returned `None`; `main(["TCS.NS"])` silently skipped the
    ticker; `FundamentalAnalyser.fetch_yf_financials("TCS.NS")` looked up `TCS.NS.NS`.
  - *After:* tickers already ending in `.NS`/`.BO` (any case) are used as given,
    so `"TCS.NS"` → `TCS.NS`, `"tcs.ns"` → `tcs.ns` and `"TCS.BO"` → `TCS.BO`.
    `"TCS"` still becomes `TCS.NS`. The `Ticker` column keeps the spelling you
    passed in.
- **B1: `Pattern`/`Code` columns ([KNOWN_ISSUES B1](KNOWN_ISSUES.md#b1))**
  - *Before:* `identify_candlestick_patterns` left out `Pattern`/`Code` when no
    pattern matched, so `main()` and `get_latest_candlestick_patterns()` raised
    `KeyError: "['Pattern', 'Code'] not in index"` when no ticker matched.
  - *After:* both columns are always present (`Pattern` object, `Code` float64,
    NaN where nothing matched), and the pipeline returns rows instead of raising.
    Output is unchanged whenever at least one pattern matched.
- **F1: debt lookup ([KNOWN_ISSUES F1](KNOWN_ISSUES.md#f1), with [F2a](KNOWN_ISSUES.md#f2a))**
  - *Before:* `compute_ratios` looked up debt in the balance sheet's *columns*,
    always got 0 and fell back to `info["totalDebt"]` (`None` if missing). `roce`
    was based on that value. Example: 5020.5 bn for RELIANCE.NS.
  - *After:* `total_debt` = `Long Term Debt` + short-term debt from the latest
    fiscal-year column. Short-term debt is the first of `Short Term Debt` /
    `Current Debt` present (F2a). `info["totalDebt"]` is still the fallback when
    that sum is 0, so TCS.NS and INFY.NS are unchanged. `roce` changes with it.
    Example: 3744.2 bn for RELIANCE.NS.
  - **Limitation:** F1 alone counted long-term debt only on live yfinance data,
    because current yfinance has no `Short Term Debt` row (2707.5 bn for
    RELIANCE.NS). F2a closes that gap by reading `Current Debt`. Lease
    obligations are still not counted (the balance sheet's `Total Debt` is
    3980.0 bn), and `roe`/`roce` still need the equity label from the open
    [F2](KNOWN_ISSUES.md#f2).

### Fixed
- Tickers that already end with `.NS`/`.BO` (any case) no longer get the
  exchange suffix appended again (`"TCS.NS"` used to request `TCS.NS.NS`), in
  `fetch_ohlc`, the multi-ticker pipeline and `FundamentalAnalyser` (KNOWN_ISSUES A1).
- `identify_candlestick_patterns` always adds `Pattern`/`Code` (NaN when
  nothing matches), so `main()` / `get_latest_candlestick_patterns()` no longer
  raise `KeyError` when no ticker has a candlestick match (KNOWN_ISSUES B1).
- Streamlit app: `main.py` no longer crashes when `config.json` is missing. Keys
  are read from `st.secrets`, then the `HF_TOKEN` / `OPENAI_API_KEY` /
  `FMP_API_KEY` environment variables, then `config.json` if present. The
  OpenAI and FMP keys are now passed to the analyzer (KNOWN_ISSUES G1).
- `config.json` is no longer tracked; use `config.example.json` as a template.
  `.streamlit/secrets.toml` is git-ignored at both levels (KNOWN_ISSUES G2).
- Importing `stock_technical_analyzer` (or `EdgeQuantAI` / `stock_analyzer`) no
  longer calls `warnings.filterwarnings("ignore")`, which silenced every warning
  in the host application. `main()` now suppresses only pandas' "round has no
  effect with datetime" `UserWarning`, locally (KNOWN_ISSUES C1).
- `FundamentalAnalyser.compute_ratios` reads `Long Term Debt` / `Short Term Debt`
  from the balance-sheet rows. It used to look them up as columns, always got 0
  and fell back to `info["totalDebt"]`. This changes `total_debt` and `roce`
  (KNOWN_ISSUES F1).
- Short-term debt is also read from the `Current Debt` row, the label current
  yfinance uses; `Short Term Debt` is still checked first. Without this, F1
  counted only long-term debt on live data (KNOWN_ISSUES F2a).

### Changed
- The project moved from its sub-folder to the repository root
  (`git mv`, history preserved). Run commands, `pip install -e .` and
  `streamlit run main.py` from the root. Streamlit Cloud's main file path is now
  `main.py` (KNOWN_ISSUES G5).
- `main.py` adds `src/` to `sys.path` only when `stock_technical_analyzer` isn't
  importable (new `app_bootstrap.py`), so an installed package is never loaded
  twice.

## [0.1.0] - 2026-11-25

A behaviour-preserving refactor: for the same inputs, every public method returns
the same values, dtypes, column order, dict keys, types and exceptions as
0.0.0.1. Golden tests generated from the 0.0.0.1 code and a differential test
against a frozen copy of it enforce this. Bugs found along the way are listed in
[KNOWN_ISSUES.md](KNOWN_ISSUES.md) and left unfixed.

### Added
- `stock_technical_analyzer` package (src layout) split into `analyzer`, `data`,
  `indicators`, `patterns`, `signals`, `levels`, `prompts`, `fundamental` and
  `constants`.
- Compatibility shims: `from EdgeQuantAI import ...` and
  `from stock_analyzer import ...` keep working.
- Full type hints with a `py.typed` marker; mypy runs in strict mode.
- Google-style docstrings with examples on every public class and method; the
  runnable examples execute as doctests.
- Characterization, differential and unit test suites (offline; mocked
  yfinance, `requests` and OpenAI; synthetic OHLCV fixture), with ≥ 95% branch
  coverage enforced.
- `pyproject.toml` (PEP 621) with compatible dependency ranges and `[dev]` extras.
- ruff (lint and format), mypy, pytest-cov, pre-commit configuration.
- GitHub Actions CI: TA-Lib C library, lint, type-check and tests with coverage
  on Python 3.10, 3.11 and 3.12.
- `examples/quickstart.py`, `LICENSE` (MIT), `CONTRIBUTING.md`, `KNOWN_ISSUES.md`.

### Changed
- Diagnostics use `logging` (`stock_technical_analyzer.*` loggers, no handlers
  configured) instead of `print`. `generate_technical_prompt` now logs the
  prompt at DEBUG instead of printing it. Return values are unchanged.
- A missing TA-Lib raises `ModuleNotFoundError` with platform-specific install
  instructions.
- `FundamentalAnalyser.safe_div` and `fetch_fmp_ratios` catch specific
  exception types instead of bare `Exception`. FMP failures are logged without
  the request URL, which contains the API key.
- Magic numbers and column names moved to `constants.py` (same values).
- README rewritten: architecture diagram, TA-Lib setup per platform,
  `print`-based quickstart (the old one used Colab-only `display()`), API
  reference.
- `main.py`: formatted, unused imports removed, `config.json` opened with a
  context manager, and `src/` added to `sys.path` so `streamlit run main.py`
  works without installing. App behaviour is unchanged.

### Removed
- `setup.py` (replaced by `pyproject.toml`).
- Import-time `sys.path` manipulation and the double import of
  `fundamental_analyzer`. `analyzer.fundamental` is now an instance of the
  exported `FundamentalAnalyser` class.
- Dead code: a commented-out copy of `get_latest_candlestick_patterns`, unused
  imports, six duplicate keys in the candlestick pattern table (no effect on
  results), and committed `__pycache__` files.

## [0.0.0.1] - 2026-02-20

- Initial release: `StockTechnicalAnalyzer`, `FundamentalAnalyser` and the
  Streamlit chat app.

[Unreleased]: https://github.com/maheshrajbhar90/EdgeQuantAI/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/maheshrajbhar90/EdgeQuantAI/compare/a1feaa5...v0.1.0
[0.0.0.1]: https://github.com/maheshrajbhar90/EdgeQuantAI/tree/a1feaa5
