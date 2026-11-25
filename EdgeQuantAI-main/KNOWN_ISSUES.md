# Known issues

Bugs and inconsistencies found during the 0.1.0 refactor. The refactor itself
was behaviour-preserving. Items marked **✅ Fixed** have since been fixed, each in
its own commit with a regression test in `tests/test_known_issue_fixes.py`. Where
a fix makes the package differ from the original code, the matching test in
`tests/test_differential.py` is marked `divergence("<ID>", ...)`. Open items are
still present, and the golden tests pin their current behaviour.

Locations are given as **original** (`EdgeQuantAI/EdgeQuantAI.py` or
`EdgeQuantAI/fundamental_analyzer.py` at commit `811823c`) and **now** (paths
under `src/stock_technical_analyzer/`).

Severity: 🔴 wrong results or crashes · 🟠 surprising behaviour · 🟡 cosmetic or docs.

---

## A. Data fetching

### A1 🔴 Exchange suffix is appended even when the ticker already has it — ✅ Fixed
- **Status:** fixed in commit `7246761` (`fix(data): don't append the exchange suffix twice (A1)`).
  `data.to_yahoo_symbol` now skips the suffix when the ticker already ends with
  `.NS`/`.BO` (or the configured suffix), compared case-insensitively. It's used by
  `fetch_ohlc`, the multi-ticker pipeline and `FundamentalAnalyser.fetch_yf_financials`.
- **Original:** `EdgeQuantAI.py:46`, `:432` · **Now:** `data.py:75`, `analyzer.py:236`
- **Problem:** `ticker + exchange_suffix` is unconditional. `fetch_ohlc("TCS.NS")`
  requests `TCS.NS.NS`, which returns nothing. The old README example
  (`["RELIANCE", "TCS.NS"]`) hits exactly this. Pinned by
  `test_fetch_ohlc_appends_suffix_even_if_present`.
- **Suggested fix:** append only when `not ticker.upper().endswith(exchange_suffix.upper())`.

### A2 🟠 Daily bars are time-shifted to 05:30
- **Original:** `EdgeQuantAI.py:62-66`, `:464-468` · **Now:** `data.py:84`, `data.py:126`
- **Problem:** yfinance returns *naive* dates for daily bars. `pd.to_datetime(..., utc=True)`
  treats them as UTC midnight, and converting to Asia/Kolkata gives `05:30:00` on
  every daily bar. Pinned by `test_fetch_ohlc_daily_dates_shift_to_0530`.
- **Suggested fix:** convert only tz-aware indexes; leave naive daily dates unchanged.

### A3 🟠 Two different normalisation paths
- **Original:** `fetch_ohlc` (`:44-70`) vs. `get_latest_candlestick_patterns` (`:439-482`)
  · **Now:** `data.fetch_ohlc` vs. `data.prepare_downloaded_ohlc`
- **Problem:** `fetch_ohlc` raises `IndexError` on single-level columns, does not coerce
  bad dates and does not check for required columns. The multi-ticker pipeline handles
  all three and does not reuse `fetch_ohlc`. Pinned by `test_fetch_ohlc_flat_columns_raises`
  and `test_get_latest_candlestick_patterns_flat_columns_ok`.
- **Suggested fix:** route both through `prepare_downloaded_ohlc` and have `fetch_ohlc`
  return `None` instead of raising.

### A4 🟡 Default `period` is `"5y"` but the docs said `"3y"` (and the example `"1y"`)
- **Original:** `EdgeQuantAI.py:32` · **Now:** `constants.py:15`
- **Problem:** the old README's "Class Structure" listed `period="3y"`. The code has
  always defaulted to `"5y"`. The new README documents the real default.
- **Suggested fix:** decide on one default. `"5y"` is fine: the indicators need ≥ 200 bars.

## B. Multi-ticker pipeline (`get_latest_candlestick_patterns` / `main`)

### B1 🔴 `KeyError` when no ticker has any candlestick match — ✅ Fixed
- **Status:** fixed in commit `5ba2ff5` (`fix(patterns): always add Pattern/Code columns (B1)`).
  `identify_candlestick_patterns` now always returns `Pattern` (object, NaN) and
  `Code` (float64, NaN) columns, so the merge can't fail.
- **Original:** `EdgeQuantAI.py:540-545` · **Now:** `analyzer.py:279`
- **Problem:** `Pattern`/`Code` only exist if some pattern matched somewhere in the
  history. If none did, `final_result_df[["Date", "Pattern", "Code", "Ticker"]]`
  raises `KeyError: "['Pattern', 'Code'] not in index"`. The merge runs outside the
  per-ticker `try`, so the error reaches the caller (verified by forcing
  `identify_candlestick_patterns` to return the input unchanged).
- **Suggested fix:** `final_result_df.reindex(columns=[...])` before the merge, or
  always create both columns in `identify_candlestick_patterns`.

### B2 🟠 Tickers without a signal disappear, unless no ticker has one
- **Now:** `analyzer.py` `_merge_patterns_and_signals`
- **Problem:** the merge is a *left* join from the signal rows, so a ticker with no
  signal on its last bar is silently dropped (e.g. `main(["RELIANCE", "TCS", "INFY"])`
  can return two rows). If *no* ticker has a signal, the raw pattern rows come back
  instead, with a different column set. The Streamlit app then answers "No technical
  data available" for valid symbols that simply have no signal.
- **Suggested fix:** left-join signals onto the pattern rows, so every processed ticker
  appears, and add a boolean `Has_Signal` column.

### B3 🟠 `Change%` holds a fraction, not a percentage, rounded to 2 dp
- **Original:** `EdgeQuantAI.py:179`, `:230`, `:568` · **Now:** `indicators.py`
  (`Change`), `signals.py` (`Change%`), `analyzer.py:355`
- **Problem:** `Change` is `pct_change()`, e.g. `0.0155` for a 1.55% move. `main()`
  rounds it to `0.02`, so the LLM sees `Change%: 0.02`, which is wrong by 100× and
  imprecise.
- **Suggested fix:** store `pct_change() * 100` under `Change%`, or rename the key to
  `Change` and round it to 4 dp.

### B4 🟡 `round(2)` warns about the datetime column
- **Now:** `analyzer.py:355`
- **Problem:** `DataFrame.round` emits `UserWarning: obj.round has no effect with datetime`.
  Since the C1 fix, `main()` hides exactly this warning around the call.
- **Suggested fix:** round only the numeric columns: `df.round({col: 2 for col in numeric_cols})`.

## C. Library hygiene

### C1 🔴 Importing the library silences *all* warnings process-wide — ✅ Fixed
- **Status:** fixed in commit `cccfd34` (`fix: stop silencing all warnings on import (C1)`). The
  module-level filter is gone. The only warning the library itself triggers
  (B4's `round` datetime `UserWarning` in `main()`) is suppressed around that one
  call, by category and message.
- **Original:** `EdgeQuantAI.py:9-10` · **Was:** `__init__.py:16`
- **Problem:** `warnings.filterwarnings("ignore")` runs at import time. It hides
  deprecation and pandas warnings for the whole application, not just this library.
- **Suggested fix:** delete it. Where specific warnings must be suppressed, wrap the
  call in `with warnings.catch_warnings(): warnings.simplefilter("ignore", SomeWarning)`.

### C2 🟠 `FundamentalAnalyser` ignores the analyzer's `exchange_suffix`
- **Original:** `EdgeQuantAI.py:33-36` · **Now:** `analyzer.py:55`
- **Problem:** `StockTechnicalAnalyzer(exchange_suffix="")` still builds a
  `FundamentalAnalyser` with `".NS"`. Pinned by `test_init_custom`.
- **Suggested fix:** pass `exchange_suffix=exchange_suffix`.

## D. Indicators, patterns and signals

### D1 🟠 Only the *last* matching candlestick pattern is kept
- **Original:** `EdgeQuantAI.py:349-353` · **Now:** `patterns.py`
- **Problem:** patterns are applied in list order and each match overwrites
  `Pattern`/`Code` on that bar, so the result depends on list position rather than
  pattern significance. The original dict also listed six patterns twice
  (`ladder_bottom`, `on_neck`, `piercing`, `rickshaw_man`, `rise_fall_3_methods`,
  `separating_lines`). Those repeats were removed, which cannot change results (see
  the comment in `constants.py`).
- **Suggested fix:** collect all matches per bar (e.g. `"doji|spinning_top"`) or use an
  explicit priority order.

### D2 🟡 Edge cases in the direction labels
- **Now:** `signals.py`
- **Problem:**
  - `ATR_Direction` is `"Decreasing"` on the first bar (NaN diff) and when ATR is unchanged.
  - `bb_direction` returns `"Bearish"` when `Close` is NaN or exactly equal to the middle band.
  - `stoch_direction` returns `"Bearish"` when %K equals %D.

  All are pinned by parametrised tests.
- **Suggested fix:** return `"Neutral"` for NaN or equal values.

### D3 🟡 The prompt names indicators the data doesn't contain
- **Now:** `prompts.py` (`SIMPLE_TEMPLATE`)
- **Problem:** the prompt says *"Evaluate short-term trend (EMA/SMA 5, 10, 20)"*, but the
  data has EMA5/EMA9/EMA26 and SMA50/SMA200.
- **Suggested fix:** change the wording to "EMA 5/9/26". This changes the prompt text,
  so regenerate the `build_prompt_*.txt` snapshots.

## E. Prompt formatting

### E1 🟠 `textwrap.dedent` runs *after* the metrics are interpolated
- **Original:** `EdgeQuantAI.py:612`, `:618-692` · **Now:** `prompts.py`
  (`generate_technical_prompt`)
- **Problem:** metric lines are joined with a 5-space prefix and inserted into an
  8-space-indented template before dedenting. Dedent therefore strips only 5 spaces:
  every prompt line keeps a 3-space indent, only the first metric is indented, and the
  rest start at column 0 (see `tests/golden/build_prompt_AAA.txt`). With one metric or
  none, the margin changes again.
- **Suggested fix:** dedent the template first, then substitute:
  `textwrap.dedent(TEMPLATE).strip().format(...)`.

## F. Fundamental analyser (`fundamental.py`)

### F1 🔴 Debt lookup reads *columns*, not rows — ✅ Fixed
- **Status:** fixed in commit `7fed69d` (`fix(fundamental): read debt from balance-sheet rows (F1)`).
  `Long Term Debt` + `Short Term Debt` are now read from the latest column's rows; a
  total of 0 still falls back to `info["totalDebt"]`.
- **Original:** `fundamental_analyzer.py:71-74` · **Now:** `fundamental.py:156`
- **Problem:** `balance.get("Long Term Debt", ...)` looks up a *column*, but statement
  line items are *rows*. It always yields `0 + 0`, so `total_debt` always falls back
  to `info["totalDebt"]`. Pinned by `fundamental_compute_ratios.json`.
- **Suggested fix:** use `_cell(balance, LONG_TERM_DEBT, bc) or 0`.

### F2 🔴 Statement row labels likely don't match current yfinance
- **Now:** `fundamental.py:28-37`
- **Problem:** `"Total Stockholder Equity"`, `"Total Cash From Operating Activities"`
  and `"Capital Expenditures"` are older yfinance labels. Current versions appear to
  use names like `"Stockholders Equity"`, `"Operating Cash Flow"` and
  `"Capital Expenditure"`. If so, `total_equity`, `operating_cf`, `fcf`, `roe` and
  `roce` are always `None`. Check against live `Ticker(...).balance_sheet.index`.
  *Checked on RELIANCE.NS (Nov 2026):* `Total Stockholder Equity` and
  `Short Term Debt` are absent; the real rows are `Stockholders Equity` and
  `Current Debt` (`Long Term Debt` and `Total Debt` exist). After the F1 fix, debt
  therefore picks up long-term debt only, until this label issue is fixed.
- **Suggested fix:** try a list of candidate labels per item.

### F3 🟠 FCF sign
- **Now:** `fundamental.py` (`fcf = operating_cf - capex`)
- **Problem:** yfinance usually reports capital expenditure as a *negative* number, in
  which case `ocf - capex` overstates free cash flow. Verify with live data.
- **Suggested fix:** `operating_cf + capex` if capex is negative, or `operating_cf - abs(capex)`.

### F4 🟡 `earnings` is fetched but never used
- **Now:** `fundamental.py:108`
- **Problem:** `fetch_yf_financials` reads `tk.earnings`, which costs an extra
  network call, and `compute_ratios` never uses it.
- **Suggested fix:** drop it from the dict, which changes the dict's keys.

## G. Streamlit app and repository

### G1 🔴 `main.py` crashes without `config.json`, even when Streamlit secrets are set — ✅ Fixed
- **Status:** fixed in commit `8d27df5` (`fix(app): load keys without config.json; stop tracking it (G1, G2)`).
  The new `app_config.py` reads each key from `st.secrets`, then environment variables
  (`HF_TOKEN`, `OPENAI_API_KEY`, `FMP_API_KEY`), then `config.json` only if the file exists.
- **Now:** `main.py:38`
- **Problem:** `config.json` is loaded unconditionally before the
  `st.secrets` → `config.json` fallback logic, so it raises `FileNotFoundError`
  on deployments that use only secrets.
- **Suggested fix:** delete the unconditional load (lines 36-38) but keep `working_dir`,
  which `load_nse_symbols` uses. The fallback below already handles a missing file.

### G2 🔴 `config.json` is tracked despite being in `.gitignore` — ✅ Fixed
- **Status:** fixed in the same commit as G1. `config.json` is no longer tracked
  (`git rm --cached`), `config.example.json` holds placeholders only, and both
  `.gitignore` files cover `config.json` and `.streamlit/secrets.toml`.
  **Untracking doesn't remove old versions from git history. Rotate any key that
  was ever committed.**
- **Problem:** the file is committed with an empty key. A developer who fills in a real
  key locally will see it as a modified file and could commit the secret.
- **Suggested fix:** `git rm --cached config.json`, then commit `config.example.json`.

### G3 🟠 `requirements.txt` (used by Streamlit Cloud)
- **Problem:** it lists `pandas-ta`, which nothing imports, and
  `--extra-index-url https://pypi.debian.net/`, an unusual extra index and a
  dependency-confusion risk. Nothing is pinned.
- **Suggested fix:** drop both, and pin, or install the package with `.` / `-e .` and
  add only the app's extra dependencies.

### G4 🟡 `.gitignore` lists `assets/nse_symbols.csv`, which the app needs (and is tracked)
- **Suggested fix:** remove the entry.

### G5 🟡 The Python project lives in an `EdgeQuantAI-main/` sub-folder
- **Problem:** this looks like an extracted GitHub zip. CI and pre-commit need
  `working-directory`/`cd` workarounds, and `.devcontainer` `openFiles: README.md`
  points at a file that doesn't exist at the repo root.
- **Suggested fix:** move the project to the repository root, then update the Streamlit
  Cloud "main file path", `.devcontainer/devcontainer.json`, `ci.yml` and
  `.pre-commit-config.yaml`.

---

## Intentional, observable differences in 0.1.0

These are not bugs. They are the only places where 0.1.0 is observably different from
the original. All return values, dtypes, column orders and exceptions are unchanged.

1. **`print` → `logging`** (requested). Diagnostics now go to the
   `stock_technical_analyzer.*` loggers instead of stdout. The library adds no handlers,
   so, as with any Python logger, WARNING and above still reach stderr until your app
   configures logging. `generate_technical_prompt` no longer prints the whole prompt; it
   logs it at DEBUG.
2. **Import-time `sys.path` hack removed.** Importing the original package appended
   `EdgeQuantAI/` to `sys.path` and loaded `fundamental_analyzer` a *second* time as a
   top-level module. As a result, `isinstance(analyzer.fundamental, EdgeQuantAI.FundamentalAnalyser)`
   was **False**. It is now True, and a bare `import fundamental_analyzer` no longer works.
3. **Missing TA-Lib** now raises `ModuleNotFoundError` (still an `ImportError`) with
   install instructions, instead of the bare `No module named 'talib'`.
4. **Exception handling narrowed** in `FundamentalAnalyser.safe_div`
   (`TypeError`/`ArithmeticError`/`ValueError`) and `fetch_fmp_ratios`
   (`requests.RequestException`/`ValueError`). Both previously caught *every*
   `Exception`. Every failure the original could realistically hit (bad operand types,
   zero division, network errors, invalid JSON) is still caught.
5. **`EdgeQuantAI.__version__`** is now `"0.1.0"` (was `"0.0.0.1"`).
6. **Running uninstalled:** `from EdgeQuantAI import ...` from the project folder now
   needs `pip install -e .` (or `src/` on `sys.path`). `main.py` adds `src/` itself, so
   `streamlit run main.py` works without installing.
