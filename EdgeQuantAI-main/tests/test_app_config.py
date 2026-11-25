"""Tests for the Streamlit app's key loading (KNOWN_ISSUES G1).

Only dummy values are used; no real key is ever read or written.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

PROJECT = Path(__file__).resolve().parent.parent
KEY_ENV_VARS = ("HF_TOKEN", "API_KEY", "OPENAI_API_KEY", "FMP_API_KEY")


def _load_app_config() -> ModuleType:
    spec = importlib.util.spec_from_file_location("app_config", PROJECT / "app_config.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# load_settings: st.secrets -> environment -> config.json (only if present)
# --------------------------------------------------------------------------- #
def test_g1_missing_config_file_is_fine(tmp_path: Path) -> None:
    cfg = _load_app_config()
    settings = cfg.load_settings(
        secrets={}, environ={"HF_TOKEN": "dummy-hf"}, config_path=tmp_path / "nope.json"
    )
    assert settings == {"API_KEY": "dummy-hf", "OPENAI_API_KEY": None, "FMP_API_KEY": None}


def test_g1_precedence_secrets_then_env_then_file(tmp_path: Path) -> None:
    cfg = _load_app_config()
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"API_KEY": "file-hf", "OPENAI_API_KEY": "file-oa", "FMP_API_KEY": "file-fmp"})
    )
    settings = cfg.load_settings(
        secrets={"API_KEY": "secret-hf"},
        environ={"HF_TOKEN": "env-hf", "OPENAI_API_KEY": "env-oa"},
        config_path=path,
    )
    assert settings == {
        "API_KEY": "secret-hf",
        "OPENAI_API_KEY": "env-oa",
        "FMP_API_KEY": "file-fmp",
    }


@pytest.mark.parametrize("value", ["", "   ", "<your-hugging-face-token>", None])
def test_g1_empty_and_placeholder_values_are_unset(tmp_path: Path, value: Any) -> None:
    cfg = _load_app_config()
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"API_KEY": value}))
    settings = cfg.load_settings(secrets={"API_KEY": value}, environ={}, config_path=path)
    assert settings["API_KEY"] is None


def test_g1_unreadable_config_file_is_ignored(tmp_path: Path) -> None:
    cfg = _load_app_config()
    path = tmp_path / "config.json"
    path.write_text("{not json")
    assert cfg.load_settings(secrets={}, environ={}, config_path=path)["API_KEY"] is None


def test_g1_read_streamlit_secrets_tolerates_missing_secrets() -> None:
    cfg = _load_app_config()

    class NoSecrets:
        def get(self, key: str, default: Any = None) -> Any:
            raise FileNotFoundError("No secrets files found")

    class SomeSecrets:
        def get(self, key: str, default: Any = None) -> Any:
            return {"API_KEY": "dummy"}.get(key, default)

    assert cfg.read_streamlit_secrets(NoSecrets()) == {}
    assert cfg.read_streamlit_secrets(SomeSecrets()) == {"API_KEY": "dummy"}


def test_g1_example_config_holds_placeholders_only() -> None:
    cfg = _load_app_config()
    example = json.loads((PROJECT / "config.example.json").read_text())
    assert set(example) == set(cfg.SETTINGS)
    settings = cfg.load_settings(
        secrets={}, environ={}, config_path=PROJECT / "config.example.json"
    )
    assert all(v is None for v in settings.values())


# --------------------------------------------------------------------------- #
# End to end: run the real main.py without config.json (stubbed Streamlit)
# --------------------------------------------------------------------------- #
_STREAMLIT_STUB = """
import json, os, sys

class _Secrets:
    def get(self, key, default=None):
        data = json.loads(os.environ.get("STUB_SECRETS", "null"))
        if data is None:
            raise FileNotFoundError("No secrets files found")
        return data.get(key, default)

class _State(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as exc:
            raise AttributeError(k) from exc
    def __setattr__(self, k, v):
        self[k] = v

class _Ctx:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def markdown(self, *a, **k): pass

secrets = _Secrets()
session_state = _State()
def set_page_config(**k): pass
def image(*a, **k): pass
def markdown(*a, **k): pass
def divider(): pass
def cache_data(fn): return fn
def chat_input(*a, **k): return None
def chat_message(role): return _Ctx()
def error(msg): print("ST_ERROR:", msg, file=sys.stderr)
def stop(): raise SystemExit(3)
"""

_HF_STUB = """
import os, sys
class InferenceClient:
    def __init__(self, api_key=None):
        ok = api_key is not None and api_key == os.environ.get("EXPECTED_KEY")
        print("HF_CLIENT_KEY_OK=" + str(ok), file=sys.stderr)
"""

_PIL_STUB = """
def open(path):
    raise FileNotFoundError(path)
"""


@pytest.fixture
def app_dir(tmp_path: Path) -> Path:
    """A copy of the app without config.json, plus stub third-party modules."""
    for name in ("main.py", "app_bootstrap.py", "app_config.py"):
        if (PROJECT / name).exists():
            shutil.copy(PROJECT / name, tmp_path / name)
    (tmp_path / "assets").mkdir()
    shutil.copy(PROJECT / "assets" / "nse_symbols.csv", tmp_path / "assets" / "nse_symbols.csv")
    stubs = tmp_path / "stubs"
    (stubs / "streamlit").mkdir(parents=True)
    (stubs / "streamlit" / "__init__.py").write_text(_STREAMLIT_STUB)
    (stubs / "huggingface_hub").mkdir()
    (stubs / "huggingface_hub" / "__init__.py").write_text(textwrap.dedent(_HF_STUB))
    (stubs / "PIL").mkdir()
    (stubs / "PIL" / "__init__.py").write_text("")
    (stubs / "PIL" / "Image.py").write_text(textwrap.dedent(_PIL_STUB))
    assert not (tmp_path / "config.json").exists()
    return tmp_path


def _run_app(app_dir: Path, **env: str) -> subprocess.CompletedProcess[str]:
    clean = {k: v for k, v in os.environ.items() if k not in KEY_ENV_VARS}
    clean["PYTHONPATH"] = str(app_dir / "stubs")
    clean.update(env)
    return subprocess.run(
        [sys.executable, str(app_dir / "main.py")],
        capture_output=True,
        text=True,
        cwd=app_dir,
        env=clean,
        check=False,
        timeout=120,
    )


def test_g1_main_runs_without_config_json_using_env(app_dir: Path) -> None:
    result = _run_app(app_dir, HF_TOKEN="dummy-env-token", EXPECTED_KEY="dummy-env-token")
    assert result.returncode == 0, result.stderr[-2000:]
    assert "HF_CLIENT_KEY_OK=True" in result.stderr


def test_g1_main_prefers_streamlit_secrets(app_dir: Path) -> None:
    result = _run_app(
        app_dir,
        STUB_SECRETS=json.dumps({"API_KEY": "dummy-secret-token"}),
        HF_TOKEN="dummy-env-token",
        EXPECTED_KEY="dummy-secret-token",
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert "HF_CLIENT_KEY_OK=True" in result.stderr


def test_g1_main_without_any_key_stops_with_message(app_dir: Path) -> None:
    result = _run_app(app_dir)
    assert result.returncode == 3, result.stderr[-2000:]
    assert "ST_ERROR: API Key not found" in result.stderr
    assert "FileNotFoundError" not in result.stderr
