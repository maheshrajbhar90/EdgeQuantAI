"""Import TA-Lib with an actionable error message when it is missing.

TA-Lib is a Python wrapper around a C library. Since TA-Lib 0.6 the PyPI wheels
bundle the C library for common platforms, but source builds (and some older
Python/OS combinations) still need it installed separately.
"""

from __future__ import annotations

from typing import Any

_INSTALL_HELP = """\
TA-Lib is required by stock_technical_analyzer but could not be imported.

Install it with:

    pip install "TA-Lib>=0.6"

Prebuilt wheels (with the C library bundled) exist for Linux, macOS and Windows
on recent Python versions. If pip falls back to building from source, install
the TA-Lib C library first:

    macOS:          brew install ta-lib
    Debian/Ubuntu:  download ta-lib_<version>_amd64.deb from
                    https://github.com/ta-lib/ta-lib/releases and
                    `sudo dpkg -i` it
    Windows:        use the official installer / wheel from the release page
    Google Colab:   !pip install TA-Lib

See https://ta-lib.github.io/ta-lib-python/install.html for details.
"""

try:
    import talib as _talib
except ImportError as exc:
    raise ModuleNotFoundError(f"{_INSTALL_HELP}\nOriginal error: {exc}", name="talib") from exc

#: The TA-Lib module, typed as ``Any``: its bundled stubs only describe NumPy
#: inputs, but this package passes ``pandas.Series`` (TA-Lib's pandas wrapper
#: then returns index-aligned ``Series``), exactly as the original code did.
talib: Any = _talib

__all__ = ["talib"]
