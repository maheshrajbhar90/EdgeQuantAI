# Contributing

Thanks for your interest in improving EdgeQuantAI. Bug reports, fixes and new
features are all welcome.

## Development setup

```bash
git clone https://github.com/maheshrajbhar90/EdgeQuantAI.git
cd EdgeQuantAI
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

If `pip install` fails on TA-Lib, see the TA-Lib section of the
[README](README.md#ta-lib).

## Checks (the same as CI)

Run from the repository root:

```bash
ruff check . && ruff format --check .
mypy
pytest --cov
```

All three must pass. CI runs them on Python 3.10, 3.11 and 3.12. Older Pythons
resolve to pandas 2.x and newer ones to pandas 3.x, so check that your change
works with both.

## Tests and behaviour changes

The suite has three layers (see the README's *Development* section):

- **Golden tests** (`tests/test_golden_*.py` and `tests/golden/`) pin the exact
  output of every public method.
- **Differential tests** (`tests/test_differential.py`) compare the package to
  a frozen copy of the original implementation in `tests/legacy/`. **Never edit
  `tests/legacy/`.**
- **Unit tests** (`tests/test_modules.py`) and the doctests in `src/`.

A **refactor** must keep every test green without touching `tests/golden/`.

A **behaviour change**, such as fixing an item in
[KNOWN_ISSUES.md](KNOWN_ISSUES.md), must:

1. Regenerate only the affected snapshots: `UPDATE_GOLDEN=1 pytest -k <test>`.
2. Update or remove the matching differential test: it compares against the
   *original* behaviour, so it should fail for an intentional change.
3. Add an entry under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md).
4. Remove the item from `KNOWN_ISSUES.md`.

Tests must not touch the network. Use the `fake_yf` fixture in
`tests/conftest.py` for price data, and mock `requests`, `yfinance.Ticker` and
OpenAI.

## Style

- Formatting and linting: ruff (configured in `pyproject.toml`), line length 100.
- Type hints on everything; `mypy` runs in strict mode.
- Google-style docstrings on public functions, classes and methods.
- Put tunable numbers and column names in `constants.py`.
- Libraries log, they don't print: `logger = logging.getLogger(__name__)`.

## Commits and pull requests

- Use [Conventional Commits](https://www.conventionalcommits.org/), e.g.
  `fix: avoid double exchange suffix`, `refactor: extract pivot maths`,
  `docs: clarify TA-Lib setup`.
- Keep each PR focused: one behaviour change per PR.
- Describe *why* in the PR body, and link the KNOWN_ISSUES item if there is one.
