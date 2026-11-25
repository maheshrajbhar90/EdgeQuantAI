"""Regenerate the committed synthetic OHLCV fixture (``ohlcv.csv``).

The fixture is a seeded random walk so that tests are deterministic and contain
no third-party market data. It is committed to the repository; this script only
exists to document how it was produced. Re-running it must produce an identical
file.

Usage::

    python tests/fixtures/make_fixture.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROWS = 320
SEED = 20240101
OUT = Path(__file__).with_name("ohlcv.csv")


def build() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    dates = pd.bdate_range("2023-01-02", periods=ROWS)
    returns = rng.normal(0.0005, 0.015, ROWS)
    close = 1000.0 * np.exp(np.cumsum(returns))
    open_ = close * (1 + rng.normal(0, 0.006, ROWS))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, ROWS)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, ROWS)))
    volume = rng.integers(800_000, 1_500_000, ROWS)

    # A handful of exact dojis so several candlestick detectors fire.
    for i in (60, 120, 180, 240):
        open_[i] = close[i]
    # Volume spike on the final bar so ``generate_signal`` returns a dict.
    volume[-1] = 4_000_000

    return pd.DataFrame(
        {
            "Date": dates.strftime("%Y-%m-%d"),
            "Open": np.round(open_, 2),
            "High": np.round(high, 2),
            "Low": np.round(low, 2),
            "Close": np.round(close, 2),
            "Volume": volume.astype("int64"),
        }
    )


if __name__ == "__main__":
    build().to_csv(OUT, index=False)
    print(f"wrote {OUT}")
