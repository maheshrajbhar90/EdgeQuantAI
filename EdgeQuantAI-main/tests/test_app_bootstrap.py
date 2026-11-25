"""Tests for the ``src/`` bootstrap used by the Streamlit app (``app_bootstrap.py``)."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
BOOTSTRAP = PROJECT / "app_bootstrap.py"

# Runs in a fresh interpreter so pytest's own ``pythonpath = ["src", ...]``
# can't mask the result. ``-I`` (isolated mode, all supported Pythons) keeps the cwd off sys.path.
_PROBE = textwrap.dedent(
    """
    import importlib.util, json, sys
    spec = importlib.util.spec_from_file_location("app_bootstrap", {bootstrap!r})
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    {setup}
    before = list(sys.path)
    added = mod.ensure_package_importable()
    path_added = sys.path[: len(sys.path) - len(before)]  # entries prepended
    import EdgeQuantAI, stock_analyzer, stock_technical_analyzer as sta
    modules = [
        name for name, m in list(sys.modules.items())
        if (getattr(m, "__file__", None) or "").replace("\\\\", "/").endswith(
            "stock_technical_analyzer/__init__.py")
    ]
    print(json.dumps({{
        "added": added,
        "path_added": path_added,
        "package_modules": modules,
        "same_class": EdgeQuantAI.StockTechnicalAnalyzer is sta.StockTechnicalAnalyzer
                      is stock_analyzer.StockTechnicalAnalyzer,
        "isinstance": isinstance(sta.StockTechnicalAnalyzer().fundamental,
                                 EdgeQuantAI.FundamentalAnalyser),
        "file": sta.__file__,
    }}))
    """
)


def _probe(setup: str = "") -> dict[str, object]:
    code = _PROBE.format(bootstrap=str(BOOTSTRAP), setup=setup)
    out = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True, cwd="/"
    )
    result: dict[str, object] = json.loads(out.stdout.strip().splitlines()[-1])
    return result


def test_installed_package_is_not_loaded_twice() -> None:
    # The test environment has the package installed (pip install -e .).
    result = _probe()
    assert result["added"] is False
    assert result["path_added"] == []
    assert result["package_modules"] == ["stock_technical_analyzer"]
    assert result["same_class"] is True
    assert result["isinstance"] is True


def test_uninstalled_package_falls_back_to_src() -> None:
    # Simulate "not installed": hide the package from every import finder.
    setup = textwrap.dedent(
        """
        import importlib.util as _u
        _real = _u.find_spec
        _u.find_spec = lambda name, *a, **k: None if name == mod.PACKAGE else _real(name, *a, **k)
        """
    )
    result = _probe(setup)
    assert result["added"] is True
    assert result["path_added"] == [str(PROJECT / "src")]
    assert result["package_modules"] == ["stock_technical_analyzer"]
    assert result["isinstance"] is True
    assert str(result["file"]).startswith(str(PROJECT / "src"))
