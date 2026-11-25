"""Resolve the Streamlit app's API keys without requiring ``config.json``.

Each setting is looked up in this order, and the first usable value wins:

1. Streamlit secrets (``st.secrets``; Streamlit Cloud or ``.streamlit/secrets.toml``)
2. Environment variables
3. ``config.json`` next to ``main.py``, **only if the file exists**

Empty strings and ``<placeholder>`` values (as in ``config.example.json``) count
as unset. Values are never logged.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

logger = logging.getLogger(__name__)

#: Setting name -> environment variable(s) that can supply it.
SETTINGS: Final[dict[str, tuple[str, ...]]] = {
    "API_KEY": ("HF_TOKEN",),  # Hugging Face token used by the chat app
    "OPENAI_API_KEY": ("OPENAI_API_KEY",),
    "FMP_API_KEY": ("FMP_API_KEY",),
}


def _usable(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text: str = value.strip()
    if not text or (text.startswith("<") and text.endswith(">")):
        return None
    return text


def read_streamlit_secrets(secrets: Any) -> dict[str, str]:
    """Return the known settings present in ``st.secrets``; ``{}`` if there are none.

    ``st.secrets`` raises when no secrets file exists, so any error means "no secrets".
    """
    found: dict[str, str] = {}
    try:
        for name in SETTINGS:
            value = _usable(secrets.get(name))
            if value is not None:
                found[name] = value
    except Exception:  # noqa: BLE001 - Streamlit raises various errors when unconfigured
        return {}
    return found


def _read_config_file(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("Ignoring unreadable config file %s", path)
        return {}
    return data if isinstance(data, dict) else {}


def load_settings(
    secrets: Mapping[str, Any], environ: Mapping[str, str], config_path: Path
) -> dict[str, str | None]:
    """Resolve every setting in :data:`SETTINGS` (secrets, then env, then file).

    Args:
        secrets: Values from Streamlit secrets (see :func:`read_streamlit_secrets`).
        environ: Environment, usually ``os.environ``.
        config_path: Path to ``config.json``; a missing file is fine.

    Returns:
        ``{setting: value or None}``.
    """
    file_values = _read_config_file(config_path)
    resolved: dict[str, str | None] = {}
    for name, env_vars in SETTINGS.items():
        candidates = [secrets.get(name), *(environ.get(v) for v in env_vars), file_values.get(name)]
        resolved[name] = next((v for v in map(_usable, candidates) if v is not None), None)
    return resolved


def load_app_settings(st_secrets: Any, app_dir: Path) -> dict[str, str | None]:
    """Convenience wrapper used by ``main.py``."""
    return load_settings(
        secrets=read_streamlit_secrets(st_secrets),
        environ=os.environ,
        config_path=app_dir / "config.json",
    )
