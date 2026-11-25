"""Make the library importable for ``streamlit run main.py`` without installing it.

Kept separate from ``main.py`` (which runs Streamlit calls at import time) so the
logic can be unit-tested.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PACKAGE = "stock_technical_analyzer"
SRC_DIR = Path(__file__).resolve().parent / "src"


def ensure_package_importable(src_dir: Path = SRC_DIR) -> bool:
    """Add ``src_dir`` to ``sys.path`` only if the package can't already be imported.

    An installed (or editable-installed) package is left alone, so it is never
    loaded a second time from a different path.

    Args:
        src_dir: Directory containing the ``stock_technical_analyzer`` package.

    Returns:
        ``True`` if ``src_dir`` was added to ``sys.path``, ``False`` otherwise.
    """
    if importlib.util.find_spec(PACKAGE) is not None:
        return False
    sys.path.insert(0, str(src_dir))
    return True
