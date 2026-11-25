# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
